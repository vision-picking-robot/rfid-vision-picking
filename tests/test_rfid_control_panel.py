"""Windows RFID control panel: reader keystrokes -> robot PC, live card, other sources, completion."""
import gc
import importlib.util
import sys
import time
from pathlib import Path

import httpx
import pytest

tk = pytest.importorskip('tkinter')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'windows_rfid_bridge'))
spec = importlib.util.spec_from_file_location('control_panel', ROOT / 'windows_rfid_bridge/control_panel.py')
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)
bridge = cp.bridge

PRODUCT = {'tag_uid': '0B71E55D', 'product_name': '쫀득초코칩', 'sku_code': 'SNACK-CHOCOCHIP-01',
           'category': 'CONFECTIONERY', 'target_box_id': 'BOX-01', 'retail_price': 2500,
           'inbound_at': '2026-11-01 13:45:00', 'expired_at': '2027-12-25 19:00:00', 'yolo_class_name': 'snack_pepero'}


def test_send_reports_registered_unknown_and_duplicate(monkeypatch):
    def fake_get(url, timeout):
        req = httpx.Request('GET', url)
        if url.endswith('/0B71AAAA'):
            return httpx.Response(404, json={'detail': '등록되지 않은 태그입니다 (0B71AAAA)'}, request=req)
        return httpx.Response(200, json=PRODUCT, request=req)

    busy = {'on': False}

    def fake_post(url, json, timeout):
        req = httpx.Request('POST', url)
        if busy['on']:
            return httpx.Response(409, json={'detail': 'tag already has an active task'}, request=req)
        return httpx.Response(200, json={'uid': '0B71E55D', 'product': PRODUCT,
                                         'task': {'task_id': 'abcdef1234', 'status': 'READY'}}, request=req)

    monkeypatch.setattr(bridge.httpx, 'get', fake_get)
    monkeypatch.setattr(bridge.httpx, 'post', fake_post)
    logs = []
    ok = bridge.send('http://robot', 'E55D', 1, log=logs.append)
    assert ok['status'] == 'registered' and ok['uid'] == '0B71E55D' and ok['task']['task_id'] == 'abcdef1234'
    assert ok['product']['product_name'] == '쫀득초코칩' and any(m.startswith('O 작업 등록') for m in logs)
    assert bridge.send('http://robot', '0B71AAAA', 1, log=logs.append)['status'] == 'unknown'
    assert 'X 등록되지 않은 태그입니다 (0B71AAAA)' in logs
    busy['on'] = True
    assert bridge.send('http://robot', '0B71E55D', 1, log=logs.append)['status'] == 'duplicate'
    assert bridge.submit('http://robot', '0B71E55D', 1) is None  # console mode: nothing new queued


@pytest.fixture(scope='module')
def tk_root():
    # One Tk interpreter per process: creating Tk() again and again intermittently fails to init Tcl.
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f'no display for Tk: {error}')
    root.withdraw()
    yield root
    root.destroy()
    gc.collect()


@pytest.fixture
def panel(tk_root):
    root = tk.Toplevel(tk_root)
    root.withdraw()
    sent = []

    def sender(api, uid, quantity, log):
        sent.append(uid)
        log('O 작업 등록: task=abcdef12 상태=READY -> 로봇이 집으러 갑니다')
        if uid.startswith('0B71AA'):
            return {'status': 'unknown', 'raw_uid': uid, 'uid': None, 'product': None, 'task': None, 'message': ''}
        return {'status': 'registered', 'raw_uid': uid, 'uid': '0B71E55D', 'product': PRODUCT,
                'task': {'task_id': 'abcdef1234', 'status': 'READY'}, 'message': ''}

    p = cp.ControlPanel(root, 'http://robot:8000', sender=sender, poll=False)
    p.sent = sent
    yield p
    p.stop.set()
    root.destroy()
    # Tk images/fonts must be freed on this (the Tk) thread; a later GC in a worker thread aborts Tcl.
    p.__dict__.clear()
    del p, root
    gc.collect()


