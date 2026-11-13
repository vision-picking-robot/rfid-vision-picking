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

LIVE = {}  # the running web app of the live_api fixture


@pytest.fixture
def live_api(tmp_path, monkeypatch, request):
    monkeypatch.delenv('PICKING_CONFIG', raising=False)
    # The cycle runs in a worker thread here; Ctrl+C handlers can only be installed on the main thread.
    monkeypatch.setattr(cycle.signal, 'signal', lambda *args: None)
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    app = create_app(tmp_path / 'rfid.db')
    app.state.box_checks = []
    if getattr(request, 'param', None) == 'box_check':  # stand-in for the web's packing-box webcam
        @app.post('/api/box-check/{step}')
        def fake_box_check(step: str, body: dict):
            app.state.box_checks.append((step, body.get('label')))
            if step == 'reference':
                return {'reference': 'now'}
            return {'ok': False, 'verdict': 'missing', 'text': '상자 안에서 물품을 찾지 못함', 'change': 0.002}
    LIVE['app'] = app
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
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


def test_phone_scan_dispatch_waits_for_the_bridge_tag_then_picks_it(live_api, tmp_path):
    log = tmp_path / 'rfid.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-rfid', '--cycles', '1', '--wait-timeout', '30',
                        '--scan-wait', '15', '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_tag' for e in events(log)))
    wait_for(lambda: httpx.get(live_api + '/api/v1/mobile/status').json()['robot_connected'])
    press(live_api, 'scan_dispatch')
    # the arm-mounted reader is on the tag; the Windows bridge sends what it read
    wait_for(lambda: any(e['event'] == 'scan_waiting' for e in events(log)))
    assert any(e.get('name') == 'label_scan' and e['vel'] == 67.5 for e in events(log))  # same speed as back up
    httpx.post(live_api + '/api/v1/scan-event', json={'uid': '0B71E65D'}).raise_for_status()
    t.join(30)
    evs = events(log)
    assert box['rc'] == 0
    assert any(e['event'] == 'remote_scan_queued' and e['uid'] == '0B71E65D' for e in evs)
    names = [e.get('name') for e in evs]
    assert names.index('label_scan_retract') < names.index('approach')  # back up before picking
    assert any(e['event'] == 'task' and e['product'] == 'canned_meat' for e in evs)
    assert any(e['event'] == 'cycle_ok' for e in evs)


def test_phone_scan_dispatch_without_a_tag_queues_nothing(live_api, tmp_path):
    log = tmp_path / 'rfid.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-rfid', '--cycles', '1', '--wait-timeout', '6',
                        '--scan-wait', '1', '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_tag' for e in events(log)))
    wait_for(lambda: httpx.get(live_api + '/api/v1/mobile/status').json()['robot_connected'])
    press(live_api, 'scan_dispatch')
    t.join(30)
    evs = events(log)
    assert any(e['event'] == 'remote_scan_timeout' for e in evs)
    assert any(e.get('name') == 'label_scan_retract' for e in evs)
    assert not any(e['event'] in ('task', 'remote_scan_queued') for e in evs)  # no invented preset tag
    assert httpx.get(live_api + '/api/v1/current-task').json()['task'] is None


def test_safety_hold_stops_the_approach_and_redoes_the_move_after_the_zone_is_clear(live_api, tmp_path, monkeypatch):
    log = tmp_path / 'safety.jsonl'
    real_movel = cycle.MockRaw.movel

    def slow_movel(self, *args):  # a move takes a while, so the hold lands mid-move
        time.sleep(0.4)
        return real_movel(self, *args)
    monkeypatch.setattr(cycle.MockRaw, 'movel', slow_movel)
    t, box = run_cycle(['--api', live_api, '--remote-trigger', '--cycles', '1', '--wait-timeout', '30',
                        '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_phone' for e in events(log)))
    press(live_api, 'start')
    wait_for(lambda: any(e['event'] == 'safety_phase' and e['active'] for e in events(log)))
    phase = httpx.get(live_api + '/api/v1/mobile/status').json()['safety_phase']
    assert phase['active'] is True
    httpx.post(live_api + '/api/v1/mobile/safety', json={'hold': True, 'message': '작업자 접근 · 로봇 정지'})
    wait_for(lambda: any(e['event'] == 'move_stop_sent' and e.get('source') == 'safety' for e in events(log)))
    wait_for(lambda: httpx.get(live_api + '/api/v1/mobile/status').json()['robot_link']['state'] == 'SAFETY_HOLD')
    time.sleep(0.6)  # let any move in flight return
    held = len(events(log))
    time.sleep(1.0)
    assert len(events(log)) == held, 'robot moved during the safety hold'
    assert t.is_alive()
    httpx.post(live_api + '/api/v1/mobile/safety', json={'hold': False, 'message': '안전구역 확보. 로봇을 다시 가동합니다.'})
    t.join(30)
    evs = events(log)
    names = [e['event'] for e in evs]
    assert box['rc'] == 0 and 'cycle_ok' in names
    assert 'safety_redo' in names and 'safety_resumed' in names
    phases = [e['active'] for e in evs if e['event'] == 'safety_phase']
    assert phases == [True, False]  # watched on the way to the object, not while carrying to the box
    assert httpx.get(live_api + '/api/v1/mobile/status').json()['safety_phase']['active'] is False


