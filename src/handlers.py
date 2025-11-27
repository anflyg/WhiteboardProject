import cv2
from src.keystone import reorder_quad
from src.state import AppState


def on_mouse(state: AppState, event, x, y, flags, userdata) -> None:
    if not state.collecting_points:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        state.mouse_points.append((x, y))
        print(f"Hörn {len(state.mouse_points)} satt till ({x}, {y})")
        if len(state.mouse_points) == 4:
            state.keystone_src = reorder_quad(state.mouse_points)
            state.keystone_enabled = True
            state.collecting_points = False
            state.mouse_points.clear()
            print("Fyra hörn satta (omordnade TL,TR,BR,BL). Keystone aktiv.")
