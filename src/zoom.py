"""
Zoom and pan helpers. Extend with smooth transitions or limits.
"""
import cv2
import numpy as np


def crop_zoom(frame: np.ndarray, center: tuple[int, int], scale: float) -> np.ndarray:
    """
    Crop around center with a given scale (>1 zooms in).
    """
    h, w = frame.shape[:2]
    cx, cy = center
    scale = max(scale, 1.0)  # undvik zoom ut mindre än original

    # Beräkna ny storlek på utsnittet som ska förstoras tillbaka till w x h.
    new_w = int(w / scale)
    new_h = int(h / scale)
    x1 = max(cx - new_w // 2, 0)  # vänsterkant, klippa mot bild
    y1 = max(cy - new_h // 2, 0)  # överkant, klippa mot bild
    x2 = min(x1 + new_w, w)       # högerkant, klippa mot bild
    y2 = min(y1 + new_h, h)       # nederkant, klippa mot bild

    cropped = frame[y1:y2, x1:x2]
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
