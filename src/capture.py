"""
Camera capture utilities. Add resolution or camera index settings here.
"""
import cv2


def open_camera(index: int = 0) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera at index {index}")
    return cap


def list_available_cameras(max_index: int = 5) -> list[int]:
    """Probe camera indexes from 0..max_index-1 and return the ones that open."""
    available = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available
