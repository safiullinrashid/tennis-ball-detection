from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from model import TennisBallDetector, TableDetector, TABLE_H, COURT_W, COURT_H, NET_H
from tracker_2d import BallTracker2D
from tracker_3d import BallTracker3D
import io
import tempfile
import os
import uuid
import cv2
import numpy as np
import subprocess as sp
import base64
import concurrent.futures
from PIL import Image

try:
    import imageio
    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False

app = Flask(__name__)
CORS(app)

detector = TennisBallDetector()
table_detector = TableDetector()

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

        detections = detector.detect_video_frame(img)
        for d in detections:
            x1, y1, x2, y2 = d['bbox']
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cx, cy = [int(v) for v in d['center']]
            cv2.circle(img, (cx, cy), 4, (0, 0, 255), -1)
        _, buffer = cv2.imencode('.jpg', img)

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

def _draw_trajectory_png(points, output_path, bgr_color, is_side=False):
    """Рисует траекторию на фоне стола с автоподбором масштаба.
    points: список {frame, x, y} — координаты в см.
    Разрывы >5 кадров = новая линия.
    """
    if not points or len(points) < 2:
        img = np.zeros((400, 800, 3), dtype=np.uint8)
        cv2.imencode('.png', img)[1].tofile(output_path)
        return

    if is_side:
        xs = [p['x'] for p in points]
        ys = [p['y'] for p in points]
        min_x, max_x = min(min(xs), 0), max(max(xs), COURT_W)
        min_y = min(min(ys), 0)
        max_y = max(max(ys), TABLE_H * 2.0)
        rx, ry = max_x - min_x, max_y - min_y
        if rx < 1: rx = COURT_W
        if ry < 1: ry = TABLE_H * 2.0
        pad_ratio = 0.08
        min_x -= rx * pad_ratio
        max_x += rx * pad_ratio
        min_y -= ry * pad_ratio
        max_y += ry * pad_ratio
        img_w, img_h = 800, max(400, int(800 / (rx / ry)))
    else:
        xs = [p['x'] for p in points]
        ys = [p['y'] for p in points]
        min_x, max_x = min(min(xs), 0), max(max(xs), COURT_W)
        min_y = min(min(ys), 0)
        max_y = max(max(ys), COURT_H)
        rx, ry = max_x - min_x, max_y - min_y
        if rx < 1: rx = COURT_W
        if ry < 1: ry = COURT_H
        pad_ratio = 0.08
        min_x -= rx * pad_ratio
        max_x += rx * pad_ratio
        min_y -= ry * pad_ratio
        max_y += ry * pad_ratio
        img_w, img_h = 800, int(800 / (COURT_W / COURT_H))

    img = np.zeros((img_h, img_w, 3), dtype=np.uint8)
    pad = 40 if is_side else 20
    tx, ty = pad, pad
    tw, th = img_w - pad * 2, img_h - pad * 2

    # Рисуем стол
    def table_to_img(tx, ty, tw, th, val, min_v, max_v, horiz=True):
        if horiz:
            return int(tx + (val - min_v) / (max_v - min_v) * tw)
        return int(ty + th * (1 - (val - min_v) / (max_v - min_v)))

    t_left = table_to_img(tx, ty, tw, th, 0, min_x, max_x, True)
    t_right = table_to_img(tx, ty, tw, th, COURT_W, min_x, max_x, True)

    if is_side:
        # Тонкая линия стола (2 px)
        ts_y = table_to_img(tx, ty, tw, th, TABLE_H, min_y, max_y, False)
        cv2.line(img, (t_left, ts_y), (t_right, ts_y), (0, 180, 0), 2)
        cv2.line(img, (t_left, ts_y + 1), (t_right, ts_y + 1), (0, 100, 0), 1)
        net_x = table_to_img(tx, ty, tw, th, COURT_W * 0.5, min_x, max_x, True)
        net_top = table_to_img(tx, ty, tw, th, TABLE_H + NET_H, min_y, max_y, False)
        net_bot = table_to_img(tx, ty, tw, th, TABLE_H, min_y, max_y, False)
        cv2.line(img, (net_x, net_top), (net_x, net_bot), (100, 100, 100), 2)
        # Верхняя перекладина сетки — показывает, что сетка идёт в глубину (по ширине стола)
        net_left = table_to_img(tx, ty, tw, th, COURT_W * 0.5 - 40, min_x, max_x, True)
        net_right = table_to_img(tx, ty, tw, th, COURT_W * 0.5 + 40, min_x, max_x, True)
        cv2.line(img, (net_left, net_top), (net_right, net_top), (120, 120, 120), 1)
        # Пол
        fl_y = table_to_img(tx, ty, tw, th, 0, min_y, max_y, False)
        if ty < fl_y < ty + th:
            cv2.line(img, (t_left, fl_y), (t_right, fl_y), (40, 40, 40), 1)
    else:
        t_top = table_to_img(tx, ty, tw, th, 0, min_y, max_y, False)
        t_bottom = table_to_img(tx, ty, tw, th, COURT_H, min_y, max_y, False)
        if t_top > t_bottom:
            t_top, t_bottom = t_bottom, t_top
        cv2.rectangle(img, (t_left, t_top), (t_right, t_bottom), (0, 60, 0), -1)
        net_x = table_to_img(tx, ty, tw, th, COURT_W * 0.5, min_x, max_x, True)
        cv2.line(img, (net_x, t_top), (net_x, t_bottom), (100, 100, 100), 2)

    def norm_x(v): return max(0, min(img_w-1, table_to_img(tx, ty, tw, th, v, min_x, max_x, True)))
    def norm_y(v): return max(0, min(img_h-1, table_to_img(tx, ty, tw, th, v, min_y, max_y, False)))

    prev_frame = None
    gap_threshold = 5
    for i, p in enumerate(points):
        nx, ny = norm_x(p['x']), norm_y(p['y'])
        alpha = (i + 1) / len(points)
        cv2.circle(img, (nx, ny), 3, (
            int(bgr_color[0] * alpha), int(bgr_color[1] * alpha), int(bgr_color[2] * alpha)), -1)

        if prev_frame is not None and 'frame' in points[i - 1] and 'frame' in p:
            gap = p['frame'] - points[i - 1]['frame']
            if gap <= gap_threshold:
                px_, py_ = norm_x(points[i-1]['x']), norm_y(points[i-1]['y'])
                cv2.line(img, (px_, py_), (nx, ny),
                         (int(bgr_color[0] * 0.7), int(bgr_color[1] * 0.7), int(bgr_color[2] * 0.7)), 2)
        prev_frame = p.get('frame')

    cv2.circle(img, (norm_x(points[0]['x']), norm_y(points[0]['y'])), 5, (0, 255, 0), -1)
    cv2.circle(img, (norm_x(points[-1]['x']), norm_y(points[-1]['y'])), 5, (0, 0, 255), -1)

    cv2.imencode('.png', img)[1].tofile(output_path)

