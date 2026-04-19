"""
Preflight checks for the 4DGaussians processing worker.

Run-before-you-go validation: confirms system binaries (ffmpeg, colmap) are on
PATH, the hustvl/4DGaussians repo is cloned, and the configured 4DGaussians
config file exists. Returns a list of human-readable issues so the worker can
refuse to start and print a clear checklist instead of failing 20 minutes into
a pipeline run.

The pure helpers here accept their system probe (`which`) and environment
dict as arguments so they're cheap to unit-test.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, List, Mapping, Sequence

REQUIRED_BINARIES: Sequence[str] = ("ffmpeg", "colmap")
REQUIRED_ENV_VARS: Sequence[str] = ("FOURDGS_REPO_DIR", "FOURDGS_CONFIG")


def check_preflight(
    *,
    env: Mapping[str, str],
    which: Callable[[str], str | None] = shutil.which,
) -> List[str]:
    """Return a list of human-readable issues. Empty list means ready to run."""
    issues: List[str] = []

    for name in REQUIRED_BINARIES:
        if not which(name):
            issues.append(
                f"Missing binary on PATH: `{name}` — install it and try again."
            )

    for var in REQUIRED_ENV_VARS:
        if not env.get(var):
            issues.append(f"Environment variable `{var}` is not set.")

    repo_dir = env.get("FOURDGS_REPO_DIR")
    if repo_dir and not Path(repo_dir).exists():
        issues.append(
            f"FOURDGS_REPO_DIR does not exist on disk: {repo_dir}. "
            "Clone hustvl/4DGaussians there."
        )

    config = env.get("FOURDGS_CONFIG")
    if config and not Path(config).exists():
        issues.append(
            f"FOURDGS_CONFIG does not exist on disk: {config}. "
            "Point it at a .py config inside the 4DGaussians repo."
        )

    return issues


def format_preflight_report(issues: Sequence[str]) -> str:
    if not issues:
        return "Preflight: ready. All required binaries, env vars, and paths are present."
    lines = ["Preflight: NOT READY. Fix the issues below before starting the worker:"]
    for i, issue in enumerate(issues, 1):
        lines.append(f"  {i}. {issue}")
    lines.append("")
    lines.append("Run `python setup_4dgaussians.py` to auto-install the 4DGaussians repo.")
    return "\n".join(lines)


def build_4dgaussians_clone_cmd(target_dir: Path | str) -> List[str]:
    """Command to clone hustvl/4DGaussians with its submodules."""
    return [
        "git",
        "clone",
        "--recurse-submodules",
        "https://github.com/hustvl/4DGaussians",
        str(target_dir),
    ]
