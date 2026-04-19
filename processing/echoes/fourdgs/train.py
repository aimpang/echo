"""
Wrappers around the hustvl/4DGaussians train.py / render.py scripts.

We shell out to the vendored 4DGaussians repo. The exact CLI differs slightly
between upstream branches, so `build_train_cmd` and `build_render_cmd` are
deliberately thin — update the extra args through the pipeline config if
upstream moves.
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from echoes._subprocess import run_logged

LOG = logging.getLogger(__name__)

# Long-running ML jobs — training can genuinely take hours on a busy GPU;
# the cap just prevents a silently-hung run from pinning the worker forever.
TRAIN_TIMEOUT_SECONDS = 6 * 60 * 60
RENDER_TIMEOUT_SECONDS = 60 * 60


def build_train_cmd(
    repo_dir: Path,
    data_dir: Path,
    model_dir: Path,
    config_file: Path,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    cmd = [
        "python",
        str(repo_dir / "train.py"),
        "-s",
        str(data_dir),
        "--model_path",
        str(model_dir),
        "--configs",
        str(config_file),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def build_render_cmd(
    repo_dir: Path,
    model_dir: Path,
    config_file: Path,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    cmd = [
        "python",
        str(repo_dir / "render.py"),
        "--model_path",
        str(model_dir),
        "--configs",
        str(config_file),
        "--skip_test",
        "--skip_video",
    ]
    if extra_args:
        cmd.extend(extra_args)
    return cmd


class StageTimer:
    """Minimal stopwatch that records elapsed time per named stage."""

    def __init__(self) -> None:
        self._elapsed: Dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self._elapsed[name] = time.perf_counter() - start

    def report(self) -> Dict[str, float]:
        return dict(self._elapsed)


_PLY_NUM_RE = re.compile(r"(\d+)")


def find_rendered_plys(model_dir: Path) -> List[Path]:
    """Return per-timestep PLYs produced by 4DGaussians, sorted numerically."""
    candidates: List[Path] = []
    for p in model_dir.rglob("*.ply"):
        candidates.append(p)

    def numeric_key(path: Path) -> tuple:
        m = _PLY_NUM_RE.findall(path.stem)
        return tuple(int(x) for x in m) if m else (0,)

    candidates.sort(key=lambda p: (numeric_key(p), p.as_posix()))
    return candidates


def run_train(
    repo_dir: Path,
    data_dir: Path,
    model_dir: Path,
    config_file: Path,
    extra_args: Optional[List[str]] = None,
) -> None:
    cmd = build_train_cmd(repo_dir, data_dir, model_dir, config_file, extra_args)
    LOG.info("train: %s", " ".join(cmd))
    run_logged(cmd, timeout=TRAIN_TIMEOUT_SECONDS, cwd=repo_dir)


def run_render(
    repo_dir: Path,
    model_dir: Path,
    config_file: Path,
    extra_args: Optional[List[str]] = None,
) -> None:
    cmd = build_render_cmd(repo_dir, model_dir, config_file, extra_args)
    LOG.info("render: %s", " ".join(cmd))
    run_logged(cmd, timeout=RENDER_TIMEOUT_SECONDS, cwd=repo_dir)
