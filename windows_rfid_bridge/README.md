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

## 실행 — 배치 파일 하나

```bat
windows_rfid_bridge\run_bridge.bat
```

더블클릭해도 된다. 이 파일 하나가 다음을 순서대로 한다.

1. 처음이면 `.venv-win` 가상환경을 만들고 `httpx`를 설치한다.
2. 처음이면 로봇 PC 주소를 묻는다. 예: `http://192.168.204.52:8000`
   (저장 위치 `windows_rfid_bridge\api_url.txt`, 바꾸려면 파일을 지우고 다시 실행)
3. 로봇 PC 연결을 확인한 뒤, 창에 입력되는 UID를 로봇 PC로 보낸다.

창을 클릭해 둔 상태에서 태그를 찍으면 다음처럼 표시되고 로봇이 집으러 간다.

```
[22:45:01] 입력 UID: 0B71E55D
[22:45:01]   DB 매칭: 쫀득초코칩 (snack_pepero) -> BOX-01
[22:45:01] O 작업 등록: task=1f86a7f8 상태=READY -> 로봇이 집으러 갑니다
[22:45:01] 다음 태그를 찍어 주세요. (종료: Ctrl+C)
```

- 등록된 태그: `0B71E55D` 쫀득초코칩/BOX-01, `0B71E75D` 복숭아녹차 340ml(페트병)/BOX-02, `0B71E65D` 스팸/BOX-03,
  `0B71ED5D` 물티슈/BOX-04 (인형은 태그 없음)
- 공백·콜론은 무시한다(`0B 71 E5 5D` = `0B71E55D`). 일부만 입력돼도(예: `E75D`) 로봇 PC가 DB에서 하나로 매칭한다.
  `0B71`처럼 여러 태그에 공통인 값만 들어오면 거부되므로 다시 찍는다.
- 3초 안에 같은 값이 반복 입력되면 한 번만 보낸다. 리더기 없이 UID를 직접 입력하고 Enter를 눌러도 된다.

| 메시지 | 의미 / 조치 |
|---|---|
| `X 로봇 PC 연결 실패` | 로봇 PC에서 `start_lab.py --host 0.0.0.0` 실행 여부, 같은 네트워크 여부, 방화벽(8000), `api_url.txt` 주소 확인 |
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
