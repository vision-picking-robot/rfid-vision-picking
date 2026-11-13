"""Box drop check: a fixed USB webcam looking into the packing box confirms each item landed in it.

The robot cycle asks for a reference picture while the arm is at home (before the pick), and after placing an
item and returning home it asks for a check: the box area of a fresh picture is compared with the reference.
Enough changed pixels inside the box -> "landed". Nothing changed -> "missing" (fell outside the box or is
still in the gripper). Almost everything changed -> "uncertain" (camera bumped, lights switched, someone's hand
over the box). The cycle only records a failed check (the task ends DEFECTIVE instead of COMPLETED); it does
not stop the robot. After every check the new picture becomes the reference for the next item.
"""
import json
import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)

# Whole frame minus the strip above the far rim (outside the box: people, the robot).
DEFAULT_BOX = [[0.0, 0.1], [1.0, 0.1], [1.0, 1.0], [0.0, 1.0]]
DIFF_LEVEL = 32       # per-pixel colour change (0-255) that counts as "changed"
MIN_CHANGE = 0.015    # share of the box area that must change for "landed"
MAX_CHANGE = 0.80     # more than this changed: camera bumped / lights -> "uncertain"
MAX_SHIFT = 60        # whole picture this much brighter/darker: lights switched or lens covered -> "uncertain"
SETTLE_S = 0.4        # use a frame taken at least this long after the request (V4L2 buffers old frames)
JPEG_PERIOD_S = 0.12
HISTORY = 20

VERDICT_TEXT = {
    "landed": "상자 투입 확인",
    "missing": "상자 안에서 물품을 찾지 못함",
    "uncertain": "판정 불가 (화면 전체가 바뀜)",
}


def box_mask(shape, polygon):
    import cv2
    h, w = shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [np.array([[x * (w - 1), y * (h - 1)] for x, y in polygon], np.int32)], 255)
    return mask > 0


