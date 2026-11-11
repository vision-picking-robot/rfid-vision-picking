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
    cyc.depth_cfg = {'zones': ZONES, 'gripper_max_open_mm': 100.0, 'gripper_close_yaw_at_rz0_deg': close0}
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
