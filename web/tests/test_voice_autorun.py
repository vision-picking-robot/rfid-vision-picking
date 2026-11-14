"""'피킹 로봇 가동' voice run: muted while the robot works, 상자 교환 완료 starts the next box, 4 boxes end it."""
import asyncio
from types import SimpleNamespace

import pytest

from app import robot_voice
from app.voice import Voice


class FakeRobot:
    """Mimics the phone-remote state the robot cycle reports while it scans, picks and returns."""

    def __init__(self, tags):
        self.tags = list(tags)  # UID read at each scan, None = nothing read
        self.link = {'state': 'IDLE', 'message': '태그 대기 중'}
        self.last_scan = None
        self.completed = None
        self.task = None
        self.estop = False
        self.paused = False
        self.commands = []
        self.seq = 0
        self.script = []

    async def snapshot(self):
        if self.script:
            self.script.pop(0)()
        if self.paused:  # a paused cycle holds before its next step
            return {'robot_connected': True, 'emergency_stopped': self.estop, 'paused': True,
                    'robot_link': {'state': 'PAUSED', 'message': '일시정지'}, 'last_scan': self.last_scan,
                    'last_completed_event': self.completed, 'current_task': self.task}
        return {'robot_connected': True, 'emergency_stopped': self.estop, 'paused': False, 'robot_link': dict(self.link),
                'last_scan': self.last_scan, 'last_completed_event': self.completed, 'current_task': self.task}

    def queue_ready(self, uid, name):
        """A tag read before a stop: the task waits READY; the cycle picks it once running."""
        self.task = {'task_id': 'ready1', 'status': 'READY', 'tag_uid': uid, 'product_name': name}

        def picking():
            self.link = {'state': 'PICKING', 'message': '피킹'}

        def placed():
            self.completed, self.task = {'task_id': 'ready1'}, None

        def home():
            self.link = {'state': 'IDLE', 'message': '태그 대기 중'}
        self.script = [picking, picking, placed, home]

    async def control(self, command):
        self.commands.append(command)
        if command == 'emergency_stop':  # the cycle stops; a running task is marked DEFECTIVE
            self.estop, self.task, self.script = True, None, []
            self.link = {'state': 'ESTOPPED', 'message': '비상 정지'}
        if command == 'reset_stop':
            self.estop = False
            self.link = {'state': 'IDLE', 'message': '태그 대기 중'}
        if command in ('pause', 'resume'):
            self.paused = command == 'pause'
        if command != 'scan_dispatch':
            return {'message': command}
        uid = self.tags.pop(0)
        self.seq += 1
        n = self.seq

        def scanning():
            self.link = {'state': 'SCANNING', 'message': '스캔'}

        def read():
            if uid is None:
                self.link = {'state': 'IDLE', 'message': '태그가 읽히지 않아'}
                return
            self.last_scan = {'seq': n, 'accepted': True, 'uid': uid, 'product_name': '스팸', 'task_id': f't{n}'}
            self.task = {'task_id': f't{n}', 'status': 'PICKING'}
            self.link = {'state': 'PICKING', 'message': '피킹'}

        def placed():
            if uid is not None:
                self.completed, self.task = {'task_id': f't{n}'}, None

        def home():
            self.link = {'state': 'IDLE', 'message': '태그 대기 중'}
        idle = [lambda: None] * 20  # picking takes a while (lets a test act mid-pick)
        self.script = [scanning, scanning, read, *idle, placed, lambda: None, home]
        return {'message': 'ok'}


def make_voice(robot):
    app = SimpleNamespace(state=SimpleNamespace(robot_snapshot=robot.snapshot, robot_control=robot.control,
                                                robot_queue_pick=None))
    voice = Voice(packing=None, enabled=True)
    voice.robot = robot_voice.RobotVoice(app)
    return voice


async def say(voice, text):
    return await voice._robot_turn(text, None)


async def until(predicate, timeout=5.0):
    for _ in range(int(timeout / 0.01)):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError('condition not reached')


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(robot_voice, 'SWAP_HOLDOFF_S', 0.0)
    monkeypatch.setattr(robot_voice, 'HOLDOFF_S', 0.0)
    real = robot_voice.AutoRun.__init__

    def quick(self, app, announce, **kw):
        real(self, app, announce, poll_s=0.005, **kw)
    monkeypatch.setattr(robot_voice.AutoRun, '__init__', quick)


def test_four_boxes_with_muting_and_box_swaps():
    async def scenario():
        robot = FakeRobot(['0B71E65D'] * 4)
        voice = make_voice(robot)
        said = []
        voice.announce = lambda text: said.append(text) or Voice.announce(voice, text)
        assert await say(voice, '피킹 로봇 가동') == ''
        assert '첫 번째 박스부터' in said[0]
        assert voice.auto.muted
        assert await say(voice, '스팸 집어줘') == ''          # muted: ignored, nothing queued
        await until(lambda: voice.auto.phase == 'swap_wait')
        assert not voice.auto.muted and voice.auto.done == 1
        assert any('인식했습니다' in s for s in said) and '새 박스로 바꾼 뒤' in said[-1]
        for box in range(2, 5):
            assert await say(voice, '상자 교환 완료') == ''
            await until(lambda: voice.auto.done == box and (voice.auto.phase == 'swap_wait' or not voice.auto.active))
        await until(lambda: not voice.auto.active)
        assert robot.commands.count('scan_dispatch') == 4
        assert said[-1].endswith('피킹 로봇 가동을 중지합니다.')
        # announcements never contain words that would drive the run by echo
        for text in said[:-1]:
            assert robot_voice.auto_word(text) is None, text
    asyncio.run(scenario())


