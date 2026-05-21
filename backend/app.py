from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from backend.model import TennisBallDetector
from backend.tracker_2d import BallTracker2D
import io
import tempfile
import os
import cv2
import numpy as np

app = Flask(__name__)
CORS(app)

detector = TennisBallDetector()

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/api/detect/image', methods=['POST'])
def detect_image():
    try:
        file = request.files['image']
        image_bytes = file.read()

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        results = detector.model(img, conf=0.01, iou=0.1)
        result_img = results[0].plot()
        _, buffer = cv2.imencode('.jpg', result_img)

        return send_file(io.BytesIO(buffer.tobytes()), mimetype='image/jpeg')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/detect/stream', methods=['POST'])
def detect_stream():
    try:
        file = request.files['image']
        image_bytes = file.read()

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        results = detector.model(img, conf=0.01, iou=0.1)

        detections = []
        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()
            for box, conf in zip(boxes, confs):
                x1, y1, x2, y2 = [int(v) for v in box]
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": float(conf)
                })

        return jsonify({"success": True, "detections": detections, "count": len(detections)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/track/2d', methods=['POST'])
def track_2d():
    """Обработка видео с детекцией на КАЖДОМ кадре"""
    try:
        file = request.files['video']
        video_bytes = file.read()

        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_input.write(video_bytes)
        temp_input.close()

        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_output.close()

        cap = cv2.VideoCapture(temp_input.name)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output.name, fourcc, fps, (width, height))

        tracker = BallTracker2D()
        frame_num = 0
        total_detections = 0

        print(f"Обработка видео. Всего кадров: {int(cap.get(cv2.CAP_PROP_FRAME_COUNT))}")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_num += 1

            # Детекция на каждом кадре
            detections = detector.detect_video_frame(frame)

            if detections:
                total_detections += len(detections)
                if frame_num % 30 == 0:  # раз в секунду выводим статистику
                    print(f"Кадр {frame_num}: обнаружено {len(detections)} мячей (всего {total_detections})")

            # Обновляем трекер
            tracker.update(detections, height)

            # Рисуем зелёные рамки
            frame = tracker.draw_detections(frame, detections, (0, 255, 0), 2)

            # Рисуем жёлтую траекторию
            frame = tracker.draw_trajectory(frame, (0, 255, 255), 2)

            out.write(frame)

        cap.release()
        out.release()

        print(f"Обработка завершена. Всего кадров: {frame_num}, всего детекций: {total_detections}")

        with open(temp_output.name, 'rb') as f:
            video_result = f.read()

        os.unlink(temp_input.name)
        os.unlink(temp_output.name)

        return send_file(
            io.BytesIO(video_result),
            mimetype='video/mp4'
        )

    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)