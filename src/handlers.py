import cv2
from src.keystone import reorder_quad
from src.state import (
    AppState,
    LEFT_KEYS,
    RIGHT_KEYS,
    UP_KEYS,
    DOWN_KEYS,
)


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


def handle_key(state: AppState, key: int) -> None:
    key_handlers = {
        ord("h"): lambda: _toggle_help(state),
        ord("0"): lambda: _reset_view(state),
        ord("t"): lambda: _toggle_keystone(state),
        ord("r"): lambda: _reset_keystone(state),
        ord("m"): lambda: _start_mouse_mode(state),
    }

    if key in key_handlers:
        key_handlers[key]()
    elif key in (ord("+"), ord("=")):
        state.zoom_scale *= 1.1
    elif key in (ord("-"), ord("_")):
        state.zoom_scale = max(1.0, state.zoom_scale / 1.1)
    elif key in LEFT_KEYS:
        _pan(state, -state.pan_step, 0)
    elif key in RIGHT_KEYS:
        _pan(state, state.pan_step, 0)
    elif key in UP_KEYS:
        _pan(state, 0, -state.pan_step)
    elif key in DOWN_KEYS:
        _pan(state, 0, state.pan_step)
    elif key in (ord("1"), ord("2"), ord("3"), ord("4")):
        _select_corner(state, int(chr(key)) - 1)
    elif key in (ord("i"), ord("j"), ord("k"), ord("l")):
        _nudge_corner(state, key)


def _toggle_help(state: AppState) -> None:
    state.show_help = not state.show_help


def _reset_view(state: AppState) -> None:
    state.reset_view()
    print("Återställd till originalvy.")


def _toggle_keystone(state: AppState) -> None:
    state.keystone_enabled = not state.keystone_enabled
    print(f"Keystone {'på' if state.keystone_enabled else 'av'}")


def _reset_keystone(state: AppState) -> None:
    state.reset_keystone()
    print("Keystone återställd.")


def _start_mouse_mode(state: AppState) -> None:
    state.collecting_points = True
    state.mouse_points.clear()
    state.keystone_enabled = False
    print("Klicka 4 hörn (start övre-vänster, sedan medurs).")


def _pan(state: AppState, dx: int, dy: int) -> None:
    cx, cy = state.center
    state.center = (cx + dx, cy + dy)


def _select_corner(state: AppState, idx: int) -> None:
    state.selected_corner = idx
    print(f"Valt hörn: {idx + 1}")


def _nudge_corner(state: AppState, key: int) -> None:
    idx = state.selected_corner
    if key == ord("j"):
        state.keystone_src[idx, 0] = max(0, state.keystone_src[idx, 0] - state.keystone_step)
    elif key == ord("l"):
        state.keystone_src[idx, 0] = min(state.width - 1, state.keystone_src[idx, 0] + state.keystone_step)
    elif key == ord("i"):
        state.keystone_src[idx, 1] = max(0, state.keystone_src[idx, 1] - state.keystone_step)
    elif key == ord("k"):
        state.keystone_src[idx, 1] = min(state.height - 1, state.keystone_src[idx, 1] + state.keystone_step)
    state.keystone_enabled = True
