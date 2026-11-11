"""Windows RFID bridge: ACR1555U (Bluetooth PC/SC) -> robot PC web API.

Each tag tap is read once, matched against the robot PC's product DB (GET /api/v1/tags/{uid})
and queued as a pick task (POST /api/v1/scan-event). The robot PC runs
`scripts/project_cycle.py ... --remote-rfid`, which waits for these tasks.

A tag is sent again only after it has been removed from the reader (no double queuing while
the tag rests on the reader). Ctrl+C stops the bridge.

    python windows_rfid_bridge/bridge.py --api http://192.168.0.10:8000
    python windows_rfid_bridge/bridge.py --api http://192.168.0.10:8000 --check
"""
import argparse
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from robot_rfid.rfid_scanner import RFIDScanner  # noqa: E402


def say(msg):
    print(time.strftime('[%H:%M:%S] ') + msg, flush=True)


def list_readers():
    from smartcard.System import readers
    return [str(r) for r in readers()]


def check(api, reader, need_reader=True):
    ok = True
    try:
        if not need_reader:
            raise LookupError  # keyboard mode: only the robot PC connection matters
        names = list_readers()
        say(f'PC/SC 리더 목록: {names or "없음"}')
        if reader:
            match = [n for n in names if reader.lower() in n.lower()]
        else:  # same default filter as RFIDScanner
            match = [n for n in names if ('acr1555' in n.lower() or 'acr1552' in n.lower()) and 'sam' not in n.lower()]
        if not match:
            say('X 리더기를 찾지 못했습니다. ACS Bluetooth PC/SC 드라이버 설치와 리더기 연결(파란 LED)을 확인하세요.')
            ok = False
        elif len(match) > 1:
            say(f'X 리더가 여러 개입니다. --reader 로 하나를 지정하세요: {match}')
            ok = False
        else:
            say(f'O 사용할 리더: {match[0]}')
    except LookupError:
        pass
    except Exception as error:  # noqa: BLE001
        say(f'X PC/SC 오류: {error}  (pyscard 설치/Smart Card 서비스 확인)')
        ok = False
    try:
        r = httpx.get(f'{api}/api/v1/current-task', timeout=5)
        r.raise_for_status()
        say(f'O 로봇 PC 웹 API 연결 성공: {api} (현재 작업: {r.json().get("task")})')
    except Exception as error:  # noqa: BLE001
        say(f'X 로봇 PC 웹 API 연결 실패: {api} -> {error}')
        say('  로봇 PC에서 start_lab.py --host 0.0.0.0 실행 여부, 같은 네트워크 여부, 방화벽(8000)을 확인하세요.')
        ok = False
    return ok


def submit(api, uid, quantity):
    """Send the raw reader value; the robot PC matches it (even partial) to one DB tag.

    Returns the matched full UID, or None when the robot PC rejected or could not be reached.
    """
    try:
        r = httpx.get(f'{api}/api/v1/tags/{uid}', timeout=5)
        if r.status_code == 200:
            info = r.json()
            note = '' if info.get('tag_uid') == uid else f' (읽은 값 {uid} -> {info.get("tag_uid")})'
            say(f'  DB 매칭: {info.get("product_name")} ({info.get("yolo_class_name")}) -> {info.get("target_box_id")}{note}')
        elif r.status_code in (404, 409):
            say(f'X DB 매칭 실패 {r.status_code}: {r.json().get("detail", r.text)[:200]}')
            say('  태그를 뗐다가 다시 올려 주세요.')
            return None
    except (httpx.HTTPError, ValueError):
        pass  # the scan-event below reports the real error
    payload = dict(uid=uid, quantity=quantity, event_id=str(uuid4()))
    # Retry the same event_id after an uncertain outcome so the robot never gets a duplicate task.
    for attempt in range(5):
        try:
            r = httpx.post(f'{api}/api/v1/scan-event', json=payload, timeout=10)
            if r.is_error:
                if 'active task' in r.text:
                    say('X 이 상품은 이미 대기/진행 중인 작업이 있어 새로 등록하지 않았습니다. (대시보드에서 작업 확인)')
                else:
                    say(f'X 등록 거부 {r.status_code}: {r.text[:200]}  (DB에 등록된 태그인지 확인)')
                return None
            body = r.json()
            task = body.get('task') or {}
            say(f'O 작업 등록: task={task.get("task_id", "?")[:8]} 상태={task.get("status")} -> 로봇이 집으러 갑니다')
            return body.get('uid') or uid
        except httpx.TransportError as error:
            if attempt == 4:
                say(f'X 로봇 PC 전송 실패: {error}')
                return None
            time.sleep(min(2 ** attempt, 8))
    return None


