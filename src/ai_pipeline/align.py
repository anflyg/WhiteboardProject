"""
Alignment between transcript segments and board content over time.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .audio import TranscriptSegment
from .board_state import TileVersion


@dataclass
class AlignBlock:
    start: float
    end: float
    speech_text: str
    board_text: List[str]
    board_images: List[str]


def align_transcript_with_board(
    transcript: List[TranscriptSegment],
    tiles: List[TileVersion],
) -> List[AlignBlock]:
    """
    Very simple placeholder alignment: pair transcript segments with any tile versions overlapping in time.
    """
    blocks: List[AlignBlock] = []
    for seg in transcript:
        related_text = []
        related_imgs = []
        for tile in tiles:
            if tile.start <= seg.end and (tile.end is None or tile.end >= seg.start):
                if tile.text:
                    related_text.append(tile.text)
                if tile.image_path:
                    related_imgs.append(tile.image_path)
        blocks.append(
            AlignBlock(
                start=seg.start,
                end=seg.end,
                speech_text=seg.text,
                board_text=related_text,
                board_images=related_imgs,
            )
        )
    return blocks
