// Work-area safety webcam on the dashboard (server: web/app/safety.py).
// Warning: 3 s beep. Hold: the robot stops. Clear for 3 s: "안전구역 확보" is spoken and the robot resumes.
const STATES = {idle: "감시 대기", clear: "감시 중", warning: "작업자 접근 경고", hold: "안전 정지"};
const SOUND_KEY = "e0509.safety-sound";

function storedSound() {
  try { return localStorage.getItem(SOUND_KEY) === "1"; } catch { return false; }
}
function storeSound(on) {
  try { localStorage.setItem(SOUND_KEY, on ? "1" : "0"); } catch { /* private window */ }
}

class Alarm {
  constructor() { this.ctx = null; this.timers = []; }
  unlock() {
    this.ctx ??= new (window.AudioContext || window.webkitAudioContext)();
    return this.ctx.resume();
  }
  tone(freq, start, length, gain = 0.25) {
    const ctx = this.ctx, osc = ctx.createOscillator(), amp = ctx.createGain();
    osc.type = "square"; osc.frequency.value = freq;
    amp.gain.setValueAtTime(0, ctx.currentTime + start);
    amp.gain.linearRampToValueAtTime(gain, ctx.currentTime + start + 0.01);
    amp.gain.setValueAtTime(gain, ctx.currentTime + start + length - 0.02);
    amp.gain.linearRampToValueAtTime(0, ctx.currentTime + start + length);
    osc.connect(amp).connect(ctx.destination);
    osc.start(ctx.currentTime + start); osc.stop(ctx.currentTime + start + length + 0.02);
    this.timers.push(osc);
  }
  warning(seconds = 3) {            // 1st stage: beep for ~3 s
    if (!this.ctx) return;
    this.silence();
    for (let t = 0; t < seconds - 0.1; t += 0.5) this.tone(1046, t, 0.25);
  }
  stop() {                          // 2nd stage: two low tones as the robot stops
    if (!this.ctx) return;
    this.silence();
    this.tone(392, 0, 0.35); this.tone(330, 0.45, 0.5);
  }
  silence() { for (const osc of this.timers.splice(0)) { try { osc.stop(); } catch { /* already stopped */ } } }
  say(text) {
    const synth = window.speechSynthesis;
    if (!synth || !window.SpeechSynthesisUtterance) return;
    synth.cancel();
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "ko-KR"; speech.rate = 1.0;
    synth.speak(speech);
  }
}

const svg = (tag, attrs, text) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
};

