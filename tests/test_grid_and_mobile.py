from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from vision_picking.contracts import PickRequest
from vision_picking.controller import Controller, ROOT
from vision_picking.pick_plane import (
    Calibration,
    DEFAULT_GRID_COLS,
    DEFAULT_GRID_ROWS,
    PickPlane,
    compute_safe_grasp_z,
)
from vision_picking.server import create_app


@pytest.fixture
def calibration():
    cfg = json.loads((ROOT / 'config/integration.json').read_text(encoding='utf-8'))
    return Calibration(**cfg['calibration'])


@pytest.fixture
def payload():
    value = json.loads((ROOT / 'config/payload.example.json').read_text(encoding='utf-8'))
    value['captured_at'] = datetime.now(timezone.utc).isoformat()
    return value


def test_15x15_grid_cell_projection_and_inverse_roundtrip(calibration):
    plane = PickPlane(calibration)
    assert DEFAULT_GRID_ROWS == 15 and DEFAULT_GRID_COLS == 15

    # Check all 4 corners map to (0,0), (1,0), (1,1), (0,1)
    expected_uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for corner, exp in zip(calibration.corners, expected_uv):
        u, v = plane.pixel_to_uv(corner.pixel)
        assert math.isclose(u, exp[0], abs_tol=1e-6)
        assert math.isclose(v, exp[1], abs_tol=1e-6)
        px_back = plane.uv_to_pixel(u, v)
        assert math.isclose(px_back[0], corner.pixel[0], abs_tol=1e-4)
        assert math.isclose(px_back[1], corner.pixel[1], abs_tol=1e-4)

    # Center pixel (319.5, 239.5) should fall in row 7, col 7 of 15x15 grid (0-indexed)
    cell = plane.grid_cell([319.5, 239.5], rows=15, cols=15)
    assert cell['row'] == 7 and cell['col'] == 7
    assert cell['cell_id'] == 'R07_C07'
    assert math.isclose(cell['cell_center_base_mm'][0], 500.0, abs_tol=0.1)
    assert math.isclose(cell['cell_center_base_mm'][1], 0.0, abs_tol=0.1)
    assert all(abs(d) < 1e-2 for d in cell['fine_offset_mm'])

    # Test off-center pixel in cell (row=7, col=6) corresponding to Pepero taught pos (491.5, -5.0)
    cell_from_base = plane.grid_cell_from_base([491.5, -5.0, 0.0], rows=15, cols=15)
    assert cell_from_base['row'] == 7 and cell_from_base['col'] == 6
    assert cell_from_base['cell_id'] == 'R07_C06'
    # Cell center for col=6 is 400 + (6.5/15)*200 = 486.67, row=7 is -100 + (7.5/15)*200 = 0.0
    assert math.isclose(cell_from_base['cell_center_base_mm'][0], 486.67, abs_tol=0.05)
    assert math.isclose(cell_from_base['cell_center_base_mm'][1], 0.0, abs_tol=0.05)
    # Fine offset + cell_center == exact_base
    for c_val, off, ex in zip(cell_from_base['cell_center_base_mm'], cell_from_base['fine_offset_mm'], cell_from_base['exact_base_mm']):
        assert math.isclose(c_val + off, ex, abs_tol=0.05)

    gmap = plane.grid_map(rows=15, cols=15)
    assert gmap['total_cells'] == 225 and len(gmap['cells']) == 225


def test_crush_safe_grasp_z_prevents_crushing_and_air_miss():
    pepero_cfg = {'grasp_height_from_floor': 120.0}
    # Without live depth sensor: uses taught 120.0mm
    nominal = compute_safe_grasp_z(floor_z=0.0, z_min=10.0, product_real=pepero_cfg)
    assert nominal['grasp_z_mm'] == 120.0 and nominal['crush_protected'] is True

    # With live RealSense depth measurement (e.g., upright box 145mm tall -> grips at 125mm)
    measured_tall = compute_safe_grasp_z(floor_z=0.0, z_min=10.0, product_real=pepero_cfg, measured_height_mm=145.0)
    assert measured_tall['grasp_z_mm'] == 125.0

    # With flat-lying Pepero box (24mm thin) when min_safe_height_from_floor=15.0 is configured
    flat_pepero = {'grasp_height_from_floor': 20.0, 'top_bite_offset_mm': 6.0, 'min_safe_height_from_floor': 15.0}
    flat_info = compute_safe_grasp_z(floor_z=0.0, z_min=10.0, product_real=flat_pepero, measured_height_mm=22.0)
    assert 15.0 <= flat_info['grasp_z_mm'] <= 20.0


