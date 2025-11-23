"""
Camera capture utilities. Add resolution or camera index settings here.
"""
import cv2


def open_camera(index: int = 0) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera at index {index}")
    return cap
