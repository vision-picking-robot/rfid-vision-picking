"""Work-area safety watch with a fixed USB webcam.

While the robot heads into an object's zone to pick it (the robot cycle reports this phase; carrying to the
box is excluded), a person near that zone starts a 3 s warning beep. If the person is still there after the
warning, the robot cycle is held (it stops the current move at once). When nobody has been near the zone for
3 s, the hold is released with the spoken notice "안전구역 확보" and the robot carries on by itself.

This is an aid for the demo, not a certified safety device: keep the pendant E-Stop at hand.

The webcam is opened here on its own (never the RealSense used by the detection pipeline). People are found
with the YOLO COCO model's "person" class when it is available, otherwise with OpenCV's HOG people detector.
Zones are polygons in normalized webcam coordinates, edited on the dashboard and stored in safety.json.
"""
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)

WARN_S = 3.0        # warning beep before the robot is held
CLEAR_S = 3.0       # nobody near the zone for this long -> "안전구역 확보" and the robot resumes
PRESENCE_S = 0.5    # a person seen within this time still counts as present (detector flicker)
DETECT_PERIOD_S = 0.2
JPEG_PERIOD_S = 0.12
MARGIN = 0.06       # "near the zone": the zone's box grown by this fraction of the frame

# Corners 1 -> 2 -> 3 -> 4 go round the work area; until zones are drawn, split the view in four.
DEFAULT_ZONES = {
    "1": [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
    "2": [[0.5, 0.0], [1.0, 0.0], [1.0, 0.5], [0.5, 0.5]],
    "3": [[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]],
    "4": [[0.0, 0.5], [0.5, 0.5], [0.5, 1.0], [0.0, 1.0]],
}
TEXT = {
    "warning": "작업자 접근 경고 · 3초 안에 벗어나지 않으면 로봇을 정지합니다",
    "warning_cleared": "작업자가 벗어나 경고를 해제했습니다",
    "hold": "작업자 접근 · 로봇 정지",
    "resume": "안전구역 확보. 로봇을 다시 가동합니다.",
}


def near(box, polygon, margin=MARGIN):
    """True when a person box (x1, y1, x2, y2, normalized) touches the zone grown by `margin`."""
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    zx1, zy1, zx2, zy2 = min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin
    x1, y1, x2, y2 = box[:4]
    return x1 < zx2 and x2 > zx1 and y1 < zy2 and y2 > zy1


class PersonDetector:
    """People in a BGR frame as normalized boxes [x1, y1, x2, y2, confidence]."""

    def __init__(self, settings):
        self.kind, self._yolo, self._hog = "none", None, None
        path = Path(settings.model_path)
        if settings.backend != "mock" and path.suffix == ".pt" and path.exists():
            try:
                from ultralytics import YOLO
                model = YOLO(str(path), task="detect")
                ids = [i for i, name in model.names.items() if name == "person"]
                if ids:
                    self._yolo, self._person, self._device = model, ids[0], settings.backend
                    self.kind = "yolo"
            except Exception as exc:  # noqa: BLE001
                log.warning("YOLO person detector unavailable: %s", exc)
        if self._yolo is None:
            try:
                import cv2
                self._hog = cv2.HOGDescriptor()
                self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
                self.kind = "hog"
            except Exception as exc:  # noqa: BLE001
                log.warning("HOG people detector unavailable: %s", exc)

    def __call__(self, frame):
        h, w = frame.shape[:2]
        if self._yolo is not None:
            result = self._yolo.predict(frame, classes=[self._person], conf=0.35, imgsz=480, verbose=False,
                                        device=self._device)[0]
            return [[float(x1) / w, float(y1) / h, float(x2) / w, float(y2) / h, float(c)]
                    for (x1, y1, x2, y2), c in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist())]
        if self._hog is not None:
            import cv2
            scale = 480 / max(w, h)
            small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame
            sh, sw = small.shape[:2]
            rects, weights = self._hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
            return [[x / sw, y / sh, (x + rw) / sw, (y + rh) / sh, float(wt)]
                    for (x, y, rw, rh), wt in zip(rects, list(weights)) if float(wt) > 0.4]
        return []


