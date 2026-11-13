"""Product YOLO: depth-labelled photos -> CPU training -> "where is product X" for the robot cycle.

Capture: one product stands anywhere in the work area; the RealSense depth finds it (robot_pick
locate_depth_objects) and its pixel box becomes the YOLO label of the colour photo of the same frame, so no
box is drawn by hand. Training runs scripts/train_products.py in a subprocess on the CPU. Locate: the active
model finds the product in the newest colour frame and the depth object under that box gives the robot its
position, height and grip direction (the same fields the zone mode used).
"""
import json
import logging
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]

# YOLO class order (class id = index). Keys are the cycle's product names (yolo_class_name of a task).
PRODUCTS = (
    ("wet_wipes", "물티슈"),
    ("canned_meat", "스팸"),
    ("snack_pepero", "쫀득초코칩"),
    ("beverage_pet", "복숭아녹차"),
)
NAMES = dict(PRODUCTS)
BOX_PAD_PX = 4          # depth blobs sit a little inside the colour outline
MIN_CONFIDENCE = 0.5
MIN_OVERLAP = 0.3       # share of the YOLO box covered by the matched depth blob's box


def box_overlap(det, blob):
    """Intersection area divided by the YOLO box area."""
    x1, y1 = max(det[0], blob[0]), max(det[1], blob[1])
    x2, y2 = min(det[2], blob[2]), min(det[3], blob[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area = max(1e-6, (det[2] - det[0]) * (det[3] - det[1]))
    return inter / area


def yolo_label(box, width, height, class_id):
    x1, y1, x2, y2 = box
    return f"{class_id} {(x1 + x2) / 2 / width:.6f} {(y1 + y2) / 2 / height:.6f} " \
           f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}\n"


def match_detection(product, detections, objects, min_confidence=MIN_CONFIDENCE, min_overlap=MIN_OVERLAP):
    """Best detection of `product` and the depth object under it -> (detection, object), or raise ValueError."""
    candidates = sorted((d for d in detections if d["product"] == product and d["confidence"] >= min_confidence),
                        key=lambda d: -d["confidence"])
    if not candidates:
        seen = ", ".join(sorted({f"{NAMES.get(d['product'], d['product'])} {d['confidence']:.2f}" for d in detections}))
        raise ValueError(f"카메라에서 {NAMES.get(product, product)}을(를) 찾지 못했습니다" + (f" (보이는 것: {seen})" if seen else ""))
    for det in candidates:
        inside = [o for o in objects if o.get("inside") and o.get("base")]
        scored = sorted(((box_overlap(det["xyxy"], o["bbox"]), o) for o in inside), key=lambda t: -t[0])
        if scored and scored[0][0] >= min_overlap:
            return det, scored[0][1]
    raise ValueError(f"{NAMES.get(product, product)}은(는) 보이지만 작업 영역 안의 깊이 물체와 맞지 않습니다 "
                     "(작업 영역 밖이거나 다른 물건과 붙어 있음)")


class ProductVision:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.samples = self._read("samples.json", [])
        self.process = None
        self._model, self._model_path, self._model_mtime = None, None, None

    # ---- files ---------------------------------------------------------------------------------
    def _read(self, name, default):
        try:
            return json.loads((self.root / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write(self, name, data):
        path = self.root / name
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)

    # ---- capture -------------------------------------------------------------------------------
    def capture(self, product, color, objects):
        import cv2
        if product not in NAMES:
            raise HTTPException(422, f"알 수 없는 상품: {product}")
        inside = [o for o in objects if o.get("inside")]
        if len(inside) != 1:
            raise HTTPException(409, f"작업 영역 안에 물체가 {len(inside)}개 보입니다. "
                                     f"{NAMES[product]} 하나만 놓고 다시 찍으세요.")
        h, w = color.shape[:2]
        x0, y0, x1, y1 = inside[0]["bbox"]
        box = [max(0, x0 - BOX_PAD_PX), max(0, y0 - BOX_PAD_PX), min(w - 1, x1 + BOX_PAD_PX), min(h - 1, y1 + BOX_PAD_PX)]
        identifier = f"{product}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
        images, labels = self.root / "images", self.root / "labels"
        images.mkdir(exist_ok=True)
        labels.mkdir(exist_ok=True)
        class_id = [p for p, _ in PRODUCTS].index(product)
        if not cv2.imwrite(str(images / f"{identifier}.jpg"), color, [cv2.IMWRITE_JPEG_QUALITY, 95]):
            raise HTTPException(500, "사진을 저장하지 못했습니다.")
        (labels / f"{identifier}.txt").write_text(yolo_label(box, w, h, class_id), encoding="utf-8")
        sample = {"id": identifier, "product": product, "box": [int(v) for v in box], "width": w, "height": h,
                  "height_mm": inside[0].get("height_mm"), "base": inside[0].get("base"),
                  "time": datetime.now().strftime("%H:%M:%S")}
        with self.lock:
            self.samples.append(sample)
            self._write("samples.json", self.samples)
        return sample

    def delete(self, identifier):
        with self.lock:
            before = len(self.samples)
            self.samples = [s for s in self.samples if s["id"] != identifier]
            if len(self.samples) == before:
                raise HTTPException(404, "없는 사진입니다.")
            self._write("samples.json", self.samples)
        for path in (self.root / "images" / f"{identifier}.jpg", self.root / "labels" / f"{identifier}.txt"):
            path.unlink(missing_ok=True)

    def preview(self, identifier):
        """The saved photo with its label box drawn in."""
        import cv2
        sample = next((s for s in self.samples if s["id"] == identifier), None)
        if sample is None:
            raise HTTPException(404, "없는 사진입니다.")
        image = cv2.imread(str(self.root / "images" / f"{identifier}.jpg"))
        if image is None:
            raise HTTPException(404, "사진 파일이 없습니다.")
        x0, y0, x1, y1 = sample["box"]
        cv2.rectangle(image, (x0, y0), (x1, y1), (60, 220, 60), 2)
        ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return data.tobytes()

    # ---- training ------------------------------------------------------------------------------
    def training(self):
        progress = self._read("training.json", None)
        running = self.process is not None and self.process.poll() is None
        if progress and progress.get("state") in ("preparing", "training") and not running:
            progress = {**progress, "state": "failed", "error": progress.get("error") or "학습 프로세스가 종료되었습니다. 로그를 확인하세요."}
        return progress

    def start_training(self, epochs, imgsz):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                raise HTTPException(409, "이미 학습 중입니다.")
            counts = {p: sum(s["product"] == p for s in self.samples) for p, _ in PRODUCTS}
            short = [NAMES[p] for p, n in counts.items() if n < 10]
            if short:
                raise HTTPException(422, f"상품마다 사진이 10장 이상 필요합니다 (부족: {', '.join(short)}).")
            base = self.root / "yolov8n.pt"
            if not base.is_file():
                raise HTTPException(422, f"기본 가중치가 없습니다: {base}")
            run = f"run-{datetime.now():%Y%m%d-%H%M%S}"
            self._write("training.json", {"state": "preparing", "run": run, "epochs": epochs, "epoch": 0,
                                          "started": datetime.now().strftime("%H:%M:%S")})
            log_file = (self.root / f"{run}.log").open("w")
            self.process = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts" / "train_products.py"), "--root", str(self.root),
                 "--run", run, "--epochs", str(epochs), "--imgsz", str(imgsz)],
                cwd=ROOT, stdout=log_file, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True)
            log_file.close()
            return self.training()

    def cancel_training(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            progress = self._read("training.json", {})
            self._write("training.json", {**progress, "state": "cancelled"})

    def stop(self):
        self.cancel_training()

    # ---- detection -----------------------------------------------------------------------------
    def active(self):
        return self._read("active.json", None)

    def model(self):
        active = self.active()
        if not active:
            raise HTTPException(409, "학습된 상품 모델이 없습니다. 사진을 찍고 학습을 먼저 하세요.")
        path = self.root / active["path"]
        mtime = path.stat().st_mtime if path.is_file() else None
        if mtime is None:
            raise HTTPException(409, f"모델 파일이 없습니다: {path}")
        with self.lock:
            if self._model is None or self._model_path != path or self._model_mtime != mtime:
                from ultralytics import YOLO
                self._model, self._model_path, self._model_mtime = YOLO(str(path), task="detect"), path, mtime
            return self._model

    def detect(self, color):
        model = self.model()
        with self.lock:
            result = model.predict(color, imgsz=640, device="cpu", conf=0.25, verbose=False)[0]
        names = result.names
        out = []
        for xyxy, conf, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
            product = names[int(cls)]
            out.append({"product": product, "name": NAMES.get(product, product), "confidence": round(float(conf), 3),
                        "xyxy": [round(float(v), 1) for v in xyxy]})
        return out

    def status(self):
        counts = {p: sum(s["product"] == p for s in self.samples) for p, _ in PRODUCTS}
        return {"products": [{"key": p, "name": n, "count": counts[p]} for p, n in PRODUCTS],
                "total": len(self.samples), "recent": self.samples[-12:][::-1],
                "training": self.training(), "active": self.active()}


# ---- HTTP -----------------------------------------------------------------------------------------
class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CaptureInput(Input):
    product: str = Field(min_length=1, max_length=40)


class TrainInput(Input):
    epochs: int = Field(default=60, ge=1, le=300)
    imgsz: int = Field(default=640, ge=320, le=1280)


router = APIRouter(prefix="/api/product-vision")


def vision(request: Request) -> ProductVision:
    found = getattr(request.app.state, "product_vision", None)
    if found is None:
        raise HTTPException(503, "상품 인식이 시작되지 않았습니다.")
    return found


async def _frame_objects(request):
    """Colour image and depth objects of one RealSense frame."""
    from .robot_pick import locate_depth_objects
    sensors = request.app.state.pipeline.latest_sensors()
    found = await locate_depth_objects(request.app, sensors=sensors)
    return sensors.color, found["objects"]


@router.get("/status")
def pv_status(request: Request):
    return vision(request).status()


@router.post("/capture")
async def pv_capture(body: CaptureInput, request: Request):
    color, objects = await _frame_objects(request)
    return vision(request).capture(body.product, color, objects)


@router.delete("/samples/{identifier}")
def pv_delete(identifier: str, request: Request):
    vision(request).delete(identifier)
    return vision(request).status()


@router.get("/samples/{identifier}.jpg")
def pv_sample(identifier: str, request: Request):
    return Response(vision(request).preview(identifier), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=3600"})


@router.post("/train", status_code=202)
def pv_train(request: Request, body: TrainInput | None = None):
    body = body or TrainInput()
    return vision(request).start_training(body.epochs, body.imgsz)


@router.post("/train/cancel")
def pv_cancel(request: Request):
    vision(request).cancel_training()
    return vision(request).status()


@router.get("/detect")
async def pv_detect(request: Request):
    import asyncio
    color, objects = await _frame_objects(request)
    detections = await asyncio.to_thread(vision(request).detect, color)
    return {"detections": detections, "objects": objects, "size": [color.shape[1], color.shape[0]]}


@router.get("/locate")
async def pv_locate(product: str, request: Request):
    """Where the robot should pick `product`: the depth object under the best YOLO box of that product."""
    import asyncio
    from .robot_pick import locate_depth_objects
    sensors = request.app.state.pipeline.latest_sensors()
    found = await locate_depth_objects(request.app, sensors=sensors)
    detections = await asyncio.to_thread(vision(request).detect, sensors.color)
    try:
        det, obj = match_detection(product, detections, found["objects"])
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"product": product, "detection": det, "object": obj, "detections": detections,
            "revision": found["revision"]}
