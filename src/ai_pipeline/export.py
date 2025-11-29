"""
Export utilities for rendering the combined lecture output.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from .align import AlignBlock


def render_markdown_document(blocks: List[AlignBlock], out_path: Path) -> Path:
    """
    Simple Markdown renderer (stub).
    """
    lines = ["# Lecture Export", ""]
    for blk in blocks:
        lines.append(f"## {blk.start:.1f}s - {blk.end:.1f}s")
        if blk.speech_text:
            lines.append("")
            lines.append("**Speech**")
            lines.append("")
            lines.append(blk.speech_text)
        if blk.board_text:
            lines.append("")
            lines.append("**Board Text**")
            lines.extend(f"- {t}" for t in blk.board_text)
        if blk.board_images:
            lines.append("")
            lines.append("**Board Images**")
            lines.extend(f"![board]({img})" for img in blk.board_images)
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def render_frames_listing(frames: List[dict], out_path: Path) -> Path:
    """
    Simple fallback renderer if no transcript: list frames with timestamps.
    """
    lines = ["# Lecture Frames", ""]
    for item in frames:
        lines.append(f"- {item.get('timestamp', 0):.2f}s: {item.get('path','')}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
