"""project_cycle depth picking: zone choice, gripper-width guard and grasp yaw."""
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import project_cycle  # noqa: E402

ZONES = {'1': 'wet_wipes', '2': 'canned_meat', '3': 'snack_pepero', '4': 'beverage_pet'}


def make_cycle(objects, close0=None, revision='rev1'):
    cyc = object.__new__(project_cycle.Cycle)
    cyc.args = SimpleNamespace(depth_api='http://web:8000', product='snack_pepero')
    cyc.depth_cfg = {'zones': ZONES, 'gripper_max_open_mm': 100.0, 'gripper_close_yaw_at_rz0_deg': close0, 'samples': 1}
    cyc.cal_revision = revision
    cyc.poses = {'floor': {'floor_z': 0.0}}
    cyc.z_min = 10.0
    item = {'x': 0, 'y': 0, 'rz': 0.0, 'grasp_height_from_floor': 120.0}
    cyc.products = {name: {'real': dict(item)} for name in ZONES.values()}
    cyc.logged = []
    cyc.log = lambda event, **kw: cyc.logged.append((event, kw))
    cyc._objects = {'objects': objects, 'revision': 'rev1'}
    return cyc


def obj(corner, base, height=60.0, footprint=(60.0, 100.0), yaw=0.0, inside=True):
    return dict(corner=corner, base=list(base), height_mm=height, footprint_mm=list(footprint),
                short_axis_yaw_deg=yaw, inside=inside)


@pytest.fixture
def web(monkeypatch):
    holder = {}

    def fake_get(url, timeout):
        assert url == 'http://web:8000/api/robot/pick/depth-objects'
        return httpx.Response(200, json=holder['data'], request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'get', fake_get)
    return holder


def run(web, cyc, product):
    web['data'] = cyc._objects
    return cyc.detect_by_depth(product)


def test_picks_object_in_the_products_zone_with_measured_height(web):
    cyc = make_cycle([obj(1, (500, -50), 58, (60, 90)), obj(2, (674, -37), 53, (68, 108))])
    target = run(web, cyc, 'canned_meat')
    x, y, z, rx, ry, rz = target['pose']
    assert (x, y) == (674, -37) and (rx, ry, rz) == (0.0, 180.0, 0.0)
    assert z == pytest.approx(33.0)  # 53 mm tall, grasp 20 mm below the top


def test_too_wide_object_is_rejected_before_any_motion(web):
    cyc = make_cycle([obj(1, (508, -50), 59, (117.5, 214))])
    with pytest.raises(RuntimeError, match='mm wide'):
        run(web, cyc, 'wet_wipes')


@pytest.mark.parametrize('objects, message', [
    ([], 'no object in zone 2'),
    ([obj(2, (674, -37), inside=False)], 'no object in zone 2'),
    ([obj(2, (674, -37), height=900)], 'implausible object height'),
])
def test_missing_or_implausible_objects_fail(web, objects, message):
    with pytest.raises(RuntimeError, match=message):
        run(web, make_cycle(objects), 'canned_meat')


def test_calibration_revision_mismatch_fails(web):
    with pytest.raises(RuntimeError, match='revision differs'):
        run(web, make_cycle([obj(2, (674, -37))], revision='other'), 'canned_meat')


@pytest.mark.parametrize('close0, short_yaw, rz', [(0, 0, 0), (0, 90, -90), (0, 30, -30), (90, 0, 90 - 180), (90, 170, -80)])
def test_grasp_yaw_aligns_fingers_with_short_side(web, close0, short_yaw, rz):
    cyc = make_cycle([obj(2, (674, -37), yaw=short_yaw)], close0=close0)
    got = run(web, cyc, 'canned_meat')['pose'][5]
    assert got == pytest.approx(rz) and -90 <= got < 90
    assert (close0 - got - short_yaw) % 180 == pytest.approx(0, abs=1e-9)  # closing yaw == short side


@pytest.mark.parametrize('height, grasp', [(53, 33.0), (173, 153.0), (27, 15.0), (51, 31.0)])
def test_grasp_height_follows_the_measured_object(web, height, grasp):
    cyc = make_cycle([obj(3, (654, 153), height=height)])
    assert run(web, cyc, 'snack_pepero')['pose'][2] == pytest.approx(grasp)


