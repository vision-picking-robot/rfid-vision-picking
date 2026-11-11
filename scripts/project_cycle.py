"""Full project cycle on taught poses (RFID scenario order, no camera).

  home -> pre_scan (label_scan_approach -> label_scan -> up) -> RFID tag -> product/box
  -> gripper open -> approach (taught product x,y, +approach_offset_z) -> descend to grasp height
  -> gripper close -> lift -> via_point -> box slot (high -> place) -> release -> retreat -> home

TCP: taught posx values are fingertip (TCP) coordinates. At start the script measures
fkin(home.posj).z - home.posx.z. If the controller has no TCP active this is the tool length
(120 mm on this cell) and every Cartesian target is converted TCP -> flange by adding it to z
(valid because every target points straight down, ry=180). If a TCP is active it measures 0.
The SafeMover floor check always runs on TCP z.

Real hardware needs `--mode real --confirm-real`. Errors or Ctrl+C send move_stop; no retries.
"""
import argparse
import json
import math
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vision_picking.legacy.safe_move import DR_BASE, SafeMover  # noqa: E402
from vision_picking.pick_plane import Calibration, DEFAULT_GRID_COLS, DEFAULT_GRID_ROWS, PickPlane, compute_safe_grasp_z  # noqa: E402

TAGS = {'0B71E55D': ('snack_pepero', 1), '0B71E75D': ('beverage_pet', 2), '0B71E65D': ('canned_meat', 3),
        '0B71ED5D': ('wet_tissue', 4), '0B71EC5D': ('doll', 5)}
OPEN_MAX = 10
JOINT_TOL = 1.0
POS_TOL = 2.0


class Logger:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.file = path, path.open('a', encoding='utf-8')

    def __call__(self, event, **fields):
        line = json.dumps(dict(time=datetime.now().isoformat(timespec='milliseconds'), event=event, **fields),
                          ensure_ascii=False)
        print(line, flush=True)
        self.file.write(line + '\n')
        self.file.flush()

    def error(self, msg):
        self('safety_block', message=msg)


class FlangeOffset:
    """SafeMover backend that receives TCP targets and drives the flange (z + offset)."""

    def __init__(self, raw, offset):
        self.raw, self.offset = raw, offset

    def _shift(self, pose, sign):
        return [pose[0], pose[1], pose[2] + sign * self.offset, *pose[3:]]

    def get_current_posx(self, ref):
        cur = self.raw.get_current_posx(ref)
        return None if cur is None else self._shift(cur, -1)

    def get_current_posj(self):
        return self.raw.get_current_posj()

    def fkin(self, posj, ref):
        pose = self.raw.fkin(posj, ref)
        return None if pose is None else self._shift(pose, -1)

    def movel(self, pos, vel, acc, ref, mod, radius):
        return self.raw.movel(self._shift(pos, +1), vel, acc, ref, mod, radius)

    def movej(self, pos, vel, acc, mod, radius):
        return self.raw.movej(pos, vel, acc, mod, radius)


class MockRaw:
    """Flange-level mock with a 120 mm tool, straight-down orientation only."""
    mock = True

    def __init__(self, poses):
        self.table = {tuple(v['posj']): [*v['posx'][:2], v['posx'][2] + 120.0, *v['posx'][3:]] for v in poses}
        self.posj = [0.0, 0.0, 90.0, 0.0, 90.0, 0.0]
        self.posx = self.fkin(self.posj, 0)
        self.position = 0

    def check_ready(self):
        return None

    def fkin(self, posj, ref):
        if tuple(posj) in self.table:
            return list(self.table[tuple(posj)])
        a = math.radians(posj[0])  # J1 rotation of the home pose
        return [373.0 * math.cos(a), 373.0 * math.sin(a), 405.0, 0.0, 180.0, 0.0]

    def get_current_posj(self):
        return list(self.posj)

    def get_current_posx(self, ref):
        return list(self.posx)

    def movej(self, pos, vel, acc, mod, radius):
        self.posj, self.posx = list(pos), self.fkin(pos, 0)
        return 0

    def movel(self, pos, vel, acc, ref, mod, radius):
        self.posx = list(pos)
        return 0

    def grip(self, target, current=None):
        if target >= 0:
            self.position = target
        return dict(code=1, result='ok', voltage=24.1, position_pulses=self.position, current=0, moving=0)

    def scan(self):
        return '0B71E55D'

    def raise_posj(self, posj, dz):
        raised = [posj[0], posj[1] - 0.001 * dz, *posj[2:]]
        base = self.fkin(posj, 0)
        self.table[tuple(raised)] = [base[0], base[1], base[2] + dz, *base[3:]]
        return raised

    def stop(self):
        pass

    def emergency_stop(self):
        self.estopped = True

    def close(self):
        pass


