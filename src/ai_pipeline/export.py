"""
Export utilities for rendering the combined lecture output.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from shutil import copy2
from typing import Any, Dict, List, Optional

from .align import AlignBlock
from .audio import TranscriptSegment

EXPORT_PACKAGE_VERSION = "v2"
MANIFEST_SCHEMA_VERSION = 2
TIMELINE_SCHEMA_VERSION = 2
PROMPT_CHATGPT_VERSION = "v1"


def render_markdown_document(blocks: List[AlignBlock], out_path: Path) -> Path:
    """
    Simple Markdown renderer (stub).
    """
    lines = ["# Lecture Export", ""]
    for blk in blocks:
        lines.append(f"## {blk.start:.1f}s - {blk.end:.1f}s")
        if blk.speech_text:
            lines.append("")
            lines.append("**Speech**")
            lines.append("")
            lines.append(blk.speech_text)
        if blk.board_text:
            lines.append("")
            lines.append("**Board Text**")
            lines.extend(f"- {t}" for t in blk.board_text)
        if blk.board_images:
            lines.append("")
            lines.append("**Board Images**")
            lines.extend(f"![board]({img})" for img in blk.board_images)
        lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def render_frames_listing(frames: List[dict], out_path: Path) -> Path:
    """
    Simple fallback renderer if no transcript: list frames with timestamps.
    """
    lines = ["# Lecture Frames", ""]
    for item in frames:
        lines.append(f"- {item.get('timestamp', 0):.2f}s: {item.get('path','')}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _timestamp_to_srt(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_transcript_txt(segments: List[TranscriptSegment], placeholder_reason: Optional[str] = None) -> tuple[str, bool]:
    if not segments:
        reason = placeholder_reason or "Transkription saknas eller är tom."
        return f"[PLACEHOLDER] {reason}\n", True
    lines: List[str] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        lines.append(text)
    if not lines:
        reason = placeholder_reason or "Transkription saknas eller är tom."
        return f"[PLACEHOLDER] {reason}\n", True
    return "\n".join(lines) + "\n", False


def _build_transcript_srt(segments: List[TranscriptSegment], placeholder_reason: Optional[str] = None) -> tuple[str, bool]:
    if not segments:
        reason = placeholder_reason or "Transkription saknas eller är tom."
        return (
            "1\n"
            "00:00:00,000 --> 00:00:01,000\n"
            f"[PLACEHOLDER] {reason}\n",
            True,
        )

    lines: List[str] = []
    idx = 1
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        start = _timestamp_to_srt(seg.start)
        end = _timestamp_to_srt(seg.end if seg.end >= seg.start else seg.start + 0.5)
        lines.extend([str(idx), f"{start} --> {end}", text, ""])
        idx += 1
    if idx == 1:
        reason = placeholder_reason or "Transkription saknas eller är tom."
        return (
            "1\n"
            "00:00:00,000 --> 00:00:01,000\n"
            f"[PLACEHOLDER] {reason}\n",
            True,
        )
    return "\n".join(lines).rstrip() + "\n", False


def _build_board_summary(blocks: List[AlignBlock], placeholder_reason: Optional[str] = None) -> tuple[str, bool]:
    if not blocks:
        reason = placeholder_reason or "Ingen tavelsammanfattning tillgänglig ännu."
        return f"# Board Summary\n\n[PLACEHOLDER] {reason}\n", True
    lines = ["# Board Summary", ""]
    for blk in blocks:
        lines.append(f"## {blk.start:.1f}s - {blk.end:.1f}s")
        if blk.speech_text:
            lines.append(blk.speech_text)
        if blk.board_text:
            lines.append("")
            lines.extend(f"- {txt}" for txt in blk.board_text)
        if blk.board_images:
            lines.append("")
            lines.extend(f"- Bild: {img}" for img in blk.board_images)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", False


def _stable_session_dir(export_root: Path, started_at: Optional[str] = None) -> Path:
    dt = datetime.now()
    if started_at:
        try:
            dt = datetime.fromisoformat(started_at)
        except Exception:
            pass
    base_name = dt.strftime("session_%Y-%m-%d_%H-%M")
    candidate = export_root / base_name
    if not candidate.exists():
        return candidate
    suffix = 1
    while True:
        candidate = export_root / f"{base_name}_{suffix:02d}"
        if not candidate.exists():
            return candidate
        suffix += 1


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _build_timeline(transcript: List[TranscriptSegment], keyframes: List[Dict[str, Any]]) -> Dict[str, Any]:
    transcript_entries: List[Dict[str, Any]] = []
    for idx, seg in enumerate(transcript, start=1):
        start = _to_float(getattr(seg, "start", 0.0), 0.0)
        end = _to_float(getattr(seg, "end", start), start)
        if end < start:
            end = start
        text = (getattr(seg, "text", "") or "").strip()
        segment_id = f"seg_{idx:04d}"
        linked_keyframes = [
            kf.get("frame_id")
            for kf in keyframes
            if _to_float(kf.get("timestamp"), 0.0) >= (start - 5.0)
            and _to_float(kf.get("timestamp"), 0.0) <= (end + 5.0)
            and kf.get("frame_id")
        ]
        transcript_entries.append(
            {
                "segment_id": segment_id,
                "start": start,
                "end": end,
                "text": text,
                "linked_keyframe_ids": linked_keyframes,
            }
        )

    events: List[Dict[str, Any]] = []
    for kf in keyframes:
        events.append(
            {
                "event_id": f"evt_{len(events)+1:04d}",
                "type": "keyframe",
                "timestamp": _to_float(kf.get("timestamp"), 0.0),
                "ref_id": kf.get("frame_id"),
            }
        )
    for seg in transcript_entries:
        events.append(
            {
                "event_id": f"evt_{len(events)+1:04d}",
                "type": "transcript_segment",
                "timestamp": _to_float(seg.get("start"), 0.0),
                "ref_id": seg.get("segment_id"),
            }
        )
    events.sort(key=lambda e: (e.get("timestamp", 0), e.get("type", "")))

    return {
        "schema_version": TIMELINE_SCHEMA_VERSION,
        "transcript_segments": transcript_entries,
        "keyframes": keyframes,
        "events": events,
        # Reserved for future OCR/math/LLM layer outputs.
        "analysis_tracks": [],
    }


def _build_chatgpt_prompt(
    *,
    session_name: str,
    transcript_placeholder: bool,
    board_placeholder: bool,
    keyframe_count: int,
) -> str:
    material_status = [
        f"- `transcript_sv.txt` ({'placeholder' if transcript_placeholder else 'innehåll finns'})",
        "- `transcript_sv.srt` (tidskodad transkription eller placeholder)",
        f"- `board_summary.md` ({'placeholder' if board_placeholder else 'innehåll finns'})",
        "- `timeline.json` (maskinläsbar tidslinje)",
        f"- `keyframes/` ({keyframe_count} bild(er))",
        "- `manifest.json` (metadata och placeholders)",
    ]
    return (
        f"Promptversion: {PROMPT_CHATGPT_VERSION}\n"
        f"Session: {session_name}\n\n"
        "Du får ett underlag från en föreläsningssession. Läs allt material innan du svarar.\n\n"
        "Material som bifogas:\n"
        + "\n".join(material_status)
        + "\n\n"
        "Instruktioner:\n"
        "1. Läs transkription och whiteboardbilder tillsammans och sammanfoga informationen.\n"
        "2. Återskapa innehållet pedagogiskt och strukturerat, med tydliga rubriker.\n"
        "3. Markera osäkerheter tydligt med rubriken 'Osäkert/ej verifierat'.\n"
        "4. Hitta inte på information som inte stöds av underlaget.\n"
        "5. Om underlag saknas eller är markerat som placeholder, säg det uttryckligen.\n"
        "6. Leverera både:\n"
        "   - En kort sammanfattning (5-10 punkter)\n"
        "   - En längre sammanfattning med förklaringar\n"
        "7. Lyft centrala begrepp, resonemang och eventuella formler.\n"
        "8. Skriv på tydlig svenska.\n"
    )


def export_session_package(
    export_root: Path,
    *,
    source_session_dir: Optional[Path],
    session_manifest: Dict[str, Any],
    transcript: List[TranscriptSegment],
    align_blocks: List[AlignBlock],
    transcript_error: Optional[str] = None,
) -> Path:
    """
    Export a stable ChatGPT-ready session package with predictable structure.
    Always creates required files, using placeholders when data is missing.
    """
    session_manifest = session_manifest or {}
    export_root.mkdir(parents=True, exist_ok=True)
    session_dir = _stable_session_dir(export_root, started_at=session_manifest.get("started_at"))
    keyframes_dir = session_dir / "keyframes"
    keyframes_dir.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []
    timeline_keyframes: List[Dict[str, Any]] = []
    for idx, frame in enumerate(session_manifest.get("frames", []) or [], start=1):
        frame = frame or {}
        src_path = None
        rel = frame.get("path", "")
        if rel and source_session_dir:
            candidate = source_session_dir / rel
            src_path = candidate if candidate.exists() else None
        target_name = Path(rel).name if rel else f"frame-{frame.get('timestamp', 0):.2f}.jpg"
        dst_path = keyframes_dir / target_name
        copied = False
        if src_path:
            try:
                copy2(src_path, dst_path)
                copied = True
            except Exception as exc:
                copied = False
                warnings.append(f"Kunde inte kopiera keyframe '{rel}': {exc}")
        timeline_keyframes.append(
            {
                "frame_id": f"kf_{idx:04d}",
                "timestamp": _to_float(frame.get("timestamp", 0), 0.0),
                "path": f"keyframes/{target_name}",
                "reason": frame.get("reason", ""),
                "delta": _to_float(frame.get("delta", 0), 0.0),
                "occluded": bool(frame.get("occluded", False)),
                "copied": copied,
            }
        )

    txt_content, txt_placeholder = _build_transcript_txt(transcript, placeholder_reason=transcript_error)
    srt_content, srt_placeholder = _build_transcript_srt(transcript, placeholder_reason=transcript_error)
    board_content, board_placeholder = _build_board_summary(align_blocks)
    prompt_content = _build_chatgpt_prompt(
        session_name=session_dir.name,
        transcript_placeholder=txt_placeholder,
        board_placeholder=board_placeholder,
        keyframe_count=len(timeline_keyframes),
    )

    (session_dir / "transcript_sv.txt").write_text(txt_content, encoding="utf-8")
    (session_dir / "transcript_sv.srt").write_text(srt_content, encoding="utf-8")
    (session_dir / "board_summary.md").write_text(board_content, encoding="utf-8")
    (session_dir / "prompt_chatgpt.txt").write_text(prompt_content, encoding="utf-8")

    timeline = _build_timeline(transcript, timeline_keyframes)
    timeline["session"] = session_dir.name
    timeline["generated_at"] = datetime.now().isoformat()
    timeline["profile"] = session_manifest.get("profile")
    timeline["transcription"] = {
        "backend": session_manifest.get("transcription_backend"),
        "model": session_manifest.get("whisper_model"),
        "language": session_manifest.get("transcription_language"),
    }
    (session_dir / "timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "export_version": EXPORT_PACKAGE_VERSION,
        "session_name": session_dir.name,
        "exported_at": datetime.now().isoformat(),
        "source_run_id": session_manifest.get("run_id"),
        "source_capture_dir": session_manifest.get("capture_dir"),
        "source_started_at": session_manifest.get("started_at"),
        "source_ended_at": session_manifest.get("ended_at"),
        "profile": session_manifest.get("profile"),
        "transcription_backend": session_manifest.get("transcription_backend"),
        "transcription_model": session_manifest.get("whisper_model"),
        "transcription_language": session_manifest.get("transcription_language"),
        "keyframe_count": len(timeline_keyframes),
        "transcript_segment_count": len(timeline.get("transcript_segments", [])),
        "timeline_schema_version": TIMELINE_SCHEMA_VERSION,
        "board_state": session_manifest.get("board_state", {}),
        "files": {
            "transcript_sv.txt": "transcript_sv.txt",
            "transcript_sv.srt": "transcript_sv.srt",
            "board_summary.md": "board_summary.md",
            "prompt_chatgpt.txt": "prompt_chatgpt.txt",
            "manifest.json": "manifest.json",
            "timeline.json": "timeline.json",
            "keyframes": "keyframes/",
        },
        "prompt_template_version": PROMPT_CHATGPT_VERSION,
        "placeholders": {
            "transcript_sv.txt": txt_placeholder,
            "transcript_sv.srt": srt_placeholder,
            "board_summary.md": board_placeholder,
        },
        "warnings": warnings,
    }
    (session_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return session_dir