def test_unsteady_scene_is_rejected(web, monkeypatch):
    frames = iter([[obj(2, (674, -37), 53)], [obj(2, (703, -127), 180)], [obj(2, (674, -37), 53)]])

    def fake_get(url, timeout):
        return httpx.Response(200, json={'objects': next(frames), 'revision': 'rev1'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(httpx, 'get', fake_get)
    monkeypatch.setattr(project_cycle.time, 'sleep', lambda s: None)
    cyc = make_cycle([])
    cyc.depth_cfg['samples'] = 3
    with pytest.raises(RuntimeError, match='not steady'):
        cyc.detect_by_depth('canned_meat')


def test_grip_waits_for_creeping_fingers_to_stop(monkeypatch):
    feedback = iter([dict(code=1, result='ok', position_pulses=292, current=150, moving=1),
                     dict(code=1, result='ok', position_pulses=380, current=150, moving=1),
                     dict(code=1, result='ok', position_pulses=397, current=150, moving=0)])
    cyc = object.__new__(project_cycle.Cycle)
    cyc.raw = SimpleNamespace(grip=lambda target, current=None: next(feedback))
    cyc.estop, cyc.logged = None, []
    cyc.log = lambda event, **kw: cyc.logged.append((event, kw))
    monkeypatch.setattr(project_cycle.time, 'sleep', lambda s: None)
    fb = cyc.grip('grip', 740, lambda p: p >= 0, current=150, settle_s=4.0)
    assert fb['position_pulses'] == 397 and not fb['moving']


def test_grip_still_fails_if_the_gripper_never_settles(monkeypatch):
    cyc = object.__new__(project_cycle.Cycle)
    cyc.raw = SimpleNamespace(grip=lambda target, current=None: dict(code=1, result='ok', position_pulses=300, current=150, moving=1))
    cyc.estop = None
    cyc.log = lambda event, **kw: None
    monkeypatch.setattr(project_cycle.time, 'sleep', lambda s: None)
    with pytest.raises(RuntimeError, match='not confirmed'):
        cyc.grip('grip', 740, lambda p: p >= 0, current=150, settle_s=0.0)


@pytest.mark.parametrize('name_tol, off, ok', [(10.0, 3.1, True), (10.0, 12.0, False), (2.0, 3.1, False)])
def test_waypoint_tolerance_only_relaxes_in_air_moves(monkeypatch, name_tol, off, ok):
    cyc = object.__new__(project_cycle.Cycle)
    cyc.estop, cyc.offset, cyc.logged = None, 120.0, []
    cyc.args = SimpleNamespace(lvel=30.0)
    cyc.mover = SimpleNamespace(movel=lambda *a: 0)
    cyc.raw = None
    cyc.log = lambda event, **kw: cyc.logged.append(event)
    monkeypatch.setattr(project_cycle, 'FlangeOffset',
                        lambda raw, offset: SimpleNamespace(get_current_posx=lambda ref: [680.5 - off, -124.2, 182.1, 0, 180, 0]))
    call = lambda: cyc.l('approach', [680.5, -124.2, 182.1, 0, 180, 0], tol=name_tol)
    if ok:
        call()
        assert 'arrival_offset' in cyc.logged
    else:
        with pytest.raises(RuntimeError, match='arrival error'):
            call()


def reach_cycle(limit_z):
    """Cycle whose fake IK reaches fingertip z <= limit_z comfortably (elbow 30) and is clamped above."""
    cyc = object.__new__(project_cycle.Cycle)
    cyc.offset, cyc.logged = 120.0, []
    cyc.log = lambda event, **kw: cyc.logged.append((event, kw))
    cyc.raw = SimpleNamespace(elbow_deg=lambda flange: 30.0 if flange[2] - 120.0 <= limit_z + 1e-6 else 0.0)
    return cyc


def test_reach_z_lowers_waypoints_until_the_elbow_is_comfortable():
    cyc = reach_cycle(limit_z=132.1)
    assert cyc.reach_z('approach', [680.5, -124.2, 32.1, 0, 180, 3.3], 182.1, 73.0) == pytest.approx(132.1)
    assert cyc.logged[0][0] == 'reach_limited'


def test_reach_z_rejects_when_the_object_top_cannot_be_cleared():
    cyc = reach_cycle(limit_z=150.0)
    with pytest.raises(RuntimeError, match='too far'):
        cyc.reach_z('approach', [659.6, 157.9, 153.3, 0, 180, -83.5], 303.3, 193.3)


def test_reach_z_keeps_requested_height_when_reachable():
    cyc = reach_cycle(limit_z=500.0)
    assert cyc.reach_z('lift', [496, 189, 150, 0, 180, 0], 400.0, 300.0) == 400.0 and cyc.logged == []


@pytest.mark.parametrize('hang, place_z', [(152.2, 85 + 100 + 32.2), (120.0, 185.0), (32.0, 185.0)])
def test_place_height_rises_for_objects_hanging_below_the_reference(hang, place_z):
    cyc = object.__new__(project_cycle.Cycle)
    moves = []
    cyc.poses = {'box_slots': {1: {'posx': [-373.0, 0.0, 85.0, 3.26, 180.0, -176.74], 'taught': True}},
                 'poses': {'home': {'posx': [373.0, 0.0, 285.0, 0, 180, 0]}}, 'motion': {'approach_offset_z': 150.0}}
    cyc.carry = {'via_point': [90, 0, 0, 0, 0, 0], 'box_high': [180, 0, 0, 0, 0, 0]}
    cyc.taught_carry = False  # legacy: release --place-extra above the slot
    cyc.args = SimpleNamespace(place_extra=100.0, lift_extra=100.0, dvel=15.0)
    cyc.log = lambda event, **kw: None
    cyc.j = lambda name, posj: None
    cyc.l = lambda name, pose, vel=None, tol=None: moves.append((name, pose[2]))
    cyc.grip = lambda *a, **k: {}
    cyc._hang = hang
    cyc.place('BOX-01')
    assert dict(moves)['box_place'] == pytest.approx(place_z)


@pytest.mark.parametrize('hang, place_z', [(32.0, 234.9), (152.2, 234.9), (200.0, 265.0)])
def test_taught_release_point_is_used_as_is_unless_the_object_hangs_too_low(hang, place_z):
    cyc = object.__new__(project_cycle.Cycle)
    moves, joints = [], []
    box_high = [-372.4, 287.3, 423.9, -9.36, 180.0, 162.96]
    cyc.poses = {'box_slots': {1: {'posx': [-368.5, 5.0, 234.9, 42.75, 180.0, -144.55], 'taught': True}},
                 'poses': {'home': {'posx': [373.0, 0.0, 285.0, 0, 180, 0]}, 'box_high': {'posx': box_high}},
                 'motion': {'approach_offset_z': 150.0}}
    cyc.carry = {'via_point': [112, 0, 0, 0, 0, 0], 'box_high': [142, 0, 0, 0, 0, 0]}
    cyc.taught_carry = True
    cyc.args = SimpleNamespace(place_extra=100.0, lift_extra=100.0, dvel=15.0)
    cyc.log = lambda event, **kw: None
    cyc.j = lambda name, posj: joints.append(name)
    cyc.l = lambda name, pose, vel=None, tol=None: moves.append((name, list(pose)))
    cyc.grip = lambda *a, **k: {}
    cyc._hang = hang
    cyc.place('BOX-01')
    assert joints == ['via_carry', 'box_carry', 'via_return']
    assert [m[0] for m in moves] == ['box_place', 'box_retreat']
    assert moves[0][1][2] == pytest.approx(place_z)  # object bottom never below PLACE_MIN_BOTTOM_MM
    assert moves[1][1] == box_high  # back up the way it came, then via_point


def test_low_lift_on_the_far_side_is_pulled_in_and_raised_to_the_via_height():
    cyc = object.__new__(project_cycle.Cycle)
    moves, logged = [], []
    cyc.poses = {'poses': {'via_point': {'posx': [-136.8, 334.4, 250.1, 155.37, 180.0, 1.78]}}}
    cyc.offset = 120.0
    # elbow comfortable only once the radius is <= 640 mm
    cyc.raw = SimpleNamespace(elbow_deg=lambda p: 30.0 if (p[0] ** 2 + p[1] ** 2) ** 0.5 <= 640 else 10.0)
    cyc.log = lambda event, **kw: logged.append(event)
    cyc.l = lambda name, pose, vel=None, tol=None: moves.append((name, list(pose)))
    cyc._above = [687.8, -76.1, 152.2, 0.0, 180.0, 0.0]
    cyc._pull_in()
    name, pose = moves[0]
    assert name == 'pull_in' and pose[2] == 250.1 and (pose[0] ** 2 + pose[1] ** 2) ** 0.5 <= 640
    moves.clear()
    cyc._above = [481.0, 202.5, 402.4, 0.0, 180.0, 0.0]  # already above the via height: no extra move
    cyc._pull_in()
    assert moves == []


def test_depth_grasp_never_lets_the_palm_reach_the_object_top(monkeypatch):
    cyc = object.__new__(project_cycle.Cycle)
    logged = []
    cyc.depth_cfg = {'zones': {'4': 'beverage_pet'}, 'samples': 1, 'finger_depth_mm': 50.0, 'palm_clearance_mm': 15.0}
    cyc.args = SimpleNamespace(depth_api='http://web', product='snack_pepero')
    cyc.cal_revision = 'r1'
    cyc.poses = {'floor': {'floor_z': 0.0}}
    cyc.z_min = 10.0
    cyc.log = lambda event, **kw: logged.append((event, kw))
    obj = {'corner': 4, 'inside': True, 'base': [481.0, 202.0], 'height_mm': 173.5, 'footprint_mm': [24.0, 33.0],
           'short_axis_yaw_deg': 90.0}

    class Resp:
        def raise_for_status(self):
            return self

        def json(self):
            return {'revision': 'r1', 'objects': [obj]}
    monkeypatch.setattr('httpx.get', lambda url, timeout: Resp())
    cyc.products = {'beverage_pet': {'real': {'top_bite_offset_mm': 35.0}}}
    assert cyc.detect_by_depth('beverage_pet')['pose'][2] == pytest.approx(173.5 - 35.0)
    cyc.products = {'beverage_pet': {'real': {'top_bite_offset_mm': 60.0}}}  # deeper than 50 - 15: clamped
    assert cyc.detect_by_depth('beverage_pet')['pose'][2] == pytest.approx(173.5 - 35.0)
    assert any(e == 'grasp_bite_limited' for e, _ in logged)


def test_depth_base_correction_maps_camera_xy_to_the_taught_fingertip():
    import json
    cyc = object.__new__(project_cycle.Cycle)
    cfg = json.loads((Path(__file__).resolve().parents[1] / 'config/integration.real.json').read_text(encoding='utf-8'))
    cyc.depth_cfg = cfg['depth_picking']
    # measured 2026-11-12: camera (575.9, 65.3) -> fingertip (569.2, 70.8), camera (656.2, -84.8) -> (656.1, -77.0)
    for cam, real in (([575.9, 65.3], [569.2, 70.8]), ([656.2, -84.8], [656.1, -77.0])):
        x, y = cyc.correct_base(cam)
        assert abs(x - real[0]) < 6 and abs(y - real[1]) < 6
    with pytest.raises(RuntimeError, match='more than'):
        cyc.correct_base([1500.0, 0.0])  # far outside the measured area: refuse instead of extrapolating
    cyc.depth_cfg = {}
    assert cyc.correct_base([1.0, 2.0]) == [1.0, 2.0]


def test_low_far_approach_first_arrives_at_the_via_height_on_the_same_radial_line():
    cyc = object.__new__(project_cycle.Cycle)
    moves = []
    cyc.poses = {'poses': {'via_point': {'posx': [-136.8, 334.4, 250.1, 155.37, 180.0, 1.78]}},
                 'motion': {'approach_offset_z': 150.0}, 'floor': {'floor_z': 0.0}}
    cyc.offset, cyc.taught_carry = 120.0, True
    cyc.args = SimpleNamespace(lift_extra=100.0, dvel=15.0)
    # comfortable only within 620 mm and below 140 mm at the far target: the approach ends low
    cyc.raw = SimpleNamespace(elbow_deg=lambda p: 30.0 if (p[0] ** 2 + p[1] ** 2) ** 0.5 <= 620 or p[2] - 120 <= 140 else 10.0)
    cyc.log = lambda event, **kw: None
    cyc.l = lambda name, pose, vel=None, tol=None: moves.append((name, list(pose)))
    cyc.grip = lambda *a, **k: {}
    cyc.approach({'pose': [674.2, 182.4, 95.0, 0.0, 180.0, 0.0], 'product': 'snack_pepero',
                  'grasp_info': {'measured_height_mm': 115.0}})
    names = [m[0] for m in moves]
    assert names == ['pre_approach', 'approach', 'descend']
    pre, approach = moves[0][1], moves[1][1]
    assert pre[2] == 250.1 and approach[2] < 250.1
    assert abs(pre[0] * approach[1] - pre[1] * approach[0]) < 1e-6  # same line from the robot base