class RealRaw:
    mock = False

    def __init__(self, namespace):
        from vision_picking.backends import RosBackend
        from vision_picking.drl_gripper import DrlGripper
        self.ros = RosBackend(namespace)
        self.hand = DrlGripper(self.ros.node, self.ros.executor, namespace)
        import rclpy
        from dsr_msgs2.srv import MoveStop
        from rclpy.context import Context
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        self._estop_ctx = Context()
        rclpy.init(context=self._estop_ctx)
        self._estop_node = Node('project_cycle_estop', context=self._estop_ctx)
        self._estop_exec = SingleThreadedExecutor(context=self._estop_ctx)
        self._estop_exec.add_node(self._estop_node)
        self._estop_client = self._estop_node.create_client(MoveStop, f'/{namespace}/motion/move_stop')
        self.scan_timeout = 5.0

    def check_ready(self):
        self.ros.check_ready()

    def fkin(self, posj, ref):
        return self.ros.motion.fkin(posj, ref)

    def get_current_posj(self):
        return self.ros.motion.get_current_posj()

    def get_current_posx(self, ref):
        return self.ros.motion.get_current_posx(ref)

    def movej(self, pos, vel, acc, mod, radius):
        return self.ros.motion.movej(pos, vel, acc, mod, radius)

    def movel(self, pos, vel, acc, ref, mod, radius):
        return self.ros.motion.movel(pos, vel, acc, ref, mod, radius)

    def grip(self, target, current=None):
        if current is None:
            return self.hand.run(target)
        return self.hand.run(target, current=current)

    def raise_posj(self, posj, dz):
        """Joint pose whose flange is dz higher with the same orientation and solution space."""
        from dsr_msgs2.srv import GetSolutionSpace, Ikin
        from vision_picking.legacy.ros_calls import call_service
        node, ex = self.ros.node, self.ros.executor
        if not hasattr(self, '_ik'):
            self._ik = node.create_client(Ikin, '/dsr01/motion/ikin')
            self._sol = node.create_client(GetSolutionSpace, '/dsr01/aux_control/get_solution_space')
        flange = self.fkin(posj, 0)
        sol = call_service(ex, self._sol, GetSolutionSpace.Request(pos=[float(v) for v in posj]), 3.0)
        target = [flange[0], flange[1], flange[2] + dz, *flange[3:6]]
        res = call_service(ex, self._ik, Ikin.Request(pos=target, sol_space=sol.sol_space, ref=0), 3.0)
        if not (sol.success and res.success):
            raise RuntimeError(f'ikin failed for raised pose of {posj}')
        return list(res.conv_posj)

    def scan(self):
        try:
            from robot_rfid.rfid_scanner import RFIDScanner
            return RFIDScanner().scan(timeout=self.scan_timeout)
        except Exception:
            return None

    def stop(self):
        self.ros.stop()

    def emergency_stop(self):
        """move_stop on a dedicated context: the main executor is blocked inside the running motion call."""
        from dsr_msgs2.srv import MoveStop
        from vision_picking.legacy.ros_calls import call_service
        result = call_service(self._estop_exec, self._estop_client, MoveStop.Request(stop_mode=1), 3)
        if not result.success:
            raise RuntimeError('move_stop not acknowledged')

    def close(self):
        self.ros.close()
        self._estop_ctx.shutdown()


def load_config(product):
    poses = yaml.safe_load((ROOT / 'config/poses.yaml').read_text(encoding='utf-8'))
    products = yaml.safe_load((ROOT / 'config/products.yaml').read_text(encoding='utf-8'))['products']
    for name in ('home', 'label_scan_approach', 'label_scan', 'via_point'):
        if not poses['poses'][name].get('taught'):
            raise SystemExit(f'{name} is not taught')
    return poses, products


def verified_real_calibration(cfg):
    cal = cfg.get('calibration') or {}
    revision = str(cal.get('revision') or '').lower()
    camera = str((cal.get('camera') or {}).get('camera_id') or '').lower()
    return (cfg.get('calibration_verified') is True and cfg.get('mock_mode') is False
            and 'mock' not in revision and 'mock' not in camera and len(cal.get('corners') or []) == 4)


