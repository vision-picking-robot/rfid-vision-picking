"""Spoken robot commands for the dashboard voice assistant.

Uses the same paths as the Galaxy remote (robot_rfid.api_server hooks on app.state): a pick queues a
task for the product's tag, the rest are phone control commands. Anything that moves the arm is asked
back once ("물티슈 집을까요?") and runs only on a spoken yes; stop commands run at once.
"""
from dataclasses import dataclass

from .voice_commands import normalized

# (aliases as spoken, tag UID, display name). The tag decides the product and its zone/box.
ITEMS = (
    (("물티슈", "티슈"), "0B71ED5D", "물티슈"),
    (("스팸",), "0B71E65D", "스팸"),
    (("쫀득초코칩", "초코칩", "쫀득", "초코"), "0B71E55D", "쫀득초코칩"),
    (("복숭아녹차", "녹차", "복숭아", "페트병", "음료수", "음료"), "0B71E75D", "복숭아녹차"),
)
STOP_RESET = ("정지해제", "비상정지해제", "정지풀어")
# Pause (the robot holds before its next move): "대기", anything with 잠깐/잠시, and 멈춰/그만.
PAUSE = ("일시정지", "대기", "잠깐", "잠시", "멈춰", "멈춤", "그만")
# Emergency stop (move_stop at once): only these.
STOP = ("정지", "스톱", "stop")
RESUME = ("재개", "다시시작", "계속", "이어서", "피킹시작")
HOME = ("홈으로", "홈복귀", "홈자세", "원위치", "홈")
SCAN = ("태그읽", "태그스캔", "리더기", "스캔")
STATUS = ("상태",)
PICK_VERBS = ("집어", "집기", "피킹", "가져", "옮겨", "담아")
YES = ("네", "응", "예", "어", "그래", "확인", "좋아", "진행", "해줘", "실행", "네해줘", "응해줘", "그래해줘", "진행해줘", "실행해줘", "네네", "응응")
NO = ("아니", "아니요", "아니야", "취소", "하지마", "됐어", "안해")


@dataclass(frozen=True)
class Action:
    kind: str          # 'control' | 'pick' | 'status' | 'ask' | 'yes' | 'no'
    command: str = ""  # control command, or tag UID for a pick
    label: str = ""    # what is said back
    confirm: bool = False


def parse(text):
    """Robot action for a final transcript, or None when it is not a robot command."""
    t = normalized(text)
    if not t:
        return None
    if any(w in t for w in STOP_RESET):
        return Action("control", "reset_stop", "비상 정지 해제", confirm=True)
    if any(w in t for w in PAUSE):
        return Action("control", "pause", "일시정지")
    if any(w in t for w in STOP):
        return Action("control", "emergency_stop", "비상 정지")
    if t in YES:
        return Action("yes")
    if t in NO or t.startswith("아니"):
        return Action("no")
    for aliases, uid, name in ITEMS:
        if any(a in t for a in aliases):
            return Action("pick", uid, name, confirm=True)
    if any(w in t for w in SCAN):
        return Action("control", "scan_dispatch", "태그 읽기", confirm=True)
    if t == "시작" or any(w in t for w in RESUME):
        return Action("control", "resume", "작업 재개", confirm=True)
    if any(w in t for w in HOME):
        return Action("control", "home", "홈 복귀", confirm=True)
    if any(w in t for w in STATUS):
        return Action("status")
    if any(w in t for w in PICK_VERBS):
        return Action("ask")
    return None


def josa(word, with_final, without_final):
    """Korean particle after `word`: 을/를, 은/는 … depending on its last syllable's final consonant."""
    code = ord(word[-1]) - 0xAC00 if word else -1
    return word + (with_final if 0 <= code <= 11171 and code % 28 else without_final)


def is_stop(action):
    return action is not None and action.kind == "control" and action.command in ("pause", "emergency_stop")


QUESTION = {
    "reset_stop": "비상 정지를 해제할까요? 해제하면 로봇이 다시 움직일 수 있습니다.",
    "scan_dispatch": "리더기로 가서 태그를 읽을까요?",
    "resume": "작업을 재개할까요?",
    "home": "홈 자세로 이동할까요?",
}


