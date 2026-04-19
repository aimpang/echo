"""
Pure helpers used by the echoes_pipeline worker.

These functions hold *decisions* (what content type to upload as, what fields
to write on failure, whether a cached download can be reused) that would
otherwise be inlined into large orchestration functions. Extracting them
keeps the side-effectful worker code small and the decisions unit-testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

MAX_ERROR_TEXT_LEN = 500


def content_type_for_upload(path: Path) -> str:
    """MIME type for a file being uploaded to the `splats` bucket."""
    if path.suffix.lower() == ".json":
        return "application/json"
    return "application/octet-stream"


def build_splat_storage_prefix(user_id: str, memory_id: str) -> str:
    """`<user_id>/<memory_id>` — the per-memory directory in the splats bucket."""
    if not user_id:
        raise ValueError("user_id must not be empty")
    if not memory_id:
        raise ValueError("memory_id must not be empty")
    return f"{user_id}/{memory_id}"


def should_download_video(video_path: Path) -> bool:
    """True if we need to (re-)fetch the source video from storage.

    A zero-byte file left over from an earlier crash is treated as missing —
    the worker will overwrite it rather than ship a broken pipeline run.
    """
    if not video_path.exists():
        return True
    return video_path.stat().st_size == 0


def build_failure_update(error: BaseException) -> Dict[str, Any]:
    """Row fields to write when a processing job crashes."""
    message = str(error)
    if len(message) > MAX_ERROR_TEXT_LEN:
        message = message[: MAX_ERROR_TEXT_LEN - 1] + "…"
    return {
        "status": "processing_failed",
        "safety_flag": message,
    }


def job_log_prefix(memory_id: str, stage: str) -> str:
    """Consistent prefix for every log line inside a worker stage."""
    return f"[memory={memory_id} stage={stage}]"


def delete_local_video(video_path: Path) -> bool:
    """Delete the staged source video from disk if it's still there.

    Idempotent: returns True if a file was removed, False if the path was
    already missing (file, parent dir, anything). Never raises on a
    missing path — the retention policy runs cleanup unconditionally and
    a crashed-then-resumed job may have already been cleaned.
    """
    try:
        if not video_path.exists():
            return False
        video_path.unlink(missing_ok=True)
        return True
    except FileNotFoundError:
        return False