def mock_hand(monkeypatch, script):
    """The mock gripper closes on an object unless the script says this close is empty (False)."""
    real_init = cycle.MockRaw.__init__

    def init(self, poses):
        real_init(self, poses)
        self.grasp_script = list(script)
    monkeypatch.setattr(cycle.MockRaw, '__init__', init)


def alerts(url):
    return httpx.get(url + '/api/v1/mobile/status').json()['alerts']


def test_empty_close_is_retried_once_and_the_cycle_carries_on(live_api, tmp_path, monkeypatch):
    mock_hand(monkeypatch, [False, True])  # first close empty, the second one holds
    log = tmp_path / 'retry.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-rfid', '--cycles', '1', '--wait-timeout', '30', '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_tag' for e in events(log)))
    httpx.post(live_api + '/api/v1/scan-event', json={'uid': '0B71E65D'}).raise_for_status()
    t.join(30)
    evs = events(log)
    names = [e.get('name') for e in evs]
    assert box['rc'] == 0 and any(e['event'] == 'cycle_ok' and e['holding'] for e in evs)
    assert [e['holding'] for e in evs if e['event'] == 'grasp'] == [False, True]
    assert any(e['event'] == 'grasp_retry' and e['attempt'] == 1 for e in evs)
    # open, rise straight up, then approach the object again before the second close
    assert names.index('retry_rise') < len(names) - names[::-1].index('approach') - 1
    assert names.count('approach') == 2 and not any(e['event'] == 'grasp_failed' for e in evs)
    assert [a['kind'] for a in alerts(live_api)] == ['grasp_retry']  # phone / web / control program are told


def test_two_empty_closes_stop_alert_and_wait_for_the_release(live_api, tmp_path, monkeypatch):
    mock_hand(monkeypatch, [False, False])
    log = tmp_path / 'fail.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-rfid', '--cycles', '2', '--wait-timeout', '30', '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_tag' for e in events(log)))
    wait_for(lambda: httpx.get(live_api + '/api/v1/mobile/status').json()['robot_connected'])
    httpx.post(live_api + '/api/v1/scan-event', json={'uid': '0B71E65D'}).raise_for_status()
    wait_for(lambda: any(e['event'] == 'estop_hold' and e.get('grasp_failed') for e in events(log)))
    wait_for(lambda: (httpx.get(live_api + '/api/v1/mobile/status').json().get('robot_link') or {}).get('state') == 'GRASP_FAILED')
    status = httpx.get(live_api + '/api/v1/mobile/status').json()
    assert status['emergency_stopped'] and status['robot_link']['state'] == 'GRASP_FAILED'
    assert '파지 실패' in status['robot_link']['message'] and '정지 해제' in status['robot_link']['message']
    assert [a['kind'] for a in alerts(live_api)] == ['grasp_retry', 'grasp_failed']
    assert alerts(live_api)[-1]['level'] == 'danger'
    time.sleep(1.2)  # it holds: no further motion until the operator releases the stop
    held = len(events(log))
    time.sleep(1.0)
    assert len(events(log)) == held and t.is_alive()
    assert httpx.get(live_api + '/api/v1/current-task').json()['task'] is None  # the task was marked DEFECTIVE
    press(live_api, 'reset_stop')
    wait_for(lambda: any(e['event'] == 'estop_released' for e in events(log)))
    wait_for(lambda: sum(e['event'] == 'waiting_for_tag' for e in events(log)) >= 2)
    after = [e.get('name') for e in events(log)[[e['event'] for e in events(log)].index('estop_released'):]]
    assert 'gripper_open' in after  # the fingers are opened before it rises and goes home
    httpx.post(live_api + '/api/v1/scan-event', json={'uid': '0B71E65D'}).raise_for_status()
    t.join(30)
    evs = events(log)
    assert box['rc'] == 0 and any(e['event'] == 'cycle_ok' for e in evs)  # the next box works (mock hand holds again)