export function connectSafetyPanel(panel) {
  const $ = name => panel.querySelector(`[data-safety="${name}"]`);
  const alarm = new Alarm();
  let soundOn = false, lastSeq = null, status = null, stopped = false;
  let editing = false, editZone = 1, points = [], resumedAt = 0, frameBusy = false;

  const soundButton = panel.querySelector('[data-safety-action="sound"]');
  function renderSound() {
    soundButton.setAttribute("aria-pressed", String(soundOn));
    soundButton.textContent = soundOn ? "경고음·음성 켜짐" : "경고음·음성 켜기";
  }
  // Browsers only allow sound after a click on the page, so the operator turns it on once.
  soundOn = storedSound();
  if (soundOn) {
    const resume = () => { void alarm.unlock().catch(() => {}); };
    document.addEventListener("pointerdown", resume, {once: true});
    document.addEventListener("keydown", resume, {once: true});
  }
  renderSound();

  async function post(path, body, method = "POST") {
    const response = await fetch("/api/safety/" + path, {method, cache: "no-store",
      headers: body ? {"Content-Type": "application/json"} : {}, body: body ? JSON.stringify(body) : undefined});
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "요청 실패");
    status = await response.json();
    render();
  }

  function announce(entry) {
    if (entry.kind === "resume") resumedAt = Date.now();
    if (!soundOn) return;
    if (entry.kind === "warning") alarm.warning(status?.warn_s || 3);
    else if (entry.kind === "warning_cleared") alarm.silence();
    else if (entry.kind === "hold") alarm.stop();
    else if (entry.kind === "resume") { alarm.silence(); alarm.say("안전구역 확보. 로봇을 다시 가동합니다."); }
  }

  function renderOverlay() {
    const overlay = $("overlay");
    overlay.replaceChildren();
    const W = 1000, H = 750;
    const active = String(status.zone || "");
    for (const [zone, poly] of Object.entries(status.zones || {})) {
      const isActive = zone === active && (status.watching || status.state === "hold");
      const cls = isActive ? `zone active ${status.state}` : "zone";
      overlay.append(svg("polygon", {points: poly.map(([x, y]) => `${x * W},${y * H}`).join(" "), class: cls}));
      const cx = poly.reduce((s, p) => s + p[0], 0) / poly.length * W, cy = poly.reduce((s, p) => s + p[1], 0) / poly.length * H;
      overlay.append(svg("text", {x: cx, y: cy, class: "zone-label" + (isActive ? " active" : "")}, `구역 ${zone}`));
    }
    for (const box of status.persons || []) {
      const [x1, y1, x2, y2, conf] = box;
      overlay.append(svg("rect", {x: x1 * W, y: y1 * H, width: (x2 - x1) * W, height: (y2 - y1) * H, class: "person"}));
      overlay.append(svg("text", {x: x1 * W + 6, y: y1 * H + 22, class: "person-label"}, `작업자 ${Math.round(conf * 100)}%`));
    }
    if (editing && points.length) {
      overlay.append(svg("polyline", {points: points.map(([x, y]) => `${x * W},${y * H}`).join(" "), class: "zone-draft"}));
      for (const [x, y] of points) overlay.append(svg("circle", {cx: x * W, cy: y * H, r: 7, class: "zone-point"}));
    }
  }

  function render() {
    if (!status) return;
    const state = status.state;
    panel.dataset.state = state;
    const badge = $("badge");
    badge.textContent = (STATES[state] || state) + (status.zone && state !== "idle" ? ` · 구역 ${status.zone}` : "");
    badge.className = "safety-badge " + state;
    $("phase").textContent = status.watching
      ? `구역 ${status.zone ?? "전체"} · ${status.product || "물품"} 피킹 접근 중`
      : state === "hold" ? `구역 ${status.zone} · 정지 유지` : "대기 · 피킹 접근 때만 감시";
    $("stage").textContent = {
      idle: "정상", clear: "정상",
      warning: `1차 경고 · ${Math.ceil(status.warn_left ?? 0)}초 후 정지`,
      hold: status.clear_left == null ? "2차 정지 · 작업자 이탈 대기" : `2차 정지 · ${Math.ceil(status.clear_left)}초 후 재가동`,
    }[state] || state;
    $("people").textContent = status.simulated ? "가상 작업자 1명 (리허설)"
      : status.persons.length ? `${status.persons.length}명 감지 · 구역 근처 ${status.near}명` : "없음";
    const cam = status.camera || {};
    $("camera").textContent = cam.ok ? `${cam.detector === "yolo" ? "YOLO" : cam.detector === "hog" ? "OpenCV" : cam.detector} · ${cam.fps || "—"} fps` : (cam.message || "꺼짐");
    const banner = $("banner");
    const recentResume = Date.now() - resumedAt < 4000;
    banner.hidden = !(state === "warning" || state === "hold" || recentResume);
    banner.className = "safety-banner " + (recentResume && state !== "hold" && state !== "warning" ? "resume" : state);
    banner.textContent = state === "warning" ? `작업자 접근 · ${Math.ceil(status.warn_left ?? 0)}초 안에 벗어나지 않으면 로봇 정지`
      : state === "hold" ? (status.clear_left == null ? "안전 정지 · 작업자가 구역에서 벗어나면 재가동" : `안전 정지 · ${Math.ceil(status.clear_left)}초 후 재가동`)
      : "안전구역 확보 · 로봇 재가동";
    const sim = panel.querySelector('[data-safety-action="simulate"]');
    sim.setAttribute("aria-pressed", String(status.simulated));
    sim.textContent = status.simulated ? "가상 작업자 퇴장" : "가상 작업자 진입";
    const events = (status.events || []).slice(-4).reverse();
    $("events").innerHTML = events.map(e => `<li><time>${e.time}</time><span class="event-type">${
      {warning: "경고", warning_cleared: "해제", hold: "정지", resume: "재가동"}[e.kind] || e.kind}</span><span>${e.text}${e.zone ? ` · 구역 ${e.zone}` : ""}</span></li>`).join("");
    renderOverlay();
  }

  async function poll() {
    if (stopped) return;
    try {
      const response = await fetch("/api/safety/status", {cache: "no-store"});
      if (response.ok) {
        status = await response.json();
        const fresh = (status.announcements || []).filter(a => lastSeq !== null && a.seq > lastSeq);
        lastSeq = Math.max(lastSeq ?? 0, ...(status.announcements || []).map(a => a.seq));
        for (const entry of fresh) announce(entry);
        render();
      }
    } catch { /* server restarting */ }
    if (!stopped) setTimeout(poll, 400);
  }

  async function frame() {
    if (stopped) return;
    if (!frameBusy) {
      frameBusy = true;
      try {
        const response = await fetch("/api/safety/frame.jpg", {cache: "no-store"});
        const img = $("image");
        if (response.status === 200) {
          const url = URL.createObjectURL(await response.blob());
          img.onload = () => URL.revokeObjectURL(url);
          img.src = url;
          img.hidden = false;
          $("empty").hidden = true;
        } else {
          img.hidden = true;
          $("empty").hidden = false;
          $("message").textContent = status?.camera?.message || "웹캠 연결 대기 · 아래에서 웹캠을 선택하세요";
        }
      } catch { /* ignore */ }
      frameBusy = false;
    }
    if (!stopped) setTimeout(frame, 150);
  }

  async function loadCameras() {
    const select = $("cameraSelect");
    try {
      const {devices} = await fetch("/api/safety/cameras", {cache: "no-store"}).then(r => r.json());
      const current = status?.camera?.index;
      select.innerHTML = `<option value="">끄기</option>` + devices.map(d =>
        `<option value="${d.index}" ${d.index === current ? "selected" : ""}>${d.name} (${d.index})</option>`).join("");
    } catch { select.innerHTML = `<option value="">목록 없음</option>`; }
  }

  panel.addEventListener("click", async event => {
    const action = event.target.closest("[data-safety-action]")?.dataset.safetyAction;
    const zoneButton = event.target.closest("[data-safety-zone]");
    try {
      if (action === "sound") {
        soundOn = !soundOn;
        storeSound(soundOn);
        if (soundOn) { await alarm.unlock(); alarm.tone(1046, 0, 0.12, 0.15); }
        else alarm.silence();
        renderSound();
      } else if (action === "simulate") {
        await post("simulate", {person: !status?.simulated});
      } else if (action === "zones") {
        editing = !editing; points = [];
        event.target.setAttribute("aria-pressed", String(editing));
        $("zoneEdit").hidden = !editing;
        panel.toggleAttribute("data-editing", editing);
        render();
      } else if (action === "zones-reset") {
        await post("zones", null, "DELETE");
      } else if (zoneButton) {
        editZone = Number(zoneButton.dataset.safetyZone); points = [];
        for (const b of panel.querySelectorAll("[data-safety-zone]")) b.setAttribute("aria-pressed", String(b === zoneButton));
        render();
      }
    } catch (error) {
      $("stage").textContent = error.message;
    }
  });

  $("view").addEventListener("click", async event => {
    if (!editing) return;
    const rect = $("view").getBoundingClientRect();
    points.push([Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
                 Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height))].map(v => Math.round(v * 1000) / 1000));
    $("zoneHint").textContent = `구역 ${editZone} · 꼭짓점 ${points.length}/4`;
    if (points.length === 4) {
      const done = points; points = [];
      await post("zones", {zone: editZone, points: done}).catch(error => { $("stage").textContent = error.message; });
      $("zoneHint").textContent = `구역 ${editZone} 저장됨 · 다른 구역을 고르거나 '구역 설정'을 다시 눌러 마치세요`;
    }
    render();
  });

  $("cameraSelect").addEventListener("change", async event => {
    const value = event.target.value;
    await post("camera", {index: value === "" ? null : Number(value)}).catch(error => { $("stage").textContent = error.message; });
  });

  void poll().then(loadCameras);
  void frame();
  return () => { stopped = true; alarm.silence(); };
}
