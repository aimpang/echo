# Echoes Processing Worker

Runs locally on an RTX 5080 to turn uploaded videos into **4D Gaussian
Splatting** scenes. Polls Supabase for jobs, stages a COLMAP dataset, trains a
4DGaussians model (hustvl/4DGaussians, CVPR 2024), exports one `.splat` per
timestep plus a `manifest.json`, and uploads the bundle back to Supabase.

## Pipeline stages

```
video ──► ffmpeg frames ──► COLMAP (features/match/map/undistort)
      ──► stage_dataset (COLMAP + times.txt)
      ──► 4DGaussians train.py
      ──► 4DGaussians render.py (per-timestep PLY)
      ──► PLY → SPLAT + manifest.json
      ──► upload to splats/<user>/<memory>/
```

Each stage is wrapped in `StageTimer` so the worker emits a per-stage timing
log on success (and `--benchmark` prints it to stdout + writes
`benchmark.json`).

## Setup

```powershell
cd processing

# Python 3.11 — the ML ecosystem (torch, open3d, mmengine, lpips)
# doesn't yet ship wheels for 3.14+. Use uv to grab it:
uv venv --python 3.11 .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install pip wheel setuptools

# PyTorch with CUDA 12.8 wheels for RTX 5080 (Blackwell sm_120).
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# Core deps
pip install -r requirements.txt
```

You also need the **CUDA Toolkit 12.8** installed system-wide (not just the
driver) so `nvcc` is on `PATH` — that's what compiles the two CUDA
extensions below. Download: https://developer.nvidia.com/cuda-12-8-0-download-archive

### Vendor hustvl/4DGaussians

```powershell
# One-shot clone helper (wraps `git clone --recurse-submodules`):
python setup_4dgaussians.py

# The vendor's requirements.txt pins torch==1.13.1 which has no wheel for
# Python 3.11 and can't target Blackwell (sm_120). Skip it — use the
# patched list at processing/vendor-requirements.txt instead, which
# omits the torch pins and mmcv (replaced by a pure-Python shim over
# mmengine — see .venv311/Lib/site-packages/mmcv/__init__.py).
pip install -r vendor-requirements.txt

# Build the CUDA extensions against your torch/CUDA install:
cd vendor/4DGaussians
pip install -e submodules/depth-diff-gaussian-rasterization
pip install -e submodules/simple-knn
cd ../..
```

Point the worker at the repo and a config file via `.env`:

```
FOURDGS_REPO_DIR=./vendor/4DGaussians
FOURDGS_CONFIG=./vendor/4DGaussians/arguments/dynerf/default.py
```

### System binaries on PATH

- **ffmpeg** — frame extraction
- **colmap** — structure-from-motion (feature, matcher, mapper, undistorter)

## Preflight

The worker runs a preflight check at startup and refuses to start if anything
is missing. It verifies:

- `ffmpeg` and `colmap` are on `PATH`
- `FOURDGS_REPO_DIR` and `FOURDGS_CONFIG` env vars are set
- Both paths exist on disk

If you see a preflight failure, run `python setup_4dgaussians.py` and then
build the CUDA extensions as above.

## Running the worker

```powershell
# Copy .env.example -> .env, fill in Supabase service role key + FOURDGS_*
python echoes_pipeline.py
```

The worker:

1. Polls for `status = 'scanning'`, runs safety (auto-pass during early access
   unless `HIVE_API_KEY` is set and `AUTO_PASS_SAFETY=false`), then advances
   to `processing`.
2. Runs the full 4DGaussians pipeline and emits a timing report.
3. Uploads every `.splat` and `manifest.json` under
   `splats/<user_id>/<memory_id>/`; sets `splat_path` on the memory to the
   manifest key.
4. Any error moves the memory to `processing_failed`.

## Benchmark mode (no Supabase)

```powershell
python echoes_pipeline.py --benchmark `
  --video .\samples\clip.mp4 `
  --out .\work\bench `
  --fps 8 --iterations 8000
```

Runs every stage on a local file and writes `work/bench/benchmark.json` plus
a human-readable timing table. Useful for tuning iteration count / fps on the
5080 and sharing numbers.

## Tests

Pure logic is unit-tested:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Covers: PLY→SPLAT conversion, ffmpeg/COLMAP command builders, dataset staging,
manifest builder, and the pipeline's pure helpers.
