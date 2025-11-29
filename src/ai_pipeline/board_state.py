"""
Tile-based board state tracking.

Stub for detecting changes, stabilization, and wipe events.
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
        self._last_change_ts: Dict[Tuple[int, int], float] = {}

    def update_frame(self, timestamp: float) -> List[TileVersion]:
        """
        Placeholder: decide if tiles changed and return new versions when stable.
        Currently returns empty list.
        """
        return []

    def close_versions(self, timestamp: float) -> None:
        """
        Close any open versions at the end of processing.
        """
        for v in self.versions:
            if v.end is None:
                v.end = timestamp