def question(action):
    if action.kind == "pick":
        return f"{josa(action.label, '을', '를')} 집어서 상자에 넣을까요?"
    # No "네 또는 아니요" in the question: its echo through the speakers must not answer it.
    return QUESTION[action.command]


HELP = ("물건 이름과 함께 '물티슈 집어줘'처럼 말하거나, '태그 읽어줘', '잠깐(일시정지)', '재개', '정지(비상 정지)', "
        "'홈으로', '지금 상태', '재고 조회', '주문 조회' 중에서 말씀해 주세요.")


def describe_status(snap):
    link = snap.get("robot_link") or {}
    if snap.get("emergency_stopped"):
        head = "비상 정지 상태입니다. '정지 해제'라고 말하면 해제할 수 있습니다."
    elif not snap.get("robot_connected"):
        head = "로봇 사이클이 연결되어 있지 않습니다."
    elif snap.get("paused"):
        head = "일시정지 상태입니다."
    else:
        head = link.get("message") or "로봇이 연결되어 있습니다."
    task = snap.get("current_task")
    parts = [head]
    if task:
        parts.append(f"현재 작업은 {task.get('product_name') or task.get('tag_uid')}, {task.get('status')} 상태입니다.")
    scan = snap.get("last_scan")
    if scan:
        what = scan.get("product_name") or scan.get("uid") or scan.get("raw_uid")
        parts.append(f"최근 태그는 {what}" + ("입니다." if scan.get("accepted") else ", 거부되었습니다."))
    return " ".join(parts)


class RobotVoice:
    """Runs parsed actions against the app's robot hooks (installed by install_rfid_routes)."""

    def __init__(self, app):
        self.app = app

    def available(self):
        return all(hasattr(self.app.state, k) for k in ("robot_control", "robot_queue_pick", "robot_snapshot"))

    async def run(self, action):
        from fastapi import HTTPException
        try:
            if action.kind == "status":
                return describe_status(await self.app.state.robot_snapshot())
            if action.kind == "pick":
                result = await self.app.state.robot_queue_pick(action.command)
                connected = (await self.app.state.robot_snapshot())["robot_connected"]
                tail = "" if connected else " 다만 로봇 사이클이 연결되어 있지 않아 아직 움직이지 않습니다."
                return f"{action.label} 작업을 등록했습니다. 로봇이 집으러 갑니다.{tail}" if result["created"] \
                    else f"{josa(action.label, '은', '는')} 이미 대기 중인 작업이 있습니다."
            packet = await self.app.state.robot_control(action.command)
            return packet["message"]
        except HTTPException as exc:
            return f"{josa(action.label or '명령', '을', '를')} 실행하지 못했습니다: {exc.detail}"


# ---- "피킹 로봇 가동": voice-run box cycle -------------------------------------------------------
# 가동 -> (voice muted) tag scan -> pick -> place -> (voice on) operator swaps the box and says
# "상자 교환 완료" -> repeat; after AUTO_ROUNDS boxes: "피킹 로봇 가동을 중지합니다".
# An E-stop (voice "멈춰", phone, …) halts the run; "작업 재개 / 재가동 / 재시작" releases it and the
# run carries on with the same box. Announcements never contain trigger words (가동/상자/교환/재개 …)
# so their echo through the speakers cannot drive a step.
import asyncio  # noqa: E402
import time  # noqa: E402

AUTO_ROUNDS = 4
AUTO_END = ("중지", "종료")
AUTO_RESUME = ("재개", "재가동", "재시작", "다시시작", "이어서", "계속")
AUTO_START = ("가동", "작동")
AUTO_SWAP = ("상자", "교환")
HOLDOFF_S = 3.0            # ignore swap/resume words this long after listening resumes (announcement echo)
SWAP_HOLDOFF_S = HOLDOFF_S
ORDINAL = {1: "첫 번째", 2: "두 번째", 3: "세 번째", 4: "네 번째", 5: "다섯 번째"}