class MobileEStopWatch(threading.Thread):
    """Polls the dashboard's mobile E-stop flag and sends move_stop the moment it is set.

    The phone button only flips a flag in the web process; this thread is what turns it into a
    real robot stop. It is not a substitute for the pendant E-Stop.
    """

    def __init__(self, api, stop_fn, log, period=0.3):
        super().__init__(daemon=True)
        self.url = api.rstrip('/') + '/api/v1/mobile/status'
        self.stop_fn, self.log, self.period = stop_fn, log, period
        self.tripped = threading.Event()
        self.alive = threading.Event()
        self.alive.set()
        self.available = True

    def poll(self):
        import httpx
        r = httpx.get(self.url, timeout=2)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return bool(r.json().get('emergency_stopped'))

    def run(self):
        warned = False
        while self.alive.is_set() and not self.tripped.is_set():
            try:
                state = self.poll()
                if state is None:
                    self.available = False
                    self.log('estop_watch_unavailable', url=self.url)
                    return
                warned = False
                if state:
                    self.tripped.set()
                    self.log('mobile_emergency_stop', action='move_stop')
                    try:
                        self.stop_fn()
                        self.log('move_stop_sent', source='mobile_estop')
                    except Exception as error:  # noqa: BLE001
                        self.log('move_stop_failed', source='mobile_estop', message=str(error))
                    return
            except Exception as error:  # noqa: BLE001
                if not warned:
                    self.log('estop_watch_unreachable', message=str(error))
                    warned = True
            time.sleep(self.period)

    def check(self):
        if self.tripped.is_set():
            raise RuntimeError('Mobile emergency stop pressed: motion stopped (reset_stop on the phone before restarting)')


