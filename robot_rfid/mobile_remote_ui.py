"""Samsung Galaxy Remote Controller UI & PWA manifest (Apple Liquid Glass Design System)."""

MANIFEST_JSON = {
    "name": "E0509 리모컨",
    "short_name": "E0509 리모컨",
    "start_url": "/remote",
    "display": "standalone",
    "background_color": "#06080F",
    "theme_color": "#06080F",
    "orientation": "portrait",
}

MOBILE_REMOTE_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#06080F">
<link rel="manifest" href="/remote/manifest.json">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<title>E0509 Controller</title>
<style>
  :root {
    --bg-deep: #05070c;
    --glass-surface: linear-gradient(145deg, rgba(255, 255, 255, 0.085) 0%, rgba(255, 255, 255, 0.025) 100%);
    --glass-elevated: linear-gradient(145deg, rgba(255, 255, 255, 0.13) 0%, rgba(255, 255, 255, 0.04) 100%);
    --glass-pressed: linear-gradient(145deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.015) 100%);
    --glass-border: rgba(255, 255, 255, 0.11);
    --glass-specular: rgba(255, 255, 255, 0.24);
    --text-primary: #f8fafc;
    --text-secondary: rgba(226, 232, 240, 0.68);
    --text-tertiary: rgba(148, 163, 184, 0.52);
    --accent-cyan: #38bdf8;
    --accent-blue: #0A84FF;
    --accent-green: #30D158;
    --accent-amber: #FF9F0A;
    --accent-red: #FF453A;
    --font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Pretendard", "Malgun Gothic", sans-serif;
    --font-mono: "JetBrains Mono", "SF Mono", Consolas, monospace;
    --radius-card: 24px;
    --radius-control: 16px;
    --radius-pill: 999px;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-tap-highlight-color: transparent;
  }

  body {
    font-family: var(--font-sans);
    background-color: var(--bg-deep);
    color: var(--text-primary);
    min-height: 100vh;
    padding: 14px 14px 36px;
    max-width: 460px;
    margin: 0 auto;
    position: relative;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
  }

  /* Ambient optical light field behind Liquid Glass layers */
  body::before,
  body::after {
    content: "";
    position: fixed;
    border-radius: 50%;
    filter: blur(72px);
    z-index: -1;
    pointer-events: none;
  }
  body::before {
    width: 300px;
    height: 300px;
    top: -80px;
    left: -60px;
    background: radial-gradient(circle, rgba(10, 132, 255, 0.22) 0%, rgba(56, 189, 248, 0.04) 70%, transparent 100%);
  }
  body::after {
    width: 320px;
    height: 320px;
    bottom: 60px;
    right: -90px;
    background: radial-gradient(circle, rgba(48, 209, 88, 0.13) 0%, rgba(99, 102, 241, 0.08) 65%, transparent 100%);
  }

  /* Liquid Glass Container Base */
  .liquid-card {
    background: var(--glass-surface);
    backdrop-filter: blur(30px) saturate(190%);
    -webkit-backdrop-filter: blur(30px) saturate(190%);
    border-radius: var(--radius-card);
    border: 1px solid var(--glass-border);
    box-shadow:
      inset 0 1px 0 0 var(--glass-specular),
      inset 0 0 24px 0 rgba(255, 255, 255, 0.02),
      0 18px 40px -12px rgba(0, 0, 0, 0.6);
    padding: 16px;
    margin-bottom: 12px;
    position: relative;
  }

  /* Top Navigation Bar */
  header.liquid-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 18px;
    border-radius: 22px;
  }
  .brand-group {
    display: flex;
    align-items: center;
    gap: 11px;
  }
  .brand-orb {
    width: 34px;
    height: 34px;
    border-radius: 11px;
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.28), rgba(10, 132, 255, 0.1));
    border: 1px solid rgba(56, 189, 248, 0.4);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.35), 0 4px 14px rgba(10, 132, 255, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #e0f2fe;
  }
  .title-wrap h1 {
    font-size: 0.96rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text-primary);
  }
  .conn-row {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 2px;
  }
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-green);
    box-shadow: 0 0 8px var(--accent-green);
  }
  .status-dot.offline {
    background: var(--accent-red);
    box-shadow: 0 0 8px var(--accent-red);
  }
  .conn-row span {
    font-size: 0.72rem;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  .status-pill {
    padding: 6px 12px;
    border-radius: var(--radius-pill);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    background: rgba(48, 209, 88, 0.14);
    color: #6ee7b7;
    border: 1px solid rgba(48, 209, 88, 0.32);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2);
  }
  .status-pill.warn {
    background: rgba(255, 159, 10, 0.16);
    color: #fcd34d;
    border-color: rgba(255, 159, 10, 0.38);
  }
  .status-pill.danger {
    background: rgba(255, 69, 58, 0.2);
    color: #fca5a5;
    border-color: rgba(255, 69, 58, 0.45);
  }

  /* Section Headers */
  .section-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 12px;
  }
  .section-label {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .step-tag {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 600;
    color: var(--accent-cyan);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .section-title {
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }
  .section-meta {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-secondary);
  }

  /* Liquid Glass Segmented Pill Control */
  .segmented-track {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    padding: 4px;
    border-radius: 14px;
    background: rgba(0, 0, 0, 0.38);
    border: 1px solid rgba(255, 255, 255, 0.07);
    box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.45);
  }
  .seg-btn {
    border: none;
    background: transparent;
    color: var(--text-secondary);
    padding: 10px 10px;
    border-radius: 10px;
    font-family: var(--font-sans);
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    transition: all 0.22s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .seg-btn.active {
    background: linear-gradient(145deg, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0.07) 100%);
    color: var(--text-primary);
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.32),
      0 4px 12px rgba(0, 0, 0, 0.35);
  }

  /* Auxiliary NFC Drawer */
  .nfc-drawer {
    display: none;
    margin-top: 12px;
    padding: 12px;
    border-radius: 16px;
    background: linear-gradient(145deg, rgba(10, 132, 255, 0.14), rgba(56, 189, 248, 0.04));
    border: 1px solid rgba(56, 189, 248, 0.26);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
  }
  .nfc-drawer-desc {
    font-size: 0.75rem;
    color: rgba(224, 242, 254, 0.88);
    margin-bottom: 10px;
    line-height: 1.45;
  }

  /* Glass Tactile Buttons */
  .grid-2col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 9px;
  }
  .glass-btn {
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: var(--glass-elevated);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    color: var(--text-primary);
    padding: 12px 13px;
    border-radius: var(--radius-control);
    cursor: pointer;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 6px;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.2),
      0 6px 16px -4px rgba(0, 0, 0, 0.35);
    transition: transform 0.14s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.18s, background 0.18s;
  }
  .glass-btn:active {
    transform: scale(0.975);
    background: var(--glass-pressed);
  }
  .glass-btn:focus-visible, .seg-btn:focus-visible {
    outline: 2px solid var(--accent-cyan);
    outline-offset: 2px;
  }
  .btn-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }
  .slot-badge {
    font-family: var(--font-mono);
    font-size: 0.66rem;
    font-weight: 600;
    color: var(--accent-cyan);
    letter-spacing: 0.05em;
  }
  .btn-label {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }
  .btn-uid {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    color: var(--text-tertiary);
  }

  /* 15x15 Optical Matrix */
  .matrix-frame {
    padding: 8px;
    border-radius: 16px;
    background: rgba(3, 5, 10, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.65);
  }
  .grid-board {
    display: grid;
    grid-template-columns: repeat(15, 1fr);
    gap: 2px;
    width: 100%;
    aspect-ratio: 4 / 3;
  }
  .grid-cell {
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.03);
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
  }
  .grid-cell:hover {
    background: rgba(255, 255, 255, 0.12);
  }
  .grid-cell.active {
    background: linear-gradient(135deg, #38bdf8 0%, #0A84FF 100%);
    border-color: rgba(255, 255, 255, 0.65);
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.75);
    transform: scale(1.08);
    z-index: 2;
  }

  /* Telemetry Readout Strip */
  .telemetry-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 10px;
  }
  .telemetry-box {
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 9px 10px;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }
  .telemetry-kicker {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
  }
  .telemetry-val {
    font-family: var(--font-mono);
    font-size: 0.73rem;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .telemetry-sub {
    font-size: 0.65rem;
    color: var(--text-secondary);
    margin-top: 2px;
  }

  /* Action Control Pad */
  .action-btn {
    border: 1px solid rgba(255, 255, 255, 0.11);
    background: var(--glass-elevated);
    color: var(--text-primary);
    padding: 13px 14px;
    border-radius: var(--radius-control);
    font-family: var(--font-sans);
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.2),
      0 6px 16px -4px rgba(0, 0, 0, 0.35);
    transition: transform 0.14s ease, background 0.18s ease;
  }
  .action-btn:active {
    transform: scale(0.975);
  }
  .action-btn.tint-green {
    background: linear-gradient(145deg, rgba(48, 209, 88, 0.22) 0%, rgba(48, 209, 88, 0.06) 100%);
    border-color: rgba(48, 209, 88, 0.36);
    color: #d1fae5;
  }
  .action-btn.tint-amber {
    background: linear-gradient(145deg, rgba(255, 159, 10, 0.22) 0%, rgba(255, 159, 10, 0.06) 100%);
    border-color: rgba(255, 159, 10, 0.36);
    color: #fef3c7;
  }
  .action-btn.estop {
    grid-column: span 2;
    padding: 14px;
    font-size: 0.86rem;
    letter-spacing: 0.02em;
    background: linear-gradient(145deg, rgba(255, 69, 58, 0.34) 0%, rgba(220, 38, 38, 0.16) 100%);
    border-color: rgba(255, 69, 58, 0.52);
    color: #fee2e2;
    box-shadow:
      inset 0 1px 0 rgba(255, 255, 255, 0.28),
      0 8px 24px -6px rgba(239, 68, 68, 0.35);
  }

  /* Notification Banner */
  .toast {
    display: none;
    background: linear-gradient(145deg, rgba(48, 209, 88, 0.24), rgba(16, 185, 129, 0.08));
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(48, 209, 88, 0.45);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25), 0 10px 28px rgba(0, 0, 0, 0.45);
    color: #ecfdf5;
    padding: 12px 16px;
    border-radius: 16px;
    margin-bottom: 12px;
    font-size: 0.82rem;
    font-weight: 600;
    text-align: center;
  }

  svg.icon {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    stroke-width: 1.8;
    fill: none;
    stroke-linecap: round;
    stroke-linejoin: round;
    flex-shrink: 0;
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      transition: none !important;
      animation: none !important;
    }
  }
