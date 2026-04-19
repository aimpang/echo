# Echoes Processing Worker

Runs locally on an RTX 5080 to process uploaded videos into Gaussian Splatting
scenes. Polls Supabase for jobs, runs safety + splat training, writes results
back.

## Setup

```powershell
cd processing
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install PyTorch with CUDA 12.x wheels for RTX 5080:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

# Core deps
pip install -r requirements.txt

# gsplat (build against the same torch/cuda)
pip install gsplat

# System binaries required:
#   - ffmpeg on PATH
#   - (optional) COLMAP on PATH for pose estimation
```

Copy `.env.example` to `.env` and fill in your Supabase service role key.

## Running

```powershell
python echoes_pipeline.py
```

The worker:

1. Polls `memories` for rows with `status = 'scanning'` and runs safety (auto-pass
   during local dev unless `HIVE_API_KEY` is set and `AUTO_PASS_SAFETY=false`).
2. Advances to `processing`, extracts frames with ffmpeg, trains a splat via
   `gsplat.examples.simple_trainer`, uploads `.splat`/`.ply` to the `splats`
   bucket, and marks the memory `ready`.
3. Any error moves the memory to `processing_failed`.

## Extending to true 4DGS

`run_gsplat` in `echoes_pipeline.py` currently trains a single static 3D scene.
To make memories time-varying:

1. Replace the single gsplat call with a 4D variant (e.g. 4DGaussians,
   Dynamic3DGS, or Dreamgaussian4D).
2. Export one splat per timestep and upload them as separate objects
   (`splats/<user>/<memory>/frame_<nnnn>.splat`).
3. Save a manifest JSON listing `{url, timeSeconds}` per frame in the
   `splats` bucket, and extend the web viewer to read it and pass `frames`
   to `<SplatViewer>`.
