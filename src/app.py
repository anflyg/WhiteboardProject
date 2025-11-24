import cv2
from src.handlers import handle_key, on_mouse
from src.keystone import apply_keystone
from src.overlay import draw_help_overlay, draw_corner_markers
from src.state import AppState, default_keystone
from src.zoom import crop_zoom


class WhiteboardApp:
    def __init__(self) -> None:
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Could not open camera")

        self.window_name = "Whiteboard Assist"
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)

        ret, frame = self.cap.read()
        if not ret:
            self.cap.release()
            raise RuntimeError("Could not read initial frame from camera")

        h, w = frame.shape[:2]
        self.state = AppState(
            width=w,
            height=h,
            center=(w // 2, h // 2),
            keystone_src=default_keystone(w, h),
        )

        cv2.setMouseCallback(self.window_name, lambda event, x, y, flags, userdata: on_mouse(self.state, event, x, y, flags, userdata))

    def run(self) -> None:
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break

                frame = apply_keystone(
                    frame,
                    self.state.keystone_src,
                    self.state.keystone_enabled,
                    (self.state.width, self.state.height),
                )
                frame = crop_zoom(frame, self.state.center, self.state.zoom_scale)

                if self.state.show_help:
                    frame = draw_help_overlay(frame)
                if self.state.mouse_points:
                    frame = draw_corner_markers(frame, self.state.mouse_points)

                cv2.imshow(self.window_name, frame)

                key = cv2.waitKeyEx(1)
                if key == ord("q"):
                    break
                if key != -1:
                    handle_key(self.state, key)

                self.state.clamp_center()
        finally:
            self.cap.release()
            cv2.destroyAllWindows()

def main() -> None:
    app = WhiteboardApp()
    app.run()
