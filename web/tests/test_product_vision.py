"""Product YOLO: depth-labelled capture, YOLO box -> depth object matching, training preconditions."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi import HTTPException

from app.product_vision import ProductVision, box_overlap, match_detection, yolo_label


def obj(bbox, base=(500.0, 0.0), inside=True, height=60.0):
    return {"bbox": list(bbox), "base": list(base), "inside": inside, "height_mm": height}


def det(product, xyxy, confidence=0.9):
    return {"product": product, "confidence": confidence, "xyxy": list(xyxy)}


class MatchTests(unittest.TestCase):
    def test_label_is_normalised_centre_and_size(self):
        self.assertEqual(yolo_label([160, 120, 480, 360], 640, 480, 2), "2 0.500000 0.500000 0.500000 0.500000\n")

    def test_overlap_is_share_of_the_yolo_box(self):
        self.assertAlmostEqual(box_overlap([0, 0, 10, 10], [5, 0, 20, 10]), 0.5)
        self.assertEqual(box_overlap([0, 0, 10, 10], [20, 20, 30, 30]), 0.0)

    def test_picks_the_depth_object_under_the_requested_product(self):
        spam = obj([100, 100, 160, 150], base=(600, -50))
        wipes = obj([300, 200, 420, 260], base=(500, 100))
        detections = [det("wet_wipes", [295, 195, 425, 262]), det("canned_meat", [98, 102, 158, 152], 0.8)]
        found, target = match_detection("canned_meat", detections, [wipes, spam])
        self.assertEqual(found["product"], "canned_meat")
        self.assertEqual(target["base"], [600, -50])

    def test_not_seen_names_what_is_visible(self):
        with self.assertRaises(ValueError) as ctx:
            match_detection("canned_meat", [det("wet_wipes", [0, 0, 10, 10])], [obj([0, 0, 10, 10])])
        self.assertIn("스팸", str(ctx.exception))
        self.assertIn("물티슈", str(ctx.exception))

    def test_low_confidence_or_outside_the_work_area_is_not_used(self):
        with self.assertRaises(ValueError):
            match_detection("canned_meat", [det("canned_meat", [0, 0, 10, 10], 0.3)], [obj([0, 0, 10, 10])])
        with self.assertRaises(ValueError) as ctx:
            match_detection("canned_meat", [det("canned_meat", [0, 0, 10, 10])], [obj([0, 0, 10, 10], inside=False)])
        self.assertIn("깊이 물체와 맞지 않습니다", str(ctx.exception))


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pv = ProductVision(Path(self.temp.name))
        self.color = np.full((480, 640, 3), 120, np.uint8)

    def test_one_object_is_saved_with_its_depth_box_as_label(self):
        sample = self.pv.capture("canned_meat", self.color, [obj([100, 100, 200, 180]), obj([0, 0, 5, 5], inside=False)])
        self.assertEqual(sample["box"], [96, 96, 204, 184])  # padded
        label = (Path(self.temp.name) / "labels" / f"{sample['id']}.txt").read_text()
        self.assertTrue(label.startswith("1 "))  # canned_meat is class 1
        self.assertTrue((Path(self.temp.name) / "images" / f"{sample['id']}.jpg").is_file())
        again = ProductVision(Path(self.temp.name))  # the index survives a restart
        self.assertEqual(again.status()["products"][1]["count"], 1)
        self.assertTrue(self.pv.preview(sample["id"]).startswith(b"\xff\xd8"))
        self.pv.delete(sample["id"])
        self.assertEqual(self.pv.status()["total"], 0)

    def test_zero_or_two_objects_are_refused(self):
        for objects in ([], [obj([0, 0, 50, 50]), obj([100, 100, 150, 150])]):
            with self.assertRaises(HTTPException) as ctx:
                self.pv.capture("wet_wipes", self.color, objects)
            self.assertEqual(ctx.exception.status_code, 409)
        with self.assertRaises(HTTPException):
            self.pv.capture("doll", self.color, [obj([0, 0, 50, 50])])

    def test_training_needs_ten_photos_of_every_product(self):
        for _ in range(10):
            self.pv.capture("wet_wipes", self.color, [obj([10, 10, 60, 60])])
        with self.assertRaises(HTTPException) as ctx:
            self.pv.start_training(1, 320)
        self.assertIn("스팸", ctx.exception.detail)

    def test_no_model_yet(self):
        with self.assertRaises(HTTPException) as ctx:
            self.pv.detect(self.color)
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
