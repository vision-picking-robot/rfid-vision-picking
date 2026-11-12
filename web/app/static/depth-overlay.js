// Live depth-camera overlay on the dashboard camera: the work-area boundary (the four calibrated
// corners) and a labelled border around every object the RealSense depth finds above the table.
// Data: GET /api/robot/pick/depth-objects (same source the robot cycle picks from).

// One product is placed near each calibration corner (config/integration.real.json depth_picking.zones);
// `key` is the item's variable name, `robotClass` the class the robot cycle uses for that zone.
export const DEPTH_ITEMS = {
  1: { key: "wet_wipes", name: "물티슈", robotClass: "wet_wipes", color: "#6fd3ff" },
  2: { key: "spam_can", name: "스팸", robotClass: "canned_meat", color: "#ffb36b" },
  3: { key: "choco_chip_box", name: "쫀득초코칩", robotClass: "snack_pepero", color: "#c79bff" },
  4: { key: "peach_tea_pet", name: "복숭아녹차", robotClass: "beverage_pet", color: "#7dffb0" },
};

const SVG = "http://www.w3.org/2000/svg";
const POLL_MS = 700;

function node(name, attrs, text) {
  const el = document.createElementNS(SVG, name);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  return el;
}

function points(list) {
  return list.map(([u, v]) => `${u},${v}`).join(" ");
}

export function describeObject(obj) {
  const item = obj.inside ? DEPTH_ITEMS[obj.corner] : null;
  const height = Math.round(obj.height_mm) + "mm";
  return item
    ? { label: `${item.name} ${height}`, key: item.key, color: item.color }
    : { label: `영역 밖 물체 ${height}`, key: "", color: "#9aa7b0" };
}

export function connectDepthOverlay(svg, image) {
  let timer = null, request = null, stopped = false;

  // SVG elements have no .hidden property: toggle the attribute (as the class overlay does).
  const show = visible => svg.toggleAttribute("hidden", !visible);
  function hide() { show(false); }

  function draw(data) {
    const { width, height } = data.camera;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const stroke = Math.max(2, width / 320);
    const font = Math.max(11, width / 48);
    const layer = [];
    if (data.work_area_px?.length === 4) {
      layer.push(node("polygon", { points: points(data.work_area_px), fill: "none", stroke: "#ffe066",
        "stroke-width": stroke, "stroke-dasharray": `${stroke * 4} ${stroke * 3}` }));
      const [u, v] = data.work_area_px[0];
      layer.push(node("text", { x: u + 4, y: v - 6, fill: "#ffe066", "font-size": font, "font-weight": 700,
        "paint-order": "stroke", stroke: "#000a", "stroke-width": 3 }, "작업 영역"));
    }
    for (const obj of data.objects || []) {
      const [x0, y0, x1, y1] = obj.bbox;
      const { label, key, color } = describeObject(obj);
      layer.push(node("rect", { x: x0, y: y0, width: x1 - x0, height: y1 - y0, rx: 3, fill: "none",
        stroke: color, "stroke-width": stroke * 1.4, "stroke-dasharray": obj.inside ? "" : `${stroke * 2} ${stroke * 2}` }));
      // Name + height above the box, the item's variable name small inside its top edge.
      const text = { fill: color, "font-weight": 700, "paint-order": "stroke", stroke: "#000c", "stroke-width": 3 };
      layer.push(node("text", { ...text, x: x0, y: Math.max(font, y0 - 4), "font-size": font }, label));
      if (key) layer.push(node("text", { ...text, x: x0 + 3, y: y0 + font * 0.8 + 2, "font-size": font * 0.62 }, key));
    }
    svg.replaceChildren(...layer);
    show(!image.hidden);
  }

  async function poll() {
    if (stopped) return;
    if (image.hidden || document.hidden) {
      hide();
    } else {
      request = new AbortController();
      try {
        const response = await fetch("/api/robot/pick/depth-objects", { cache: "no-store", signal: request.signal });
        if (response.ok) draw(await response.json());
        else hide();  // no depth frame / no calibration: show the plain video
      } catch {
        if (!stopped) hide();
      }
    }
    if (!stopped) timer = setTimeout(poll, POLL_MS);
  }

  poll();
  return () => { stopped = true; clearTimeout(timer); request?.abort(); hide(); };
}
