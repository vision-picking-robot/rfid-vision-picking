import asyncio
from datetime import datetime
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator
import yaml

try:
    from .database import Database, SEED_TAGS, normalize_uid
    from .mobile_remote_ui import MANIFEST_JSON, MOBILE_REMOTE_HTML
    from .rfid_scanner import RFIDScanner
    from .services import ReaderBusy, ReaderUnavailable, enqueue_scan, scan_uid
except ImportError:
    from database import Database, SEED_TAGS, normalize_uid
    from mobile_remote_ui import MANIFEST_JSON, MOBILE_REMOTE_HTML
    from rfid_scanner import RFIDScanner
    from services import ReaderBusy, ReaderUnavailable, enqueue_scan, scan_uid


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class ScanEvent(StrictInput):
    uid: str
    quantity: int = Field(default=1, ge=1, le=10000)
    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=128)

    @field_validator('uid')
    @classmethod
    def valid_uid(cls, value):
        return normalize_uid(value)


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


class GridLocateInput(StrictInput):
    pixel: list[FiniteFloat] | None = Field(default=None, min_length=2, max_length=2)
    base_xy: list[FiniteFloat] | None = Field(default=None, min_length=2, max_length=3)
    rows: int = Field(default=15, ge=1, le=50)
    cols: int = Field(default=15, ge=1, le=50)
    product: str = Field(default='snack_pepero', min_length=1, max_length=64)
    measured_height_mm: FiniteFloat | None = Field(default=None, gt=0, le=500)


def _load_grid_context(app: FastAPI):
    from vision_picking.paths import ROOT
    from vision_picking.pick_plane import Calibration, PickPlane
    ctrl = getattr(app.state, 'controller', None)
    if ctrl is not None:
        cfg = ctrl.config
        poses = ctrl.poses
        products = ctrl.products
    else:
        cfg_path = Path(os.getenv('PICKING_CONFIG', str(ROOT / 'config/integration.json')))
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        poses = yaml.safe_load((ROOT / 'config/poses.yaml').read_text(encoding='utf-8'))
        products = yaml.safe_load((ROOT / 'config/products.yaml').read_text(encoding='utf-8'))['products']
    plane = PickPlane(Calibration(**cfg['calibration']))
    return plane, poses, products


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
        'events': [],
    }
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

    @app.get('/api/v1/tags')
    async def list_tags():
        return {'tags': await asyncio.to_thread(db.products)}

    @app.get('/api/v1/tags/{uid}')
    async def get_tag(uid: str):
        try:
            product = await asyncio.to_thread(db.product, uid)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if product is None:
            raise HTTPException(404, 'Unknown tag')
        return product

    @app.post('/api/v1/scan-event')
    async def scan(event: ScanEvent):
        try:
            task, created = await asyncio.to_thread(db.enqueue, event.uid, event.quantity, event.event_id)
        except KeyError as exc:
            raise HTTPException(404, 'Unknown tag') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        packet = {'type': 'scan', 'task': task, 'product': await asyncio.to_thread(db.product, event.uid)}
        if created:
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

    @app.get('/api/v1/mobile/status')
    async def mobile_status():
        task = await asyncio.to_thread(db.current_task)
        return {
            **mobile_state,
            'current_task': task,
        }

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
        record_mobile_event('box_placed', box_slot=body.box_slot, uid=body.uid)
        broadcast(packet)
        return {'ok': True, **packet}

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
            broadcast(packet)
        return {'ok': True, **packet}

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
                    pipeline.packing.set_paused(123, True)
                except Exception:
                    pass
        elif cmd == 'pause':
            mobile_state['paused'] = True
            mobile_state['robot_state'] = 'PAUSED'
            if pipeline is not None and hasattr(pipeline, 'packing'):
                try:
                    pipeline.packing.set_paused(123, True)
                except Exception:
                    pass
        elif cmd in ('start', 'resume', 'reset_stop'):
            mobile_state['emergency_stopped'] = False
            mobile_state['paused'] = False
            mobile_state['robot_state'] = 'STANDBY'
            if pipeline is not None and hasattr(pipeline, 'packing'):
                try:
                    pipeline.packing.set_paused(123, False)
                except Exception:
                    pass
        elif cmd == 'home':
            if mobile_state['emergency_stopped']:
                raise HTTPException(409, '비상 정지 상태입니다. reset_stop 후 홈 복귀하세요.')
            mobile_state['robot_state'] = 'RETURNING_HOME'
        elif cmd == 'scan_dispatch':
            if mobile_state['emergency_stopped']:
                raise HTTPException(409, '비상 정지 상태입니다.')
            mobile_state['robot_state'] = 'SCANNING'
        packet = {
            'type': 'remote_control',
            'command': cmd,
            'robot_state': mobile_state['robot_state'],
            'paused': mobile_state['paused'],
            'emergency_stopped': mobile_state['emergency_stopped'],
        }
        record_mobile_event('remote_control', **packet)
        broadcast(packet)
        return {'ok': True, **packet}

    @app.get('/api/v1/grid/config')
    async def grid_config(rows: int = 15, cols: int = 15):
        try:
            plane, poses, products = await asyncio.to_thread(_load_grid_context, app)
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
            plane, poses, products = await asyncio.to_thread(_load_grid_context, app)
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
        return HTMLResponse(MOBILE_REMOTE_HTML)

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
