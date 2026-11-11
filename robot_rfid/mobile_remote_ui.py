"""Samsung Galaxy Remote Controller UI & PWA manifest for E0509 Vision Picking."""

MANIFEST_JSON = {
    "name": "E0509 갤럭시 로봇 리모컨",
    "short_name": "E0509 리모컨",
    "start_url": "/remote",
    "display": "standalone",
    "background_color": "#0b1120",
    "theme_color": "#1e293b",
    "orientation": "portrait",
}

MOBILE_REMOTE_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#0f172a">
<link rel="manifest" href="/remote/manifest.json">
<title>E0509 갤럭시 리모트 컨트롤러</title>
<style>
  :root {
    --bg: #0b1120;
    --card: #162032;
    --border: #28354a;
    --text: #f8fafc;
    --sub: #94a3b8;
    --accent: #38bdf8;
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --purple: #a855f7;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Malgun Gothic", sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 12px;
    max-width: 520px;
    margin: 0 auto;
    padding-bottom: 40px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 14px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    margin-bottom: 12px;
  }
  .title-wrap h1 { font-size: 1.05rem; font-weight: 700; letter-spacing: -0.3px; }
  .title-wrap p { font-size: 0.75rem; color: var(--sub); margin-top: 2px; }
  .badge {
    padding: 5px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    background: rgba(34, 197, 94, 0.18);
    color: var(--green);
    border: 1px solid rgba(34, 197, 94, 0.4);
  }
  .badge.warn { background: rgba(245, 158, 11, 0.18); color: var(--amber); border-color: rgba(245, 158, 11, 0.4); }
  .badge.danger { background: rgba(239, 68, 68, 0.2); color: var(--red); border-color: rgba(239, 68, 68, 0.5); }
  .section {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px;
    margin-bottom: 12px;
  }
  .section-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .mode-switch {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    background: #0f172a;
    padding: 5px;
    border-radius: 10px;
    border: 1px solid var(--border);
  }
  .mode-btn {
    border: none;
    background: transparent;
    color: var(--sub);
    padding: 10px 8px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;
  }
  .mode-btn.active {
    background: var(--accent);
    color: #090d16;
  }
  .box-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .btn {
    border: 1px solid var(--border);
    background: #1e293b;
    color: var(--text);
    padding: 12px 10px;
    border-radius: 10px;
    font-size: 0.85rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    transition: transform 0.08s, background 0.15s;
  }
  .btn:active { transform: scale(0.97); }
  .btn .sub-txt { font-size: 0.7rem; color: var(--sub); font-weight: 500; }
  .btn.primary { background: rgba(56, 189, 248, 0.16); border-color: var(--accent); color: #e0f2fe; }
  .btn.success { background: rgba(34, 197, 94, 0.18); border-color: var(--green); }
  .btn.amber { background: rgba(245, 158, 11, 0.18); border-color: var(--amber); }
  .btn.danger { background: rgba(239, 68, 68, 0.25); border-color: var(--red); color: #fecaca; }
  .control-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .estop-btn {
    grid-column: span 2;
    padding: 14px;
    font-size: 0.95rem;
    background: #dc2626;
    border-color: #f87171;
    color: #fff;
  }
  .board-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
  .grid-board {
    display: grid;
    grid-template-columns: repeat(15, 1fr);
    gap: 2px;
    width: 100%;
    aspect-ratio: 4 / 3;
    background: #090d16;
    padding: 4px;
    border-radius: 8px;
    border: 1px solid var(--border);
  }
  .grid-cell {
    background: #1e293b;
    border-radius: 2px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .grid-cell.active {
    background: var(--green);
    box-shadow: 0 0 8px var(--green);
  }
  .info-bar {
    width: 100%;
    font-size: 0.76rem;
    color: var(--sub);
    background: #0f172a;
    padding: 8px 10px;
    border-radius: 8px;
    line-height: 1.45;
  }
  .toast {
    display: none;
    background: rgba(34, 197, 94, 0.2);
    border: 1px solid var(--green);
    color: #dcfce7;
    padding: 12px;
    border-radius: 12px;
    margin-bottom: 12px;
    font-size: 0.85rem;
    font-weight: 700;
    text-align: center;
  }
  .nfc-panel {
    display: none;
    margin-top: 10px;
    padding: 10px;
    border-radius: 10px;
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid var(--purple);
  }
</style>
</head>
<body>
  <header>
    <div class="title-wrap">
      <h1>🤖 E0509 갤럭시 리모트 컨트롤러</h1>
      <p id="conn-text">실시간 WebSocket 연결 중...</p>
    </div>
    <span id="state-badge" class="badge">STANDBY</span>
  </header>

  <div id="complete-toast" class="toast"></div>

  <section class="section">
    <div class="section-title">
      <span>1. RFID 스캔 운용 모드 (우선순위 제어)</span>
      <span id="mode-indicator" style="font-size:0.72rem;color:var(--sub);">리더기 우선</span>
    </div>
    <div class="mode-switch">
      <button id="btn-mode-ext" class="mode-btn active" onclick="setScanMode('external_reader')">
        📡 전용 리더기 모드 (기본)
      </button>
      <button id="btn-mode-nfc" class="mode-btn" onclick="setScanMode('phone_nfc')">
        📱 핸드폰 NFC 태깅 (보조)
      </button>
    </div>
    <div id="nfc-subpanel" class="nfc-panel">
      <div style="font-size:0.78rem;margin-bottom:8px;color:#e9d5ff;">
        📱 <b>보조 모드 활성화됨:</b> 갤럭시 뒷면을 상자 태그에 접촉하거나 아래 태그 전송을 누르세요.
      </div>
      <div class="box-grid">
        <button class="btn primary" onclick="sendPhoneNfc('0B71E55D', 1)">
          🏷️ 빼빼로 NFC 전송
          <span class="sub-txt">0B71E55D · BOX-01</span>
        </button>
        <button class="btn primary" onclick="startNativeNfcScan()">
          📲 갤럭시 뒷면 태그 읽기
          <span class="sub-txt">Android NFC 리더</span>
        </button>
      </div>
    </div>
  </section>

  <section class="section">
    <div class="section-title">
      <span>2. 상자 배치 알림 (사람 배치 ➔ 로봇팔 리더기 출동)</span>
    </div>
    <div class="box-grid">
      <button class="btn primary" onclick="notifyBoxPlaced(1, '0B71E55D')">
        📦 1번 상자 배치 완료
        <span class="sub-txt">빼빼로 (0B71E55D)</span>
      </button>
      <button class="btn primary" onclick="notifyBoxPlaced(2, '0B71E75D')">
        📦 2번 상자 배치 완료
        <span class="sub-txt">제로콜라 (0B71E75D)</span>
      </button>
      <button class="btn primary" onclick="notifyBoxPlaced(3, '0B71E65D')">
        📦 3번 상자 배치 완료
        <span class="sub-txt">스팸 (0B71E65D)</span>
      </button>
      <button class="btn primary" onclick="notifyBoxPlaced(4, '0B71ED5D')">
        📦 4번 상자 배치 완료
        <span class="sub-txt">물티슈 (0B71ED5D)</span>
      </button>
    </div>
  </section>

  <section class="section">
    <div class="section-title">
      <span>3. 15×15 바둑판 그리드 좌표 변환 & 2단계 보정</span>
      <span id="cell-label" style="color:var(--green);">셀 터치 시 시뮬레이션</span>
    </div>
    <div class="board-wrap">
      <div id="grid-board" class="grid-board"></div>
      <div id="grid-info" class="info-bar">
        15×15 바둑판 셀(총 225칸) 중 물품이 탐지된 칸으로 1차 상공 접근 후, 중심 오차(ΔX, ΔY) 및 과자 보호 높이(Z)로 2단계 정밀 피킹합니다.
      </div>
    </div>
  </section>

  <section class="section">
    <div class="section-title">
      <span>4. 로봇팔 원격 조작반 (Remote HMI)</span>
    </div>
    <div class="control-grid">
      <button class="btn success" onclick="sendControl('resume')">▶ 작업 시작 / 재개</button>
      <button class="btn amber" onclick="sendControl('pause')">⏸ 일시정지</button>
      <button class="btn" onclick="sendControl('scan_dispatch')">📡 리더기 스캔 출동</button>
      <button class="btn" onclick="sendControl('home')">🏠 홈 자세 복귀</button>
      <button class="btn danger estop-btn" onclick="sendControl('emergency_stop')">■ 비상 정지 (E-STOP)</button>
    </div>
  </section>

<script>
  const board = document.getElementById('grid-board');
  for (let r = 0; r < 15; r++) {
    for (let c = 0; c < 15; c++) {
      const cell = document.createElement('div');
      cell.className = 'grid-cell';
      cell.id = `cell-${r}-${c}`;
      cell.onclick = () => simulateGridCell(r, c);
      board.appendChild(cell);
    }
  }

  function triggerHaptic(pattern = [200, 100, 250]) {
    if (window.GalaxyNativeBridge && window.GalaxyNativeBridge.vibrate) {
      window.GalaxyNativeBridge.vibrate(250);
    } else if (navigator.vibrate) {
      navigator.vibrate(pattern);
    }
  }

  function showToast(msg) {
    const t = document.getElementById('complete-toast');
    t.textContent = msg;
    t.style.display = 'block';
    triggerHaptic([200, 100, 300]);
    setTimeout(() => { t.style.display = 'none'; }, 6000);
  }

  function updateModeUI(mode) {
    const isExt = mode === 'external_reader';
    document.getElementById('btn-mode-ext').classList.toggle('active', isExt);
    document.getElementById('btn-mode-nfc').classList.toggle('active', !isExt);
    document.getElementById('nfc-subpanel').style.display = isExt ? 'none' : 'block';
    document.getElementById('mode-indicator').textContent = isExt ? '전용 리더기 우선 (기본)' : '핸드폰 NFC 태깅 (보조)';
    if (window.GalaxyNativeBridge && window.GalaxyNativeBridge.setNfcEnabled) {
      window.GalaxyNativeBridge.setNfcEnabled(!isExt);
    }
  }

  function highlightCell(cell) {
    if (!cell) return;
    document.querySelectorAll('.grid-cell.active').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`cell-${cell.row}-${cell.col}`);
    if (target) target.classList.add('active');
    document.getElementById('cell-label').textContent = `${cell.cell_id} (${cell.row + 1}행 ${cell.col + 1}열)`;
    const base = cell.cell_center_base_mm || [0, 0, 0];
    const exact = cell.exact_base_mm || [0, 0, 0];
    const offset = cell.fine_offset_mm || [0, 0, 0];
    const graspZ = cell.grasp_z_mm !== undefined ? cell.grasp_z_mm : 120.0;
    document.getElementById('grid-info').innerHTML =
      `<b>[1단계 셀 중심 접근]</b> ${cell.cell_id} ➔ X=${base[0]}mm, Y=${base[1]}mm<br>` +
      `<b>[2단계 미세 보정]</b> ΔX=${offset[0]}mm, ΔY=${offset[1]}mm ➔ 목표(${exact[0]}, ${exact[1]})mm<br>` +
      `<b>[크기 맞춤 안전 하강]</b> Z=${graspZ}mm (과자 찌그러짐 방지 보호 적용)`;
  }

  async function setScanMode(mode) {
    const res = await fetch('/api/v1/mobile/scan-mode', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode})
    });
    if (res.ok) {
      const data = await res.json();
      updateModeUI(data.scan_mode);
    }
  }

  async function notifyBoxPlaced(slot, uid) {
    const res = await fetch('/api/v1/mobile/box-placed', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({box_slot: slot, uid: uid, quantity: 1})
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || `📦 ${slot}번 상자 배치 알림 전송 완료`);
      refreshStatus();
    } else {
      alert(data.detail || '요청 처리 실패');
    }
  }

  async function sendPhoneNfc(uid, boxSlot = 1) {
    const res = await fetch('/api/v1/mobile/nfc-tag', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({uid, box_slot: boxSlot, quantity: 1})
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`📱 핸드폰 NFC 태깅 완료: ${data.product.product_name}`);
      refreshStatus();
    } else {
      alert(data.detail || 'NFC 태깅 오류');
    }
  }

  function startNativeNfcScan() {
    if (window.GalaxyNativeBridge && window.GalaxyNativeBridge.promptNfcScan) {
      window.GalaxyNativeBridge.promptNfcScan();
    } else if ('NDEFReader' in window) {
      const ndef = new NDEFReader();
      ndef.scan().then(() => {
        ndef.onreading = event => {
          const uid = (event.serialNumber || '0B71E55D').replace(/[^0-9a-fA-F]/g, '').toUpperCase();
          sendPhoneNfc(uid, 1);
        };
      }).catch(err => alert('Web NFC 권한 확인: ' + err));
    } else {
      alert('갤럭시 전용 APK 또는 Android Chrome에서 뒷면 NFC 태그 읽기가 작동합니다.');
    }
  }

  async function sendControl(command) {
    const res = await fetch('/api/v1/mobile/control', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({command})
    });
    if (res.ok) {
      const data = await res.json();
      updateBadge(data.robot_state);
      triggerHaptic([80]);
    }
  }

  async function simulateGridCell(row, col) {
    const u = Math.round(((col + 0.5) / 15) * 639);
    const v = Math.round(((row + 0.5) / 15) * 479);
    const res = await fetch('/api/v1/grid/locate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({pixel: [u, v], rows: 15, cols: 15, product: 'snack_pepero'})
    });
    if (res.ok) {
      const data = await res.json();
      highlightCell({...data.grid_cell, grasp_z_mm: data.grasp_height_info.grasp_z_mm});
    }
  }

  function updateBadge(state) {
    const badge = document.getElementById('state-badge');
    badge.textContent = state;
    badge.className = 'badge';
    if (state === 'PAUSED' || state === 'BOX_PLACED') badge.classList.add('warn');
    if (state === 'EMERGENCY_STOP') badge.classList.add('danger');
  }

  async function refreshStatus() {
    try {
      const res = await fetch('/api/v1/mobile/status');
      if (!res.ok) return;
      const data = await res.json();
      updateModeUI(data.scan_mode);
      updateBadge(data.robot_state);
      if (data.grid && data.grid.active_cell) {
        highlightCell(data.grid.active_cell);
      }
    } catch (e) {}
  }

  function connectWs() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws`);
    ws.onopen = () => {
      document.getElementById('conn-text').textContent = '🟢 실시간 연결됨 (' + location.host + ')';
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'scan_mode') updateModeUI(msg.mode);
        if (msg.type === 'remote_control') updateBadge(msg.robot_state);
        if (msg.type === 'box_placed') {
          updateBadge('BOX_PLACED');
          showToast(msg.message);
        }
        if (msg.type === 'grid_active_cell') {
          highlightCell(msg.cell);
        }
        if (msg.type === 'task_progress' && msg.status === 'COMPLETED') {
          updateBadge('COMPLETED');
          showToast('✅ 피킹 및 상자 적재 완료! 상자를 회수하세요.');
        }
        if (msg.type === 'task_completed_haptic') {
          updateBadge('COMPLETED');
          showToast(msg.message);
        }
      } catch (e) {}
    };
    ws.onclose = () => {
      document.getElementById('conn-text').textContent = '🔴 연결 재시도 중...';
      setTimeout(connectWs, 2000);
    };
  }

  window.onNativeNfcTag = function(uid) {
    sendPhoneNfc(uid, 1);
  };

  refreshStatus();
  connectWs();
</script>
</body>
</html>
"""
