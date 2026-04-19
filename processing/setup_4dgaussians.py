"""
One-shot setup helper for the 4DGaussians vendor checkout.

Clones hustvl/4DGaussians (with submodules) into `vendor/4DGaussians` and
prints the remaining manual steps — building the CUDA extensions — which
must happen on the target machine against its own torch/CUDA install.

Usage:
    python setup_4dgaussians.py                    # clone into ./vendor/4DGaussians
    python setup_4dgaussians.py --target some/dir  # clone elsewhere
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from echoes.fourdgs.preflight import build_4dgaussians_clone_cmd

DEFAULT_TARGET = Path("vendor/4DGaussians")

POST_CLONE_INSTRUCTIONS = """
Next steps (run these in your processing venv):

  1. Install PyTorch with CUDA 12.8 wheels (needed for RTX 5080 sm_120):

        pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

  2. Install the patched vendor deps — DO NOT use the upstream requirements.txt,
     which pins torch==1.13.1 (no wheel for Python 3.11, can't target Blackwell)
     and mmcv (replaced by the mmengine shim). Use processing/vendor-requirements.txt:

        pip install -r vendor-requirements.txt

  3. Build the CUDA extensions against your installed torch/CUDA:

        cd {target}
        pip install -e submodules/depth-diff-gaussian-rasterization
        pip install -e submodules/simple-knn

Then add to processing/.env:

    FOURDGS_REPO_DIR={target}
    FOURDGS_CONFIG={target}/arguments/dynerf/default.py

Verify with a benchmark run (no Supabase required):

    python echoes_pipeline.py --benchmark --video samples/clip.mp4 --out work/bench
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help="Directory to clone 4DGaussians into (default: vendor/4DGaussians)",
    )
    args = parser.parse_args(argv)

    target: Path = args.target.resolve()

    if target.exists():
        print(f"[skip] {target} already exists — not re-cloning.")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = build_4dgaussians_clone_cmd(target)
        print("[run]", " ".join(cmd))
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print("\nClone failed. Check network + git access.", file=sys.stderr)
            return result.returncode

    print(POST_CLONE_INSTRUCTIONS.format(target=target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
