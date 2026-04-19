"""
Stage a COLMAP-preprocessed monocular video into the directory layout the
hustvl/4DGaussians repo consumes for a real-world scene, plus a `times.txt`
file listing per-image time in seconds.

Resulting layout:

    <out>/
      images/              # undistorted RGB frames (one per video frame)
      sparse/0/            # COLMAP cameras.bin, images.bin, points3D.bin
      times.txt            # N lines, one float per image (seconds from start)
      manifest.json        # human-friendly summary

4DGaussians' dataloader can then be pointed at this directory.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Iterable, List, Sequence

LOG = logging.getLogger(__name__)

_FRAME_RE = re.compile(r"frame_(\d+)\.(?:jpg|jpeg|png)$", re.IGNORECASE)


def build_times_for_frames(n_frames: int, fps: int) -> List[float]:
    if n_frames <= 0:
        return []
    return [i / float(fps) for i in range(n_frames)]


def normalize_times(times: Sequence[float]) -> List[float]:
    if not times:
        return []
    if len(times) == 1:
        return [0.0]
    lo = min(times)
    hi = max(times)
    span = hi - lo
    if span == 0:
        return [0.0] * len(times)
    return [(t - lo) / span for t in times]


def frame_index_from_path(path: Path) -> int:
    m = _FRAME_RE.search(path.name)
    if not m:
        raise ValueError(f"Not a frame filename: {path.name}")
    return int(m.group(1))


def write_times_txt(path: Path, times: Iterable[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for t in times:
            f.write(f"{t:.6f}\n")


def stage_dataset(
    colmap_dense_dir: Path,
    fps: int,
    out_dir: Path,
) -> Path:
    """
    Arrange a `colmap_dense_dir` (from `colmap image_undistorter`) into the
    target layout. Returns the staging directory path.

    `colmap_dense_dir` is expected to contain:
        images/            # undistorted
        sparse/            # COLMAP sparse model (0 or flat)
    """
    out_dir = Path(out_dir)
    images_out = out_dir / "images"
    sparse_out = out_dir / "sparse" / "0"
    images_out.mkdir(parents=True, exist_ok=True)
    sparse_out.mkdir(parents=True, exist_ok=True)

    # Copy undistorted images
    src_images = colmap_dense_dir / "images"
    copied: List[Path] = []
    for src in sorted(src_images.iterdir()):
        if not src.is_file():
            continue
        dst = images_out / src.name
        shutil.copy2(src, dst)
        copied.append(dst)
    LOG.info("Staged %d images", len(copied))

    # Copy sparse model (images.bin, cameras.bin, points3D.bin)
    src_sparse = colmap_dense_dir / "sparse"
    # undistorter writes a flat sparse/ (not sparse/0); pick the right source
    if (src_sparse / "0").exists():
        src_sparse = src_sparse / "0"
    for name in ("cameras.bin", "images.bin", "points3D.bin"):
        src = src_sparse / name
        if src.exists():
            shutil.copy2(src, sparse_out / name)
        else:
            LOG.warning("Missing sparse file: %s", src)

    # Times
    frame_indices = [frame_index_from_path(p) for p in copied]
    frame_indices.sort()
    times = [(idx - 1) / float(fps) for idx in frame_indices]
    write_times_txt(out_dir / "times.txt", times)

    manifest = {
        "frame_count": len(copied),
        "fps": fps,
        "duration_seconds": times[-1] if times else 0.0,
        "layout": "colmap+times",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    return out_dir
