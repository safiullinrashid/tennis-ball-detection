import numpy as np
from collections import deque

class BallTracker2D:
    """
    2D трекер для одной камеры
    """
    def __init__(self, max_history=300, max_jump_px=150):
        self.trajectory = []           # все точки (x, y, frame_id)
        self.history = deque(maxlen=10)  # последние 10 точек
        self.max_jump_px = max_jump_px   # максимальное перемещение за кадр (пиксели)
        self.frame_count = 0

    def update(self, detections, frame_shape):
        """
        Обновляет траекторию на основе детекций
        Возвращает: (x, y) или None
        """
        self.frame_count += 1
        h, w = frame_shape[:2]

        if not detections:
            # Нет детекции - экстраполируем
            return self._extrapolate()

        # Берем детекцию с максимальной уверенностью
        best = max(detections, key=lambda d: d['confidence'])
        center = best['center']
        x, y = center[0], center[1]

        # Проверка на вылет за пределы кадра
        if x < 0 or x > w or y < 0 or y > h:
            return self._extrapolate()

        # Проверка на слишком большой прыжок
        if self.history:
            last_x, last_y = self.history[-1]
            distance = np.sqrt((x - last_x)**2 + (y - last_y)**2)

            if distance > self.max_jump_px:
                # Возможно ложная детекция - используем предсказание
                return self._extrapolate()

        # Нормальная детекция
        self.history.append((x, y))
        self.trajectory.append({
            "frame": self.frame_count,
            "x": float(x),
            "y": float(y),
            "confidence": best['confidence']
        })
        return (x, y)

    def _extrapolate(self):
        """Предсказывает следующую позицию по последним точкам"""
        if len(self.history) < 2:
            return None

        if len(self.history) == 2:
            # Линейная экстраполяция
            (x1, y1), (x2, y2) = self.history[-2], self.history[-1]
            x = 2 * x2 - x1
            y = 2 * y2 - y1
        else:
            # Полиномиальная (3 точки)
            pts = list(self.history)[-3:]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]

            # Простая квадратичная экстраполяция
            dx1, dx2 = xs[1] - xs[0], xs[2] - xs[1]
            dy1, dy2 = ys[1] - ys[0], ys[2] - ys[1]

            x = xs[-1] + dx2 + (dx2 - dx1)
            y = ys[-1] + dy2 + (dy2 - dy1)

        # Проверка на вылет за пределы
        if x < 0 or x > 1920:  # примерные границы
            x = max(0, min(x, 1920))
        if y < 0 or y > 1080:
            y = max(0, min(y, 1080))

        self.history.append((x, y))
        self.trajectory.append({
            "frame": self.frame_count,
            "x": float(x),
            "y": float(y),
            "confidence": 0.0  # экстраполированная точка
        })
        return (x, y)

    def get_trajectory(self):
        """Возвращает всю траекторию для отрисовки"""
        return self.trajectory

    def get_trajectory_points(self):
        """Возвращает список точек (x, y) для отрисовки"""
        return [(t['x'], t['y']) for t in self.trajectory]

    def draw_trajectory(self, frame, color=(0, 255, 255), thickness=2):
        """Рисует траекторию на кадре"""
        points = self.get_trajectory_points()
        for i in range(1, len(points)):
            cv2.line(frame,
                    (int(points[i-1][0]), int(points[i-1][1])),
                    (int(points[i][0]), int(points[i][1])),
                    color, thickness)
        return frame