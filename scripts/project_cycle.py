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
        '0B71ED5D': ('wet_tissue', 4)}
OPEN_MAX = 10


class GraspFailed(RuntimeError):
    """The gripper closed empty on every try: stop, tell the operator, and wait for a release."""


class VisionMiss(RuntimeError):
    """The requested item was not found (or not pickable) before the arm moved toward it: the task is
    recorded as failed and the cycle waits for the next one instead of exiting."""

JOINT_TOL = 1.0
POS_TOL = 2.0
# In-air waypoints (approach above / lift out of the grasp) near the far, stretched edge of the work
# area end a few mm off: the controller bends the line near the elbow singularity (seen: 3 mm at
# x 680, J3 15 deg, re-commanding the same pose does not converge). The grasp itself keeps POS_TOL.
WAYPOINT_TOL = 10.0
# Elbow (J3) angle below which a pose is treated as out of comfortable reach. The controller's IK
# clamps J3 to exactly 0 for unreachable poses and reports success; movel then does not move
# (alarm 1206 "NOT REACHABLE") or ends short near the singularity.
ELBOW_MIN_DEG = 20.0
REACH_STEP_MM = 10.0
# Box slot 1's place height (slot z + place_extra) was proven with the taught snack box held 120 mm
# above its bottom. A taller held object hangs further below the fingertip (a bottle grasped at
# 152 mm hit the box at the same height), so raise the place height by the extra hang.
PLACE_REF_HANG_MM = 120.0
# Same proven case as a floor for the held object's bottom (85 + 100 - 120 mm), used when the release
# point itself is taught (poses.box_high taught): release at the taught z, raised only if a long object
# would hang below this.
PLACE_MIN_BOTTOM_MM = 65.0


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
        self.grasp_script = []

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
        """Mock hand. A close (target >= 700) holds an object unless `grasp_script` says otherwise:
        each entry is one close, True = object in the hand, False = closes empty (tests use this)."""
        if target >= 700 and current is not None:
            hold = self.grasp_script.pop(0) if self.grasp_script else True
            self.position = 520 if hold else target
            return dict(code=1, result='ok', voltage=24.1, position_pulses=self.position,
                        current=int(current * 0.95) if hold else 0, moving=0)
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

    def elbow_deg(self, flange_pose):
        """IK elbow angle (J3, deg) for a flange pose in the current solution space; None if IK fails."""
        from dsr_msgs2.srv import GetSolutionSpace, Ikin
        from vision_picking.legacy.ros_calls import call_service
        node, ex = self.ros.node, self.ros.executor
        if not hasattr(self, '_ik'):
            self._ik = node.create_client(Ikin, '/dsr01/motion/ikin')
            self._sol = node.create_client(GetSolutionSpace, '/dsr01/aux_control/get_solution_space')
        posj = self.get_current_posj()
        sol = call_service(ex, self._sol, GetSolutionSpace.Request(pos=[float(v) for v in posj]), 3.0)
        res = call_service(ex, self._ik, Ikin.Request(pos=[float(v) for v in flange_pose],
                                                      sol_space=sol.sol_space, ref=0), 3.0)
        return float(res.conv_posj[2]) if (sol.success and res.success) else None

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


