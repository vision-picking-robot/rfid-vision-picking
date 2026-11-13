"""Demo catalog for the packing station: team members, warehouse products and past orders.

Everything is generated once from a fixed seed, so it looks random but stays the same across restarts
and on every PC. The four presentation items (the ones with RFID tags) always come first.
"""
import random

# Team members and their team numbers (random-looking, fixed). Order #123 belongs to the first one.
TEAM = (
    ("김나은", "TM-26-0417"),
    ("김병용", "TM-26-1283"),
    ("김원준", "TM-26-0756"),
    ("주만기", "TM-26-1932"),
    ("이창환", "TM-26-0548"),
)
REMOVED_PEOPLE = ("홍길동", "김서연")  # earlier sample customers

# RFID tag -> packing SKU for the presentation items (robot_rfid.database SEEDS)
TAG_SKUS = {"0B71E55D": "PK-001", "0B71E75D": "PK-002", "0B71E65D": "PK-003", "0B71ED5D": "PK-004"}
PRESENTATION_SKUS = tuple(TAG_SKUS.values())

# Warehouse location of the seeded items (PK-001..PK-005)
SEED_BINS = {"PK-001": "A동 01열 1단", "PK-002": "B동 01열 2단", "PK-003": "A동 02열 3단",
             "PK-004": "C동 01열 1단", "PK-005": "D동 07열 2단"}

_FILLER = {  # zone: (building, items)
    "과자": ("A동", ("새우깡", "꼬깔콘 고소한맛", "포카칩 오리지널", "허니버터칩", "바나나킥", "초코파이 12입",
                   "몽쉘 크림케이크", "오징어땅콩", "칸쵸", "홈런볼 초코", "빈츠", "에이스 크래커", "마가렛트",
                   "카스타드", "고래밥", "썬칩", "프링글스 오리지널", "꿀꽈배기", "맛동산", "버터링")),
    "음료": ("B동", ("생수 2L", "생수 500ml 20입", "콜라 355ml 캔", "사이다 500ml", "이온음료 620ml",
                   "스포츠음료 600ml", "아이스티 복숭아 1.5L", "비타민음료 100ml", "에너지드링크 250ml",
                   "옥수수수염차 500ml", "헛개차 500ml", "우유 1L", "바나나우유 240ml", "두유 190ml 16입",
                   "캔커피 175ml", "아메리카노 500ml", "오렌지주스 1.5L", "탄산수 레몬 500ml",
                   "녹차 티백 50입", "보리차 티백 30입")),
    "식품": ("A동", ("라면 5입", "매운 라면 5입", "짜장 라면 5입", "우동 라면 5입", "컵라면 6입",
                   "즉석밥 210g 12입", "3분 카레 순한맛", "3분 짜장", "참치캔 150g 3입", "꽁치 통조림 400g",
                   "옥수수 통조림 340g", "고추장 500g", "된장 500g", "간장 930ml", "식용유 1.8L", "설탕 1kg",
                   "소금 500g", "밀가루 1kg", "도시락김 16봉", "즉석 미역국")),
    "생활용품": ("C동", ("키친타올 4롤", "화장지 30롤", "손소독제 500ml", "주방세제 1L", "세탁세제 3L",
                     "섬유유연제 2.5L", "고무장갑 중형", "지퍼백 대형 30매", "위생장갑 200매",
                     "종량제 봉투 20L 10매", "칫솔 4입", "치약 120g 3입", "샴푸 750ml", "바디워시 900ml",
                     "면봉 300개입", "마스크 KF94 50매", "일회용 수저 100세트", "알루미늄 호일", "랩 30cm",
                     "건전지 AA 10입")),
    "물류 소모품": ("D동", ("택배 박스 1호 10매", "택배 박스 3호 10매", "박스 테이프 6롤", "에어캡 50m",
                        "송장 라벨지 100매", "바코드 라벨 롤", "케이블 타이 200개", "스트레치 필름 500mm",
                        "유성 매직 12색", "A4 복사용지 500매", "볼펜 흑색 12입", "포스트잇 76x76",
                        "스테이플러 심 1000개", "커터칼 대형", "목장갑 10켤레", "안전화 깔창",
                        "정전기 방지 장갑", "RFID 태그 스티커 100매", "실리카겔 100입", "파렛트 커버")),
}


def _catalog():
    rng = random.Random(2026)
    products, used = [], set(SEED_BINS.values())
    number = 6
    for zone, (building, names) in _FILLER.items():
        for name in names:
            while True:
                location = f"{building} {rng.randint(1, 12):02d}열 {rng.randint(1, 4)}단"
                if location not in used:
                    used.add(location)
                    break
            stock = 0 if rng.random() < 0.06 else rng.randint(4, 240)
            products.append({"sku": f"PK-{number:03d}", "name": name, "unit": "개", "stock": stock,
                             "alias": zone, "bin": location})
            number += 1
    return tuple(products)


CATALOG = _catalog()  # 100 products, PK-006 .. PK-105

_STATES = ("delivered",) * 9 + ("shipped",) * 6 + ("awaiting_dispatch",) * 4 + ("received",) * 3


def _orders():
    rng = random.Random(123)
    skus = list(PRESENTATION_SKUS) * 3 + [p["sku"] for p in CATALOG]
    orders = []
    for number, state in zip(range(101, 101 + len(_STATES)), _STATES):
        picked = rng.sample(skus, rng.randint(1, 4))
        items = list(dict.fromkeys(picked))  # one line per product
        orders.append({"number": number, "customer": rng.choice(TEAM)[0], "state": state,
                       "items": [{"id": f"{number}-{i}", "sku": sku, "done": state != "received"}
                                 for i, sku in enumerate(items, 1)]})
    return tuple(orders)


SAMPLE_ORDERS = _orders()  # #101 .. #122 (past orders; #123 is the live demo order, #124 the voice example)
