"""TDD tests for 4DGaussians train/render wrapper (command builders + timers)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from echoes.fourdgs.train import (
    StageTimer,
    build_render_cmd,
    build_train_cmd,
    find_rendered_plys,
)


class TestBuildTrainCmd:
    def test_minimal(self):
        cmd = build_train_cmd(
            repo_dir=Path("/repo"),
            data_dir=Path("/data"),
            model_dir=Path("/out"),
            config_file=Path("/repo/arguments/monocular.py"),
        )
        assert cmd[0] == "python"
        assert any(str(Path("/repo/train.py")) in part for part in cmd)
        # -s <data>
        i = cmd.index("-s")
        assert cmd[i + 1] == str(Path("/data"))
        # --model_path <out>
        i = cmd.index("--model_path")
        assert cmd[i + 1] == str(Path("/out"))
        # --configs <cfg>
        i = cmd.index("--configs")
        assert cmd[i + 1] == str(Path("/repo/arguments/monocular.py"))

    def test_extra_args_appended(self):
        cmd = build_train_cmd(
            repo_dir=Path("/repo"),
            data_dir=Path("/data"),
            model_dir=Path("/out"),
            config_file=Path("/repo/arguments/monocular.py"),
            extra_args=["--iterations", "6000", "--seed", "42"],
        )
        assert cmd[-4:] == ["--iterations", "6000", "--seed", "42"]


class TestBuildRenderCmd:
    def test_minimal(self):
        cmd = build_render_cmd(
            repo_dir=Path("/repo"),
            model_dir=Path("/out"),
            config_file=Path("/repo/arguments/monocular.py"),
        )
        assert cmd[0] == "python"
        assert any(str(Path("/repo/render.py")) in part for part in cmd)
        i = cmd.index("--model_path")
        assert cmd[i + 1] == str(Path("/out"))
        # Render only train set so we get one frame per input time
        assert "--skip_test" in cmd
        assert "--skip_video" in cmd


class TestStageTimer:
    def test_records_elapsed(self):
        timer = StageTimer()
        with timer.stage("preprocess"):
            time.sleep(0.005)
        with timer.stage("train"):
            time.sleep(0.005)
        report = timer.report()
        assert set(report.keys()) == {"preprocess", "train"}
        assert report["preprocess"] >= 0.0
        assert report["train"] >= 0.0

    def test_exception_still_records_stage(self):
        timer = StageTimer()
        with pytest.raises(RuntimeError):
            with timer.stage("boom"):
                raise RuntimeError("bad")
        assert "boom" in timer.report()


class TestFindRenderedPlys:
    def test_picks_up_numbered_plys(self, tmp_path: Path):
        train_dir = tmp_path / "train" / "ours_6000" / "renders"
        train_dir.mkdir(parents=True)
        # per-timestep ply output
        point_dir = tmp_path / "point_cloud"
        point_dir.mkdir()
        (point_dir / "time_00000.ply").touch()
        (point_dir / "time_00001.ply").touch()
        (point_dir / "time_00002.ply").touch()
        plys = find_rendered_plys(tmp_path)
        assert [p.name for p in plys] == [
            "time_00000.ply",
            "time_00001.ply",
            "time_00002.ply",
        ]

    def test_sorts_numerically_not_lexically(self, tmp_path: Path):
        d = tmp_path / "point_cloud"
        d.mkdir()
        for i in [10, 2, 1, 20, 3]:
            (d / f"time_{i:05d}.ply").touch()
        plys = find_rendered_plys(tmp_path)
        names = [p.name for p in plys]
        # numeric-sorted (via the zero-padded filename)
        assert names == [
            "time_00001.ply",
            "time_00002.ply",
            "time_00003.ply",
            "time_00010.ply",
            "time_00020.ply",
        ]

    def test_returns_empty_if_no_plys(self, tmp_path: Path):
        assert find_rendered_plys(tmp_path) == []
