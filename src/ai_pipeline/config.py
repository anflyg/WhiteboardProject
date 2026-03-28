"""
Configuration profiles for AI pipeline.

Profiles:
- quick: light and fast
- recommended: default balanced profile
- full_local: heavier local/offline quality profile
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PipelineConfig:
    name: str = "recommended"
    whisper_model: str = "small"
    ocr_lang: str = "eng+sv"
    whisper_language: Optional[str] = "sv"
    vision_backend: str = "local_basic"
    use_cloud_fallback: bool = False
    ssim_threshold: float = 0.97
    fallback_interval_seconds: int = 20
    frame_delta_threshold: float = 8.0
    align_image_window_seconds: float = 5.0
    min_frame_interval_seconds: float = 3.0
    stabilization_seconds: float = 0.8
    tile_rows: int = 3
    tile_cols: int = 4
    max_parallel_ocr: int = 1
    downscale_width: Optional[int] = 1280
    export_dir: Path = Path("exports")
    capture_dir: Path = Path("captures")
    keep_intermediates: bool = False


def default_config(mode: str = "recommended") -> PipelineConfig:
    mode = mode.lower()
    if mode == "quick":
        return PipelineConfig(
            name="quick",
            whisper_model="tiny",
            vision_backend="local_basic",
            use_cloud_fallback=False,
            ssim_threshold=0.96,
            fallback_interval_seconds=30,
            frame_delta_threshold=9.0,
            min_frame_interval_seconds=4.0,
            stabilization_seconds=0.6,
            tile_rows=2,
            tile_cols=3,
            max_parallel_ocr=1,
            downscale_width=960,
        )
    if mode == "full_local" or mode == "full":
        return PipelineConfig(
            name="full_local",
            whisper_model="large",
            vision_backend="local_strong",
            use_cloud_fallback=False,
            ssim_threshold=0.985,
            fallback_interval_seconds=10,
            frame_delta_threshold=6.0,
            min_frame_interval_seconds=1.5,
            stabilization_seconds=1.0,
            tile_rows=4,
            tile_cols=5,
            max_parallel_ocr=2,
            downscale_width=None,
        )
    return PipelineConfig(
        name="recommended",
        whisper_model="small",
        vision_backend="local_basic",
        use_cloud_fallback=False,
        ssim_threshold=0.97,
        fallback_interval_seconds=20,
        frame_delta_threshold=8.0,
        min_frame_interval_seconds=3.0,
        stabilization_seconds=0.8,
        tile_rows=3,
        tile_cols=4,
        max_parallel_ocr=1,
        downscale_width=1280,
    )


def load_config(mode: Optional[str] = None) -> PipelineConfig:
    """
    Later this can read from a file/env; for now pick quick/recommended/full_local.
    """
    return default_config(mode or "recommended")
