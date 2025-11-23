"""
Perspective correction helpers (keystone/deskew).
"""
import cv2
import numpy as np


def warp_perspective(
    frame: np.ndarray,
    src_pts: np.ndarray,
    dst_size: tuple[int, int],
    dst_pts: np.ndarray | None = None,
) -> np.ndarray:
    """
    Apply perspective transform using four source points (clockwise).
    Optionally provide dst_pts (4x2) to map till en mindre rektangel
    i ett större canvas.
    """
    if src_pts.shape != (4, 2):
        raise ValueError("src_pts must be shape (4, 2)")

    width, height = dst_size
    if dst_pts is None:
        dst_pts = np.array(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
            dtype="float32",
        )
    matrix = cv2.getPerspectiveTransform(src_pts.astype("float32"), dst_pts.astype("float32"))
    return cv2.warpPerspective(frame, matrix, (width, height))
