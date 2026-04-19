"""
Frame extraction + COLMAP preprocessing.

Pure command builders are tested directly; the runner functions shell out to
ffmpeg / colmap and are smoke-tested during pipeline runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

from echoes._subprocess import run_logged

LOG = logging.getLogger(__name__)

# Wall-clock caps — a healthy run finishes well below these; they exist to
# stop a stuck ffmpeg/colmap binary from blocking the whole worker forever.
FFMPEG_EXTRACT_TIMEOUT_SECONDS = 10 * 60
COLMAP_STAGE_TIMEOUT_SECONDS = 30 * 60

PathLike = Union[str, Path]


def frame_time_seconds(frame_index: int, fps: int) -> float:
    if frame_index < 1:
        raise ValueError("frame_index is 1-based; must be >= 1")
    return (frame_index - 1) / float(fps)


def frame_filename(frame_index: int, ext: str = "jpg") -> str:
    return f"frame_{frame_index:06d}.{ext}"


def build_ffmpeg_extract_cmd(
    video_path: PathLike, frames_dir: PathLike, fps: int
) -> List[str]:
    out_pattern = str(Path(frames_dir) / "frame_%06d.jpg")
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-qscale:v",
        "2",
        out_pattern,
    ]


def build_colmap_feature_cmd(
    database_path: PathLike, image_path: PathLike
) -> List[str]:
    return [
        "colmap",
        "feature_extractor",
        "--database_path",
        str(database_path),
        "--image_path",
        str(image_path),
        "--ImageReader.single_camera",
        "1",
        "--SiftExtraction.use_gpu",
        "1",
    ]


def build_colmap_matcher_cmd(database_path: PathLike) -> List[str]:
    return [
        "colmap",
        "exhaustive_matcher",
        "--database_path",
        str(database_path),
        "--SiftMatching.use_gpu",
        "1",
    ]


def build_colmap_mapper_cmd(
    database_path: PathLike,
    image_path: PathLike,
    sparse_dir: PathLike,
) -> List[str]:
    return [
        "colmap",
        "mapper",
        "--database_path",
        str(database_path),
        "--image_path",
        str(image_path),
        "--output_path",
        str(sparse_dir),
    ]


def build_colmap_undistorter_cmd(
    sparse_dir: PathLike,
    images_dir: PathLike,
    output_dir: PathLike,
) -> List[str]:
    return [
        "colmap",
        "image_undistorter",
        "--image_path",
        str(images_dir),
        "--input_path",
        str(sparse_dir),
        "--output_path",
        str(output_dir),
        "--output_type",
        "COLMAP",
    ]


# ---------------------------------------------------------------------------
# Runners (subprocess; thin)
# ---------------------------------------------------------------------------


@dataclass
class ExtractResult:
    frames_dir: Path
    frame_count: int
    fps: int


def extract_frames(
    video_path: PathLike, frames_dir: PathLike, fps: int
) -> ExtractResult:
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_ffmpeg_extract_cmd(video_path, frames_dir, fps=fps)
    LOG.info("ffmpeg: %s", " ".join(cmd))
    run_logged(cmd, timeout=FFMPEG_EXTRACT_TIMEOUT_SECONDS)
    frame_count = len(list(frames_dir.glob("frame_*.jpg")))
    return ExtractResult(frames_dir=frames_dir, frame_count=frame_count, fps=fps)


@dataclass
class ColmapResult:
    workspace: Path
    sparse_dir: Path          # e.g. workspace/sparse/0
    dense_dir: Path           # undistorted images + sparse copy
    database_path: Path


def run_colmap(images_dir: PathLike, workspace: PathLike) -> ColmapResult:
    """Runs COLMAP feature -> match -> map -> undistort.

    Requires `colmap` on PATH and a CUDA build for GPU features.
    """
    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    db = workspace / "database.db"
    sparse_root = workspace / "sparse"
    sparse_root.mkdir(exist_ok=True)
    dense = workspace / "dense"
    dense.mkdir(exist_ok=True)

    for cmd in (
        build_colmap_feature_cmd(db, images_dir),
        build_colmap_matcher_cmd(db),
        build_colmap_mapper_cmd(db, images_dir, sparse_root),
    ):
        LOG.info("colmap: %s", " ".join(cmd))
        run_logged(cmd, timeout=COLMAP_STAGE_TIMEOUT_SECONDS)

    # COLMAP mapper outputs models into sparse/0, sparse/1, ... — we take 0.
    sparse0 = sparse_root / "0"
    if not sparse0.exists():
        raise RuntimeError(
            "COLMAP produced no reconstruction — not enough parallax?"
        )

    undistort = build_colmap_undistorter_cmd(
        sparse_dir=sparse0, images_dir=images_dir, output_dir=dense
    )
    LOG.info("colmap: %s", " ".join(undistort))
    run_logged(undistort, timeout=COLMAP_STAGE_TIMEOUT_SECONDS)

    return ColmapResult(
        workspace=workspace,
        sparse_dir=sparse0,
        dense_dir=dense,
        database_path=db,
    )
