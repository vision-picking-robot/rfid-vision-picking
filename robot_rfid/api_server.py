import asyncio
from datetime import datetime
import json
import math
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator
import yaml

try:
    from .database import Database, MIN_PARTIAL_UID, SEED_TAGS, clean_uid, normalize_uid
    from .mobile_remote_ui import MANIFEST_JSON, MOBILE_REMOTE_HTML
    from .rfid_scanner import RFIDScanner
    from .services import ReaderBusy, ReaderUnavailable, enqueue_scan, scan_uid
except ImportError:
    from database import Database, MIN_PARTIAL_UID, SEED_TAGS, clean_uid, normalize_uid
    from mobile_remote_ui import MANIFEST_JSON, MOBILE_REMOTE_HTML
    from rfid_scanner import RFIDScanner
    from services import ReaderBusy, ReaderUnavailable, enqueue_scan, scan_uid


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class ScanEvent(StrictInput):
    # Raw reader value; may be partial (Bluetooth reader). Resolved against the DB in the route.
    uid: str
    quantity: int = Field(default=1, ge=1, le=10000)
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)

    @field_validator('uid')
    @classmethod
    def valid_uid(cls, value):
        value = clean_uid(value)
        if not MIN_PARTIAL_UID <= len(value) <= 14:
            raise ValueError(f'UID must contain {MIN_PARTIAL_UID}-14 hexadecimal characters')
        return value


class Progress(StrictInput):
    completed: int = Field(ge=0)
    status: str
    error: str | None = None


class HardwareOrMockScanRequest(StrictInput):
    uid: str | None = None
    quantity: int = Field(default=1, ge=1, le=10000)
    timeout_s: float = Field(default=1.5, gt=0.1, le=10.0)
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)

    @field_validator('uid')
    @classmethod
    def valid_uid(cls, value):
        return normalize_uid(value) if value is not None else None


class ScanModeInput(StrictInput):
    mode: Literal['external_reader', 'phone_nfc']


class BoxPlacedInput(StrictInput):
    box_slot: int = Field(default=1, ge=1, le=4)
    uid: str | None = None
    quantity: int = Field(default=1, ge=1, le=10000)
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)

    @field_validator('uid')
    @classmethod
    def valid_uid(cls, value):
        return normalize_uid(value) if value is not None else None


class MobileNfcTagInput(StrictInput):
    uid: str
    box_slot: int = Field(default=1, ge=1, le=4)
    quantity: int = Field(default=1, ge=1, le=10000)
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)

    @field_validator('uid')
    @classmethod
    def valid_uid(cls, value):
        return normalize_uid(value)


class MobileControlInput(StrictInput):
    command: Literal['start', 'pause', 'resume', 'home', 'emergency_stop', 'reset_stop', 'scan_dispatch']


class RobotLinkInput(StrictInput):
    """State the robot cycle (scripts/project_cycle.py) reports back to the phone."""
    mode: str = Field(default='cycle', min_length=1, max_length=32)
    state: str = Field(min_length=1, max_length=40)
    message: str | None = Field(default=None, max_length=300)
    ack_seq: int | None = Field(default=None, ge=0)
    ack_result: Literal['done', 'ignored', 'failed'] | None = None


class WorkItemReport(StrictInput):
    zone: int = Field(ge=1, le=4)
    product: str = Field(min_length=1, max_length=64)
    base: list[FiniteFloat] = Field(min_length=2, max_length=2)
    footprint_mm: list[FiniteFloat] | None = Field(default=None, min_length=2, max_length=2)
    short_axis_yaw_deg: FiniteFloat | None = None
    height_mm: FiniteFloat | None = None


class WorkItemsInput(StrictInput):
    source: str = Field(default='robot_cycle', min_length=1, max_length=32)
    revision: str | None = Field(default=None, max_length=64)
    items: list[WorkItemReport] = Field(max_length=16)


