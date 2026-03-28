"""
AI pipeline package: audio, frames, vision, align, export.

This is scaffold code only; real model backends are plugged in later.
"""

from .audio import TranscriptSegment, Transcriber, make_transcriber, AudioRecorder, WhisperTranscriber
from .frames import FrameEvent, FrameExtractor
from .board_state import TileVersion, BoardState
from .vision import BoardRecognizer, BoardRecognitionResult, make_recognizer, BasicBoardRecognizer, DummyBoardRecognizer
from .align import AlignBlock, align_transcript_with_board
from .export import render_markdown_document, render_frames_listing, export_session_package
from .config import PipelineConfig, load_config, default_config

__all__ = [
    "TranscriptSegment",
    "Transcriber",
    "make_transcriber",
    "AudioRecorder",
    "WhisperTranscriber",
    "FrameEvent",
    "FrameExtractor",
    "TileVersion",
    "BoardState",
    "BoardRecognizer",
    "BoardRecognitionResult",
    "make_recognizer",
    "BasicBoardRecognizer",
    "DummyBoardRecognizer",
    "AlignBlock",
    "align_transcript_with_board",
    "render_markdown_document",
    "render_frames_listing",
    "export_session_package",
    "PipelineConfig",
    "load_config",
    "default_config",
]
