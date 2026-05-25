from ultralytics import YOLO
import cv2
import numpy as np

COURT_W = 274.0
COURT_H = 152.5
TABLE_H = 76.0
NET_H = 15.25

class TennisBallDetector:
    def __init__(self, model_path="models/best.pt"):
        self.model = YOLO(model_path)

    def detect_video_frame(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([5, 80, 80]), np.array([20, 255, 255]))
        filtered = cv2.bitwise_and(frame, frame, mask=mask)

        results = self.model(filtered, conf=0.03, iou=0.3, augment=False, verbose=False, max_det=5)

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
        self.hsv_lower = np.array([95, 40, 40])
        self.hsv_upper = np.array([135, 255, 255])

    def detect_bounds(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        kernel = np.ones((7, 7), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        frame_area = frame.shape[0] * frame.shape[1]
        if area < frame_area * 0.03:
            return None
        return cv2.boundingRect(largest)

    def detect_surface_row(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        blue_per_row = np.sum(mask > 0, axis=1)
        if np.max(blue_per_row) < 10:
            return None
        kernel = np.ones(11) / 11
        smooth = np.convolve(blue_per_row.astype(float), kernel, mode='same')
        return int(np.argmax(smooth))

    def pixel_to_table(self, px, py, bounds, frame_h, frame_w, camera='top', M_calib=None):
        if M_calib is not None:
            pts = np.array([[[px, py]]], dtype=np.float32)
            transformed = cv2.perspectiveTransform(pts, M_calib)
            lx, ly = float(transformed[0, 0, 0]), float(transformed[0, 0, 1])
            if camera == 'side':
                return lx, ly
            return lx, ly

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
                bx, by, bw, bh = bounds
                scale = COURT_W / bw if bw > 0 else 1.0
                lx = (px - bx) * scale
                pixels_above_table = (by + bh - py)
                ly = TABLE_H + pixels_above_table * scale
            else:
                lx = (px / frame_w) * COURT_W
                ly = (1 - py / frame_h) * TABLE_H * 2
        return lx, ly
