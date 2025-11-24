from dataclasses import dataclass, field
import numpy as np


PAN_STEP = 20
KEYSTONE_STEP = 10

LEFT_KEYS = (81, 2424832, 65361, 63234, ord("a"))
RIGHT_KEYS = (83, 2555904, 65363, 63235, ord("d"))
UP_KEYS = (82, 2490368, 65362, 63232, ord("w"))
DOWN_KEYS = (84, 2621440, 65364, 63233, ord("s"))


def default_keystone(width: int, height: int) -> np.ndarray:
    return np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")


@dataclass
class AppState:
    width: int
    height: int
    zoom_scale: float = 1.0
    center: tuple[int, int] = (0, 0)
    keystone_src: np.ndarray | None = None
    keystone_enabled: bool = False
    selected_corner: int = 0
    collecting_points: bool = False
    mouse_points: list[tuple[int, int]] = field(default_factory=list)
    show_help: bool = True
    pan_step: int = PAN_STEP
    keystone_step: int = KEYSTONE_STEP

    def reset_keystone(self) -> None:
        self.keystone_src = default_keystone(self.width, self.height)
        self.keystone_enabled = False

    def reset_view(self) -> None:
        self.zoom_scale = 1.0
        self.center = (self.width // 2, self.height // 2)
        self.reset_keystone()
        self.collecting_points = False
        self.mouse_points.clear()

    def clamp_center(self) -> None:
        crop_w = max(1, int(self.width / self.zoom_scale))
        crop_h = max(1, int(self.height / self.zoom_scale))
        half_w = max(1, crop_w // 2)
        half_h = max(1, crop_h // 2)
        cx = max(half_w, min(self.center[0], self.width - half_w))
        cy = max(half_h, min(self.center[1], self.height - half_h))
        self.center = (cx, cy)
