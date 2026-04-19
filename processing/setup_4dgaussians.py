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
Next steps (run these in your processing venv, with torch+CUDA already installed):

    cd {target}
    pip install -r requirements.txt
    pip install -e submodules/depth-diff-gaussian-rasterization
    pip install -e submodules/simple-knn

Then add to processing/.env:

    FOURDGS_REPO_DIR={target}
    FOURDGS_CONFIG={target}/arguments/dynerf/default.py

Run the preflight check:

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
