"""
Echoes local processing worker.

Two modes:

1. Worker mode (default):
       python echoes_pipeline.py
   Polls Supabase for memories in `scanning` / `processing` status and runs
   the full 4DGaussians pipeline end to end, uploading per-frame .splat files
   and a manifest.json to the `splats` bucket.

2. Benchmark mode:
       python echoes_pipeline.py --benchmark --video clip.mp4 --out work/bench
   Runs the pipeline on a local video without touching Supabase. Emits a
   per-stage timing report and writes `benchmark.json`. Use this to validate
   RTX 5080 performance.

State machine (must match web/src/lib/memory/status.ts):
    uploading -> scanning -> processing -> ready
                      \\-> rejected
                      \\-> processing_failed
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from supabase import Client

from echoes.fourdgs.pipeline import (
    build_benchmark_parser,
    format_timing_report,
    run_full_pipeline,
    write_benchmark_log,
)

LOG = logging.getLogger("echoes")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise SystemExit(f"Missing required env var: {name}")
    return val or ""


AUTO_PASS_SAFETY = os.environ.get("AUTO_PASS_SAFETY", "true").lower() == "true"
HIVE_API_KEY = os.environ.get("HIVE_API_KEY")
WORK_DIR = Path(os.environ.get("WORK_DIR", "./work")).resolve()
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "5"))
FRAMES_PER_SECOND = int(os.environ.get("FRAMES_PER_SECOND", "8"))
MAX_TRAIN_ITERATIONS = int(os.environ.get("MAX_TRAIN_ITERATIONS", "8000"))


@dataclass
class Memory:
    id: str
    user_id: str
    status: str
    source_video_path: Optional[str]
    duration_seconds: Optional[float]


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------


def client() -> "Client":
    from supabase import create_client

    url = _env("SUPABASE_URL", required=True)
    key = _env("SUPABASE_SERVICE_ROLE_KEY", required=True)
    return create_client(url, key)


def claim_next(sb: "Client", status: str) -> Optional[Memory]:
    res = (
        sb.table("memories")
        .select("id,user_id,status,source_video_path,duration_seconds")
        .eq("status", status)
        .order("created_at")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    r = rows[0]
    return Memory(
        id=r["id"],
        user_id=r["user_id"],
        status=r["status"],
        source_video_path=r.get("source_video_path"),
        duration_seconds=r.get("duration_seconds"),
    )


def set_status(sb: "Client", memory_id: str, **fields) -> None:
    sb.table("memories").update(fields).eq("id", memory_id).execute()


def download_video(sb: "Client", memory: Memory, dest: Path) -> Path:
    if not memory.source_video_path:
        raise RuntimeError("Memory has no source_video_path")
    LOG.info("Downloading %s", memory.source_video_path)
    data = sb.storage.from_("videos").download(memory.source_video_path)
    dest.write_bytes(data)
    return dest


def upload_splat_dir(sb: "Client", memory: Memory, splat_dir: Path) -> str:
    """Upload every .splat plus manifest.json and return the manifest object key."""
    prefix = f"{memory.user_id}/{memory.id}"
    manifest_key = f"{prefix}/manifest.json"

    for path in sorted(splat_dir.iterdir()):
        if not path.is_file():
            continue
        key = f"{prefix}/{path.name}"
        content_type = (
            "application/json"
            if path.suffix == ".json"
            else "application/octet-stream"
        )
        LOG.info("Uploading %s", key)
        sb.storage.from_("splats").upload(
            path=key,
            file=path.read_bytes(),
            file_options={"content-type": content_type, "upsert": "true"},
        )
    return manifest_key


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


def run_safety_scan(video_path: Path) -> tuple[bool, Optional[str]]:
    if AUTO_PASS_SAFETY or not HIVE_API_KEY:
        LOG.info("Auto-passing safety (AUTO_PASS_SAFETY=%s)", AUTO_PASS_SAFETY)
        return True, None

    import requests

    with open(video_path, "rb") as f:
        response = requests.post(
            "https://api.thehive.ai/api/v2/task/sync",
            headers={"Authorization": f"Token {HIVE_API_KEY}"},
            files={"media": f},
            timeout=120,
        )
    response.raise_for_status()
    result = response.json()
    for output in result.get("status", [{}])[0].get("response", {}).get("output", []):
        for cls in output.get("classes", []):
            if cls.get("score", 0) > 0.8 and cls.get("class") in {
                "sexual_activity",
                "nudity",
                "gore",
                "violence",
            }:
                return False, cls["class"]
    return True, None


# ---------------------------------------------------------------------------
# Pipeline resolution (env + args)
# ---------------------------------------------------------------------------


def _resolve_repo_and_config(
    repo_dir_arg: Optional[str], config_arg: Optional[str]
) -> tuple[Path, Path]:
    repo_dir = repo_dir_arg or os.environ.get("FOURDGS_REPO_DIR")
    config = config_arg or os.environ.get("FOURDGS_CONFIG")
    if not repo_dir:
        raise SystemExit(
            "FOURDGS_REPO_DIR not set. Clone hustvl/4DGaussians and point "
            "this env var at the repo root."
        )
    if not config:
        raise SystemExit(
            "FOURDGS_CONFIG not set. Point it at a config .py inside the "
            "4DGaussians repo (e.g. arguments/dynerf/default.py)."
        )
    return Path(repo_dir), Path(config)


# ---------------------------------------------------------------------------
# Worker jobs
# ---------------------------------------------------------------------------


def run_scanning_job(sb: "Client", memory: Memory) -> None:
    job_dir = WORK_DIR / memory.id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / "input.mp4"

    try:
        download_video(sb, memory, video_path)
        passed, flag = run_safety_scan(video_path)
        if not passed:
            LOG.warning("Safety scan rejected %s (%s)", memory.id, flag)
            set_status(
                sb,
                memory.id,
                status="rejected",
                safety_flag=flag,
                safety_checked_at="now()",
            )
            return
        set_status(
            sb,
            memory.id,
            status="processing",
            safety_flag=None,
            safety_checked_at="now()",
            processing_started_at="now()",
        )
    except Exception as err:
        LOG.exception("Scan stage failed for %s", memory.id)
        set_status(sb, memory.id, status="processing_failed", safety_flag=str(err))


def run_processing_job(sb: "Client", memory: Memory) -> None:
    job_dir = WORK_DIR / memory.id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / "input.mp4"
    if not video_path.exists():
        download_video(sb, memory, video_path)

    try:
        repo_dir, config_file = _resolve_repo_and_config(None, None)
        result = run_full_pipeline(
            video_path=video_path,
            work_dir=job_dir,
            fps=FRAMES_PER_SECOND,
            iterations=MAX_TRAIN_ITERATIONS,
            repo_dir=repo_dir,
            config_file=config_file,
        )

        LOG.info("\n%s", format_timing_report(result["timings"]))

        splat_dir: Path = result["splat_dir"]  # type: ignore[assignment]
        manifest_key = upload_splat_dir(sb, memory, splat_dir)

        set_status(
            sb,
            memory.id,
            status="ready",
            splat_path=manifest_key,
            duration_seconds=result["duration_seconds"],
            processing_completed_at="now()",
        )
        LOG.info("Memory %s is ready (%d frames)", memory.id, result["frame_count"])
    except Exception as err:
        LOG.exception("Processing failed for %s", memory.id)
        set_status(sb, memory.id, status="processing_failed", safety_flag=str(err))


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


def run_benchmark(argv: list[str]) -> int:
    parser = build_benchmark_parser()
    args = parser.parse_args(argv)

    video = Path(args.video).resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_dir, config_file = _resolve_repo_and_config(args.repo_dir, args.config)

    LOG.info("Benchmark: video=%s out=%s fps=%d iters=%d", video, out_dir, args.fps, args.iterations)

    result = run_full_pipeline(
        video_path=video,
        work_dir=out_dir,
        fps=args.fps,
        iterations=args.iterations,
        repo_dir=repo_dir,
        config_file=config_file,
    )

    report = format_timing_report(result["timings"])
    print("\n" + report)
    log_path = write_benchmark_log(out_dir, result)
    print(f"\nBenchmark log: {log_path}")
    print(f"Manifest:      {result['manifest_path']}")
    print(f"Frames:        {result['frame_count']}")
    return 0


# ---------------------------------------------------------------------------
# Worker main loop
# ---------------------------------------------------------------------------


def run_worker() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    sb = client()
    LOG.info("Echoes worker online. Work dir: %s", WORK_DIR)
    while True:
        try:
            scan_job = claim_next(sb, "scanning")
            if scan_job:
                LOG.info("Claiming scan job %s", scan_job.id)
                run_scanning_job(sb, scan_job)
                continue

            proc_job = claim_next(sb, "processing")
            if proc_job:
                LOG.info("Claiming processing job %s", proc_job.id)
                run_processing_job(sb, proc_job)
                continue

            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            LOG.info("Shutdown requested")
            return
        except Exception:
            LOG.exception("Worker loop error")
            time.sleep(POLL_INTERVAL)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--benchmark":
        return run_benchmark(argv[1:])
    run_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