def wait_removed(scanner, uid):
    """Block until the tag leaves the reader.

    Partial reads of the resting tag are ignored; only "no card" or a different full-length UID
    counts as removed, so a flaky read never queues the same tag twice.
    """
    while True:
        try:
            seen = scanner.scan(timeout=0.8)
        except TimeoutError:
            return
        if len(seen) >= len(uid) and seen != uid:
            return
        time.sleep(0.2)


def keyboard_loop(api, quantity, lines=None, repeat_s=3.0):
    """Send each typed line as a UID (reader in keyboard mode, or a person typing).

    Spaces/colons are ignored and partial values are matched by the robot PC. The same tag
    typed again within repeat_s seconds (a reader repeating while the tag rests) is skipped.
    """
    lines = lines if lines is not None else iter(input, None)
    last_uid, last_at = None, 0.0
    for line in lines:
        raw = ''.join(ch for ch in line.upper() if ch in '0123456789ABCDEF')
        if not raw:
            continue
        if len(raw) < 4:
            say(f'X 너무 짧은 값입니다: {line.strip()!r} (4글자 이상 필요). 태그를 다시 찍어 주세요.')
            continue
        say(f'입력 UID: {raw}' + ('' if len(raw) >= 8 else '  (일부만 입력됨, 로봇 PC DB에서 매칭)'))
        now = time.monotonic()
        if raw == last_uid and now - last_at < repeat_s:
            say('  같은 태그 반복 입력이라 건너뜁니다.')
            continue
        uid = submit(api, raw, quantity)
        if uid:
            last_uid, last_at = uid, now
            if raw != uid:
                last_uid = raw  # also skip the same partial value repeated right away
        say('다음 태그를 찍어 주세요. (종료: Ctrl+C)')


def main(argv=None):
    parser = argparse.ArgumentParser(description='ACR1555U -> robot PC RFID bridge')
    parser.add_argument('--api', required=True, help='robot PC dashboard URL, e.g. http://192.168.0.10:8000')
    parser.add_argument('--reader', help='PC/SC reader name substring when several readers are listed')
    parser.add_argument('--quantity', type=int, default=1)
    parser.add_argument('--check', action='store_true', help='only check reader and robot PC connection')
    parser.add_argument('--read-only', action='store_true', help='print UIDs without sending them')
    parser.add_argument('--keyboard', action='store_true',
                        help='no PC/SC: read UIDs typed into this window (reader keyboard mode or manual entry)')
    args = parser.parse_args(argv)
    api = args.api.rstrip('/')
    if args.keyboard:
        if not check(api, args.reader, need_reader=False):
            say('점검 실패로 종료합니다. 위 X 항목을 해결한 뒤 다시 실행하세요.')
            return 1
        say('이 창을 클릭해 둔 상태에서 태그를 찍어 주세요. 직접 UID를 입력하고 Enter를 눌러도 됩니다. (종료: Ctrl+C)')
        try:
            keyboard_loop(api, args.quantity)
        except (KeyboardInterrupt, EOFError):
            say('종료합니다.')
        return 0
    if args.check:
        return 0 if check(api, args.reader) else 1
    if not args.read_only and not check(api, args.reader):
        say('점검 실패로 종료합니다. 위 X 항목을 해결한 뒤 다시 실행하세요.')
        return 1
    scanner = RFIDScanner(args.reader)
    say('태그를 리더기에 올려 주세요. (종료: Ctrl+C)')
    try:
        while True:
            try:
                uid = scanner.scan(timeout=3600)
            except TimeoutError:
                continue
            say(f'태그 UID: {uid}' + ('' if len(uid) >= 8 else '  (일부만 읽힘, 로봇 PC DB에서 매칭)'))
            if not args.read_only:
                uid = submit(api, uid, args.quantity) or uid
            wait_removed(scanner, uid)
            say('태그를 뗐습니다. 다음 태그를 올려 주세요.')
    except KeyboardInterrupt:
        say('종료합니다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
