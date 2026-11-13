"""Spoken robot commands: stop at once, anything that moves asks back first, packing demo still answers."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.robot_voice import parse


def test_parse_maps_phrases_to_robot_actions():
    # emergency stop: only 정지 / 스톱
    for phrase in ('정지', '스톱', '로봇 정지해', 'stop'):
        assert parse(phrase).command == 'emergency_stop' and not parse(phrase).confirm, phrase
    # pause: 일시정지, 대기, anything with 잠깐/잠시, and 멈춰/그만
    for phrase in ('피킹 일시정지해줘', '대기', '잠깐', '잠깐만요', '잠시 멈춰', '잠시만', '멈춰', '그만'):
        assert parse(phrase).command == 'pause' and not parse(phrase).confirm, phrase
    assert parse('정지 해제').command == 'reset_stop' and parse('정지 해제').confirm
    pick = parse('물티슈 집어줘')
    assert pick.kind == 'pick' and pick.command == '0B71ED5D' and pick.confirm
    assert parse('초코칩 가져와').command == '0B71E55D'
    assert parse('음료수 옮겨줘').command == '0B71E75D'
    assert parse('태그 읽어줘').command == 'scan_dispatch'
    assert parse('작업 재개해줘').command == 'resume' and parse('시작').command == 'resume'
    assert parse('홈으로 가').command == 'home'
    assert parse('지금 상태 알려줘').kind == 'status'
    assert parse('집어').kind == 'ask'
    assert parse('네').kind == 'yes' and parse('아니요').kind == 'no'
    assert parse('오늘 날씨 어때') is None


def test_dashboard_voice_drives_the_robot_paths(tmp_path):
    settings = Settings(camera_autostart=False, voice_enabled=True)
    with TestClient(create_app(settings, state_root=tmp_path)) as client:
        wake = client.post('/api/voice/wake').json()
        turn = iter(range(1, 100))

        def say(text):
            body = dict(session=wake['session'], turn=next(turn), text=text)
            response = client.post('/api/voice/transcript', json=body)
            assert response.status_code == 200, response.text
            return response.json()['reply']

        # a pick is asked back; "아니요" queues nothing
        assert '집어서 상자에 넣을까요' in say('스팸 집어줘')
        assert '취소' in say('아니요')
        assert client.get('/api/v1/current-task').json()['task'] is None
        # "네" queues the task for the product's tag and shows it as the last tag (source voice)
        say('스팸 집어줘')
        assert '작업을 등록했습니다' in say('네')
        task = client.get('/api/v1/current-task').json()['task']
        assert task['tag_uid'] == '0B71E65D'
        scan = client.get('/api/v1/last-scan').json()['last_scan']
        assert scan['source'] == 'voice' and scan['accepted']
        # stop runs at once, even while a question is pending
        assert '처음 자세로 돌아갈까요' in say('홈으로')
        say('정지')
        status = client.get('/api/v1/mobile/status').json()
        assert status['emergency_stopped'] and status['commands'][-1]['command'] == 'emergency_stop'
        assert not any(c['command'] == 'home' for c in status['commands'])
        # moving again needs the asked-back reset
        assert '비상 잠금을 풀까요' in say('정지 해제')
        say('네')
        assert not client.get('/api/v1/mobile/status').json()['emergency_stopped']
        # the packing demo still answers its own phrases; unknown speech gets the help text
        assert '복숭아녹차' in say('재고 알려줘')
        assert '물티슈 집어줘' in say('오늘 날씨 어때')
        assert '현재 작업은' in say('지금 상태')


def test_manual_lists_the_words_the_recognizer_uses(tmp_path):
    from app import robot_voice as rv
    with TestClient(create_app(Settings(camera_autostart=False), state_root=tmp_path)) as client:
        manual = client.get('/api/voice/manual').json()
    estop, pause, reset = manual['immediate']
    assert estop['words'] == ['정지', '스톱', 'stop']
    assert all(parse(w).command == 'emergency_stop' for w in estop['words'])
    assert all(parse(w).command == 'pause' for w in pause['words'] if not w.startswith('('))
    assert all(parse(w).command == 'reset_stop' for w in reset['words'])
    picks = manual['asked'][0]['words']
    assert len(picks) == len(rv.ITEMS) and picks[0].startswith('물티슈')
    assert '피킹 로봇 가동' in [s['say'] for s in manual['auto']['steps']]
    titles = [p['title'] for p in manual['packing']]
    assert '재고 조회' in titles and '주문 확정' in titles
    # phrases the robot takes over (멈춰 / 시작 / 집어) are not listed as packing-demo phrases
    assert not any('멈춰' in ' '.join(p['phrases']) for p in manual['packing'])


def test_particles_follow_the_item_name():
    from app.robot_voice import josa
    assert josa('스팸', '을', '를') == '스팸을' and josa('물티슈', '을', '를') == '물티슈를'
    assert josa('복숭아녹차', '은', '는') == '복숭아녹차는' and josa('쫀득초코칩', '은', '는') == '쫀득초코칩은'


def test_nothing_the_robot_says_is_itself_a_command():
    """The laptop microphone hears the speaker: a reply containing "일시정지" paused the robot again and
    again (2026-11-13). Every fixed robot reply and question must parse to no command."""
    from app import robot_voice as rv
    spoken = [*rv.QUESTION.values(), *rv.CONTROL_REPLY.values(), rv.NOT_CONNECTED.strip()]
    for text in spoken:
        assert parse(text) is None, text


def test_own_reply_heard_back_is_ignored_but_short_answers_are_not(tmp_path):
    with TestClient(create_app(Settings(camera_autostart=False, voice_enabled=True), state_root=tmp_path)) as client:
        wake = client.post('/api/voice/wake').json()
        turn = [wake['turn']]

        def say(text):
            response = client.post('/api/voice/transcript', json=dict(session=wake['session'], turn=turn[0], text=text))
            assert response.status_code == 200, response.text
            turn[0] = response.json()['turn']
            return response.json()

        client.get('/api/v1/mobile/status', params={'robot': 'remote_rfid'})  # robot cycle connected
        reply = say('대기')['reply']
        assert reply == '알겠습니다. 로봇이 다음 동작 전에 기다립니다.'
        before = len(client.get('/api/v1/mobile/status').json()['commands'])
        for heard in ('로봇이 다음 동작 전에', '알겠습니다 로봇이 다음 동작', '로봇이 다음 동장 전에 기다립니다'):
            assert say(heard).get('echo') is True, heard  # pieces of the reply, also slightly misheard
        assert len(client.get('/api/v1/mobile/status').json()['commands']) == before
        # a short command right after the reply still works: the operator can always stop the robot
        say('정지')
        assert client.get('/api/v1/mobile/status').json()['emergency_stopped']
        history = client.get('/api/voice/history').json()
        entries = history if isinstance(history, list) else history.get('history', [])
        assert sum(bool(e.get('echo')) for e in entries) == 3