class SafetyMonitor:
    def __init__(self, config_path, settings, phase_fn, hold_fn, clock=time.monotonic,
                 warn_s=WARN_S, clear_s=CLEAR_S, state_fn=None):
        self.config_path = Path(config_path)
        self.settings, self.phase_fn, self.hold_fn, self.clock = settings, phase_fn, hold_fn, clock
        self.state_fn = state_fn      # (state, zone, message): the phone shows the warning stage too
        self._reported = None
        self.warn_s, self.clear_s = warn_s, clear_s
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        config = self._load()
        self.zones = config.get("zones") or DEFAULT_ZONES
        env_index = os.getenv("SAFETY_CAMERA_INDEX")
        self.camera_index = int(env_index) if env_index not in (None, "") else config.get("camera_index")
        self.state, self.zone, self.product = "idle", None, None
        self.warn_started = self.absent_since = None
        self.last_seen = None
        self.hold_zone = None
        self.persons, self.near_persons = [], []
        self.simulated = False
        self.announcements, self.seq = [], 0
        self.events = []
        self.camera = {"ok": False, "index": self.camera_index, "detector": "-", "fps": 0.0, "message": "카메라 꺼짐"}
        self._jpeg, self._jpeg_at = None, 0.0
        self._cap, self._detector = None, None
        self._camera_wanted = settings.camera_autostart and self.camera_index is not None

    # ---- config --------------------------------------------------------------------------------
    def _load(self):
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({"zones": self.zones, "camera_index": self.camera_index},
                                               ensure_ascii=False, indent=2), encoding="utf-8")

    def set_zone(self, zone, polygon):
        with self.lock:
            self.zones = {**self.zones, str(zone): [[round(float(x), 4), round(float(y), 4)] for x, y in polygon]}
            self._save()

    def reset_zones(self):
        with self.lock:
            self.zones = dict(DEFAULT_ZONES)
            self._save()

    def use_camera(self, index):
        with self.lock:
            self.camera_index = index
            self._camera_wanted = index is not None
            self._save()
            self._close_camera()
            self.camera.update(index=index, ok=False, message="카메라 연결 중" if index is not None else "카메라 꺼짐")

    def simulate(self, present):
        """Rehearsal without a webcam: a virtual person standing at the zone the robot is picking from."""
        with self.lock:
            self.simulated = bool(present)

    # ---- state machine -------------------------------------------------------------------------
    def _announce(self, kind):
        self.seq += 1
        entry = {"seq": self.seq, "kind": kind, "text": TEXT[kind], "zone": self.hold_zone or self.zone,
                 "time": time.strftime("%H:%M:%S")}
        self.announcements = (self.announcements + [entry])[-12:]
        self.events = (self.events + [entry])[-30:]
        log.info("safety %s zone=%s", kind, entry["zone"])

    def _watched(self, zone):
        return [self.zones[str(zone)]] if zone and str(zone) in self.zones else list(self.zones.values())

    def step(self, persons=None):
        """Advance the warning / hold / resume machine. Called ~10x per second."""
        now = self.clock()
        phase = self.phase_fn()
        release = hold = False
        with self.lock:
            if persons is not None:
                self.persons = persons
            self.zone = phase.get("zone") if phase else None
            self.product = phase.get("product") if phase else None
            zone = self.hold_zone if self.state == "hold" else self.zone
            watched = self._watched(zone)
            self.near_persons = [p for p in self.persons if any(near(p, poly) for poly in watched)]
            if self.near_persons or (self.simulated and (phase or self.state == "hold")):
                self.last_seen = now
            present = self.last_seen is not None and now - self.last_seen <= PRESENCE_S
            if self.state == "hold":
                if present:
                    self.absent_since = None
                else:
                    # clear time counts from the moment the person was last seen
                    self.absent_since = self.absent_since or self.last_seen or now
                if self.absent_since is not None and now - self.absent_since >= self.clear_s:
                    self.state, release = ("clear" if phase else "idle"), True
                    self._announce("resume")
                    self.hold_zone = self.absent_since = None
            elif not phase:
                if self.state == "warning":
                    self._announce("warning_cleared")
                self.state = "idle"
            elif self.state in ("idle", "clear") and present:
                self.state, self.warn_started = "warning", now
                self._announce("warning")
            elif self.state == "warning":
                if not present:
                    self.state = "clear"
                    self._announce("warning_cleared")
                elif now - self.warn_started >= self.warn_s:
                    self.state, self.hold_zone, self.absent_since, hold = "hold", self.zone, None, True
                    self._announce("hold")
            elif self.state == "idle":
                self.state = "clear"
        if hold:
            self.hold_fn(True, TEXT["hold"] + (f" (구역 {self.hold_zone})" if self.hold_zone else ""))
        if release:
            self.hold_fn(False, TEXT["resume"])
        self._report_state(release)
        return self.state

    def _report_state(self, resumed):
        """Tell the server when the stage changes (warning / hold / clear), with the sentence to show."""
        if self.state_fn is None or self.state == self._reported:
            return
        previous, self._reported = self._reported, self.state
        message = {"warning": TEXT["warning"], "hold": TEXT["hold"]}.get(self.state)
        if message is None:  # back to normal: say why
            message = TEXT["resume"] if resumed else TEXT["warning_cleared"] if previous == "warning" else None
        zone = self.hold_zone or self.zone
        try:
            self.state_fn(self.state, zone, message)
        except Exception as exc:  # noqa: BLE001
            log.warning("safety state report failed: %s", exc)

    def status(self):
        now = self.clock()
        with self.lock:
            warn_left = max(0.0, self.warn_s - (now - self.warn_started)) if self.state == "warning" else None
            clear_left = (max(0.0, self.clear_s - (now - self.absent_since))
                          if self.state == "hold" and self.absent_since is not None else None)
            return {"state": self.state, "zone": self.hold_zone or self.zone, "product": self.product,
                    "watching": self.zone is not None or self.state == "hold", "persons": self.persons,
                    "near": len(self.near_persons), "simulated": self.simulated, "zones": self.zones,
                    "warn_left": warn_left, "clear_left": clear_left, "camera": dict(self.camera),
                    "announcements": list(self.announcements), "events": list(self.events),
                    "warn_s": self.warn_s, "clear_s": self.clear_s}

    def jpeg(self):
        with self.lock:
            return self._jpeg if self._jpeg and time.monotonic() - self._jpeg_at < 3.0 else None

    # ---- camera loop ---------------------------------------------------------------------------
    def _open_camera(self):
        import cv2
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else (cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_V4L2)
        cap = cv2.VideoCapture(self.camera_index, backend)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"웹캠 {self.camera_index}번을 열 수 없습니다. 연결과 번호를 확인하세요.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if self._detector is None:
            self._detector = PersonDetector(self.settings)
        self._cap = cap
        self.camera.update(ok=True, detector=self._detector.kind, message="감시 중")

    def _close_camera(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _loop(self):
        import cv2
        next_detect = next_jpeg = retry_at = 0.0
        frames, fps_at = 0, time.monotonic()
        while not self.stop_event.is_set():
            persons = None
            if self._camera_wanted and self._cap is None and time.monotonic() >= retry_at:
                try:
                    self._open_camera()
                except Exception as exc:  # noqa: BLE001
                    self.camera.update(ok=False, message=str(exc))
                    retry_at = time.monotonic() + 3.0
            if self._cap is not None:
                ok, frame = self._cap.read()
                if not ok or frame is None:
                    self.camera.update(ok=False, message="웹캠 영상이 끊겼습니다. 다시 연결합니다.")
                    self._close_camera()
                    retry_at = time.monotonic() + 2.0
                else:
                    frames += 1
                    t = time.monotonic()
                    if t - fps_at >= 2.0:
                        self.camera["fps"], frames, fps_at = round(frames / (t - fps_at), 1), 0, t
                    if t >= next_detect:
                        next_detect = t + DETECT_PERIOD_S
                        try:
                            persons = self._detector(frame)
                        except Exception as exc:  # noqa: BLE001
                            log.warning("person detection failed: %s", exc)
                            persons = []
                    if t >= next_jpeg:
                        next_jpeg = t + JPEG_PERIOD_S
                        ok, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        if ok:
                            with self.lock:
                                self._jpeg, self._jpeg_at = data.tobytes(), t
            else:
                time.sleep(0.1)
            try:
                self.step(persons)
            except Exception as exc:  # noqa: BLE001
                log.warning("safety step failed: %s", exc)
        self._close_camera()

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, name="safety-watch", daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=3)