class MobileRemote(threading.Thread):
    """Carries out the Galaxy remote's buttons on the robot.

    The phone only changes state in the web process (POST /api/v1/mobile/control). This thread polls
    GET /api/v1/mobile/status?robot=<mode> (which is also the heartbeat the phone shows as "로봇 연결"):
      - emergency_stop -> move_stop at once, then every later step raises.
      - pause / resume -> a running arm move is stopped at once (move_stop) and redone to the same
        target after resume; a gripper step finishes first. The cycle holds before its next step.
      - start, scan_dispatch, home, box_placed -> queued; the main loop runs them while idle.
      - safety_hold (web/app/safety.py: a person near the zone being picked) -> move_stop at once; the
        cycle waits and redoes the interrupted move when the hold is released ("안전구역 확보").
    It is not a substitute for the pendant E-Stop.
    """

    QUEUED = ('start', 'scan_dispatch', 'home', 'box_placed')

    def __init__(self, api, stop_fn, log, period=0.3, mode='cycle'):
        super().__init__(daemon=True)
        self.api = api.rstrip('/')
        self.url = f'{self.api}/api/v1/mobile/status'
        self.mode = mode
        self.stop_fn, self.log, self.period = stop_fn, log, period
        self.tripped = threading.Event()
        self.estop_active = False  # latest web state; tripped stays set until wait_reset() clears it
        self.paused = threading.Event()
        self.alive = threading.Event()
        self.alive.set()
        self.available = True
        self.busy = False
        self.last_seq = None
        self._commands = []
        self._lock = threading.Lock()
        self.safety = threading.Event()  # set while the work-area safety watch holds the robot
        self.safety_count = 0            # holds/pauses so far: a move running across a new one is redone
        self.moving = False              # an arm move (movej/movel) is running: a pause stops it at once
        self.idle_note = None            # last outcome shown in front of the next '태그 대기 중' message

    def alert(self, kind, message):
        """Operator alert for the phone / web / control program: POST /api/v1/mobile/alert (best effort)."""
        import httpx
        self.log('operator_alert', kind=kind, message=message)
        try:
            httpx.post(f'{self.api}/api/v1/mobile/alert', json={'kind': kind, 'message': message}, timeout=2)
        except Exception as error:  # noqa: BLE001
            self.log('alert_failed', message=str(error))
        if kind == 'grasp_retry':
            self.report('GRASP_RETRY', message)

    def fail_stop(self, message):
        """After a final grasp failure: put the whole system in the E-stop state so the operator must
        look and press [정지 해제] (phone / web / voice) before the robot moves again."""
        import httpx
        try:
            httpx.post(f'{self.api}/api/v1/mobile/control', json={'command': 'emergency_stop'}, timeout=3)
        except Exception as error:  # noqa: BLE001
            self.log('fail_stop_post_failed', message=str(error))
        self._grace_until = time.monotonic() + 2.0  # a status poll that started before the POST must not undo it
        self.estop_active = True
        self.tripped.set()
        self.report('GRASP_FAILED', f'{message} — 로봇을 정지했습니다. 물건과 그리퍼를 확인한 뒤 [정지 해제]를 누르세요.')

    def safety_phase(self, active, zone=None, product=None):
        """Tell the safety watch whether the robot is heading into an object's zone (best effort)."""
        import httpx
        self._phase_active = bool(active)
        try:
            httpx.post(f'{self.api}/api/v1/mobile/safety-phase',
                       json={'active': bool(active), 'zone': zone, 'product': product}, timeout=2)
        except Exception as error:  # noqa: BLE001
            self.log('safety_phase_failed', message=str(error))

    def poll(self):
        """Status dict, or None when the web has no mobile API."""
        import httpx
        r = httpx.get(self.url, params={'robot': self.mode}, timeout=2)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def report(self, state, message=None, ack=None, result=None):
        """Tell the phone what the robot is doing (best effort; never raises)."""
        import httpx
        body = {'mode': self.mode, 'state': state, 'message': message}
        if state in ('IDLE', 'ERROR', 'ESTOPPED') and getattr(self, '_phase_active', False):
            self.safety_phase(False)  # a cycle that ended or failed mid-approach is no longer picking
        if ack is not None:
            body.update(ack_seq=int(ack), ack_result=result or 'done')
        try:
            httpx.post(f'{self.api}/api/v1/mobile/robot-state', json=body, timeout=2)
        except Exception as error:  # noqa: BLE001
            self.log('remote_report_failed', message=str(error))

    def apply(self, status):
        """Update pause/E-stop flags and queue new commands from one status poll."""
        if isinstance(status, bool):  # legacy poll result: E-stop flag only
            status = {'emergency_stopped': status}
        self.estop_active = bool(status.get('emergency_stopped')) or time.monotonic() < getattr(self, '_grace_until', 0.0)
        if status.get('emergency_stopped') and not self.tripped.is_set():
            self.tripped.set()
            self.log('mobile_emergency_stop', action='move_stop')
            try:
                self.stop_fn()
                self.log('move_stop_sent', source='mobile_estop')
            except Exception as error:  # noqa: BLE001
                self.log('move_stop_failed', source='mobile_estop', message=str(error))
        if status.get('safety_hold') and not self.safety.is_set():
            self.safety_count += 1
            self.safety.set()
            self.log('safety_hold', message=status.get('safety_message'), action='move_stop')
            try:
                self.stop_fn()
                self.log('move_stop_sent', source='safety')
            except Exception as error:  # noqa: BLE001
                self.log('move_stop_failed', source='safety', message=str(error))
        elif not status.get('safety_hold') and self.safety.is_set():
            self.safety.clear()
            self.log('safety_clear', message=status.get('safety_message'))
        if status.get('paused') and not status.get('emergency_stopped'):
            if not self.paused.is_set():
                self.paused.set()
                if self.moving:
                    # Stop the running arm move now instead of letting it finish (up to ~15 s); the
                    # cycle redoes that move to the same target after 재개, like after a safety hold.
                    self.safety_count += 1
                    self.log('pause_stop', action='move_stop')
                    try:
                        self.stop_fn()
                    except Exception as error:  # noqa: BLE001
                        self.log('move_stop_failed', source='pause', message=str(error))
        else:
            self.paused.clear()
        commands = status.get('commands') or []
        if self.last_seq is None:
            # Commands pressed before this cycle started are stale: never act on them.
            self.last_seq = int(status.get('command_seq') or 0)
            return
        fresh = [c for c in commands if c.get('seq', 0) > self.last_seq]
        if fresh:
            self.last_seq = max(c['seq'] for c in fresh)
        for c in fresh:
            name = c.get('command')
            self.log('remote_command', seq=c['seq'], command=name, busy=self.busy)
            if name not in self.QUEUED:
                continue  # pause/resume/emergency_stop/reset_stop act through the flags above
            if self.busy:
                self.report('BUSY', f'사이클 진행 중이라 {name} 명령을 건너뜁니다.', ack=c['seq'], result='ignored')
                continue
            with self._lock:
                self._commands.append(c)

    def run(self):
        warned = False
        # Keeps polling after an E-stop: --remote-rfid waits for reset_stop and carries on.
        while self.alive.is_set():
            try:
                status = self.poll()
                if status is None:
                    self.available = False
                    self.log('estop_watch_unavailable', url=self.url)
                    return
                warned = False
                self.apply(status)
            except Exception as error:  # noqa: BLE001
                if not warned:
                    self.log('estop_watch_unreachable', message=str(error))
                    warned = True
            time.sleep(self.period)

    def wait_reset(self):
        """Block until the web shows the E-stop released (phone [정지 해제] or voice 작업 재개)."""
        while self.alive.is_set():
            if self.tripped.is_set() and not self.estop_active:
                self.tripped.clear()
                return True
            time.sleep(self.period)
        return False

    def take(self, wanted):
        """Pop the oldest queued command whose name is in `wanted` (others stay queued)."""
        with self._lock:
            for i, c in enumerate(self._commands):
                if c.get('command') in wanted:
                    return self._commands.pop(i)
        return None

    def post_items(self, items, revision=None):
        """Show depth-camera sightings on the phone's work-area map (best effort)."""
        import httpx
        try:
            httpx.post(f'{self.api}/api/v1/mobile/work-items',
                       json={'source': 'robot_cycle', 'revision': revision, 'items': items}, timeout=2)
        except Exception as error:  # noqa: BLE001
            self.log('remote_items_failed', message=str(error))

    def check(self):
        """Called before/after every motion step: raise on E-stop, hold while paused."""
        if self.tripped.is_set():
            raise RuntimeError('Mobile emergency stop pressed: motion stopped (reset_stop on the phone before restarting)')
        if self.safety.is_set():
            self.report('SAFETY_HOLD', '작업자 접근 — 안전 정지 중입니다. 안전구역이 확보되면 다시 가동합니다.')
            while self.safety.is_set() and not self.tripped.is_set() and self.alive.is_set():
                time.sleep(self.period / 2)
            if self.tripped.is_set():
                raise RuntimeError('Mobile emergency stop pressed during a safety hold')
            self.log('safety_resumed')
            self.report('RUNNING', '안전구역 확보 — 작업을 다시 시작합니다.')
        if self.paused.is_set():
            self.log('remote_paused')
            self.report('PAUSED', '일시정지됨 — 다음 동작 전에 대기 중입니다.')
            while self.paused.is_set() and not self.tripped.is_set():
                time.sleep(self.period / 2)
            if self.tripped.is_set():
                raise RuntimeError('Mobile emergency stop pressed while paused')
            self.log('remote_resumed')
            self.report('RUNNING', '재개 — 사이클을 계속합니다.')