def compare(before, after, polygon, level=DIFF_LEVEL, min_change=MIN_CHANGE, max_change=MAX_CHANGE):
    """Changed share of the box area between two BGR frames, with a verdict and the changed blob."""
    import cv2
    inside = box_mask(before.shape, polygon)
    a = cv2.GaussianBlur(before, (7, 7), 0).astype(np.int16)
    b = cv2.GaussianBlur(after, (7, 7), 0).astype(np.int16)
    delta = b - a
    # Auto exposure shifts the whole picture a little: cancel the typical change of each colour channel.
    shift = np.median(delta[inside], axis=0)
    changed = (np.abs(delta - shift).max(axis=2) > level) & inside
    changed = cv2.morphologyEx(changed.astype(np.uint8) * 255, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
    area = int(inside.sum()) or 1
    share = float(changed.sum()) / area
    verdict = "uncertain" if share > max_change or np.abs(shift).max() > MAX_SHIFT else "landed" if share >= min_change else "missing"
    blob = None
    if changed.any():
        contours, _ = cv2.findContours(changed.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
        H, W = before.shape[:2]
        blob = [round(x / W, 4), round(y / H, 4), round((x + w) / W, 4), round((y + h) / H, 4)]
    return {"verdict": verdict, "change": round(share, 4), "blob": blob, "changed": changed,
            "shift": [round(float(s), 1) for s in shift]}


def annotate(frame, polygon, changed=None, blob=None, colour=(80, 200, 255)):
    import cv2
    out = frame.copy()
    h, w = out.shape[:2]
    if changed is not None:
        tint = out.copy()
        tint[changed] = (0, 200, 255)
        out = cv2.addWeighted(tint, 0.45, out, 0.55, 0)
    pts = np.array([[x * (w - 1), y * (h - 1)] for x, y in polygon], np.int32)
    cv2.polylines(out, [pts], True, colour, 2)
    if blob:
        x1, y1, x2, y2 = blob
        cv2.rectangle(out, (int(x1 * w), int(y1 * h)), (int(x2 * w), int(y2 * h)), (60, 220, 60), 2)
    ok, data = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return data.tobytes() if ok else None


class BoxCheck:
    def __init__(self, config_path, settings, clock=time.monotonic):
        self.config_path = Path(config_path)
        self.settings, self.clock = settings, clock
        config = self._load()
        self.camera_index = config.get("camera_index")
        self.box = config.get("box") or DEFAULT_BOX
        self.min_change = float(config.get("min_change", MIN_CHANGE))
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.camera = {"ok": False, "index": self.camera_index, "fps": 0.0, "message": "카메라 꺼짐"}
        self._cap = None
        # A webcam chosen for the box stays on across restarts (start_lab turns autostart off for the main camera).
        self._camera_wanted = self.camera_index is not None
        self._frame, self._frame_at, self._jpeg = None, 0.0, None
        self.reference, self.reference_at, self.reference_label = None, None, None
        self.images = {}          # before / after / reference JPEGs of the last check
        self.history, self.seq = [], 0

    # ---- config --------------------------------------------------------------------------------
    def _load(self):
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({"camera_index": self.camera_index, "box": self.box,
                                                "min_change": self.min_change}, ensure_ascii=False, indent=2),
                                    encoding="utf-8")

    def set_box(self, polygon):
        with self.lock:
            self.box = [[round(float(x), 4), round(float(y), 4)] for x, y in polygon]
            self.reference = None  # the old reference was compared over another area
            self._save()

    def reset_box(self):
        self.set_box(DEFAULT_BOX)

    def use_camera(self, index):
        with self.lock:
            self.camera_index = index
            self._camera_wanted = index is not None
            self._close_camera()
            self._frame, self._jpeg, self.reference = None, None, None
            self.camera.update(index=index, ok=False, message="카메라 연결 중" if index is not None else "카메라 꺼짐")
            self._save()

    # ---- checks --------------------------------------------------------------------------------
    def fresh_frame(self, timeout=3.0):
        """A frame taken after this call (plus SETTLE_S), so it shows the scene as it is now."""
        wanted = self.clock() + SETTLE_S
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            with self.lock:
                if self._frame is not None and self._frame_at >= wanted:
                    return self._frame.copy()
            time.sleep(0.03)
        raise HTTPException(503, self.camera.get("message") or "상자 확인 웹캠 영상이 없습니다.")

    def take_reference(self, label=None):
        frame = self.fresh_frame()
        with self.lock:
            self.reference, self.reference_at, self.reference_label = frame, datetime.now(), label
            self.images["reference"] = annotate(frame, self.box)
        return self.status()

    def verify(self, label=None, keep_reference=False):
        with self.lock:
            reference = None if self.reference is None else self.reference.copy()
        if reference is None:
            raise HTTPException(409, "기준 사진이 없습니다. 작업 시작 때 기준 사진을 먼저 찍어야 합니다.")
        frame = self.fresh_frame()
        found = compare(reference, frame, self.box, min_change=self.min_change)
        with self.lock:
            self.seq += 1
            result = {"id": self.seq, "time": datetime.now().strftime("%H:%M:%S"), "label": label,
                      "verdict": found["verdict"], "ok": found["verdict"] == "landed",
                      "text": VERDICT_TEXT[found["verdict"]], "change": found["change"],
                      "min_change": self.min_change, "blob": found["blob"]}
            self.images["before"] = annotate(reference, self.box)
            self.images["after"] = annotate(frame, self.box, found["changed"], found["blob"])
            self.history = (self.history + [result])[-HISTORY:]
            if not keep_reference:  # robot cycle: the box now holds this item, the next item compares with it
                self.reference, self.reference_at, self.reference_label = frame, datetime.now(), label
        log.info("box check %s: %s (%.1f%% changed)", label, found["verdict"], found["change"] * 100)
        return result

    def status(self):
        with self.lock:
            return {"camera": dict(self.camera), "box": self.box, "min_change": self.min_change,
                    "reference": self.reference_at.strftime("%H:%M:%S") if self.reference_at and
                    self.reference is not None else None,
                    "reference_label": self.reference_label,
                    "last": self.history[-1] if self.history else None, "history": list(self.history)}

    def jpeg(self):
        with self.lock:
            return self._jpeg if self._jpeg and self.clock() - self._frame_at < 3.0 else None

    # ---- camera loop ---------------------------------------------------------------------------
    def _open_camera(self):
        import cv2
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else (
            cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_V4L2)
        cap = cv2.VideoCapture(self.camera_index, backend)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError(f"웹캠 {self.camera_index}번을 열 수 없습니다. 다른 프로그램이 쓰고 있는지 확인하세요.")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cap = cap
        self.camera.update(ok=True, message="상자 확인 대기")

    def _close_camera(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _loop(self):
        import cv2
        next_jpeg = retry_at = 0.0
        frames, fps_at = 0, time.monotonic()
        while not self.stop_event.is_set():
            if self._camera_wanted and self._cap is None and time.monotonic() >= retry_at:
                try:
                    self._open_camera()
                except Exception as exc:  # noqa: BLE001
                    self.camera.update(ok=False, message=str(exc))
                    retry_at = time.monotonic() + 3.0
            cap = self._cap
            if cap is None:
                time.sleep(0.1)
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                self.camera.update(ok=False, message="웹캠 영상이 끊겼습니다. 다시 연결합니다.")
                with self.lock:
                    self._close_camera()
                retry_at = time.monotonic() + 2.0
                continue
            t = self.clock()
            frames += 1
            if t - fps_at >= 2.0:
                self.camera["fps"], frames, fps_at = round(frames / (t - fps_at), 1), 0, t
            jpeg = None
            if t >= next_jpeg:
                next_jpeg = t + JPEG_PERIOD_S
                ok, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                jpeg = data.tobytes() if ok else None
            with self.lock:
                self._frame, self._frame_at = frame, t
                if jpeg:
                    self._jpeg = jpeg
        with self.lock:
            self._close_camera()

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._loop, name="box-check", daemon=True)
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=3)