def _write_video(frames, output_path, fps, width, height):
    if not frames:
        return True
    # imageio (с FFmpeg, если установлен) — лучший вариант
    if HAS_IMAGEIO:
        try:
            writer = imageio.get_writer(output_path, fps=fps, codec='libx264')
            for f in frames:
                writer.append_data(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            writer.close()
            return True
        except Exception as e:
            print(f"imageio libx264 не сработал: {e}")
            try:
                # без указания codec — использует внутренний кодировщик imageio
                writer = imageio.get_writer(output_path, fps=fps)
                for f in frames:
                    writer.append_data(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
                writer.close()
                return True
            except Exception as e2:
                print(f"imageio fallback не сработал: {e2}")
    # OpenCV — последний шанс
    for codec in ['mp4v', 'avc1', 'X264', 'H264', 'MJPG']:
        try:
            writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*codec), fps, (width, height))
            if writer.isOpened():
                for f in frames:
                    writer.write(f)
                writer.release()
                return True
        except:
            pass
    return False

@app.route('/api/track/2d', methods=['POST'])
def track_2d():
    try:
        file = request.files['video']
        video_bytes = file.read()

        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_input.write(video_bytes)
        temp_input.close()

        cap = cv2.VideoCapture(temp_input.name)
        fps = max(1, int(cap.get(cv2.CAP_PROP_FPS)))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) // 2 * 2
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) // 2 * 2
        if width < 2: width = 640
        if height < 2: height = 480

        tracker = BallTracker2D(ignore_bottom=0)
        frame_num = 0
        total_detections = 0
        trajectory = []
        all_frames = []

        print(f"Обработка {total_frames} кадров, {width}x{height}")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))

            frame_num += 1
            detections = detector.detect_video_frame(frame)

            if detections:
                total_detections += len(detections)

            pt = tracker.update(detections, height)
            if pt is not None:
                trajectory.append({"frame": frame_num, "x": round(pt[0], 1), "y": round(pt[1], 1)})

            frame = tracker.draw_detections(frame, detections, (0, 255, 0), 2)
            frame = tracker.draw_trajectory(frame, (0, 255, 255), 2)
            all_frames.append(frame)

            if frame_num % 30 == 0:
                print(f"Кадр {frame_num}: {len(detections)} мячей (всего {total_detections})")

        cap.release()
        os.unlink(temp_input.name)

        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_output.close()
        ok = _write_video(all_frames, temp_output.name, fps, width, height)

        print(f"Готово: {frame_num} кадров, {total_detections} детекций, {len(trajectory)} точек траектории, видео: {'✓' if ok else '✗'}")

        if not ok:
            os.unlink(temp_output.name)
            # Возвращаем JSON с траекторией — фронтенд нарисует через canvas
            return jsonify({
                "success": True,
                "video_ok": False,
                "detections": total_detections,
                "trajectory": trajectory,
                "fps": fps,
                "frame_count": frame_num
            })

        response = send_file(
            temp_output.name,
            mimetype='video/mp4',
            as_attachment=True,
            download_name=f'tracked_2d_{file.filename}'
        )

        @response.call_on_close
        def cleanup():
            try:
                os.unlink(temp_output.name)
            except:
                pass

        return response

    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({"error": str(e)}), 500

