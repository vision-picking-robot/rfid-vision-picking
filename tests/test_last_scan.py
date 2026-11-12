"""Every tag read (accepted or rejected) is shown live on the dashboard and the phone (last_scan)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from robot_rfid.api_server import install_rfid_routes
from robot_rfid.mobile_remote_ui import MOBILE_REMOTE_HTML


def client_for(tmp_path):
    app = FastAPI()
    install_rfid_routes(app, tmp_path / 'rfid.db')
    return TestClient(app)


def test_last_scan_follows_accepted_and_rejected_tags(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get('/api/v1/last-scan').json() == {'last_scan': None}
        client.post('/api/v1/scan-event', json={'uid': '0B71E55D'})
        scan = client.get('/api/v1/last-scan').json()['last_scan']
        assert scan['accepted'] and scan['uid'] == '0B71E55D' and scan['product_name'] == '쫀득초코칩'
        assert scan['target_box_id'] == 'BOX-01' and scan['task_id'] and scan['source'] == 'remote_reader'
        first = scan['seq']

        assert client.post('/api/v1/scan-event', json={'uid': '0B71EC5D'}).status_code == 409  # retired toy tag
        scan = client.get('/api/v1/last-scan').json()['last_scan']
        assert not scan['accepted'] and scan['raw_uid'] == '0B71EC5D' and scan['seq'] == first + 1

        assert client.post('/api/v1/scan-event', json={'uid': '0B71E55D'}).status_code == 409  # already queued
        scan = client.get('/api/v1/last-scan').json()['last_scan']
        assert not scan['accepted'] and '대기' in scan['error'] and scan['product_name'] == '쫀득초코칩'

        status = client.get('/api/v1/mobile/status').json()
        assert status['last_scan']['seq'] == scan['seq']
        assert status['events'][-1]['kind'] == 'tag_scanned'


def test_phone_page_renders_the_last_scan_card():
    assert 'id="tagFeed"' in MOBILE_REMOTE_HTML and 'renderLastScan(data.last_scan)' in MOBILE_REMOTE_HTML