</style>
</head>
<body>
  <header class="liquid-card liquid-header">
    <div class="brand-group">
      <div class="brand-orb" aria-hidden="true">
        <svg class="icon" viewBox="0 0 24 24">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      </div>
      <div class="title-wrap">
        <h1>E0509 Remote Controller</h1>
        <div class="conn-row">
          <span id="conn-dot" class="status-dot"></span>
          <span id="conn-text">CONNECTING...</span>
        </div>
      </div>
    </div>
    <span id="state-badge" class="status-pill">STANDBY</span>
  </header>

  <div id="complete-toast" class="toast" role="status" aria-live="polite"></div>

  <section class="liquid-card">
    <div class="section-head">
      <div class="section-label">
        <span class="step-tag">01</span>
        <span class="section-title">RFID 스캔 운용 모드</span>
      </div>
      <span id="mode-indicator" class="section-meta">EXTERNAL PRIORITY</span>
    </div>
    <div class="segmented-track" role="tablist" aria-label="RFID 스캔 모드 선택">
      <button id="btn-mode-ext" class="seg-btn active" onclick="setScanMode('external_reader')">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5M19.1 4.9C23 8.8 23 15.2 19.1 19.1"/>
          <circle cx="12" cy="12" r="2"/>
        </svg>
        <span>전용 리더기 우선</span>
      </button>
      <button id="btn-mode-nfc" class="seg-btn" onclick="setScanMode('phone_nfc')">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="5" y="2" width="14" height="20" rx="3"/>
          <path d="M12 18h.01M9.5 7.5a3.5 3.5 0 0 1 5 0"/>
        </svg>
        <span>모바일 NFC 보조</span>
      </button>
    </div>

    <div id="nfc-subpanel" class="nfc-drawer">
      <p class="nfc-drawer-desc">
        보조 태그 모드가 활성화되었습니다. 디바이스 후면을 상자 태그에 접촉하거나 수동 패킷을 전송하세요.
      </p>
      <div class="grid-2col">
        <button class="glass-btn" onclick="sendPhoneNfc('0B71E55D', 1)">
          <div class="btn-top-row">
            <span class="slot-badge">NFC PACKET</span>
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
          </div>
          <span class="btn-label">빼빼로 태그 전송</span>
          <span class="btn-uid">0B71E55D · BOX-01</span>
        </button>
        <button class="glass-btn" onclick="startNativeNfcScan()">
          <div class="btn-top-row">
            <span class="slot-badge">READER ON</span>
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12h20M12 2v20"/></svg>
          </div>
          <span class="btn-label">후면 NFC 스캔 대기</span>
          <span class="btn-uid">ISO-14443A / NDEF</span>
        </button>
      </div>
    </div>
  </section>

  <section class="liquid-card">
    <div class="section-head">
      <div class="section-label">
        <span class="step-tag">02</span>
        <span class="section-title">상자 배치 완료 및 스캔 출동</span>
      </div>
      <span class="section-meta">4 SLOTS</span>
    </div>
    <div class="grid-2col">
      <button class="glass-btn" onclick="notifyBoxPlaced(1, '0B71E55D')">
        <div class="btn-top-row">
          <span class="slot-badge">SLOT 01</span>
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/></svg>
        </div>
        <span class="btn-label">아몬드 빼빼로</span>
        <span class="btn-uid">UID 0B71E55D</span>
      </button>

      <button class="glass-btn" onclick="notifyBoxPlaced(2, '0B71E75D')">
        <div class="btn-top-row">
          <span class="slot-badge">SLOT 02</span>
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/></svg>
        </div>
        <span class="btn-label">제로 콜라 500ml</span>
        <span class="btn-uid">UID 0B71E75D</span>
      </button>

      <button class="glass-btn" onclick="notifyBoxPlaced(3, '0B71E65D')">
        <div class="btn-top-row">
          <span class="slot-badge">SLOT 03</span>
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/></svg>
        </div>
        <span class="btn-label">스팸 클래식</span>
        <span class="btn-uid">UID 0B71E65D</span>
      </button>

      <button class="glass-btn" onclick="notifyBoxPlaced(4, '0B71ED5D')">
        <div class="btn-top-row">
          <span class="slot-badge">SLOT 04</span>
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/></svg>
        </div>
        <span class="btn-label">물티슈 100매</span>
        <span class="btn-uid">UID 0B71ED5D</span>
      </button>
    </div>
  </section>

  <section class="liquid-card">
    <div class="section-head">
      <div class="section-label">
        <span class="step-tag">03</span>
        <span class="section-title">15×15 그리드 트래킹 및 보정</span>
      </div>
      <span id="cell-label" class="section-meta">READY · 225 CELLS</span>
    </div>
    <div class="matrix-frame">
      <div id="grid-board" class="grid-board" role="grid" aria-label="15x15 작업 영역 그리드"></div>
    </div>
    <div class="telemetry-grid">
      <div class="telemetry-box">
        <div class="telemetry-kicker">1차 셀 중심</div>
        <div id="tel-coarse" class="telemetry-val">486.7, 0.0</div>
        <div class="telemetry-sub">BASE XY (mm)</div>
      </div>
      <div class="telemetry-box">
        <div class="telemetry-kicker">2차 미세 보정</div>
        <div id="tel-offset" class="telemetry-val">+4.8, -5.0</div>
        <div class="telemetry-sub">ΔX, ΔY (mm)</div>
      </div>
      <div class="telemetry-box">
        <div class="telemetry-kicker">안전 파지 높이</div>
        <div id="tel-grasp" class="telemetry-val">Z 120.0 mm</div>
        <div class="telemetry-sub">파손 방지 적용</div>
      </div>
    </div>
  </section>

  <section class="liquid-card">
    <div class="section-head">
      <div class="section-label">
        <span class="step-tag">04</span>
        <span class="section-title">매니퓰레이터 제어</span>
      </div>
      <span class="section-meta">REMOTE HMI</span>
    </div>
    <div class="grid-2col">
      <button class="action-btn tint-green" onclick="sendControl('resume')">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><polygon points="6 3 20 12 6 21 6 3"/></svg>
        <span>작업 시작 · 재개</span>
      </button>
      <button class="action-btn tint-amber" onclick="sendControl('pause')">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
        <span>일시정지</span>
      </button>
      <button class="action-btn" onclick="sendControl('scan_dispatch')">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>
        <span>리더기 스캔 출동</span>
      </button>
      <button class="action-btn" onclick="sendControl('home')">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1v-9.5Z"/></svg>
        <span>홈 자세 복귀</span>
      </button>
      <button class="action-btn estop" onclick="sendControl('emergency_stop')">
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <span>비상 정지 (EMERGENCY STOP)</span>
      </button>
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
    t.textContent = msg.replace(/^[^가-힣A-Za-z0-9]+/, '').trim();
    t.style.display = 'block';
    triggerHaptic([200, 100, 300]);
    setTimeout(() => { t.style.display = 'none'; }, 6000);
  }

  function updateModeUI(mode) {
    const isExt = mode === 'external_reader';
    document.getElementById('btn-mode-ext').classList.toggle('active', isExt);
    document.getElementById('btn-mode-nfc').classList.toggle('active', !isExt);
    document.getElementById('nfc-subpanel').style.display = isExt ? 'none' : 'block';
    document.getElementById('mode-indicator').textContent = isExt ? 'EXTERNAL PRIORITY' : 'DEVICE NFC ACTIVE';
    if (window.GalaxyNativeBridge && window.GalaxyNativeBridge.setNfcEnabled) {
      window.GalaxyNativeBridge.setNfcEnabled(!isExt);
    }
  }

  function highlightCell(cell) {
    if (!cell) return;
    document.querySelectorAll('.grid-cell.active').forEach(el => el.classList.remove('active'));
    const target = document.getElementById(`cell-${cell.row}-${cell.col}`);
    if (target) target.classList.add('active');
    document.getElementById('cell-label').textContent = `${cell.cell_id} · R${String(cell.row + 1).padStart(2, '0')} C${String(cell.col + 1).padStart(2, '0')}`;
    const base = cell.cell_center_base_mm || [0, 0, 0];
    const offset = cell.fine_offset_mm || [0, 0, 0];
    const graspZ = cell.grasp_z_mm !== undefined ? cell.grasp_z_mm : 120.0;
    const fmtSign = (n) => (n >= 0 ? `+${Number(n).toFixed(1)}` : `${Number(n).toFixed(1)}`);
    document.getElementById('tel-coarse').textContent = `${Number(base[0]).toFixed(1)}, ${Number(base[1]).toFixed(1)}`;
    document.getElementById('tel-offset').textContent = `${fmtSign(offset[0])}, ${fmtSign(offset[1])}`;
    document.getElementById('tel-grasp').textContent = `Z ${Number(graspZ).toFixed(1)} mm`;
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
      showToast(data.message || `${slot}번 상자 배치 알림 전송 완료`);
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
      showToast(`모바일 NFC 태깅 등록 완료: ${data.product.product_name}`);
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
      alert('갤럭시 전용 APK 또는 Android Chrome에서 후면 NFC 태그 읽기가 작동합니다.');
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
    badge.className = 'status-pill';
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
    const dot = document.getElementById('conn-dot');
    ws.onopen = () => {
      dot.classList.remove('offline');
      document.getElementById('conn-text').textContent = 'ONLINE · ' + location.host;
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
          showToast('피킹 및 상자 적재 완료 — 상자를 회수하세요');
        }
        if (msg.type === 'task_completed_haptic') {
          updateBadge('COMPLETED');
          showToast(msg.message);
        }
      } catch (e) {}
    };
    ws.onclose = () => {
      dot.classList.add('offline');
      document.getElementById('conn-text').textContent = 'RECONNECTING...';
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