TRACKED_VIDEO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tracked_output')
os.makedirs(TRACKED_VIDEO_DIR, exist_ok=True)

calibration_temp = {}

@app.route('/api/calibrate/get_frame', methods=['POST'])
def calibrate_get_frame():
    try:
        camera = request.form.get('camera')
        video_file = request.files['video']
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_video.write(video_file.read())
        temp_video.close()
        cap = cv2.VideoCapture(temp_video.name)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return jsonify({"error": "Не могу прочитать видео"}), 500
        frame_name = f'calib_{camera}_{uuid.uuid4().hex}.jpg'
        frame_path = os.path.join(TRACKED_VIDEO_DIR, frame_name)
        cv2.imwrite(frame_path, frame)
        calibration_temp[camera] = {'video_path': temp_video.name, 'frame_path': frame_path}
        return jsonify({"success": True, "image_url": f'/api/track/video/{frame_name}'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/calibrate/save_corners', methods=['POST'])
def calibrate_save_corners():
    try:
        data = request.json
        camera = data.get('camera')
        if camera in calibration_temp:
            for f in ['video_path', 'frame_path']:
                if os.path.exists(calibration_temp[camera][f]):
                    os.unlink(calibration_temp[camera][f])
            del calibration_temp[camera]
        return jsonify({"success": True, "message": f"Калибровка {camera} сохранена"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/track/video/<filename>')
def serve_tracked_video(filename):
    filepath = os.path.join(TRACKED_VIDEO_DIR, filename)
    if not os.path.exists(filepath):
        print(f"404: {filepath} не найден (папка: {TRACKED_VIDEO_DIR})")
        # список файлов в папке для диагностики
        files = os.listdir(TRACKED_VIDEO_DIR) if os.path.isdir(TRACKED_VIDEO_DIR) else []
        print(f"  Файлы в папке: {files}")
    return send_from_directory(TRACKED_VIDEO_DIR, filename)

@app.route('/api/track/3d', methods=['POST'])
def track_3d():
    try:
        file_top = request.files['video_top']
        file_side = request.files['video_side']
        render_video = request.form.get('render_video', '0') == '1'

        vid_id = uuid.uuid4().hex

        temp_top = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_top.write(file_top.read())
        temp_top.close()

        temp_side = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_side.write(file_side.read())
        temp_side.close()

        # Параметры верхней камеры
        cap = cv2.VideoCapture(temp_top.name)
        top_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) // 2 * 2
        top_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) // 2 * 2
        top_fps = max(1, int(cap.get(cv2.CAP_PROP_FPS)))
        top_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        # Параметры боковой камеры
        cap = cv2.VideoCapture(temp_side.name)
        side_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) // 2 * 2
        side_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) // 2 * 2
        side_fps = max(1, int(cap.get(cv2.CAP_PROP_FPS)))
        side_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        def process_camera(path, out_path, w, h, fps, label, max_miss=0, render=True):
            cap_ = cv2.VideoCapture(path)
            local_detector = TennisBallDetector()  # отдельный экземпляр для каждого потока
            tracker_ = BallTracker2D(ignore_bottom=0)
            dets_ = {}
            all_frames = []
            n = 0
            table_bounds = None
            surface_row = None
            total = int(cap_.get(cv2.CAP_PROP_FRAME_COUNT))
            miss = 0
            had_any = False
            print(f"Обработка {label}: {total} кадров, {w}x{h}, fps={fps}")
            while True:
                ret, frame = cap_.read()
                if not ret:
                    break
                if frame.shape[1] != w or frame.shape[0] != h:
                    frame = cv2.resize(frame, (w, h))
                n += 1
                if n == 1:
                    cam_type = 'side' if label == 'боковая' else 'top'
                    table_bounds = table_detector.detect_bounds(frame, camera=cam_type)
                    if table_bounds:
                        print(f"  {label}: bounds стола {table_bounds} (frame={w}x{h})")
                        vis = frame.copy()
                        bx, by = table_bounds[0], table_bounds[1]
                        bw_, bh_ = table_bounds[2], table_bounds[3]
                        cv2.rectangle(vis, (int(bx), int(by)), (int(bx + bw_), int(by + bh_)), (0, 255, 0), 4)
                        cv2.putText(vis, f"table ({cam_type})", (bx, max(30, by - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                        vis_path = os.path.join(TRACKED_VIDEO_DIR, f'{vid_id}_{label}_table.png')
                        cv2.imwrite(vis_path, vis)
                        print(f"  {label}: сохранена визуализация стола → {vis_path}")
                    else:
                        print(f"  {label}: стол не найден, используется весь кадр")
                    if label == 'боковая':
                        surface_row = table_detector.detect_surface_row(frame)
                        if surface_row is not None:
                            print(f"  {label}: поверхность стола на строке {surface_row}")
                            vis = frame.copy()
                            cv2.line(vis, (0, surface_row), (w, surface_row), (0, 255, 255), 3)
                            cv2.putText(vis, f"surface row {surface_row}", (20, max(30, surface_row - 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                            srf_path = os.path.join(TRACKED_VIDEO_DIR, f'table_{vid_id}_side_surface.png')
                            cv2.imwrite(srf_path, vis)
                        else:
                            print(f"  {label}: поверхность стола не найдена")
                d = local_detector.detect_video_frame(frame)
                tracker_.update(d, h)
                if d:
                    dets_[n] = d[0]['center']
                    miss = 0
                    had_any = True
                else:
                    miss += 1
                if render:
                    frame = tracker_.draw_detections(frame, d, (0, 255, 0), 2)
                    frame = tracker_.draw_trajectory(frame, (0, 255, 255), 2)
                    all_frames.append(frame)
                if max_miss and had_any and miss > max_miss and n > total * 0.2:
                    print(f"  {label}: мяч потерян на {miss} кадров, прерываем (кадр {n}/{total})")
                    break
                if n % 60 == 0:
                    print(f"  {label}: кадр {n}")
            cap_.release()
            ok = True
            if render:
                ok = _write_video(all_frames, out_path, fps, w, h)
            print(f"  {label}: {len(dets_)} детекций, видео {'✓' if ok else '✗'}")
            for i, (fn, (dx, dy)) in enumerate(sorted(dets_.items())[:3]):
                print(f"  {label} детекция #{i+1}: кадр {fn} → px=({dx:.0f}, {dy:.0f})")
            return dets_, table_bounds, surface_row

        top_out = os.path.join(TRACKED_VIDEO_DIR, f'{vid_id}_top.mp4')
        side_out = os.path.join(TRACKED_VIDEO_DIR, f'{vid_id}_side.mp4')

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_top = executor.submit(process_camera, temp_top.name, top_out, top_w, top_h, top_fps, 'верхняя', 300, render_video)
            fut_side = executor.submit(process_camera, temp_side.name, side_out, side_w, side_h, side_fps, 'боковая', 300, render_video)
            top_dets, top_table, top_surface = fut_top.result()
            side_dets, side_table, side_surface = fut_side.result()

        top_video_ok = os.path.exists(top_out) and os.path.getsize(top_out) > 0
        side_video_ok = os.path.exists(side_out) and os.path.getsize(side_out) > 0

        # Визуализация стола на первом кадре (до удаления temp)
        top_table_vis = os.path.join(TRACKED_VIDEO_DIR, f'table_{vid_id}_top.png')
        side_table_vis = os.path.join(TRACKED_VIDEO_DIR, f'table_{vid_id}_side.png')
        side_surface_vis = os.path.join(TRACKED_VIDEO_DIR, f'table_{vid_id}_side_surface.png')
        for cap_path, out_path, bounds, surf_row, label in [
            (temp_top.name, top_table_vis, top_table, None, 'top'),
            (temp_side.name, side_table_vis, side_table, side_surface, 'side'),
        ]:
            if bounds is not None and os.path.exists(cap_path):
                cap_v = cv2.VideoCapture(cap_path)
                ret, fr = cap_v.read()
                cap_v.release()
                if ret:
                    if len(bounds) == 6:
                        bx, by, bw_, bh_, slope, intercept = bounds
                    else:
                        bx, by, bw_, bh_ = bounds
                        slope, intercept = 0, by + bh_
                    cv2.rectangle(fr, (int(bx), int(by)), (int(bx + bw_), int(by + bh_)), (0, 255, 0), 2)
                    if abs(slope) > 0.001:
                        x_left, x_right = 0, fr.shape[1] - 1
                        y_left = int(slope * x_left + intercept)
                        y_right = int(slope * x_right + intercept)
                        cv2.line(fr, (x_left, y_left), (x_right, y_right), (0, 255, 0), 4)
                    else:
                        cv2.line(fr, (int(bx), int(by + bh_ // 2)), (int(bx + bw_), int(by + bh_ // 2)), (0, 255, 0), 4)
                    cv2.putText(fr, f"table {label}", (int(bx), max(30, int(by) - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    if surf_row is not None:
                        cv2.line(fr, (0, int(surf_row)), (fr.shape[1], int(surf_row)), (0, 255, 255), 3)
                        cv2.putText(fr, f"surface row {surf_row}", (20, max(30, int(surf_row) - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                    cv2.imwrite(out_path, fr)
                    print(f"  Визуализация стола сохранена: {out_path}")

        os.unlink(temp_top.name)
        os.unlink(temp_side.name)

        print(f"  ВЕРХ: {top_total} кадров, {top_fps} FPS")
        print(f"  БОК:  {side_total} кадров, {side_fps} FPS")
        print(f"  Размеры кадров: верх {top_w}x{top_h}, бок {side_w}x{side_h}")
        print(f"  Всего детекций: верх {len(top_dets)}, бок {len(side_dets)}")

        print("Сборка 3D траектории...")
        tracker3d = BallTracker3D()
        # Поиск совпадений с учётом разницы FPS
        fps_ratio = side_fps / top_fps if top_fps > 0 else 1.0
        side_keys = sorted(side_dets.keys())
        used_side = set()
        matched_pairs = []
        tolerance = 10
        for tf in sorted(top_dets.keys()):
            best = None
            best_dist = 999
            expected_sf = int(round(tf * fps_ratio))
            # Ищем в окрестности ожидаемого кадра
            for sf in side_keys:
                if sf in used_side:
                    continue
                d = abs(sf - expected_sf)
                if d < best_dist:
                    best_dist = d
                    best = sf
            if best is not None and best_dist <= tolerance:
                matched_pairs.append((tf, best))
                used_side.add(best)

        top_2d = []
        side_2d = []
        for tf, sf in matched_pairs:
            avg_frame = (tf + sf) // 2
            tracker3d.update(
                [{'center': top_dets[tf], 'confidence': 0.5}],
                [{'center': side_dets[sf], 'confidence': 0.5}],
                (top_h, top_w), (side_h, side_w),
                table_top=top_table, table_side=side_table,
                surface_row_side=side_surface
            )
            top_2d.append({"frame": avg_frame, "x": round(top_dets[tf][0], 1), "y": round(top_dets[tf][1], 1)})
            side_2d.append({"frame": avg_frame, "x": round(side_dets[sf][0], 1), "y": round(side_dets[sf][1], 1)})

        trajectory = tracker3d.get_trajectory_3d()
        print(f"3D готово. Точек: {len(trajectory)} (совпадений: {len(matched_pairs)})")
        if trajectory:
            xs = [p['X'] for p in trajectory]
            ys = [p['Y'] for p in trajectory]
            zs = [p['Z'] for p in trajectory]
            print(f"  3D X: {min(xs):.0f}–{max(xs):.0f} см (0–274)")
            print(f"  3D Y: {min(ys):.0f}–{max(ys):.0f} см (0–152.5)")
            print(f"  3D Z: {min(zs):.0f}–{max(zs):.0f} см (0–106.5)")
            # Первые 3 точки
            for i, p in enumerate(trajectory[:3]):
                print(f"  3D точка #{i+1}: кадр {p['frame']} → X={p['X']} Y={p['Y']} Z={p['Z']}")
            # Одна точка в середине
            mid = trajectory[len(trajectory)//2]
            print(f"  3D точка (середина): кадр {mid['frame']} → X={mid['X']} Y={mid['Y']} Z={mid['Z']}")

        # Конвертируем пиксельные координаты → координаты стола (см) для PNG
        def to_table_pts(pts, bounds, fw, fh, camera, surface_row=None):
            result = []
            for p in pts:
                lx, ly = table_detector.pixel_to_table(
                    p['x'], p['y'], bounds, fh, fw, camera, surface_row=surface_row)
                result.append({"frame": p['frame'], "x": round(lx, 1), "y": round(ly, 1)})
            return result

        def smooth_pts(pts, window=1):
            n = len(pts)
            if n < window * 2 + 1:
                return pts
            kernel = np.ones(window) / window
            xs = np.array([p['x'] for p in pts])
            ys = np.array([p['y'] for p in pts])
            pad_x = np.concatenate([[xs[0]] * (window // 2), xs, [xs[-1]] * (window // 2)])
            pad_y = np.concatenate([[ys[0]] * (window // 2), ys, [ys[-1]] * (window // 2)])
            sx = np.convolve(pad_x, kernel, mode='valid')
            sy = np.convolve(pad_y, kernel, mode='valid')
            sx[0], sx[-1] = xs[0], xs[-1]
            sy[0], sy[-1] = ys[0], ys[-1]
            return [{"frame": p['frame'], "x": round(sx[i], 1), "y": round(sy[i], 1)} for i, p in enumerate(pts)]

        top_table_coords = smooth_pts(to_table_pts(top_2d, top_table, top_w, top_h, 'top'))
        side_table_coords = smooth_pts(to_table_pts(side_2d, side_table, side_w, side_h, 'side', surface_row=side_surface))
        if top_table_coords:
            tx_s = [p['x'] for p in top_table_coords]
            ty_s = [p['y'] for p in top_table_coords]
            print(f"  PNG верх: X={min(tx_s):.0f}–{max(tx_s):.0f} Y={min(ty_s):.0f}–{max(ty_s):.0f} ({len(top_table_coords)} точек)")
        if side_table_coords:
            sx_s = [p['x'] for p in side_table_coords]
            sy_s = [p['y'] for p in side_table_coords]
            print(f"  PNG бок: X={min(sx_s):.0f}–{max(sx_s):.0f} Y={min(sy_s):.0f}–{max(sy_s):.0f} ({len(side_table_coords)} точек)")

        # Генерируем изображения траекторий на фоне стола
        top_png = os.path.join(TRACKED_VIDEO_DIR, f'{vid_id}_top_traj.png')
        side_png = os.path.join(TRACKED_VIDEO_DIR, f'{vid_id}_side_traj.png')
        _draw_trajectory_png(top_table_coords, top_png, (255, 212, 0), is_side=False)
        _draw_trajectory_png(side_table_coords, side_png, (0, 136, 255), is_side=True)

        return jsonify({
            "success": True,
            "points_3d": len(trajectory),
            "trajectory": trajectory,
            "top_2d": top_2d,
            "side_2d": side_2d,
            "fps": top_fps,
            "frame_count_top": top_total,
            "frame_count_side": side_total,
            "video_ok": top_video_ok and side_video_ok,
            "top_video_url": f'/api/track/video/{vid_id}_top.mp4' if top_video_ok else None,
            "side_video_url": f'/api/track/video/{vid_id}_side.mp4' if side_video_ok else None,
            "top_traj_url": f'/api/track/video/{vid_id}_top_traj.png',
            "side_traj_url": f'/api/track/video/{vid_id}_side_traj.png',
            "top_table_vis_url": f'/api/track/video/table_{vid_id}_top.png' if os.path.exists(top_table_vis) else None,
            "side_table_vis_url": f'/api/track/video/table_{vid_id}_side.png' if os.path.exists(side_table_vis) else None,
            "side_surface_vis_url": f'/api/track/video/table_{vid_id}_side_surface.png' if os.path.exists(side_surface_vis) else None,
        })
    except Exception as e:
        print(f"Ошибка 3D: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)