"""TDD tests for building the 4DGaussians-compatible dataset layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from echoes.fourdgs.dataset import (
    build_times_for_frames,
    frame_index_from_path,
    normalize_times,
    write_times_txt,
)


class TestBuildTimesForFrames:
    def test_even_spacing(self):
        times = build_times_for_frames(n_frames=5, fps=4)
        assert times == [0.0, 0.25, 0.5, 0.75, 1.0]

    def test_single_frame(self):
        assert build_times_for_frames(n_frames=1, fps=30) == [0.0]

    def test_zero_frames_is_empty(self):
        assert build_times_for_frames(n_frames=0, fps=30) == []


class TestNormalizeTimes:
    def test_maps_to_zero_one(self):
        norm = normalize_times([0.0, 0.5, 1.0, 2.0])
        assert norm[0] == pytest.approx(0.0)
        assert norm[-1] == pytest.approx(1.0)

    def test_single_value_is_zero(self):
        assert normalize_times([3.0]) == [0.0]

    def test_constant_times_are_all_zero(self):
        assert normalize_times([1.0, 1.0, 1.0]) == [0.0, 0.0, 0.0]

    def test_empty_is_empty(self):
        assert normalize_times([]) == []


class TestFrameIndexFromPath:
    def test_extracts_digits(self):
        assert frame_index_from_path(Path("frame_000042.jpg")) == 42

    def test_ignores_non_frame_files(self):
        with pytest.raises(ValueError):
            frame_index_from_path(Path("random.jpg"))


class TestWriteTimesTxt:
    def test_writes_one_per_line(self, tmp_path: Path):
        out = tmp_path / "times.txt"
        write_times_txt(out, [0.0, 0.125, 0.25])
        contents = out.read_text().strip().splitlines()
        assert contents == ["0.000000", "0.125000", "0.250000"]