class Cycle:
    def __init__(self, raw, poses, products, args, log):
        self.raw, self.poses, self.products, self.args, self.log = raw, poses, products, args, log
        self.estop = None
        floor = poses['floor']
        self.z_min = floor['floor_z'] + floor['safety_margin'] + floor['nfc_protrusion']
        home = poses['poses']['home']
        flange = raw.fkin(home['posj'], DR_BASE)
        if flange is None:
            raise RuntimeError('fkin failed; cannot determine TCP offset')
        dx, dy, dz = (flange[i] - home['posx'][i] for i in range(3))
        if abs(dx) > POS_TOL or abs(dy) > POS_TOL or not (-POS_TOL <= dz <= 250):
            raise RuntimeError(f'Taught home posx does not match fkin(posj): d=({dx:.1f},{dy:.1f},{dz:.1f})')
        self.offset = 0.0 if abs(dz) <= POS_TOL else round(dz, 1)
        self.mover = SafeMover(self.z_min, FlangeOffset(raw, self.offset), poses['motion']['max_vel'],
                               poses['motion']['max_acc'], logger=log)
        log('tcp_offset', flange_minus_taught_z=round(dz, 2), applied_offset=self.offset, z_min=self.z_min)
        # Carry height: transfer poses raised by --lift-extra so the held object clears the box wall.
        P = poses['poses']
        box_hi = [P['home']['posj'][0] + 180.0, *P['home']['posj'][1:]]
        self.carry = {}
        for name, posj in (('home', P['home']['posj']), ('via_point', P['via_point']['posj']), ('box_high', box_hi)):
            raised = raw.raise_posj(posj, args.lift_extra) if args.lift_extra else list(posj)
            check = raw.fkin(raised, DR_BASE)
            base = raw.fkin(posj, DR_BASE)
            if check is None or abs(check[2] - base[2] - args.lift_extra) > POS_TOL or \
                    abs(check[0] - base[0]) > POS_TOL or abs(check[1] - base[1]) > POS_TOL:
                raise RuntimeError(f'Raised {name} pose failed verification')
            if max(abs(a - b) for a, b in zip(raised, posj)) > 45.0:
                raise RuntimeError(f'Raised {name} pose changes a joint by more than 45 deg; refusing')
            self.carry[name] = raised
        log('carry_poses', lift_extra=args.lift_extra, place_extra=args.place_extra,
            carry_z=round(P['home']['posx'][2] + args.lift_extra, 1),
            posj={k: [round(v, 2) for v in val] for k, val in self.carry.items()})
        cfg_path = Path(getattr(args, 'picking_config', None) or (ROOT / 'config/integration.json'))
        self.plane = None
        self.cal_revision = None
        self.depth_cfg = {}
        if cfg_path.is_file():
            try:
                cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
                self.depth_cfg = cfg.get('depth_picking') or {}
                cal_data = cfg.get('calibration')
                if cal_data and args.mode == 'real' and not verified_real_calibration(cfg):
                    # Never steer the physical arm with MOCK/unverified camera calibration.
                    log('grid_disabled', config=str(cfg_path), revision=cal_data.get('revision'),
                        reason='real mode needs calibration_verified=true and a non-mock calibration')
                    cal_data = None
                if cal_data:
                    self.plane = PickPlane(Calibration(**cal_data))
                    self.cal_revision = cal_data.get('revision')
            except Exception as exc:  # noqa: BLE001
                log('grid_plane_skip', reason=str(exc))
        if getattr(args, 'depth_api', None) and (self.plane is None or not self.depth_cfg.get('zones')):
            raise RuntimeError('--depth-api needs --picking-config with a verified calibration and depth_picking.zones')
        if args.mode == 'real' and getattr(args, 'pixel', None) and self.plane is None:
            raise RuntimeError('--pixel needs a verified real camera calibration (--picking-config with calibration_verified=true)')

    def _estop_check(self):
        if self.estop is not None:
            self.estop.check()

    def j(self, name, posj):
        self._estop_check()
        t0 = time.monotonic()
        self.mover.movej(posj, self.args.jvel, self.args.jvel)
        self._estop_check()
        cur = self.raw.get_current_posj()
        err = max(abs(a - b) for a, b in zip(cur, posj))
        if err > JOINT_TOL:
            raise RuntimeError(f'{name}: joint arrival error {err:.2f} deg')
        self.log('step', name=name, kind='movej', seconds=round(time.monotonic() - t0, 1))

    def l(self, name, pose, vel=None):
        self._estop_check()
        t0 = time.monotonic()
        self.mover.movel(pose, vel or self.args.lvel, vel or self.args.lvel, DR_BASE)
        self._estop_check()
        cur = FlangeOffset(self.raw, self.offset).get_current_posx(DR_BASE)
        err = max(abs(a - b) for a, b in zip(cur[:3], pose[:3]))
        if err > POS_TOL:
            raise RuntimeError(f'{name}: TCP arrival error {err:.1f} mm')
        self.log('step', name=name, kind='movel', tcp=[round(v, 1) for v in cur[:3]],
                 seconds=round(time.monotonic() - t0, 1))

    def grip(self, name, target, ok, current=None, settle_s=0.0):
        self._estop_check()
        fb = self.raw.grip(target, current)
        # At a low force limit the fingers keep creeping into a soft or slipping object for a
        # moment after the DRL settle time; poll the status until they stop (code 1, moving 0).
        deadline = time.monotonic() + settle_s
        while fb['code'] == 1 and fb['moving'] and time.monotonic() < deadline:
            time.sleep(0.5)
            fb = self.raw.grip(-1)
        if fb['code'] != 1 or fb['moving'] or not ok(fb['position_pulses']):
            raise RuntimeError(f"{name}: gripper not confirmed ({fb['result']}, pos={fb['position_pulses']})")
        self.log('step', name=name, kind='gripper', position=fb['position_pulses'], current=fb['current'])
        return fb

    # ---- Steps matching robot_rfid.orchestrator.Orchestrator's robot interface ----
    def pre_scan(self):
        P = self.poses['poses']
        self.raw.check_ready()
        # Recovery: if an earlier stop left the tool low, rise straight up before any joint move.
        cur = FlangeOffset(self.raw, self.offset).get_current_posx(DR_BASE)
        safe_z = P['home']['posx'][2]
        if cur is not None and cur[2] < safe_z - POS_TOL:
            self.log('recovery', tcp=[round(v, 1) for v in cur[:3]], rise_to=safe_z)
            self.l('recovery_rise', [cur[0], cur[1], safe_z, *cur[3:6]], self.args.dvel)
        self.j('home', P['home']['posj'])
        self.j('label_scan_approach', P['label_scan_approach']['posj'])
        scan_hi = P['label_scan_approach']['posx']
        self.l('label_scan', [*scan_hi[:2], P['label_scan']['posx'][2], *scan_hi[3:]], self.args.dvel)

    def scan(self):
        P = self.poses['poses']
        uid = self.raw.scan() or self.args.tag
        self.log('rfid', uid=uid, reader='real' if uid != self.args.tag else 'preset')
        self.l('label_scan_retract', P['label_scan_approach']['posx'])
        self.j('home_after_scan', P['home']['posj'])
        return uid

    def detect_by_depth(self, product):
        """Locate `product` with the depth camera: the object in its corner zone of the work area."""
        import httpx
        zones = {int(k): v for k, v in self.depth_cfg['zones'].items()}
        zone = next((z for z, name in zones.items() if name == product), None)
        if zone is None:
            raise RuntimeError(f'no depth zone is assigned to {product}')
        url = f"{self.args.depth_api.rstrip('/')}/api/robot/pick/depth-objects"
        samples = []
        for i in range(int(self.depth_cfg.get('samples', 3))):
            if i:
                time.sleep(0.3)
            data = httpx.get(url, timeout=10).raise_for_status().json()
            if data.get('revision') != self.cal_revision:
                raise RuntimeError('web calibration revision differs from --picking-config; re-export the calibration')
            found = [o for o in data['objects'] if o.get('corner') == zone and o.get('inside') and o.get('base')]
            if not found:
                raise RuntimeError(f'depth camera sees no object in zone {zone} ({product})')
            samples.append(found[0])  # largest blob in the zone
        # A hand or arm over the table shows up as a tall "object": only act on a still scene.
        tol = float(self.depth_cfg.get('stable_tol_mm', 10.0))
        obj = samples[-1]
        if any(math.dist(s['base'], obj['base']) > tol or abs(s['height_mm'] - obj['height_mm']) > tol for s in samples):
            raise RuntimeError(f'zone {zone} is not steady across {len(samples)} depth frames '
                               '(person or moving object over the table?)')
        short_mm = (obj.get('footprint_mm') or [0.0])[0]
        max_open = float(self.depth_cfg.get('gripper_max_open_mm', 100.0))
        if short_mm > max_open:
            raise RuntimeError(f'{product} is {short_mm:.0f} mm wide (gripper opens {max_open:.0f} mm); '
                               'place it so its short side fits the gripper')
        if not 5.0 <= obj['height_mm'] <= float(self.depth_cfg.get('max_height_mm', 300.0)):
            raise RuntimeError(f"implausible object height {obj['height_mm']} mm in zone {zone}")
        item = (self.products.get(product) or self.products[self.args.product])['real']
        # The nominal (taught) height sets a 50 % floor in compute_safe_grasp_z, which would put the
        # fingers above a lower measured object; with a measurement, only keep the 15 mm table margin.
        measured_item = dict(item, grasp_height_from_floor=obj['height_mm'], min_safe_height_from_floor=15.0)
        grasp_info = compute_safe_grasp_z(self.poses['floor']['floor_z'], self.z_min, measured_item,
                                          measured_height_mm=obj['height_mm'])
        if grasp_info['grasp_z_mm'] >= self.poses['floor']['floor_z'] + obj['height_mm']:
            raise RuntimeError(f"grasp height {grasp_info['grasp_z_mm']} mm is not below the object top")
        close0 = self.depth_cfg.get('gripper_close_yaw_at_rz0_deg')
        if close0 is None or obj.get('short_axis_yaw_deg') is None:
            rz = item.get('rz', 0.0)
        else:  # fingers close along base yaw (close0 - rz) for tool orientation (0, 180, rz)
            rz = (float(close0) - obj['short_axis_yaw_deg'] + 90.0) % 180.0 - 90.0
        x, y = obj['base']
        self.log('vision', source=f'depth camera zone {zone}', product=product, base=[x, y],
                 height_mm=obj['height_mm'], footprint_mm=obj.get('footprint_mm'),
                 short_axis_yaw=obj.get('short_axis_yaw_deg'), rz=round(rz, 1), grasp_z=grasp_info['grasp_z_mm'])
        return dict(product=product, pose=[x, y, grasp_info['grasp_z_mm'], 0.0, 180.0, rz],
                    grid_cell=None, grasp_info=grasp_info)

    def detect(self, task):
        product = task.get('yolo_class_name') if isinstance(task, dict) else task
        if getattr(self.args, 'depth_api', None):
            return self.detect_by_depth(product)
        if product not in self.products or not self.products[product]['real'].get('taught'):
            self.log('vision_fallback', requested=product, used=self.args.product)
            product = self.args.product
        item = self.products[product]['real']
        floor_z = self.poses['floor']['floor_z']
        grasp_info = compute_safe_grasp_z(floor_z, self.z_min, item, measured_height_mm=getattr(self.args, 'measured_height', None))
        grasp_z = grasp_info['grasp_z_mm']
        target_x, target_y = item['x'], item['y']
        grid_info = None
        if self.plane is not None:
            rows = getattr(self.args, 'grid_rows', DEFAULT_GRID_ROWS)
            cols = getattr(self.args, 'grid_cols', DEFAULT_GRID_COLS)
            try:
                if getattr(self.args, 'pixel', None):
                    u_px, v_px = (float(v) for v in self.args.pixel.split(','))
                    grid_info = self.plane.grid_cell((u_px, v_px), rows=rows, cols=cols)
                    target_x, target_y = grid_info['exact_base_mm'][0], grid_info['exact_base_mm'][1]
                elif self.plane.contains_base([target_x, target_y, floor_z]):
                    grid_info = self.plane.grid_cell_from_base([target_x, target_y, floor_z], rows=rows, cols=cols)
            except Exception as exc:  # noqa: BLE001
                self.log('grid_lookup_skip', reason=str(exc))
        if grid_info is not None:
            self.log('grid_cell', product=product, cell_id=grid_info['cell_id'], row=grid_info['row'], col=grid_info['col'],
                     rows=grid_info['rows'], cols=grid_info['cols'], cell_center_mm=grid_info['cell_center_base_mm'],
                     fine_offset_mm=grid_info['fine_offset_mm'], grasp_z=grasp_z)
        self.log('vision', source='15x15 grid + taught product pose' if grid_info else 'taught product pose (no camera)',
                 product=product, grasp_z=grasp_z)
        return dict(product=product, pose=[target_x, target_y, grasp_z, 0.0, 180.0, item.get('rz', 0.0)],
                    grid_cell=grid_info, grasp_info=grasp_info)

    def approach(self, target):
        up = self.poses['motion']['approach_offset_z']
        grasp = target['pose']
        self._approach = [*grasp[:2], grasp[2] + up, *grasp[3:]]
        self._above = [*grasp[:2], grasp[2] + up + self.args.lift_extra, *grasp[3:]]
        self._product = target['product']
        self.grip('gripper_open', 0, lambda p: p <= OPEN_MAX)
        grid_info = target.get('grid_cell') if isinstance(target, dict) else None
        if grid_info is not None:
            cell_xy = grid_info['cell_center_base_mm'][:2]
            self._grid_approach = [cell_xy[0], cell_xy[1], grasp[2] + up, *grasp[3:]]
            self.l('grid_coarse_approach', self._grid_approach)
        self.l('approach', self._approach)
        self.l('descend', grasp, self.args.dvel)

    def grip_object(self):
        limit = getattr(self.args, 'grip_current', 150)
        closed = self.grip('grip', 740, lambda p: p >= 0, current=limit, settle_s=4.0)
        # Empty close reaches ~739 at low current; an object stalls the fingers earlier, or (thin
        # or soft packs) near full close with the current pinned at the limit.
        self.holding = closed['position_pulses'] < 700 or (
            closed['position_pulses'] < 735 and closed['current'] >= 0.8 * limit)
        self.log('grasp', product=self._product, holding=self.holding, position=closed['position_pulses'],
                 current=closed['current'], note='object detected' if self.holding else 'empty close (no object)')
        if self.args.require_object and not self.holding:
            raise RuntimeError('No object in the gripper (empty close)')

    def retract(self):
        self.l('lift', self._above)
        home = self.poses['poses']['home']['posx']
        self.l('home_carry', [home[0], home[1], home[2] + self.args.lift_extra, *home[3:]])

    def place(self, box_id=1):
        P, up = self.poses['poses'], self.poses['motion']['approach_offset_z']
        slot = int(str(box_id).split('-')[-1]) if box_id else 1
        if not (self.poses['box_slots'].get(slot) or {}).get('taught'):
            self.log('box_fallback', requested=box_id, used_slot=1, reason='slot not taught')
            slot = 1
        slot_pose = self.poses['box_slots'][slot]['posx']
        self.j('via_carry', self.carry['via_point'])
        self.j('box_carry', self.carry['box_high'])
        self.l('box_place', [*slot_pose[:2], slot_pose[2] + self.args.place_extra, *slot_pose[3:]], self.args.dvel)
        self.grip('release', 0, lambda p: p <= OPEN_MAX)
        carry_z = P['home']['posx'][2] + self.args.lift_extra
        self.l('box_retreat', [*slot_pose[:2], carry_z, *slot_pose[3:]])
        self.j('via_return', self.carry['via_point'])
        self.last_slot = slot

    def home(self):
        self.j('home_return', self.poses['poses']['home']['posj'])

    def stop(self):
        self.raw.stop()

    def run(self, cycle):
        self.pre_scan()
        uid = self.scan()
        product, box = TAGS.get(uid, (self.args.product, 1))
        target = self.detect(product)
        self.approach(target)
        self.grip_object()
        self.retract()
        self.place(box)
        self.home()
        self.log('cycle_ok', cycle=cycle, product=target['product'], box_slot=self.last_slot, holding=self.holding)


