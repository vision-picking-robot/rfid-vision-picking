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

  /* 15x15 grid over the real (rectangular) work area, drawn to scale in BASE mm */
  .grid-frame {
    padding: 8px;
    border-radius: 14px;
    background: var(--grid-board-bg);
    border: 1px solid var(--border-hairline);
  }
  .area-svg {
    display: block;
    width: 100%;
    height: auto;
    max-height: 68vh;
    touch-action: manipulation;
  }
  .area-svg .cell {
    fill: var(--grid-cell-bg);
    stroke: var(--grid-cell-border);
    stroke-width: 0.8;
    cursor: pointer;
  }
  .area-svg .cell.item { fill: var(--sky-100); }
  .area-svg .cell.active { fill: var(--grid-cell-active-bg); stroke: var(--grid-cell-active-border); stroke-width: 1.4; }
  .area-svg .outline { fill: none; stroke: var(--navy-800); stroke-width: 2.4; }
  html[data-theme="dark"] .area-svg .outline { stroke: var(--sky-400); }
  .area-svg .corner-dot { fill: var(--navy-900); }
  html[data-theme="dark"] .area-svg .corner-dot { fill: var(--sky-400); }
  .area-svg .corner-num { fill: #FFFFFF; font: 700 13px 'JetBrains Mono', monospace; }
  html[data-theme="dark"] .area-svg .corner-num { fill: #05080F; }
  .area-svg .item-box { fill: rgba(14, 165, 233, 0.20); stroke: var(--sky-600); stroke-width: 2.4; stroke-linejoin: round; }
  .area-svg .item-box.reported { stroke-dasharray: 7 4; }
  .area-svg .item-box.missing { fill: none; stroke: var(--text-muted); stroke-dasharray: 4 5; stroke-width: 1.6; }
  .area-svg .item-center { fill: var(--sky-600); }
  .area-svg .item-label { fill: var(--text-primary); font: 700 12px 'Inter', sans-serif; paint-order: stroke;
    stroke: var(--grid-board-bg); stroke-width: 3px; }
  .area-svg .dim-label { fill: var(--text-muted); font: 600 11px 'JetBrains Mono', monospace; }
  .area-note { margin-top: 8px; font-size: 11px; color: var(--text-muted); line-height: 1.5; }
  .area-note.warn { color: #B45309; }
  .item-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
  .item-row {
    display: grid; grid-template-columns: 26px 1fr auto; gap: 8px; align-items: center;
    padding: 8px 10px; border-radius: 12px; background: var(--glass-subtle); border: 1px solid var(--border-hairline);
    appearance: none; text-align: left; color: var(--text-primary); font-family: inherit; cursor: pointer;
  }
  .item-zone { font: 700 12px 'JetBrains Mono', monospace; color: var(--sky-600); text-align: center; }
  .item-name { font-size: 12px; font-weight: 700; }
  .item-meta { font: 500 10.5px 'JetBrains Mono', monospace; color: var(--text-muted); }
  .item-cell { font: 700 11px 'JetBrains Mono', monospace; color: var(--text-secondary); }
  .link-banner {
    margin-bottom: 10px; padding: 9px 11px; border-radius: 12px; font-size: 12px; line-height: 1.45;
    background: var(--glass-subtle); border: 1px solid var(--border-hairline); color: var(--text-secondary);
  }
  .link-banner.ok { border-color: var(--btn-sky-border); color: var(--text-primary); }
  .tag-feed { display: grid; gap: 4px; padding: 11px 13px; border-radius: 14px; font-size: 13px; line-height: 1.45;
    background: var(--glass-subtle); border: 1px solid var(--border-hairline); color: var(--text-secondary); }
  .tag-feed strong { color: var(--text-primary); font-size: 15px; }
  .tag-feed .tag-uid { font-family: ui-monospace, monospace; letter-spacing: 0.04em; }
  .tag-feed.ok { border-color: var(--btn-sky-border); }
  .tag-feed.bad { border-color: rgba(180, 83, 9, 0.45); color: #B45309; }
  .tag-feed.fresh { animation: tagPulse 1.2s ease-out 1; }
  @keyframes tagPulse { from { box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.55); } to { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); } }
  .link-banner.down { border-color: rgba(180, 83, 9, 0.45); color: #B45309; }
  .ctrl-btn[hidden] { display: none; }
  .ctrl-btn:disabled { opacity: 0.45; }

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

  <!-- 00. Last tag -->
  <section class="glass-card">
    <div class="section-head">
      <div class="section-title-wrap">
        <span class="section-index">00</span>
        <h2 class="section-title">최근 인식 태그</h2>
      </div>
      <span class="section-meta" id="tagFeedTime">LIVE</span>
    </div>
    <div class="tag-feed" id="tagFeed"><span>아직 인식된 태그가 없습니다.</span></div>
  </section>

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
          <div class="slot-name">쫀득초코칩 태그 전송</div>
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
        <div class="slot-name">쫀득초코칩</div>
        <div class="slot-uid">UID 0B71E55D</div>
      </button>

      <button type="button" class="slot-card" onclick="notifyBoxPlaced(2, '0B71E75D')">
        <div class="slot-top">
          <span class="slot-tag">SLOT 02</span>
          <span class="slot-action-label">DISPATCH</span>
        </div>
        <div class="slot-name">복숭아녹차 340ml (페트병)</div>
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
        <h2 class="section-title">15×15 작업 영역 · 물품 위치</h2>
      </div>
      <span class="section-meta" id="cellLabel">셀 선택</span>
    </div>

    <div class="grid-frame">
      <svg class="area-svg" id="areaSvg" xmlns="http://www.w3.org/2000/svg" role="img"
           aria-label="꼭짓점 1-4로 만든 직사각형 작업 영역과 15x15 셀, 물품 테두리"></svg>
    </div>
    <p class="area-note" id="areaNote">작업 영역 보정을 불러오는 중...</p>
    <div class="item-list" id="itemList"></div>

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

    <div class="link-banner" id="linkBanner">로봇 PC 사이클 연결 상태 확인 중...</div>
    <div class="control-grid">
      <button type="button" class="ctrl-btn ctrl-primary" id="startBtn" onclick="sendStartOrResume()">
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
      <button type="button" class="ctrl-btn ctrl-estop" id="resetStopBtn" hidden onclick="sendControl('reset_stop')">
        비상 정지 해제 (RESET STOP)
      </button>
    </div>
    <p class="estop-note">로봇 PC의 사이클이 이 버튼을 감지하면 move_stop을 보냅니다. 통신이 끊기면 동작하지 않으므로
      펜던트 E-Stop을 대신하지 않습니다.</p>
  </section>
</main>

<div class="toast" id="toast"></div>

<script>
  let lastCompletedTaskId = null;
  let activeRow = -1;
  let activeCol = -1;

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
    // APK: MainActivity registers "GalaxyNativeBridge" with vibrate(ms: Long).
    const bridge = window.GalaxyNativeBridge;
    if (bridge && vibratePattern && vibratePattern.length) {
      const total = vibratePattern.filter((_, i) => i % 2 === 0).reduce((a, b) => a + b, 0);
      try { bridge.vibrate(total); } catch (_) {}
    }
    clearTimeout(window.__toastTimer);
    window.__toastTimer = setTimeout(() => el.classList.remove('show'), 2400);
  }

  // ---- Work area: 4 taught corners (BASE mm) drawn to scale, 15x15 cells, item outlines ----
  const SVG_NS = 'http://www.w3.org/2000/svg';
  let area = null;          // GET /api/v1/mobile/work-area
  let frame = null;         // BASE mm -> drawing mm (origin corner 1, x along 1->2, y toward 4)
  let liveDepth = null;     // GET /api/robot/pick/depth-objects (same web server), if available
  let liveDepthError = null;
  let selectedProduct = null;

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1]]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1]; }

  function buildFrame(corners) {
    const o = corners[0];
    const d = sub(corners[1], o);
    const len = Math.hypot(d[0], d[1]) || 1;
    const ex = [d[0] / len, d[1] / len];
    let ey = [-ex[1], ex[0]];
    if (dot(sub(corners[3], o), ey) < 0) ey = [ex[1], -ex[0]];
    return p => { const v = sub(p, o); return [dot(v, ex), dot(v, ey)]; };
  }

  function el(name, attrs, text) {
    const node = document.createElementNS(SVG_NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function pts(list) { return list.map(p => frame(p).map(v => v.toFixed(1)).join(',')).join(' '); }

  function cellQuad(r, c) {
    const L = area.lattice_base_mm;
    return [L[r][c], L[r][c + 1], L[r + 1][c + 1], L[r + 1][c]];
  }

  function insideQuad(p, quad) {
    let sign = 0;
    for (let i = 0; i < 4; i++) {
      const a = quad[i], b = quad[(i + 1) % 4];
      const cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
      if (Math.abs(cross) < 1e-9) continue;
      const s = cross > 0 ? 1 : -1;
      if (sign === 0) sign = s; else if (s !== sign) return false;
    }
    return true;
  }

  function cellOf(base) {
    if (!area) return null;
    for (let r = 0; r < area.rows; r++)
      for (let c = 0; c < area.cols; c++)
        if (insideQuad(base, cellQuad(r, c))) return {row: r, col: c};
    return null;
  }

  function cellId(cell) {
    return cell ? `R${String(cell.row).padStart(2, '0')}_C${String(cell.col).padStart(2, '0')}` : '영역 밖';
  }

  // Rotated rectangle of the object's footprint in BASE: short side along short_axis_yaw_deg.
  function footprintCorners(item) {
    const [x, y] = item.base;
    const fp = item.footprint_mm || [60, 60];
    const th = (item.short_axis_yaw_deg || 0) * Math.PI / 180;
    const u = [Math.cos(th), Math.sin(th)], v = [-Math.sin(th), Math.cos(th)];
    const hs = fp[0] / 2, hl = fp[1] / 2;
    return [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([a, b]) =>
      [x + a * hs * u[0] + b * hl * v[0], y + a * hs * u[1] + b * hl * v[1]]);
  }

  function currentItems() {
    const zones = area ? area.zones : {};
    const names = area ? area.product_names : {};
    const byZone = {};
    if (liveDepth && Array.isArray(liveDepth.objects)) {
      for (const o of liveDepth.objects) {
        if (!o.inside || !o.base || !o.corner) continue;
        const z = String(o.corner);
        if (byZone[z]) continue;  // objects are sorted largest first: keep the largest per zone
        byZone[z] = {zone: o.corner, product: zones[z], base: o.base, footprint_mm: o.footprint_mm,
                     short_axis_yaw_deg: o.short_axis_yaw_deg, height_mm: o.height_mm, source: 'live'};
      }
    }
    const reported = area && area.reported_items ? area.reported_items.items || [] : [];
    for (const it of reported) {
      const z = String(it.zone);
      if (!byZone[z]) byZone[z] = {...it, source: 'reported'};
    }
    return Object.keys(zones).sort().map(z => ({zone: Number(z), product: zones[z], name: names[z] || zones[z],
                                                 ...(byZone[z] || {}), found: !!byZone[z]}));
  }

  function renderArea() {
    const svg = document.getElementById('areaSvg');
    svg.innerHTML = '';
    if (!area) return;
    const corners = area.corners_base_mm;
    frame = buildFrame(corners);
    const drawn = corners.map(frame);
    const pad = 34;
    const xs = drawn.map(p => p[0]), ys = drawn.map(p => p[1]);
    const minX = Math.min(...xs) - pad, minY = Math.min(...ys) - pad;
    const w = Math.max(...xs) - Math.min(...xs) + 2 * pad, h = Math.max(...ys) - Math.min(...ys) + 2 * pad;
    svg.setAttribute('viewBox', `${minX.toFixed(1)} ${minY.toFixed(1)} ${w.toFixed(1)} ${h.toFixed(1)}`);
    const items = currentItems();
    const itemCells = new Set();
    items.forEach(it => { if (it.found) { const c = cellOf(it.base); if (c) itemCells.add(`${c.row}_${c.col}`); } });

    for (let r = 0; r < area.rows; r++) {
      for (let c = 0; c < area.cols; c++) {
        const quad = cellQuad(r, c);
        if (quad.some(p => !p)) continue;
        let cls = 'cell';
        if (itemCells.has(`${r}_${c}`)) cls += ' item';
        if (r === activeRow && c === activeCol) cls += ' active';
        const poly = el('polygon', {points: pts(quad), class: cls});
        poly.addEventListener('click', () => selectGridCell(r, c));
        svg.appendChild(poly);
      }
    }
    svg.appendChild(el('polygon', {points: pts(corners), class: 'outline'}));

    // Edge lengths: the area is a rectangle, so each 15x15 cell is a rectangle too.
    const mid = (a, b) => frame([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
    const top = mid(corners[0], corners[1]);
    svg.appendChild(el('text', {x: top[0], y: top[1] - 12, 'text-anchor': 'middle', class: 'dim-label'},
                       `1-2 ${area.size_mm.col_axis_1_2} mm`));
    const left = mid(corners[0], corners[3]);
    svg.appendChild(el('text', {x: left[0] - 12, y: left[1], 'text-anchor': 'middle', class: 'dim-label',
                                transform: `rotate(-90 ${left[0] - 12} ${left[1]})`},
                       `1-4 ${area.size_mm.row_axis_1_4} mm`));

    for (const it of items) {
      if (!it.found) continue;
      const box = footprintCorners(it);
      const cls = 'item-box' + (it.source === 'reported' ? ' reported' : '');
      const poly = el('polygon', {points: pts(box), class: cls});
      poly.addEventListener('click', () => focusItem(it));
      svg.appendChild(poly);
      const c = frame(it.base);
      svg.appendChild(el('circle', {cx: c[0], cy: c[1], r: 3.2, class: 'item-center'}));
      svg.appendChild(el('text', {x: c[0], y: c[1] - 8, 'text-anchor': 'middle', class: 'item-label'},
                         `${it.zone} ${it.name}`));
    }

    drawn.forEach((p, i) => {
      svg.appendChild(el('circle', {cx: p[0], cy: p[1], r: 11, class: 'corner-dot'}));
      svg.appendChild(el('text', {x: p[0], y: p[1] + 4.5, 'text-anchor': 'middle', class: 'corner-num'}, String(i + 1)));
    });
    renderItemList(items);
  }

  function renderItemList(items) {
    const list = document.getElementById('itemList');
    list.innerHTML = '';
    for (const it of items) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'item-row';
      const cell = it.found ? cellOf(it.base) : null;
      const meta = it.found
        ? `X ${it.base[0].toFixed(1)} · Y ${it.base[1].toFixed(1)}` +
          (it.height_mm ? ` · H ${Number(it.height_mm).toFixed(0)}` : '') +
          (it.footprint_mm ? ` · ${it.footprint_mm[0].toFixed(0)}×${it.footprint_mm[1].toFixed(0)} mm` : '') +
          (it.source === 'reported' ? ' · 로봇 최근 인식' : ' · 실시간')
        : '깊이 카메라에서 이 구역의 물품을 찾지 못했습니다';
      row.innerHTML = `<span class="item-zone">${it.zone}</span>` +
        `<span><div class="item-name"></div><div class="item-meta"></div></span>` +
        `<span class="item-cell">${it.found ? cellId(cell) : '-'}</span>`;
      row.querySelector('.item-name').textContent = it.name;
      row.querySelector('.item-meta').textContent = meta;
      if (it.found) row.addEventListener('click', () => focusItem(it));
      list.appendChild(row);
    }
  }

  function focusItem(it) {
    const cell = cellOf(it.base);
    selectedProduct = it.product;
    if (cell) selectGridCell(cell.row, cell.col, it.base, it.height_mm);
  }

  function renderAreaNote() {
    const note = document.getElementById('areaNote');
    if (!area) return;
    const msgs = [`꼭짓점 1→2 ${area.size_mm.col_axis_1_2} mm × 1→4 ${area.size_mm.row_axis_1_4} mm 직사각형 · ` +
                  `셀 ${area.cell_mm[0]}×${area.cell_mm[1]} mm (15×15)`];
    let warn = !area.calibration_verified;
    if (warn) msgs.push('검증되지 않은(MOCK) 보정입니다.');
    if (liveDepth) {
      if (liveDepth.revision && area.revision && liveDepth.revision !== area.revision) {
        msgs.push('카메라 보정 revision이 로봇 설정과 다릅니다 — 보정을 다시 내보내세요.');
        warn = true;
      } else {
        msgs.push('실선: 깊이 카메라 실시간 인식 · 점선: 로봇 최근 인식');
      }
    } else {
      msgs.push(`실시간 깊이 인식 없음${liveDepthError ? ` (${liveDepthError})` : ''} · 점선은 로봇 사이클이 마지막으로 인식한 위치`);
    }
    note.textContent = msgs.join(' ');
    note.classList.toggle('warn', warn);
  }

  async function loadWorkArea() {
    try {
      const res = await fetch('/api/v1/mobile/work-area?rows=15&cols=15', {cache: 'no-store'});
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || res.status);
      area = data;
      renderArea();
      renderAreaNote();
    } catch (err) {
      document.getElementById('areaNote').textContent = `작업 영역을 불러오지 못했습니다: ${err.message || err}`;
    }
  }

  async function loadLiveDepth() {
    if (document.hidden) return;
    try {
      const res = await fetch('/api/robot/pick/depth-objects', {cache: 'no-store', redirect: 'error'});
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      liveDepth = data;
      liveDepthError = null;
    } catch (err) {
      liveDepth = null;
      liveDepthError = String(err.message || err).slice(0, 80);
    }
    if (area) { renderArea(); renderAreaNote(); }
  }

  function renderGrid() { renderArea(); }

  async function selectGridCell(row, col, exactBase, heightMm) {
    activeRow = row;
    activeCol = col;
    renderArea();
    if (!area) return;
    const quad = cellQuad(row, col);
    const center = [quad.reduce((s, p) => s + p[0], 0) / 4, quad.reduce((s, p) => s + p[1], 0) / 4];
    const body = {base_xy: exactBase || center, rows: 15, cols: 15, product: selectedProduct || 'snack_pepero'};
    if (heightMm) body.measured_height_mm = Number(heightMm);
    selectedProduct = null;
    try {
      const res = await fetch('/api/v1/grid/locate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || '셀 좌표 계산 실패'); return; }
      if (data.grid_cell) {
        const c = data.grid_cell;
        document.getElementById('cellLabel').textContent =
          `${c.cell_id} · R${String(c.row + 1).padStart(2, '0')} C${String(c.col + 1).padStart(2, '0')}`;
        const center = c.cell_center_base_mm;
        document.getElementById('coarseXY').textContent =
          `${center[0].toFixed(1)}, ${center[1].toFixed(1)}`;
        const dx = c.fine_offset_mm[0].toFixed(1);
        const dy = c.fine_offset_mm[1].toFixed(1);
        document.getElementById('fineDelta').textContent =
          `${dx >= 0 ? '+' : ''}${dx}, ${dy >= 0 ? '+' : ''}${dy}`;
        document.getElementById('safeGraspZ').textContent =
          `Z ${Number(data.grasp_height_info.grasp_z_mm).toFixed(1)} mm`;
        if (c.row !== activeRow || c.col !== activeCol) { activeRow = c.row; activeCol = c.col; renderArea(); }
      }
    } catch (_) {
      showToast('셀 좌표 요청 실패 — 서버 연결을 확인하세요.');
    }
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

  let nativeNfcMode = null;
  function updateScanModeUI(mode) {
    const isExt = mode === 'external_reader';
    // APK: turn the phone's NFC reader on/off with the mode (MainActivity.setNfcEnabled).
    const bridge = window.GalaxyNativeBridge;
    if (bridge && bridge.setNfcEnabled && nativeNfcMode !== mode) {
      try { bridge.setNfcEnabled(!isExt); } catch (_) {}
    }
    nativeNfcMode = mode;
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
        if (data.robot_connected) {
          showToast(`SLOT 0${slot} 배치 확인 · 로봇 출동`, [60, 40, 90]);
        } else {
          showToast(`SLOT 0${slot} 작업 등록 · 로봇 PC 사이클 미연결`, [40]);
          setLinkBanner(data.message, false);
        }
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

  // APK: MainActivity calls this when the phone's NFC reader sees a tag.
  window.onNativeNfcTag = uid => sendPhoneNfc(String(uid).toUpperCase(), 1);

  async function startWebNfc() {
    const bridge = window.GalaxyNativeBridge;
    if (bridge && bridge.promptNfcScan) {
      try { bridge.promptNfcScan(); } catch (_) {}
      return;
    }
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

  let lastStatus = null;
  let lastAckSeq = null;

  function setLinkBanner(text, ok) {
    const b = document.getElementById('linkBanner');
    b.textContent = text;
    b.classList.toggle('ok', ok === true);
    b.classList.toggle('down', ok === false);
  }

  function sendStartOrResume() {
    // Paused -> resume the running cycle; otherwise ask an idle cycle to start.
    sendControl(lastStatus && lastStatus.paused ? 'resume' : 'start');
  }

  async function sendControl(command) {
    try {
      const res = await fetch('/api/v1/mobile/control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command})
      });
      let data = {};
      try { data = await res.json(); } catch (_) {}
      if (res.ok) {
        const pattern = command === 'emergency_stop' ? [250, 80, 250] : [45];
        showToast(data.robot_connected ? (data.message || `명령 전송: ${command}`)
                                       : `${command} 저장됨 · 로봇 PC 사이클 미연결`, pattern);
        if (!data.robot_connected && data.message) setLinkBanner(data.message, false);
      } else {
        // 409 (E-stop active) etc. used to fail silently; always tell the operator why.
        const detail = typeof data.detail === 'string' ? data.detail : `명령 거부 (HTTP ${res.status})`;
        showToast(detail, [30, 60, 30]);
      }
      pollStatus();
    } catch (_) {
      showToast('제어 명령 전송 실패 — 서버 연결을 확인하세요.');
    }
  }

  function renderRobotLink(data) {
    const link = data.robot_link;
    document.getElementById('resetStopBtn').hidden = !data.emergency_stopped;
    document.getElementById('startBtn').textContent = data.paused && !data.emergency_stopped ? '재개' : '작업 시작 · 재개';
    if (data.robot_connected && link) {
      const modes = {remote_rfid: '태그 대기 모드', remote_trigger: '리모컨 출동 모드', orchestrator: '연속 실행 모드'};
      setLinkBanner(`로봇 PC 사이클 연결됨 (${modes[link.mode] || link.mode}) · ${link.state || ''}` +
                    (link.message ? ` — ${link.message}` : ''), true);
      if (link.ack_seq && link.ack_seq !== lastAckSeq) {
        if (lastAckSeq !== null && link.message) showToast(link.message, [35]);
        lastAckSeq = link.ack_seq;
      }
    } else {
      setLinkBanner('로봇 PC 사이클 미연결 — 비상 정지 외 버튼은 로봇 PC에서 ' +
                    'project_cycle.py --api ... (--remote-rfid 또는 --remote-trigger) 를 실행해야 로봇이 움직입니다.', false);
    }
  }

  const SCAN_SOURCES = {remote_reader: 'Windows 리더기', phone_nfc: '휴대폰 NFC', hardware: '로봇 PC 리더기', hardware_pcsc: '로봇 PC 리더기', preset: '대시보드 버튼'};
  let lastScanSeq = null;
  function renderLastScan(scan) {
    const box = document.getElementById('tagFeed');
    if (!scan) return;
    const when = new Date(scan.timestamp).toLocaleTimeString('ko-KR', {hour12: false});
    const source = SCAN_SOURCES[scan.source] || scan.source;
    const uid = scan.uid || scan.raw_uid;
    const title = scan.accepted ? (scan.product_name || '등록 상품') + ' → ' + (scan.target_box_id || '') : '인식 거부';
    const detail = scan.accepted ? '작업 등록됨' : (scan.error || '등록되지 않은 태그');
    box.replaceChildren(...[
      ['strong', title], ['span', 'UID ' + uid, 'tag-uid'], ['span', detail + ' · ' + source]
    ].map(([tag, text, cls]) => { const el = document.createElement(tag); el.textContent = text; if (cls) el.className = cls; return el; }));
    box.className = 'tag-feed ' + (scan.accepted ? 'ok' : 'bad');
    document.getElementById('tagFeedTime').textContent = when;
    if (lastScanSeq !== null && scan.seq !== lastScanSeq) {
      void box.offsetWidth;  // restart the highlight
      box.classList.add('fresh');
      showToast(scan.accepted ? `태그 인식: ${scan.product_name || uid}` : `태그 거부: ${uid}`, scan.accepted ? [60] : [60, 60, 60]);
    }
    lastScanSeq = scan.seq;
  }

  async function pollStatus() {
    try {
      const res = await fetch('/api/v1/mobile/status', {cache: 'no-store'});
      if (!res.ok) return;
      const data = await res.json();
      lastStatus = data;
      document.getElementById('connText').textContent = `ONLINE · ${window.location.host || '127.0.0.1:8009'}`;
      const badge = document.getElementById('robotStateBadge');
      badge.textContent = data.robot_state;
      updateScanModeUI(data.scan_mode);
      renderRobotLink(data);

      const reported = data.work_items;
      if (area && JSON.stringify(reported || null) !== JSON.stringify(area.reported_items || null)) {
        area.reported_items = reported;
        renderArea();
        renderAreaNote();
      }

      renderLastScan(data.last_scan);

      if (data.last_completed_event && data.last_completed_event.task_id !== lastCompletedTaskId) {
        lastCompletedTaskId = data.last_completed_event.task_id;
        showToast(`피킹 및 상자 적재 완료 (${data.last_completed_event.task_id})`, [180, 90, 220]);
      }
    } catch (_) {
      document.getElementById('connText').textContent = 'OFFLINE · RECONNECTING';
    }
  }

  loadWorkArea().then(loadLiveDepth);
  pollStatus();
  setInterval(pollStatus, 1000);
  setInterval(loadLiveDepth, 3000);
</script>
</body>
</html>
"""
