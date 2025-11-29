"""
Frame extraction and change detection.

Stub implementation that outlines SSIM/delta workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np


@dataclass
class FrameEvent:
    timestamp: float
    path: Optional[Path] = None
    occluded: bool = False
    reason: str = ""


class FrameExtractor:
    def __init__(
        self,
        ssim_threshold: float = 0.97,
        fallback_interval_seconds: int = 25,
    ) -> None:
        self.ssim_threshold = ssim_threshold
        self.fallback_interval_seconds = fallback_interval_seconds
        self._last_frame: Optional[np.ndarray] = None
        self._last_event_ts: float = 0.0

    def process_frame(self, frame: np.ndarray, timestamp: float) -> Optional[FrameEvent]:
        """
        Return a FrameEvent when a keyframe should be captured; otherwise None.
        Current placeholder logic: capture the first frame and then every fallback interval.
        """
        capture = False
        reason = ""
        if self._last_frame is None:
            capture = True
            reason = "first"
        elif (timestamp - self._last_event_ts) >= self.fallback_interval_seconds:
            capture = True
            reason = "interval"

        self._last_frame = frame

        if not capture:
            return None

        self._last_event_ts = timestamp
        return FrameEvent(timestamp=timestamp, occluded=False, reason=reason)

    def finalize(self) -> List[FrameEvent]:
        return []
