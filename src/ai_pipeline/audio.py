"""
Audio handling: recording and transcription.

Recorder prefers sounddevice, then PyAudio; otherwise writes an empty wav.
Transcriber prefers Whisper if installed; otherwise returns an empty transcript.
"""
from __future__ import annotations

import os
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Protocol


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> List[TranscriptSegment]:
        ...


class DummyTranscriber:
    """Placeholder that returns an empty transcript."""

    def __init__(self, model_name: str = "medium", language: Optional[str] = None, error: Optional[str] = None) -> None:
        self.model_name = model_name
        self.language = language
        self.error = error

    def transcribe(self, audio_path: Path) -> List[TranscriptSegment]:
        return []


class WhisperTranscriber:
    """Whisper-based transcriber if the whisper package is available."""

    def __init__(self, model_name: str = "medium", language: Optional[str] = None) -> None:
        import whisper  # type: ignore

        self.model = whisper.load_model(model_name)
        self.language = language

    def transcribe(self, audio_path: Path) -> List[TranscriptSegment]:
        kwargs = {"task": "transcribe"}
        if self.language:
            kwargs["language"] = self.language
        result = self.model.transcribe(str(audio_path), **kwargs)
        segments: List[TranscriptSegment] = []
        for seg in result.get("segments", []):
            segments.append(
                TranscriptSegment(start=float(seg.get("start", 0.0)), end=float(seg.get("end", 0.0)), text=seg.get("text", "").strip())
            )
        return segments


def _whisper_model_candidates(model_name: str) -> List[Path]:
    """
    Build a prioritized list of possible local model paths before falling back to download.
    """
    names = [f"{model_name}.pt", f"{model_name}.pt.bin"]
    candidates: List[Path] = []

    env_path = os.getenv("WHISPER_MODEL_PATH")
    if env_path:
        p = Path(env_path).expanduser()
        if p.is_dir():
            for name in names:
                candidates.append(p / name)
        else:
            candidates.append(p)

    env_dir = os.getenv("WHISPER_MODEL_DIR")
    if env_dir:
        d = Path(env_dir).expanduser()
        for name in names:
            candidates.append(d / name)

    project_root = Path(__file__).resolve().parents[2]
    search_roots = [project_root, Path.cwd(), project_root.parent]
    for root in search_roots:
        base = root / "whisper_models"
        for name in names:
            candidates.append(base / name)

    unique: List[Path] = []
    seen = set()
    for c in candidates:
        if c not in seen:
            unique.append(c)
            seen.add(c)
    return unique


def _resolve_model_target(model_name: str) -> tuple[str, List[Path]]:
    candidates = _whisper_model_candidates(model_name)
    for path in candidates:
        if path.is_file():
            return str(path), candidates
    return model_name, candidates


def make_transcriber(model_name: str = "medium", language: Optional[str] = None) -> Transcriber:
    model_target, candidates = _resolve_model_target(model_name)
    try:
        import whisper  # noqa: F401

        return WhisperTranscriber(model_name=model_target, language=language)
    except Exception as exc:
        tried = [str(p) for p in candidates]
        hint = ""
        if tried:
            hint = "; searched for local model at: " + ", ".join(tried)
        advice = "Set WHISPER_MODEL_PATH to your downloaded .pt file or place it under whisper_models/."
        return DummyTranscriber(model_name=model_name, language=language, error=f"{exc}{hint} {advice}")


class AudioRecorder:
    """
    Simple audio recorder. Tries sounddevice, then PyAudio; falls back to an empty wav.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, chunk: int = 1024) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk = chunk
        self._backend = None
        self._stream = None
        self._wav: Optional[wave.Wave_write] = None
        self._path: Optional[Path] = None
        self._active_backend_name: str = "none"

        try:
            import sounddevice  # type: ignore

            self._backend = ("sounddevice", sounddevice)
        except ImportError:
            try:
                import pyaudio  # type: ignore

                self._backend = ("pyaudio", pyaudio.PyAudio())
            except ImportError:
                self._backend = None

    @property
    def backend_available(self) -> bool:
        return self._backend is not None

    @property
    def backend_name(self) -> str:
        return self._active_backend_name

    def start(self, path: Path) -> bool:
        """
        Start recording to the given path. Returns True if audio will be captured, False if fallback.
        """
        self._path = path
        if self._backend is None:
            self._create_empty_wav(path)
            self._active_backend_name = "none"
            return False

        try:
            self._wav = wave.open(str(path), "wb")
            self._wav.setnchannels(self.channels)
            self._wav.setsampwidth(2)  # 16-bit
            self._wav.setframerate(self.sample_rate)

            name, backend = self._backend
            if name == "sounddevice":
                import numpy as np  # type: ignore

                def callback(indata, frames, time_info, status):
                    if self._wav:
                        try:
                            self._wav.writeframes(indata.astype(np.int16).tobytes())
                        except Exception:
                            pass

                self._stream = backend.InputStream(
                    channels=self.channels,
                    samplerate=self.sample_rate,
                    blocksize=self.chunk,
                    dtype="int16",
                    callback=callback,
                )
                self._stream.start()
            elif name == "pyaudio":
                p = backend
                fmt = p.get_format_from_width(2)
                self._stream = p.open(
                    format=fmt,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.chunk,
                    stream_callback=self._on_audio,
                )
                self._stream.start_stream()
            self._active_backend_name = name
            return True
        except Exception:
            self._cleanup()
            self._create_empty_wav(path)
            self._active_backend_name = "none"
            return False

    def stop(self) -> None:
        if self._stream is not None:
            try:
                # sounddevice streams have .stop(), PyAudio streams have stop_stream()
                if hasattr(self._stream, "stop"):
                    self._stream.stop()
                if hasattr(self._stream, "stop_stream"):
                    self._stream.stop_stream()
                if hasattr(self._stream, "close"):
                    self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._wav is not None:
            try:
                self._wav.close()
            except Exception:
                pass
            self._wav = None
        self._cleanup()

    def _on_audio(self, in_data, frame_count, time_info, status_flags):
        if self._wav:
            try:
                self._wav.writeframes(in_data)
            except Exception:
                pass
        return (None, 0)

    def _create_empty_wav(self, path: Path) -> None:
        try:
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(self.channels)
                wav.setsampwidth(2)
                wav.setframerate(self.sample_rate)
                wav.writeframes(b"")
        except Exception:
            pass

    def _cleanup(self) -> None:
        if self._backend:
            name, backend = self._backend
            if name == "pyaudio":
                try:
                    backend.terminate()
                except Exception:
                    pass
        self._backend = None


def chunks_from_stream(audio_iter: Iterable[bytes]) -> Iterable[bytes]:
    """
    Placeholder for future streaming/chunked transcription if needed.
    """
    yield from audio_iter
