"""
Frame extraction and change detection.

Stub implementation that outlines SSIM/delta workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import cv2


@dataclass
class FrameEvent:
    timestamp: float
    path: Optional[Path] = None
    occluded: bool = False
    reason: str = ""
    delta: float = 0.0


class FrameExtractor:
    def __init__(
        self,
        ssim_threshold: float = 0.97,
        fallback_interval_seconds: int = 25,
        delta_threshold: float = 8.0,
        downscale_width: int = 320,
        min_interval_seconds: float = 3.0,
        occlusion_dark_threshold: int = 35,
        occlusion_dark_ratio: float = 0.6,
        wipe_delta_threshold: float = 22.0,
        wipe_brightness_jump: float = 18.0,
    ) -> None:
        self.ssim_threshold = ssim_threshold
        self.fallback_interval_seconds = fallback_interval_seconds
        self.delta_threshold = delta_threshold
        self.downscale_width = downscale_width
        self.min_interval_seconds = min_interval_seconds
        self.occlusion_dark_threshold = occlusion_dark_threshold
        self.occlusion_dark_ratio = occlusion_dark_ratio
        self.wipe_delta_threshold = wipe_delta_threshold
        self.wipe_brightness_jump = wipe_brightness_jump
        self._last_frame: Optional[np.ndarray] = None
        self._last_small: Optional[np.ndarray] = None
        self._last_brightness: Optional[float] = None
        self._last_event_ts: float = 0.0

    def process_frame(self, frame: np.ndarray, timestamp: float) -> Optional[FrameEvent]:
        """
        Return a FrameEvent when a keyframe should be captured; otherwise None.
        Heuristic: första frame, sedan vid tydlig förändring (mean abs diff på nedskalad gråbild)
        eller fallback-intervall.
        """
        capture = False
        reason = ""
        occluded = False
        small = self._to_small_gray(frame)
        mean_brightness = float(np.mean(small))

        if self._is_dark_occlusion(small):
            occluded = True
            reason = "occluded"
        if self._last_small is None:
            capture = True
            reason = "first"
        else:
            delta = self._mean_abs_diff(self._last_small, small)
            if delta >= self.delta_threshold:
                capture = True
                reason = f"delta:{delta:.2f}"
                if self._looks_like_wipe(delta, mean_brightness):
                    reason = f"wipe:{delta:.2f}"
        if not capture and (timestamp - self._last_event_ts) >= self.fallback_interval_seconds:
            capture = True
            reason = "interval"

        self._last_frame = frame
        self._last_small = small
        self._last_brightness = mean_brightness

        if capture and self._last_event_ts > 0 and (timestamp - self._last_event_ts) < self.min_interval_seconds:
            capture = False
            reason = "too_soon"

        # Skip capturing obvious occlusion frames to avoid useless keyframes.
        if occluded:
            capture = False

        if not capture:
            return None

        self._last_event_ts = timestamp
        delta_val = self._mean_abs_diff(self._last_small, small) if self._last_small is not None else 0.0
        return FrameEvent(timestamp=timestamp, occluded=occluded, reason=reason, delta=delta_val)

    def finalize(self) -> List[FrameEvent]:
        return []

    def _to_small_gray(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if w <= 0 or h <= 0:
            return np.zeros((1, 1), dtype=np.uint8)
        scale = self.downscale_width / float(w)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return gray

    def _mean_abs_diff(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.shape != b.shape:
            return float("inf")
        return float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))))

    def _is_dark_occlusion(self, gray: np.ndarray) -> bool:
        dark_pixels = np.mean(gray < self.occlusion_dark_threshold)
        return dark_pixels >= self.occlusion_dark_ratio

    def _looks_like_wipe(self, delta: float, mean_brightness: float) -> bool:
        if self._last_brightness is None:
            return False
        brightness_jump = mean_brightness - self._last_brightness
        return delta >= self.wipe_delta_threshold and brightness_jump >= self.wipe_brightness_jump
