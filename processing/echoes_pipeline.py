"""
Echoes local processing worker.

Polls Supabase for memories that need processing, runs safety + 4D Gaussian
Splatting (via `gsplat`), and writes results back.

Run locally on the RTX 5080:
    python echoes_pipeline.py

State machine (must match src/lib/memory/status.ts on the web side):
    uploading -> scanning -> processing -> ready
                      \-> rejected
                      \-> processing_failed
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from supabase import Client, create_client

LOG = logging.getLogger("echoes")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
)

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
AUTO_PASS_SAFETY = os.environ.get("AUTO_PASS_SAFETY", "true").lower() == "true"
HIVE_API_KEY = os.environ.get("HIVE_API_KEY")
WORK_DIR = Path(os.environ.get("WORK_DIR", "./work")).resolve()
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "5"))
FRAMES_PER_SECOND = int(os.environ.get("FRAMES_PER_SECOND", "8"))
MAX_TRAIN_ITERATIONS = int(os.environ.get("MAX_TRAIN_ITERATIONS", "8000"))

WORK_DIR.mkdir(parents=True, exist_ok=True)


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


def client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def claim_next(sb: Client, status: str) -> Optional[Memory]:
    """Fetch one memory in the given status. Simple FIFO; no locking for MVP."""
    res = (
        sb.table("memories")
        .select(
            "id,user_id,status,source_video_path,duration_seconds"
        )
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


def set_status(sb: Client, memory_id: str, **fields) -> None:
    sb.table("memories").update(fields).eq("id", memory_id).execute()


def download_video(sb: Client, memory: Memory, dest: Path) -> Path:
    if not memory.source_video_path:
        raise RuntimeError("Memory has no source_video_path")
    LOG.info("Downloading %s", memory.source_video_path)
    data = sb.storage.from_("videos").download(memory.source_video_path)
    dest.write_bytes(data)
    return dest


def upload_splat(sb: Client, memory: Memory, splat_file: Path) -> str:
    key = f"{memory.user_id}/{memory.id}.splat"
    LOG.info("Uploading splat to %s", key)
    sb.storage.from_("splats").upload(
        path=key,
        file=splat_file.read_bytes(),
        file_options={"content-type": "application/octet-stream", "upsert": "true"},
    )
    return key


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------


def run_safety_scan(video_path: Path) -> tuple[bool, Optional[str]]:
    """Return (passed, flag)."""
    if AUTO_PASS_SAFETY or not HIVE_API_KEY:
        LOG.info("Auto-passing safety (AUTO_PASS_SAFETY=%s)", AUTO_PASS_SAFETY)
        return True, None

    # Minimal Hive integration. See https://docs.thehive.ai/
    with open(video_path, "rb") as f:
        response = requests.post(
            "https://api.thehive.ai/api/v2/task/sync",
            headers={"Authorization": f"Token {HIVE_API_KEY}"},
            files={"media": f},
            timeout=120,
        )
    response.raise_for_status()
    result = response.json()
    # Very simple heuristic: reject if any class scores above 0.8
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


def extract_frames(video_path: Path, frames_dir: Path) -> int:
    frames_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={FRAMES_PER_SECOND}",
        "-qscale:v",
        "2",
        str(frames_dir / "frame_%04d.jpg"),
    ]
    LOG.info("Extracting frames: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return len(list(frames_dir.glob("frame_*.jpg")))


def run_gsplat(frames_dir: Path, out_dir: Path) -> Path:
    """
    Run gsplat training on the extracted frames.

    For this MVP we invoke gsplat's built-in `simple_trainer` via a subprocess.
    Swap in a true 4D variant (e.g. 4DGaussians) when extending beyond static
    scenes.

    Expected to produce `<out_dir>/point_cloud.ply` and/or `<out_dir>/out.splat`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # TODO: replace with a 4D pipeline.
    cmd = [
        sys.executable,
        "-m",
        "gsplat.examples.simple_trainer",
        "default",
        "--data_dir",
        str(frames_dir),
        "--result_dir",
        str(out_dir),
        "--max_steps",
        str(MAX_TRAIN_ITERATIONS),
        "--save_ply",
    ]
    LOG.info("Running gsplat: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

    splat_path = out_dir / "out.splat"
    if not splat_path.exists():
        # gsplat outputs ply; convert to .splat if you have a converter.
        ply = next(out_dir.glob("**/*.ply"), None)
        if ply is None:
            raise RuntimeError("gsplat produced no ply/splat output")
        LOG.info("Falling back to PLY output at %s", ply)
        return ply
    return splat_path


# ---------------------------------------------------------------------------
# Job runners
# ---------------------------------------------------------------------------


def run_scanning_job(sb: Client, memory: Memory) -> None:
    job_dir = WORK_DIR / memory.id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / "input.mp4"

    try:
        download_video(sb, memory, video_path)
        passed, flag = run_safety_scan(video_path)
        if not passed:
            LOG.warning("Safety scan rejected memory %s (%s)", memory.id, flag)
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


def run_processing_job(sb: Client, memory: Memory) -> None:
    job_dir = WORK_DIR / memory.id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_path = job_dir / "input.mp4"
    if not video_path.exists():
        download_video(sb, memory, video_path)

    try:
        frames_dir = job_dir / "frames"
        n_frames = extract_frames(video_path, frames_dir)
        LOG.info("Extracted %d frames", n_frames)

        out_dir = job_dir / "gsplat"
        splat_path = run_gsplat(frames_dir, out_dir)

        key = upload_splat(sb, memory, splat_path)
        set_status(
            sb,
            memory.id,
            status="ready",
            splat_path=key,
            processing_completed_at="now()",
        )
        LOG.info("Memory %s is ready", memory.id)
    except Exception as err:
        LOG.exception("Processing failed for %s", memory.id)
        set_status(sb, memory.id, status="processing_failed", safety_flag=str(err))
    finally:
        # Keep the job_dir around on failure for inspection; clean on success.
        pass


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
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


if __name__ == "__main__":
    main()
