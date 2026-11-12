"""Browser transcripts use the original packing processor on every OS."""
import asyncio
import logging
from datetime import datetime
from uuid import uuid4
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from .store import DomainError
from .voice_commands import INTENTS, normalized, packing_answer
from . import robot_voice

# Packing-demo intents whose phrases now drive the real robot instead (stop / go / pick).
ROBOT_OWNED = ('cmd-stop', 'cmd-go', 'cmd-pick')

log = logging.getLogger("app.voice")
router = APIRouter(prefix='/api/voice')

class Transcript(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    session: str = Field(min_length=32, max_length=32)
    turn: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=500)

class Voice:
    def __init__(self, packing, enabled, *, barge_in=False):
        self.packing, self.enabled = packing, enabled
        self.state = 'idle' if enabled else 'disabled'
        self.error = self.transcript = self.reply = ''
        self.session = None
        self.turn = 0
        self.confirming = False
        self.robot = None          # robot_voice.RobotVoice, set by the app when the robot API is installed
        self.pending = None        # robot action waiting for a spoken yes/no
        self.auto = None           # robot_voice.AutoRun while "피킹 로봇 가동" runs
        self.announcement, self.announce_seq = '', 0   # spoken by the browser when announce_seq changes
        self.history = []          # recent transcripts and what they did (GET /api/voice/history)
        self.lock = asyncio.Lock()

    def status(self):
        return dict(state=self.state, can_stop=self.session is not None, barge_in=False,
                    last_playback=None, error=self.error, transcript=self.transcript, reply=self.reply,
                    announcement=self.announcement, announce_seq=self.announce_seq,
                    auto=self.auto.info() if self.auto else None)

    def announce(self, text):
        self.announcement, self.announce_seq = text, self.announce_seq + 1
        log.info("[음성 안내] %s", text)

    async def start(self):
        pass  # Browser owns microphone permission; no server audio subprocess.

    async def stop(self, *, session_only=False):
        self.session = None
        self.confirming = False
        self.pending = None
        if self.auto is not None and self.auto.active:  # voice switched off: no further robot steps
            await self.auto.cancel()
        self.state = 'idle' if self.enabled else 'disabled'
        return self.status()

    async def wake(self):
        if not self.enabled:
            raise DomainError('YOLO_VOICE_ENABLED=1로 서버를 시작하세요.', 503)
        if self.session or self.lock.locked():
            raise DomainError('기존 음성 대화를 중단한 뒤 다시 시작하세요.', 409)
        self.session, self.turn = uuid4().hex, 1
        self.state = 'listening'
        self.error = self.transcript = self.reply = ''
        return dict(self.status(), session=self.session, turn=self.turn)

    async def accept(self, data):
        if self.lock.locked():
            raise DomainError('이전 음성 명령을 처리 중입니다.', 409)
        async with self.lock:
            if not self.session or (data.session, data.turn) != (self.session, self.turn):
                raise DomainError('만료되었거나 중복된 음성 명령입니다.', 409)
            self.turn += 1
            self.state, self.transcript = 'processing', data.text
            intent = INTENTS.get(normalized(data.text))
            log.info("[Web Speech API 수신] session=%s, turn=%s, text='%s', normalized='%s', intent=%s",
                     data.session, data.turn, data.text, normalized(data.text), intent)
            robot_reply = await self._robot_turn(data.text, intent)
            self.history = (self.history + [dict(
                time=datetime.now().astimezone().isoformat(timespec='seconds'), text=data.text,
                reply=robot_reply, auto=self.auto.info() if self.auto else None)])[-50:]
            if robot_reply is not None:
                if self.session == data.session:
                    self.reply, self.confirming = robot_reply, False
                    self.state = 'listening'
                log.info("[Web Speech API 로봇 응답] session=%s, reply='%s', pending=%s",
                         data.session, robot_reply, self.pending)
                return dict(self.status(), turn=self.turn)
            if intent == 'end':
                self.reply = '대화를 종료했습니다.'
                log.info("[Web Speech API 응답] session=%s, reply='%s'", data.session, self.reply)
                await self.stop()
            else:
                try:
                    answer = await asyncio.to_thread(packing_answer, self.packing, intent, confirming=self.confirming)
                except DomainError as exc:
                    if self.session == data.session:
                        self.reply, self.confirming = str(exc), False
                        log.warning("[Web Speech API 도메인 예외] %s", exc)
                except Exception as exc:
                    log.error("[Web Speech API 예외] %s", exc, exc_info=True)
                    await self.stop()
                    raise
                else:
                    if self.session == data.session:
                        self.reply, self.confirming = answer.text, answer.confirm
                        log.info("[Web Speech API 응답] session=%s, reply='%s', confirming=%s",
                                 data.session, self.reply, self.confirming)
                if self.session == data.session:
                    self.state = 'listening'
            return dict(self.status(), turn=self.turn)

    async def _robot_turn(self, text, intent):
        """Reply for a robot command (stop at once; anything that moves is asked back first), or None
        to let the packing demo handle the transcript."""
        if self.robot is None or not self.robot.available():
            return None
        action = robot_voice.parse(text)
        auto, word = self.auto, robot_voice.auto_word(text)
        if robot_voice.is_stop(action):  # never waits behind a question, never muted
            self.pending = None
            # a running "피킹 로봇 가동" halts on the E-stop and waits for 작업 재개
            return await self.robot.run(action)
        if auto is not None and auto.active:
            if word == 'end':
                await auto.cancel()
                self.announce('피킹 로봇 가동을 중지합니다.')
                return ''
            if auto.muted:
                return ''  # robot working: other voices and noise are ignored
            if auto.phase == 'stopped':
                if word in ('resume', 'start'):
                    auto.resume()
                    return ''
                if action is not None and action.kind == 'status':
                    return await self.robot.run(action)
                return ''
            if word == 'swap':
                auto.box_swapped()
                return ''
            if action is not None and action.kind == 'status':
                return await self.robot.run(action)
            return '진행 중입니다. 새 박스로 바꾼 뒤 알려 주세요.'
        unfinished = auto is not None and auto.phase in ('error', 'idle') and 0 < auto.done < auto.rounds
        if word == 'start' or (word == 'resume' and ('가동' in normalized(text) or unfinished)):
            # 가동 / 재가동 (or 작업 재개 after a run that was cut off): run the boxes, carrying on the count
            self.pending = None
            self.auto = robot_voice.AutoRun(self.robot.app, self.announce)
            self.auto.start(done=auto.done if unfinished else 0)
            return ''
        if self.pending is not None:
            pending, self.pending = self.pending, None
            if action is not None and action.kind == 'yes':
                return await self.robot.run(pending)
            if action is not None and action.kind == 'no':
                return f"{robot_voice.josa(pending.label, '을', '를')} 취소했습니다."
            if action is None and intent not in ROBOT_OWNED and intent is not None:
                return None  # a packing question instead of an answer: drop the pending action
        if intent is not None and intent not in ROBOT_OWNED:
            return None  # exact packing-demo phrase (재고/주문 조회, 예시 주문, 주문 확정, 대화 종료 …)
        if action is not None and action.kind in ('yes', 'no'):
            return '확인할 명령이 없습니다. ' + robot_voice.HELP
        if action is None:
            return robot_voice.HELP
        if action.kind == 'ask':
            return '어떤 물건을 집을까요? 물티슈, 스팸, 쫀득초코칩, 복숭아녹차 중에서 말씀해 주세요.'
        if action.confirm:
            self.pending = action
            return robot_voice.question(action)
        return await self.robot.run(action)

def check_control_origin(request):
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise DomainError('로컬 대시보드에서 음성 대화를 제어하세요.', 403)
    origin = request.headers.get('origin')
    if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        raise DomainError('동일 출처의 대시보드에서 제어하세요.', 403)

@router.get('/status')
async def status(request: Request):
    return request.app.state.voice.status()

@router.get('/history')
async def history(request: Request):
    """Recent transcripts with the reply they got (None = handled by the packing demo)."""
    return {'history': request.app.state.voice.history}

@router.post('/wake')
async def wake(request: Request):
    check_control_origin(request)
    return await request.app.state.voice.wake()

@router.post('/transcript')
async def transcript(data: Transcript, request: Request):
    check_control_origin(request)
    return await request.app.state.voice.accept(data)

@router.post('/stop')
async def stop_listening(request: Request):
    check_control_origin(request)
    return await request.app.state.voice.stop(session_only=True)
