from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from backend.model import TennisBallDetector
import os
import io
import cv2
import numpy as np

app = Flask(__name__)
CORS(app)

# Создаем папку для загрузок
os.makedirs('backend/uploads', exist_ok=True)

# Инициализируем детектор
detector = TennisBallDetector()

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/api/detect/image', methods=['POST'])
def detect_image():
    """Обработка изображения"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No image selected"}), 400

        # Читаем изображение
        image_bytes = file.read()

        # Детекция
        detections, result_image = detector.detect_image(image_bytes)

        # Возвращаем результат
        return send_file(
            io.BytesIO(result_image),
            mimetype='image/jpeg',
            as_attachment=False,
            download_name='result.jpg'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/detect/video', methods=['POST'])
def detect_video():
    """Обработка видео"""
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video uploaded"}), 400

        file = request.files['video']
        if file.filename == '':
            return jsonify({"error": "No video selected"}), 400

        # Читаем видео
        video_bytes = file.read()

        # Детекция
        result_video = detector.detect_video(video_bytes)

        if result_video:
            return send_file(
                io.BytesIO(result_video),
                mimetype='video/mp4',
                as_attachment=False,
                download_name='result.mp4'
            )
        else:
            return jsonify({"error": "Video processing failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/detect/stream', methods=['POST'])
def detect_stream():
    """Обработка с информацией о детекции (для статистики)"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        file = request.files['image']
        image_bytes = file.read()

        # Получаем детекции
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        results = detector.model(
            img,
            conf=0.1,
            iou=0.5,
            imgsz=1024
        )

        detections = []
        if len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()

            for box, conf in zip(boxes, confs):
                detections.append({
                    "x": float(box[0]),
                    "y": float(box[1]),
                    "width": float(box[2] - box[0]),
                    "height": float(box[3] - box[1]),
                    "confidence": float(conf)
                })

        return jsonify({
            "success": True,
            "detections": detections,
            "count": len(detections)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)