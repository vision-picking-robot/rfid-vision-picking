// Packing-box webcam on the dashboard (server: web/app/box_check.py).
// The robot cycle takes a reference picture before the pick and checks the box after placing each item.
const BADGE = {landed: ["clear", "투입 확인"], missing: ["hold", "투입 실패"], uncertain: ["warning", "판정 불가"]};

const svg = (tag, attrs, text) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
};
const esc = text => String(text ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const pct = value => value == null ? "—" : `${(value * 100).toFixed(1)}%`;

export function connectBoxCheckPanel(panel) {
  const $ = name => panel.querySelector(`[data-box="${name}"]`);
  let status = null, stopped = false, frameBusy = false;
  let editing = false, points = [], showLast = false, lastSeen = null, flashUntil = 0;

  async function call(path, body, method = "POST") {
    const response = await fetch("/api/box-check/" + path, {method, cache: "no-store",
      headers: body ? {"Content-Type": "application/json"} : {}, body: body ? JSON.stringify(body) : undefined});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "요청 실패");
    return data;
  }

  function renderOverlay() {
    const overlay = $("overlay");
    overlay.replaceChildren();
    const W = 1000, H = 750;
    if (showLast) return;  // the saved picture already has the area and the changed blob drawn in
    const poly = status.box || [];
    overlay.append(svg("polygon", {points: poly.map(([x, y]) => `${x * W},${y * H}`).join(" "), class: "zone active"}));
    const cx = poly.reduce((s, p) => s + p[0], 0) / (poly.length || 1) * W;
    const cy = poly.reduce((s, p) => s + p[1], 0) / (poly.length || 1) * H;
    overlay.append(svg("text", {x: cx, y: cy, class: "zone-label active"}, "상자 영역"));
    if (editing && points.length) {
      overlay.append(svg("polyline", {points: points.map(([x, y]) => `${x * W},${y * H}`).join(" "), class: "zone-draft"}));
      for (const [x, y] of points) overlay.append(svg("circle", {cx: x * W, cy: y * H, r: 7, class: "zone-point"}));
    }
  }

  function render() {
    if (!status) return;
    const last = status.last;
    const [cls, label] = last ? BADGE[last.verdict] || ["", last.verdict] : ["", "확인 대기"];
    const badge = $("badge");
    badge.textContent = label;
    badge.className = "safety-badge " + cls;
    $("verdict").textContent = last ? `${last.time} · ${last.text}` : "—";
    $("change").textContent = last ? `${pct(last.change)} (기준 ${pct(last.min_change)})` : "—";
    $("reference").textContent = status.reference ? `${status.reference}${status.reference_label ? " · " + status.reference_label : ""}` : "없음";
    const cam = status.camera || {};
    $("camera").textContent = cam.ok ? `${cam.index}번 · ${cam.fps || "—"} fps` : (cam.message || "꺼짐");
    const banner = $("banner");
    banner.hidden = !(last && Date.now() < flashUntil);
    if (last) {
      banner.className = "safety-banner " + (last.ok ? "resume" : last.verdict === "uncertain" ? "warning" : "hold");
      banner.textContent = `${last.label ? last.label + " · " : ""}${last.text}${last.ok ? "" : " — 기록하고 계속 진행합니다"}`;
    }
    const viewButton = panel.querySelector('[data-box-action="view"]');
    viewButton.setAttribute("aria-pressed", String(showLast));
    viewButton.textContent = showLast ? "실시간 영상으로" : "마지막 판정 사진";
    const events = (status.history || []).slice(-5).reverse();
    $("events").innerHTML = events.map(e => `<li><time>${esc(e.time)}</time><span class="event-type">${
      esc((BADGE[e.verdict] || ["", e.verdict])[1])}</span><span>${esc(e.label || "수동 확인")} · 변화 ${pct(e.change)}</span></li>`).join("");
    renderOverlay();
  }

  async function poll() {
    if (stopped) return;
    try {
      status = await call("status", null, "GET");
      const id = status.last?.id ?? null;
      if (lastSeen !== null && id !== null && id !== lastSeen) flashUntil = Date.now() + 8000;  // a new check came in
      lastSeen = id;
      render();
    } catch { /* server restarting */ }
    if (!stopped) setTimeout(poll, 700);
  }

  async function frame() {
    if (stopped) return;
    if (!frameBusy) {
      frameBusy = true;
      try {
        const url = showLast ? `/api/box-check/image/after.jpg?id=${status?.last?.id ?? 0}` : "/api/box-check/frame.jpg";
        const response = await fetch(url, {cache: "no-store"});
        const img = $("image");
        if (response.status === 200) {
          const src = URL.createObjectURL(await response.blob());
          img.onload = () => URL.revokeObjectURL(src);
          img.src = src;
          img.hidden = false;
          $("empty").hidden = true;
        } else {
          img.hidden = true;
          $("empty").hidden = false;
          $("message").textContent = showLast ? "아직 판정 사진이 없습니다" : status?.camera?.message || "웹캠 연결 대기 · 아래에서 웹캠을 선택하세요";
        }
      } catch { /* ignore */ }
      frameBusy = false;
    }
    if (!stopped) setTimeout(frame, showLast ? 1000 : 150);
  }

  async function loadCameras() {
    const select = $("cameraSelect");
    try {
      const {devices} = await call("cameras", null, "GET");
      const current = status?.camera?.index;
      select.innerHTML = `<option value="">끄기</option>` + devices.map(d =>
        `<option value="${d.index}" ${d.index === current ? "selected" : ""}>${esc(d.name)} (${d.index})</option>`).join("");
    } catch { select.innerHTML = `<option value="">목록 없음</option>`; }
  }

  panel.addEventListener("click", async event => {
    const button = event.target.closest("[data-box-action]");
    const action = button?.dataset.boxAction;
    if (!action) return;
    try {
      if (action === "area") {
        editing = !editing; points = []; showLast = false;
        button.setAttribute("aria-pressed", String(editing));
        $("areaEdit").hidden = !editing;
        panel.toggleAttribute("data-editing", editing);
      } else if (action === "area-reset") {
        status = await call("box", null, "DELETE");
      } else if (action === "reference") {
        button.disabled = true;
        status = await call("reference", {label: "수동"}).finally(() => { button.disabled = false; });
      } else if (action === "verify") {
        button.disabled = true;
        await call("verify", {label: "수동 확인", keep_reference: true}).finally(() => { button.disabled = false; });
        flashUntil = Date.now() + 8000;
        status = await call("status", null, "GET");
        lastSeen = status.last?.id ?? null;
      } else if (action === "view") {
        showLast = !showLast;
      }
      render();
    } catch (error) {
      $("verdict").textContent = error.message;
    }
  });

  $("view").addEventListener("click", async event => {
    if (!editing) return;
    const rect = $("view").getBoundingClientRect();
    points.push([Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
                 Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height))].map(v => Math.round(v * 1000) / 1000));
    $("areaHint").textContent = `상자 영역 · 꼭짓점 ${points.length}/4`;
    if (points.length === 4) {
      const done = points; points = [];
      try {
        status = await call("box", {points: done});
        $("areaHint").textContent = "상자 영역 저장됨 · 기준 사진을 다시 찍으세요 ('상자 영역 설정'을 다시 눌러 마침)";
      } catch (error) { $("areaHint").textContent = error.message; }
    }
    render();
  });

  $("cameraSelect").addEventListener("change", async event => {
    const value = event.target.value;
    try { status = await call("camera", {index: value === "" ? null : Number(value)}); render(); }
    catch (error) { $("verdict").textContent = error.message; }
  });

  void poll().then(loadCameras);
  void frame();
  return () => { stopped = true; };
}
