"""
Perspective correction helpers (keystone/deskew).
"""
import cv2
import numpy as np


def fit_rect_with_aspect(w: int, h: int, aspect: float) -> np.ndarray:
    """
    Fit a rectangle with a given aspect into w x h without changing the aspect.
    Returns four points TL, TR, BR, BL in float32.
    """
    frame_aspect = w / h
    if frame_aspect >= aspect:
        dst_h = h
        dst_w = int(h * aspect)
    else:
        dst_w = w
        dst_h = int(w / aspect)
    ox = (w - dst_w) // 2
    oy = (h - dst_h) // 2
    return np.array(
        [
            [ox, oy],
            [ox + dst_w - 1, oy],
            [ox + dst_w - 1, oy + dst_h - 1],
            [ox, oy + dst_h - 1],
        ],
        dtype="float32",
    )


def quad_aspect(src_pts: np.ndarray) -> float:
    """
    Approximate aspect ratio of a quad by averaging top/bottom width and left/right height.
    """
    top = np.linalg.norm(src_pts[1] - src_pts[0])
    bottom = np.linalg.norm(src_pts[2] - src_pts[3])
    left = np.linalg.norm(src_pts[3] - src_pts[0])
    right = np.linalg.norm(src_pts[2] - src_pts[1])
    mean_w = max(1e-6, (top + bottom) / 2.0)
    mean_h = max(1e-6, (left + right) / 2.0)
    return mean_w / mean_h


def reorder_quad(pts: list[tuple[int, int]]) -> np.ndarray:
    """
    Take four points in any order and return TL, TR, BR, BL.
    Uses sums/differences to robustly find corners.
    """
    if len(pts) != 4:
        raise ValueError("Need 4 points to reorder")
    pts_np = np.array(pts, dtype="float32")
    s = pts_np.sum(axis=1)
    diff = np.diff(pts_np, axis=1).flatten()
    tl = pts_np[np.argmin(s)]
    br = pts_np[np.argmax(s)]
    tr = pts_np[np.argmin(diff)]
    bl = pts_np[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype="float32")


def apply_keystone(
    frame: np.ndarray,
    src_pts: np.ndarray | None,
    enabled: bool,
    dst_size: tuple[int, int],
) -> np.ndarray:
    """
    Apply keystone if enabled; otherwise return the frame unchanged.
    """
    if not enabled or src_pts is None:
        return frame
    width, height = dst_size
    aspect = quad_aspect(src_pts)
    dst_pts = fit_rect_with_aspect(width, height, aspect)
    return warp_perspective(frame, src_pts, (width, height), dst_pts)


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