# ---- HTTP -----------------------------------------------------------------------------------------
class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CameraInput(Input):
    index: int | None = Field(default=None, ge=0, le=63)


class BoxInput(Input):
    points: list[list[float]] = Field(min_length=3, max_length=12)


class CheckInput(Input):
    label: str | None = Field(default=None, max_length=120)
    keep_reference: bool = False  # manual check from the dashboard: compare again later with the same reference


router = APIRouter(prefix="/api/box-check")


def checker(request: Request) -> BoxCheck:
    found = getattr(request.app.state, "box_check", None)
    if found is None:
        raise HTTPException(503, "상자 확인 카메라가 시작되지 않았습니다.")
    return found


@router.get("/status")
def box_status(request: Request):
    return checker(request).status()


@router.get("/frame.jpg")
def box_frame(request: Request):
    data = checker(request).jpeg()
    if data is None:
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/image/{kind}.jpg")
def box_image(kind: str, request: Request):
    data = checker(request).images.get(kind)
    if data is None:
        raise HTTPException(404, "아직 사진이 없습니다.")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/cameras")
def box_cameras():
    from .capture import camera_devices
    return {"devices": [d for d in camera_devices() if "realsense" not in d["name"].lower()]}


@router.post("/camera")
def box_camera(body: CameraInput, request: Request):
    checker(request).use_camera(body.index)
    return checker(request).status()


@router.post("/box")
def box_area(body: BoxInput, request: Request):
    if any(len(p) != 2 or not all(0.0 <= v <= 1.0 for v in p) for p in body.points):
        raise HTTPException(422, "상자 영역 좌표는 0~1 사이의 [x, y] 목록이어야 합니다.")
    checker(request).set_box(body.points)
    return checker(request).status()


@router.delete("/box")
def box_area_reset(request: Request):
    checker(request).reset_box()
    return checker(request).status()


@router.post("/reference")
def box_reference(request: Request, body: CheckInput | None = None):
    return checker(request).take_reference(body.label if body else None)


@router.post("/verify")
def box_verify(request: Request, body: CheckInput | None = None):
    return checker(request).verify(body.label if body else None, body.keep_reference if body else False)
