"""Find objects standing on the table from one aligned RealSense depth frame.

No trained model: the table is the dominant plane inside the calibrated work area, so every
blob that rises above it is an object. For each blob the top-face centre is pushed down along
the table normal to the table, and that "foot" pixel is what the 4-corner calibration maps to
robot BASE X/Y (the calibration is a table-plane homography, so tall objects must not be mapped
by their top pixel, which perspective shifts away from the camera axis).
"""
import numpy as np

MIN_HEIGHT_MM = 15.0
MIN_AREA_PX = 120
PLANE_TOL_M = 0.006
SEARCH_MARGIN = 0.12  # grow the corner quad so objects placed right at a corner are still seen


def _quad_mask(shape, quad, margin):
    import cv2

    pts = np.asarray(quad, dtype=np.float32)
    centre = pts.mean(axis=0)
    grown = centre + (pts - centre) * (1.0 + margin)
    mask = np.zeros(shape, np.uint8)
    cv2.fillPoly(mask, [np.round(grown).astype(np.int32)], 1)
    return mask.astype(bool)


def _deproject(u, v, d, intrinsics):
    fx, fy, cx, cy = intrinsics
    return np.stack([(u - cx) * d / fx, (v - cy) * d / fy, d], axis=-1)


def _project(point, intrinsics):
    fx, fy, cx, cy = intrinsics
    return [float(fx * point[0] / point[2] + cx), float(fy * point[1] / point[2] + cy)]


def fit_table_plane(points, iterations=300, tol=PLANE_TOL_M, seed=0):
    """RANSAC plane (unit normal n, offset c) with n pointing toward the camera (n_z < 0)."""
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(iterations):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(b - a, c - a)
        norm = np.linalg.norm(normal)
        if norm < 1e-9:
            continue
        normal /= norm
        inliers = np.abs(points @ normal - normal @ a) < tol
        if best is None or inliers.sum() > best.sum():
            best = inliers
    table = points[best]
    centroid = table.mean(axis=0)
    normal = np.linalg.svd(table - centroid)[2][2]
    if normal[2] > 0:
        normal = -normal
    return normal, -float(normal @ centroid), float(best.mean())


def find_objects(depth, intrinsics, quad, min_height_mm=MIN_HEIGHT_MM, min_area_px=MIN_AREA_PX,
                 margin=SEARCH_MARGIN):
    """Objects above the table inside the (slightly grown) work-area quad, largest first.

    depth: HxW metres aligned to colour (0 = no data); intrinsics: (fx, fy, ppx, ppy);
    quad: the four calibration corner pixels. Each object has `pixel` (foot point on the table,
    for the calibration), `top_pixel`, `height_mm`, `area_px` and `bbox` [x0, y0, x1, y1].
    """
    import cv2

    if depth is None or intrinsics is None:
        raise ValueError('depth frame with intrinsics is required')
    h, w = depth.shape
    area = _quad_mask((h, w), quad, margin) & (depth > 0)
    if area.sum() < 500:
        raise ValueError('too few valid depth pixels in the work area')
    vs, us = np.nonzero(area)
    points = _deproject(us.astype(np.float32), vs.astype(np.float32), depth[vs, us], intrinsics)
    sample = points[np.random.default_rng(1).choice(len(points), min(len(points), 6000), replace=False)]
    normal, offset, table_share = fit_table_plane(sample)

    heights = np.zeros((h, w), np.float32)
    heights[vs, us] = (points @ normal + offset) * 1000.0  # mm above the table
    raised = (heights > min_height_mm).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    raised = cv2.morphologyEx(cv2.morphologyEx(raised, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(raised, connectivity=8)

    objects = []
    for label in range(1, count):
        x0, y0, bw, bh, n = stats[label]
        if n < min_area_px:
            continue
        # Closing can pull no-depth pixels into the blob; they have no 3-D point.
        bv, bu = np.nonzero((labels == label) & area)
        if len(bv) < min_area_px // 2:
            continue
        blob_h = heights[bv, bu]
        top = float(np.percentile(blob_h, 90))
        face = blob_h >= top - 15.0
        fu, fv = bu[face].astype(np.float32), bv[face].astype(np.float32)
        top_point = _deproject(fu, fv, depth[bv[face], bu[face]], intrinsics).mean(axis=0)
        foot = top_point - normal * (top / 1000.0)
        # Footprint as seen from above: every blob point dropped onto the table, then its
        # minimum-area rectangle in pixels (the route maps the corners to robot BASE).
        pts = _deproject(bu.astype(np.float32), bv.astype(np.float32), depth[bv, bu], intrinsics)
        drop = pts - np.outer(blob_h / 1000.0, normal)
        fx, fy, cx, cy = intrinsics
        foot_px = np.stack([fx * drop[:, 0] / drop[:, 2] + cx, fy * drop[:, 1] / drop[:, 2] + cy], axis=1)
        rect = cv2.boxPoints(cv2.minAreaRect(foot_px.astype(np.float32)))
        if not (np.isfinite(foot).all() and np.isfinite(rect).all()):
            continue
        objects.append(dict(pixel=[round(c, 1) for c in _project(foot, intrinsics)],
                            top_pixel=[round(float(fu.mean()), 1), round(float(fv.mean()), 1)],
                            height_mm=round(top, 1), area_px=int(n),
                            bbox=[int(x0), int(y0), int(x0 + bw), int(y0 + bh)],
                            footprint_px=[[round(float(x), 1), round(float(y), 1)] for x, y in rect]))
    objects.sort(key=lambda o: o['area_px'], reverse=True)
    return dict(objects=objects, table_share=round(table_share, 3),
                table_normal=[round(float(v), 4) for v in normal])
