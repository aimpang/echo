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

Each stage logs a `[memory=<id> stage=<name>]` prefix so grep-piping the
worker log reconstructs a single job's timeline.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from supabase import Client

from echoes._sentry import capture_exception, init_sentry_if_configured
from echoes.fourdgs.pipeline import (
    build_benchmark_parser,
    build_completion_update,
    format_timing_report,
    run_full_pipeline,
    write_benchmark_log,
)
from echoes.fourdgs.preflight import check_preflight, format_preflight_report
from echoes.worker import (
    build_failure_update,
    build_splat_storage_prefix,
    content_type_for_upload,
    delete_local_video,
    job_log_prefix,
    should_download_video,
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


AUTO_PASS_SAFETY = os.environ.get("AUTO_PASS_SAFETY", "false").lower() == "true"
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


def mark_processing_failed(sb: "Client", memory: Memory, error: BaseException) -> None:
    """Best-effort: write `processing_failed` + a short error on the row.

    If the DB is also down (the usual reason the job failed in the first
    place), we log and move on rather than bubbling a second exception out
    of the failure handler.
    """
    capture_exception(error)
    try:
        set_status(sb, memory.id, **build_failure_update(error))
    except Exception as db_err:
        LOG.exception(
            "%s could not write processing_failed to DB — row is stuck",
            job_log_prefix(memory.id, "fail-handler"),
        )
        capture_exception(db_err)


def download_video(sb: "Client", memory: Memory, dest: Path) -> Path:
    if not memory.source_video_path:
        raise RuntimeError(
            f"Memory {memory.id} has no source_video_path (nothing to download)"
        )
    prefix = job_log_prefix(memory.id, "download")
    LOG.info("%s start %s", prefix, memory.source_video_path)
    data = sb.storage.from_("videos").download(memory.source_video_path)
    dest.write_bytes(data)
    LOG.info("%s done (%d bytes)", prefix, len(data))
    return dest


def delete_source_video(sb: "Client", memory: Memory) -> bool:
    """Remove the uploaded video from the `videos` bucket. Non-fatal: logs
    and returns False on failure so a finished memory isn't marked failed
    just because cleanup couldn't delete one object."""
    if not memory.source_video_path:
        return True
    prefix = job_log_prefix(memory.id, "cleanup")
    try:
        sb.storage.from_("videos").remove([memory.source_video_path])
        LOG.info("%s deleted source video %s", prefix, memory.source_video_path)
        return True
    except Exception:
        LOG.exception(
            "%s could not delete source video %s (memory is still ready)",
            prefix,
            memory.source_video_path,
        )
        return False


def _upload_one(sb: "Client", storage_key: str, local_path: Path) -> None:
    sb.storage.from_("splats").upload(
        path=storage_key,
        file=local_path.read_bytes(),
        file_options={
            "content-type": content_type_for_upload(local_path),
            "upsert": "true",
        },
    )


def upload_splat_dir(sb: "Client", memory: Memory, splat_dir: Path) -> str:
    """Upload every .splat plus manifest.json and return the manifest object key."""
    prefix = build_splat_storage_prefix(memory.user_id, memory.id)
    manifest_key = f"{prefix}/manifest.json"
    log_prefix = job_log_prefix(memory.id, "upload")

    files = [p for p in sorted(splat_dir.iterdir()) if p.is_file()]
    LOG.info("%s start (%d files)", log_prefix, len(files))
    for path in files:
        key = f"{prefix}/{path.name}"
        LOG.debug("%s uploading %s", log_prefix, key)
        _upload_one(sb, key, path)
    LOG.info("%s done → %s", log_prefix, manifest_key)
    return manifest_key


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


def run_safety_scan(
    video_path: Path, memory_id: str
) -> tuple[bool, Optional[str]]:
    log_prefix = job_log_prefix(memory_id, "safety")
    if AUTO_PASS_SAFETY or not HIVE_API_KEY:
        LOG.info(
            "%s auto-pass (AUTO_PASS_SAFETY=%s, HIVE_API_KEY=%s)",
            log_prefix,
            AUTO_PASS_SAFETY,
            "set" if HIVE_API_KEY else "unset",
        )
        return True, None

    import requests

    LOG.info("%s sending to Hive", log_prefix)
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
                LOG.warning("%s rejected (%s)", log_prefix, cls["class"])
                return False, cls["class"]
    LOG.info("%s passed", log_prefix)
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
# Processing job — split into single-purpose steps
# ---------------------------------------------------------------------------


def ensure_video_staged(sb: "Client", memory: Memory, video_path: Path) -> None:
    """Download the source video iff it's not already on disk."""
    if should_download_video(video_path):
        download_video(sb, memory, video_path)
    else:
        LOG.info(
            "%s reusing cached video (%d bytes)",
            job_log_prefix(memory.id, "download"),
            video_path.stat().st_size,
        )


def run_pipeline_for_memory(memory: Memory, job_dir: Path) -> dict:
    """Invoke the 4DGaussians pipeline on a staged job dir."""
    log_prefix = job_log_prefix(memory.id, "pipeline")
    repo_dir, config_file = _resolve_repo_and_config(None, None)
    LOG.info("%s start (fps=%d iters=%d)", log_prefix, FRAMES_PER_SECOND, MAX_TRAIN_ITERATIONS)
    result = run_full_pipeline(
        video_path=job_dir / "input.mp4",
        work_dir=job_dir,
        fps=FRAMES_PER_SECOND,
        iterations=MAX_TRAIN_ITERATIONS,
        repo_dir=repo_dir,
        config_file=config_file,
    )
    LOG.info("%s done\n%s", log_prefix, format_timing_report(result["timings"]))
    return result


def publish_splats(sb: "Client", memory: Memory, result: dict) -> str:
    """Upload splat bundle + mark the memory as ready. Returns manifest key."""
    splat_dir: Path = result["splat_dir"]  # type: ignore[assignment]
    manifest_key = upload_splat_dir(sb, memory, splat_dir)
    update = build_completion_update(
        manifest_key=manifest_key,
        duration_seconds=float(result["duration_seconds"]),  # type: ignore[arg-type]
    )
    set_status(sb, memory.id, **update)
    LOG.info(
        "%s ready (%d frames)",
        job_log_prefix(memory.id, "finalize"),
        result["frame_count"],
    )
    return manifest_key


def cleanup_after_success(sb: "Client", memory: Memory, job_dir: Path) -> None:
    """Enforce the retention policy: after a successful run the original
    video exists in three places (storage, local job dir, in-memory data
    during upload). Wipe the first two. Every step is best-effort and
    idempotent — a failure here doesn't invalidate the ready memory, and
    re-running on a partially cleaned job is expected (crash recovery).
    """
    log_prefix = job_log_prefix(memory.id, "cleanup")

    # 1. Storage copy (canonical "original").
    delete_source_video(sb, memory)

    # 2. Local staged copy in the job dir.
    local_video = job_dir / "input.mp4"
    if delete_local_video(local_video):
        LOG.info("%s deleted local video %s", log_prefix, local_video)
    else:
        LOG.info("%s local video already gone (%s)", log_prefix, local_video)

    # 3. The rest of the job workspace (frames, COLMAP, model, splats).
    try:
        shutil.rmtree(job_dir, ignore_errors=True)
        LOG.info("%s removed job dir %s", log_prefix, job_dir)
    except Exception:
        LOG.exception("%s could not remove job dir %s", log_prefix, job_dir)


# ---------------------------------------------------------------------------
# Worker jobs
# ---------------------------------------------------------------------------


def run_scanning_job(sb: "Client", memory: Memory) -> None:
    log_prefix = job_log_prefix(memory.id, "scanning")
    LOG.info("%s start", log_prefix)

    job_dir = WORK_DIR / memory.id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / "input.mp4"

    try:
        ensure_video_staged(sb, memory, video_path)
        passed, flag = run_safety_scan(video_path, memory.id)
        if not passed:
            set_status(
                sb,
                memory.id,
                status="rejected",
                safety_flag=flag,
                safety_checked_at="now()",
            )
            LOG.info("%s → rejected", log_prefix)
            return
        set_status(
            sb,
            memory.id,
            status="processing",
            safety_flag=None,
            safety_checked_at="now()",
            processing_started_at="now()",
        )
        LOG.info("%s → processing", log_prefix)
    except Exception as err:
        LOG.exception("%s failed: %s", log_prefix, err)
        mark_processing_failed(sb, memory, err)


def run_processing_job(sb: "Client", memory: Memory) -> None:
    log_prefix = job_log_prefix(memory.id, "processing")
    LOG.info("%s start", log_prefix)

    job_dir = WORK_DIR / memory.id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / "input.mp4"

    try:
        ensure_video_staged(sb, memory, video_path)
        result = run_pipeline_for_memory(memory, job_dir)
        publish_splats(sb, memory, result)
        cleanup_after_success(sb, memory, job_dir)
        LOG.info("%s → ready", log_prefix)
    except Exception as err:
        LOG.exception("%s failed: %s", log_prefix, err)
        mark_processing_failed(sb, memory, err)


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------


def _run_preflight_or_die() -> None:
    issues = check_preflight(env=os.environ)
    if issues:
        LOG.error("\n%s", format_preflight_report(issues))
        raise SystemExit(1)
    LOG.info("Preflight OK")


def run_benchmark(argv: list[str]) -> int:
    parser = build_benchmark_parser()
    args = parser.parse_args(argv)

    video = Path(args.video).resolve()
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")

    # Let --repo-dir / --config flags populate env so preflight sees them.
    if args.repo_dir:
        os.environ["FOURDGS_REPO_DIR"] = args.repo_dir
    if args.config:
        os.environ["FOURDGS_CONFIG"] = args.config
    _run_preflight_or_die()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_dir, config_file = _resolve_repo_and_config(args.repo_dir, args.config)

    LOG.info(
        "Benchmark: video=%s out=%s fps=%d iters=%d",
        video,
        out_dir,
        args.fps,
        args.iterations,
    )

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


def _claim_and_run_once(sb: "Client") -> bool:
    """Try to claim one scanning or processing job. Returns True if we ran
    one (so the caller should loop again immediately rather than sleep)."""
    scan_job = claim_next(sb, "scanning")
    if scan_job:
        LOG.info("Claimed scan job %s", scan_job.id)
        run_scanning_job(sb, scan_job)
        return True

    proc_job = claim_next(sb, "processing")
    if proc_job:
        LOG.info("Claimed processing job %s", proc_job.id)
        run_processing_job(sb, proc_job)
        return True

    return False


def run_worker() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    init_sentry_if_configured()
    _run_preflight_or_die()
    sb = client()
    LOG.info("Echoes worker online. Work dir: %s", WORK_DIR)
    while True:
        try:
            if _claim_and_run_once(sb):
                continue
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            LOG.info("Shutdown requested")
            return
        except Exception as loop_err:
            LOG.exception("Worker loop error — sleeping and retrying")
            capture_exception(loop_err)
            time.sleep(POLL_INTERVAL)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--benchmark":
        return run_benchmark(argv[1:])
    run_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