def test_phone_page_shows_safety_and_grasp_alerts_with_vibration():
    from robot_rfid.mobile_remote_ui import MOBILE_REMOTE_HTML as html  # noqa: N811
    assert 'id="alertBanner"' in html and 'renderAlerts(data)' in html
    assert 'safety_state' in html and 'data.alerts' in html
    for kind in ('warning', 'hold', 'resume', 'grasp_retry', 'grasp_failed'):
        assert f'{kind}:' in html.split('const BUZZ')[1].split('};')[0]
    assert 'function buzz(' in html and 'bridge.vibrate(ms)' in html


def test_alert_endpoint_keeps_ten_and_rejects_unknown_kinds(client):
    assert client.post('/api/v1/mobile/alert', json={'kind': 'bogus', 'message': 'x'}).status_code == 422
    for i in range(12):
        assert client.post('/api/v1/mobile/alert', json={'kind': 'grasp_retry', 'message': f'try {i}'}).status_code == 200
    kept = client.get('/api/v1/mobile/status').json()['alerts']
    assert [a['seq'] for a in kept] == list(range(3, 13)) and kept[-1]['message'] == 'try 11'
    failed = client.post('/api/v1/mobile/alert', json={'kind': 'grasp_failed', 'message': '파지 실패'}).json()
    assert failed['alert']['level'] == 'danger'


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


def test_remote_rfid_cycle_holds_on_estop_and_carries_on_after_reset(live_api, tmp_path):
    log = tmp_path / 'hold.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-rfid', '--cycles', '2', '--wait-timeout', '30',
                        '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_tag' for e in events(log)))
    wait_for(lambda: httpx.get(live_api + '/api/v1/mobile/status').json()['robot_connected'])
    press(live_api, 'emergency_stop')
    wait_for(lambda: any(e['event'] == 'estop_hold' for e in events(log)))
    time.sleep(0.5)
    assert t.is_alive(), 'cycle must wait for the release, not exit'
    assert httpx.get(live_api + '/api/v1/mobile/status').json()['robot_link']['state'] == 'ESTOPPED'
    press(live_api, 'reset_stop')
    wait_for(lambda: any(e['event'] == 'estop_released' for e in events(log)))
    wait_for(lambda: sum(e['event'] == 'waiting_for_tag' for e in events(log)) >= 2)
    httpx.post(live_api + '/api/v1/scan-event', json={'uid': '0B71E65D'}).raise_for_status()
    t.join(30)
    evs = events(log)
    assert box['rc'] == 0 and any(e['event'] == 'cycle_ok' for e in evs)
    names = [e.get('name') for e in evs]
    assert names.index('home_return') < names.index('approach')


@pytest.mark.parametrize('live_api', ['box_check'], indirect=True)
def test_box_check_failure_is_recorded_and_the_cycle_carries_on(live_api, tmp_path):
    log = tmp_path / 'box.jsonl'
    t, box = run_cycle(['--api', live_api, '--remote-rfid', '--cycles', '1', '--wait-timeout', '30',
                        '--box-check', '--log', str(log)])
    wait_for(lambda: any(e['event'] == 'waiting_for_tag' for e in events(log)))
    httpx.post(live_api + '/api/v1/scan-event', json={'uid': '0B71E65D'}).raise_for_status()
    t.join(30)
    evs = events(log)
    assert box['rc'] == 0, 'a failed box check is recorded, not a stop'
    checks = LIVE['app'].state.box_checks
    assert [step for step, _ in checks] == ['reference', 'verify']
    names = [e.get('name') for e in evs]
    place = max(i for i, n in enumerate(names) if n == 'box_retreat')
    home_after = names.index('home_return', place)
    verify_at = next(i for i, e in enumerate(evs) if e['event'] == 'box_check')
    assert home_after < verify_at, 'the arm leaves the box camera view before the check'
    ok = next(e for e in evs if e['event'] == 'cycle_ok')
    assert ok['box_check'] == ['1번째 상자 안에서 물품을 찾지 못함']
    with LIVE['app'].state.database.connect() as db:
        task = db.execute('SELECT status, error FROM tasks ORDER BY rowid DESC LIMIT 1').fetchone()
    assert task['status'] == 'DEFECTIVE' and '상자 투입 확인 실패' in task['error']
