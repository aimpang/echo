"""
Pipeline orchestration helpers for the 4DGaussians worker.

The pure functions here are fully unit-tested. The side-effectful orchestrator
(`run_full_pipeline`) composes the already-tested preprocess / dataset / train
/ export modules, so we rely on integration runs (including `--benchmark`) to
exercise it rather than mocking subprocesses in tests.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from echoes.fourdgs.dataset import stage_dataset
from echoes.fourdgs.export import (
    MANIFEST_FILENAME,
    convert_plys_to_splats,
    pair_plys_with_times,
    write_manifest_file,
)
from echoes.fourdgs.train import (
    StageTimer,
    find_rendered_plys,
    run_render,
    run_train,
)
from echoes.preprocess import extract_frames, run_colmap

LOG = logging.getLogger(__name__)

DEFAULT_FPS = 8
DEFAULT_ITERATIONS = 8000


def total_seconds(timings: Mapping[str, float]) -> float:
    return float(sum(timings.values()))


def format_timing_report(timings: Mapping[str, float]) -> str:
    lines = ["stage                    seconds"]
    lines.append("-" * 33)
    for name, seconds in timings.items():
        lines.append(f"{name:<25}{seconds:>8.2f}")
    lines.append("-" * 33)
    lines.append(f"{'total':<25}{total_seconds(timings):>8.2f}")
    return "\n".join(lines)


def build_completion_update(
    manifest_key: str, duration_seconds: float
) -> Dict[str, Any]:
    """Fields to update on the memory row after the pipeline succeeds.

    Nulls out `source_video_path` because the source video is deleted from
    storage on success — keeping the old path would point at a missing object.
    """
    return {
        "status": "ready",
        "splat_path": manifest_key,
        "duration_seconds": duration_seconds,
        "processing_completed_at": "now()",
        "source_video_path": None,
    }


def build_benchmark_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="echoes_pipeline --benchmark",
        description="Run the full 4DGaussians pipeline on a local video and "
        "emit per-stage timings.",
    )
    parser.add_argument("--video", required=True, help="Path to input video file")
    parser.add_argument(
        "--out", required=True, help="Output directory (created if missing)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help=f"Frames per second to extract (default: {DEFAULT_FPS})",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Train iterations (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--repo-dir",
        default=None,
        help="Path to vendored hustvl/4DGaussians repo. Falls back to "
        "$FOURDGS_REPO_DIR.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to 4DGaussians config .py. Falls back to $FOURDGS_CONFIG.",
    )
    return parser


def run_full_pipeline(
    video_path: Path,
    work_dir: Path,
    *,
    fps: int,
    iterations: int,
    repo_dir: Path,
    config_file: Path,
) -> Dict[str, object]:
    """
    Full pipeline: frames -> COLMAP -> stage -> train -> render -> export.
    Returns a dict with manifest path, splat dir, frame count, and timings.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    frames_dir = work_dir / "frames"
    colmap_workspace = work_dir / "colmap"
    staged = work_dir / "staged"
    model_dir = work_dir / "model"
    splat_dir = work_dir / "splats"

    timer = StageTimer()

    with timer.stage("extract_frames"):
        extract_frames(video_path, frames_dir, fps=fps)

    with timer.stage("colmap"):
        colmap_result = run_colmap(frames_dir, colmap_workspace)

    with timer.stage("stage_dataset"):
        stage_dataset(colmap_result.dense_dir, fps=fps, out_dir=staged)

    with timer.stage("train"):
        run_train(
            repo_dir=repo_dir,
            data_dir=staged,
            model_dir=model_dir,
            config_file=config_file,
            extra_args=["--iterations", str(iterations)],
        )

    with timer.stage("render"):
        run_render(
            repo_dir=repo_dir,
            model_dir=model_dir,
            config_file=config_file,
        )

    with timer.stage("export"):
        plys = find_rendered_plys(model_dir)
        if not plys:
            raise RuntimeError(f"No PLY frames produced in {model_dir}")
        splat_paths = convert_plys_to_splats(plys, splat_dir)

        # Use times.txt from the staged dataset to timestamp each frame.
        times_txt = staged / "times.txt"
        times: List[float] = []
        if times_txt.exists():
            times = [float(x) for x in times_txt.read_text().splitlines() if x.strip()]

        entries = pair_plys_with_times(splat_paths, times)
        duration = max((t for _, t in entries), default=0.0)
        manifest_entries = [(p.name, t) for p, t in entries]
        manifest_path = write_manifest_file(
            splat_dir / MANIFEST_FILENAME, manifest_entries, duration
        )

    timings = timer.report()
    return {
        "manifest_path": manifest_path,
        "splat_dir": splat_dir,
        "frame_count": len(splat_paths),
        "duration_seconds": duration,
        "timings": timings,
    }


def write_benchmark_log(out_dir: Path, result: Mapping[str, object]) -> Path:
    """Write a JSON timing log alongside the manifest."""
    log_path = Path(out_dir) / "benchmark.json"
    payload = {
        "frame_count": result["frame_count"],
        "duration_seconds": result["duration_seconds"],
        "timings": result["timings"],
        "total_seconds": total_seconds(result["timings"]),  # type: ignore[arg-type]
    }
    log_path.write_text(json.dumps(payload, indent=2))
    return log_path
