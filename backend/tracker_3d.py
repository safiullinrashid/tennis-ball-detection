import numpy as np
from collections import deque

COURT_W = 274.0
COURT_H = 152.5
TABLE_H = 76.0
NET_H = 15.25

class BallTracker3D:
    def __init__(self, max_history=500):
        self.trajectory_3d = []
        self.history_top = deque(maxlen=2)
        self.history_side = deque(maxlen=2)
        self.frame_count = 0

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
            MAX_H = TABLE_H + NET_H * 2

            if camera == 'top' and bounds is not None:
                bx, by, bw, bh = bounds
                rx = (px - bx) / bw
                ry = (py - by) / bh
                lx = (1 - ry) * COURT_W
                ly = (1 - rx) * COURT_H
            elif camera == 'top':
                lx = (1 - py / fh) * COURT_W
                ly = (1 - px / fw) * COURT_H
            else:
                lx = (px / fw) * COURT_W
                ly = max(0, min(MAX_H, (1 - py / fh) * TABLE_H * 2))
            return lx, ly

        length_from_top, width_from_top = _to_table_coords(
            x_top, y_top, table_top, w_top, h_top, 'top')
        length_from_side, height = _to_table_coords(
            x_side, y_side, table_side, w_side, h_side, 'side')

        x_final = (length_from_top + length_from_side) / 2
        height = min(height, TABLE_H + NET_H * 2)

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

    def get_trajectory_3d(self):
        if self.trajectory_3d:
            zs = [p['Z'] for p in self.trajectory_3d]
            min_z = min(zs)
            shift = TABLE_H - min_z
            if abs(shift) > 1:
                print(f"  Коррекция Z: min={min_z:.0f} → shift={shift:.0f} до TABLE_H={TABLE_H}")
                for p in self.trajectory_3d:
                    p['Z'] = max(0, round(p['Z'] + shift, 1))
        return self.trajectory_3d