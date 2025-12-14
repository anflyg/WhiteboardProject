"""
Vision/OCR abstraction for board recognition.

Basic implementation using pytesseract + enkla heuristiker för att skilja text från ritningar.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, Optional

import cv2


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


class BasicBoardRecognizer:
    """
    Minimal lokal OCR/detektion:
    - pytesseract för att fånga text
    - enkelt kantmått för att markera ritningar (om ingen text hittas)
    """

    def __init__(self, lang: Optional[str] = None, edge_threshold: int = 1200) -> None:
        self.lang = lang or "eng+sv"
        self.edge_threshold = edge_threshold
        try:
            import pytesseract  # noqa: F401

            self._tesseract_available = True
        except Exception:
            self._tesseract_available = False

    def recognize(self, frame_path: Path) -> BoardRecognitionResult:
        text = ""
        images: List[Path] = []
        try:
            import pytesseract

            img = cv2.imread(str(frame_path))
            if img is None:
                return BoardRecognitionResult(text="", latex=None, images=[])
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            try:
                text = pytesseract.image_to_string(gray, lang=self.lang).strip()
            except Exception:
                text = ""

            edges = cv2.Canny(gray, 50, 150)
            edge_count = int((edges > 0).sum())
            if not text:
                if edge_count >= self.edge_threshold:
                    images.append(frame_path)
                else:
                    # Även om det är svagt, spara som bild så inget tappas bort.
                    images.append(frame_path)
        except Exception:
            return BoardRecognitionResult(text="", latex=None, images=[])

        return BoardRecognitionResult(text=text, latex=None, images=images)


def make_recognizer(backend_name: str = "local_basic", lang: Optional[str] = None) -> BoardRecognizer:
    if backend_name == "local_basic":
        try:
            return BasicBoardRecognizer(lang=lang)
        except Exception:
            return DummyBoardRecognizer(backend_name=backend_name)
    return DummyBoardRecognizer(backend_name=backend_name)
