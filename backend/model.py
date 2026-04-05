from ultralytics import YOLO
import cv2
import numpy as np
import tempfile
import os

class TennisBallDetector:
    def __init__(self, model_path="models/best.pt"):
        self.model = YOLO(model_path)

    def detect_image(self, image_bytes, return_annotated=True):
        """
        Детекция на изображении
        return_annotated: вернуть аннотированное изображение или только координаты
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        h, w = img.shape[:2]

        # Для маленьких мячей - увеличиваем
        scale = 1.5 if min(h, w) < 640 else 1.0
        if scale > 1.0:
            img_scaled = cv2.resize(img, (int(w*scale), int(h*scale)))
        else:
            img_scaled = img

        # Обесцвечивание (убираем зависимость от цвета)
        gray_img = cv2.cvtColor(img_scaled, cv2.COLOR_BGR2GRAY)
        gray_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)

        # Детекция
        results = self.model(
            gray_img,
            conf=0.05,
            iou=0.3,
            augment=True,
            imgsz=1280,
            verbose=False
        )

        # Собираем детекции
        detections = []
        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()

            # Коэффициенты масштабирования обратно
            scale_x = w / img_scaled.shape[1]
            scale_y = h / img_scaled.shape[0]

            for box, conf in zip(boxes, confs):
                x1 = int(box[0] * scale_x)
                y1 = int(box[1] * scale_y)
                x2 = int(box[2] * scale_x)
                y2 = int(box[3] * scale_y)

                if (x2 - x1) < 3 or (y2 - y1) < 3:
                    continue

                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "center": [(x1 + x2) / 2, (y1 + y2) / 2],
                    "width": x2 - x1,
                    "height": y2 - y1,
                    "confidence": float(conf)
                })

        # Аннотируем если нужно
        if return_annotated:
            result_img = img.copy()
            for d in detections:
                x1, y1, x2, y2 = d["bbox"]
                conf = d["confidence"]
                cv2.rectangle(result_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(result_img, f"ball {conf:.2f}", (x1, y1-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            _, buffer = cv2.imencode('.jpg', result_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            result_bytes = buffer.tobytes()
            return detections, result_bytes

        return detections

    def detect_video_frame(self, frame, return_annotated=True):
        """Детекция на одном кадре видео (для покадровой обработки)"""
        h, w = frame.shape[:2]

        scale = 1.5 if min(h, w) < 640 else 1.0
        if scale > 1.0:
            frame_scaled = cv2.resize(frame, (int(w*scale), int(h*scale)))
        else:
            frame_scaled = frame

        gray_frame = cv2.cvtColor(frame_scaled, cv2.COLOR_BGR2GRAY)
        gray_frame = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR)

        results = self.model(gray_frame, conf=0.05, iou=0.3, augment=True, imgsz=1280, verbose=False)

        detections = []
        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()

            scale_x = w / frame_scaled.shape[1]
            scale_y = h / frame_scaled.shape[0]

            for box, conf in zip(boxes, confs):
                x1 = int(box[0] * scale_x)
                y1 = int(box[1] * scale_y)
                x2 = int(box[2] * scale_x)
                y2 = int(box[3] * scale_y)

                if (x2 - x1) < 3 or (y2 - y1) < 3:
                    continue

                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "center": [(x1 + x2) / 2, (y1 + y2) / 2],
                    "confidence": float(conf)
                })

        if return_annotated:
            result_frame = frame.copy()
            for d in detections:
                x1, y1, x2, y2 = d["bbox"]
                cv2.rectangle(result_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            return detections, result_frame

        return detections