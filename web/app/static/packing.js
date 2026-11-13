import { currentDestination, icon } from "./station-nav.js";
import { demo, record } from "./packing-demo.js";
import { connectDashboardCamera } from "./dashboard-camera.js";
import { connectSafetyPanel } from "./safety-panel.js";
import { BrowserVoice } from "./browser-voice.js";
import { ClapWake } from "./clap-wake.js";

const root = document.getElementById("packing-station");
const view = document.getElementById("demo-view");
let selectedOrder = 123;
let selectedSku = new URLSearchParams(location.search).get("sku") || "PK-001";
let selectedUserId = null;
let logKind = "전체";
let activity = [];
let form = "";
let voiceOpen = false;
let voiceStatus = null;
let voiceSerial = 0;
const browserVoice = new BrowserVoice(status => {
  ++voiceSerial; voiceStatus = status;
  // A finished conversation (silence, "대화 종료", error) goes back to waiting for a double clap.
  if (clapArmed && !browserVoice.active && !browserVoice.starting && !waking && ["idle", "error"].includes(status.state)) {
    void clapWake.arm().catch(error => { clapNote = error.message; renderVoice(); });
  }
  renderVoice();
});
// Double clap -> "음성 인식을 시작합니다" -> speech recognition, then back to the clap wait.
let clapArmed = false, clapNote = "", waking = false;
const clapWake = new ClapWake(() => void clapTriggered());
const WAKE_PHRASE = "음성 인식을 시작합니다";

function sayAndWait(text, timeoutMs = 4000) {
  return new Promise(resolve => {
    const synth = window.speechSynthesis;
    if (!synth || !window.SpeechSynthesisUtterance) return resolve();
    const speech = new SpeechSynthesisUtterance(text);
    speech.lang = "ko-KR";
    const done = () => { clearTimeout(timer); resolve(); };
    const timer = setTimeout(done, timeoutMs);
    speech.onend = speech.onerror = done;
    synth.speak(speech);
  });
}

async function clapTriggered() {
  if (!clapArmed || browserVoice.active || waking) return;
  waking = true;
  clapNote = "";
  voiceStatus = {...(voiceStatus || {}), state: "preparing"};
  renderVoice();
  try {
    await sayAndWait(WAKE_PHRASE);
    if (clapArmed) await browserVoice.start();
  } catch (error) {
    clapNote = error.message;
  } finally {
    waking = false;
    if (clapArmed && !browserVoice.active) void clapWake.arm().catch(error => { clapNote = error.message; });
    renderVoice();
  }
}
const voiceStates = {disabled: "음성 기능 꺼짐", idle: "호출 대기", preparing: "마이크 준비 중", preparing_reply: "Yuna 응답 준비 중",
  permission: "브라우저의 마이크 접근 창에서 허용을 눌러 주세요.", listening: "듣는 중", processing: "명령 처리 중", speaking: "Yuna 응답 중", stopping: "청취 중단 중", error: "음성 오류"};
let reply = "";
let confirmingOrder = false;
let station;
let signature = "";
let requestSerial = 0;
let pending = false;
let lastPlaceClick = -Infinity;
const api = "/api/packing";

async function request(path = "", method = "GET", body) {
  const response = await fetch(api + path, {
    method, cache: "no-store",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : "요청을 처리하지 못했습니다. 입력값과 서버 연결을 확인하세요.");
  }
  return response.json();
}

async function refresh() {
  const serial = ++requestSerial;
  const onLogs = currentDestination().id === "logs";
  const [next, records] = await Promise.all([request(), onLogs ? request("/logs") : null]);
  if (serial !== requestSerial) return;
  if (records) activity = records;
  const content = JSON.stringify([next, records]);
  if (content === signature) return;
  station = next;
  signature = content;
  if (!form && !pending) render();
}

const mainOrder = () => station.orders.find(o => o.number === 123);
const extraOrder = () => station.orders.some(o => o.number === 124);
const productBySku = sku => station.products.find(p => p.sku === sku);
const userForOrder = order => station.users.find(user => user.id === order.customer_id);
const currentUser = () => station.users.find(user => user.id === selectedUserId) || station.users[0];
const stockLink = sku => "/?sku=" + encodeURIComponent(sku) + "#stock";
const trainLink = sku => "/training?sku=" + encodeURIComponent(sku) + "#collect";
const orderItems = (order = mainOrder()) => order.items.map(i => ({...productBySku(i.sku), ...i}));
const packed = (order = mainOrder()) => order.items.filter(i => i.done).length;
const isPacked = () => mainOrder().state === "awaiting_dispatch";
const ORDER_STATES = {received: "주문 접수", awaiting_dispatch: "발송 대기", shipped: "발송 완료", delivered: "배송 완료"};
const ORDER_STEP = {received: 0, packing: 1, awaiting_dispatch: 2, shipped: 3, delivered: 4};
function orderStatus(order = mainOrder()) {
  return ORDER_STATES[order.state] || (order.paused ? "일시정지" : "피킹 중");
}
const orderStyle = order => order.paused ? "amber" : ["shipped", "delivered"].includes(order.state) ? "neutral" : "";
// Photos of the four presentation items (same pictures as the Windows control program)
const PRODUCT_PHOTOS = {"PK-001": "chocochip", "PK-002": "peach_green_tea", "PK-003": "spam", "PK-004": "wet_wipes"};
const PRESENTATION = Object.keys(PRODUCT_PHOTOS);
const teamNumber = user => user?.uid || "미지정";
const workEvents = () => station.events.map(e => [
  new Date(e.time).toLocaleTimeString("ko-KR", {hour12:false}), "작업", e.source, e.message
]);

