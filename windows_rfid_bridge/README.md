# Windows RFID 브리지 (태그 UID → 로봇 PC)

ACR1555U 리더기는 Windows PC에 연결되어 태그 UID를 **키보드처럼 입력**한다.
브리지는 그 UID를 로봇 PC(Ubuntu)로 보내기만 한다. 상품·박스 매칭(DB)과 로봇 제어는 모두 로봇 PC가 한다.

```
[Windows PC] 리더기 --키보드 입력--> bridge.py --HTTP POST /api/v1/scan-event {uid}-->
[로봇 PC]   웹(8000): UID → DB(상품/박스) → 작업 큐  →  project_cycle.py --remote-rfid: 집기 → 박스 → 완료 보고
```

PC/SC 드라이버는 쓰지 않는다.

## 준비물

- Windows 10/11 PC, 로봇 PC와 **같은 네트워크**(같은 Wi-Fi 또는 같은 공유기)
- Python 3.10 이상 — https://www.python.org/downloads/ 설치 시 **"Add python.exe to PATH" 체크**
- Git — https://git-scm.com/download/win (없으면 GitHub에서 **Code → Download ZIP**)
- 태그를 찍으면 메모장에 UID가 입력되는 상태의 리더기

## 받기 (최초 1회)

```bat
cd %USERPROFILE%\Desktop
git clone https://github.com/leechanghwanspace/test.git robotArm_Controller_demo
```

업데이트는 `git pull`(ZIP이면 다시 받아 덮어쓰기). `windows_rfid_bridge\api_url.txt`와 `.venv-win`은 남겨도 된다.

## 실행 — RFID 태그 관제 프로그램

```bat
windows_rfid_bridge\run_bridge.bat
```

더블클릭해도 된다. 처음이면 `.venv-win` 가상환경을 만들고 `httpx`를 설치한 뒤, 콘솔 창 없이
**RFID 태그 관제** 프로그램(`control_panel.py`)을 연다. 갤럭시 리모컨 앱과 같은 네이비·스카이블루 다크 화면이다.

- 바탕화면 바로가기: `windows_rfid_bridge\make_shortcut.bat`을 한 번 실행하면 바탕화면에 "RFID 태그 관제" 아이콘이 생긴다.
  이후로는 아이콘만 더블클릭한다.
- 로봇 PC 주소: 프로그램 아래쪽 **로봇 PC** 칸에 입력하고 **연결**을 누른다(`api_url.txt`에 저장).
  처음 기본값은 `http://192.168.204.52:8000`.
- 화면 크기 자동 맞춤: 노트북마다 해상도·배율(125%/150%)이 달라도 창을 최대화해 열고, 글자·사진·여백을
  그 화면에 맞게 키우거나 줄인다(1280×720 ~ 4K 확인). 창 크기를 바꾸면 바로 다시 맞춘다.
  사진을 부드럽게 줄이려고 `pillow`를 함께 설치한다(없어도 동작은 한다).
- 전체 화면: `F11` (해제 `Esc`). 발표 때 쓰기 좋다.

| 화면 영역 | 내용 |
|---|---|
| 상단 | 로봇 PC 연결 상태, 로봇 사이클 상태(대기·피킹 중·일시정지·비상 정지), 시계 |
| 최근 인식 태그 | 상품 사진, 이름, UID, 목적지 박스, SKU, 분류, 가격, 입고일, 유통기한, 작업 ID·상태. 로봇이 담으면 **피킹 완료**로 바뀐다 |
| 등록 상품 | 4개 상품 사진·UID·박스. 방금 인식한 상품이 강조되고 출동 횟수가 표시된다 |
| 이벤트 로그 | 예전 콘솔 창과 같은 기록 |
| 하단 | 리더기 입력 상태, UID 직접 입력, 로봇 PC 주소 |

프로그램 창이 선택된 상태에서 태그를 찍으면 된다(아래쪽 입력칸에 커서가 있으면 그 칸에 들어가므로 창의 빈 곳을 한 번 클릭).
갤럭시 NFC·웹 대시보드 등 다른 경로로 들어온 태그도 로봇 PC에서 받아 같은 화면에 띄운다.
상품 사진은 `windows_rfid_bridge/assets/products/`에 있다(태그 UID별 파일 이름은 `control_panel.py`의 `PRODUCTS`).

### 예전 콘솔 방식

`windows_rfid_bridge\run_bridge_console.bat` — 검은 콘솔 창에 같은 내용을 글자로 표시한다(처음 실행 시 로봇 PC 주소를 묻는다).
태그를 찍으면 다음처럼 표시되고 로봇이 집으러 간다.

```
[22:45:01] 입력 UID: 0B71E55D
[22:45:01]   DB 매칭: 쫀득초코칩 (snack_pepero) -> BOX-01
[22:45:01] O 작업 등록: task=1f86a7f8 상태=READY -> 로봇이 집으러 갑니다
[22:45:01] 다음 태그를 찍어 주세요. (종료: Ctrl+C)
```

- 등록된 태그: `0B71E55D` 쫀득초코칩/BOX-01, `0B71E75D` 복숭아녹차 340ml(페트병)/BOX-02, `0B71E65D` 스팸/BOX-03,
  `0B71ED5D` 물티슈/BOX-04. 인형 태그 `0B71EC5D`는 일부러 등록하지 않았다 — 찍으면 관제 화면에
  **미등록 태그 / 등록되지 않은 태그**로 표시되고 작업은 만들어지지 않는다(시연용)
- 공백·콜론은 무시한다(`0B 71 E5 5D` = `0B71E55D`). 일부만 입력돼도(예: `E75D`) 로봇 PC가 DB에서 하나로 매칭한다.
  `0B71`처럼 여러 태그에 공통인 값만 들어오면 거부되므로 다시 찍는다.
- 3초 안에 같은 값이 반복 입력되면 한 번만 보낸다. 리더기 없이 UID를 직접 입력하고 Enter를 눌러도 된다.

| 메시지 (관제 화면 배지) | 의미 / 조치 |
|---|---|
| `X 로봇 PC 연결 실패` (상단 "로봇 PC 연결 실패") | 로봇 PC에서 `start_lab.py --host 0.0.0.0` 실행 여부, 같은 네트워크 여부, 방화벽(8000), `api_url.txt` 주소 확인 |
| `X DB 매칭 실패` / `X 등록 거부` | DB에 없는 태그. 다시 찍거나 태그를 확인한다 |
| `X ... 이미 대기/진행 중인 작업` | 같은 상품 작업이 남아 있다. 로봇 PC에서 작업을 정리한다 |

## 로봇 PC 쪽 (로봇 PC 담당자)

```bash
python scripts/start_lab.py --host 0.0.0.0     # 인증 없음: 신뢰할 수 있는 실습실 망에서만
python scripts/project_cycle.py --mode real --confirm-real --cycles 0 --api http://127.0.0.1:8000 --remote-rfid \
  --picking-config config/integration.real.json --depth-api http://127.0.0.1:8000
```

로봇 PC의 IP는 `ip -br addr`로 확인한다(Wi-Fi 인터페이스의 주소).

## 주의

- 이 브리지는 로봇을 직접 움직이지 않는다. 로봇 동작·정지는 로봇 PC와 펜던트(E-Stop)에서 한다.
- 태그를 한 번 찍을 때마다 작업이 하나 생긴다. 잘못 찍었으면 로봇 PC에서 작업을 정리한다.
- 박스 슬롯은 현재 1번만 교시되어 있어 BOX-02~04 상품도 슬롯 1에 놓인다(로봇 PC 로그에 `box_fallback`).
