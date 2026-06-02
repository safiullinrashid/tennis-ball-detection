from ultralytics import YOLO
import cv2
import numpy as np
import torch
import os

COURT_W = 274.0
COURT_H = 152.5
TABLE_H = 76.0
NET_H = 15.25

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TennisBallDetector:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = os.path.join(BASE_DIR, "models", "best.pt")
        self.model = YOLO(model_path)
        if torch.cuda.is_available():
            self.model.to('cuda')

    def detect_video_frame(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([5, 80, 80]), np.array([20, 255, 255]))
        filtered = cv2.bitwise_and(frame, frame, mask=mask)

        results = self.model(filtered, conf=0.5, iou=0.3, augment=False, verbose=False, max_det=1)

        detections = []
        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            for box, conf in zip(boxes, confs):
                x1, y1, x2, y2 = [int(v) for v in box]
                bw, bh = x2 - x1, y2 - y1
                if bw < 8 or bw > 60 or bh < 8 or bh > 60:
                    continue
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "center": [(x1 + x2) / 2, (y1 + y2) / 2],
                    "confidence": float(conf),
                })

        return detections[:1]

class TableDetector:
    def __init__(self):
        self.hsv_lower = np.array([85, 30, 30])
        self.hsv_upper = np.array([145, 255, 255])

    def detect_bounds(self, frame, camera='top'):
        if camera == 'top':
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
            kernel = np.ones((7, 7), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest)
                frame_area = frame.shape[0] * frame.shape[1]
                if area >= frame_area * 0.03:
                    rect = cv2.boundingRect(largest)
                    print(f"  top: blue mask rect={rect}, area={area/frame_area:.1%}")
                    return rect
            return None

        if camera == 'side':
            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (3, 3), 0)
            border_top = int(h * 0.2)
            border_bot = int(h * 0.85)
            step = max(1, w // 60)
            raw_pts = []
            for col in range(0, w, step):
                c_left = max(0, col - 2)
                c_right = min(w, col + 3)
                strip = blur[border_top:border_bot, c_left:c_right]
                row_vals = np.mean(strip, axis=1)
                grad = np.diff(row_vals.astype(float))
                peak = int(np.argmax(grad))
                raw_pts.append((col, border_top + peak))
            if len(raw_pts) < 15:
                return None
            xs = np.array([p[0] for p in raw_pts], dtype=float)
            ys = np.array([p[1] for p in raw_pts], dtype=float)
            A = np.vstack([xs, np.ones(len(xs))]).T
            slope, intercept = np.linalg.lstsq(A, ys, rcond=None)[0]
            pred = slope * xs + intercept
            resid = np.abs(ys - pred)
            good = resid < 2 * np.std(resid) if np.std(resid) > 1 else np.ones(len(xs), dtype=bool)
            if np.sum(good) > 10:
                xs, ys = xs[good], ys[good]
                A = np.vstack([xs, np.ones(len(xs))]).T
                slope, intercept = np.linalg.lstsq(A, ys, rcond=None)[0]
            y_left = slope * 0 + intercept
            y_right = slope * (w - 1) + intercept
            y_min = max(0, min(y_left, y_right) - 5)
            y_max = min(h - 1, max(y_left, y_right) + 5)
            print(f"  side: ребро slope={slope:.5f}, intercept={intercept:.1f}, "
                  f"точек={len(raw_pts)}/{int(np.sum(good))}, y={y_left:.0f}–{y_right:.0f}")
            return (0, int(y_min), w, int(y_max - y_min + 1),
                    float(slope), float(intercept))
        return None

    def detect_surface_row(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        blue_per_row = np.sum(mask > 0, axis=1)
        if np.max(blue_per_row) < 10:
            return None
        kernel = np.ones(11) / 11
        smooth = np.convolve(blue_per_row.astype(float), kernel, mode='same')
        return int(np.argmax(smooth))

    def pixel_to_table(self, px, py, bounds, frame_h, frame_w, camera='top', surface_row=None):
        if camera == 'top' and bounds is not None:
            bx, by, bw, bh = bounds
            rel_x = (px - bx) / bw
            rel_y = (py - by) / bh
            lx = (1 - rel_y) * COURT_W
            ly = (1 - rel_x) * COURT_H
            return lx, ly

        if camera == 'top':
            lx = (1 - py / frame_h) * COURT_W
            ly = (1 - px / frame_w) * COURT_H
        else:  # side camera
            if bounds is not None:
                if len(bounds) == 6:
                    bx, by, bw, bh, slope, intercept = bounds
                else:
                    bx, by, bw, bh = bounds
                    slope, intercept = 0, by + bh
                scale = COURT_W / bw if bw > 0 else 1.0
                lx = (px - bx) * scale
                surface_y = surface_row if surface_row is not None else (slope * px + intercept)
                pixels_above_table = surface_y - py
                ly = TABLE_H + pixels_above_table * scale - 4
            else:
                lx = (px / frame_w) * COURT_W
                ly = (1 - py / frame_h) * TABLE_H * 2
        return lx, ly
