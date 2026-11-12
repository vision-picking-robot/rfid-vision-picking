"""Galaxy remote buttons must reach the robot cycle, and the work-area map must match the taught corners."""
import importlib.util
import json
import math
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from robot_rfid.api_server import create_app

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('project_cycle_remote', ROOT / 'scripts/project_cycle.py')
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('PICKING_CONFIG', raising=False)
    with TestClient(create_app(tmp_path / 'rfid.db')) as c:
        yield c


def test_control_reports_when_no_robot_cycle_listens(client):
    res = client.post('/api/v1/mobile/control', json={'command': 'home'}).json()
    assert res['robot_connected'] is False and '연결되지 않아' in res['message']
    client.get('/api/v1/mobile/status', params={'robot': 'remote_rfid'})  # robot heartbeat
    res = client.post('/api/v1/mobile/control', json={'command': 'scan_dispatch'}).json()
    assert res['robot_connected'] is True and '전달' in res['message']
    status = client.get('/api/v1/mobile/status').json()
    assert [c['command'] for c in status['commands']] == ['home', 'scan_dispatch']
    assert status['command_seq'] == 2 and status['robot_link']['mode'] == 'remote_rfid'


def test_only_reset_stop_releases_emergency_stop(client):
    client.post('/api/v1/mobile/control', json={'command': 'emergency_stop'})
    for cmd in ('start', 'resume', 'home', 'scan_dispatch'):
        res = client.post('/api/v1/mobile/control', json={'command': cmd})
        assert res.status_code == 409 and res.json()['detail']
    assert client.get('/api/v1/mobile/status').json()['emergency_stopped'] is True
    assert client.post('/api/v1/mobile/control', json={'command': 'reset_stop'}).json()['emergency_stopped'] is False
    assert client.post('/api/v1/mobile/control', json={'command': 'start'}).status_code == 200


def test_robot_state_report_and_ack(client):
    res = client.post('/api/v1/mobile/robot-state', json={
        'mode': 'remote_trigger', 'state': 'RETURNING_HOME', 'message': 'home', 'ack_seq': 3, 'ack_result': 'done'})
    assert res.status_code == 200
    status = client.get('/api/v1/mobile/status').json()
    assert status['robot_connected'] is True and status['robot_state'] == 'RETURNING_HOME'
    assert status['robot_link']['ack_seq'] == 3


def test_work_area_is_the_taught_rectangle_not_a_square(client):
    real = json.loads((ROOT / 'config/integration.real.json').read_text(encoding='utf-8'))
    area = client.get('/api/v1/mobile/work-area').json()
    taught = [c['pose'][:2] for c in real['calibration']['corners']]
    assert area['corners_base_mm'] == [[round(v, 1) for v in p] for p in taught]
    w, h = area['size_mm']['col_axis_1_2'], area['size_mm']['row_axis_1_4']
    assert w == pytest.approx(math.dist(taught[0], taught[1]), abs=0.1)
    assert h == pytest.approx(math.dist(taught[0], taught[3]), abs=0.1)
    assert h / w > 1.4  # rectangle, so each of the 15x15 cells is a rectangle as well
    lattice = area['lattice_base_mm']
    assert len(lattice) == 16 and all(len(r) == 16 for r in lattice)
    for corner, (r, c) in zip(area['corners_base_mm'], [(0, 0), (0, 15), (15, 15), (15, 0)]):
        assert lattice[r][c] == pytest.approx(corner, abs=0.2)
    assert area['zones'] == {'1': 'wet_wipes', '2': 'canned_meat', '3': 'snack_pepero', '4': 'beverage_pet'}
    assert set(area['product_names']) == {'1', '2', '3', '4'}
    # A cell picked on the phone maps back to the same cell on the server.
    cell_center = [sum(p[i] for p in (lattice[3][4], lattice[3][5], lattice[4][5], lattice[4][4])) / 4 for i in (0, 1)]
    loc = client.post('/api/v1/grid/locate', json={'base_xy': cell_center}).json()
    assert (loc['grid_cell']['row'], loc['grid_cell']['col']) == (3, 4)


def test_work_items_keep_latest_per_zone(client):
    item = lambda z, x: {'zone': z, 'product': 'p', 'base': [x, 0.0], 'footprint_mm': [40.0, 90.0],  # noqa: E731
                         'short_axis_yaw_deg': 30.0, 'height_mm': 60.0}
    client.post('/api/v1/mobile/work-items', json={'items': [item(1, 450.0)]})
    client.post('/api/v1/mobile/work-items', json={'items': [item(3, 700.0)]})
    client.post('/api/v1/mobile/work-items', json={'items': [item(1, 455.0)]})
    items = client.get('/api/v1/mobile/work-area').json()['reported_items']['items']
    assert [(i['zone'], i['base'][0]) for i in items] == [(1, 455.0), (3, 700.0)]