def key(panel, ch, keysym=None):
    event = type('KeyEvent', (), {'widget': panel.root, 'char': ch, 'keysym': keysym or ch})()
    return panel.on_key(event)


def settle(panel, until, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        panel.root.update()
        if until():
            return
        time.sleep(0.02)
    raise AssertionError('panel did not update')


def test_reader_keystrokes_show_the_product_card(panel):
    for ch in '0b71e55d':
        key(panel, ch)
    assert panel.buffer == '0B71E55D'
    key(panel, '\r', 'Return')
    settle(panel, lambda: panel.current and panel.current['status'] == 'registered')
    assert panel.sent == ['0B71E55D'] and panel.buffer == ''
    assert panel.name.cget('text') == '쫀득초코칩' and panel.uid.cget('text') == '0B71E55D'
    assert '작업 등록' in panel.badge.cget('text')
    assert panel.fields['box'].cget('text') == 'BOX-01' and panel.fields['price'].cget('text') == '2,500원'
    assert panel.fields['sku'].cget('text') == 'SNACK-CHOCOCHIP-01' and panel.fields['state'].cget('text') == '대기'
    assert str(panel.photo.cget('image')) == str(panel.photos['0B71E55D'])  # the item's photo is shown
    assert panel.tiles['0B71E55D']['frame'].cget('highlightthickness') == 2
    for ch in '0B71E55D\r':  # the reader repeating the same tag right away is not sent twice
        key(panel, ch, 'Return' if ch == '\r' else None)
    panel.root.update()
    assert panel.sent == ['0B71E55D']


def test_unknown_tag_is_flagged_and_entries_are_left_alone(panel):
    assert panel.submit('0B71AAAA')
    settle(panel, lambda: panel.current and panel.current['status'] == 'unknown')
    assert panel.name.cget('text') == '등록되지 않은 태그' and '미등록' in panel.badge.cget('text')
    entry_event = type('KeyEvent', (), {'widget': panel.manual, 'char': 'A', 'keysym': 'A'})()
    assert panel.on_key(entry_event) is None and panel.buffer == ''  # typing in an input box is not reader input
    assert not panel.submit('E7')  # too short


def test_scans_from_other_sources_and_completion_come_from_the_robot_pc(panel):
    status = {'robot_connected': True, 'robot_link': {'state': 'IDLE'}, 'scan_seq': 3, 'last_scan': {'seq': 3}}
    panel.apply_tags([PRODUCT])
    panel.apply_status(status)  # reads from before the program started are not replayed
    assert panel.current is None and '대기' in panel.robot_text.cget('text')
    status.update(scan_seq=4, last_scan={'seq': 4, 'source': 'phone_nfc', 'uid': '0B71E55D', 'raw_uid': '0B71E55D',
                                         'product_name': '쫀득초코칩', 'task_id': 'nfc-task-1', 'accepted': True})
    panel.apply_status(status)
    assert panel.current == {'uid': '0B71E55D', 'task_id': 'nfc-task-1', 'status': 'registered'}
    assert '갤럭시 NFC' in panel.live_meta.cget('text') and panel.fields['category'].cget('text') == '과자'
    status['last_completed_event'] = {'task_id': 'nfc-task-1'}
    panel.apply_status(status)
    assert panel.current['status'] == 'completed' and '피킹 완료' in panel.badge.cget('text')
    assert panel.fields['state'].cget('text') == '완료'
    status['emergency_stopped'] = True
    panel.apply_status(status)
    assert '비상 정지' in panel.robot_text.cget('text')


@pytest.mark.parametrize('screen', [(1280, 720), (1280, 800), (1366, 768), (1440, 900), (1536, 864), (1600, 900),
                                    (1920, 1080), (1920, 1200), (2256, 1504), (2560, 1440), (2560, 1600),
                                    (2880, 1800), (3840, 2160)])
def test_layout_fits_every_laptop_screen(tk_root, screen):
    """Maximized on each common laptop resolution, the full layout (photo, details, tiles, footer) fits."""
    w, h = screen
    win_w, win_h = w, int(h * 0.92)  # maximized: minus taskbar and title bar
    top = tk.Toplevel(tk_root)
    top.withdraw()
    p = cp.ControlPanel(top, 'http://robot:8000', sender=lambda *a, **k: None, poll=False, screen=screen)
    try:
        p.show('0B71E75D', 'registered', product={**PRODUCT, 'product_name': '복숭아녹차 340ml (페트병)'},
               task={'task_id': 'abcdef1234', 'status': 'READY'}, message='BOX-02로 담을 작업을 등록했습니다.')
        for _ in range(3):
            p.log('O 작업 등록: task=abcdef12 상태=READY -> 로봇이 집으러 갑니다')
        top.update_idletasks()
        assert top.winfo_reqwidth() <= win_w and top.winfo_reqheight() <= win_h, \
            f'{screen}: needs {top.winfo_reqwidth()}x{top.winfo_reqheight()} > {win_w}x{win_h}'
        photo_h = p.photos['0B71E75D'].height()
        assert photo_h >= 0.45 * win_h * 560 / 1000  # the photo grows with the screen, not stuck small
        assert p.f['name'].actual('size') != 0
        # resizing (restore / F11) rescales fonts and photos live
        assert p.rescale(win_w // 2 + 200, win_h // 2 + 120) or p.s == cp.layout_scale(win_w // 2 + 200, win_h // 2 + 120)
        assert p.photos['0B71E75D'].height() < photo_h or photo_h <= p.px(cp.PHOTO_H)
    finally:
        p.stop.set()
        top.destroy()
        p.__dict__.clear()
        gc.collect()


def test_grasp_alerts_show_a_strip_and_do_not_replay_old_ones(panel):
    old = {'seq': 1, 'kind': 'grasp_retry', 'message': '스팸 파지에 실패해 다시 시도합니다 (1/1)'}
    status = {'robot_connected': True, 'robot_link': {'state': 'IDLE'}, 'scan_seq': 1, 'last_scan': {'seq': 1},
              'alerts': [old]}
    panel.apply_status(status)
    panel.root.update()
    assert not panel.alert_strip.winfo_manager()  # alerts from before the program started are not shown
    failed = {'seq': 2, 'kind': 'grasp_failed', 'message': '파지 실패: 2번 시도했지만 빈 채로 닫혔습니다 (canned_meat)'}
    status.update(alerts=[old, failed], emergency_stopped=True)
    panel.apply_status(status)
    panel.root.update()
    assert panel.alert_strip.winfo_manager() == 'pack' and '파지 실패 · 로봇 정지' in panel.alert_title.cget('text')
    assert '정지 해제' in panel.alert_text.cget('text')
    assert '파지 실패' in panel.log_box.get('1.0', 'end')
    status['emergency_stopped'] = True
    panel.apply_status(status)  # still stopped: the failure strip stays
    panel.root.update()
    assert panel.alert_strip.winfo_manager() == 'pack'
    status['emergency_stopped'] = False
    panel.apply_status(status)  # released: it goes away
    panel.root.update()
    assert not panel.alert_strip.winfo_manager()
    retry = {'seq': 3, 'kind': 'grasp_retry', 'message': '스팸 파지에 실패해 다시 시도합니다 (1/1)'}
    status.update(alerts=[old, failed, retry])
    panel.apply_status(status)
    panel.root.update()
    assert panel.alert_strip.winfo_manager() == 'pack' and '다시 시도' in panel.alert_title.cget('text')
    status.update(safety_state={'state': 'warning'}, alerts=[])
    panel.apply_status(status)
    assert '작업자 접근 경고' in panel.robot_text.cget('text')


def test_offline_robot_pc_is_shown(panel):
    panel.apply_offline('connection refused')
    assert '연결 실패' in panel.server_text.cget('text') and panel.connected is False
    assert '로봇 PC 연결 실패' in panel.log_box.get('1.0', 'end')
