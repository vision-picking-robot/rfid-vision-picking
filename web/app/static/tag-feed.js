// Live "last tag read" strip: whichever source read it (Windows bridge, dashboard, phone NFC),
// accepted or rejected. Data: GET /api/v1/last-scan.
const SOURCES = { remote_reader: "Windows 리더기", phone_nfc: "휴대폰 NFC", hardware: "로봇 PC 리더기", hardware_pcsc: "로봇 PC 리더기", preset: "대시보드 버튼" };
const POLL_MS = 1000;

export function describeScan(scan) {
  const uid = scan.uid || scan.raw_uid;
  const time = new Date(scan.timestamp).toLocaleTimeString("ko-KR", { hour12: false });
  const source = SOURCES[scan.source] || scan.source;
  return scan.accepted
    ? `최근 태그 ${time} · ${uid} · ${scan.product_name || "등록 상품"} → ${scan.target_box_id || "-"} · 작업 등록 (${source})`
    : `최근 태그 ${time} · ${uid} · 인식 거부: ${scan.error || "등록되지 않은 태그"} (${source})`;
}

export function connectTagFeed(el) {
  let timer = null, request = null, stopped = false, lastSeq = null;

  async function poll() {
    if (stopped) return;
    request = new AbortController();
    try {
      const response = await fetch("/api/v1/last-scan", { cache: "no-store", signal: request.signal });
      const scan = response.ok ? (await response.json()).last_scan : null;
      if (scan) {
        const text = describeScan(scan);
        if (el.textContent !== text) el.textContent = text;
        el.classList.toggle("bad", !scan.accepted);
        if (lastSeq !== null && scan.seq !== lastSeq) {
          el.classList.remove("fresh");
          void el.offsetWidth;  // restart the highlight
          el.classList.add("fresh");
        }
        lastSeq = scan.seq;
        el.hidden = false;
      }
    } catch { /* keep the last text; the server may be restarting */ }
    if (!stopped) timer = setTimeout(poll, POLL_MS);
  }

  poll();
  return () => { stopped = true; clearTimeout(timer); request?.abort(); };
}
