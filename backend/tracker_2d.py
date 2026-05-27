import cv2

class BallTracker2D:
    def __init__(self, ignore_bottom=550):
        self.trajectory = []
        self.ignore_bottom = ignore_bottom

    def update(self, detections, frame_height=None):
        if detections:
            for d in detections:
                center = d.get('center')
                confidence = d.get('confidence', 0)
                if not center or confidence < 0.1:
                    continue

                x, y = center[0], center[1]

                if frame_height and y > frame_height - self.ignore_bottom:
                    continue

                self.trajectory.append((x, y))

            if len(self.trajectory) > 500:
                self.trajectory = self.trajectory[-500:]

            if self.trajectory:
                return self.trajectory[-1]

        return None

    def get_trajectory_points(self):
        return self.trajectory

    def draw_trajectory(self, frame, color=(0, 255, 255), thickness=2):
        points = self.get_trajectory_points()
        for i in range(1, len(points)):
            p1 = (int(points[i-1][0]), int(points[i-1][1]))
            p2 = (int(points[i][0]), int(points[i][1]))
            cv2.line(frame, p1, p2, color, thickness)
        return frame

    def draw_detections(self, frame, detections, color=(0, 255, 0), thickness=2):
        for d in detections:
            x1, y1, x2, y2 = d['bbox']
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            cx, cy = d['center']
            cv2.circle(frame, (int(cx), int(cy)), 3, (0, 0, 255), -1)
        return frame