"""Train the product YOLO on the depth-labelled photos (web/app/product_vision.py) on the CPU.

Run by the web server: python scripts/train_products.py --root state/product_vision --run run-... --epochs 60
Writes <root>/training.json (progress), and on success <root>/models/<run>.pt + <root>/active.json.
"""
import argparse
import json
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from app.product_vision import PRODUCTS  # noqa: E402

VAL_SHARE = 0.2


def write(root, name, data):
    path = root / name
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def build_dataset(root, run, seed=42):
    """Per product 80/20 split of the captured photos into <root>/datasets/<run> (YOLO layout)."""
    samples = json.loads((root / "samples.json").read_text(encoding="utf-8"))
    directory = root / "datasets" / run
    rng = random.Random(seed)
    counts = {"train": 0, "val": 0}
    for product, _ in PRODUCTS:
        mine = [s for s in samples if s["product"] == product]
        rng.shuffle(mine)
        n_val = max(1, round(len(mine) * VAL_SHARE))
        for i, sample in enumerate(mine):
            split = "val" if i < n_val else "train"
            for kind, ext in (("images", ".jpg"), ("labels", ".txt")):
                target = directory / kind / split
                target.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / kind / f"{sample['id']}{ext}", target / f"{sample['id']}{ext}")
            counts[split] += 1
    (directory / "data.yaml").write_text(json.dumps({
        "path": str(directory), "train": "images/train", "val": "images/val",
        "names": {i: p for i, (p, _) in enumerate(PRODUCTS)}}, ensure_ascii=False), encoding="utf-8")
    return directory, counts


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    state = {"state": "preparing", "run": args.run, "epochs": args.epochs, "epoch": 0,
             "started": datetime.now().strftime("%H:%M:%S")}
    write(root, "training.json", state)
    try:
        directory, counts = build_dataset(root, args.run)
        state.update(counts=counts)
        from ultralytics import YOLO
        from ultralytics.data import utils as data_utils
        data_utils.check_font = lambda *a, **k: None  # offline: no font download for plots
        model = YOLO(str(root / "yolov8n.pt"), task="detect")

        def epoch_end(trainer):
            metrics = {k: round(float(v), 4) for k, v in (trainer.metrics or {}).items()}
            state.update(state="training", epoch=min(trainer.epoch + 1, args.epochs), metrics=metrics,
                         updated=datetime.now().strftime("%H:%M:%S"))
            write(root, "training.json", state)

        model.add_callback("on_train_start", lambda t: (state.update(state="training"), write(root, "training.json", state)))
        model.add_callback("on_fit_epoch_end", epoch_end)
        model.train(data=str(directory / "data.yaml"), epochs=args.epochs, imgsz=args.imgsz, device="cpu",
                    batch=16, workers=4, patience=20, seed=42, project=str(root / "runs"), name=args.run,
                    exist_ok=False, plots=False, verbose=False,
                    # fixed camera over one table: vary light/colour and position, no upside-down products
                    hsv_h=0.01, hsv_s=0.5, hsv_v=0.4, degrees=10.0, translate=0.15, scale=0.3,
                    fliplr=0.5, flipud=0.0, mosaic=1.0, close_mosaic=10)
        best = Path(model.trainer.best)
        if not best.is_file():
            raise RuntimeError("best.pt was not produced")
        (root / "models").mkdir(exist_ok=True)
        target = root / "models" / f"{args.run}.pt"
        shutil.copyfile(best, target)
        metrics = {k: round(float(v), 4) for k, v in (model.trainer.metrics or {}).items()}
        active = {"run": args.run, "path": str(target.relative_to(root)), "metrics": metrics, "counts": counts,
                  "epochs": state["epoch"], "trained": datetime.now().strftime("%Y-%m-%d %H:%M")}
        write(root, "active.json", active)
        state.update(state="done", metrics=metrics, finished=datetime.now().strftime("%H:%M:%S"))
        write(root, "training.json", state)
        return 0
    except Exception as exc:  # noqa: BLE001
        state.update(state="failed", error=f"{type(exc).__name__}: {exc}")
        write(root, "training.json", state)
        raise


if __name__ == "__main__":
    sys.exit(main())
