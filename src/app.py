"""
PySide6 GUI application wrapper for the whiteboard assist tool.
This replaces the previous cv2.namedWindow approach and uses a native menubar.
"""
from __future__ import annotations

import sys
from typing import Optional

import cv2
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox

from src.capture import list_available_cameras, open_camera
from src.handlers import on_mouse
from src.keystone import apply_keystone
from src.overlay import draw_corner_markers, draw_help_overlay
from src.state import AppState, default_keystone
from src.zoom import crop_zoom


class VideoLabel(QLabel):
    """Simple video widget that forwards mouse clicks to a callback."""

    def __init__(self, on_click, parent=None) -> None:
        super().__init__(parent)
        self._on_click = on_click
        self._frame_size: Optional[tuple[int, int]] = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 480)
        self.setStyleSheet("background-color: black;")
        # keep aspect by scaling pixmap manually (no QLabel stretching)
        self.setScaledContents(False)

    def set_frame_size(self, width: int, height: int) -> None:
        self._frame_size = (width, height)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._on_click:
            pos = event.position() if hasattr(event, "position") else event.pos()
            x, y = pos.x(), pos.y()
            if self._frame_size:
                frame_w, frame_h = self._frame_size
                # Map click from letterboxed/centered pixmap back to frame coords.
                label_w, label_h = max(1, self.width()), max(1, self.height())
                scale = min(label_w / frame_w, label_h / frame_h)
                display_w = frame_w * scale
                display_h = frame_h * scale
                offset_x = (label_w - display_w) / 2
                offset_y = (label_h - display_h) / 2
                x = (x - offset_x) / scale
                y = (y - offset_y) / scale
            self._on_click(int(x), int(y))
        super().mousePressEvent(event)


