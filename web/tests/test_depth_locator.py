"""Depth-only object finding: synthetic tilted table with two boxes seen by a pinhole camera."""
import numpy as np

from app.depth_locator import find_objects

FX = FY = 380.0
CX, CY = 320.0, 240.0
INTR = (FX, FY, CX, CY)


def render(boxes, tilt=0.03, base_depth=0.95):
    """Depth of a slightly tilted table plus axis-aligned boxes given in table metres."""
    v, u = np.mgrid[:480, :640].astype(np.float64)
    rx, ry = (u - CX) / FX, (v - CY) / FY
    # table plane z = base_depth + tilt * y  (camera frame); ray (rx, ry, 1) * t
    depth = base_depth / (1.0 - tilt * ry)
    for (bx, by, half, height) in boxes:  # box top at plane height `height` above the table
        top = base_depth - height
        t = top / (1.0 - tilt * ry)
        x, y = rx * t, ry * t
        inside = (np.abs(x - bx) < half) & (np.abs(y - by) < half)
        depth = np.where(inside, np.minimum(depth, t), depth)
    return depth.astype(np.float32)


def test_finds_boxes_with_height_and_foot_pixel():
    boxes = [(0.12, -0.08, 0.04, 0.10), (-0.15, 0.10, 0.03, 0.05)]
    depth = render(boxes)
    quad = [[60, 40], [580, 40], [580, 440], [60, 440]]
    found = find_objects(depth, INTR, quad)
    assert len(found['objects']) == 2 and found['table_share'] > 0.7
    tall, short = found['objects']
    assert abs(tall['height_mm'] - 100) < 8 and abs(short['height_mm'] - 50) < 8
    # foot pixel = where the box centre meets the table, i.e. the box centre at table depth
    for obj, (bx, by, _, _) in ((tall, boxes[0]), (short, boxes[1])):
        table_t = 0.95 / (1.0 - 0.03 * (by / 0.95))
        expect = [FX * bx / table_t + CX, FY * by / table_t + CY]
        assert np.hypot(obj['pixel'][0] - expect[0], obj['pixel'][1] - expect[1]) < 4
    # the top pixel is pushed outward by perspective, the foot pixel is not
    assert abs(tall['top_pixel'][0] - CX) > abs(tall['pixel'][0] - CX)


def test_flat_table_has_no_objects_and_holes_are_ignored():
    depth = render([])
    depth[200:220, 300:330] = 0.0  # missing depth is not an object
    found = find_objects(depth, INTR, [[60, 40], [580, 40], [580, 440], [60, 440]])
    assert found['objects'] == []


def test_footprint_is_measured_at_table_level():
    depth = render([(0.0, 0.0, 0.04, 0.15)])  # 80 mm square, 150 mm tall, centred
    obj = find_objects(depth, INTR, [[60, 40], [580, 40], [580, 440], [60, 440]])['objects'][0]
    (x0, y0), (x1, y1), (x2, y2) = obj['footprint_px'][:3]
    sides = sorted([np.hypot(x1 - x0, y1 - y0), np.hypot(x2 - x1, y2 - y1)])
    expect = 0.08 * FX / 0.95  # top face dropped to the table, not its larger near-camera image
    assert all(abs(s - expect) < 4 for s in sides)


def test_depth_holes_inside_an_object_do_not_produce_nan():
    depth = render([(0.0, 0.0, 0.04, 0.10)])
    depth[236:240, 318:322] = 0.0  # specular hole in the box top
    obj = find_objects(depth, INTR, [[60, 40], [580, 40], [580, 440], [60, 440]])['objects'][0]
    assert np.isfinite(obj['pixel']).all() and np.isfinite(obj['footprint_px']).all()
