# RFID Vision Picking

RFID 태그로 주문을 확인하고, 깊이 카메라와 YOLO로 작업대 위 상품을 찾아
두산 **E0509** 로봇팔이 상자에 담는 피킹 시스템입니다.

## 동작 흐름

태그 스캔 → 주문·상품 매칭 → 상품 위치 탐지 → 파지 → 상자에 적재 → 투입 확인 → 홈 복귀

1. Windows PC의 **RFID 관제 프로그램**이 리더기에서 읽은 태그를 로봇 PC로 보냅니다.
2. 웹 서버가 DB에서 상품을 찾아 작업을 등록합니다. 등록되지 않은 태그는 거부합니다.
3. 로봇 사이클이 RealSense 깊이(구역 기준) 또는 상품 YOLO로 물품 위치를 찾아 집습니다.
4. 그리퍼의 위치와 전류로 파지 여부를 판정합니다. 실패하면 한 번 다시 집습니다.
5. 상자에 놓은 뒤 상자 위 웹캠으로 물품이 들어갔는지 확인합니다.

## 주요 기능

| 기능 | 설명 |
|---|---|
| 원격 RFID 작업 등록 | 리더기(ACR1555U) → Windows 관제 프로그램 → 로봇 PC 작업 큐 |
| 위치 탐지 | RealSense D455f 깊이 + 4점 평면 보정, 상품 YOLO(`--vision yolo`) |
| 파지 확인·재시도 | 빈 그리퍼 판정 후 1회 재시도, 다시 실패하면 정지 후 알림 |
| 상자 투입 확인 | 상자 위 웹캠으로 확인(`--box-check`), 실패는 기록하고 계속 진행 |
| 웹 대시보드 | 작업 큐, 카메라·깊이, 재고·주문, 상품 YOLO 학습 (`:8000`) |
| 갤럭시 리모컨 | 시작·일시정지·비상정지·정지 해제, 작업대 지도, 진동 알림 |
| 음성 제어 | "정지"는 비상정지, "대기"는 일시정지, "피킹 로봇 가동"은 자동 진행 |

**관리 상품:** 물티슈 · 스팸 · 쫀득초코칩 · 복숭아녹차 340ml

## 구성

| 구분 | 사양 |
|---|---|
| 로봇 | Doosan E0509 + Robotis RH-P12-RN(A) 그리퍼 (Tool Flange RS-485) |
| 로봇 PC | Ubuntu 24.04 · ROS 2 Jazzy · Python 3.12 |
| 센서 | Intel RealSense D455f, USB 웹캠(상자 확인), ACS ACR1555U RFID 리더 |
| 기타 | Windows PC(RFID 관제), 갤럭시 폰(리모컨 앱) |

```
scripts/            실행 진입점 (start_lab.py, project_cycle.py, train_products.py)
vision_picking/     피킹 제어기, 좌표 변환, DRL 그리퍼
controller/         SafeMover(바닥·속도 검사), 제어 API (:8011)
robot_rfid/         태그 DB, 작업 큐, 오케스트레이터, 모바일 리모컨 UI
web/                웹 대시보드·음성·카메라·상품 YOLO (:8000)
windows_rfid_bridge/ Windows RFID 관제 프로그램
galaxy_app/         갤럭시 리모컨 APK
ros/                warehouse_gripper ROS 2 플러그인
config/             교시 좌표, 상품별 파지값, 보정값
```

## 빠른 시작

### 로봇 없이 (MOCK)

```bash
git clone https://github.com/vision-picking-robot/rfid-vision-picking.git robotArm_Controller_demo
cd robotArm_Controller_demo
python3.12 -m venv --system-site-packages .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/project_cycle.py --cycles 1   # 모의 피킹 사이클 1회
python scripts/start_lab.py                  # 대시보드 http://127.0.0.1:8000
python -m pytest tests robot_rfid -q
```

### 실물 로봇

순서대로 실행합니다. 처음이라면 [상세 설치·실행 절차](docs/SETUP.md)부터 따라 주세요.

```bash
# 1. 두산 드라이버
ros2 launch dsr_bringup2 dsr_bringup2_rviz.launch.py name:=dsr01 mode:=real host:=<로봇 IP> port:=12345 model:=e0509

# 2. 웹 서버 (같은 LAN의 Windows PC·폰에서 접속)
python scripts/start_lab.py --host 0.0.0.0

# 3. 대시보드에서 카메라 선택·시작 후 피킹 사이클
python scripts/project_cycle.py --mode real --confirm-real --cycles 0 \
  --api http://127.0.0.1:8000 --remote-rfid \
  --picking-config config/integration.real.json --depth-api http://127.0.0.1:8000 \
  --vision yolo --box-check
```

- `--vision yolo`: 학습된 상품 YOLO가 작업 영역 어디서든 태그의 상품을 찾는다. 빼면 구역 방식(구역 1~4 = 물티슈·스팸·쫀득초코칩·복숭아녹차)이라
  구역에 다른 물품이 있으면 그 물품을 집는다.
- `--box-check`: 상자 위 웹캠으로 물품이 상자에 들어갔는지 판정한다.
- 깊이 정보는 카메라 영상을 누군가 볼 때만 갱신된다. 대시보드를 열어 두거나 `/stream.mjpg`를 받는 프로그램을 띄워 둔다.

- Windows PC: [`windows_rfid_bridge\run_bridge.bat`](windows_rfid_bridge/README.md)
- 갤럭시 폰: APK 설치 또는 `http://<로봇 PC IP>:8000/remote` ([galaxy_app](galaxy_app/README.md))

> ⚠️ 웹캠·음성·폰 정지는 시연 보조 기능이며 인증된 안전장치가 아닙니다. **펜던트 E-Stop을 항상 손 닿는 곳에 두세요.**

## 문서

- [상세 설치·실행 절차](docs/SETUP.md): 드라이버·그리퍼 빌드, 실물 연결, 보정값 입력
- [실습실 인수인계](docs/LAB_HANDOFF.md): 최근 기능과 현장 확인 순서
- [현장 런북과 검증 한계](docs/04-runbook-and-validation.md)
- [환경](docs/01-environment-report.md) · [레거시 자산](docs/02-legacy-assets.md) · [음성·페이로드](docs/03-pipeline-and-speech.md) · [최신 검증 리포트](docs/latest-validation-review.md)