class WhiteboardWindow(QMainWindow):
    """
    Qt View/Controller that owns the capture device and orchestrates frame processing.
    Model: AppState
    View: this window + VideoLabel
    Controller: actions/shortcuts calling state mutations and capture changes
    """

    def __init__(self, camera_index: int = 0) -> None:
        super().__init__()
        self.setWindowTitle("Whiteboard Assist")

        self.cap = None
        self.state: Optional[AppState] = None

        self.video_label = VideoLabel(self._handle_mouse_click)
        self.setCentralWidget(self.video_label)

        self._init_camera(camera_index)
        self._build_menus()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_frame)
        self.timer.start(30)

    def _init_camera(self, camera_index: int) -> None:
        self.cap = open_camera(camera_index)
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
        # Set an initial size that matches the camera aspect ratio to avoid stretching on startup.
        self.video_label.set_frame_size(w, h)
        self.video_label.resize(w, h)
        self.state.current_camera_index = camera_index
        self.state.available_cameras = list_available_cameras()
        if camera_index not in self.state.available_cameras:
            self.state.available_cameras.insert(0, camera_index)
        self.statusBar().showMessage(f"Camera {camera_index}")

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # Camera menu
        self.camera_menu = menubar.addMenu("Camera")
        self._refresh_camera_menu()

        # View menu
        view_menu = menubar.addMenu("View")
        self._add_action(view_menu, "Zoom In", "Ctrl++", self._zoom_in)
        self._add_action(view_menu, "Zoom Out", "Ctrl+-", self._zoom_out)
        self._add_action(view_menu, "Reset View", "0", self._reset_view)
        help_act = self._add_action(view_menu, "Toggle Help Overlay", "H", self._toggle_help)
        help_act.setCheckable(True)
        help_act.setChecked(True)

        # Keystone menu
        keystone_menu = menubar.addMenu("Keystone")
        self._add_action(keystone_menu, "Toggle Keystone", "T", self._toggle_keystone)
        self._add_action(keystone_menu, "Reset Keystone", "R", self._reset_keystone)
        self._add_action(keystone_menu, "Set Corners (mouse)", "M", self._start_mouse_mode)
        keystone_menu.addSeparator()
        self._add_action(keystone_menu, "Nudge Corner Up", "I", lambda: self._nudge_corner("up"))
        self._add_action(keystone_menu, "Nudge Corner Left", "J", lambda: self._nudge_corner("left"))
        self._add_action(keystone_menu, "Nudge Corner Down", "K", lambda: self._nudge_corner("down"))
        self._add_action(keystone_menu, "Nudge Corner Right", "L", lambda: self._nudge_corner("right"))
        keystone_menu.addSeparator()
        for idx in range(4):
            self._add_action(
                keystone_menu,
                f"Select Corner {idx + 1}",
                str(idx + 1),
                lambda i=idx: self._select_corner(i),
            )

        # Help menu
        help_menu = menubar.addMenu("Help")
        self._add_action(help_menu, "Show Help Overlay", "H", self._toggle_help)
        self._add_action(help_menu, "Quit", "Q", self.close)

    def _add_action(self, menu, title: str, shortcut: str, handler):
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _refresh_camera_menu(self) -> None:
        self.camera_menu.clear()
        refresh_action = QAction("Refresh camera list", self)
        refresh_action.triggered.connect(self._refresh_camera_list)
        self.camera_menu.addAction(refresh_action)
        self.camera_menu.addSeparator()

        self._refresh_camera_list(populate_menu=False)
        if not self.state.available_cameras:
            no_cam = QAction("No cameras found", self)
            no_cam.setEnabled(False)
            self.camera_menu.addAction(no_cam)
            return

        for cam_idx in self.state.available_cameras:
            action = QAction(f"Camera {cam_idx}", self)
            action.setCheckable(True)
            action.setChecked(cam_idx == self.state.current_camera_index)
            action.triggered.connect(lambda checked, idx=cam_idx: self._switch_camera(idx))
            self.camera_menu.addAction(action)

    def _refresh_camera_list(self, populate_menu: bool = True) -> None:
        self.state.available_cameras = list_available_cameras()
        if self.state.current_camera_index not in self.state.available_cameras:
            self.state.available_cameras.insert(0, self.state.current_camera_index)
        if populate_menu:
            self._refresh_camera_menu()

    def _update_frame(self) -> None:
        if not self.cap or not self.state:
            return
        ret, frame = self.cap.read()
        if not ret:
            self.statusBar().showMessage("Kunde inte läsa från kameran")
            return

        frame = apply_keystone(frame, self.state.keystone_src, self.state.keystone_enabled, (self.state.width, self.state.height))
        frame = crop_zoom(frame, self.state.center, self.state.zoom_scale)
        if self.state.show_help:
            frame = draw_help_overlay(frame)
        if self.state.mouse_points:
            frame = draw_corner_markers(frame, self.state.mouse_points)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        self.video_label.set_frame_size(w, h)
        # scale pixmap to label while preserving aspect ratio to avoid stretching at startup
        pix = QPixmap.fromImage(qimg)
        self.video_label.setPixmap(pix.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.state.clamp_center()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self._zoom_in()
        elif key in (Qt.Key_Minus, Qt.Key_Underscore):
            self._zoom_out()
        elif key in (Qt.Key_Left, Qt.Key_A):
            self._pan(-self.state.pan_step, 0)
        elif key in (Qt.Key_Right, Qt.Key_D):
            self._pan(self.state.pan_step, 0)
        elif key in (Qt.Key_Up, Qt.Key_W):
            self._pan(0, -self.state.pan_step)
        elif key in (Qt.Key_Down, Qt.Key_S):
            self._pan(0, self.state.pan_step)
        elif key == Qt.Key_0:
            self._reset_view()
        elif key == Qt.Key_H:
            self._toggle_help()
        elif key == Qt.Key_T:
            self._toggle_keystone()
        elif key == Qt.Key_R:
            self._reset_keystone()
        elif key == Qt.Key_M:
            self._start_mouse_mode()
        elif key in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4):
            self._select_corner(int(chr(key)) - 1)
        elif key in (Qt.Key_I, Qt.Key_J, Qt.Key_K, Qt.Key_L):
            direction = {Qt.Key_I: "up", Qt.Key_K: "down", Qt.Key_J: "left", Qt.Key_L: "right"}[key]
            self._nudge_corner(direction)
        elif key == Qt.Key_Q:
            self.close()
        else:
            super().keyPressEvent(event)

    # --- Controller helpers ---
    def _zoom_in(self) -> None:
        self.state.zoom_scale *= 1.1

    def _zoom_out(self) -> None:
        self.state.zoom_scale = max(1.0, self.state.zoom_scale / 1.1)

    def _pan(self, dx: int, dy: int) -> None:
        cx, cy = self.state.center
        self.state.center = (cx + dx, cy + dy)

    def _toggle_help(self) -> None:
        self.state.show_help = not self.state.show_help

    def _reset_view(self) -> None:
        self.state.reset_view()

    def _toggle_keystone(self) -> None:
        self.state.keystone_enabled = not self.state.keystone_enabled

    def _reset_keystone(self) -> None:
        self.state.reset_keystone()

    def _start_mouse_mode(self) -> None:
        self.state.collecting_points = True
        self.state.mouse_points.clear()
        self.state.keystone_enabled = False
        self.statusBar().showMessage("Klicka 4 hörn (start övre-vänster, medurs)")

    def _select_corner(self, idx: int) -> None:
        self.state.selected_corner = idx
        self.statusBar().showMessage(f"Valt hörn: {idx + 1}")

    def _nudge_corner(self, direction: str) -> None:
        idx = self.state.selected_corner
        if self.state.keystone_src is None:
            return
        if direction == "left":
            self.state.keystone_src[idx, 0] = max(0, self.state.keystone_src[idx, 0] - self.state.keystone_step)
        elif direction == "right":
            self.state.keystone_src[idx, 0] = min(self.state.width - 1, self.state.keystone_src[idx, 0] + self.state.keystone_step)
        elif direction == "up":
            self.state.keystone_src[idx, 1] = max(0, self.state.keystone_src[idx, 1] - self.state.keystone_step)
        elif direction == "down":
            self.state.keystone_src[idx, 1] = min(self.state.height - 1, self.state.keystone_src[idx, 1] + self.state.keystone_step)
        self.state.keystone_enabled = True

    def _handle_mouse_click(self, x: int, y: int) -> None:
        if not self.state.collecting_points:
            return
        # Reuse existing click logic from handlers
        on_mouse(self.state, cv2.EVENT_LBUTTONDOWN, x, y, None, None)

    def _switch_camera(self, new_index: int) -> None:
        try:
            new_cap = open_camera(new_index)
            ret, frame = new_cap.read()
            if not ret:
                new_cap.release()
                QMessageBox.warning(self, "Kamera", f"Kunde inte läsa från kamera {new_index}")
                return
        except RuntimeError as exc:
            QMessageBox.warning(self, "Kamera", str(exc))
            return

        if self.cap:
            self.cap.release()
        self.cap = new_cap
        h, w = frame.shape[:2]
        self.state.width = w
        self.state.height = h
        self.state.current_camera_index = new_index
        self.state.reset_view()
        self.state.keystone_src = default_keystone(w, h)
        self._refresh_camera_list(populate_menu=False)
        self.statusBar().showMessage(f"Kamera {new_index} aktiv")

    def closeEvent(self, event) -> None:
        if self.cap:
            self.cap.release()
        super().closeEvent(event)


def main(camera_index: int = 0) -> None:
    app = QApplication(sys.argv)
    window = WhiteboardWindow(camera_index)
    window.show()
    sys.exit(app.exec())
