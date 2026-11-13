import importlib.util
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('project_cycle_safety', ROOT / 'scripts/project_cycle.py')
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


def test_mock_calibration_never_steers_real_mode():
    cfg = json.loads((ROOT / 'config/integration.json').read_text(encoding='utf-8'))
    assert cycle.verified_real_calibration(cfg) is False
    verified = dict(cfg, calibration_verified=True, mock_mode=False,
                    calibration=dict(cfg['calibration'], revision='site-v1',
                                     camera=dict(cfg['calibration']['camera'], camera_id='realsense')))
    assert cycle.verified_real_calibration(verified) is True


def test_estop_watch_sends_stop_and_blocks_next_step(monkeypatch):
    stops, logs = [], []
    watch = cycle.MobileEStopWatch('http://robot:8000', lambda: stops.append(1),
                                   lambda e, **k: logs.append(e), period=0.01)
    states = iter([False, True])
    # run() keeps polling after an E-stop (the cycle waits for reset_stop), so drive it from a thread.
    monkeypatch.setattr(watch, 'poll', lambda: next(states, True))
    thread = threading.Thread(target=watch.run, daemon=True)
    thread.start()
    assert watch.tripped.wait(5), 'E-stop was not picked up'
    watch.alive.clear()
    thread.join(5)
    assert not thread.is_alive()
    assert stops == [1] and 'mobile_emergency_stop' in logs
    with pytest.raises(RuntimeError, match='emergency stop'):
        watch.check()


def test_mobile_ui_commands_match_api():
    from robot_rfid.mobile_remote_ui import MOBILE_REMOTE_HTML as html  # noqa: N811
    assert "sendControl('dispatch_scan')" not in html and 'dispatch_scan: true' not in html
    assert '펜던트 E-Stop을 대신하지 않습니다' in html