MobileEStopWatch = MobileRemote  # old name used by earlier scripts/tests


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
        motion = poses['motion']
        self.mover = SafeMover(self.z_min, FlangeOffset(raw, self.offset), motion['max_vel'],
                               motion['max_acc'], logger=log)
        # Empty travel moves (home, tag reader, back from the box) may use their own, higher limit.
        self.travel_mover = SafeMover(self.z_min, FlangeOffset(raw, self.offset),
                                      motion.get('travel_max_vel', motion['max_vel']),
                                      motion.get('travel_max_acc', motion['max_acc']), logger=log)
        log('tcp_offset', flange_minus_taught_z=round(dz, 2), applied_offset=self.offset, z_min=self.z_min)
        P = poses['poses']
        # Taught carry: via_point, box_high and the box slot are hand-taught at their real heights.
        self.taught_carry = bool((P.get('box_high') or {}).get('taught'))
        if self.taught_carry:
            self.carry = {}
            tcp = FlangeOffset(raw, self.offset)
            for name in ('via_point', 'box_high'):
                pose = tcp.fkin(P[name]['posj'], DR_BASE)
                if pose is None or max(abs(pose[i] - P[name]['posx'][i]) for i in range(3)) > POS_TOL:
                    raise RuntimeError(f'Taught {name} posx does not match fkin(posj)')
                if pose[2] < self.z_min:
                    raise RuntimeError(f'Taught {name} is below the floor limit')
                self.carry[name] = list(P[name]['posj'])
            log('carry_poses', taught=True, posj=self.carry,
                tcp={k: P[k]['posx'][:3] for k in self.carry}, box_slot_1=poses['box_slots'][1]['posx'][:3])
            self._init_vision(args, log)
            return
        # Carry height: transfer poses raised by --lift-extra so the held object clears the box wall.
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
        self._init_vision(args, log)

    def _init_vision(self, args, log):
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

    def _speed_key(self):
        if getattr(self, '_loaded', False):
            return 'load_speed'
        if getattr(self, '_to_pick', False):
            return 'empty_speed'
        return 'travel_speed'

    def speed(self):
        """Speed factor: --load-speed from the descend onto the object until it is released,
        --empty-speed on the way to the object, --travel-speed for every other empty move
        (home, tag reader, back from the box)."""
        key = self._speed_key()
        return float(getattr(self.args, key, None) or getattr(self.args, 'empty_speed', 1.0) or 1.0)

    def _travel(self, absolute):
        """(vel, mover) override for an empty travel move when --travel-jvel/--travel-lvel is given: an
        absolute speed checked against poses.yaml travel_max_vel/acc instead of max_vel/acc."""
        if absolute is None or self._speed_key() != 'travel_speed':
            return None
        return float(absolute), getattr(self, 'travel_mover', self.mover)

    def _guarded(self, name, move):
        """Run one move; if a safety hold stopped it part-way, wait for "안전구역 확보" and move to the
        same target again (the target is absolute, so redoing it simply finishes the move)."""
        remote = getattr(self, 'estop', None)
        holds = lambda: getattr(remote, 'safety_count', 0)  # noqa: E731
        for attempt in range(20):
            self._estop_check()  # waits here while a safety hold or pause is active
            count = holds()
            if remote is not None:
                remote.moving = True
            try:
                move()
            except Exception:
                if holds() == count:
                    raise
                self.log('safety_redo', name=name, attempt=attempt + 1, note='move stopped by a safety hold or pause')
                continue
            finally:
                if remote is not None:
                    remote.moving = False
            if holds() != count:
                self.log('safety_redo', name=name, attempt=attempt + 1, note='move stopped by a safety hold or pause')
                continue
            self._estop_check()
            return
        raise RuntimeError(f'{name}: interrupted by the safety watch too many times')

    def _safety_phase(self, active):
        """Pick phase for the work-area safety watch: from the approach to the grasp only."""
        remote = getattr(self, 'estop', None)
        if remote is None or not hasattr(remote, 'safety_phase') or getattr(remote, '_phase_active', False) == active:
            return
        zone = getattr(self, '_zone', None)
        zones = (getattr(self, 'depth_cfg', None) or {}).get('zones') or {}
        if zone is None and zones:
            zone = next((int(z) for z, name in zones.items() if name == getattr(self, '_product', None)), None)
        remote.safety_phase(active, zone, getattr(self, '_product', None))
        self.log('safety_phase', active=active, zone=zone, product=getattr(self, '_product', None))

    def j(self, name, posj):
        t0 = time.monotonic()
        jvel, mover = self._travel(getattr(self.args, 'travel_jvel', None)) or (self.args.jvel * self.speed(), self.mover)
        self._guarded(name, lambda: mover.movej(posj, jvel, jvel))
        cur = self.raw.get_current_posj()
        err = max(abs(a - b) for a, b in zip(cur, posj))
        if err > JOINT_TOL:
            raise RuntimeError(f'{name}: joint arrival error {err:.2f} deg')
        self.log('step', name=name, kind='movej', vel=round(jvel, 1), seconds=round(time.monotonic() - t0, 1))

    def l(self, name, pose, vel=None, tol=POS_TOL, scaled=True):
        t0 = time.monotonic()
        # Only default transfer moves (vel None) go fast; explicit slow ones (descents, recovery) stay.
        fast = self._travel(getattr(self.args, 'travel_lvel', None)) if vel is None and scaled else None
        vel, mover = fast or ((vel or self.args.lvel) * (self.speed() if scaled else 1.0), self.mover)
        self._guarded(name, lambda: mover.movel(pose, vel, vel, DR_BASE))
        cur = FlangeOffset(self.raw, self.offset).get_current_posx(DR_BASE)
        err = max(abs(a - b) for a, b in zip(cur[:3], pose[:3]))
        if err > tol:
            raise RuntimeError(f'{name}: TCP arrival error {err:.1f} mm')
        if err > POS_TOL:
            self.log('arrival_offset', name=name, error_mm=round(err, 1), tolerance_mm=tol)
        self.log('step', name=name, kind='movel', tcp=[round(v, 1) for v in cur[:3]], vel=round(vel, 1),
                 seconds=round(time.monotonic() - t0, 1))

    def grip(self, name, target, ok, current=None, settle_s=0.0):
        self._estop_check()
        t0 = time.monotonic()
        fb = self.raw.grip(target, current)
        command_s = time.monotonic() - t0
        if command_s > 8.0:  # normally ~4 s; the controller's DRL start/report was slow
            self.log('gripper_slow', name=name, seconds=round(command_s, 1))
        # At a low force limit the fingers keep creeping into a soft or slipping object for a
        # moment after the DRL settle time; poll the status until they stop (code 1, moving 0).
        deadline = time.monotonic() + settle_s
        while fb['code'] == 1 and fb['moving'] and time.monotonic() < deadline:
            time.sleep(0.5)
            fb = self.raw.grip(-1)
        if fb['code'] != 1 or fb['moving'] or not ok(fb['position_pulses']):
            raise RuntimeError(f"{name}: gripper not confirmed ({fb['result']}, pos={fb['position_pulses']})")
        self.log('step', name=name, kind='gripper', position=fb['position_pulses'], current=fb['current'],
                 seconds=round(time.monotonic() - t0, 1))
        return fb

    # ---- Steps matching robot_rfid.orchestrator.Orchestrator's robot interface ----
    def pre_scan(self):
        P = self.poses['poses']
        self.raw.check_ready()
        # Recovery: if an earlier stop left the tool low, rise straight up before any joint move.
        self._recovery_rise()
        self.j('home', P['home']['posj'])
        self.j('label_scan_approach', P['label_scan_approach']['posj'])
        scan_hi = P['label_scan_approach']['posx']
        # Down onto the tag at the same speed as label_scan_retract goes back up (operator choice).
        self.l('label_scan', [*scan_hi[:2], P['label_scan']['posx'][2], *scan_hi[3:]])

    def scan(self):
        uid = self.raw.scan()
        if uid:
            self.log('rfid', uid=uid, reader='real')
        elif self.args.tag:  # only when the operator passed --tag explicitly
            uid = self.args.tag
            self.log('rfid', uid=uid, reader='preset')
        else:
            self.scan_retract()
            raise RuntimeError('RFID reader read no tag (no reader on this PC?); not inventing one')
        self.scan_retract()
        return uid

    def scan_retract(self):
        P = self.poses['poses']
        self.l('label_scan_retract', P['label_scan_approach']['posx'])
        self.j('home_after_scan', P['home']['posj'])

    def correct_base(self, base):
        """Depth-camera BASE x,y -> measured robot x,y (depth_picking.base_correction, hand-taught points)."""
        corr = self.depth_cfg.get('base_correction')
        if not corr:
            return [float(base[0]), float(base[1])]
        (a, b, c), (d, e, f) = corr['affine']
        x, y = float(base[0]), float(base[1])
        cx, cy = a * x + b * y + c, d * x + e * y + f
        limit = float(corr.get('max_shift_mm', 30.0))
        if math.hypot(cx - x, cy - y) > limit:
            raise RuntimeError(f'base correction moves ({x:.0f}, {y:.0f}) by more than {limit:.0f} mm; '
                               'the object is outside the corrected area or the correction is stale')
        return [round(cx, 1), round(cy, 1)]

    def detect_by_depth(self, product):
        """Locate `product` with the depth camera: the object in its corner zone of the work area."""
        import httpx
        zones = {int(k): v for k, v in self.depth_cfg['zones'].items()}
        zone = next((z for z, name in zones.items() if name == product), None)
        if zone is None:
            raise RuntimeError(f'no depth zone is assigned to {product}')
        self._zone = zone  # the safety watch guards this zone during the approach
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
        return self._grasp_from_object(product, obj, zone, source=f'depth camera zone {zone}')

    def detect_by_yolo(self, product):
        """Locate `product` anywhere in the work area: the product YOLO box (web /api/product-vision/locate)
        picks the depth object under it, so no fixed zone per product is needed."""
        import httpx
        url = f"{self.args.depth_api.rstrip('/')}/api/product-vision/locate"
        samples = []
        for i in range(int(self.depth_cfg.get('samples', 3))):
            if i:
                time.sleep(0.3)
            response = httpx.get(url, params={'product': product}, timeout=15)
            if response.status_code == 404:
                raise RuntimeError(response.json().get('detail') or f'YOLO did not find {product}')
            data = response.raise_for_status().json()
            if data.get('revision') != self.cal_revision:
                raise RuntimeError('web calibration revision differs from --picking-config; re-export the calibration')
            samples.append(data)
        tol = float(self.depth_cfg.get('stable_tol_mm', 10.0))
        obj = samples[-1]['object']
        if any(math.dist(s['object']['base'], obj['base']) > tol or
               abs(s['object']['height_mm'] - obj['height_mm']) > tol for s in samples):
            raise RuntimeError(f'{product} is not steady across {len(samples)} frames '
                               '(person or moving object over the table?)')
        zone = obj.get('corner')
        self._zone = zone  # the safety watch guards the nearest corner zone during the approach
        conf = samples[-1]['detection']['confidence']
        return self._grasp_from_object(product, obj, zone, source=f'yolo {conf:.2f}')

    def _grasp_from_object(self, product, obj, zone, source):
        """Grasp pose for a depth object (base X/Y, height, footprint, short-axis yaw)."""
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
        top_z = self.poses['floor']['floor_z'] + obj['height_mm']
        # The palm sits finger_depth above the fingertip: never bite so deep that it presses on the top.
        finger = self.depth_cfg.get('finger_depth_mm')
        if finger is not None:
            max_bite = float(finger) - float(self.depth_cfg.get('palm_clearance_mm', 15.0))
            if top_z - grasp_info['grasp_z_mm'] > max_bite:
                self.log('grasp_bite_limited', product=product, wanted_z=grasp_info['grasp_z_mm'],
                         z=round(top_z - max_bite, 2), max_bite_mm=max_bite)
                grasp_info = dict(grasp_info, grasp_z_mm=round(top_z - max_bite, 2),
                                  height_from_floor_mm=round(obj['height_mm'] - max_bite, 2))
        if grasp_info['grasp_z_mm'] >= top_z:
            raise RuntimeError(f"grasp height {grasp_info['grasp_z_mm']} mm is not below the object top")
        close0 = self.depth_cfg.get('gripper_close_yaw_at_rz0_deg')
        if close0 is None or obj.get('short_axis_yaw_deg') is None:
            rz = item.get('rz', 0.0)
        else:  # fingers close along base yaw (close0 - rz) for tool orientation (0, 180, rz)
            rz = (float(close0) - obj['short_axis_yaw_deg'] + 90.0) % 180.0 - 90.0
        x, y = self.correct_base(obj['base'])
        self.log('vision', source=source, product=product, base=[x, y], camera_base=obj['base'],
                 height_mm=obj['height_mm'], footprint_mm=obj.get('footprint_mm'),
                 short_axis_yaw=obj.get('short_axis_yaw_deg'), rz=round(rz, 1), grasp_z=grasp_info['grasp_z_mm'])
        remote = getattr(self, 'estop', None)
        if remote is not None and hasattr(remote, 'post_items'):
            item = {'zone': zone, 'product': product, 'base': [x, y], 'height_mm': obj['height_mm']}
            if obj.get('footprint_mm'):
                item['footprint_mm'] = obj['footprint_mm']
            if obj.get('short_axis_yaw_deg') is not None:
                item['short_axis_yaw_deg'] = obj['short_axis_yaw_deg']
            remote.post_items([item], getattr(self, 'cal_revision', None))
        return dict(product=product, pose=[x, y, grasp_info['grasp_z_mm'], 0.0, 180.0, rz],
                    grid_cell=None, grasp_info=grasp_info)

    def detect(self, task):
        product = task.get('yolo_class_name') if isinstance(task, dict) else task
        self._zone = None
        if getattr(self.args, 'depth_api', None):
            if getattr(self.args, 'vision', 'zone') == 'yolo':
                return self.detect_by_yolo(product)
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

    def reach_z(self, name, pose, want_z, min_z):
        """Highest fingertip z <= want_z (10 mm steps, >= min_z) the arm reaches with elbow >= ELBOW_MIN_DEG."""
        elbow_deg = getattr(self.raw, 'elbow_deg', None)
        if elbow_deg is None:  # mock robot: no kinematic limit model
            return want_z
        z = want_z
        while z >= min_z - 1e-6:
            elbow = elbow_deg([pose[0], pose[1], z + self.offset, *pose[3:6]])
            if elbow is not None and abs(elbow) >= ELBOW_MIN_DEG:
                if z < want_z:
                    self.log('reach_limited', name=name, wanted_z=round(want_z, 1), z=round(z, 1), elbow_deg=round(elbow, 1))
                return z
            z -= REACH_STEP_MM
        raise RuntimeError(f'{name}: x {pose[0]:.0f} y {pose[1]:.0f} is too far to stay {min_z:.0f} mm high '
                           '(elbow near full stretch); move the object closer to the robot')

    def approach(self, target):
        up = self.poses['motion']['approach_offset_z']
        grasp = target['pose']
        info = target.get('grasp_info') or {}
        floor_z = self.poses['floor']['floor_z']
        height = info.get('measured_height_mm') or info.get('nominal_height_mm')
        # Fingers must clear the object top on the way down, and lift it at least as high.
        min_z = floor_z + height + 20.0 if height else grasp[2] + 40.0
        approach_z = self.reach_z('approach', grasp, grasp[2] + up, min_z)
        above_z = self.reach_z('lift', grasp, grasp[2] + up + self.args.lift_extra, approach_z)
        self._to_pick = True  # pre_approach / approach at --empty-speed
        self._hang = max(0.0, grasp[2] - floor_z)  # held object length below the fingertip
        self._approach = [*grasp[:2], approach_z, *grasp[3:]]
        self._above = [*grasp[:2], above_z, *grasp[3:]]
        self._product = target['product']
        self._safety_phase(True)  # from here to the grasp a person near this zone holds the robot
        self.grip('gripper_open', 0, lambda p: p <= OPEN_MAX)
        if getattr(self, 'taught_carry', False):
            # Mirror of pull_in: a low approach on the far side would otherwise be a long descending
            # line from the via_point over the other zones. Arrive at the via height on the same
            # radial line first, then go out and down to the approach point.
            pre = self._inward_at_carry('pre_approach', self._approach)
            if pre is not None:
                self.l('pre_approach', pre, tol=WAYPOINT_TOL)
        grid_info = target.get('grid_cell') if isinstance(target, dict) else None
        if grid_info is not None:
            cell_xy = grid_info['cell_center_base_mm'][:2]
            self._grid_approach = [cell_xy[0], cell_xy[1], approach_z, *grasp[3:]]
            self.l('grid_coarse_approach', self._grid_approach, tol=WAYPOINT_TOL)
        self.l('approach', self._approach, tol=WAYPOINT_TOL)
        self._loaded, self._to_pick = True, False  # descend, grasp, carry and place at --load-speed
        self.l('descend', grasp, self.args.dvel)

    def _close_gripper(self):
        item = (self.products.get(getattr(self, '_product', None)) or {}).get('real') or {}
        limit = int(item.get('grip_current_ma') or getattr(self.args, 'grip_current', 150))
        closed = self.grip('grip', 740, lambda p: p >= 0, current=limit, settle_s=4.0)
        # Empty close reaches ~739 at low current; an object stalls the fingers earlier, or (thin
        # or soft packs) near full close with the current pinned at the limit.
        self.holding = closed['position_pulses'] < 700 or (
            closed['position_pulses'] < 735 and closed['current'] >= 0.8 * limit)
        self.log('grasp', product=self._product, holding=self.holding, position=closed['position_pulses'],
                 current=closed['current'], current_limit=limit, note='object detected' if self.holding else 'empty close (no object)')

    def _alert(self, kind, message):
        """Tell the phone, the web and the control program (best effort)."""
        remote = getattr(self, 'estop', None)
        if remote is not None and hasattr(remote, 'alert'):
            remote.alert(kind, message)

    def _regrasp(self, attempt, retries):
        """Empty close: open, rise straight up off the spot, look for the object again, approach again."""
        product = getattr(self, '_product', None)
        name = (self.products.get(product) or {}).get('name') or product
        self.log('grasp_retry', product=product, attempt=attempt, retries=retries)
        self._alert('grasp_retry', f'{name} 파지에 실패해 다시 시도합니다 ({attempt}/{retries})')
        self._loaded, self._to_pick = False, True
        self.grip('gripper_open', 0, lambda p: p <= OPEN_MAX)
        self.l('retry_rise', self._approach, tol=WAYPOINT_TOL)
        self.approach(self.detect(product))  # the object may have been nudged: measure it again

    def grip_object(self):
        retries = max(0, int(getattr(self.args, 'grasp_retries', 0) or 0))
        for attempt in range(retries + 1):
            self._close_gripper()
            if self.holding:
                return
            if attempt < retries:
                self._regrasp(attempt + 1, retries)
        if retries:
            message = f"파지 실패: {retries + 1}번 시도했지만 그리퍼가 빈 채로 닫혔습니다 ({getattr(self, '_product', '')})"
            self.log('grasp_failed', product=getattr(self, '_product', None), attempts=retries + 1)
            self._alert('grasp_failed', message)
            raise GraspFailed(message)
        if self.args.require_object:
            raise RuntimeError('No object in the gripper (empty close)')

    def retract(self):
        self._safety_phase(False)  # carrying to the box: no work-area warnings
        self.l('lift', self._above, tol=WAYPOINT_TOL)
        if self.taught_carry:
            self._pull_in()
            return  # place() goes on to the taught via_point
        home = self.poses['poses']['home']['posx']
        self.l('home_carry', [home[0], home[1], home[2] + self.args.lift_extra, *home[3:]])

    def _inward_at_carry(self, name, pose):
        """Point on the line from the robot to `pose` (same orientation) at the via_point height that the
        arm reaches comfortably, or None when `pose` is already at or above that height."""
        carry_z = self.poses['poses']['via_point']['posx'][2]
        if pose[2] >= carry_z - POS_TOL:
            return None
        elbow_deg = getattr(self.raw, 'elbow_deg', None)
        for scale in [1.0 - 0.05 * i for i in range(11)]:  # down to half the radius
            target = [pose[0] * scale, pose[1] * scale, carry_z, *pose[3:6]]
            if elbow_deg is None:
                return target
            elbow = elbow_deg([*target[:2], carry_z + self.offset, *target[3:6]])
            if elbow is not None and abs(elbow) >= ELBOW_MIN_DEG:
                return target
        raise RuntimeError(f'{name}: cannot reach {carry_z:.0f} mm even at half the radius')

    def _pull_in(self):
        """Far side of the table: the stretched arm cannot lift to the via_point height there, and a
        joint move from that low lift would sweep the held object over the neighbouring zones. Pull the
        object straight in toward the robot while rising until the via_point height is reachable."""
        target = self._inward_at_carry('pull_in', self._above)
        if target is None:
            return
        self.log('pull_in', from_tcp=[round(v, 1) for v in self._above[:3]], to_tcp=[round(v, 1) for v in target[:3]])
        self.l('pull_in', target, tol=WAYPOINT_TOL)

    def place(self, box_id=1):
        P, up = self.poses['poses'], self.poses['motion']['approach_offset_z']
        slot = int(str(box_id).split('-')[-1]) if box_id else 1
        if not (self.poses['box_slots'].get(slot) or {}).get('taught'):
            self.log('box_fallback', requested=box_id, used_slot=1, reason='slot not taught')
            slot = 1
        slot_pose = self.poses['box_slots'][slot]['posx']
        self.j('via_carry', self.carry['via_point'])
        self.j('box_carry', self.carry['box_high'])
        if self.taught_carry:
            hang = getattr(self, '_hang', 0.0)
            extra = max(0.0, PLACE_MIN_BOTTOM_MM - (slot_pose[2] - hang))
            if extra:
                self.log('place_raised', hang_mm=round(hang, 1), extra_mm=round(extra, 1))
            self.l('box_place', [*slot_pose[:2], slot_pose[2] + extra, *slot_pose[3:]], self.args.dvel)
            self.grip('release', 0, lambda p: p <= OPEN_MAX)
            self._loaded = False  # empty again
            self.l('box_retreat', P['box_high']['posx'])
            self.j('via_return', self.carry['via_point'])
            self.last_slot = slot
            return
        extra = max(0.0, getattr(self, '_hang', 0.0) - PLACE_REF_HANG_MM)
        if extra:
            self.log('place_raised', hang_mm=round(self._hang, 1), extra_mm=round(extra, 1))
        self.l('box_place', [*slot_pose[:2], slot_pose[2] + self.args.place_extra + extra, *slot_pose[3:]], self.args.dvel)
        self.grip('release', 0, lambda p: p <= OPEN_MAX)
        self._loaded = False
        carry_z = P['home']['posx'][2] + self.args.lift_extra
        self.l('box_retreat', [*slot_pose[:2], carry_z, *slot_pose[3:]])
        self.j('via_return', self.carry['via_point'])
        self.last_slot = slot

    def home(self):
        self.j('home_return', self.poses['poses']['home']['posj'])

    def recover_home(self):
        """After a stop mid-motion: rise straight up to the home height, then go home."""
        self._safety_phase(False)
        self._recovery_rise()
        self.home()

    def _recovery_rise(self):
        """Rise straight up toward the home height before a joint move. On the far, stretched side of the
        work area only as high as the arm still reaches (a full-height rise there stopped 2.4 mm short and
        ended the cycle after an E-stop release)."""
        cur = FlangeOffset(self.raw, self.offset).get_current_posx(DR_BASE)
        safe_z = self.poses['poses']['home']['posx'][2]
        if cur is None or cur[2] >= safe_z - POS_TOL:
            return
        z = self.reach_z('recovery_rise', cur, safe_z, cur[2])
        self.log('recovery', tcp=[round(v, 1) for v in cur[:3]], rise_to=round(z, 1))
        if z > cur[2] + POS_TOL:
            self.l('recovery_rise', [cur[0], cur[1], z, *cur[3:6]], self.args.dvel)

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


