"""Bounded, logged wrapper around ``subprocess.run``.

Every external command the worker runs (ffmpeg, colmap, 4DGaussians) goes
through ``run_logged`` so that:

* A hanging process is killed by an explicit ``timeout`` instead of blocking
  the worker forever.
* stdout/stderr are captured on failure and written to the log, instead of
  disappearing into the child's inherited handles.

On success the call is otherwise transparent — it returns the same
``CompletedProcess`` ``subprocess.run`` would, and a non-zero exit still
raises ``CalledProcessError`` so existing callers don't need to change.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional, Sequence, Union

LOG = logging.getLogger(__name__)

PathLike = Union[str, Path]

_STDERR_TAIL_CHARS = 4000


def run_logged(
    cmd: Sequence[str],
    *,
    timeout: float,
    cwd: Optional[PathLike] = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` with a timeout; log and re-raise on failure.

    Always captures stdout/stderr as text so we can surface them in logs.
    """
    try:
        return subprocess.run(
            list(cmd),
            check=True,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        LOG.error(
            "command failed (exit=%s): %s\nstderr tail:\n%s",
            exc.returncode,
            " ".join(cmd),
            _tail(exc.stderr),
        )
        raise
    except subprocess.TimeoutExpired as exc:
        LOG.error(
            "command timed out after %ss: %s\nstderr tail:\n%s",
            exc.timeout,
            " ".join(cmd),
            _tail(_decode(exc.stderr)),
        )
        raise


def _tail(text: Optional[str]) -> str:
    if not text:
        return "(no stderr captured)"
    if len(text) <= _STDERR_TAIL_CHARS:
        return text
    return "…" + text[-_STDERR_TAIL_CHARS:]


def _decode(data: Union[bytes, str, None]) -> Optional[str]:
    if data is None:
        return None
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data
