"""
Export the trained 4DGaussians result as a sequence of .splat files plus a
manifest.json the web viewer can consume.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from echoes.converters.ply_to_splat import convert_ply_file_to_splat

LOG = logging.getLogger(__name__)

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "manifest.json"

# A pair of (path-or-url, time_seconds)
Entry = Tuple[str, float]


def pair_plys_with_times(
    plys: Sequence[Path], times: Sequence[float]
) -> List[Tuple[Path, float]]:
    n = len(plys)
    if n == 0:
        return []
    if n == 1:
        return [(plys[0], times[0] if times else 0.0)]

    if len(times) == n:
        return [(plys[i], times[i]) for i in range(n)]

    if len(times) < 2:
        # Default linear spread over [0, n-1] seconds
        return [(plys[i], float(i)) for i in range(n)]

    lo, hi = times[0], times[-1]
    span = hi - lo
    # n > 1, so (n-1) is safe
    return [(plys[i], lo + span * (i / (n - 1))) for i in range(n)]


def build_manifest_dict(
    entries: Sequence[Entry], duration_seconds: float
) -> dict:
    return {
        "version": MANIFEST_VERSION,
        "durationSeconds": duration_seconds,
        "frames": [
            {"url": url, "timeSeconds": float(t)} for url, t in entries
        ],
    }


def write_manifest_file(
    path: Path,
    entries: Sequence[Entry],
    duration_seconds: float,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_manifest_dict(entries, duration_seconds)
    path.write_text(json.dumps(data, indent=2))
    return path


def convert_plys_to_splats(
    plys: Iterable[Path], out_dir: Path
) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths: List[Path] = []
    for i, ply in enumerate(plys):
        splat = out_dir / f"frame_{i:05d}.splat"
        convert_ply_file_to_splat(ply, splat)
        out_paths.append(splat)
    LOG.info("Converted %d PLY frames to .splat", len(out_paths))
    return out_paths
