import cv2
import numpy as np
import json
import os

class CourtCalibration:
    """
    Калибровка стола для преобразования 2D → 3D
    """

    # Реальные размеры стола в сантиметрах
    COURT_WIDTH = 274.0   # длина (X)
    COURT_HEIGHT = 152.5  # ширина (Y)
    COURT_HEIGHT_CM = 76.0  # высота стола (Z)

    def __init__(self, calibration_file="court_calibration.json"):
        self.calibration_file = calibration_file
        self.M_top = None      # матрица для камеры сверху
        self.side_params = None  # параметры для боковой камеры

    def calibrate_top_camera(self, image, corners_px):
        """
        Калибровка камеры сверху по 4 углам стола
        corners_px: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] в пикселях
        Порядок: левый дальний, правый дальний, левый ближний, правый ближний
        """
        # Реальные координаты в сантиметрах
        corners_cm = np.array([
            [0, self.COURT_HEIGHT],      # левый дальний
            [self.COURT_WIDTH, self.COURT_HEIGHT],  # правый дальний
            [0, 0],                      # левый ближний
            [self.COURT_WIDTH, 0]        # правый ближний
        ], dtype=np.float32)

        corners_px = np.array(corners_px, dtype=np.float32)
        self.M_top = cv2.getPerspectiveTransform(corners_px, corners_cm)

        # Сохраняем калибровку
        self._save_calibration()
        return self.M_top

    def calibrate_side_camera(self, image, left_x_px, right_x_px, table_y_px, floor_y_px):
        """
        Калибровка боковой камеры
        left_x_px, right_x_px: координаты левого и правого края стола по X
        table_y_px: Y координата верхней кромки стола
        floor_y_px: Y координата пола
        """
        self.side_params = {
            "left_x": left_x_px,
            "right_x": right_x_px,
            "table_y": table_y_px,
            "floor_y": floor_y_px,
            "court_length_cm": self.COURT_WIDTH,
            "court_height_cm": self.COURT_HEIGHT_CM
        }
        self._save_calibration()
        return self.side_params

    def pixel_to_cm_top(self, x, y):
        """Преобразует пиксель в координаты стола (см) из камеры сверху"""
        if self.M_top is None:
            raise ValueError("Калибровка камеры сверху не выполнена")

        point = np.array([x, y], dtype=np.float32).reshape(-1, 1, 2)
        cm_coords = cv2.perspectiveTransform(point, self.M_top)
        return cm_coords[0][0]  # (X, Y) в см

    def pixel_to_cm_side(self, x, y):
        """Преобразует пиксель в координаты из боковой камеры"""
        if self.side_params is None:
            raise ValueError("Калибровка боковой камеры не выполнена")

        # X координата (длина стола)
        percent_x = (x - self.side_params["left_x"]) / (self.side_params["right_x"] - self.side_params["left_x"])
        x_cm = percent_x * self.side_params["court_length_cm"]
        x_cm = max(0, min(x_cm, self.side_params["court_length_cm"]))

        # Z координата (высота)
        percent_y = (y - self.side_params["table_y"]) / (self.side_params["floor_y"] - self.side_params["table_y"])
        z_cm = self.side_params["court_height_cm"] * (1 - percent_y)
        z_cm = max(0, min(z_cm, self.side_params["court_height_cm"] + 50))

        return x_cm, z_cm

    def _save_calibration(self):
        """Сохраняет калибровку в файл"""
        data = {}
        if self.M_top is not None:
            data['M_top'] = self.M_top.tolist()
        if self.side_params is not None:
            data['side_params'] = self.side_params

        with open(self.calibration_file, 'w') as f:
            json.dump(data, f)

    def load_calibration(self):
        """Загружает калибровку из файла"""
        if not os.path.exists(self.calibration_file):
            return False

        with open(self.calibration_file, 'r') as f:
            data = json.load(f)

        if 'M_top' in data:
            self.M_top = np.array(data['M_top'])
        if 'side_params' in data:
            self.side_params = data['side_params']

        return True