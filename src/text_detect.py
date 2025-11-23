"""
Text detection/OCR helpers. Use pytesseract/easyocr to locate text regions.
"""
from typing import List, Tuple

import cv2
import numpy as np
import pytesseract


def detect_text_boxes(frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    Returns bounding boxes (x, y, w, h) for detected text.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    boxes: List[Tuple[int, int, int, int]] = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if text:
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            boxes.append((x, y, w, h))
    return boxes