const escapeHtml = value => String(value).replace(/[&<>"']/g, ch =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

function button(action, label, style = "", disabled = false) {
  return `<button type="button" data-action="${action}" class="${style}" ${disabled ? "disabled" : ""}>${label}</button>`;
}

function badge(text, style = "") {
  return `<span class="pill ${style}">${escapeHtml(text)}</span>`;
}

function panel(title, body, action = "") {
  return `<section class="panel"><div class="panel-head"><h2>${escapeHtml(title)}</h2>${action}</div>${body}</section>`;
}

function table(headings, rows) {
  const headers = headings.map(text => `<th scope="col">${text}</th>`).join("");
  const body = rows.map(cells => `<tr>${cells.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("");
  return `<div class="sheet"><table><thead><tr>${headers}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function facts(entries) {
  return `<dl class="facts">${entries.map(([label, value]) =>
    `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>`;
}

function eventList(events) {
  return `<ol class="activity">${events.slice().reverse().map(([time, , source, text]) =>
    `<li><time>${escapeHtml(time)}</time><span class="event-type">${escapeHtml(source)}</span><span>${escapeHtml(text)}</span></li>`
  ).join("")}</ol>`;
}

function pickList() {
  const rows = orderItems().map((item, index) => {
    const done = item.done;
    const active = index === packed();
    const status = done ? "담음" : active ? (mainOrder().paused ? "정지" : "피킹 중") : "대기";
    const mark = icon(done ? "circle-check" : active ? "scan" : "circle");
    return `<li class="${done ? "done" : active ? "target" : ""}">${mark}<span>${escapeHtml(item.name)}</span>
      <span class="unit">1${escapeHtml(item.unit)} · ${status}</span></li>`;
  });
  return `<ul class="picks">${rows.join("")}</ul>`;
}

function packingControls() {
  if (isPacked()) return badge("포장 완료");
  const toggle = mainOrder().paused ? button("toggle", icon("play") + "작업 재개", "main-btn")
                             : button("toggle", icon("pause") + "작업 정지", "stop-btn");
  const next = orderItems().find(i => !i.done);
  return `<div><div class="buttons">${toggle}${button("place-" + next.id, "놓기 완료 시연", "", mainOrder().paused)}</div>
    <p class="meta">놓기 완료 시 재고 차감 · ${escapeHtml(next.name)} 1${escapeHtml(next.unit)}</p></div>`;
}

let stopCamera, stopSafety;
function disconnectCamera() {
  stopCamera?.();
  stopCamera = null;
  stopSafety?.();
  stopSafety = null;
}

function renderDashboard() {
  if (!view.querySelector("#live-camera")) {
    view.replaceChildren(document.getElementById("dashboard-layout").content.cloneNode(true));
  }
  // Keep the camera mounted across inventory and order updates.
  stopCamera ??= connectDashboardCamera(document.getElementById("live-camera"), () => station);
  stopSafety ??= connectSafetyPanel(document.getElementById("safety-camera"));
  if (!station) {
    document.getElementById("dashboard-order").textContent = "주문 조회 대기 중";
    return;
  }
  const progress = mainOrder().items.map(item => `<span class="${item.done ? "filled" : ""}"></span>`).join("");
  const quickButtons = [
    button("cmd-go", icon("play") + "시작 · 재개", "main-btn"),
    button("cmd-stop", icon("pause") + "정지", "stop-btn"),
    button("cmd-pick", icon("robot-arm") + "집기"),
    button("query-stock", icon("boxes") + "재고 조회"),
    button("query-order", icon("package-check") + "주문 조회"),
    button("cmd-order", icon("plus") + "예시 주문")
  ].join("");
  const rfidButtons = [
    button("rfid-scan-auto", icon("scan") + "RFID 리더기 스캔", "main-btn"),
    ...rfidPresetTags.map(([uid, label]) => button("rfid-tag-" + uid, `<span class="mono tag-uid">${uid.slice(-4)}</span>${escapeHtml(label)}`))
  ].join("");
  const statusBanner = (reply || lastRfidMessage)
    ? `<p class="reply status-banner" role="status">${escapeHtml(lastRfidMessage || reply)}</p>`
    : "";
  document.getElementById("dashboard-order").innerHTML = `
    <div><div class="row"><strong class="order-no">#123</strong>${badge(orderStatus(), mainOrder().paused ? "amber" : "")}</div>
      <p class="order-name">${escapeHtml(mainOrder().customer)} <span class="meta">· 팀원 번호 ${escapeHtml(teamNumber(userForOrder(mainOrder())))}</span></p></div>
    <div><div class="row"><span class="meta">포장 수량</span><span class="qty">${packed()} / ${mainOrder().items.length}</span></div>
      <div class="progress" aria-hidden="true">${progress}</div></div>
    ${pickList()}${packingControls()}
    <div class="control-groups">
      <section>
        <h3 class="group-label">수동 제어 <span>음성 명령과 같은 동작</span></h3>
        <div class="buttons">${quickButtons}</div>
      </section>
      <section>
        <h3 class="group-label">RFID 태그 <span>리더기 스캔 또는 태그 직접 선택</span></h3>
        <div class="buttons">${rfidButtons}</div>
      </section>
      ${statusBanner}
    </div>`;
  document.getElementById("dashboard-events").innerHTML = eventList(workEvents().slice(-3));
}

function shippingProgress(step) {
  const stages = ["주문 접수", "택배 상품 준비", "발송 대기", "발송 완료", "배송 완료"];
  return `<ol class="pipeline" aria-label="배송 진행 단계">${stages.map((name, i) => {
    const state = i === step ? 'class="current" aria-current="step"' : i < step ? 'class="passed"' : "";
    return `<li ${state}>${name}</li>`;
  }).join("")}</ol>`;
}

function orders() {
  const sorted = station.orders.slice().sort((a, b) => b.number - a.number);
  const rows = sorted.map(o => [button("select-" + o.number, "#" + o.number, "link"), escapeHtml(o.customer),
    `<span class="mono">${escapeHtml(teamNumber(userForOrder(o)))}</span>`, badge(orderStatus(o), orderStyle(o)),
    escapeHtml(orderItems(o).map(p => p.name).slice(0, 2).join(", ") + (o.items.length > 2 ? ` 외 ${o.items.length - 2}` : "")),
    o.items.length + "개"]);
  const order = station.orders.find(o => o.number === selectedOrder) || mainOrder();
  const live = order.number === 123;
  const items = live && order.state !== "received" ? pickList()
    : table(["주문 품목", "SKU", "수량", "보관 위치", "상태"], orderItems(order).map(p => [escapeHtml(p.name),
      `<span class="mono">${escapeHtml(p.sku)}</span>`, "1" + escapeHtml(p.unit), escapeHtml(p.bin || "—"),
      p.done ? badge("담음", "neutral") : badge("대기", "amber")]));
  return panel("주문 목록", table(["주문 번호", "주문자", "팀원 번호", "상태", "주문 품목", "수량"], rows),
      `<div class="row">${badge(station.orders.length + "건", "neutral")}${button("new-order", icon("mic") + "음성 주문 예시")}</div>`) +
    panel("주문 #" + order.number, `<div class="pad stack">
      ${shippingProgress(ORDER_STEP[order.state] ?? 1)}
      ${facts([["주문자", order.customer], ["팀원 번호", teamNumber(userForOrder(order))],
        ["포장 수량", packed(order) + " / " + order.items.length], ["상태", orderStatus(order)]])}
      ${items}${live && order.state !== "received" ? packingControls() : ""}
    </div>`);
}

function field(label, name, value = "", attrs = "") {
  return `<label class="field">${label}<input name="${name}" value="${escapeHtml(value)}" required maxlength="40" ${attrs}></label>`;
}

function editForm(kind, fields, submitLabel = "저장") {
  return `<form data-edit="${kind}" class="pad"><div class="fields">${fields.join("")}</div>
    <div class="buttons end">${button("cancel", "취소")}<button type="submit" class="main-btn">${submitLabel}</button></div></form>`;
}

// ---- inventory: label scan lookup (reader typing into this page, or a tag read elsewhere) ----
let stockQuery = "";
let scanBuffer = "", scanTimer = null;
let stockScan = null;          // {state: "ok"|"error"|"busy", data, message, source, at}
let lastScanSeq = null;        // /api/v1/last-scan seq already shown

async function lookupTag(raw, source = "이 화면에서 스캔") {
  const uid = String(raw).toUpperCase().replace(/[^0-9A-F]/g, "");
  if (uid.length < 4) { stockScan = {state: "error", message: "UID가 너무 짧습니다. 라벨을 다시 찍어 주세요.", source, at: new Date()}; render(); return; }
  stockScan = {state: "busy", message: uid + " 조회 중", source, at: new Date()};
  render();
  try {
    const response = await fetch(api + "/stock/tag/" + encodeURIComponent(uid), {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "조회하지 못했습니다.");
    stockScan = {state: "ok", data, source, at: new Date()};
    selectedSku = data.product.sku;
    announce(`${data.product.name} 재고 ${data.product.stock}${data.product.unit}, 위치 ${data.product.bin}`);
  } catch (error) {
    stockScan = {state: "error", message: error.message, uid, source, at: new Date()};
  }
  if (currentDestination().id === "stock") render();
}

function scanPanel() {
  const time = stockScan ? stockScan.at.toLocaleTimeString("ko-KR", {hour12: false}) : "";
  let body;
  if (!stockScan) {
    body = `<div class="scan-empty"><strong>라벨을 리더기에 찍으세요</strong>
      <p class="meta">이 화면이 열린 PC에 연결된 리더기, 또는 UID 직접 입력으로 조회합니다. 조회만 하고 로봇 작업은 만들지 않습니다.</p></div>`;
  } else if (stockScan.state === "busy") {
    body = `<div class="scan-empty"><strong>${escapeHtml(stockScan.message)}</strong></div>`;
  } else if (stockScan.state === "error") {
    body = `<div class="scan-empty scan-error"><strong>${escapeHtml(stockScan.message)}</strong>
      <p class="meta">${escapeHtml(stockScan.source)} · ${time}</p></div>`;
  } else {
    const {product: p, tag, uid} = stockScan.data;
    const photo = PRODUCT_PHOTOS[p.sku];
    const [building, row, level] = (p.bin || "").split(" ");
    const level_ = p.available <= 0 ? "amber" : p.available < 5 ? "amber" : "";
    body = `<div class="scan-result">
      ${photo ? `<img class="scan-photo" src="/static/products/${photo}.jpg" alt="${escapeHtml(p.name)} 사진" width="120" height="160">` : ""}
      <div class="scan-main">
        <p class="meta">${escapeHtml(stockScan.source)} · ${time} · <span class="mono">${escapeHtml(uid)}</span></p>
        <h3 class="scan-name">${escapeHtml(tag.product_name || p.name)}</h3>
        <p class="meta mono">${escapeHtml(p.sku)} · ${escapeHtml(tag.sku_code || "")} · 출고 박스 ${escapeHtml(tag.target_box_id || "—")}</p>
        <div class="scan-figures">
          <div><span>현재 재고</span><strong>${p.stock}<em>${escapeHtml(p.unit)}</em></strong></div>
          <div><span>주문 가능</span><strong>${p.available}<em>${escapeHtml(p.unit)}</em></strong>${p.reserved ? `<small>예약 ${p.reserved}${escapeHtml(p.unit)}</small>` : ""}</div>
          <div><span>보관 위치</span><strong class="scan-bin">${escapeHtml(p.bin || "미지정")}</strong>
            ${building ? `<small>${escapeHtml(building)} 창고 · ${escapeHtml(row || "")} · ${escapeHtml(level || "")}</small>` : ""}</div>
        </div>
        ${level_ ? `<p>${badge(p.available <= 0 ? "주문 가능 수량 없음" : "재고 부족", "amber")}</p>` : ""}
      </div></div>`;
  }
  return panel("라벨 스캔 재고 조회", `<div class="pad scan-pad">${body}
    <form class="scan-form" data-scan-form><label class="field">UID 직접 입력
      <input name="scan_uid" placeholder="예: 0B71E55D" maxlength="20" autocomplete="off"></label>
      <button type="submit" class="main-btn">${icon("scan")}조회</button></form></div>`,
    `<span class="reader-state ${scanBuffer ? "typing" : ""}">${scanBuffer ? "리더기 입력 중 " + escapeHtml(scanBuffer) : "리더기 대기"}</span>`);
}

function inventory() {
  if (!productBySku(selectedSku)) selectedSku = station.products[0].sku;
  const model = station.model;
  const query = stockQuery.trim().toLowerCase();
  const ordered = [...PRESENTATION.map(productBySku).filter(Boolean),
    ...station.products.filter(p => !PRESENTATION.includes(p.sku))];
  const shown = query ? ordered.filter(p => [p.name, p.sku, p.bin, p.alias].some(v => String(v || "").toLowerCase().includes(query))) : ordered;
  const rows = shown.map(p => [button("sku-" + p.sku, escapeHtml(p.name), "link") +
      (PRESENTATION.includes(p.sku) ? " " + badge("발표 품목") : ""),
    `<span class="mono">${escapeHtml(p.sku)}</span>`, p.stock, p.reserved, p.available, escapeHtml(p.bin || "—"),
    escapeHtml(model.classes.find(c => c.sku === p.sku)?.name || "미연결")]);
  const product = productBySku(selectedSku) || station.products[0];
  const assigned = model.classes.find(c => c.sku === selectedSku);
  const add = form === "product" ? editForm("product", [
    field("상품명", "name"), field("단위", "unit", "개"), field("입고 수량", "stock", 1, 'type="number" min="0" max="9999"'),
    '<label class="field">음성 별칭 (선택)<input name="alias" maxlength="80"></label>',
    '<label class="field">보관 위치 (선택)<input name="bin" maxlength="80"></label>'
  ]) : "";
  const adjust = form === "adjust" ? editForm("adjust", [
    field("실사한 보유 수량", "stock", product.stock, `type="number" min="${product.reserved}" max="9999"`),
    `<input type="hidden" name="expected_stock" value="${product.stock}">`,
    `<p class="meta">예약 수량 ${product.reserved}${escapeHtml(product.unit)} 이상으로 입력하세요.</p>`
  ]) : "";
  const options = model.classes.map(c => {
    const other = c.sku && c.sku !== product.sku ? productBySku(c.sku) : null;
    return `<option value="${c.id}" ${other ? "disabled" : ""} ${c.sku === product.sku ? "selected" : ""}>${escapeHtml(c.name)}${other ? " · " + escapeHtml(other.name) + " 연결됨" : ""}</option>`;
  });
  const mapping = form === "mapping" ? editForm("mapping", [
    `<input type="hidden" name="model_id" value="${escapeHtml(model.id)}">`,
    `<label class="field">탐지 클래스<select name="class_id"><option value="">미연결</option>${options.join("")}</select></label>`
  ]) : "";
  const search = `<div class="stock-search pad"><label class="field">품목 검색
      <input type="search" data-stock-search value="${escapeHtml(stockQuery)}" placeholder="상품명, SKU, 위치(예: B동)" autocomplete="off"></label>
      <p class="meta">${shown.length} / ${station.products.length}개 품목 · 발표 품목 4개가 맨 위</p></div>`;
  return scanPanel() + panel("상품 재고", add + search + `<div class="stock-table">${table(["상품명", "SKU", "보유", "예약", "가용", "위치", "탐지 클래스"], rows)}</div>`,
      button("add-product", icon("plus") + "상품 등록")) +
    panel(product.name, `<div class="pad stack">${facts([["음성 별칭", product.alias], ["수량 단위", product.unit],
      ["활성 모델", model.name], ["탐지 클래스", assigned?.name || "미연결"]])}
      <div class="buttons">${button("adjust", "재고 수량 조정")}${button("mapping", assigned ? "클래스 연결 변경" : "탐지 클래스 연결", "", !model.classes.length)}
      ${assigned ? "" : `<a class="link" href="${trainLink(product.sku)}">새 클래스 학습 ${icon("arrow-right")}</a>`}</div>
      ${model.classes.length ? "" : '<p class="meta">활성 모델에 등록된 클래스가 없습니다.</p>'}</div>` + adjust + mapping);
}

// A team number for someone added on this screen (TM-YY-NNNN, not used by anyone yet)
function suggestTeamNumber() {
  const used = new Set(station.users.map(user => user.uid));
  const year = String(new Date().getFullYear()).slice(-2);
  for (;;) {
    const number = `TM-${year}-${String(Math.floor(Math.random() * 9000) + 1000)}`;
    if (!used.has(number)) return number;
  }
}

function users() {
  const person = currentUser();
  const ordersOf = user => station.orders.filter(order => order.customer_id === user.id);
  const rows = station.users.map(user => [button("person-" + user.id, escapeHtml(user.name), "link"),
    `<span class="mono">${escapeHtml(teamNumber(user))}</span>`, ordersOf(user).length + "건",
    user.packing ? badge("패킹 중") : badge("대기", "neutral")]);
  const add = form === "customer" ? editForm("customer", [field("팀원 이름", "name")], "팀원 등록") : "";
  const list = panel("팀원 목록", add + table(["팀원", "팀원 번호", "주문", "상태"], rows),
    button("add-customer", icon("user-plus") + "팀원 추가", "main-btn"));
  if (!person) return list;
  const orders = ordersOf(person).sort((a, b) => b.number - a.number);
  const edit = form === "rfid" ? editForm("rfid", [field("팀원 번호", "uid", person.uid || suggestTeamNumber()),
    `<input type="hidden" name="expected_uid" value="${escapeHtml(person.uid || "")}">`], "번호 저장") : "";
  const history = orders.length ? table(["주문", "상태", "품목"], orders.slice(0, 6).map(o => [
    button("select-" + o.number, "#" + o.number, "link"), badge(orderStatus(o), orderStyle(o)), o.items.length + "개"])) : "";
  const detail = panel(person.name, `<div class="pad stack">
    ${facts([["팀원 번호", teamNumber(person)], ["주문", orders.length + "건"]])}
    <div class="buttons">${button("edit-rfid", person.uid ? "팀원 번호 변경" : "팀원 번호 지정", "", person.packing)}
    ${orders.length ? button("order-detail", "주문 상세 " + icon("arrow-right"), "link") : ""}</div>
    ${person.packing ? '<p class="meta">패킹 중인 주문이 끝나면 번호를 바꿀 수 있습니다.</p>' : ""}</div>` + edit + history);
  return `<div class="admin-columns">${list}${detail}</div>`;
}

function modelManagement() {
  const model = station.model;
  const missing = station.products.filter(p => !model.classes.some(c => c.sku === p.sku));
  const rows = [...missing, ...station.products.filter(p => !missing.includes(p))].map(p => {
    const bound = model.classes.find(c => c.sku === p.sku);
    const named = model.classes.find(c => c.name.toLowerCase() === p.name.toLowerCase());
    const status = bound ? badge(bound.name) : named ? badge("같은 이름의 클래스 있음", "neutral") : badge("미연결", "amber");
    const tasks = `<a class="link" href="${stockLink(p.sku)}">클래스 연결${bound ? " 변경" : ""}</a>`;
    return [escapeHtml(p.name), escapeHtml(p.sku), status, `<div class="buttons">${tasks}
      ${bound ? "" : `<a class="link" href="${trainLink(p.sku)}">새 클래스 학습 ${icon("arrow-right")}</a>`}</div>`];
  });
  return panel("활성 모델", `<div class="pad stack">${facts([["모델", model.name], ["탐지 클래스", model.classes.length + "개"],
    ["클래스 미연결 상품", missing.length + "개"]])}<div class="buttons">
    <a class="link" href="/training#models">모델 버전·적용 ${icon("arrow-right")}</a>
    <a class="link" href="/training#jobs">학습 작업 ${icon("arrow-right")}</a></div></div>`) +
    panel("재고 상품별 클래스", table(["상품", "SKU", "활성 모델의 클래스", "작업"], rows));
}

function logs() {
  const filters = ["전체", "사용자", "재고", "모델", "주문", "음성"].map(kind =>
    `<button type="button" data-action="log-${kind}" aria-pressed="${logKind === kind}">${kind}</button>`).join("");
  const items = activity.map(e => ({...e, kind: ["패킹", "배송"].includes(e.source) ? "주문" : e.source}));
  for (const [time, kind, source, message] of demo.events) items.push({time, kind, source, message});
  const filtered = items.filter(e => logKind === "전체" || e.kind === logKind ||
    (logKind === "재고" && e.source === "패킹" && e.message.includes("출고 반영")))
    .sort((a,b) => b.time.localeCompare(a.time));
  const body = filtered.length ? table(["일시", "구분", "내용"], filtered.map(e => [
    escapeHtml(e.time.includes("T") ? new Date(e.time).toLocaleString("ko-KR") : e.time),
    badge(e.kind, "neutral"), escapeHtml((e.source === e.kind ? "" : e.source + " · ") + e.message)]))
    : '<p class="pad meta">이 항목에 기록된 활동이 없습니다.</p>';
  return panel("활동 기록", `<div class="tabs log-filters" role="group" aria-label="로그 구분">${filters}</div>` + body,
    badge(filtered.length + "건", "neutral"));
}

const voiceCommands = {
  "cmd-go": "피킹 시작해줘",
  "cmd-stop": "멈춰",
  "cmd-pick": "집어 (상품 피킹)",
  "query-stock": "재고 파악해줘",
  "query-order": "주문 내역 알려줘",
  "cmd-order": "쫀득초코칩·복숭아녹차·물티슈 하나씩 주문해줘"
};

const rfidPresetTags = [
  ["0B71E55D", "쫀득초코칩 (BOX-01)"],
  ["0B71E75D", "복숭아녹차 (BOX-02)"],
  ["0B71E65D", "스팸 (BOX-03)"],
  ["0B71ED5D", "물티슈 (BOX-04)"]
];
let lastRfidMessage = "";

async function updateVoice(action = "status") {
  const serial = ++voiceSerial;
  const previous = voiceStatus;
  if (action === "stop") {
    voiceStatus = {...previous, state: "stopping", can_stop: false};
    renderVoice();
  }
  try {
    const response = await fetch("/api/voice/" + action,
      {method: action === "status" ? "GET" : "POST", cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "음성 서버 연결을 확인하세요.");
    if (serial !== voiceSerial || JSON.stringify(data) === JSON.stringify(voiceStatus)) return;
    voiceStatus = data;
  } catch (error) {
    if (serial !== voiceSerial) return;
    voiceStatus = {...previous, state: "error", error: error.message};
  }
  renderVoice();
}

function renderVoice() {
  const voicePanel = document.getElementById("voice-panel");
  voicePanel.hidden = !voiceOpen;
  root.querySelector(".voice").setAttribute("aria-expanded", String(voiceOpen));
  if (!voiceOpen) return;
  const commands = Object.entries(voiceCommands).map(([id, label]) => button(id, label)).join("");
  const confirm = confirmingOrder ? `<div class="buttons">${button("confirm-order", "네, 주문해줘", "main-btn")}${button("discard-order", "취소")}</div>` : "";
  const status = voiceStatus || {};
  let stateLabel = voiceStates[status.state];
  if (status.state === "speaking" && status.barge_in) stateLabel = "Yuna 응답 중 · 지금 말해도 됩니다";
  if (status.state === "listening" && status.last_playback === "interrupted") stateLabel = "낭독 중단 · 듣는 중";
  const canWake = !status.can_stop && ["idle", "error"].includes(status.state) && !waking;
  if (clapArmed && clapWake.listening && canWake) stateLabel = "박수 두 번 치면 음성 인식을 시작합니다";
  const auto = status.auto;
  if (auto?.active) {
    const phase = {starting: "시작", scanning: "태그 인식 중", picking: "피킹 중", next: "다음 박스 준비",
      swap_wait: "박스 교환 대기 · 교환 후 '상자 교환 완료'라고 말씀해 주세요"}[auto.phase] || auto.phase;
    stateLabel = `피킹 로봇 가동 중 · ${auto.done}/${auto.total} · ${phase}${auto.muted ? " (음성 명령 차단)" : ""}`;
  }
  const hint = clapNote || status.error || (status.state === "disabled" ? "YOLO_VOICE_ENABLED=1로 서버를 시작하세요." : "");
  voicePanel.innerHTML = `<div class="row"><h3>음성 명령</h3><div class="buttons">
      ${button("voice-manual", manualOpen ? "사용법 닫기" : "음성 사용법", manualOpen ? "main-btn" : "")}${button("voice", "닫기", "link")}</div></div>
    ${manualOpen ? manualHtml() : ""}
    <p role="status">${escapeHtml(stateLabel || "상태 확인 중")}</p>
    <div class="buttons">${button("wake", "음성 명령 켜기 (박수 대기)", "main-btn", clapArmed || status.state === "disabled")}
      ${button("listen-now", "바로 듣기", "", !canWake)}
      ${button("stop-listening", "음성 명령 끄기", "stop-btn", !clapArmed && !status.can_stop)}</div>
    ${hint ? `<p>${escapeHtml(hint)}</p>` : ""}
    ${status.transcript ? `<p>작업자 · ${escapeHtml(status.transcript)}</p>` : ""}
    ${status.reply ? `<p>Yuna · ${escapeHtml(status.reply)}</p>` : ""}
    <h3>버튼으로 실행</h3><div class="buttons">${commands}</div>
    ${reply ? `<p class="reply" role="status">${escapeHtml(reply)}</p>` : ""}${confirm}`;
}

// ---- voice manual (GET /api/voice/manual: the recognizer's own word lists) ----
let manualOpen = false, voiceManual = null;
const chips = words => `<span class="chips">${words.map(w => `<span class="chip">${escapeHtml(w)}</span>`).join("")}</span>`;

function manualHtml() {
  const m = voiceManual;
  if (!m) return '<p class="meta">사용법을 불러오는 중입니다.</p>';
  const tone = {danger: "chip-danger", warn: "chip-warn", ask: ""};
  return `<section class="voice-manual" aria-label="음성 사용법">
    <div class="manual-block"><h4>시작하기</h4><ul>${m.start.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ul></div>
    <div class="manual-block"><h4>바로 실행 <small>되묻지 않음</small></h4>
      <div class="manual-cards">${m.immediate.map(c => `<div class="manual-card ${tone[c.tone] || ""}">
        <strong>${escapeHtml(c.title)}</strong>${chips(c.words)}<p>${escapeHtml(c.effect)}</p></div>`).join("")}</div></div>
    <div class="manual-block"><h4>되물은 뒤 "네"라고 하면 실행</h4>
      ${table(["명령", "인식 단어", "되묻는 말"], m.asked.map(a => [`<strong>${escapeHtml(a.title)}</strong>`,
        chips(a.words) + (a.example ? `<p class="meta">예: ${escapeHtml(a.example)}</p>` : ""), escapeHtml(a.question)]))}
      <p class="meta">대답 · 예: ${chips(m.answers.yes)}</p>
      <p class="meta">대답 · 아니요: ${chips(m.answers.no)}</p></div>
    <div class="manual-block"><h4>피킹 로봇 가동 <small>상자 4개 자동 진행</small></h4>
      ${table(["이렇게 말하기", "인식 단어", "동작"], m.auto.steps.map(s => [`<strong>"${escapeHtml(s.say)}"</strong>`, chips(s.words), escapeHtml(s.effect)]))}
      <ul>${m.auto.notes.map(n => `<li>${escapeHtml(n)}</li>`).join("")}</ul>
      <p class="meta">로봇 안내 방송</p><ul class="manual-quotes">${m.auto.announcements.map(a => `<li>"${escapeHtml(a)}"</li>`).join("")}</ul></div>
    <div class="manual-block"><h4>패킹 데모 <small>문장 그대로</small></h4>
      ${table(["명령", "말하는 문장"], m.packing.map(p => [`<strong>${escapeHtml(p.title)}</strong>`, chips(p.phrases)]))}
      <p class="meta">${escapeHtml(m.packing_note)}</p></div>
    <div class="manual-block"><h4>알아 둘 점</h4><ul>${[m.match_note, ...m.cautions].map(c => `<li>${escapeHtml(c)}</li>`).join("")}</ul></div>
  </section>`;
}

async function runCommand(action) {
  const answer = await request("/command", "POST", {action});
  const label = voiceCommands[action] || (action === "confirm-order" ? "네, 주문해줘" : "취소");
  record("음성", "사용자", label);
  reply = answer.text;
  lastRfidMessage = "";
  record("음성", "시스템", reply);
  confirmingOrder = answer.confirm;
  announce(reply);
  if (action === "cmd-pick") {
    const selectBtn = document.querySelector('[data-pick="select"]:not(:disabled)');
    if (selectBtn) selectBtn.click();
  }
}

async function runRfidScan(uid = null) {
  const result = await request("/rfid-scan", "POST", uid ? {uid, quantity: 1} : {quantity: 1});
  lastRfidMessage = result.text;
  reply = result.text;
  record("주문", "RFID", result.text);
  announce(result.text);
}

const pages = { orders, stock: inventory, people: users, "model-management": modelManagement, logs };

function render() {
  const route = location.hash.slice(1);
  if (route === "robot") {
    location.replace("/robot");
    return;
  }
  // Bookmarks from the original single-page training UI still open the real tool.
  if (["collect", "jobs", "models", "live", "training"].includes(route)) {
    location.replace("/training#" + (route === "training" ? "collect" : route));
    return;
  }
  const page = currentDestination();
  document.title = page.label + " · Vision Lab";
  document.getElementById("page-title").textContent = page.label;
  root.querySelector(".headline .date").textContent = ["people", "stock", "model-management", "logs"].includes(page.id) ? "관리" : "예시 주문 · 패킹 시뮬레이션";
  root.querySelector(".voice").disabled = !station;
  renderVoice();
  if (page.id === "dashboard") {
    renderDashboard();
  } else {
    disconnectCamera();
    view.innerHTML = station ? pages[page.id]() : '<p role="status">재고와 주문을 불러오는 중입니다.</p>';
    const selected = station && page.id === "people" ? "person-" + currentUser()?.id : page.id === "stock" ? "sku-" + selectedSku : "";
    if (selected && station) view.querySelector(`[data-action="${CSS.escape(selected)}"]`)?.closest("tr")?.classList.add("selected-row");
  }
}

function announce(text) {
  document.getElementById("demo-status").textContent = text;
}

function showOrder(id) {
  selectedOrder = id;
  location.hash = "orders";
}

const actions = {
  async wake() {
    clapArmed = true;
    clapNote = "";
    try { await clapWake.arm(); } catch (error) { clapArmed = false; clapNote = "마이크를 열 수 없습니다: " + error.message; }
    renderVoice();
  },
  "listen-now"() { clapWake.pause(); return browserVoice.start(); },
  "stop-listening"() {
    clapArmed = false;
    clapWake.disarm();
    return browserVoice.stop();
  },
  async "voice-manual"() {
    manualOpen = !manualOpen;
    if (manualOpen && !voiceManual) {
      const response = await fetch("/api/voice/manual", {cache: "no-store"});
      if (!response.ok) throw new Error("음성 사용법을 불러오지 못했습니다.");
      voiceManual = await response.json();
    }
  },
  async voice() {
    voiceOpen = !voiceOpen;
    if (voiceOpen) await updateVoice();
    reply = "";
    confirmingOrder = false;
  },
  "new-order"() {
    voiceOpen = true;
    void updateVoice();
    return runCommand("cmd-order");
  },
  async "confirm-order"() {
    if (!confirmingOrder || extraOrder()) return;
    await runCommand("confirm-order");
    showOrder(124);
  },
  "discard-order"() {
    return runCommand("discard-order");
  },
  async toggle() {
    const action = mainOrder().paused ? "cmd-go" : "cmd-stop";
    announce((await request("/command", "POST", {action})).text);
  },
  "order-detail"() { showOrder(Math.max(...station.orders.filter(order => order.customer_id === currentUser().id).map(o => o.number))); },
  "all-logs"() { logKind = "전체"; location.hash = "logs"; },
  "select-123"() { selectedOrder = 123; },
  "select-124"() { selectedOrder = 124; },
  "add-product"() { form = "product"; },
  "add-customer"() { form = "customer"; },
  "edit-rfid"() { form = "rfid"; },
  async "unlink-rfid"() {
    const user = currentUser();
    await request("/users/" + user.id + "/rfid", "PUT", {uid: null, expected_uid: user.uid});
    form = "";
    announce("RFID 할당을 해제했습니다.");
  },
  adjust() { form = "adjust"; },
  mapping() { form = "mapping"; },
  cancel() { form = ""; }
};

function showError(error, source = "action") {
  const message = document.getElementById("packing-error");
  message.dataset.source = source;
  message.textContent = error.message || "서버 연결을 확인하세요.";
  message.hidden = false;
}

async function perform(work, reload = false) {
  if (pending) return;
  pending = true;
  document.getElementById("packing-error").hidden = true;
  try {
    await work();
    if (reload) await refresh();
  } catch (error) {
    showError(error);
    await refresh().catch(() => {});
  } finally {
    pending = false;
    render();
  }
}

root.addEventListener("click", async event => {
  const control = event.target.closest("button[data-action]");
  if (!control || control.disabled || pending) return;
  const action = control.dataset.action;
  if (action.startsWith("place-")) {
    // A double click must not advance the newly rendered next item.
    if (performance.now() - lastPlaceClick < 650 || event.detail > 1) return;
    lastPlaceClick = performance.now();
    const id = action.slice(6);
    await perform(() => request("/orders/123/items/" + encodeURIComponent(id) + "/complete", "PUT"), true);
  } else if (Object.hasOwn(voiceCommands, action)) {
    await perform(() => runCommand(action), true);
  } else if (action === "rfid-scan-auto") {
    await perform(() => runRfidScan(null), true);
  } else if (action.startsWith("rfid-tag-")) {
    await perform(() => runRfidScan(action.slice(9)), true);
  } else if (Object.hasOwn(actions, action)) {
    await perform(actions[action], ["toggle", "new-order", "confirm-order", "unlink-rfid"].includes(action));
  } else {
    if (action.startsWith("select-")) selectedOrder = Number(action.slice(7));
    else if (action.startsWith("sku-")) { selectedSku = action.slice(4); form = ""; }
    else if (action.startsWith("person-")) { selectedUserId = Number(action.slice(7)); form = ""; }
    else if (action.startsWith("log-")) logKind = action.slice(4);
    else return;
    render();
  }
  const firstField = view.querySelector("form input:not([type=hidden]), form select");
  if (firstField) firstField.focus();
  else {
    const selector = ["wake", "listen-now", "stop-listening"].includes(action)
      ? '#voice-panel [data-action="wake"]:enabled, #voice-panel [data-action="listen-now"]:enabled, #voice-panel [data-action="stop-listening"]:enabled'
      : `[data-action="${CSS.escape(action)}"]:not(:disabled)`;
    const nextControl = root.querySelector(selector);
    if (nextControl && !nextControl.closest("[hidden]")) nextControl.focus({ preventScroll: true });
  }
});

root.addEventListener("input", event => {
  if (event.target instanceof HTMLInputElement) event.target.setCustomValidity("");
  if (event.target.matches("[data-stock-search]")) {
    stockQuery = event.target.value;
    const caret = event.target.selectionStart;
    render();
    const box = view.querySelector("[data-stock-search]");
    box?.focus();
    box?.setSelectionRange(caret, caret);
  }
});

// RFID reader in keyboard mode on the inventory page: it types the UID and Enter into the page.
document.addEventListener("keydown", event => {
  if (currentDestination().id !== "stock" || event.ctrlKey || event.altKey || event.metaKey) return;
  if (event.target.closest?.("input, textarea, select, [contenteditable]")) return;
  const state = () => {
    const label = view.querySelector(".reader-state");
    if (label) { label.textContent = scanBuffer ? "리더기 입력 중 " + scanBuffer : "리더기 대기"; label.classList.toggle("typing", !!scanBuffer); }
  };
  if (event.key === "Enter") {
    if (!scanBuffer) return;
    const uid = scanBuffer;
    scanBuffer = "";
    state();
    event.preventDefault();
    void lookupTag(uid, "리더기 스캔 (이 PC)");
  } else if (/^[0-9a-fA-F]$/.test(event.key)) {
    scanBuffer = (scanBuffer + event.key.toUpperCase()).slice(-20);
    clearTimeout(scanTimer);
    scanTimer = setTimeout(() => { scanBuffer = ""; state(); }, 1500);
    state();
  }
});

// A tag read anywhere else (Windows control program, phone NFC, dashboard) is looked up here too.
async function followLastScan() {
  if (currentDestination().id !== "stock") return;
  try {
    const response = await fetch("/api/v1/last-scan", {cache: "no-store"});
    if (!response.ok) return;
    const scan = (await response.json()).last_scan;
    const seq = scan?.seq ?? 0;
    if (lastScanSeq === null) { lastScanSeq = seq; return; }
    if (seq === lastScanSeq) return;
    lastScanSeq = seq;
    const sources = {remote_reader: "리더기 (관제 프로그램)", phone_nfc: "갤럭시 NFC", voice: "음성 명령"};
    if (scan.uid || scan.raw_uid) await lookupTag(scan.uid || scan.raw_uid, sources[scan.source] || scan.source);
  } catch {
    // RFID routes may be absent on a dashboard-only server
  }
}

root.addEventListener("submit", async event => {
  const scanForm = event.target.closest("form[data-scan-form]");
  if (scanForm) {
    event.preventDefault();
    const value = scanForm.elements.scan_uid.value;
    if (value.trim()) await lookupTag(value, "UID 직접 입력");
    return;
  }
  const editor = event.target.closest("form[data-edit]");
  if (!editor) return;
  event.preventDefault();
  if (pending) return;
  const values = Object.fromEntries([...new FormData(editor)].map(([key, value]) => [key, value.trim()]));
  for (const [name, value] of Object.entries(values)) {
    if (!value && editor.elements[name].required) {
      editor.elements[name].setCustomValidity("값을 입력해 주세요.");
      editor.reportValidity();
      return;
    }
  }
  const kind = editor.dataset.edit;
  const sku = selectedSku;
  await perform(async () => {
    if (kind === "customer") {
      const user = await request("/users", "POST", {name: values.name});
      selectedUserId = user.id;
      form = "rfid";
      announce(user.name + " 팀원을 추가했습니다. 팀원 번호를 확인하고 저장하세요.");
      return;
    }
    if (kind === "rfid") {
      await request("/users/" + currentUser().id + "/rfid", "PUT", {uid: values.uid, expected_uid: values.expected_uid || null});
    } else if (kind === "product") {
      const added = await request("/products", "POST", {...values, stock: Number(values.stock)});
      selectedSku = added.sku;
    } else if (kind === "adjust") {
      await request("/products/" + sku + "/stock", "PUT", {stock: Number(values.stock), expected_stock: Number(values.expected_stock)});
    } else if (kind === "mapping") {
      await request("/models/" + encodeURIComponent(values.model_id) + "/products/" + sku + "/class", "PUT",
        {class_id: values.class_id === "" ? null : Number(values.class_id)});
    }
    form = "";
    announce("저장했습니다.");
  }, true);
  if (form === "rfid") view.querySelector('[name="uid"]')?.focus();
});

window.addEventListener("hashchange", () => {
  form = "";
  lastScanSeq = null;  // only tags read while the inventory page is open are shown there
  voiceOpen = false;
  confirmingOrder = false;
  render();
  void sync();
  window.scrollTo(0, 0);
});

window.addEventListener("pagehide", disconnectCamera);
window.addEventListener("pageshow", event => { if (event.persisted) render(); });
render();

async function sync() {
  if (pending || document.hidden) return;
  try {
    await Promise.all([refresh(), voiceOpen ? updateVoice() : undefined, followLastScan()]);
    const message = document.getElementById("packing-error");
    if (message.dataset.source === "sync") message.hidden = true;
  } catch (error) {
    showError(error, "sync");
  }
}
window.addEventListener("focus", sync);
document.addEventListener("visibilitychange", sync);
setInterval(sync, 2000);
sync();
