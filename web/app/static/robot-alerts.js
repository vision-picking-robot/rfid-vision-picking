// Operator alerts on every page: grasp retry / failure reported by the robot cycle (GET /api/v1/mobile/status).
// Retry = amber, shown a few seconds. Failure = red, stays until the stop is released ([정지 해제]).
const POLL_MS = 1500;
let seen = null, timer = null, banner = null;

function ensureBanner() {
  if (banner) return banner;
  banner = document.createElement("div");
  banner.className = "robot-alert";
  banner.setAttribute("role", "alert");
  banner.hidden = true;
  banner.innerHTML = '<div><strong data-alert="title"></strong><p data-alert="text"></p></div>' +
    '<button type="button" data-alert="close" aria-label="알림 닫기">닫기</button>';
  banner.querySelector('[data-alert="close"]').addEventListener("click", hide);
  document.body.append(banner);
  return banner;
}

function hide() {
  clearTimeout(timer);
  timer = null;
  if (banner) banner.hidden = true;
}

function show(level, title, text, holdMs) {
  const el = ensureBanner();
  el.className = "robot-alert " + level;
  el.querySelector('[data-alert="title"]').textContent = title;
  el.querySelector('[data-alert="text"]').textContent = text;
  el.hidden = false;
  clearTimeout(timer);
  timer = holdMs ? setTimeout(hide, holdMs) : null;
}

async function poll() {
  try {
    const response = await fetch("/api/v1/mobile/status", {cache: "no-store"});
    if (response.ok) {
      const data = await response.json();
      const alerts = data.alerts || [];
      const newest = alerts.length ? alerts[alerts.length - 1].seq : 0;
      if (seen === null) seen = newest;  // alerts from before this page opened are not replayed
      for (const alert of alerts.filter(a => a.seq > seen)) {
        if (alert.kind === "grasp_failed") {
          show("danger", "파지 실패 · 로봇 정지", alert.message + " — 물건과 그리퍼를 확인한 뒤 [정지 해제]를 누르세요.", 0);
        } else {
          show("warning", "파지 실패 · 다시 시도합니다", alert.message, 8000);
        }
      }
      seen = Math.max(seen, newest);
      const last = alerts[alerts.length - 1];
      if (banner && !banner.hidden && banner.classList.contains("danger") && !timer
          && !(data.emergency_stopped && last && last.kind === "grasp_failed")) hide();
    }
  } catch {
    // the server is restarting or this server has no robot API
  }
  setTimeout(poll, POLL_MS);
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", poll);
else poll();