def remote_home(runner, remote, cmd):
    """Phone [홈 자세 복귀] while idle."""
    remote.busy = True
    remote.report('RETURNING_HOME', '홈 자세로 복귀 중입니다.', ack=cmd['seq'], result='done')
    try:
        runner.home()
    except Exception as error:
        remote.report('ERROR', f'홈 복귀 실패: {error}', ack=cmd['seq'], result='failed')
        raise
    finally:
        remote.busy = False
    remote.report('IDLE', '홈 복귀 완료 — 대기 중입니다.')


def last_scan_seq(api):
    return (api.get('/api/v1/last-scan').raise_for_status().json().get('last_scan') or {}).get('seq')


def wait_bridge_scan(api, before_seq, timeout, check, period=0.3):
    """The next tag read the web recorded after `before_seq` (any source), or None after `timeout` s."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check()
        scan = api.get('/api/v1/last-scan').raise_for_status().json().get('last_scan')
        if scan and scan.get('seq') != before_seq:
            return scan
        time.sleep(period)
    return None


def remote_scan(runner, remote, api, cmd, log):
    """Phone [리더기 스캔 출동] with the reader on the arm: lower it onto the box tag and wait for the
    Windows bridge to send what it read (its POST /api/v1/scan-event queues the task, which the main
    loop then picks). Nothing is queued when no tag arrives in time; a tag is never invented."""
    remote.busy = True
    remote.report('SCANNING', '리더기 위치로 이동해 태그를 읽습니다.', ack=cmd['seq'], result='done')
    wait_s = float(getattr(runner.args, 'scan_wait', 10.0))
    try:
        before = last_scan_seq(api)  # before moving: a read during the descent still counts
        runner.pre_scan()
        log('scan_waiting', seconds=wait_s, note='waiting for the Windows bridge to send the tag UID')
        remote.report('SCANNING', f'태그 대기 중 (최대 {wait_s:.0f}초) — 리더기가 태그를 읽으면 작업이 등록됩니다.')
        scan = wait_bridge_scan(api, before, wait_s, runner._estop_check)
        runner.scan_retract()
        if scan is None:
            log('remote_scan_timeout', seconds=wait_s)
            remote.report('IDLE', f'{wait_s:.0f}초 안에 태그가 읽히지 않아 작업을 만들지 않았습니다.')
        elif not scan.get('accepted'):
            log('remote_scan_rejected', uid=scan.get('raw_uid'), detail=scan.get('error'))
            remote.report('IDLE', f"태그 {scan.get('raw_uid')} 거부: {scan.get('error')}")
        else:
            log('remote_scan_queued', uid=scan.get('uid'), task_id=scan.get('task_id'), product=scan.get('product_name'))
    finally:
        remote.busy = False


def wait_remote_trigger(runner, remote, log, triggers, timeout=0.0):
    """Idle until the phone sends one of `triggers`; [홈 복귀] runs in the meantime. Returns the command."""
    remote.busy = False
    remote.report('IDLE', '대기 중 — 리모컨의 [작업 시작] 또는 [리더기 스캔 출동]을 누르세요.')
    log('waiting_for_phone', triggers=list(triggers))
    started = time.monotonic()
    while True:
        runner._estop_check()
        cmd = remote.take(('home', *triggers))
        if cmd is not None and cmd['command'] == 'home':
            remote_home(runner, remote, cmd)
            continue
        if cmd is not None:
            remote.busy = True
            remote.report('RUNNING', f"{cmd['command']} — 사이클을 시작합니다.", ack=cmd['seq'], result='done')
            return cmd
        if timeout and time.monotonic() - started > timeout:
            raise TimeoutError(f'No phone trigger within {timeout:.0f}s')
        time.sleep(0.2)


def box_check(api, step, log, label=None):
    """Packing-box webcam (web/app/box_check.py): 'reference' at home before the pick, 'verify' after placing.

    Best effort: a missing webcam or reference is logged and never stops the robot."""
    try:
        return api.post(f'/api/box-check/{step}', json={'label': label}, timeout=10).raise_for_status().json()
    except Exception as error:  # noqa: BLE001
        log('box_check_unavailable', step=step, message=str(error))
        return None


def finish_held_item(runner, args, watch, log):
    """After an E-stop reset with an item still in the gripper: put it in the box instead of going home
    holding it (the next task would open the gripper at home and drop it). The task stays DEFECTIVE
    (interrupted by the E-stop); a stop during this place is handled by the main loop again."""
    import httpx
    product = getattr(runner, '_product', None)
    box = getattr(runner, '_task_box', None)
    log('estop_finish_place', product=product, box=box)
    watch.report('RUNNING', '정지 전에 잡고 있던 물품을 상자에 넣습니다.')
    runner.place(box)
    runner.home()
    result = None
    if getattr(args, 'box_check', False):
        with httpx.Client(base_url=args.api, timeout=10) as api:
            result = box_check(api, 'verify', log, f'{product} (비상정지 후 마무리)')
    log('estop_finish_placed', product=product, verdict=result and result['verdict'])
    text = '' if result is None else f" · {result['text']}"
    watch.idle_note = f'정지 전에 잡고 있던 물품을 상자에 넣었습니다{text}. 작업은 비상정지로 중단 기록됩니다.'
    watch.report('IDLE', watch.idle_note)


def run_remote_task(runner, args, log, cycle):
    """Execute the next task another PC queued through POST /api/v1/scan-event (UID -> DB match on the web)."""
    import httpx
    api = httpx.Client(base_url=args.api, timeout=10)
    remote = runner.estop if isinstance(runner.estop, MobileRemote) else None
    runner.raw.check_ready()
    runner.home()
    log('waiting_for_tag', api=args.api, note='scan a tag on the remote reader PC')
    if remote is not None:
        remote.busy = False
        # keep the last outcome (skipped item, item placed after an E-stop) visible on the phone
        note, remote.idle_note = getattr(remote, 'idle_note', None), None
        remote.report('IDLE', (f'{note} — ' if note else '')
                      + '태그 대기 중 — 상자 배치 버튼, 리더기 스캔 출동, 홈 복귀를 사용할 수 있습니다.')
    started = time.monotonic()
    while True:
        task = api.get('/api/v1/current-task').raise_for_status().json()['task']
        if task is not None:
            break
        runner._estop_check()
        if remote is not None:
            cmd = remote.take(('home', 'scan_dispatch', 'start', 'box_placed'))
            if cmd is not None and cmd['command'] == 'home':
                remote_home(runner, remote, cmd)
            elif cmd is not None and cmd['command'] == 'scan_dispatch':
                remote_scan(runner, remote, api, cmd, log)
            elif cmd is not None:
                # Box tasks are queued by the web itself; start just confirms the cycle is waiting.
                remote.report('IDLE', '대기 중 — 등록된 상자 작업을 확인합니다.', ack=cmd['seq'], result='done')
        if args.wait_timeout and time.monotonic() - started > args.wait_timeout:
            raise TimeoutError(f'No remote RFID task within {args.wait_timeout:.0f}s')
        time.sleep(0.5)
    if remote is not None:
        remote.busy = True
        remote.report('PICKING', f"{task.get('product_name') or task.get('yolo_class_name')} 피킹을 시작합니다.")
    if task['status'] == 'PICKING':
        raise RuntimeError('Interrupted PICKING task requires operator reconciliation')
    tid, completed = task['task_id'], task['completed']
    runner._task_box = task.get('target_box_id')  # an E-stop while carrying finishes into this box
    log('task', task_id=tid, uid=task.get('tag_uid'), product=task.get('yolo_class_name'),
        name=task.get('product_name'), box=task.get('target_box_id'), quantity=task['quantity'])
    patch = lambda done, status, error=None: api.patch(  # noqa: E731
        f'/api/v1/tasks/{tid}', json=dict(completed=done, status=status, error=error)).raise_for_status()
    name = task.get('product_name') or task.get('yolo_class_name')
    box_failures = []
    # The arm is at home (out of the box webcam's view): picture of the box before this task's items go in.
    checking = getattr(args, 'box_check', False) and box_check(api, 'reference', log, f'{name} 작업 전') is not None
    try:
        patch(completed, 'PICKING')
        while completed < task['quantity']:
            try:
                target = runner.detect(task)
            except RuntimeError as error:  # nothing moved toward the item yet: skip, do not stop the cycle
                raise VisionMiss(str(error)) from error
            runner.approach(target)
            runner.grip_object()
            runner.retract()
            runner.place(task.get('target_box_id'))
            completed += 1
            if checking:
                runner.home()  # move the arm out of the box webcam's view before the picture
                result = box_check(api, 'verify', log, f"{name} {completed}/{task['quantity']}")
                if result is not None:
                    log('box_check', task_id=tid, item=completed, verdict=result['verdict'], change=result['change'])
                    if not result['ok']:  # record only: the cycle carries on
                        box_failures.append(f"{completed}번째 {result['text']}")
                        if remote is not None:
                            remote.report('PICKING', f"상자 투입 확인 실패 · {result['text']} (기록 후 계속 진행)")
            patch(completed, 'PICKING')
        if box_failures:
            patch(completed, 'DEFECTIVE', '상자 투입 확인 실패: ' + ', '.join(box_failures))
        else:
            patch(completed, 'COMPLETED')
        runner.home()
        log('cycle_ok', cycle=cycle, scenario='remote_rfid', task_id=tid, product=target['product'],
            box_slot=runner.last_slot, holding=runner.holding, box_check=box_failures or ('ok' if checking else 'off'))
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
    parser.add_argument('--tag', default=None,
                        help='preset tag used when the reader reads nothing (only if given; never assumed)')
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
    parser.add_argument('--empty-speed', type=float, default=1.875,
                        help='speed factor (x jvel/lvel/dvel) on the way to the object (gripper empty)')
    parser.add_argument('--travel-speed', type=float, default=2.25,
                        help='speed factor for the other empty moves: home, to/from the tag reader, back from the box')
    parser.add_argument('--travel-jvel', type=float, default=None,
                        help='deg/s for empty travel movej (home, tag reader, back from the box), '
                             'limited by poses.yaml travel_max_vel/acc instead of max_vel/acc')
    parser.add_argument('--travel-lvel', type=float, default=None,
                        help='mm/s for empty travel movel (tag reader down/up, retreat from the box)')
    parser.add_argument('--load-speed', type=float, default=1.5625,
                        help='speed factor from the descend to the grasp until the release (holding the object)')
    parser.add_argument('--scan-wait', type=float, default=10.0,
                        help='[리더기 스캔 출동]: seconds to wait at the reader for the Windows bridge to send a tag')
    parser.add_argument('--require-object', action='store_true',
                        help='fail when the gripper closes empty (only with --grasp-retries 0; retries always fail the cycle)')
    parser.add_argument('--grasp-retries', type=int, default=1,
                        help='empty close: open, rise, re-detect and try again this many times; still empty -> '
                             'stop, alert phone/web/control program and wait for [정지 해제] (0 = old behaviour)')
    parser.add_argument('--remote-rfid', action='store_true',
                        help='with --api: wait for tasks queued by another PC (POST /api/v1/scan-event) instead of scanning')
    parser.add_argument('--vision', choices=['zone', 'yolo'], default='zone',
                        help="with --depth-api: 'zone' = one product per corner zone, 'yolo' = the product YOLO "
                             '(web /api/product-vision) finds it anywhere in the work area')
    parser.add_argument('--box-check', action='store_true',
                        help='remote mode: confirm each placed item landed in the box with the packing-box webcam '
                             '(web /api/box-check); a failed check marks the task DEFECTIVE but does not stop')
    parser.add_argument('--wait-timeout', type=float, default=0, help='remote mode: seconds to wait per task, 0 = forever')
    parser.add_argument('--api', help='run the repo RFID Orchestrator against this web API, e.g. http://127.0.0.1:8000')
    parser.add_argument('--remote-trigger', action='store_true',
                        help='with --api (orchestrator mode): wait for the Galaxy remote [작업 시작]/[리더기 스캔 출동]/'
                             '상자 배치 button before each cycle instead of starting immediately')
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
    if args.remote_trigger and (not args.api or args.remote_rfid):
        parser.error('--remote-trigger requires --api and does not combine with --remote-rfid (which already waits)')
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
    watch = None
    try:
        runner = Cycle(raw, poses, products, args, log)
        if args.api:
            mode = 'remote_rfid' if args.remote_rfid else ('remote_trigger' if args.remote_trigger else 'orchestrator')
            watch = MobileRemote(args.api, raw.emergency_stop, log, mode=mode)
            try:
                status = watch.poll()
                if status and status.get('emergency_stopped'):
                    raise RuntimeError('Mobile emergency stop is active; press reset_stop on the phone first')
                if status:
                    watch.apply(status)  # remembers the current command seq so old presses are ignored
            except RuntimeError:
                raise
            except Exception as error:  # noqa: BLE001
                log('estop_watch_unreachable', message=str(error))
            watch.start()
            runner.estop = watch
            log('estop_watch', url=watch.url, mode=mode,
                note='phone E-stop -> move_stop, pause/resume between steps; pendant E-Stop is still the real safety stop')
        while args.cycles == 0 or cycle < args.cycles:
            cycle += 1
            if args.api and args.remote_rfid:
                try:
                    run_remote_task(runner, args, log, cycle)
                except RuntimeError as error:
                    if isinstance(error, VisionMiss) and not (watch is not None and watch.tripped.is_set()):
                        # Task already DEFECTIVE with the reason; the arm is still at home.
                        log('task_skipped', cycle=cycle, message=str(error))
                        if watch is not None:
                            watch.busy = False
                            watch.idle_note = f'물품을 찾지 못해 작업을 건너뛰었습니다: {error}'
                            watch.report('IDLE', watch.idle_note)
                        continue
                    grasp_failed = isinstance(error, GraspFailed) and watch is not None
                    if not (watch is not None and watch.tripped.is_set()) and not grasp_failed:
                        raise
                    # E-stop (or a grasp that failed on every try): motion already stopped (task marked
                    # DEFECTIVE if it was running). Hold until it is released, then recover and wait
                    # for the next task.
                    log('estop_hold', cycle=cycle, message=str(error), grasp_failed=grasp_failed)
                    watch.busy = True
                    if grasp_failed:
                        watch.fail_stop(str(error))
                    else:
                        watch.report('ESTOPPED', '비상 정지 — 정지 해제(또는 음성 "작업 재개")를 기다립니다.')
                    if not watch.wait_reset():
                        raise
                    log('estop_released', cycle=cycle)
                    watch.report('RUNNING', '정지 해제 — 홈으로 복귀합니다.')
                    runner.raw.check_ready()
                    if grasp_failed:  # the fingers are still closed on nothing
                        runner.grip('gripper_open', 0, lambda p: p <= OPEN_MAX)
                    runner.recover_home()
                    if not grasp_failed and getattr(runner, '_loaded', False) and getattr(runner, 'holding', False):
                        finish_held_item(runner, args, watch, log)
                    watch.busy = False
                    continue
            elif args.api:
                import logging
                from robot_rfid.orchestrator import APIClient, Orchestrator
                logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
                adapter = OrchestratorRobot(runner)
                if args.remote_trigger:
                    trigger = lambda: wait_remote_trigger(  # noqa: E731
                        runner, watch, log, ('start', 'scan_dispatch', 'box_placed'), args.wait_timeout)
                else:
                    watch.busy = True  # starts at once; phone start/scan/home are reported as ignored
                    watch.report('RUNNING', '사이클 진행 중 (--remote-trigger 없이 실행됨).')
                    trigger = lambda: None  # noqa: E731
                task = Orchestrator(APIClient(args.api), adapter, adapter, adapter).run_box(trigger)
                log('cycle_ok', cycle=cycle, scenario='orchestrator', task=task)
            else:
                runner.run(cycle)
            if watch is not None:
                watch.busy = False
                watch.report('IDLE', f'{cycle}번째 사이클 완료.')
    except KeyboardInterrupt:
        log('interrupted', cycle=cycle)
        code = 130
    except Exception as error:  # noqa: BLE001 - stop on anything, never retry motion
        log('error', cycle=cycle, type=type(error).__name__, message=str(error))
        code = 1
        if watch is not None:
            watch.report('ERROR', f'사이클 중단: {error}'[:300])
    finally:
        if watch is not None:
            watch.alive.clear()
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
