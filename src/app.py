"""
PySide6 GUI application wrapper for the whiteboard assist tool.
This replaces the previous cv2.namedWindow approach and uses a native menubar.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from shutil import rmtree, which
from pathlib import Path
from typing import Optional

import cv2
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
)

from src.capture import list_available_cameras, open_camera
from src.handlers import on_mouse
from src.keystone import apply_keystone
from src.overlay import draw_corner_markers, draw_help_overlay
from src.state import AppState, default_keystone
from src.zoom import crop_zoom
from src.ai_pipeline import (
    BoardState,
    FrameExtractor,
    load_config,
    make_transcriber,
    make_recognizer,
    AudioRecorder,
    export_session_package,
    AlignBlock,
    align_transcript_with_board,
    TileVersion,
)


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
        self.camera_action_group = QActionGroup(self)
        self.camera_action_group.setExclusive(True)

        # AI pipeline stubs (no heavy processing yet)
        self.ai_config = load_config()
        self.ai_running = False
        self.ai_started_at: Optional[float] = None
        self.frame_extractor = FrameExtractor(
            ssim_threshold=self.ai_config.ssim_threshold,
            fallback_interval_seconds=self.ai_config.fallback_interval_seconds,
            delta_threshold=getattr(self.ai_config, "frame_delta_threshold", 8.0),
            min_interval_seconds=getattr(self.ai_config, "min_frame_interval_seconds", 3.0),
        )
        self.board_state = BoardState(
            rows=self.ai_config.tile_rows,
            cols=self.ai_config.tile_cols,
            stabilization_seconds=self.ai_config.stabilization_seconds,
        )
        self.board_recognizer = make_recognizer(self.ai_config.vision_backend, lang=getattr(self.ai_config, "ocr_lang", None))
        self.transcriber = make_transcriber(self.ai_config.whisper_model, language=getattr(self.ai_config, "whisper_language", None))
        self.transcriber_is_dummy = self.transcriber.__class__.__name__ == "DummyTranscriber"
        self.transcriber_backend = getattr(self.transcriber, "backend_name", "unknown")
        self.transcriber_error = getattr(self.transcriber, "error", None)
        self.audio_recorder = AudioRecorder()
        self.session_dir: Optional[Path] = None
        self.frames_dir: Optional[Path] = None
        self.manifest_path: Optional[Path] = None
        self.manifest: dict = {}
        self.frame_count: int = 0
        self.audio_path: Optional[Path] = None
        self.last_export_dir: Optional[Path] = None
        self.last_export_error: Optional[str] = None
        self.ffmpeg_available: bool = self._check_ffmpeg()

        self._last_processed_frame = None

        self.video_label = VideoLabel(self._handle_mouse_click)
        self.video_label.installEventFilter(self)
        self.setCentralWidget(self.video_label)

        self._init_capture_button()

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

    def _init_capture_button(self) -> None:
        self.capture_button = QPushButton(self.video_label)
        self.capture_button.setObjectName("captureButton")
        self.capture_button.setFixedSize(72, 72)
        self.capture_button.setCursor(Qt.PointingHandCursor)
        self.capture_button.setToolTip("Ta foto (mellanslag eller Ctrl+P)")
        self.capture_button.setAccessibleName("Ta foto (stillbild)")
        self.capture_button.setText("PHOTO")
        self._style_capture_button()
        self.capture_button.clicked.connect(self._capture_frame)
        self._position_capture_button()

        # Recording button (continuous)
        self.record_button = QPushButton(self.video_label)
        self.record_button.setObjectName("recordButton")
        self.record_button.setFixedSize(72, 72)
        self.record_button.setCursor(Qt.PointingHandCursor)
        self.record_button.setToolTip("Starta eller stoppa AI-inspelning (Ctrl+Shift+S/E)")
        self.record_button.setAccessibleName("Starta eller stoppa AI-inspelning")
        self.record_button.setText("AI REC")
        self.record_button.clicked.connect(self._toggle_ai_recording)
        self._style_record_button(active=False)
        self._position_record_button()

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        # Camera menu
        self.camera_menu = menubar.addMenu("Camera")
        self._refresh_camera_menu()

        # Capture menu
        capture_menu = menubar.addMenu("Capture")
        self._add_action(capture_menu, "Take Photo", "Ctrl+P", self._capture_frame)
        self._add_action(capture_menu, "Choose Save Folder...", "", self._choose_capture_dir)
        self._add_action(capture_menu, "Set Subject Prefix...", "", self._set_capture_prefix)
        format_menu = capture_menu.addMenu("Image Format")
        self.format_group = QActionGroup(self)
        self.format_group.setExclusive(True)
        for fmt in ("jpg", "png"):
            action = QAction(fmt.upper(), self)
            action.setCheckable(True)
            action.setChecked(fmt == self.state.capture_format)
            action.triggered.connect(lambda checked, f=fmt: self._set_capture_format(f))
            self.format_group.addAction(action)
            format_menu.addAction(action)

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

        # AI menu (start/stop stub)
        ai_menu = menubar.addMenu("AI")
        self._add_action(ai_menu, "Start AI (recommended mode)", "Ctrl+Shift+S", self._start_ai)
        self._add_action(ai_menu, "Stop AI", "Ctrl+Shift+E", self._stop_ai)
        self._add_action(ai_menu, "Exportera för ChatGPT", "Ctrl+Shift+X", self._export_for_chatgpt)

        # Help menu
        help_menu = menubar.addMenu("Help")
        self._add_action(help_menu, "Show Help Overlay", "H", self._toggle_help)
        self._add_action(help_menu, "FFmpeg install guide", "", self._show_ffmpeg_help)
        self._add_action(help_menu, "Quit", "Q", self.close)

    def _add_action(self, menu, title: str, shortcut: str, handler):
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _style_capture_button(self) -> None:
        # Mimic a minimal camera shutter button
        self.capture_button.setStyleSheet(
            """
            QPushButton#captureButton {
                background-color: #a00000;
                border: 4px solid #ff5f5f;
                border-radius: 36px;
            }
            QPushButton#captureButton:hover {
                background-color: #b30000;
                border-color: #ff8a8a;
            }
            QPushButton#captureButton:pressed {
                background-color: #7a0000;
                border-color: #ffb3b3;
            }
            QPushButton#captureButton {
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            """
        )

    def _style_record_button(self, active: bool) -> None:
        if active:
            style = """
            QPushButton#recordButton {
                background-color: #d00000;
                border: 4px solid #ff8080;
                border-radius: 36px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#recordButton:hover {
                background-color: #e00000;
                border-color: #ff9a9a;
            }
            QPushButton#recordButton:pressed {
                background-color: #900000;
                border-color: #ffbfbf;
            }
            """
        else:
            style = """
            QPushButton#recordButton {
                background-color: #444;
                border: 4px solid #777;
                border-radius: 36px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#recordButton:hover {
                background-color: #555;
                border-color: #888;
            }
            QPushButton#recordButton:pressed {
                background-color: #333;
                border-color: #aaa;
            }
            """
        self.record_button.setStyleSheet(style)

    def _position_capture_button(self) -> None:
        if not getattr(self, "capture_button", None):
            return
        margin = 16
        btn_size = self.capture_button.size()
        x = max(margin, self.video_label.width() - btn_size.width() - margin)
        y = max(margin, self.video_label.height() - btn_size.height() - margin)
        self.capture_button.move(x, y)
        self.capture_button.raise_()

    def _position_record_button(self) -> None:
        if not getattr(self, "record_button", None):
            return
        margin = 16
        btn_size = self.record_button.size()
        x = margin
        y = max(margin, self.video_label.height() - btn_size.height() - margin)
        self.record_button.move(x, y)
        self.record_button.raise_()

    def _refresh_camera_menu(self) -> None:
        self.camera_menu.clear()
        self.camera_action_group = QActionGroup(self)
        self.camera_action_group.setExclusive(True)
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
            self.camera_action_group.addAction(action)
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
        self._last_processed_frame = frame.copy()
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

        # AI pipeline stub hook: check for frame events while running
        if self.ai_running:
            now = time.monotonic()
            rel_ts = now - (self.ai_started_at or now)
            event = self.frame_extractor.process_frame(self._last_processed_frame, rel_ts)
            if event:
                saved_path = self._save_frame_event(event, self._last_processed_frame)
                if saved_path:
                    self._append_manifest_frame(
                        event.timestamp,
                        saved_path,
                        reason=event.reason,
                        delta=event.delta,
                        occluded=event.occluded,
                    )
                changed_versions = self.board_state.update_frame(
                    rel_ts,
                    frame_path=str(saved_path) if saved_path else None,
                    reason=event.reason,
                    delta=event.delta,
                    occluded=event.occluded,
                    frame=self._last_processed_frame,
                )
                board_frame = self.board_state.frame_history[-1]
                print(
                    "[BOARD STATE] "
                    f"frame={board_frame.frame_id} rev={board_frame.revision_id} "
                    f"reason={board_frame.reason or 'unknown'} ts={board_frame.timestamp:.2f} "
                    f"changed_versions={len(changed_versions)} "
                    f"max_tile_delta={board_frame.max_tile_delta:.2f} "
                    f"changed_tiles={board_frame.changed_tile_count}",
                    flush=True,
                )
                self.statusBar().showMessage(
                    f"Inspelning pågår: {self.frame_count} bild(er) sparade"
                    + ("" if self.audio_recorder.backend_available else " (ingen ljud-backend)")
                )

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
        elif key == Qt.Key_Space:
            self._capture_frame()
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

    def _capture_frame(self) -> None:
        if not self.state:
            QMessageBox.warning(self, "Foto", "App-tillstånd saknas. Försök igen.")
            return

        if self._last_processed_frame is None:
            QMessageBox.warning(self, "Foto", "Ingen bild att spara ännu.")
            return

        save_dir = self._ensure_capture_dir()
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        prefix = self._safe_prefix(self.state.capture_prefix)
        name_parts = [part for part in (prefix, f"whiteboard-{timestamp}") if part]
        filename = "_".join(name_parts) + f".{self.state.capture_format}"
        filepath = save_dir / filename

        try:
            ok = cv2.imwrite(str(filepath), self._last_processed_frame)
        except Exception as exc:
            QMessageBox.warning(self, "Foto", f"Kunde inte spara bilden:\n{exc}")
            return

        if ok:
            self.statusBar().showMessage(f"Sparade foto: {filepath}")
        else:
            QMessageBox.warning(
                self,
                "Foto",
                f"Kunde inte spara bilden till {filepath}.\nKontrollera skrivbehörighet eller välj annan mapp via Capture → Choose Save Folder.",
            )

    def _ensure_capture_dir(self) -> Path:
        directory = self.state.capture_dir or Path.home() / "Documents" / "WhiteboardShots"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _safe_prefix(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", text.strip())
        return cleaned.strip("-")

    def _choose_capture_dir(self) -> None:
        start_dir = str(self.state.capture_dir) if self.state.capture_dir else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "Välj mapp för bilder", start_dir)
        if selected:
            self.state.capture_dir = Path(selected)
            self.statusBar().showMessage(f"Sparar bilder i: {self.state.capture_dir}")

    def _set_capture_prefix(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Ämne / föreläsning",
            "Prefix för filnamn (valfritt):",
            text=self.state.capture_prefix,
        )
        if ok:
            self.state.capture_prefix = text.strip()
            preview = self._safe_prefix(self.state.capture_prefix)
            example = f"{preview + '_' if preview else ''}whiteboard-YYYY-MM-DD_HH-MM-SS.{self.state.capture_format}"
            self.statusBar().showMessage(f"Prefix sparat. Exempel: {example}")

    def _set_capture_format(self, fmt: str) -> None:
        fmt = fmt.lower()
        if fmt not in ("jpg", "png"):
            return
        self.state.capture_format = fmt
        if hasattr(self, "format_group"):
            for action in self.format_group.actions():
                action.setChecked(action.text().lower() == fmt)

    def _handle_mouse_click(self, x: int, y: int) -> None:
        if not self.state.collecting_points:
            return
        # Reuse existing click logic from handlers
        on_mouse(self.state, cv2.EVENT_LBUTTONDOWN, x, y, None, None)

    # --- AI control (stub) ---
    def _start_ai(self) -> None:
        if self.ai_running:
            self.statusBar().showMessage("AI är redan igång (stub)")
            return
        self._start_new_session()
        self.ai_running = True
        self.ai_started_at = time.monotonic()
        self._start_audio()
        if not self.ffmpeg_available:
            self.statusBar().showMessage("FFmpeg saknas – installera via hjälp-menyn för transkription.")
        if self.transcriber_is_dummy:
            extra = f" (fel: {self.transcriber_error})" if self.transcriber_error else ""
            self.statusBar().showMessage(f"faster-whisper saknas/laddas ej{extra}; ingen transkription.")
        profile_msg = (
            f"AI-profil: {self.ai_config.name} | Modell: {self.ai_config.whisper_model} | "
            f"Backend: {self.transcriber_backend}"
        )
        print(f"[AI CONFIG] {profile_msg}", flush=True)
        self.statusBar().showMessage(profile_msg)
        self._style_record_button(active=True)

    def _stop_ai(self) -> Optional[Path]:
        if not self.ai_running:
            self.statusBar().showMessage("AI är redan stoppad")
            return None
        self.ai_running = False
        self.board_state.close_versions(time.monotonic() - (self.ai_started_at or 0))
        self._stop_audio()
        export_dir = self._postprocess_session()
        self._finalize_manifest()
        self.statusBar().showMessage("AI stoppad (export klar)")
        self._style_record_button(active=False)
        return export_dir

    def _toggle_ai_recording(self) -> None:
        if self.ai_running:
            self._stop_ai()
        else:
            self._start_ai()

    def _export_for_chatgpt(self) -> None:
        """
        User-triggered GUI flow for ChatGPT export.
        """
        try:
            if self.ai_running:
                export_dir = self._stop_ai()
                if export_dir:
                    QMessageBox.information(
                        self,
                        "Export klar",
                        f"Underlaget för ChatGPT är exporterat.\n\nSparad plats:\n{export_dir}",
                    )
                    return
                raise RuntimeError(self.last_export_error or "Exporten kunde inte skapas.")

            if self.session_dir and self.session_dir.exists() and self.manifest:
                export_dir = self._postprocess_session(raise_on_error=True)
                QMessageBox.information(
                    self,
                    "Export klar",
                    f"Underlaget för ChatGPT är exporterat.\n\nSparad plats:\n{export_dir}",
                )
                return

            if self.last_export_dir and self.last_export_dir.exists():
                QMessageBox.information(
                    self,
                    "Exportera för ChatGPT",
                    f"Senaste export finns här:\n{self.last_export_dir}",
                )
                return

            QMessageBox.information(
                self,
                "Exportera för ChatGPT",
                "Ingen inspelad session att exportera ännu.\nStarta AI-inspelning och stoppa den först.",
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Export misslyckades",
                "Kunde inte exportera underlag för ChatGPT.\n\n"
                f"Fel: {exc}",
            )

    def _start_audio(self) -> None:
        if not self.session_dir:
            return
        self.audio_path = self.session_dir / "audio.wav"
        ok = self.audio_recorder.start(self.audio_path)
        if not ok:
            self.statusBar().showMessage("Ljud-backend saknas, spelar inte in ljud")
        elif self.transcriber_is_dummy:
            self.statusBar().showMessage(
                f"Ljud inspelas med {self.audio_recorder.backend_name}, men faster-whisper saknas/ffmpeg saknas (ingen transkription)"
            )
        elif not self.ffmpeg_available:
            self.statusBar().showMessage(
                f"Ljud inspelas med {self.audio_recorder.backend_name}, men ffmpeg saknas (installera via hjälp-menyn)"
            )
        else:
            self.statusBar().showMessage(f"Ljud inspelas med {self.audio_recorder.backend_name}")

    def _stop_audio(self) -> None:
        try:
            self.audio_recorder.stop()
        except Exception:
            pass

    def _postprocess_session(self, raise_on_error: bool = False) -> Optional[Path]:
        """
        Minimal postprocess: transcribe audio, align frames, export stable session package.
        """
        export_root = (Path.cwd() / self.ai_config.export_dir).resolve()
        self.last_export_error = None
        export_dir: Optional[Path] = None

        transcript = []
        transcript_error = None
        if self.audio_path and self.audio_path.exists() and self.audio_path.stat().st_size > 0:
            try:
                transcript = self.transcriber.transcribe(self.audio_path)
            except Exception as exc:
                transcript_error = str(exc)
        else:
            transcript_error = "Ingen ljudfil inspelad eller filen är tom."

        frames = self.manifest.get("frames", [])

        # Kör enkel board-recognition på sessionsframes (text vs ritningar)
        board_tiles: list[TileVersion] = []
        for f in frames:
            try:
                if not self.session_dir:
                    continue
                frame_path = self.session_dir / f["path"]
                rec = self.board_recognizer.recognize(frame_path)
                ts = f.get("timestamp", 0)
                if rec.text:
                    board_tiles.append(TileVersion(tile_id=(0, len(board_tiles)), start=ts, end=ts, text=rec.text, image_path=None))
                for img_path in rec.images:
                    board_tiles.append(
                        TileVersion(tile_id=(0, len(board_tiles)), start=ts, end=ts, text=None, image_path=str(img_path))
                    )
            except Exception:
                continue

        if transcript:
            if board_tiles:
                blocks = align_transcript_with_board(transcript, board_tiles)
            else:
                blocks = [AlignBlock(start=seg.start, end=seg.end, speech_text=seg.text, board_text=[], board_images=[]) for seg in transcript]
        else:
            blocks = []

        detail = f" ({self.transcriber_error})" if self.transcriber_error else ""
        effective_transcript_error = transcript_error
        if not effective_transcript_error and self.transcriber_is_dummy:
            effective_transcript_error = f"faster-whisper saknas eller kunde inte laddas{detail}."
        self.manifest["board_state"] = self.board_state.export_metadata()

        try:
            export_dir = export_session_package(
                export_root,
                source_session_dir=self.session_dir,
                session_manifest=self.manifest,
                transcript=transcript,
                align_blocks=blocks,
                transcript_error=effective_transcript_error,
            )
            self.last_export_dir = export_dir
            print(f"[EXPORT] success session={export_dir.name}", flush=True)
            self.statusBar().showMessage(f"Export skapad: {export_dir.name}")
        except Exception as exc:
            self.last_export_error = str(exc)
            print(f"[EXPORT] failure error={exc}", flush=True)
            self.statusBar().showMessage(f"Export misslyckades: {exc}")
            if raise_on_error:
                raise
        finally:
            # Cleanup intermediates if configured
            if not self.ai_config.keep_intermediates and self.session_dir:
                try:
                    rmtree(self.session_dir)
                except Exception:
                    pass
        return export_dir

    # --- Session / manifest helpers ---
    def _start_new_session(self) -> None:
        # Create session folder and manifest under configured capture dir
        run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")
        base_dir = (Path.cwd() / self.ai_config.capture_dir).resolve()
        self.session_dir = base_dir / run_id
        self.frames_dir = self.session_dir / "frames"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.session_dir / "manifest.json"
        self.frame_count = 0
        self.manifest = {
            "run_id": run_id,
            "started_at": datetime.now().isoformat(),
            "profile": self.ai_config.name,
            "whisper_model": self.ai_config.whisper_model,
            "transcription_backend": self.transcriber_backend,
            "transcription_language": getattr(self.ai_config, "whisper_language", None),
            "capture_dir": str(self.session_dir),
            "audio": "audio.wav",
            "frames": [],
        }
        self._write_manifest()

    def _append_manifest_frame(self, timestamp: float, path: Path, reason: str = "", delta: float = 0.0, occluded: bool = False) -> None:
        if not self.manifest_path:
            return
        rel_path = path.relative_to(self.session_dir) if self.session_dir else path.name
        self.manifest.setdefault("frames", []).append(
            {"timestamp": timestamp, "path": str(rel_path), "reason": reason, "delta": delta, "occluded": occluded}
        )
        self.frame_count += 1
        self._write_manifest()

    def _finalize_manifest(self) -> None:
        if not self.manifest_path:
            return
        self.manifest["ended_at"] = datetime.now().isoformat()
        self.manifest["frame_count"] = self.frame_count
        self._write_manifest()

    def _write_manifest(self) -> None:
        if not self.manifest_path:
            return
        try:
            self.manifest_path.write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _save_frame_event(self, event, frame) -> Optional[Path]:
        if not self.frames_dir:
            return None
        # Build filename with timestamp to keep ordering.
        filename = f"frame-{event.timestamp:.2f}.jpg"
        filepath = self.frames_dir / filename
        try:
            cv2.imwrite(str(filepath), frame)
            return filepath
        except Exception:
            return None

    def _check_ffmpeg(self) -> bool:
        return which("ffmpeg") is not None

    def _show_ffmpeg_help(self) -> None:
        msg = (
            "ffmpeg krävs för transkription (faster-whisper).\n\n"
            "macOS:\n"
            "  1) Installera Homebrew (om saknas):\n"
            "     /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"\n"
            "  2) Lägg till brew i PATH:\n"
            "     echo 'eval \"$(/opt/homebrew/bin/brew shellenv)\"' >> ~/.zprofile\n"
            "     eval \"$(/opt/homebrew/bin/brew shellenv)\"\n"
            "  3) Installera ffmpeg:\n"
            "     brew install ffmpeg\n\n"
            "Windows:\n"
            "  1) Installera ffmpeg via officiell build (gyan.dev eller ffmpeg.org) eller via paketmanager (winget/choco).\n"
            "  2) Lägg till ffmpeg/bin i PATH och starta om appen."
        )
        QMessageBox.information(self, "ffmpeg install", msg)

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
        self._refresh_camera_menu()
        self.statusBar().showMessage(f"Kamera {new_index} aktiv")

    def eventFilter(self, obj, event):
        if obj is self.video_label and event.type() == QEvent.Resize:
            self._position_capture_button()
            self._position_record_button()
        return super().eventFilter(obj, event)

    def closeEvent(self, event) -> None:
        if self.cap:
            self.cap.release()
        if self.ai_running:
            self._stop_ai()
        super().closeEvent(event)


def main(camera_index: int = 0) -> None:
    app = QApplication(sys.argv)
    window = WhiteboardWindow(camera_index)
    window.show()
    sys.exit(app.exec())
