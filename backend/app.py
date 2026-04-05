from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
from backend.model import TennisBallDetector
from backend.tracker_2d import BallTracker2D
from backend.tracker_3d import BallTracker3D
from backend.court_calibration import CourtCalibration
import os
import io
import cv2
import numpy as np
import json

app = Flask(__name__)
CORS(app)

# Инициализация
detector = TennisBallDetector()
calibration = CourtCalibration()

# Временные трекеры для текущей сессии
current_tracker_2d = None
current_tracker_3d = None
current_video_fps = 0

# Папки
os.makedirs('backend/uploads', exist_ok=True)
os.makedirs('backend/trajectories', exist_ok=True)

# ============ БАЗОВЫЕ МАРШРУТЫ ============

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/api/detect/image', methods=['POST'])
def detect_image():
    """Детекция на одном изображении"""
    try:
        file = request.files['image']
        image_bytes = file.read()

        detections, result_image = detector.detect_image(image_bytes)

        return send_file(
            io.BytesIO(result_image),
            mimetype='image/jpeg',
            as_attachment=False
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============ 2D ТРЕКИНГ ДЛЯ ВИДЕО ============

@app.route('/api/track/2d', methods=['POST'])
def track_2d():
    """Обработка видео с одной камеры + 2D траектория"""
    global current_tracker_2d

    try:
        file = request.files['video']
        video_bytes = file.read()

        # Сохраняем временное видео
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_input.write(video_bytes)
        temp_input.close()

        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_output.close()

        # Открываем видео
        cap = cv2.VideoCapture(temp_input.name)
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output.name, fourcc, fps, (width, height))

        # Создаем трекер
        tracker = BallTracker2D(max_jump_px=150)
        trajectories = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Детекция
            detections = detector.detect_video_frame(frame, return_annotated=False)

            # Обновление трекера
            point = tracker.update(detections, frame.shape)

            # Рисуем траекторию
            frame = tracker.draw_trajectory(frame)

            # Рисуем текущую детекцию
            for d in detections:
                x1, y1, x2, y2 = d['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Сохраняем точку в траекторию
            if point:
                trajectories.append({
                    "frame": tracker.frame_count,
                    "x": point[0],
                    "y": point[1]
                })

            out.write(frame)

        cap.release()
        out.release()

        # Сохраняем траекторию в JSON
        traj_file = f"backend/trajectories/trajectory_2d_{int(time.time())}.json"
        with open(traj_file, 'w') as f:
            json.dump(trajectories, f)

        # Отправляем результат
        with open(temp_output.name, 'rb') as f:
            video_result = f.read()

        os.unlink(temp_input.name)
        os.unlink(temp_output.name)

        return send_file(
            io.BytesIO(video_result),
            mimetype='video/mp4',
            as_attachment=False,
            download_name='tracked_2d.mp4'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============ 3D ТРЕКИНГ ДЛЯ ДВУХ ВИДЕО ============

@app.route('/api/track/3d', methods=['POST'])
def track_3d():
    """Обработка двух видео (сбоку и сверху) + 3D траектория"""
    global current_tracker_3d

    try:
        video_top = request.files['video_top']
        video_side = request.files['video_side']

        # Калибровка (можно передать параметры через запрос)
        calibration_data = request.form.get('calibration', '{}')
        calibration_params = json.loads(calibration_data)

        # Сохраняем видео
        temp_top = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_top.write(video_top.read())
        temp_top.close()

        temp_side = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_side.write(video_side.read())
        temp_side.close()

        # Открываем оба видео
        cap_top = cv2.VideoCapture(temp_top.name)
        cap_side = cv2.VideoCapture(temp_side.name)

        fps_top = int(cap_top.get(cv2.CAP_PROP_FPS))
        fps_side = int(cap_side.get(cv2.CAP_PROP_FPS))

        # Создаем выходные видео
        temp_output_top = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_output_side = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')

        out_top = cv2.VideoWriter(temp_output_top.name, cv2.VideoWriter_fourcc(*'mp4v'), fps_top,
                                   (int(cap_top.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap_top.get(cv2.CAP_PROP_FRAME_HEIGHT))))
        out_side = cv2.VideoWriter(temp_output_side.name, cv2.VideoWriter_fourcc(*'mp4v'), fps_side,
                                    (int(cap_side.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap_side.get(cv2.CAP_PROP_FRAME_HEIGHT))))

        # Калибруем камеры (если переданы параметры)
        if 'corners_top' in calibration_params:
            calibration.calibrate_top_camera(None, calibration_params['corners_top'])
        if 'side_params' in calibration_params:
            calibration.calibrate_side_camera(None, **calibration_params['side_params'])

        # Создаем 3D трекер
        tracker_3d = BallTracker3D()

        frame_count = 0
        trajectories_3d = []

        while True:
            ret_top, frame_top = cap_top.read()
            ret_side, frame_side = cap_side.read()

            if not ret_top or not ret_side:
                break

            # Детекция на обоих кадрах
            detections_top = detector.detect_video_frame(frame_top, return_annotated=False)
            detections_side = detector.detect_video_frame(frame_side, return_annotated=False)

            # Обновление 3D трекера
            point_3d = tracker_3d.update(detections_top, detections_side, frame_top.shape, frame_side.shape)

            if point_3d:
                trajectories_3d.append(point_3d)

            # Рисуем детекции и проекции траектории
            for d in detections_top:
                x1, y1, x2, y2 = d['bbox']
                cv2.rectangle(frame_top, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Рисуем 2D проекцию 3D траектории на вид сверху
            proj_top = tracker_3d.get_trajectory_2d_projection('top')
            for i in range(1, len(proj_top)):
                # Преобразуем реальные координаты в пиксели
                # (нужна обратная трансформация)
                pass

            for d in detections_side:
                x1, y1, x2, y2 = d['bbox']
                cv2.rectangle(frame_side, (x1, y1), (x2, y2), (0, 255, 0), 2)

            out_top.write(frame_top)
            out_side.write(frame_side)
            frame_count += 1

        cap_top.release()
        cap_side.release()
        out_top.release()
        out_side.release()

        # Сохраняем 3D траекторию
        traj_file = tracker_3d.export_trajectory(f"backend/trajectories/trajectory_3d_{int(time.time())}.json")

        # Удаляем временные файлы
        os.unlink(temp_top.name)
        os.unlink(temp_side.name)

        # Отправляем результат (можно оба видео или zip)
        return jsonify({
            "success": True,
            "trajectory_file": traj_file,
            "points_3d": len(trajectories_3d),
            "message": "3D трекинг завершен"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============ КАЛИБРОВКА ============

@app.route('/api/calibrate/top', methods=['POST'])
def calibrate_top():
    """Калибровка камеры сверху по 4 углам стола"""
    try:
        data = request.json
        corners = data.get('corners')

        if not corners or len(corners) != 4:
            return jsonify({"error": "Нужно 4 угла стола"}), 400

        calibration.calibrate_top_camera(None, corners)
        return jsonify({"success": True, "message": "Калибровка выполнена"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/calibrate/side', methods=['POST'])
def calibrate_side():
    """Калибровка боковой камеры"""
    try:
        data = request.json
        calibration.calibrate_side_camera(
            None,
            data.get('left_x'),
            data.get('right_x'),
            data.get('table_y'),
            data.get('floor_y')
        )
        return jsonify({"success": True, "message": "Калибровка выполнена"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    import tempfile
    import time
    app.run(debug=True, host='0.0.0.0', port=5000)