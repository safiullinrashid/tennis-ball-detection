from ultralytics import YOLO
import cv2
import numpy as np

class TennisBallDetector:
    def __init__(self, model_path="models/best.pt"):
        self.model = YOLO(model_path)

    def detect_video_frame(self, frame):
        """
        Детекция мяча с усилением для разных направлений
        """
        h, w = frame.shape[:2]

        # 1. Повышаем контрастность
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        # 2. Цветовой фильтр (оранжевый диапазон)
        hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)
        lower_orange = np.array([5, 80, 80])
        upper_orange = np.array([20, 255, 255])
        mask = cv2.inRange(hsv, lower_orange, upper_orange)

        # 3. Применяем маску
        filtered = cv2.bitwise_and(enhanced, enhanced, mask=mask)

        # 4. Детекция на оригинале + на фильтрованном
        results_orig = self.model(
            frame,
            conf=0.05,
            iou=0.3,
            augment=True,      # важно для разных ракурсов
            verbose=False,
            max_det=1
        )

        results_filtered = self.model(
            filtered,
            conf=0.03,          # ещё ниже для фильтрованного
            iou=0.3,
            augment=True,
            verbose=False,
            max_det=1          # <-- ИЗМЕНЕНО: было 3, стало 1
        )

        # Объединяем детекции
        all_detections = []

        # Добавляем детекции из оригинального кадра
        if len(results_orig[0].boxes) > 0:
            boxes = results_orig[0].boxes.xyxy.cpu().numpy()
            confs = results_orig[0].boxes.conf.cpu().numpy()
            for box, conf in zip(boxes, confs):
                x1, y1, x2, y2 = [int(v) for v in box]
                box_w = x2 - x1      # <-- ДОБАВЛЕНО
                box_h = y2 - y1      # <-- ДОБАВЛЕНО
                
                # <-- ДОБАВЛЕНО: фильтр по размеру
                if box_w < 10 or box_w > 60:
                    continue
                if box_h < 10 or box_h > 60:
                    continue
                # <-- КОНЕЦ ФИЛЬТРА
                
                if (x2 - x1) > 8 and (y2 - y1) > 8:  # отсекаем шум
                    all_detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "center": [(x1 + x2) / 2, (y1 + y2) / 2],
                        "confidence": float(conf),
                        "source": "original"
                    })

        # Добавляем детекции из фильтрованного кадра
        if len(results_filtered[0].boxes) > 0:
            boxes = results_filtered[0].boxes.xyxy.cpu().numpy()
            confs = results_filtered[0].boxes.conf.cpu().numpy()
            for box, conf in zip(boxes, confs):
                x1, y1, x2, y2 = [int(v) for v in box]
                box_w = x2 - x1      # <-- ДОБАВЛЕНО
                box_h = y2 - y1      # <-- ДОБАВЛЕНО
                
                # <-- ДОБАВЛЕНО: фильтр по размеру
                if box_w < 5 or box_w > 15:
                    continue
                if box_h < 5 or box_h > 15:
                    continue
                # <-- КОНЕЦ ФИЛЬТРА
                
                if (x2 - x1) > 8 and (y2 - y1) > 8:
                    all_detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "center": [(x1 + x2) / 2, (y1 + y2) / 2],
                        "confidence": float(conf) + 0.05,  # бонус к уверенности
                        "source": "filtered"
                    })

        # Удаляем дубликаты (по IoU)
        unique_detections = []
        for d in all_detections:
            is_duplicate = False
            x1, y1, x2, y2 = d['bbox']
            for u in unique_detections:
                ux1, uy1, ux2, uy2 = u['bbox']
                # Проверяем перекрытие
                if abs(x1 - ux1) < 20 and abs(y1 - uy1) < 20:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_detections.append(d)

        # Сортируем по уверенности
        unique_detections.sort(key=lambda d: d['confidence'], reverse=True)

        return unique_detections[:1]  # <-- ИЗМЕНЕНО: было 3, стало 1 (максимум 1 мяч)