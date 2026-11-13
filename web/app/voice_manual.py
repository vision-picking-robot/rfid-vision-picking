"""Voice manual for the dashboard, built from the same word lists the recognizer uses.

Changing a word in robot_voice.py or voice_commands.py changes the manual too (GET /api/voice/manual).
"""
from . import robot_voice as rv
from .voice_commands import PHRASES

# Recognizer words are stored without spaces; show the common ones the way they are said.
SPOKEN = {
    "정지해제": "정지 해제", "비상정지해제": "비상정지 해제", "정지풀어": "정지 풀어",
    "다시시작": "다시 시작", "피킹시작": "피킹 시작", "홈복귀": "홈 복귀", "홈자세": "홈 자세",
    "태그읽": "태그 읽어줘", "태그스캔": "태그 스캔", "네해줘": "네 해줘", "응해줘": "응 해줘",
    "그래해줘": "그래 해줘", "하지마": "하지 마", "안해": "안 해", "stop": "stop",
}


def spoken(words):
    return [SPOKEN.get(w, w) for w in words]


def build(robot_owned=()):
    items = [{"name": name, "words": spoken(aliases)} for aliases, _, name in rv.ITEMS]
    pick_question = rv.question(rv.Action("pick", "", "물티슈"))
    packing = {
        "query-stock": "재고 조회", "query-order": "주문 조회", "cmd-order": "예시 주문",
        "confirm-order": "주문 확정", "discard-order": "주문 취소", "end": "대화 끝내기",
    }
    return {
        "start": [
            "박수를 두 번 치면 \"음성 인식을 시작합니다\" 안내 후 듣기 시작합니다 ([음성 명령 켜기]를 먼저 누름).",
            "[바로 듣기]를 누르면 박수 없이 바로 듣습니다.",
            "\"대화 종료\"라고 하면 다시 박수 대기로 돌아갑니다.",
        ],
        "match_note": "로봇 명령은 띄어쓰기와 상관없이 아래 단어가 문장 안에 들어 있으면 인식합니다. "
                      "위쪽 표가 먼저 적용됩니다 (예: '일시정지'는 '정지'보다 먼저 일시정지로 인식).",
        "immediate": [
            {"title": "비상 정지", "words": spoken(rv.STOP), "effect": "로봇이 즉시 멈춥니다 (move_stop).",
             "tone": "danger"},
            {"title": "일시정지", "words": spoken(rv.PAUSE) + ["(\"잠깐\"·\"잠시\"가 들어간 말 전부)"],
             "effect": "진행 중인 한 동작을 마치고 다음 동작 전에 멈춥니다. \"재개\"로 이어서 진행.", "tone": "warn"},
            {"title": "비상 정지 해제", "words": spoken(rv.STOP_RESET), "effect": rv.QUESTION["reset_stop"],
             "tone": "ask"},
        ],
        "asked": [
            {"title": "물건 집기", "words": [f"{i['name']}: " + ", ".join(i["words"]) for i in items],
             "example": "\"물티슈 집어줘\", \"초코칩 가져와\", \"음료수 옮겨줘\"", "question": pick_question},
            {"title": "태그 읽기", "words": spoken(rv.SCAN), "question": rv.QUESTION["scan_dispatch"]},
            {"title": "작업 재개", "words": ["시작 (단독)"] + spoken(rv.RESUME), "question": rv.QUESTION["resume"]},
            {"title": "홈 자세로", "words": spoken(rv.HOME), "question": rv.QUESTION["home"]},
            {"title": "물건 없이 '집어'", "words": spoken(rv.PICK_VERBS),
             "question": "어떤 물건을 집을까요? 물티슈, 스팸, 쫀득초코칩, 복숭아녹차 중에서 말씀해 주세요."},
            {"title": "지금 상태", "words": spoken(rv.STATUS), "question": "(바로 대답) 로봇 연결·정지 상태, 현재 작업, 최근 태그"},
        ],
        "answers": {"yes": spoken(rv.YES), "no": spoken(rv.NO) + ["(\"아니\"로 시작하는 말)"]},
        "auto": {
            "steps": [
                {"say": "피킹 로봇 가동", "words": spoken(rv.AUTO_START),
                 "effect": "상자 4개를 차례로 처리합니다 (태그 읽기 → 집기 → 상자에 넣기)."},
                {"say": "상자 교환 완료", "words": spoken(rv.AUTO_SWAP), "effect": "새 상자로 바꾼 뒤 다음 상자를 진행합니다."},
                {"say": "작업 재개", "words": spoken(rv.AUTO_RESUME), "effect": "정지·일시정지 뒤 같은 상자부터 이어서 진행합니다."},
                {"say": "가동 중지", "words": spoken(rv.AUTO_END), "effect": "자동 진행을 끝냅니다."},
            ],
            "notes": [
                f"로봇이 움직이는 동안에는 정지·일시정지(와 일시정지 뒤 재개) 말만 듣고 나머지는 무시합니다.",
                f"안내 방송이 끝난 뒤 {rv.HOLDOFF_S:.0f}초 동안은 상자·재개 말을 무시합니다 (스피커 소리 오인식 방지).",
            ],
            "announcements": [
                "피킹 로봇을 시작합니다. 첫 번째 박스부터 진행합니다.",
                "○○ 태그를 인식했습니다. 피킹을 시작합니다.",
                "○○을/를 넣었습니다. 새 박스로 바꾼 뒤 알려 주세요.",
                "정지했습니다. 준비되면 말씀해 주세요. → 다시 진행합니다.",
                f"{rv.ORDINAL.get(rv.AUTO_ROUNDS)} 박스까지 모두 마쳤습니다. 피킹 로봇 가동을 중지합니다.",
            ],
        },
        "packing": [{"title": packing[intent], "phrases": list(phrases)}
                    for intent, phrases in PHRASES.items() if intent in packing and intent not in robot_owned],
        "packing_note": "패킹 데모 문장은 문장 전체가 같아야 인식합니다. 재고·주문 조회는 앞에 '응', '네', '어'를 붙여도 됩니다.",
        "cautions": [
            "\"정지\"·\"스톱\"은 비상 정지입니다. 잠시 멈추려면 \"잠깐\"이나 \"대기\"라고 말하세요.",
            "\"홈\"·\"스캔\"·\"초코\"처럼 짧은 단어는 문장 안에 있기만 해도 인식됩니다.",
            "음성 명령은 시연 보조 기능입니다. 펜던트 E-Stop을 항상 가까이 두세요.",
        ],
    }
