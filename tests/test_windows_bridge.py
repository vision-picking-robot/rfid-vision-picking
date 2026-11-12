import importlib.util
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bridge', ROOT / 'windows_rfid_bridge/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def test_submit_reuses_event_id_after_transport_error(monkeypatch):
    sent = []

    def fake_get(url, timeout):
        return httpx.Response(200, json={'product_name': 'p', 'yolo_class_name': 'snack_pepero',
                                         'target_box_id': 'BOX-01'}, request=httpx.Request('GET', url))

    def fake_post(url, json, timeout):
        sent.append(json['event_id'])
        if len(sent) == 1:
            raise httpx.ConnectError('down')
        return httpx.Response(200, json={'task': {'task_id': 'abcdef12', 'status': 'QUEUED'}},
                              request=httpx.Request('POST', url))

    monkeypatch.setattr(bridge.httpx, 'get', fake_get)
    monkeypatch.setattr(bridge.httpx, 'post', fake_post)
    monkeypatch.setattr(bridge.time, 'sleep', lambda s: None)
    assert bridge.submit('http://robot:8000', '0B71E55D', 1) == '0B71E55D'
    assert len(sent) == 2 and sent[0] == sent[1]


def test_keyboard_mode_sends_typed_uids_and_skips_quick_repeats(monkeypatch):
    sent = []
    monkeypatch.setattr(bridge, 'submit', lambda api, uid, qty: sent.append(uid) or {'E75D': '0B71E75D'}.get(uid, uid))
    bridge.keyboard_loop('http://robot:8000', 1, lines=['0b 71 e5 5d', '0B71E55D', 'E7', '', 'E75D', 'E75D', '0B71ED5D'])
    assert sent == ['0B71E55D', 'E75D', '0B71ED5D']