ROBOT_LINK_TIMEOUT_S = 3.0
# Commands only the robot cycle can carry out; the phone is told when no cycle is listening.
ROBOT_COMMANDS = ('start', 'pause', 'resume', 'home', 'scan_dispatch')


class GridLocateInput(StrictInput):
    pixel: list[FiniteFloat] | None = Field(default=None, min_length=2, max_length=2)
    base_xy: list[FiniteFloat] | None = Field(default=None, min_length=2, max_length=3)
    rows: int = Field(default=15, ge=1, le=50)
    cols: int = Field(default=15, ge=1, le=50)
    product: str = Field(default='snack_pepero', min_length=1, max_length=64)
    measured_height_mm: FiniteFloat | None = Field(default=None, gt=0, le=500)


def _picking_config(app: FastAPI):
    """Work-area config: PICKING_CONFIG, else the controller's, else the real calibration if exported."""
    from vision_picking.paths import ROOT
    env = os.getenv('PICKING_CONFIG')
    if env:
        return json.loads(Path(env).read_text(encoding='utf-8'))
    ctrl = getattr(app.state, 'controller', None)
    if ctrl is not None:
        return ctrl.config
    real = ROOT / 'config/integration.real.json'
    path = real if real.is_file() else ROOT / 'config/integration.json'
    return json.loads(path.read_text(encoding='utf-8'))


def _load_grid_context(app: FastAPI):
    from vision_picking.paths import ROOT
    from vision_picking.pick_plane import Calibration, PickPlane
    ctrl = getattr(app.state, 'controller', None)
    cfg = _picking_config(app)
    if ctrl is not None:
        poses = ctrl.poses
        products = ctrl.products
    else:
        poses = yaml.safe_load((ROOT / 'config/poses.yaml').read_text(encoding='utf-8'))
        products = yaml.safe_load((ROOT / 'config/products.yaml').read_text(encoding='utf-8'))['products']
    plane = PickPlane(Calibration(**cfg['calibration']))
    return plane, poses, products, cfg


def _work_area(app: FastAPI, rows: int, cols: int):
    """Work-area geometry in robot BASE mm for the phone: true 4-corner outline and N x M grid lines."""
    plane, poses, products, cfg = _load_grid_context(app)
    corners = [[round(v, 1) for v in p[:2]] for p in plane.xyz]
    # (rows+1) x (cols+1) lattice of grid-line intersections on the (projective) work quad.
    lattice = []
    for r in range(rows + 1):
        line = []
        for c in range(cols + 1):
            base = plane.uv_to_base(c / cols, r / rows)
            line.append(None if base is None else [round(base[0], 1), round(base[1], 1)])
        lattice.append(line)
    side = lambda a, b: round(math.dist(corners[a], corners[b]), 1)  # noqa: E731
    zones = {str(k): v for k, v in ((cfg.get('depth_picking') or {}).get('zones') or {}).items()}
    names = {key: (val.get('display_name') or key) for key, val in products.items()}
    cal = cfg.get('calibration') or {}
    return {
        'rows': rows,
        'cols': cols,
        'corners_base_mm': corners,
        'lattice_base_mm': lattice,
        # Corner order is 1->2->3->4 around the area; grid columns run 1->2, rows run 1->4.
        'size_mm': {'col_axis_1_2': side(0, 1), 'row_axis_1_4': side(0, 3),
                    'opposite_4_3': side(3, 2), 'opposite_2_3': side(1, 2)},
        'cell_mm': [round((side(0, 1) + side(3, 2)) / 2 / cols, 1), round((side(0, 3) + side(1, 2)) / 2 / rows, 1)],
        'zones': zones,
        'product_names': {z: names.get(p, p) for z, p in zones.items()},
        'revision': cal.get('revision'),
        'calibration_verified': cfg.get('calibration_verified') is True and cfg.get('mock_mode') is False,
    }