def test_remote_ui_uses_native_bridge_and_draws_area():
    from robot_rfid.mobile_remote_ui import MOBILE_REMOTE_HTML as html  # noqa: N811
    assert 'window.GalaxyNativeBridge' in html and 'window.GalaxyBridge' not in html
    assert 'window.onNativeNfcTag' in html and 'setNfcEnabled' in html
    assert '/api/v1/mobile/work-area' in html and 'footprintCorners' in html
    assert "sendControl('reset_stop')" in html
    assert 'exact_base_xy' not in html and 'safe_grasp_z_mm' not in html  # fields the API never returned


# ---- End to end: real HTTP server + mock robot cycle driven by phone buttons ----

@pytest.fixture
def live_api(tmp_path, monkeypatch):
    monkeypatch.delenv('PICKING_CONFIG', raising=False)
    # The cycle runs in a worker thread here; Ctrl+C handlers can only be installed on the main thread.
    monkeypatch.setattr(cycle.signal, 'signal', lambda *args: None)
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(tmp_path / 'rfid.db'), host='127.0.0.1', port=port,
                                           log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{port}'
    for _ in range(100):
        try:
            httpx.get(url + '/api/v1/mobile/status', timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield url
    server.should_exit = True
    thread.join(5)


def press(url, command):
    res = httpx.post(url + '/api/v1/mobile/control', json={'command': command}, timeout=5)
    assert res.status_code == 200, res.text
    return res.json()


def wait_for(predicate, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError('timed out')


def events(log):
    return [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []


def run_cycle(argv):
    box = {}
    t = threading.Thread(target=lambda: box.setdefault('rc', cycle.main(argv)), daemon=True)
    t.start()
    return t, box


def test_phone_home_pause_start_resume_drive_the_cycle(live_api, tmp_path, monkeypatch):
    log = tmp_path / 'cycle.jsonl'
    real_movej = cycle.MockRaw.movej

    def slow_movej(self, *args):  # give the operator time to press pause mid-cycle
        time.sleep(0.3)
        return real_movej(self, *args)
    monkeypatch.setattr(cycle.MockRaw, 'movej', slow_movej)
    press(live_api, 'home')  # pressed before the cycle runs: must be ignored as stale
    t, box = run_cycle(['--api', live_api, '--remote-trigger', '--cycles', '1', '--wait-timeout', '30',
                        '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_phone' for e in events(log)))
    assert httpx.get(live_api + '/api/v1/mobile/status').json()['robot_connected'] is True
    assert not any(e.get('name') == 'home_return' for e in events(log))

    ack = press(live_api, 'home')['seq']
    wait_for(lambda: httpx.get(live_api + '/api/v1/mobile/status').json()['robot_link'].get('ack_seq') == ack)
    wait_for(lambda: any(e.get('name') == 'home_return' for e in events(log)))

    press(live_api, 'start')
    wait_for(lambda: any(e.get('name') == 'home' for e in events(log)))  # cycle is moving
    press(live_api, 'pause')
    wait_for(lambda: any(e['event'] == 'remote_paused' for e in events(log)))
    held = len(events(log))
    time.sleep(1.0)
    assert len(events(log)) == held, 'cycle moved while paused'
    assert not any(e.get('name') == 'approach' for e in events(log))
    assert t.is_alive()

    press(live_api, 'resume')
    t.join(30)
    names = [e['event'] for e in events(log)]
    assert box['rc'] == 0 and 'remote_resumed' in names and 'cycle_ok' in names
    status = httpx.get(live_api + '/api/v1/mobile/status').json()
    assert status['last_completed_event'] is not None


def test_phone_scan_dispatch_in_remote_rfid_mode(live_api, tmp_path):
    log = tmp_path / 'rfid.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-rfid', '--cycles', '1', '--wait-timeout', '30',
                        '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_tag' for e in events(log)))
    wait_for(lambda: httpx.get(live_api + '/api/v1/mobile/status').json()['robot_connected'])
    press(live_api, 'scan_dispatch')
    t.join(30)
    evs = events(log)
    assert box['rc'] == 0
    assert any(e['event'] == 'remote_scan_queued' and e['uid'] == '0B71E55D' for e in evs)
    assert any(e.get('name') == 'label_scan' for e in evs) and any(e['event'] == 'cycle_ok' for e in evs)


def test_phone_estop_while_paused_stops_the_cycle(live_api, tmp_path):
    log = tmp_path / 'estop.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-trigger', '--cycles', '1', '--wait-timeout', '30',
                        '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_phone' for e in events(log)))
    press(live_api, 'pause')  # pause while idle holds the wait loop too
    wait_for(lambda: any(e['event'] == 'remote_paused' for e in events(log)))
    press(live_api, 'emergency_stop')
    t.join(30)
    names = [e['event'] for e in events(log)]
    assert box['rc'] == 1 and 'move_stop_sent' in names and 'cycle_ok' not in names