def auto_word(text):
    """'end' | 'resume' | 'start' | 'swap' | None for the auto-run vocabulary."""
    t = normalized(text)
    for word, words in (("end", AUTO_END), ("resume", AUTO_RESUME), ("start", AUTO_START), ("swap", AUTO_SWAP)):
        if any(w in t for w in words):
            return word
    return None


class AutoRunError(RuntimeError):
    pass


class AutoRunStopped(AutoRunError):
    """The robot is E-stopped: wait for a resume word."""


class AutoRun:
    """Drives the robot through the phone-remote hooks and watches its reported state."""

    def __init__(self, app, announce, rounds=AUTO_ROUNDS, poll_s=0.5, scan_timeout_s=60.0,
                 pick_timeout_s=300.0, idle_timeout_s=120.0):
        self.app, self.announce, self.rounds, self.poll_s = app, announce, rounds, poll_s
        self.scan_timeout_s, self.pick_timeout_s, self.idle_timeout_s = scan_timeout_s, pick_timeout_s, idle_timeout_s
        self.done = 0
        self.phase = "idle"
        self.muted = False
        self.unmuted_at = 0.0
        self.swapped = asyncio.Event()
        self.resumed = asyncio.Event()
        self.task = None

    @property
    def active(self):
        return self.task is not None and not self.task.done()

    def info(self):
        return dict(active=self.active, phase=self.phase, done=self.done, total=self.rounds, muted=self.muted)

    def start(self, done=0):
        self.done, self.phase, self.muted = done, "starting", True
        # said right away so the transcript reply already carries it
        self.announce(f"피킹 로봇을 시작합니다. {ORDINAL.get(done + 1, str(done + 1) + '번째')} 박스부터 진행합니다.")
        self.task = asyncio.create_task(self._run())

    async def cancel(self):
        if self.active:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self.phase, self.muted = "idle", False

    def _settled(self):
        return not self.muted and time.monotonic() - self.unmuted_at >= HOLDOFF_S

    def box_swapped(self):
        """Operator said 상자/교환. True when it starts the next box."""
        if self.phase != "swap_wait" or not self._settled() or time.monotonic() - self.unmuted_at < SWAP_HOLDOFF_S:
            return False
        self.swapped.set()
        return True

    def resume(self):
        """Operator said 작업 재개 / 재가동 / 재시작 while the run is stopped."""
        if self.phase != "stopped" or not self._settled():
            return False
        self.resumed.set()
        return True

    # -- robot state ------------------------------------------------------------------------------
    async def snap(self):
        snap = await self.app.state.robot_snapshot()
        if snap.get("emergency_stopped"):
            raise AutoRunStopped("비상 정지")
        if not snap.get("robot_connected"):
            raise AutoRunError("로봇 사이클 연결이 끊겼습니다")
        if (snap.get("robot_link") or {}).get("state") == "ERROR":
            raise AutoRunError((snap["robot_link"].get("message") or "로봇 오류")[:120])
        return snap

    async def wait(self, check, timeout_s, what):
        deadline = None if timeout_s is None else time.monotonic() + timeout_s
        while deadline is None or time.monotonic() < deadline:
            result = check(await self.snap())
            if result:
                return result
            await asyncio.sleep(self.poll_s)
        raise AutoRunError(f"{what} 시간이 초과되었습니다")

    async def wait_idle(self):
        await self.wait(lambda s: (s.get("robot_link") or {}).get("state") == "IDLE" and not s.get("current_task"),
                        self.idle_timeout_s, "로봇 대기 상태 확인")

    def listen(self, phase):
        self.phase, self.muted, self.unmuted_at = phase, False, time.monotonic()
        self.swapped.clear()
        self.resumed.clear()

    # -- one box ----------------------------------------------------------------------------------
    async def one_box(self):
        """Pick the item of the current box. Uses a task already queued (tag read before a stop),
        otherwise scans the tag first. Returns the item name, or None if no tag was read."""
        self.muted = True
        snap = await self.snap()
        task = snap.get("current_task")
        if task and task.get("status") == "READY":
            name = task.get("product_name") or task.get("tag_uid")
            self.announce(f"{name} 피킹을 이어서 진행합니다.")
        else:
            await self.wait_idle()
            before = ((await self.snap()).get("last_scan") or {}).get("seq")
            self.phase = "scanning"
            await self.app.state.robot_control("scan_dispatch")
            seen = {"scanning": False}

            def scanned(s):
                scan = s.get("last_scan") or {}
                if scan.get("seq") != before and scan.get("seq") is not None:
                    return ("ok", scan) if scan.get("accepted") else ("rejected", scan)
                state = (s.get("robot_link") or {}).get("state")
                if state == "SCANNING":
                    seen["scanning"] = True
                elif seen["scanning"] and state == "IDLE":
                    return ("none", None)
                return None
            outcome, scan = await self.wait(scanned, self.scan_timeout_s, "태그 인식")
            if outcome != "ok":
                return None
            name = scan.get("product_name") or scan.get("uid")
            task = {"task_id": scan.get("task_id")}
            self.announce(f"{name} 태그를 인식했습니다. 피킹을 시작합니다.")
        self.phase = "picking"
        task_id = task.get("task_id")
        await self.wait(lambda s: (s.get("last_completed_event") or {}).get("task_id") == task_id,
                        self.pick_timeout_s, "피킹")
        return name

    async def wait_swap(self, message):
        self.listen("swap_wait")
        self.announce(message)
        await self.wait(lambda s: self.swapped.is_set(), None, "박스 교환")
        self.phase, self.muted = "next", True

    async def halted(self):
        """E-stopped: listen for a resume word (or a release from the phone), then release and go on."""
        self.listen("stopped")
        self.announce("정지했습니다. 준비되면 말씀해 주세요.")
        while not self.resumed.is_set():
            snap = await self.app.state.robot_snapshot()
            if not snap.get("emergency_stopped"):
                break  # released elsewhere (phone [정지 해제])
            await asyncio.sleep(self.poll_s)
        self.phase, self.muted = "resuming", True
        snap = await self.app.state.robot_snapshot()
        if snap.get("emergency_stopped"):
            await self.app.state.robot_control("reset_stop")
        self.announce("다시 진행합니다.")
        # the robot cycle rises, goes home and reports IDLE (or starts a queued pick right away)
        await self.wait(lambda s: (s.get("robot_link") or {}).get("state") in ("IDLE", "PICKING"),
                        self.idle_timeout_s, "로봇 복귀")

    async def _run(self):
        swap_message = None
        try:
            while self.done < self.rounds:
                try:
                    if swap_message:
                        await self.wait_swap(swap_message)
                        await self.wait_idle()
                        self.announce(f"확인했습니다. {ORDINAL.get(self.done + 1, str(self.done + 1) + '번째')} "
                                      "박스의 태그를 읽으러 갑니다.")
                        swap_message = None
                    name = await self.one_box()
                except AutoRunStopped:
                    await self.halted()
                    continue  # same box again (a queued task is picked, otherwise the tag is re-read)
                if name is None:
                    swap_message = "태그를 읽지 못했습니다. 박스를 확인한 뒤 다시 알려 주세요."
                    continue
                self.done += 1
                if self.done < self.rounds:
                    swap_message = f"{josa(name, '을', '를')} 넣었습니다. 새 박스로 바꾼 뒤 알려 주세요."
            await self.wait_idle()
            self.phase, self.muted = "done", False
            self.announce(f"{ORDINAL.get(self.rounds, self.rounds)} 박스까지 모두 마쳤습니다. 피킹 로봇 가동을 중지합니다.")
        except AutoRunError as exc:
            self.phase, self.muted = "error", False
            self.announce(f"{exc}. 피킹 로봇 가동을 중지합니다.")
        except asyncio.CancelledError:
            self.phase, self.muted = "idle", False
            raise
        except Exception as exc:  # noqa: BLE001 - HTTPException from a control command, etc.
            self.phase, self.muted = "error", False
            self.announce(f"명령을 보낼 수 없습니다: {getattr(exc, 'detail', exc)}. 피킹 로봇 가동을 중지합니다.")