def test_2stage_coarse_to_fine_grid_pick_api(tmp_path, payload):
    controller = Controller(journal=tmp_path / 'grid_jobs.sqlite3')
    with TestClient(create_app(controller)) as client:
        plan_res = client.post('/api/v1/grid-plan?rows=15&cols=15&measured_height_mm=140.0', json=payload)
        assert plan_res.status_code == 200
        plan = plan_res.json()
        assert plan['grid_cell']['rows'] == 15 and plan['grid_cell']['cols'] == 15
        assert plan['grasp_height_info']['grasp_z_mm'] == 120.0
        step_names = [step[0] for step in plan['route']]
        assert step_names == [
            'home',
            'grid_coarse_approach',
            'fine_align_approach',
            'pick',
            'lift',
            'via',
            'place_approach',
            'place',
            'retreat',
            'home',
        ]

        pick_res = client.post('/api/v1/grid-pick?rows=15&cols=15&measured_height_mm=140.0', json=payload)
        assert pick_res.status_code == 200
        result = pick_res.json()
        assert result['state'] == 'completed'
        assert 'grid_coarse_approach' in result['completed_steps']
        assert 'fine_align_approach' in result['completed_steps']


def test_mobile_remote_controller_and_priority_scan_mode(tmp_path):
    controller = Controller(journal=tmp_path / 'mobile.sqlite3')
    with TestClient(create_app(controller)) as client:
        # 1. Remote UI and manifest load
        assert client.get('/remote').status_code == 200
        assert client.get('/remote/manifest.json').json()['short_name'] == 'E0509 리모컨'

        # 2. Default mode is external_reader (Priority 1)
        status = client.get('/api/v1/mobile/status').json()
        assert status['scan_mode'] == 'external_reader'
        assert status['robot_state'] == 'STANDBY'

        # 3. Phone NFC tagging is blocked while in external_reader mode
        blocked = client.post('/api/v1/mobile/nfc-tag', json={'uid': '0BE5715D', 'box_slot': 1})
        assert blocked.status_code == 409

        # 4. Human places box 1 -> notifies robot arm via mobile remote
        placed = client.post('/api/v1/mobile/box-placed', json={'box_slot': 1, 'uid': '0BE5715D', 'quantity': 1})
        assert placed.status_code == 200
        placed_data = placed.json()
        assert placed_data['box_slot'] == 1
        assert placed_data['product']['yolo_class_name'] == 'snack_pepero'
        task_id = placed_data['task']['task_id']

        # 5. Locate Pepero on 15x15 grid via API
        loc = client.post('/api/v1/grid/locate', json={'pixel': [292.0, 227.5], 'rows': 15, 'cols': 15, 'product': 'snack_pepero'})
        assert loc.status_code == 200
        loc_data = loc.json()
        assert loc_data['grid_cell']['cell_id'] == 'R07_C06'
        assert len(loc_data['trajectory']['coarse_grid_approach_pose']) == 6

        # 6. Complete task -> triggers haptic completion state for Galaxy app
        assert client.patch(f'/api/v1/tasks/{task_id}', json={'completed': 1, 'status': 'PICKING'}).status_code == 200
        done = client.patch(f'/api/v1/tasks/{task_id}', json={'completed': 1, 'status': 'COMPLETED'})
        assert done.status_code == 200
        status_after = client.get('/api/v1/mobile/status').json()
        assert status_after['robot_state'] == 'COMPLETED'
        assert status_after['last_completed_event']['vibrate'] == [200, 100, 250]

        # 7. Switch to auxiliary phone_nfc mode -> phone NFC tagging now succeeds
        mode_res = client.post('/api/v1/mobile/scan-mode', json={'mode': 'phone_nfc'})
        assert mode_res.status_code == 200 and mode_res.json()['scan_mode'] == 'phone_nfc'
        nfc_ok = client.post('/api/v1/mobile/nfc-tag', json={'uid': '0B71E75D', 'box_slot': 2})
        assert nfc_ok.status_code == 200
        assert nfc_ok.json()['source'] == 'phone_nfc'

        # 8. Remote pause / resume / emergency_stop controls
        assert client.post('/api/v1/mobile/control', json={'command': 'pause'}).json()['paused'] is True
        assert client.post('/api/v1/mobile/control', json={'command': 'resume'}).json()['paused'] is False
        estop = client.post('/api/v1/mobile/control', json={'command': 'emergency_stop'}).json()
        assert estop['emergency_stopped'] is True and controller.cancel.is_set()
        assert client.post('/api/v1/mobile/control', json={'command': 'reset_stop'}).json()['emergency_stopped'] is False


def test_project_cycle_with_pixel_and_depth_height(tmp_path):
    spec = importlib.util.spec_from_file_location('project_cycle_grid', ROOT / 'scripts/project_cycle.py')
    cycle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cycle)
    log = tmp_path / 'grid_cycle.jsonl'
    rc = cycle.main(['--cycles', '1', '--pixel', '292.0,227.5', '--measured-height', '135.0', '--log', str(log)])
    assert rc == 0
    records = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    grid_ev = next(r for r in records if r['event'] == 'grid_cell')
    assert grid_ev['cell_id'] == 'R07_C06'
    assert grid_ev['grasp_z'] == 115.0  # 135mm - 20mm top bite offset = 115mm
    steps = [r['name'] for r in records if r['event'] == 'step']
    assert 'grid_coarse_approach' in steps and 'approach' in steps and 'descend' in steps
