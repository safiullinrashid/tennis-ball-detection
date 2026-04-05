import numpy as np
from collections import deque
from .court_calibration import CourtCalibration

class BallTracker3D:
    """
    3D трекер для двух камер (сбоку и сверху)
    """
    def __init__(self, max_history=300):
        self.trajectory_3d = []        # (X, Y, Z, frame)
        self.history_2d_top = deque(maxlen=5)   # последние точки с верхней камеры
        self.history_2d_side = deque(maxlen=5)  # последние точки с боковой камеры
        self.frame_count = 0
        self.calibration = CourtCalibration()

    def update(self, detections_top, detections_side, frame_shape_top, frame_shape_side):
        """
        Обновляет 3D траекторию на основе детекций с двух камер
        """
        self.frame_count += 1

        # Получаем 2D координаты из каждой камеры
        point_top = self._get_best_point(detections_top)
        point_side = self._get_best_point(detections_side)

        if point_top is None or point_side is None:
            # Не хватает данных для 3D
            return None

        x_top, y_top = point_top
        x_side, y_side = point_side

        # Преобразуем в реальные координаты
        try:
            # Из камеры сверху: X, Y на столе
            x_cm, y_cm = self.calibration.pixel_to_cm_top(x_top, y_top)

            # Из боковой камеры: X, Z
            x_side_cm, z_cm = self.calibration.pixel_to_cm_side(x_side, y_side)

            # Усредняем X из двух камер
            x_final = (x_cm + x_side_cm) / 2

            # Сохраняем 3D точку
            point_3d = {
                "frame": self.frame_count,
                "X": float(x_final),
                "Y": float(y_cm),
                "Z": float(z_cm)
            }
            self.trajectory_3d.append(point_3d)

            return point_3d

        except Exception as e:
            print(f"Ошибка 3D реконструкции: {e}")
            return None

    def _get_best_point(self, detections):
        """Извлекает центр лучшей детекции"""
        if not detections:
            return None

        best = max(detections, key=lambda d: d['confidence'])
        center = best['center']
        return (center[0], center[1])

    def get_trajectory_3d(self):
        """Возвращает всю 3D траекторию"""
        return self.trajectory_3d

    def get_trajectory_2d_projection(self, camera='top'):
        """
        Возвращает 2D проекцию 3D траектории для отрисовки на кадре
        camera: 'top' или 'side'
        """
        if camera == 'top':
            return [(p['X'], p['Y']) for p in self.trajectory_3d]
        else:
            return [(p['X'], p['Z']) for p in self.trajectory_3d]

    def export_trajectory(self, filename="trajectory_3d.json"):
        """Экспортирует 3D траекторию в JSON файл"""
        import json
        with open(filename, 'w') as f:
            json.dump(self.trajectory_3d, f, indent=2)
        return filename