class OrchestratorRobot:
    """Adapter: Orchestrator robot/scanner/vision interfaces -> Cycle steps."""

    def __init__(self, cycle):
        self.c = cycle

    def pre_scan(self): self.c.pre_scan()
    def scan(self): return self.c.scan()
    def detect(self, task): return self.c.detect(task)
    def approach(self, pose): self.c.approach(pose)
    def grip(self): self.c.grip_object()
    def retract(self): self.c.retract()
    def place(self, box): self.c.place(box)
    def home(self): self.c.home()
    def stop(self):
        # Orchestrator calls stop() inside its except block; never let a failed stop hide the cause.
        try:
            self.c.stop()
        except Exception as error:  # noqa: BLE001
            self.c.log('move_stop_failed', message=str(error))


def run_remote_task(runner, args, log, cycle):
    """Execute the next task another PC queued through POST /api/v1/scan-event (UID -> DB match on the web)."""
    import httpx
    api = httpx.Client(base_url=args.api, timeout=10)
    runner.raw.check_ready()
    runner.home()
    log('waiting_for_tag', api=args.api, note='scan a tag on the remote reader PC')
    started = time.monotonic()
    while True:
        task = api.get('/api/v1/current-task').raise_for_status().json()['task']
        if task is not None:
            break
        runner._estop_check()
        if args.wait_timeout and time.monotonic() - started > args.wait_timeout:
            raise TimeoutError(f'No remote RFID task within {args.wait_timeout:.0f}s')
        time.sleep(0.5)
    if task['status'] == 'PICKING':
        raise RuntimeError('Interrupted PICKING task requires operator reconciliation')
    tid, completed = task['task_id'], task['completed']
    log('task', task_id=tid, uid=task.get('tag_uid'), product=task.get('yolo_class_name'),
        name=task.get('product_name'), box=task.get('target_box_id'), quantity=task['quantity'])
    patch = lambda done, status, error=None: api.patch(  # noqa: E731
        f'/api/v1/tasks/{tid}', json=dict(completed=done, status=status, error=error)).raise_for_status()
    try:
        patch(completed, 'PICKING')
        while completed < task['quantity']:
            target = runner.detect(task)
            runner.approach(target)
            runner.grip_object()
            runner.retract()
            runner.place(task.get('target_box_id'))
            completed += 1
            patch(completed, 'PICKING')
        patch(completed, 'COMPLETED')
        runner.home()
        log('cycle_ok', cycle=cycle, scenario='remote_rfid', task_id=tid, product=target['product'],
            box_slot=runner.last_slot, holding=runner.holding)
    except Exception as error:
        try:
            runner.stop()
        except Exception as stop_error:  # noqa: BLE001
            log('move_stop_failed', message=str(stop_error))
        try:
            patch(completed, 'DEFECTIVE', str(error))
        except Exception:  # noqa: BLE001
            log('task_report_failed', task_id=tid)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mode', choices=['mock', 'real'], default='mock')
    parser.add_argument('--confirm-real', action='store_true')
    parser.add_argument('--namespace', default='dsr01')
    parser.add_argument('--cycles', type=int, default=1, help='0 = until Ctrl+C or first error')
    parser.add_argument('--product', default='snack_pepero', help='fallback when no RFID reader is attached')
    parser.add_argument('--tag', default='0B71E55D', help='preset tag used when no RFID reader is attached')
    parser.add_argument('--jvel', type=float, default=10.0, help='deg/s')
    parser.add_argument('--lvel', type=float, default=30.0, help='mm/s for transfer moves')
    parser.add_argument('--dvel', type=float, default=15.0, help='mm/s for descents')
    parser.add_argument('--log', type=Path)
    parser.add_argument('--lift-extra', type=float, default=100.0,
                        help='mm added to the lift and carry height (home/via/box transfer)')
    parser.add_argument('--place-extra', type=float, default=100.0,
                        help='mm above the taught box slot z where the object is released')
    parser.add_argument('--depth-api', help='locate products with the RealSense depth camera via this web, '
                        'e.g. http://127.0.0.1:8000 (needs --picking-config with depth_picking.zones)')
    parser.add_argument('--grip-current', type=int, default=150,
                        help='gripper goal current in mA for the grasp (force limit; was 400, which crushed snack boxes)')
    parser.add_argument('--require-object', action='store_true', help='fail when the gripper closes empty')
    parser.add_argument('--remote-rfid', action='store_true',
                        help='with --api: wait for tasks queued by another PC (POST /api/v1/scan-event) instead of scanning')
    parser.add_argument('--wait-timeout', type=float, default=0, help='remote mode: seconds to wait per task, 0 = forever')
    parser.add_argument('--api', help='run the repo RFID Orchestrator against this web API, e.g. http://127.0.0.1:8000')
    parser.add_argument('--grid-rows', type=int, default=DEFAULT_GRID_ROWS, help='checkerboard grid rows (default 15)')
    parser.add_argument('--grid-cols', type=int, default=DEFAULT_GRID_COLS, help='checkerboard grid cols (default 15)')
    parser.add_argument('--pixel', help='optional detected pixel u,v inside the 4-corner ROI for grid picking')
    parser.add_argument('--measured-height', type=float, default=None, help='optional RealSense measured object height in mm')
    parser.add_argument('--picking-config', type=Path, default=None, help='calibration JSON path')
    args = parser.parse_args(argv)
    if args.mode == 'real' and not args.confirm_real:
        parser.error('--mode real requires --confirm-real')
    if args.remote_rfid and not args.api:
        parser.error('--remote-rfid requires --api')
    poses, products = load_config(args.product)
    log = Logger(args.log or ROOT / 'state' / 'project_cycle' / f'{args.mode}-{datetime.now():%Y%m%d-%H%M%S}.jsonl')
    taught = [*poses['poses'].values(), poses['box_slots'][1]]
    raw = MockRaw(taught) if args.mode == 'mock' else RealRaw(args.namespace)

    def on_signal(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)
    log('start', mode=args.mode, cycles=args.cycles or 'infinite', product=args.product, log=str(log.path))
    cycle, code = 0, 0
    try:
        runner = Cycle(raw, poses, products, args, log)
        if args.api:
            watch = MobileEStopWatch(args.api, raw.emergency_stop, log)
            try:
                if watch.poll():
                    raise RuntimeError('Mobile emergency stop is active; press reset_stop on the phone first')
            except RuntimeError:
                raise
            except Exception as error:  # noqa: BLE001
                log('estop_watch_unreachable', message=str(error))
            watch.start()
            runner.estop = watch
            log('estop_watch', url=watch.url, note='phone E-stop -> move_stop; pendant E-Stop is still the real safety stop')
        while args.cycles == 0 or cycle < args.cycles:
            cycle += 1
            if args.api and args.remote_rfid:
                run_remote_task(runner, args, log, cycle)
            elif args.api:
                import logging
                from robot_rfid.orchestrator import APIClient, Orchestrator
                logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
                adapter = OrchestratorRobot(runner)
                task = Orchestrator(APIClient(args.api), adapter, adapter, adapter).run_box(lambda: None)
                log('cycle_ok', cycle=cycle, scenario='orchestrator', task=task)
            else:
                runner.run(cycle)
    except KeyboardInterrupt:
        log('interrupted', cycle=cycle)
        code = 130
    except Exception as error:  # noqa: BLE001 - stop on anything, never retry motion
        log('error', cycle=cycle, type=type(error).__name__, message=str(error))
        code = 1
    finally:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            raw.stop()
            log('move_stop_sent')
        except Exception as error:  # noqa: BLE001
            log('move_stop_failed', message=str(error))
        raw.close()
        log('end', completed_cycles=cycle - (1 if code else 0), exit_code=code)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
