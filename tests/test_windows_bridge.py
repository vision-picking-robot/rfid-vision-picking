import importlib.util
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bridge', ROOT / 'windows_rfid_bridge/bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class FakeScanner:
    def __init__(self, sequence):
        self.sequence = list(sequence)

    def scan(self, timeout=0):
        item = self.sequence.pop(0)
        if item is None:
            raise TimeoutError
        return item


def test_tag_resting_on_reader_is_not_resent():
    scanner = FakeScanner(['0BE5715D', '0BE5715D', None])
    bridge.wait_removed(scanner, '0BE5715D')
    assert scanner.sequence == []


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
    assert bridge.submit('http://robot:8000', '0BE5715D', 1) == '0BE5715D'
    assert len(sent) == 2 and sent[0] == sent[1]


def test_keyboard_mode_sends_typed_uids_and_skips_quick_repeats(monkeypatch):
    sent = []
    monkeypatch.setattr(bridge, 'submit', lambda api, uid, qty: sent.append(uid) or {'E75D': '0B71E75D'}.get(uid, uid))
    bridge.keyboard_loop('http://robot:8000', 1, lines=['0b e5 71 5d', '0BE5715D', 'E7', '', 'E75D', 'E75D', '0B71EC5D'])
    assert sent == ['0BE5715D', 'E75D', '0B71EC5D']
