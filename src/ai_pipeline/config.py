"""
Configuration profiles for AI pipeline.

Quick mode targets laptops without strong GPU.
Full mode is for offline, higher-quality processing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PipelineConfig:
    name: str = "quick"
    whisper_model: str = "small"
    vision_backend: str = "local_basic"
    use_cloud_fallback: bool = False
    ssim_threshold: float = 0.97
    fallback_interval_seconds: int = 10
    stabilization_seconds: float = 0.8
    tile_rows: int = 3
    tile_cols: int = 4
    max_parallel_ocr: int = 1
    downscale_width: Optional[int] = 1280
    export_dir: Path = Path("exports")
    capture_dir: Path = Path("captures")
    keep_intermediates: bool = False


def default_config(mode: str = "quick") -> PipelineConfig:
    mode = mode.lower()
    if mode == "full":
        return PipelineConfig(
            name="full",
            whisper_model="large",
            vision_backend="local_strong",
            use_cloud_fallback=False,
            ssim_threshold=0.98,
            fallback_interval_seconds=20,
            stabilization_seconds=1.0,
            tile_rows=4,
            tile_cols=5,
            max_parallel_ocr=2,
            downscale_width=None,
        )
    return PipelineConfig()


def load_config(mode: Optional[str] = None) -> PipelineConfig:
    """
    Later this can read from a file/env; for now pick quick/full.
    """
    return default_config(mode or "quick")
