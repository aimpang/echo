"""TDD tests for preprocess command builders (pure functions only)."""

from __future__ import annotations

import pytest

from echoes.preprocess import (
    build_ffmpeg_extract_cmd,
    build_colmap_feature_cmd,
    build_colmap_matcher_cmd,
    build_colmap_mapper_cmd,
    build_colmap_undistorter_cmd,
    frame_time_seconds,
    frame_filename,
)


class TestFrameTimeSeconds:
    def test_first_frame_is_zero(self):
        assert frame_time_seconds(1, fps=30) == 0.0

    def test_advances_linearly_with_index(self):
        assert frame_time_seconds(2, fps=30) == pytest.approx(1 / 30)
        assert frame_time_seconds(31, fps=30) == pytest.approx(1.0)

    def test_works_for_various_fps(self):
        assert frame_time_seconds(5, fps=8) == pytest.approx(0.5)

    def test_rejects_non_positive_index(self):
        with pytest.raises(ValueError):
            frame_time_seconds(0, fps=30)


class TestFrameFilename:
    def test_pads_to_six_digits(self):
        assert frame_filename(1) == "frame_000001.jpg"
        assert frame_filename(1234) == "frame_001234.jpg"

    def test_supports_custom_extension(self):
        assert frame_filename(2, ext="png") == "frame_000002.png"


class TestFfmpegCommand:
    def test_includes_input_and_fps_filter(self):
        cmd = build_ffmpeg_extract_cmd("video.mp4", "frames/", fps=12)
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert "video.mp4" in cmd
        assert any("fps=12" in part for part in cmd)

    def test_output_is_glob_pattern(self):
        cmd = build_ffmpeg_extract_cmd("v.mp4", "out/", fps=8)
        assert any(part.endswith("frame_%06d.jpg") for part in cmd)

    def test_overwrites_existing_output(self):
        cmd = build_ffmpeg_extract_cmd("v.mp4", "out/", fps=8)
        assert "-y" in cmd


class TestColmapCommands:
    def test_feature_extractor(self):
        cmd = build_colmap_feature_cmd("db.db", "images/")
        assert cmd[0] == "colmap"
        assert cmd[1] == "feature_extractor"
        assert "--database_path" in cmd
        assert "db.db" in cmd
        assert "--image_path" in cmd

    def test_exhaustive_matcher(self):
        cmd = build_colmap_matcher_cmd("db.db")
        assert cmd[:2] == ["colmap", "exhaustive_matcher"]
        assert "db.db" in cmd

    def test_mapper(self):
        cmd = build_colmap_mapper_cmd("db.db", "images/", "sparse/")
        assert cmd[:2] == ["colmap", "mapper"]
        assert "sparse/" in cmd

    def test_undistorter(self):
        cmd = build_colmap_undistorter_cmd(
            sparse_dir="sparse/0", images_dir="images/", output_dir="dense/"
        )
        assert cmd[:2] == ["colmap", "image_undistorter"]
        assert "dense/" in cmd
        assert "--output_type" in cmd
        # LLFF-friendly output type:
        i = cmd.index("--output_type")
        assert cmd[i + 1] == "COLMAP"
