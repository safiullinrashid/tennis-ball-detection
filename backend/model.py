from ultralytics import YOLO
import cv2
import numpy as np
import tempfile
import os

class TennisBallDetector:
    def __init__(self, model_path="models/best.pt"):
        self.model = YOLO(model_path)

    def detect_image(self, image_bytes):
        """Детекция на изображении"""

        # Декодируем изображение
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 🔥 УЛУЧШЕНИЕ 1: увеличиваем разрешение
        img_resized = cv2.resize(img, (1024, 1024))

        # 🔥 УЛУЧШЕНИЕ 2: снижаем confidence
        results = self.model(
            img_resized,
            conf=0.1,      # было 0.25
            iou=0.5,
            imgsz=1024
        )

        detections = []

        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()

            for box, conf in zip(boxes, confs):

                # 🔥 УЛУЧШЕНИЕ 3: фильтр по размеру (убираем шум)
                x1, y1, x2, y2 = box
                w = x2 - x1
                h = y2 - y1

                if w < 5 or h < 5:
                    continue

                detections.append({
                    "bbox": box.tolist(),
                    "confidence": float(conf)
                })

        # Рисуем результат
        result_img = results[0].plot()

        _, buffer = cv2.imencode('.jpg', result_img)
        result_bytes = buffer.tobytes()

        return detections, result_bytes

    def detect_video(self, video_bytes):
        """Детекция на видео"""

        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_input.write(video_bytes)
        temp_input.close()

        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_output.close()

        # 🔥 улучшенные параметры
        results = self.model(
            temp_input.name,
            conf=0.1,
            iou=0.5,
            imgsz=1024,
            save=True,
            project='temp',
            name='video_output'
        )

        processed_video = 'temp/video_output/result.mp4'

        if os.path.exists(processed_video):
            with open(processed_video, 'rb') as f:
                video_result = f.read()

            os.unlink(temp_input.name)

            import shutil
            shutil.rmtree('temp', ignore_errors=True)

            return video_result

        return None