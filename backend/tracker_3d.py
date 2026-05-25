import cv2
import numpy as np
from collections import deque
from scipy.ndimage import uniform_filter1d

COURT_W = 274.0
COURT_H = 152.5
TABLE_H = 76.0
NET_H = 15.25

class BallTracker3D:
    def __init__(self, max_history=500, M_top=None, M_side=None):
        self.trajectory_3d = []
        self.history_top = deque(maxlen=2)
        self.history_side = deque(maxlen=2)
        self.frame_count = 0
        self.M_top = M_top
        self.M_side = M_side

    def update(self, detections_top, detections_side, shape_top, shape_side,
               table_top=None, table_side=None):
        self.frame_count += 1

        point_top = self._best_point(detections_top)
        point_side = self._best_point(detections_side)

        if point_top is None or point_side is None:
            return None

        x_top, y_top = point_top
        x_side, y_side = point_side

        h_top, w_top = shape_top[:2]
        h_side, w_side = shape_side[:2]

        def _to_table_coords(px, py, bounds, fw, fh, camera):
            M = self.M_top if camera == 'top' else self.M_side
            if M is not None:
                pts = np.array([[[px, py]]], dtype=np.float32)
                transformed = cv2.perspectiveTransform(pts, M)
                return float(transformed[0, 0, 0]), float(transformed[0, 0, 1])

            if camera == 'top' and bounds is not None:
                bx, by, bw, bh = bounds
                rx = (px - bx) / bw
                ry = (py - by) / bh
                lx = (1 - ry) * COURT_W
                ly = (1 - rx) * COURT_H
            elif camera == 'top':
                lx = (1 - py / fh) * COURT_W
                ly = (1 - px / fw) * COURT_H
            else:  # side camera
                if bounds is not None:
                    bx, by, bw, bh = bounds
                    scale = COURT_W / bw if bw > 0 else 1.0
                    table_center_px = bx + bw / 2
                    real_center = COURT_W / 2
                    offset_px = px - table_center_px
                    lx = real_center + offset_px * scale
                    pixels_above_table = (by + bh - py)
                    ly = TABLE_H + pixels_above_table * scale
                else:
                    lx = (px / fw) * COURT_W
                    ly = (1 - py / fh) * TABLE_H * 2
            return lx, ly

        length_from_top, width_from_top = _to_table_coords(
            x_top, y_top, table_top, w_top, h_top, 'top')
        length_from_side, height = _to_table_coords(
            x_side, y_side, table_side, w_side, h_side, 'side')

        x_final = (length_from_top + length_from_side) / 2

        point_3d = {
            "frame": self.frame_count,
            "X": round(x_final, 1),
            "Y": round(width_from_top, 1),
            "Z": round(height, 1)
        }
        self.trajectory_3d.append(point_3d)
        self.history_top.append((length_from_top, width_from_top))
        self.history_side.append((length_from_side, height))

        return point_3d

    def _best_point(self, detections):
        if not detections:
            return None
        best = max(detections, key=lambda d: d['confidence'])
        return best['center']

    def _smooth_series(self, values, window=5):
        if len(values) < window * 2:
            return values
        arr = np.array(values, dtype=float)
        return uniform_filter1d(arr, size=window, mode='nearest').tolist()

    def get_trajectory_3d(self):
        if not self.trajectory_3d:
            return []
        pts = self.trajectory_3d

        xs = self._smooth_series([p['X'] for p in pts])
        ys = self._smooth_series([p['Y'] for p in pts])
        zs = self._smooth_series([p['Z'] for p in pts])
        min_z = min(zs)
        shift = TABLE_H - min_z
        if abs(shift) > 2:
            zs = [round(z + shift, 1) for z in zs]
        result = []
        for i, p in enumerate(pts):
            result.append({
                "frame": p['frame'],
                "X": round(xs[i], 1),
                "Y": round(ys[i], 1),
                "Z": round(zs[i], 1)
            })
        return result