def test_no_tag_retries_the_same_box_and_stop_then_resume_carries_on():
    async def scenario():
        robot = FakeRobot([None, '0B71E65D', '0B71E65D', '0B71E65D'])
        voice = make_voice(robot)
        await say(voice, '로봇 가동해')
        await until(lambda: voice.auto.phase == 'swap_wait')
        assert voice.auto.done == 0 and '태그를 읽지 못했습니다' in voice.announcement
        await say(voice, '교환 완료')
        await until(lambda: voice.auto.done == 1 and voice.auto.phase == 'swap_wait')
        await say(voice, '상자 교환 완료')
        await until(lambda: voice.auto.phase == 'picking')
        await say(voice, '정지')                                # heard even while muted
        assert robot.commands[-1] == 'emergency_stop'
        await until(lambda: voice.auto.phase == 'stopped')
        assert voice.auto.active and not voice.auto.muted and '정지했습니다' in voice.announcement
        assert robot_voice.auto_word(voice.announcement) is None  # its echo cannot resume the run
        assert await say(voice, '스팸 집어줘') == ''             # only resume words act while stopped
        await say(voice, '작업 재개')
        await until(lambda: voice.auto.done == 2 and voice.auto.phase == 'swap_wait')
        assert 'reset_stop' in robot.commands
        assert robot.commands.count('scan_dispatch') == 4      # the interrupted box is scanned again
    asyncio.run(scenario())


def test_pause_words_hold_a_running_box_and_resume_carries_on():
    async def scenario():
        robot = FakeRobot(['0B71E65D'])
        voice = make_voice(robot)
        await say(voice, '피킹 로봇 가동')
        await until(lambda: voice.auto.phase == 'picking')
        await say(voice, '잠깐만')                              # pause, heard while muted (not an E-stop)
        assert robot.commands[-1] == 'pause' and not robot.estop
        assert await say(voice, '스팸 집어줘') == ''             # other speech still ignored
        await say(voice, '작업 재개')                            # "재개" works while paused
        assert robot.commands[-1] == 'resume' and not robot.paused
        await until(lambda: voice.auto.done == 1)
    asyncio.run(scenario())


def test_resume_after_a_pause_continues_the_robot_not_an_unfinished_run():
    async def scenario():
        robot = FakeRobot([])
        voice = make_voice(robot)
        voice.auto = robot_voice.AutoRun(voice.robot.app, voice.announce)
        voice.auto.done = 2                                     # an earlier run was cut off at box 2 of 4
        await say(voice, '잠깐')                                 # phone-tag task running, no voice run
        assert robot.commands[-1] == 'pause' and robot.paused
        reply = await say(voice, '재개')
        assert reply == robot_voice.question(robot_voice.parse('재개'))  # asked back, no new run
        assert not voice.auto.active
        await say(voice, '네')
        assert robot.commands[-1] == 'resume' and not robot.paused
        assert 'scan_dispatch' not in robot.commands
        assert robot.paused is False
        await say(voice, '재개')                                 # not paused: carries on the cut-off run
        assert voice.auto.active
        await voice.auto.cancel()
    asyncio.run(scenario())


def test_phone_estop_halts_and_phone_release_resumes():
    async def scenario():
        robot = FakeRobot(['0B71E65D', '0B71E65D'])
        voice = make_voice(robot)
        await say(voice, '피킹 로봇 가동')
        await until(lambda: voice.auto.phase == 'picking')
        await robot.control('emergency_stop')                  # pressed on the phone
        await until(lambda: voice.auto.phase == 'stopped')
        robot.estop = False                                     # [정지 해제] on the phone
        robot.link = {'state': 'IDLE', 'message': '태그 대기 중'}
        await until(lambda: voice.auto.done == 1)
        assert voice.auto.active
    asyncio.run(scenario())


def test_a_tag_read_before_the_stop_is_picked_without_rescanning():
    async def scenario():
        robot = FakeRobot([])
        robot.queue_ready('0B71E65D', '스팸')
        voice = make_voice(robot)
        await say(voice, '재가동')                              # contains 가동: also starts a run
        await until(lambda: voice.auto.done == 1)
        assert 'scan_dispatch' not in robot.commands
    asyncio.run(scenario())


def test_swap_word_is_ignored_right_after_listening_resumes(monkeypatch):
    monkeypatch.setattr(robot_voice, 'SWAP_HOLDOFF_S', 60.0)
    auto = robot_voice.AutoRun.__new__(robot_voice.AutoRun)
    auto.phase, auto.muted, auto.unmuted_at = 'swap_wait', False, robot_voice.time.monotonic()
    auto.swapped = asyncio.Event()
    assert auto.box_swapped() is False  # an echo of the announcement cannot start the next box