# ---- HTTP -----------------------------------------------------------------------------------------
class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ZoneInput(Input):
    zone: int = Field(ge=1, le=4)
    points: list[list[float]] = Field(min_length=3, max_length=12)


class SimulateInput(Input):
    person: bool


class CameraInput(Input):
    index: int | None = Field(default=None, ge=0, le=63)


router = APIRouter(prefix="/api/safety")


def monitor(request: Request) -> SafetyMonitor:
    found = getattr(request.app.state, "safety", None)
    if found is None:
        raise HTTPException(503, "안전 감시가 시작되지 않았습니다.")
    return found


@router.get("/status")
def safety_status(request: Request):
    return monitor(request).status()


@router.get("/frame.jpg")
def safety_frame(request: Request):
    data = monitor(request).jpeg()
    if data is None:
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/zones")
def safety_zone(body: ZoneInput, request: Request):
    if any(len(p) != 2 or not all(0.0 <= v <= 1.0 for v in p) for p in body.points):
        raise HTTPException(422, "구역 좌표는 0~1 사이의 [x, y] 목록이어야 합니다.")
    monitor(request).set_zone(body.zone, body.points)
    return monitor(request).status()


@router.delete("/zones")
def safety_zone_reset(request: Request):
    monitor(request).reset_zones()
    return monitor(request).status()


@router.post("/simulate")
def safety_simulate(body: SimulateInput, request: Request):
    monitor(request).simulate(body.person)
    return monitor(request).status()


@router.get("/cameras")
def safety_cameras():
    from .capture import camera_devices
    devices = [d for d in camera_devices() if "realsense" not in d["name"].lower()]
    return {"devices": devices}


@router.post("/camera")
def safety_camera(body: CameraInput, request: Request):
    monitor(request).use_camera(body.index)
    return monitor(request).status()
