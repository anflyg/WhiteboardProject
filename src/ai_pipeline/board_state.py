"""
Tile-based board state tracking.

First practical version for tracking board state over time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class TileVersion:
    tile_id: Tuple[int, int]
    start: float
    end: Optional[float]
    text: Optional[str] = None
    latex: Optional[str] = None
    image_path: Optional[str] = None


@dataclass
class BoardFrameState:
    frame_id: str
    timestamp: float
    reason: str
    delta: float
    occluded: bool
    frame_path: Optional[str]
    revision_id: str
    mean_tile_delta: float
    max_tile_delta: float
    changed_tile_count: int
    tile_deltas: Dict[str, float]
    detected_events: List[str] = field(default_factory=list)


@dataclass
class BoardRevision:
    revision_id: str
    start: float
    end: Optional[float]
    event_reason: str
    first_frame_id: str
    last_frame_id: str
    frame_count: int = 0
    occluded_frames: int = 0


@dataclass
class BoardSemanticEvent:
    event_id: str
    event_type: str
    timestamp: float
    frame_id: str
    revision_id: str
    details: Dict[str, object] = field(default_factory=dict)


class BoardState:
    def __init__(
        self,
        rows: int = 3,
        cols: int = 4,
        stabilization_seconds: float = 0.8,
        tile_delta_change_threshold: float = 6.0,
        wipe_changed_ratio_threshold: float = 0.7,
        wipe_mean_delta_multiplier: float = 1.8,
        section_changed_ratio_threshold: float = 0.4,
        section_max_delta_multiplier: float = 1.4,
        min_section_gap_seconds: float = 8.0,
        stable_max_delta_multiplier: float = 0.6,
        stable_changed_tiles_ratio_threshold: float = 0.15,
        min_stable_duration_seconds: float = 4.0,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.stabilization_seconds = stabilization_seconds
        self.tile_delta_change_threshold = tile_delta_change_threshold
        self.wipe_changed_ratio_threshold = wipe_changed_ratio_threshold
        self.wipe_mean_delta_multiplier = wipe_mean_delta_multiplier
        self.section_changed_ratio_threshold = section_changed_ratio_threshold
        self.section_max_delta_multiplier = section_max_delta_multiplier
        self.min_section_gap_seconds = min_section_gap_seconds
        self.stable_max_delta_multiplier = stable_max_delta_multiplier
        self.stable_changed_tiles_ratio_threshold = stable_changed_tiles_ratio_threshold
        self.min_stable_duration_seconds = min_stable_duration_seconds
        self.versions: List[TileVersion] = []
        self.frame_history: List[BoardFrameState] = []
        self.revisions: List[BoardRevision] = []
        self.events: List[BoardSemanticEvent] = []
        self._frame_index = 0
        self._revision_index = 0
        self._event_index = 0
        self._section_index = 0
        self._open_revision_id: Optional[str] = None
        self._open_tile_version: Optional[TileVersion] = None
        self._last_gray_frame: Optional[np.ndarray] = None
        self._last_section_started_ts: Optional[float] = None
        self._current_section_id: Optional[str] = None
        self._current_section_stable: bool = False
        self._last_unstable_ts: Optional[float] = None

    def update_frame(
        self,
        timestamp: float,
        frame_path: Optional[str] = None,
        reason: str = "",
        delta: float = 0.0,
        occluded: bool = False,
        frame: Optional[np.ndarray] = None,
    ) -> List[TileVersion]:
        """
        Register a keyframe/frame-event in the board timeline.
        This is intentionally simple but real and used in runtime code path.
        Returns the currently affected tile versions (non-empty in normal runtime).
        """
        self._frame_index += 1
        frame_id = f"bf_{self._frame_index:05d}"
        reason_key = (reason or "unknown").split(":", 1)[0]
        changed_versions: List[TileVersion] = []

        if self._open_revision_id is None:
            self._start_revision(timestamp, reason_key, frame_id, frame_path)
            if self._open_tile_version:
                changed_versions.append(self._open_tile_version)
        elif not occluded and self._should_start_new_revision(reason_key):
            self._close_current_revision(timestamp)
            if self.versions:
                changed_versions.append(self.versions[-1])
            self._start_revision(timestamp, reason_key, frame_id, frame_path)
            if self._open_tile_version:
                changed_versions.append(self._open_tile_version)
        elif self._open_tile_version and self._open_tile_version not in changed_versions:
            changed_versions.append(self._open_tile_version)

        revision = self.revisions[-1]
        revision.last_frame_id = frame_id
        revision.frame_count += 1
        if occluded:
            revision.occluded_frames += 1

        tile_deltas = self._compute_tile_deltas(frame)
        delta_values = list(tile_deltas.values())
        mean_tile_delta = float(np.mean(delta_values)) if delta_values else 0.0
        max_tile_delta = float(np.max(delta_values)) if delta_values else 0.0
        changed_tile_count = sum(1 for d in delta_values if d >= self.tile_delta_change_threshold)
        changed_ratio = (changed_tile_count / max(1, self.rows * self.cols))
        detected_events = self._detect_semantic_events(
            timestamp=float(timestamp),
            frame_id=frame_id,
            revision_id=revision.revision_id,
            reason_key=reason_key,
            occluded=bool(occluded),
            changed_tile_count=changed_tile_count,
            changed_ratio=changed_ratio,
            mean_tile_delta=mean_tile_delta,
            max_tile_delta=max_tile_delta,
        )

        frame_state = BoardFrameState(
            frame_id=frame_id,
            timestamp=float(timestamp),
            reason=reason or "",
            delta=float(delta),
            occluded=bool(occluded),
            frame_path=frame_path,
            revision_id=revision.revision_id,
            mean_tile_delta=mean_tile_delta,
            max_tile_delta=max_tile_delta,
            changed_tile_count=changed_tile_count,
            tile_deltas=tile_deltas,
            detected_events=detected_events,
        )
        self.frame_history.append(frame_state)
        return changed_versions

    def _detect_semantic_events(
        self,
        *,
        timestamp: float,
        frame_id: str,
        revision_id: str,
        reason_key: str,
        occluded: bool,
        changed_tile_count: int,
        changed_ratio: float,
        mean_tile_delta: float,
        max_tile_delta: float,
    ) -> List[str]:
        detected: List[str] = []
        if occluded:
            return detected

        wipe_detected = (
            reason_key in {"delta", "wipe", "interval"}
            and changed_ratio >= self.wipe_changed_ratio_threshold
            and mean_tile_delta >= (self.tile_delta_change_threshold * self.wipe_mean_delta_multiplier)
        )
        if wipe_detected:
            self._register_event(
                event_type="wipe_detected",
                timestamp=timestamp,
                frame_id=frame_id,
                revision_id=revision_id,
                details={"changed_ratio": changed_ratio, "mean_tile_delta": mean_tile_delta, "max_tile_delta": max_tile_delta},
            )
            detected.append("wipe_detected")

        should_start_section = False
        section_reason = ""
        if self._last_section_started_ts is None:
            should_start_section = True
            section_reason = "first_frame"
        elif wipe_detected:
            should_start_section = True
            section_reason = "after_wipe"
        elif (
            changed_ratio >= self.section_changed_ratio_threshold
            and max_tile_delta >= (self.tile_delta_change_threshold * self.section_max_delta_multiplier)
            and (timestamp - (self._last_section_started_ts or 0)) >= self.min_section_gap_seconds
        ):
            should_start_section = True
            section_reason = "large_change"

        if should_start_section:
            self._section_index += 1
            section_id = f"sec_{self._section_index:04d}"
            self._last_section_started_ts = timestamp
            self._current_section_id = section_id
            self._current_section_stable = False
            self._last_unstable_ts = timestamp
            self._register_event(
                event_type="section_started",
                timestamp=timestamp,
                frame_id=frame_id,
                revision_id=revision_id,
                details={"section_id": section_id, "reason": section_reason},
            )
            detected.append("section_started")

        # Stable section detection v1: low tile-change for a minimum duration,
        # and not simultaneously in a new section/wipe event.
        stable_max_delta = self.tile_delta_change_threshold * self.stable_max_delta_multiplier
        stable_changed_tiles_limit = max(0, int(np.ceil(self.rows * self.cols * self.stable_changed_tiles_ratio_threshold)))
        low_change = max_tile_delta <= stable_max_delta and changed_tile_count <= stable_changed_tiles_limit

        if self._current_section_id and not wipe_detected and "section_started" not in detected:
            if low_change:
                if self._last_unstable_ts is None:
                    self._last_unstable_ts = timestamp
                elapsed_low_change = timestamp - self._last_unstable_ts
                if (not self._current_section_stable) and elapsed_low_change >= self.min_stable_duration_seconds:
                    self._current_section_stable = True
                    self._register_event(
                        event_type="section_stable",
                        timestamp=timestamp,
                        frame_id=frame_id,
                        revision_id=revision_id,
                        details={
                            "section_id": self._current_section_id,
                            "low_change_seconds": elapsed_low_change,
                            "max_tile_delta": max_tile_delta,
                            "changed_tile_count": changed_tile_count,
                        },
                    )
                    detected.append("section_stable")
            else:
                self._last_unstable_ts = timestamp
                self._current_section_stable = False
        return detected

    def _register_event(
        self,
        *,
        event_type: str,
        timestamp: float,
        frame_id: str,
        revision_id: str,
        details: Optional[Dict[str, object]] = None,
    ) -> None:
        self._event_index += 1
        self.events.append(
            BoardSemanticEvent(
                event_id=f"be_{self._event_index:05d}",
                event_type=event_type,
                timestamp=timestamp,
                frame_id=frame_id,
                revision_id=revision_id,
                details=details or {},
            )
        )

    def _compute_tile_deltas(self, frame: Optional[np.ndarray]) -> Dict[str, float]:
        if frame is None:
            return {}
        if frame.ndim == 3:
            gray = np.mean(frame.astype(np.float32), axis=2)
        elif frame.ndim == 2:
            gray = frame.astype(np.float32)
        else:
            return {}

        row_blocks = np.array_split(gray, self.rows, axis=0)
        prev_row_blocks = np.array_split(self._last_gray_frame, self.rows, axis=0) if self._last_gray_frame is not None else None
        tile_deltas: Dict[str, float] = {}
        for r, row_block in enumerate(row_blocks):
            col_blocks = np.array_split(row_block, self.cols, axis=1)
            for c, tile in enumerate(col_blocks):
                tile_id = f"{r},{c}"
                if tile.size == 0:
                    tile_deltas[tile_id] = 0.0
                    continue
                if self._last_gray_frame is None:
                    tile_deltas[tile_id] = 0.0
                else:
                    prev_col_blocks = np.array_split(prev_row_blocks[r], self.cols, axis=1)
                    prev_tile = prev_col_blocks[c]
                    if prev_tile.shape != tile.shape:
                        tile_deltas[tile_id] = float("inf")
                    else:
                        tile_deltas[tile_id] = float(np.mean(np.abs(tile - prev_tile)))

        self._last_gray_frame = gray
        return tile_deltas

    def _should_start_new_revision(self, reason_key: str) -> bool:
        return reason_key in {"first", "delta", "interval", "wipe"}

    def _start_revision(self, timestamp: float, reason_key: str, frame_id: str, frame_path: Optional[str]) -> None:
        self._revision_index += 1
        revision_id = f"rev_{self._revision_index:04d}"
        revision = BoardRevision(
            revision_id=revision_id,
            start=float(timestamp),
            end=None,
            event_reason=reason_key,
            first_frame_id=frame_id,
            last_frame_id=frame_id,
        )
        self.revisions.append(revision)
        self._open_revision_id = revision_id

        # Keep one global tile-version timeline in this package.
        tile = TileVersion(tile_id=(0, 0), start=float(timestamp), end=None, image_path=frame_path)
        self.versions.append(tile)
        self._open_tile_version = tile

    def _close_current_revision(self, timestamp: float) -> None:
        if self.revisions and self.revisions[-1].end is None:
            self.revisions[-1].end = float(timestamp)
        if self._open_tile_version and self._open_tile_version.end is None:
            self._open_tile_version.end = float(timestamp)

    def close_versions(self, timestamp: float) -> None:
        """
        Close open revision/tile versions at end of processing.
        """
        self._close_current_revision(timestamp)
        for v in self.versions:
            if v.end is None:
                v.end = timestamp
        self._open_revision_id = None
        self._open_tile_version = None

    def export_metadata(self) -> Dict[str, object]:
        """
        Compact export payload for manifest/timeline usage.
        """
        return {
            "summary": {
                "rows": self.rows,
                "cols": self.cols,
                "stabilization_seconds": self.stabilization_seconds,
                "tile_delta_change_threshold": self.tile_delta_change_threshold,
                "frame_count": len(self.frame_history),
                "revision_count": len(self.revisions),
                "tile_version_count": len(self.versions),
                "event_count": len(self.events),
                "section_count": self._section_index,
                "wipe_count": sum(1 for e in self.events if e.event_type == "wipe_detected"),
                "stable_section_count": sum(1 for e in self.events if e.event_type == "section_stable"),
                "current_section_id": self._current_section_id,
                "current_section_stable": self._current_section_stable,
                "last_mean_tile_delta": self.frame_history[-1].mean_tile_delta if self.frame_history else 0.0,
                "last_max_tile_delta": self.frame_history[-1].max_tile_delta if self.frame_history else 0.0,
            },
            "revisions": [
                {
                    "revision_id": r.revision_id,
                    "start": r.start,
                    "end": r.end,
                    "event_reason": r.event_reason,
                    "frame_count": r.frame_count,
                    "occluded_frames": r.occluded_frames,
                    "first_frame_id": r.first_frame_id,
                    "last_frame_id": r.last_frame_id,
                }
                for r in self.revisions
            ],
            "recent_frames": [
                {
                    "frame_id": f.frame_id,
                    "timestamp": f.timestamp,
                    "reason": f.reason,
                    "delta": f.delta,
                    "occluded": f.occluded,
                    "frame_path": f.frame_path,
                    "revision_id": f.revision_id,
                    "mean_tile_delta": f.mean_tile_delta,
                    "max_tile_delta": f.max_tile_delta,
                    "changed_tile_count": f.changed_tile_count,
                    "tile_deltas": f.tile_deltas,
                    "detected_events": f.detected_events,
                }
                for f in self.frame_history[-50:]
            ],
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp,
                    "frame_id": e.frame_id,
                    "revision_id": e.revision_id,
                    "details": e.details,
                }
                for e in self.events[-100:]
            ],
        }
