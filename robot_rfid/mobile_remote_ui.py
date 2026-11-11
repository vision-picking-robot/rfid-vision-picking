"""Minimalist White/Black & Sky Blue & Navy Remote Controller UI for Doosan E0509."""

from __future__ import annotations

MOBILE_REMOTE_MANIFEST = {
    "name": "E0509 Remote Controller",
    "short_name": "E0509 리모컨",
    "start_url": "/remote",
    "display": "standalone",
    "background_color": "#F8FAFC",
    "theme_color": "#0F172A",
    "orientation": "portrait",
}
MANIFEST_JSON = MOBILE_REMOTE_MANIFEST

MOBILE_REMOTE_HTML = """<!DOCTYPE html>
<html lang="ko" data-theme="light">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover" />
<meta name="theme-color" content="#F8FAFC" id="metaThemeColor" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<title>E0509 Remote Controller</title>
<link rel="manifest" href="/remote/manifest.json" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet" />
<style>
  /* ==========================================================================
     Monotone Palette:
     1) Light Mode : White (#FFFFFF / #F8FAFC) + Sky Blue (#38BDF8 / #0284C7) + Navy (#0F172A / #1E3A8A)
     2) Dark Mode  : Black (#05070B / #090D16) + Sky Blue (#38BDF8 / #0EA5E9) + Navy (#0F172A / #1E3A8A)
     Zero emojis, zero decorative icons, zero purple/neon/rainbow colors.
     ========================================================================== */
  :root,
  html[data-theme="light"] {
    --bg-base: #F4F7FB;
    --bg-gradient: linear-gradient(180deg, #FFFFFF 0%, #F1F6FD 100%);
    --glass-surface: rgba(255, 255, 255, 0.84);
    --glass-elevated: rgba(255, 255, 255, 0.94);
    --glass-subtle: #F8FAFC;
    --border-hairline: rgba(15, 23, 42, 0.09);
    --border-strong: rgba(30, 58, 138, 0.18);
    --specular-top: inset 0 1px 0 rgba(255, 255, 255, 0.95);
    --card-shadow: 0 10px 28px -8px rgba(15, 23, 42, 0.06), 0 2px 6px rgba(15, 23, 42, 0.03);

    --navy-950: #0A1122;
    --navy-900: #0F172A;
    --navy-800: #1E3A8A;
    --navy-700: #1D4ED8;

    --sky-600: #0284C7;
    --sky-500: #0EA5E9;
    --sky-400: #38BDF8;
    --sky-100: #E0F2FE;
    --sky-50:  #F0F9FF;

    --text-primary: #0F172A;
    --text-secondary: #475569;
    --text-muted: #64748B;
    --text-on-navy: #FFFFFF;

    --seg-track-bg: #E9EFF8;
    --seg-pill-bg: #0F172A;
    --seg-text-active: #FFFFFF;
    --seg-text-inactive: #475569;

    --slot-bg: #FFFFFF;
    --slot-bg-hover: #F0F9FF;
    --slot-border: rgba(15, 23, 42, 0.10);
    --slot-active-border: #0284C7;
    --slot-tag-color: #0284C7;

    --grid-board-bg: #EEF4FA;
    --grid-cell-bg: #FFFFFF;
    --grid-cell-border: rgba(15, 23, 42, 0.07);
    --grid-cell-active-bg: #0284C7;
    --grid-cell-active-border: #0F172A;

    --btn-primary-bg: #0F172A;
    --btn-primary-text: #FFFFFF;
    --btn-primary-border: #0F172A;

    --btn-sky-bg: #E0F2FE;
    --btn-sky-text: #0F172A;
    --btn-sky-border: rgba(2, 132, 199, 0.30);

    --btn-secondary-bg: #FFFFFF;
    --btn-secondary-text: #0F172A;
    --btn-secondary-border: rgba(15, 23, 42, 0.14);

    --btn-outline-navy-bg: #F8FAFC;
    --btn-outline-navy-text: #1E3A8A;
    --btn-outline-navy-border: rgba(30, 58, 138, 0.28);

    --status-pill-bg: #E0F2FE;
    --status-pill-text: #0369A1;
    --status-pill-border: rgba(2, 132, 199, 0.25);
    --dot-color: #0284C7;
  }

  html[data-theme="dark"] {
    --bg-base: #05080F;
    --bg-gradient: linear-gradient(180deg, #05080F 0%, #091020 100%);
    --glass-surface: rgba(13, 21, 38, 0.82);
    --glass-elevated: rgba(18, 29, 53, 0.90);
    --glass-subtle: rgba(10, 16, 30, 0.85);
    --border-hairline: rgba(148, 163, 184, 0.14);
    --border-strong: rgba(56, 189, 248, 0.28);
    --specular-top: inset 0 1px 0 rgba(255, 255, 255, 0.08);
    --card-shadow: 0 14px 34px -8px rgba(0, 0, 0, 0.65);

    --navy-950: #05080F;
    --navy-900: #0F172A;
    --navy-800: #1E3A8A;
    --navy-700: #1D4ED8;

    --sky-600: #0284C7;
    --sky-500: #0EA5E9;
    --sky-400: #38BDF8;
    --sky-100: rgba(56, 189, 248, 0.14);
    --sky-50:  rgba(56, 189, 248, 0.08);

    --text-primary: #F8FAFC;
    --text-secondary: #94A3B8;
    --text-muted: #64748B;
    --text-on-navy: #FFFFFF;

    --seg-track-bg: #080D19;
    --seg-pill-bg: #1E3A8A;
    --seg-text-active: #FFFFFF;
    --seg-text-inactive: #94A3B8;

    --slot-bg: rgba(15, 23, 42, 0.85);
    --slot-bg-hover: rgba(30, 58, 138, 0.45);
    --slot-border: rgba(148, 163, 184, 0.14);
    --slot-active-border: #38BDF8;
    --slot-tag-color: #38BDF8;

    --grid-board-bg: #060A12;
    --grid-cell-bg: #0F172A;
    --grid-cell-border: rgba(148, 163, 184, 0.10);
    --grid-cell-active-bg: #38BDF8;
    --grid-cell-active-border: #FFFFFF;

    --btn-primary-bg: #38BDF8;
    --btn-primary-text: #05080F;
    --btn-primary-border: #38BDF8;

    --btn-sky-bg: #1E3A8A;
    --btn-sky-text: #F8FAFC;
    --btn-sky-border: rgba(56, 189, 248, 0.32);

    --btn-secondary-bg: #0F172A;
    --btn-secondary-text: #F8FAFC;
    --btn-secondary-border: rgba(148, 163, 184, 0.18);

    --btn-outline-navy-bg: rgba(15, 23, 42, 0.90);
    --btn-outline-navy-text: #38BDF8;
    --btn-outline-navy-border: rgba(56, 189, 248, 0.35);

    --status-pill-bg: rgba(56, 189, 248, 0.12);
    --status-pill-text: #38BDF8;
    --status-pill-border: rgba(56, 189, 248, 0.30);
    --dot-color: #38BDF8;
  }

  * {
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
    margin: 0;
    padding: 0;
  }

  html, body {
    min-height: 100%;
    background: var(--bg-gradient);
    background-color: var(--bg-base);
    color: var(--text-primary);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
    font-size: 14px;
    line-height: 1.45;
    -webkit-font-smoothing: antialiased;
    transition: background-color 0.2s ease, color 0.2s ease;
  }

  .app-shell {
    max-width: 440px;
    margin: 0 auto;
    padding: 14px 14px 32px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  /* Liquid Glass Container */
  .glass-card {
    background: var(--glass-surface);
    backdrop-filter: blur(24px) saturate(160%);
    -webkit-backdrop-filter: blur(24px) saturate(160%);
    border: 1px solid var(--border-hairline);
    border-radius: 20px;
    padding: 16px;
    box-shadow: var(--card-shadow), var(--specular-top);
  }

  /* Header Bar */
  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 13px 16px;
    border-radius: 18px;
  }
  .brand-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .brand-title {
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text-primary);
  }
  .brand-sub {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text-secondary);
  }
  .conn-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--dot-color);
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .status-pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 5px 10px;
    border-radius: 999px;
    background: var(--status-pill-bg);
    color: var(--status-pill-text);
    border: 1px solid var(--status-pill-border);
  }
  .theme-btn {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 5px 9px;
    border-radius: 999px;
    border: 1px solid var(--border-hairline);
    background: var(--glass-subtle);
    color: var(--text-primary);
    cursor: pointer;
  }

  /* Section Header */
  .section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .section-title-wrap {
    display: flex;
    align-items: baseline;
    gap: 7px;
  }
  .section-index {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: var(--sky-600);
  }
  html[data-theme="dark"] .section-index {
    color: var(--sky-400);
  }
  .section-title {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text-primary);
  }
  .section-meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-muted);
  }

  /* Segmented Control */
  .segmented-track {
    position: relative;
    display: grid;
    grid-template-columns: 1fr 1fr;
    padding: 4px;
    background: var(--seg-track-bg);
    border-radius: 12px;
    border: 1px solid var(--border-hairline);
  }
  .segment-pill {
    position: absolute;
    top: 4px;
    bottom: 4px;
    left: 4px;
    width: calc(50% - 4px);
    border-radius: 9px;
    background: var(--seg-pill-bg);
    transition: transform 0.22s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .segmented-track[data-mode="phone_nfc"] .segment-pill {
    transform: translateX(100%);
  }
  .segment-btn {
    position: relative;
    z-index: 1;
    appearance: none;
    border: none;
    background: transparent;
    color: var(--seg-text-inactive);
    font-family: inherit;
    font-size: 12px;
    font-weight: 600;
    padding: 9px 10px;
    border-radius: 9px;
    cursor: pointer;
    transition: color 0.18s ease;
  }
  .segment-btn.active {
    color: var(--seg-text-active);
  }

  /* Auxiliary NFC Drawer */
  .nfc-drawer {
    display: none;
    margin-top: 12px;
    padding: 12px;
    border-radius: 14px;
    background: var(--sky-50);
    border: 1px solid var(--border-strong);
  }
  .nfc-drawer.visible {
    display: block;
  }
  .nfc-caption {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 10px;
  }

  /* Box Slot Grid */
  .slot-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .slot-card {
    appearance: none;
    text-align: left;
    background: var(--slot-bg);
    border: 1px solid var(--slot-border);
    border-radius: 14px;
    padding: 12px 13px;
    color: var(--text-primary);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: border-color 0.15s ease, background-color 0.15s ease, transform 0.12s ease;
  }
  .slot-card:active {
    transform: scale(0.985);
    background: var(--slot-bg-hover);
    border-color: var(--slot-active-border);
  }
  .slot-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .slot-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: var(--slot-tag-color);
  }
  .slot-action-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
  }
  .slot-name {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text-primary);
    margin-top: 2px;
  }
  .slot-uid {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
  }

  /* 15x15 Checkerboard Grid */
  .grid-frame {
    padding: 8px;
    border-radius: 14px;
    background: var(--grid-board-bg);
    border: 1px solid var(--border-hairline);
  }
  .grid-board {
    display: grid;
    grid-template-columns: repeat(15, 1fr);
    gap: 2px;
    aspect-ratio: 1 / 1;
  }
  .grid-cell {
    background: var(--grid-cell-bg);
    border: 1px solid var(--grid-cell-border);
    border-radius: 2px;
    cursor: pointer;
    transition: background-color 0.1s ease;
  }
  .grid-cell.active {
    background: var(--grid-cell-active-bg);
    border-color: var(--grid-cell-active-border);
  }

  /* Telemetry Readout */
  .telemetry-strip {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-top: 10px;
  }
  .telemetry-box {
    padding: 9px 10px;
    border-radius: 12px;
    background: var(--glass-subtle);
    border: 1px solid var(--border-hairline);
  }
  .telemetry-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    margin-bottom: 3px;
  }
  .telemetry-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 700;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }
  .telemetry-unit {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--text-secondary);
    margin-top: 1px;
  }

  /* Control Buttons (Strictly White / Sky Blue / Navy) */
  .control-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }
  .ctrl-btn {
    appearance: none;
    border-radius: 12px;
    padding: 12px 12px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.01em;
    cursor: pointer;
    text-align: center;
    transition: transform 0.12s ease, opacity 0.15s ease;
  }
  .ctrl-btn:active {
    transform: scale(0.985);
  }
  .ctrl-primary {
    background: var(--btn-primary-bg);
    color: var(--btn-primary-text);
    border: 1px solid var(--btn-primary-border);
  }
  .ctrl-sky {
    background: var(--btn-sky-bg);
    color: var(--btn-sky-text);
    border: 1px solid var(--btn-sky-border);
  }
  .ctrl-secondary {
    background: var(--btn-secondary-bg);
    color: var(--btn-secondary-text);
    border: 1px solid var(--btn-secondary-border);
  }
  .estop-note { margin: 10px 2px 0; font-size: 12px; line-height: 1.5; opacity: .75; }
  .ctrl-estop {
    grid-column: span 2;
    background: var(--btn-outline-navy-bg);
    color: var(--btn-outline-navy-text);
    border: 1px solid var(--btn-outline-navy-border);
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  /* Toast Banner */
  .toast {
    position: fixed;
    left: 50%;
    bottom: 20px;
    transform: translateX(-50%) translateY(16px);
    background: var(--navy-900);
    color: #FFFFFF;
    border: 1px solid rgba(56, 189, 248, 0.35);
    padding: 10px 16px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease, transform 0.2s ease;
    z-index: 100;
    white-space: nowrap;
  }
  .toast.show {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
</style>
</head>
<body>
<main class="app-shell">
  <!-- Header -->
  <header class="glass-card top-bar">
    <div class="brand-group">
      <div class="brand-title">E0509 Remote Controller</div>
      <div class="brand-sub">
        <span class="conn-dot"></span>
        <span id="connText">ONLINE · 127.0.0.1:8009</span>
      </div>
    </div>
    <div class="header-actions">
      <button type="button" class="theme-btn" id="themeToggleBtn" onclick="toggleTheme()">DARK</button>
      <div class="status-pill" id="robotStateBadge">STANDBY</div>
    </div>
  </header>

  <!-- 01. Scan Mode -->
  <section class="glass-card">
    <div class="section-head">
      <div class="section-title-wrap">
        <span class="section-index">01</span>
        <h2 class="section-title">RFID 스캔 운용 모드</h2>
      </div>
      <span class="section-meta" id="scanModeMeta">PRIORITY 1 · READER</span>
    </div>

    <div class="segmented-track" id="scanTrack" data-mode="external_reader">
      <div class="segment-pill"></div>
      <button type="button" class="segment-btn active" id="modeExternalBtn" onclick="setScanMode('external_reader')">
        전용 리더기 우선
      </button>
      <button type="button" class="segment-btn" id="modePhoneBtn" onclick="setScanMode('phone_nfc')">
        모바일 NFC 보조
      </button>
    </div>

    <div class="nfc-drawer" id="nfcQuickPanel">
      <p class="nfc-caption">
        보조 태그 모드가 활성화되었습니다. 디바이스 후면을 상자 태그에 접촉하거나 수동 패킷을 전송하세요.
      </p>
      <div class="slot-grid">
        <button type="button" class="slot-card" onclick="sendPhoneNfc('0B71E55D', 1)">
          <div class="slot-top">
            <span class="slot-tag">NFC PACKET</span>
            <span class="slot-action-label">SEND</span>
          </div>
          <div class="slot-name">빼빼로 태그 전송</div>
          <div class="slot-uid">0B71E55D · BOX-01</div>
        </button>
        <button type="button" class="slot-card" onclick="startWebNfc()">
          <div class="slot-top">
            <span class="slot-tag">READER ON</span>
            <span class="slot-action-label">SCAN</span>
          </div>
          <div class="slot-name">후면 NFC 스캔 대기</div>
          <div class="slot-uid">ISO-14443A / NDEF</div>
        </button>
      </div>
    </div>
  </section>

  <!-- 02. Box Placement Notification -->
  <section class="glass-card">
    <div class="section-head">
      <div class="section-title-wrap">
        <span class="section-index">02</span>
        <h2 class="section-title">상자 배치 완료 및 스캔 출동</h2>
      </div>
      <span class="section-meta">4 SLOTS</span>
    </div>

    <div class="slot-grid">
      <button type="button" class="slot-card" onclick="notifyBoxPlaced(1, '0B71E55D')">
        <div class="slot-top">
          <span class="slot-tag">SLOT 01</span>
          <span class="slot-action-label">DISPATCH</span>
        </div>
        <div class="slot-name">아몬드 빼빼로</div>
        <div class="slot-uid">UID 0B71E55D</div>
      </button>

      <button type="button" class="slot-card" onclick="notifyBoxPlaced(2, '0B71E75D')">
        <div class="slot-top">
          <span class="slot-tag">SLOT 02</span>
          <span class="slot-action-label">DISPATCH</span>
        </div>
        <div class="slot-name">제로 콜라 500ml</div>
        <div class="slot-uid">UID 0B71E75D</div>
      </button>

      <button type="button" class="slot-card" onclick="notifyBoxPlaced(3, '0B71E65D')">
        <div class="slot-top">
          <span class="slot-tag">SLOT 03</span>
          <span class="slot-action-label">DISPATCH</span>
        </div>
        <div class="slot-name">스팸 클래식</div>
        <div class="slot-uid">UID 0B71E65D</div>
      </button>

      <button type="button" class="slot-card" onclick="notifyBoxPlaced(4, '0B71ED5D')">
        <div class="slot-top">
          <span class="slot-tag">SLOT 04</span>
          <span class="slot-action-label">DISPATCH</span>
        </div>
        <div class="slot-name">물티슈 100매</div>
        <div class="slot-uid">UID 0B71ED5D</div>
      </button>
    </div>
  </section>

  <!-- 03. 15x15 Checkerboard Grid -->
  <section class="glass-card">
    <div class="section-head">
      <div class="section-title-wrap">
        <span class="section-index">03</span>
        <h2 class="section-title">15×15 그리드 트래킹 및 보정</h2>
      </div>
      <span class="section-meta" id="cellLabel">R07_C06 · R08 C07</span>
    </div>

    <div class="grid-frame">
      <div class="grid-board" id="gridBoard"></div>
    </div>

    <div class="telemetry-strip">
      <div class="telemetry-box">
        <div class="telemetry-label">1차 셀 중심</div>
        <div class="telemetry-val" id="coarseXY">486.7, 0.0</div>
        <div class="telemetry-unit">BASE XY (mm)</div>
      </div>
      <div class="telemetry-box">
        <div class="telemetry-label">2차 미세 보정</div>
        <div class="telemetry-val" id="fineDelta">+0.0, +0.2</div>
        <div class="telemetry-unit">ΔX, ΔY (mm)</div>
      </div>
      <div class="telemetry-box">
        <div class="telemetry-label">안전 파지 높이</div>
        <div class="telemetry-val" id="safeGraspZ">Z 120.0 mm</div>
        <div class="telemetry-unit">파손 방지 적용</div>
      </div>
    </div>
  </section>

  <!-- 04. Manipulator Controls -->
  <section class="glass-card">
    <div class="section-head">
      <div class="section-title-wrap">
        <span class="section-index">04</span>
        <h2 class="section-title">매니퓰레이터 제어</h2>
      </div>
      <span class="section-meta">REMOTE HMI</span>
    </div>

    <div class="control-grid">
      <button type="button" class="ctrl-btn ctrl-primary" onclick="sendControl('resume')">
        작업 시작 · 재개
      </button>
      <button type="button" class="ctrl-btn ctrl-sky" onclick="sendControl('pause')">
        일시정지
      </button>
      <button type="button" class="ctrl-btn ctrl-secondary" onclick="sendControl('scan_dispatch')">
        리더기 스캔 출동
      </button>
      <button type="button" class="ctrl-btn ctrl-secondary" onclick="sendControl('home')">
        홈 자세 복귀
      </button>
      <button type="button" class="ctrl-btn ctrl-estop" onclick="sendControl('emergency_stop')">
        비상 정지 (EMERGENCY STOP)
      </button>
    </div>
    <p class="estop-note">로봇 PC의 사이클이 이 버튼을 감지하면 move_stop을 보냅니다. 통신이 끊기면 동작하지 않으므로
      펜던트 E-Stop을 대신하지 않습니다.</p>
  </section>
</main>

<div class="toast" id="toast"></div>

<script>
  let lastCompletedTaskId = null;
  let activeRow = 7;
  let activeCol = 6;

  function applyTheme(theme) {
    const html = document.documentElement;
    html.setAttribute('data-theme', theme);
    const btn = document.getElementById('themeToggleBtn');
    const meta = document.getElementById('metaThemeColor');
    if (theme === 'dark') {
      btn.textContent = 'LIGHT';
      if (meta) meta.setAttribute('content', '#05080F');
    } else {
      btn.textContent = 'DARK';
      if (meta) meta.setAttribute('content', '#F8FAFC');
    }
    try { localStorage.setItem('e0509_theme', theme); } catch (_) {}
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(current === 'light' ? 'dark' : 'light');
  }

  (function initTheme() {
    const params = new URLSearchParams(window.location.search);
    const qTheme = params.get('theme');
    if (qTheme === 'dark' || qTheme === 'light') {
      applyTheme(qTheme);
      return;
    }
    try {
      const saved = localStorage.getItem('e0509_theme');
      if (saved === 'dark' || saved === 'light') {
        applyTheme(saved);
      }
    } catch (_) {}
  })();

  function showToast(msg, vibratePattern = [40]) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('show');
    if (navigator.vibrate && vibratePattern) {
      try { navigator.vibrate(vibratePattern); } catch (_) {}
    }
    if (window.GalaxyBridge && window.GalaxyBridge.vibrate) {
      try { window.GalaxyBridge.vibrate(vibratePattern.join(',')); } catch (_) {}
    }
    clearTimeout(window.__toastTimer);
    window.__toastTimer = setTimeout(() => el.classList.remove('show'), 2400);
  }

  function renderGrid() {
    const board = document.getElementById('gridBoard');
    board.innerHTML = '';
    for (let r = 0; r < 15; r++) {
      for (let c = 0; c < 15; c++) {
        const cell = document.createElement('div');
        cell.className = 'grid-cell' + (r === activeRow && c === activeCol ? ' active' : '');
        cell.onclick = () => selectGridCell(r, c);
        board.appendChild(cell);
      }
    }
  }

  async function selectGridCell(row, col) {
    activeRow = row;
    activeCol = col;
    renderGrid();
    const u = (col + 0.5) / 15.0;
    const v = (row + 0.5) / 15.0;
    const px = 120 + u * 400 + 2.0;
    const py = 60 + v * 300 - 1.5;
    try {
      const res = await fetch('/api/v1/grid/locate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pixel: [px, py], rows: 15, cols: 15, product: 'snack_pepero'})
      });
      const data = await res.json();
      if (data.grid_cell) {
        const c = data.grid_cell;
        document.getElementById('cellLabel').textContent =
          `${c.cell_id} · R${String(c.row + 1).padStart(2, '0')} C${String(c.col + 1).padStart(2, '0')}`;
        document.getElementById('coarseXY').textContent =
          `${c.center_base[0].toFixed(1)}, ${c.center_base[1].toFixed(1)}`;
        const dx = (data.exact_base_xy[0] - c.center_base[0]).toFixed(1);
        const dy = (data.exact_base_xy[1] - c.center_base[1]).toFixed(1);
        document.getElementById('fineDelta').textContent =
          `${dx >= 0 ? '+' : ''}${dx}, ${dy >= 0 ? '+' : ''}${dy}`;
        document.getElementById('safeGraspZ').textContent =
          `Z ${data.safe_grasp_z_mm.toFixed(1)} mm`;
      }
    } catch (_) {}
  }

  async function setScanMode(mode) {
    try {
      const res = await fetch('/api/v1/mobile/scan-mode', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mode})
      });
      const data = await res.json();
      updateScanModeUI(data.scan_mode);
      showToast(
        data.scan_mode === 'external_reader'
          ? '전용 RFID 리더기 우선 모드로 전환되었습니다.'
          : '모바일 NFC 보조 모드가 활성화되었습니다.'
      );
    } catch (_) {
      showToast('스캔 모드 변경 중 통신 오류가 발생했습니다.');
    }
  }

  function updateScanModeUI(mode) {
    const isExt = mode === 'external_reader';
    document.getElementById('scanTrack').setAttribute('data-mode', mode);
    document.getElementById('modeExternalBtn').classList.toggle('active', isExt);
    document.getElementById('modePhoneBtn').classList.toggle('active', !isExt);
    document.getElementById('nfcQuickPanel').classList.toggle('visible', !isExt);
    document.getElementById('scanModeMeta').textContent = isExt
      ? 'PRIORITY 1 · READER'
      : 'DEVICE NFC ACTIVE';
  }

  async function notifyBoxPlaced(slot, uid) {
    try {
      const res = await fetch('/api/v1/mobile/box-placed', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({box_slot: slot, uid, quantity: 1})
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`SLOT 0${slot} 배치 확인 · 리더기 스캔 및 피킹 출동`, [60, 40, 90]);
        pollStatus();
      } else {
        showToast(data.detail || '상자 배치 알림 전송 실패');
      }
    } catch (_) {
      showToast('서버 연결을 확인해주세요.');
    }
  }

  async function sendPhoneNfc(uid, slot) {
    try {
      const res = await fetch('/api/v1/mobile/nfc-tag', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({uid, box_slot: slot, quantity: 1})
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`모바일 NFC 인식 완료 (${data.product.display_name})`, [70, 40, 110]);
        pollStatus();
      } else {
        showToast(data.detail || 'NFC 보조 모드를 먼저 활성화하세요.');
      }
    } catch (_) {
      showToast('NFC 패킷 전송 실패');
    }
  }

  async function startWebNfc() {
    if ('NDEFReader' in window) {
      try {
        const ndef = new NDEFReader();
        await ndef.scan();
        showToast('디바이스 후면에 RFID/NFC 태그를 접촉하세요.');
        ndef.onreading = event => {
          const uid = (event.serialNumber || '0B71E55D').replace(/:/g, '').toUpperCase();
          sendPhoneNfc(uid, 1);
        };
      } catch (_) {
        showToast('NFC 권한을 허용해주세요.');
      }
    } else {
      sendPhoneNfc('0B71E55D', 1);
    }
  }

  async function sendControl(command) {
    try {
      const res = await fetch('/api/v1/mobile/control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command})
      });
      const data = await res.json();
      if (res.ok) {
        const pattern = command === 'emergency_stop' ? [250, 80, 250] : [45];
        showToast(data.message || `제어 명령 전송: ${command}`, pattern);
        pollStatus();
      }
    } catch (_) {
      showToast('제어 명령 전송 실패');
    }
  }

  async function pollStatus() {
    try {
      const res = await fetch('/api/v1/mobile/status');
      if (!res.ok) return;
      const data = await res.json();
      document.getElementById('connText').textContent = `ONLINE · ${window.location.host || '127.0.0.1:8009'}`;
      const badge = document.getElementById('robotStateBadge');
      badge.textContent = data.robot_state;
      updateScanModeUI(data.scan_mode);

      if (data.last_grid_lookup && data.last_grid_lookup.grid_cell) {
        const c = data.last_grid_lookup.grid_cell;
        activeRow = c.row;
        activeCol = c.col;
        renderGrid();
      }

      if (data.last_completed_event && data.last_completed_event.task_id !== lastCompletedTaskId) {
        lastCompletedTaskId = data.last_completed_event.task_id;
        showToast(`피킹 및 상자 적재 완료 (${data.last_completed_event.task_id})`, [180, 90, 220]);
      }
    } catch (_) {
      document.getElementById('connText').textContent = 'OFFLINE · RECONNECTING';
    }
  }

  renderGrid();
  selectGridCell(7, 6);
  pollStatus();
  setInterval(pollStatus, 2500);
</script>
</body>
</html>
"""
