"""Spoken robot commands: stop at once, anything that moves asks back first, packing demo still answers."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.robot_voice import parse


def test_parse_maps_phrases_to_robot_actions():
    assert parse('멈춰').command == 'emergency_stop' and not parse('멈춰').confirm
    assert parse('피킹 일시정지해줘').command == 'pause'
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
        assert '홈 자세로 이동할까요' in say('홈으로')
        say('멈춰')
        status = client.get('/api/v1/mobile/status').json()
        assert status['emergency_stopped'] and status['commands'][-1]['command'] == 'emergency_stop'
        assert not any(c['command'] == 'home' for c in status['commands'])
        # moving again needs the asked-back reset
        assert '해제할까요' in say('정지 해제')
        say('네')
        assert not client.get('/api/v1/mobile/status').json()['emergency_stopped']
        # the packing demo still answers its own phrases; unknown speech gets the help text
        assert '생수' in say('재고 알려줘')
        assert '물티슈 집어줘' in say('오늘 날씨 어때')
        assert '현재 작업은' in say('지금 상태')


def test_particles_follow_the_item_name():
    from app.robot_voice import josa
    assert josa('스팸', '을', '를') == '스팸을' and josa('물티슈', '을', '를') == '물티슈를'
    assert josa('복숭아녹차', '은', '는') == '복숭아녹차는' and josa('쫀득초코칩', '은', '는') == '쫀득초코칩은'
