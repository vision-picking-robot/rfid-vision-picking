# 실습실 현장 실행 가이드 & AI 프롬프트북 (바둑판 그리드 비전 피킹)

**문서 버전:** 1.0.0  
**최종 갱신일:** 2026-11-11  
**대상 환경:** Ubuntu 24.04 (ROS 2 Jazzy, Python 3.12) / Windows 10·11 (RFID Bridge)  
**핵심 장비:** Doosan E0509, ROBOTIS RH-P12-RN(A), Intel RealSense D455f, ACS ACR1555U RFID

---

## 📋 목차
1. [시스템 아키텍처 & 동작 시나리오](#1-시스템-아키텍처--동작-시나리오)
2. [사전 준비 & 하드웨어 체크리스트](#2-사전-준비--하드웨어-체크리스트)
3. [단계별 현장 실행 절차 (Runbook)](#3-단계별-현장-실행-절차-runbook)
4. [노트북 AI 지시용 복사-붙여넣기 프롬프트북](#4-노트북-ai-지시용-복사-붙여넣기-프롬프트북)
5. [현장 긴급 트러블슈팅](#5-현장-긴급-트러블슈팅)
6. [[로드맵] 갤럭시 전용 리모트 컨트롤러 앱 기획](#6-로드맵-갤럭시-전용-리모트-컨트롤러-앱-기획)

---

## 1. 시스템 아키텍처 & 동작 시나리오

### 💡 파이프라인 흐름도
```
[1. 작업대 4점 정의] ───> 카메라 영상 내 사각형 ROI 생성 & N×M 바둑판 그리드 셀 분할
                                         │
[2. RFID 상자 태깅]  ───> ACR1555U 스캔 ➔ "빼빼로" 품목 판정 및 작업 큐 등록
                                         │
[3. 물품 셀 탐색]    ───> 바둑판 셀 중 빼빼로가 위치한 셀 번호(Row, Col) 및 대략 중심(X, Y) 도출
                                         │
[4. 1단계 상공 접근]  ───> 로봇 암이 해당 그리드 셀 상공(Z = 250~300mm)으로 고속 안전 이동
                                         │
[5. 2단계 실시간 보정]───> RealSense D455f Depth 센서로 물체 표면 Z 높이 및 중심 미세 오차(ΔX, ΔY) 측정
                                         │
[6. 정밀 안전 파지]  ───> 과자 찌그러짐 방지 높이까지 하강 ➔ 전류(65mA) 피드백 기반 부드러운 파지
                                         │
[7. 박스 적재 및 복귀]───> 지정 박스 슬롯으로 이동하여 적재 ➔ 홈 복귀 ➔ 작업 완료 보고
```

---

## 2. 사전 준비 & 하드웨어 체크리스트

### ⚠️ 필수 안전 수칙
- [ ] **티칭 펜던트 E-Stop(비상정지 버튼)**을 항상 손 닿는 곳에 비치
- [ ] 실물 구동 전 주변 작업 반경(반경 1m 이내) 사람 및 장애물 완전 제거
- [ ] 노트북 유선 랜 연결 시 **USB 허브를 거치지 않고 노트북 본체 포트에 직결** (USB 허브 경유 시 통신 리셋 결함 발생 방지)

### 🔌 하드웨어 물리 세팅
1. **RealSense D455f 카메라 거치**:
   - 작업대 바닥면으로부터 **최소 50cm ~ 70cm 높이**에 수직(Top-down) 또는 60~75도 각도로 단단히 고정.
   - *주의: D455는 40cm 이하에서는 깊이 측정 음영(블랙아웃)이 발생하므로 반드시 50cm 이상 이격.*
2. **노트북 유선 랜 IP 설정**:
   - IP 주소: `110.120.1.11`
   - 서브넷 마스크: `255.255.255.0`
   - 게이트웨이: 비워둠
3. **두산 로봇 제어기 통신**:
   - 로봇 IP: 펜던트 화면에서 확인 (`110.120.1.56` ~ `110.120.1.63` 중 1개)
   - 포트: DRFL `12345`

---

## 3. 단계별 현장 실행 절차 (Runbook)

### [Phase 1] 네트워크 점검 및 MOCK 무결성 확인
1. 로봇 핑 테스트:
   ```bash
   ping -c 3 110.120.1.56
   ```
2. MOCK 모드로 소프트웨어 파이프라인 정상 여부 1차 검증:
   ```bash
   cd ~/vision_lab/robotArm_Controller_demo
   source .venv/bin/activate
   export MOCK_MODE=true
   python mock_demo.py
   python scripts/test_gripper.py --mode mock --action status
   ```

### [Phase 2] RealSense 카메라 4점 영역(ROI) 및 깊이(Depth) 측정 확인
1. RealSense 연결 및 스트리밍 확인:
   ```bash
   python camera_depth/realsense_viewer.py
   ```
2. 작업대 바닥 4점 코너 좌표 확인:
   - 좌상(Top-Left), 우상(Top-Right), 우하(Bottom-Right), 좌하(Bottom-Left)의 픽셀 좌표 `(u, v)` 및 로봇 베이스 좌표 `(X, Y, Z)` 티칭.
3. 물체 높이 실측 도구 실행:
   ```bash
   python camera_depth/realsense_measure_height.py
   ```
   - 마우스로 바닥과 빼빼로 상단을 클릭하여 실제 수직 높이(Z)가 약 15~25mm로 측정되는지 검증.

### [Phase 3] 두산 로봇 실물 연결 & TCP 오프셋 보정 (⚠️ 핵심)
1. **두산 펜던트 설정**:
   - 그리퍼(RH-P12-RN) 장착 시 손끝까지의 오프셋(약 Z +120mm)이 Tool에 등록되어 있는지 확인하고 활성화.
2. ROS 2 드라이버 실행:
   ```bash
   source /opt/ros/jazzy/setup.bash
   source ~/ros2_ws/install/setup.bash
   export ROBOT_IP=110.120.1.56 # 확인된 IP
   ros2 launch dsr_bringup2 dsr_bringup2_rviz.launch.py name:=dsr01 mode:=real host:="$ROBOT_IP" port:=12345 model:=e0509
   ```
3. 그리퍼 플러그인 로드 및 단독 테스트:
   ```bash
   ros2 launch warehouse_gripper gripper.launch.py
   # 다른 터미널에서
   python scripts/test_gripper.py --mode real --namespace dsr01 --action status
   ```

### [Phase 4] RFID 리더기 연동 (Windows PC 또는 로컬)
1. ACR1555U 리더기 절전 해제:
   ```bash
   python -m robot_rfid.rfid_power --no-sleep
   ```
2. Windows 블루투스 브리지 사용 시:
   ```bat
   windows_rfid_bridge\4_run_bridge.bat
   ```

### [Phase 5] 통합 대시보드 및 실물 피킹 사이클 가동
1. 웹 대시보드 기동:
   ```bash
   python scripts/start_lab.py --host 0.0.0.0
   ```
2. 실물 프로젝트 사이클 대기 모드 실행:
   ```bash
   python scripts/project_cycle.py --mode real --confirm-real --cycles 0 --api http://127.0.0.1:8000 --remote-rfid
   ```

---

## 4. 노트북 AI 지시용 복사-붙여넣기 프롬프트북

실습실에서 노트북의 Antigravity 또는 AI 어시스턴트에게 **아래 프롬프트 블록을 순서대로 복사해서 붙여넣으시면 막힘없이 코딩 및 실행 지원을 받을 수 있습니다.**

---

### 💬 프롬프트 1: [시작 시] 환경 점검 및 실습 모드 전환
```text
지금 두산 E0509 실습실에 도착했습니다. 
현재 레포(robotArm_RFID_demo)의 상태를 점검하고, 로봇 제어기 IP(예: 110.120.1.56)와의 핑 상태를 확인해 주세요. 
그리퍼 단독 진단(test_gripper.py) 및 start_lab.py를 띄워 기본 웹 UI와 MOCK 상태가 정상인지 함께 점검해 주세요.
```

---

### 💬 프롬프트 2: [기능 구현] 4점 바둑판 그리드(Grid) 분할 모듈 작성
```text
현재 vision_picking/pick_plane.py의 PickPlane(호모그래피 4점 보정) 클래스를 확장해 주세요.
작업대 4개 모서리(TL, TR, BR, BL)로 지정된 영역을 N x M (예: 4 x 4) 바둑판 격자로 나누고,
1. 특정 픽셀 (u, v) 또는 물체 바운딩 박스가 주어졌을 때 어느 그리드 셀(row, col)에 위치하는지 반환하는 함수,
2. 해당 그리드 셀의 중심 로봇 Base (X, Y) 좌표를 산출하는 함수를 추가해 주세요.
관련 단위 테스트도 함께 작성해 주세요.
```

---

### 💬 프롬프트 3: [기능 구현] 2단계 보정(상공 이동 ➔ Depth 기반 Z높이 보정) 연동
```text
scripts/project_cycle.py의 피킹 모션을 2단계(Coarse-to-Fine) 방식으로 개작해 주세요.
1단계: 바둑판 그리드 셀의 로봇 좌표 상공 (Z = 250mm)으로 먼저 접근(MoveL/MoveJ)
2단계: RealSense D455f의 실제 깊이값(Z_depth)을 읽어와 물체의 실측 표면 높이를 반영한 뒤, 
과자가 찌그러지지 않는 안전 파지 높이(Z_grasp = Z_surface - offset)로 정밀 하강하도록 만들어 주세요.
Z축 하한 안전값(SafeMover z_min) 검증도 철저히 유지해 주세요.
```

---

### 💬 프롬프트 4: [실측값 반영] 현장 티칭 4점 좌표 및 상품별 파지값 저장
```text
방금 실습실 펜던트와 카메라로 작업대 4점 좌표와 빼빼로 파지값을 측정했습니다.
아래 실측값을 config/hardware.local.json 및 config/products.yaml에 정확히 반영하고 verified 플래그를 true로 변경해 주세요.

[실측 데이터]
- 카메라 코너 (u, v) ↔ 로봇 베이스 (X, Y, Z):
  * TL: (px_u, px_v) ➔ (X, Y, Z)
  * TR: (px_u, px_v) ➔ (X, Y, Z)
  * BR: (px_u, px_v) ➔ (X, Y, Z)
  * BL: (px_u, px_v) ➔ (X, Y, Z)
- 빼빼로 실측 파지 펄스: min_pulse=xxx, max_pulse=yyy, target_current=65mA
- 빼빼로 바닥 기준 파지 높이: grasp_height_mm=xx
```

---

### 💬 프롬프트 5: [실물 테스트] 전체 E2E 시나리오 1회 실물 검증
```text
이제 실물 로봇과 그리퍼, RFID 리더기(또는 브리지)가 모두 준비되었습니다.
안전을 최우선으로 하여,
1. 비상정지 대기 상태 및 SafeMover 파라미터를 점검하고,
2. RFID 빼빼로 태그 인식 ➔ 바둑판 셀 인식 ➔ 1단계 상공 이동 ➔ 2단계 Depth 보정 하강 ➔ 전류 기반 파지 ➔ 박스 슬롯 1 적재까지의 실물 사이클을 1회 실행(project_cycle.py --mode real --confirm-real --cycles 1)하는 과정을 모니터링하고 가이드해 주세요.
```

---

## 5. 현장 긴급 트러블슈팅

| 현상 | 원인 | 조치 방법 |
|---|---|---|
| **`ping` 실패 (Request timed out)** | 유선 LAN IP 미설정 or 케이블 불량 | 노트북 IPv4를 `110.120.1.11 / 255.255.255.0`으로 재확인, USB 이더넷 어댑터 노트북 직결 |
| **`AUTHORITY: MONITORING_ACCESS_CONTROL_DENY`** | ROS 드라이버 중복 기동 or 티칭 펜던트 권한 미승인 | 기존 터미널 프로세스 종료 확인, 펜던트에서 [제어권 승인/알람 해제] 터치 |
| **로봇이 바닥으로 120mm 더 깊게 내려감** | 펜던트에 그리퍼 손끝 TCP가 미설정됨 | 즉시 E-Stop 누름 ➔ 펜던트에서 Tool 설정(오프셋 Z +120mm)을 기본 TCP로 활성화 |
| **RealSense 깊이 영상에 구멍(검은색) 발생** | 카메라 설치 높이가 40cm 이하로 너무 가까움 | 카메라 거치대를 위로 올려 바닥과의 거리를 50~70cm로 확보 |
| **그리퍼가 닫히지 않고 타임아웃 발생** | DRFL 플러그인 직결 통신 충돌 | `drl_gripper.py`를 사용하는 컨트롤러 DRL 모드로 자동 전환되었는지 확인 |
| **RFID 리더기가 태그를 읽지 않음** | 리더기 자체 절전 모드 진입 | `python -m robot_rfid.rfid_power --no-sleep` 실행하여 절전 해제(0x04) 확인 |

---

## 6. 갤럭시 전용 리모트 컨트롤러 앱 & 15×15 그리드 API (구현 완료)

### 🎯 핵심 운용 원칙
- **주력 시연 (Priority 1)**: 전용 하드웨어 RFID 리더기(`ACR1555U` / 로봇팔 라벨 스캔) 우선 시연 (`scan_mode = "external_reader"`).
- **갤럭시 앱의 기본 역할**: 현장 작업자를 위한 **무선 원격 조작반(HMI) + 15×15 바둑판 모니터링 + 상자 배치/완료 햅틱 알림**.
- **스마트폰 자체 NFC 태깅**: 앱 내 보조 옵션(토글 스위치 `scan_mode = "phone_nfc"`)으로 내장되어, 기본은 비활성화 상태로 두고 **보조 시연 시에만 켜서 가동**.

### 🔌 구현 완료된 핵심 모듈 & 엔드포인트
1. **15×15 바둑판 그리드 & 과자 찌그러짐 방지 높이 변환 (`vision_picking/pick_plane.py`)**:
   - `PickPlane.grid_cell(pixel, rows=15, cols=15)`: 225개 정밀 셀 중 `(row, col)` 식별, 셀 중심 BASE 좌표(`cell_center_base_mm`) 및 미세 오차(`fine_offset_mm`) 산출.
   - `compute_safe_grasp_z(...)`: RealSense 실측 높이 또는 상품 규격 기반 과자 찌그러짐 방지 및 헛손질 방지 하강 Z 높이 산출.
2. **2단계(Coarse-to-Fine) 그리드 피킹 (`vision_picking/controller.py` & `scripts/project_cycle.py`)**:
   - `POST /api/v1/grid-plan`, `POST /api/v1/grid-pick`: `home` ➔ `grid_coarse_approach`(15×15 셀 중심 상공) ➔ `fine_align_approach`(ΔX, ΔY 미세 정렬) ➔ `pick`(안전 Z 하강) ➔ `place`.
   - `python scripts/project_cycle.py --pixel u,v --measured-height 135.0`: CLI에서 즉시 15×15 그리드 2단계 접근 및 실측 높이 피킹 실행.
3. **모바일 리모트 컨트롤러 & 그리드 API (`robot_rfid/api_server.py`)**:
   - `GET /remote`: 갤럭시 모바일 리모트 컨트롤러 UI (WebSocket 실시간 연동 & 햅틱 진동).
   - `GET /api/v1/mobile/status`: 현재 스캔 모드, 로봇 상태, 배치된 상자, 활성 그리드 셀 조회.
   - `POST /api/v1/mobile/scan-mode`: `external_reader`(기본) ↔ `phone_nfc`(보조) 전환.
   - `POST /api/v1/mobile/box-placed`: 1~4번 상자 배치 완료 알림 및 로봇팔 리더기 스캔 출동 트리거.
   - `POST /api/v1/mobile/nfc-tag`: 보조 모드(`phone_nfc`) 활성화 시에만 갤럭시 뒷면 NFC 태깅 허용.
   - `POST /api/v1/mobile/control`: `start`, `pause`, `resume`, `home`, `scan_dispatch`, `emergency_stop`, `reset_stop`.
   - `GET /api/v1/grid/config`, `POST /api/v1/grid/locate`: 15×15 바둑판 그리드 맵 및 셀 좌표/궤적 즉시 계산.
4. **갤럭시 안드로이드 네이티브 프로젝트 (`galaxy_app/`)**:
   - `galaxy_app/app/src/main/java/com/visionlab/galaxyremote/MainActivity.kt`: 삼성 갤럭시 NFC 리더(`NfcAdapter`) 및 진동(`Vibrator`) 네이티브 브리지 내장.
   - `.github/workflows/build-galaxy-apk.yml`: GitHub Actions에서 자동으로 `galaxy-e0509-remote-apk` 빌드 및 아티팩트 업로드.


