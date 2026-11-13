"""Packing-box webcam: reference before the pick, check after placing -> landed / missing / uncertain."""
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from app.box_check import DEFAULT_BOX, BoxCheck, compare
from app.config import Settings
from app.main import create_app


def empty_box(seed=0):
    """Cardboard-coloured box interior with a little sensor noise."""
    rng = np.random.default_rng(seed)
    frame = np.full((480, 640, 3), (150, 175, 195), np.int16)
    frame[:, :80] -= 25                    # left wall in shade
    frame += rng.integers(-4, 5, frame.shape)
    return np.clip(frame, 0, 255).astype(np.uint8)


def with_item(frame, box=(260, 280, 380, 400), colour=(40, 60, 170)):
    out = frame.copy()
    x1, y1, x2, y2 = box
    out[y1:y2, x1:x2] = colour
    return out


class CompareTests(unittest.TestCase):
    def test_item_in_the_box_is_landed_with_its_blob(self):
        found = compare(empty_box(1), with_item(empty_box(2)), DEFAULT_BOX)
        self.assertEqual(found["verdict"], "landed")
        x1, y1, x2, y2 = found["blob"]
        self.assertAlmostEqual(x1, 260 / 640, delta=0.02)
        self.assertAlmostEqual(y2, 400 / 480, delta=0.02)

    def test_unchanged_box_is_missing(self):
        self.assertEqual(compare(empty_box(1), empty_box(2), DEFAULT_BOX)["verdict"], "missing")

    def test_auto_exposure_shift_alone_is_not_an_item(self):
        brighter = np.clip(empty_box(2).astype(np.int16) + 40, 0, 255).astype(np.uint8)
        found = compare(empty_box(1), brighter, DEFAULT_BOX)
        self.assertEqual(found["verdict"], "missing")
        self.assertLess(found["change"], 0.01)

    def test_change_outside_the_box_area_is_ignored(self):
        outside = with_item(empty_box(2), box=(100, 0, 500, 40))  # strip above the far rim
        self.assertEqual(compare(empty_box(1), outside, DEFAULT_BOX)["verdict"], "missing")

    def test_whole_picture_changed_is_uncertain(self):
        ramp = np.tile(np.linspace(0, 255, 640, dtype=np.uint8)[None, :, None], (480, 1, 3))
        self.assertEqual(compare(empty_box(1), ramp, DEFAULT_BOX)["verdict"], "uncertain")  # camera knocked
        dark = np.full((480, 640, 3), 10, np.uint8)
        self.assertEqual(compare(empty_box(1), dark, DEFAULT_BOX)["verdict"], "uncertain")  # lights off

    def test_cream_coloured_item_on_cardboard_still_counts(self):
        cream = with_item(empty_box(2), colour=(200, 225, 235))  # wet wipes pack: close to cardboard
        self.assertEqual(compare(empty_box(1), cream, DEFAULT_BOX)["verdict"], "landed")


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.check = BoxCheck(Path(self.temp.name) / "box.json", Settings(camera_autostart=False))
        self.check.camera.update(ok=True)

    def feed(self, frame):
        """Pretend the camera loop delivered `frame` a moment after the request."""
        import threading

        def later():
            time.sleep(0.45)
            with self.check.lock:
                self.check._frame, self.check._frame_at = frame, time.monotonic()
        threading.Thread(target=later, daemon=True).start()

    def test_reference_then_verify_and_the_reference_moves_on(self):
        self.feed(empty_box(1))
        self.check.take_reference("before")
        self.feed(with_item(empty_box(2)))
        first = self.check.verify("item 1/2")
        self.assertTrue(first["ok"])
        self.assertIn("after", self.check.images)
        # The second check compares with the box that already holds item 1: nothing new -> missing.
        self.feed(with_item(empty_box(3)))
        second = self.check.verify("item 2/2")
        self.assertEqual(second["verdict"], "missing")
        self.assertEqual([h["label"] for h in self.check.status()["history"]], ["item 1/2", "item 2/2"])

    def test_manual_check_keeps_the_reference(self):
        self.feed(empty_box(1))
        self.check.take_reference("empty")
        for _ in range(2):  # pressing "지금 확인" again still compares with the empty box
            self.feed(with_item(empty_box(2)))
            self.assertTrue(self.check.verify("manual", keep_reference=True)["ok"])
        self.assertEqual(self.check.status()["reference_label"], "empty")

    def test_box_area_persists_and_drops_the_old_reference(self):
        self.feed(empty_box(1))
        self.check.take_reference()
        self.check.set_box([[0.1, 0.2], [0.9, 0.2], [0.9, 0.9], [0.1, 0.9]])
        self.assertIsNone(self.check.status()["reference"])
        again = BoxCheck(Path(self.temp.name) / "box.json", Settings(camera_autostart=False))
        self.assertEqual(again.box[0], [0.1, 0.2])


class ApiTests(unittest.TestCase):
    def test_endpoints_without_a_webcam(self):
        with tempfile.TemporaryDirectory() as temp:
            app = create_app(Settings(camera_autostart=False), state_root=temp)
            with TestClient(app) as c:
                status = c.get("/api/box-check/status").json()
                self.assertEqual(status["box"], DEFAULT_BOX)
                self.assertIsNone(status["last"])
                self.assertEqual(c.get("/api/box-check/frame.jpg").status_code, 204)
                self.assertEqual(c.post("/api/box-check/verify", json={"label": "x"}).status_code, 409)
                bad = c.post("/api/box-check/box", json={"points": [[0, 0], [2, 0], [0, 1]]})
                self.assertEqual(bad.status_code, 422)
                ok = c.post("/api/box-check/box", json={"points": [[0, 0.1], [1, 0.1], [1, 1], [0, 1]]})
                self.assertEqual(ok.json()["box"][0], [0, 0.1])
                self.assertEqual(c.get("/api/box-check/image/after.jpg").status_code, 404)


if __name__ == "__main__":
    unittest.main()