def install_rfid_routes(app: FastAPI, db_path=None):
    db = Database(db_path or os.getenv('RFID_DB', 'rfid.db'))
    app.state.database = db
    mobile_state = {
        'scan_mode': 'external_reader',
        'robot_state': 'STANDBY',
        'paused': False,
        'emergency_stopped': False,
        'placed_boxes': {},
        'grid': {'rows': 15, 'cols': 15, 'active_cell': None},
        'last_completed_event': None,
        # Most recent tag read from any source (Windows bridge, dashboard, phone NFC), accepted or not.
        'scan_seq': 0,
        'last_scan': None,
        'events': [],
        # Commands for the robot cycle, consumed by seq (project_cycle MobileRemote polls these).
        'command_seq': 0,
        'commands': [],
        # Last report from the robot cycle; robot_connected is derived from its age.
        'robot_link': None,
        'work_items': None,
    }
    link_seen = {'monotonic': None}
    app.state.mobile_remote = mobile_state
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def database_lifespan(application):
        await asyncio.to_thread(db.initialize)
        async with previous_lifespan(application) as state:
            yield state

    app.router.lifespan_context = database_lifespan
    clients: set[asyncio.Queue] = set()

    def broadcast(packet):
        for queue in tuple(clients):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(packet)

    def record_mobile_event(kind: str, **payload):
        entry = {'kind': kind, 'timestamp': datetime.now().astimezone().isoformat(), **payload}
        mobile_state['events'] = (mobile_state['events'] + [entry])[-30:]
        return entry

    def note_scan(raw_uid, source, *, uid=None, product=None, task=None, created=None, error=None):
        """Remember the latest tag read so the dashboard and the phone can show it live."""
        mobile_state['scan_seq'] += 1
        entry = {
            'seq': mobile_state['scan_seq'],
            'timestamp': datetime.now().astimezone().isoformat(),
            'source': source,
            'raw_uid': raw_uid,
            'uid': uid,
            'product_name': (product or {}).get('product_name'),
            'target_box_id': (product or {}).get('target_box_id'),
            'task_id': (task or {}).get('task_id'),
            'accepted': error is None,
            'created': created,
            'error': error,
        }
        mobile_state['last_scan'] = entry
        # Clients poll it (GET /api/v1/last-scan, /api/v1/mobile/status); the /ws scan packets are unchanged.
        record_mobile_event('tag_scanned', **{k: v for k, v in entry.items() if k not in ('seq', 'timestamp')})
        return entry

    app.state.note_scan = note_scan  # other routes on this app (dashboard RFID buttons) report reads too

    @app.get('/api/v1/last-scan')
    async def last_scan():
        return {'last_scan': mobile_state['last_scan']}

    @app.get('/api/v1/tags')
    async def list_tags():
        return {'tags': await asyncio.to_thread(db.products)}

    async def resolve(raw):
        """Registered UID for a full or partial reader value: 422 malformed, 404 unknown, 409 ambiguous."""
        if not MIN_PARTIAL_UID <= len(clean_uid(raw)) <= 14:
            raise HTTPException(422, f'UID must contain {MIN_PARTIAL_UID}-14 hexadecimal characters')
        try:
            return await asyncio.to_thread(db.resolve_uid, raw)
        except KeyError as exc:
            raise HTTPException(404, f'Unknown tag: {exc.args[0] if exc.args else raw}') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/v1/tags/{uid}')
    async def get_tag(uid: str):
        product = await asyncio.to_thread(db.product, await resolve(uid))
        if product is None:
            raise HTTPException(404, 'Unknown tag')
        return product

    @app.post('/api/v1/scan-event')
    async def scan(event: ScanEvent):
        try:
            uid = await resolve(event.uid)
        except HTTPException as exc:
            reason = {404: '등록되지 않은 태그입니다', 409: '등록되지 않은 태그입니다 (여러 태그와 일부만 일치)',
                      422: 'UID 형식이 아닙니다 (너무 짧거나 김)'}.get(exc.status_code, str(exc.detail))
            note_scan(event.uid, 'remote_reader', error=reason)
            raise
        product = await asyncio.to_thread(db.product, uid)
        try:
            task, created = await asyncio.to_thread(db.enqueue, uid, event.quantity, event.event_id)
        except KeyError as exc:
            note_scan(event.uid, 'remote_reader', uid=uid, error='Unknown tag')
            raise HTTPException(404, 'Unknown tag') from exc
        except ValueError as exc:
            note_scan(event.uid, 'remote_reader', uid=uid, product=product,
                      error='이미 대기/진행 중인 작업이 있습니다' if 'active task' in str(exc) else str(exc))
            raise HTTPException(409, str(exc)) from exc
        packet = {'type': 'scan', 'raw_uid': event.uid, 'uid': uid, 'task': task, 'product': product}
        if created:
            note_scan(event.uid, 'remote_reader', uid=uid, product=product, task=task, created=True)
            broadcast(packet)
        return {**packet, 'created': created}

    @app.post('/api/v1/rfid/scan')
    async def scan_reader_or_preset(body: HardwareOrMockScanRequest):
        try:
            normalized, source = await asyncio.to_thread(scan_uid, body.uid, body.timeout_s)
        except ReaderBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        except ReaderUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        try:
            task, created = await asyncio.to_thread(enqueue_scan, db, normalized, body.quantity, body.event_id)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown tag') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        product = await asyncio.to_thread(db.product, normalized)
        packet = {'type': 'scan', 'source': source, 'uid': normalized, 'task': task, 'product': product}
        if created:
            note_scan(normalized, source, uid=normalized, product=product, task=task, created=True)
            broadcast(packet)
        return {**packet, 'created': created}

    @app.get('/api/v1/current-task')
    async def current_task():
        return {'task': await asyncio.to_thread(db.current_task)}

    @app.patch('/api/v1/tasks/{task_id}')
    async def progress(task_id: str, body: Progress):
        try:
            await asyncio.to_thread(db.progress, task_id, body.completed, body.status, body.error)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown task') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        mobile_state['robot_state'] = body.status
        packet = {'type': 'task_progress', 'task_id': task_id, **body.model_dump()}
        broadcast(packet)
        if body.status == 'COMPLETED':
            haptic = {
                'type': 'task_completed_haptic',
                'task_id': task_id,
                'completed': body.completed,
                'vibrate': [200, 100, 250],
                'message': '✅ 물품 피킹 및 상자 적재 완료! 상자를 회수하세요.',
            }
            mobile_state['last_completed_event'] = haptic
            record_mobile_event('task_completed', **haptic)
            broadcast(haptic)
        return packet

    def robot_connected():
        seen = link_seen['monotonic']
        return seen is not None and time.monotonic() - seen <= ROBOT_LINK_TIMEOUT_S

    def touch_robot_link(mode, **fields):
        link_seen['monotonic'] = time.monotonic()
        link = dict(mobile_state['robot_link'] or {})
        link.update(mode=mode, last_seen=datetime.now().astimezone().isoformat(), **fields)
        mobile_state['robot_link'] = link

    def push_command(command, **payload):
        mobile_state['command_seq'] += 1
        entry = {'seq': mobile_state['command_seq'], 'command': command,
                 'timestamp': datetime.now().astimezone().isoformat(), **payload}
        mobile_state['commands'] = (mobile_state['commands'] + [entry])[-20:]
        return entry

    @app.get('/api/v1/mobile/status')
    async def mobile_status(robot: str | None = None):
        # The robot cycle polls with ?robot=<mode>; that poll is its heartbeat.
        if robot:
            touch_robot_link(robot[:32])
        task = await asyncio.to_thread(db.current_task)
        return {
            **mobile_state,
            'robot_connected': robot_connected(),
            'current_task': task,
        }

    @app.post('/api/v1/mobile/robot-state')
    async def robot_state_report(body: RobotLinkInput):
        fields = {'state': body.state, 'message': body.message}
        if body.ack_seq is not None:
            fields.update(ack_seq=body.ack_seq, ack_result=body.ack_result)
        touch_robot_link(body.mode, **fields)
        if not mobile_state['emergency_stopped']:
            mobile_state['robot_state'] = body.state
        packet = {'type': 'robot_state', **mobile_state['robot_link']}
        record_mobile_event('robot_state', **packet)
        broadcast(packet)
        return {'ok': True, 'robot_link': mobile_state['robot_link']}

    @app.get('/api/v1/mobile/work-area')
    async def mobile_work_area(rows: int = 15, cols: int = 15):
        if not (1 <= rows <= 50 and 1 <= cols <= 50):
            raise HTTPException(422, 'rows/cols must be 1-50')
        try:
            area = await asyncio.to_thread(_work_area, app, rows, cols)
        except Exception as exc:
            raise HTTPException(422, f'작업 영역 보정을 읽을 수 없습니다: {exc}') from exc
        # Korean names as on the slot buttons (DB product_name per yolo_class_name).
        try:
            db_names = {p['yolo_class_name']: p['product_name'] for p in await asyncio.to_thread(db.products)
                        if p.get('yolo_class_name') and p.get('product_name')}
        except Exception:
            db_names = {}
        area['product_names'] = {z: db_names.get(p, area['product_names'].get(z, p)) for z, p in area['zones'].items()}
        return {**area, 'reported_items': mobile_state['work_items']}

    @app.post('/api/v1/mobile/work-items')
    async def report_work_items(body: WorkItemsInput):
        now = datetime.now().astimezone().isoformat()
        # The cycle reports one product at a time; keep the latest sighting per zone.
        by_zone = {item['zone']: item for item in (mobile_state['work_items'] or {}).get('items', [])}
        by_zone.update({item.zone: {**item.model_dump(), 'reported_at': now} for item in body.items})
        mobile_state['work_items'] = {
            'source': body.source,
            'revision': body.revision,
            'reported_at': now,
            'items': [by_zone[z] for z in sorted(by_zone)],
        }
        broadcast({'type': 'work_items', **mobile_state['work_items']})
        return {'ok': True, **mobile_state['work_items']}

    @app.post('/api/v1/mobile/scan-mode')
    async def set_scan_mode(body: ScanModeInput):
        mobile_state['scan_mode'] = body.mode
        record_mobile_event('scan_mode', mode=body.mode)
        broadcast({'type': 'scan_mode', 'mode': body.mode})
        return {
            'ok': True,
            'scan_mode': body.mode,
            'priority_note': '전용 리더기 우선 모드 (기본)' if body.mode == 'external_reader' else '갤럭시 직접 NFC 태깅 모드 (보조 활성화)',
        }

    @app.post('/api/v1/mobile/box-placed')
    async def notify_box_placed(body: BoxPlacedInput):
        if mobile_state['emergency_stopped']:
            raise HTTPException(409, '비상 정지 상태입니다. 먼저 정지를 해제하세요.')
        slot_key = str(body.box_slot)
        placed_info = {
            'box_slot': body.box_slot,
            'uid': body.uid,
            'placed_at': datetime.now().astimezone().isoformat(),
            'scan_mode': mobile_state['scan_mode'],
            'status': 'WAITING_ROBOT_SCAN',
        }
        mobile_state['placed_boxes'][slot_key] = placed_info
        mobile_state['robot_state'] = 'BOX_PLACED'
        task = None
        product = None
        created = False
        if body.uid is not None:
            try:
                task, created = await asyncio.to_thread(enqueue_scan, db, body.uid, body.quantity, body.event_id)
                product = await asyncio.to_thread(db.product, body.uid)
            except KeyError as exc:
                raise HTTPException(404, 'Unknown tag') from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        msg = f'📦 {body.box_slot}번 상자 배치 완료 — 로봇팔 리더기 인식 출동'
        packet = {
            'type': 'box_placed',
            'box_slot': body.box_slot,
            'scan_mode': mobile_state['scan_mode'],
            'task': task,
            'product': product,
            'created': created,
            'message': msg,
        }
        command = push_command('box_placed', box_slot=body.box_slot, uid=body.uid)
        record_mobile_event('box_placed', box_slot=body.box_slot, uid=body.uid)
        broadcast(packet)
        connected = robot_connected()
        if not connected:
            packet['message'] = (f'{body.box_slot}번 상자 작업을 등록했습니다. 로봇 PC 사이클이 연결되지 않아 '
                                 '아직 출동하지 않습니다 (project_cycle.py --api 실행 필요).')
        return {'ok': True, **packet, 'seq': command['seq'], 'robot_connected': connected}

    @app.post('/api/v1/mobile/nfc-tag')
    async def mobile_nfc_tag(body: MobileNfcTagInput):
        if mobile_state['scan_mode'] != 'phone_nfc':
            raise HTTPException(
                409,
                "현재 '전용 리더기 우선 모드(external_reader)'입니다. 핸드폰 태깅은 보조 모드(phone_nfc) 활성화 시에만 가동됩니다.",
            )
        try:
            task, created = await asyncio.to_thread(enqueue_scan, db, body.uid, body.quantity, body.event_id)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown tag') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        product = await asyncio.to_thread(db.product, body.uid)
        mobile_state['placed_boxes'][str(body.box_slot)] = {
            'box_slot': body.box_slot,
            'uid': body.uid,
            'placed_at': datetime.now().astimezone().isoformat(),
            'scan_mode': 'phone_nfc',
            'status': 'TAGGED_BY_PHONE',
        }
        mobile_state['robot_state'] = 'SCANNING'
        packet = {
            'type': 'scan',
            'source': 'phone_nfc',
            'uid': body.uid,
            'box_slot': body.box_slot,
            'task': task,
            'product': product,
            'created': created,
        }
        record_mobile_event('phone_nfc_tag', uid=body.uid, box_slot=body.box_slot)
        if created:
            note_scan(body.uid, 'phone_nfc', uid=body.uid, product=product, task=task, created=True)
            broadcast(packet)
        return {'ok': True, **packet}

    def pause_packing(pipeline, paused):
        """Mirror pause/stop on the dashboard packing demo (order 123)."""
        packing = pipeline.packing
        (getattr(packing, 'set_paused', None) or packing.pause)(123, paused)

    @app.post('/api/v1/mobile/control')
    async def mobile_control(body: MobileControlInput):
        cmd = body.command
        ctrl = getattr(app.state, 'controller', None)
        pipeline = getattr(app.state, 'pipeline', None)
        if cmd == 'emergency_stop':
            mobile_state['emergency_stopped'] = True
            mobile_state['paused'] = True
            mobile_state['robot_state'] = 'EMERGENCY_STOP'
            if ctrl is not None:
                ctrl.cancel.set()
            if pipeline is not None and hasattr(pipeline, 'packing'):
                try:
                    pause_packing(pipeline, True)
                except Exception:
                    pass
        elif cmd == 'pause':
            mobile_state['paused'] = True
            mobile_state['robot_state'] = 'PAUSED'
            if pipeline is not None and hasattr(pipeline, 'packing'):
                try:
                    pause_packing(pipeline, True)
                except Exception:
                    pass
        elif cmd in ('start', 'resume', 'reset_stop'):
            # Only an explicit reset_stop releases an emergency stop; start/resume must not.
            if mobile_state['emergency_stopped'] and cmd != 'reset_stop':
                raise HTTPException(409, '비상 정지 상태입니다. [정지 해제]를 먼저 누르세요.')
            mobile_state['emergency_stopped'] = False
            mobile_state['paused'] = False
            mobile_state['robot_state'] = 'STANDBY'
            if pipeline is not None and hasattr(pipeline, 'packing'):
                try:
                    pause_packing(pipeline, False)
                except Exception:
                    pass
        elif cmd == 'home':
            if mobile_state['emergency_stopped']:
                raise HTTPException(409, '비상 정지 상태입니다. reset_stop 후 홈 복귀하세요.')
            mobile_state['robot_state'] = 'RETURNING_HOME'
        elif cmd == 'scan_dispatch':
            if mobile_state['emergency_stopped']:
                raise HTTPException(409, '비상 정지 상태입니다. 정지 해제 후 다시 시도하세요.')
            mobile_state['robot_state'] = 'SCANNING'
        entry = push_command(cmd)
        connected = robot_connected()
        labels = {'start': '작업 시작', 'resume': '재개', 'pause': '일시정지', 'home': '홈 복귀',
                  'scan_dispatch': '리더기 스캔 출동', 'emergency_stop': '비상 정지', 'reset_stop': '정지 해제'}
        if cmd == 'emergency_stop':
            message = '비상 정지 전송 — 로봇 사이클이 move_stop을 보냅니다.' if connected else \
                '비상 정지 상태로 전환했지만 로봇 PC 사이클이 연결되어 있지 않습니다. 펜던트 E-Stop을 사용하세요.'
        elif connected:
            message = f'{labels[cmd]} 명령을 로봇 사이클에 전달했습니다.'
        else:
            message = (f'{labels[cmd]} 명령을 저장했지만 로봇 PC 사이클이 연결되지 않아 로봇이 움직이지 않습니다 '
                       '(project_cycle.py --api 실행 필요).')
        packet = {
            'type': 'remote_control',
            'command': cmd,
            'seq': entry['seq'],
            'robot_state': mobile_state['robot_state'],
            'paused': mobile_state['paused'],
            'emergency_stopped': mobile_state['emergency_stopped'],
            'robot_connected': connected,
            'message': message,
        }
        record_mobile_event('remote_control', **packet)
        broadcast(packet)
        return {'ok': True, **packet}

    # ---- Hooks for in-process callers (the dashboard voice assistant): same paths as the phone ----
    async def control_command(command):
        """Run a phone control command; returns the packet, or raises HTTPException like the route."""
        return await mobile_control(MobileControlInput(command=command))

    async def queue_pick(uid, source='voice'):
        """Queue a pick task for a registered tag exactly as a reader scan would."""
        uid = await resolve(uid)
        product = await asyncio.to_thread(db.product, uid)
        try:
            task, created = await asyncio.to_thread(db.enqueue, uid, 1, str(uuid4()))
        except ValueError as exc:
            note_scan(uid, source, uid=uid, product=product,
                      error='이미 대기/진행 중인 작업이 있습니다' if 'active task' in str(exc) else str(exc))
            raise HTTPException(409, str(exc)) from exc
        note_scan(uid, source, uid=uid, product=product, task=task, created=created)
        if created:
            broadcast({'type': 'scan', 'source': source, 'uid': uid, 'task': task, 'product': product})
        return {'uid': uid, 'task': task, 'product': product, 'created': created}

    async def robot_snapshot():
        return {**{k: mobile_state[k] for k in ('robot_state', 'paused', 'emergency_stopped', 'robot_link', 'last_scan',
                                                'last_completed_event')},
                'robot_connected': robot_connected(), 'current_task': await asyncio.to_thread(db.current_task)}

    app.state.robot_control = control_command
    app.state.robot_queue_pick = queue_pick
    app.state.robot_snapshot = robot_snapshot

    @app.get('/api/v1/grid/config')
    async def grid_config(rows: int = 15, cols: int = 15):
        try:
            plane, poses, products, _ = await asyncio.to_thread(_load_grid_context, app)
            grid = plane.grid_map(rows=rows, cols=cols)
        except Exception as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            'rows': rows,
            'cols': cols,
            'grid': grid,
            'floor': poses.get('floor'),
            'products': {k: v.get('real') for k, v in products.items()},
        }

    @app.post('/api/v1/grid/locate')
    async def grid_locate(body: GridLocateInput):
        from vision_picking.pick_plane import compute_safe_grasp_z
        if body.pixel is None and body.base_xy is None:
            raise HTTPException(422, 'pixel 또는 base_xy 좌표를 입력하세요.')
        try:
            plane, poses, products, _ = await asyncio.to_thread(_load_grid_context, app)
            floor = poses['floor']
            floor_z = floor['floor_z']
            z_min = floor_z + floor['safety_margin'] + floor['nfc_protrusion']
            if body.pixel is not None:
                cell = plane.grid_cell(body.pixel, rows=body.rows, cols=body.cols)
            else:
                xyz = [*body.base_xy[:2], floor_z]
                cell = plane.grid_cell_from_base(xyz, rows=body.rows, cols=body.cols)
        except Exception as exc:
            raise HTTPException(422, str(exc)) from exc

        prod_cfg = (products.get(body.product) or products.get('snack_pepero') or {}).get('real') or {}
        grasp_info = compute_safe_grasp_z(floor_z, z_min, prod_cfg, measured_height_mm=body.measured_height_mm)
        grasp_z = grasp_info['grasp_z_mm']
        up = poses['motion']['approach_offset_z']
        cell_xy = cell['cell_center_base_mm'][:2]
        exact_xy = cell['exact_base_mm'][:2]
        abc = cell['exact_pose'][3:]

        coarse_approach_pose = [cell_xy[0], cell_xy[1], round(grasp_z + up, 2), *abc]
        fine_approach_pose = [exact_xy[0], exact_xy[1], round(grasp_z + up, 2), *abc]
        grasp_pose = [exact_xy[0], exact_xy[1], grasp_z, *abc]

        active_cell = {**cell, 'grasp_z_mm': grasp_z, 'product': body.product}
        mobile_state['grid'] = {'rows': body.rows, 'cols': body.cols, 'active_cell': active_cell}
        broadcast({'type': 'grid_active_cell', 'cell': active_cell, 'grasp_height_info': grasp_info})
        return {
            'ok': True,
            'product': body.product,
            'grid_cell': cell,
            'grasp_height_info': grasp_info,
            'trajectory': {
                'coarse_grid_approach_pose': coarse_approach_pose,
                'fine_aligned_approach_pose': fine_approach_pose,
                'crush_safe_grasp_pose': grasp_pose,
            },
        }

    @app.get('/remote', include_in_schema=False)
    async def mobile_remote_page():
        # no-store: the Galaxy WebView otherwise keeps serving an old copy of the remote after updates.
        return HTMLResponse(MOBILE_REMOTE_HTML, headers={'Cache-Control': 'no-store'})

    @app.get('/remote/manifest.json', include_in_schema=False)
    async def mobile_remote_manifest():
        return JSONResponse(MANIFEST_JSON)

    @app.websocket('/ws')
    async def websocket(socket: WebSocket):
        await socket.accept()
        queue = asyncio.Queue(maxsize=100)
        clients.add(queue)

        async def sender():
            while True:
                await socket.send_json(await queue.get())

        writer = asyncio.create_task(sender())
        try:
            await socket.send_json({'type': 'snapshot', 'task': await asyncio.to_thread(db.current_task)})
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(queue)
            writer.cancel()
            await asyncio.gather(writer, return_exceptions=True)

    return db


def create_app(db_path=None):
    app = FastAPI(title='RFID Pick-and-Place')
    install_rfid_routes(app, db_path=db_path)
    return app


app = create_app()
