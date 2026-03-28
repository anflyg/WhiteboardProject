"""
Tile-based board state tracking.

First practical version for tracking board state over time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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


class BoardState:
    def __init__(
        self,
        rows: int = 3,
        cols: int = 4,
        stabilization_seconds: float = 0.8,
    ) -> None:
        self.rows = rows
        self.cols = cols
        self.stabilization_seconds = stabilization_seconds
        self.versions: List[TileVersion] = []
        self.frame_history: List[BoardFrameState] = []
        self.revisions: List[BoardRevision] = []
        self._last_change_ts: Dict[Tuple[int, int], float] = {}
        self._frame_index = 0
        self._revision_index = 0
        self._open_revision_id: Optional[str] = None
        self._open_tile_version: Optional[TileVersion] = None

    def update_frame(
        self,
        timestamp: float,
        frame_path: Optional[str] = None,
        reason: str = "",
        delta: float = 0.0,
        occluded: bool = False,
    ) -> BoardFrameState:
        """
        Register a keyframe/frame-event in the board timeline.
        This is intentionally simple but real and used in runtime code path.
        """
        self._frame_index += 1
        frame_id = f"bf_{self._frame_index:05d}"
        reason_key = (reason or "unknown").split(":", 1)[0]

        if self._open_revision_id is None:
            self._start_revision(timestamp, reason_key, frame_id, frame_path)
        elif not occluded and self._should_start_new_revision(reason_key):
            self._close_current_revision(timestamp)
            self._start_revision(timestamp, reason_key, frame_id, frame_path)

        revision = self.revisions[-1]
        revision.last_frame_id = frame_id
        revision.frame_count += 1
        if occluded:
            revision.occluded_frames += 1

        frame = BoardFrameState(
            frame_id=frame_id,
            timestamp=float(timestamp),
            reason=reason or "",
            delta=float(delta),
            occluded=bool(occluded),
            frame_path=frame_path,
            revision_id=revision.revision_id,
        )
        self.frame_history.append(frame)
        return frame

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
                "frame_count": len(self.frame_history),
                "revision_count": len(self.revisions),
                "tile_version_count": len(self.versions),
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
                }
                for f in self.frame_history[-50:]
            ],
        }
