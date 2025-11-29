"""
Vision/OCR abstraction for board recognition.

Stub implementations; plug in real models later.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol


@dataclass
class BoardRecognitionResult:
    text: str
    latex: str | None
    images: List[Path]
    confidence: float | None = None


class BoardRecognizer(Protocol):
    def recognize(self, frame_path: Path) -> BoardRecognitionResult:
        ...


class DummyBoardRecognizer:
    def __init__(self, backend_name: str = "local_basic") -> None:
        self.backend_name = backend_name

    def recognize(self, frame_path: Path) -> BoardRecognitionResult:
        return BoardRecognitionResult(text="", latex=None, images=[], confidence=None)


def make_recognizer(backend_name: str = "local_basic") -> BoardRecognizer:
    return DummyBoardRecognizer(backend_name=backend_name)
