"""TDD tests for pipeline orchestration helpers (pure pieces)."""

from __future__ import annotations

import pytest

from echoes.fourdgs.pipeline import (
    build_benchmark_parser,
    build_completion_update,
    format_timing_report,
    total_seconds,
)


class TestTotalSeconds:
    def test_sums_values(self):
        assert total_seconds({"a": 1.0, "b": 2.5}) == pytest.approx(3.5)

    def test_empty(self):
        assert total_seconds({}) == 0.0


class TestFormatTimingReport:
    def test_includes_every_stage(self):
        report = format_timing_report(
            {"extract": 1.5, "colmap": 30.0, "train": 600.0}
        )
        assert "extract" in report
        assert "colmap" in report
        assert "train" in report

    def test_includes_total_line(self):
        report = format_timing_report({"a": 2.0, "b": 3.0})
        # total appears somewhere
        assert "total" in report.lower()
        assert "5.0" in report or "5.00" in report

    def test_preserves_insertion_order(self):
        report = format_timing_report({"zeta": 1.0, "alpha": 1.0})
        assert report.index("zeta") < report.index("alpha")

    def test_empty_timings(self):
        report = format_timing_report({})
        # Still produces some output (likely a total=0 line)
        assert "total" in report.lower()


class TestBuildCompletionUpdate:
    def test_includes_ready_status_and_splat_path(self):
        payload = build_completion_update("a/b/manifest.json", duration_seconds=2.5)
        assert payload["status"] == "ready"
        assert payload["splat_path"] == "a/b/manifest.json"
        assert payload["duration_seconds"] == 2.5

    def test_nulls_out_source_video_path(self):
        payload = build_completion_update("m.json", duration_seconds=0.0)
        assert payload["source_video_path"] is None

    def test_sets_processing_completed_at_sentinel(self):
        payload = build_completion_update("m.json", duration_seconds=0.0)
        assert payload["processing_completed_at"] == "now()"


class TestBuildBenchmarkParser:
    def test_requires_video_path(self):
        parser = build_benchmark_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parses_video_and_out(self):
        parser = build_benchmark_parser()
        args = parser.parse_args(["--video", "clip.mp4", "--out", "work/bench"])
        assert args.video == "clip.mp4"
        assert args.out == "work/bench"

    def test_optional_fps_and_iterations(self):
        parser = build_benchmark_parser()
        args = parser.parse_args(
            ["--video", "c.mp4", "--out", "o", "--fps", "12", "--iterations", "4000"]
        )
        assert args.fps == 12
        assert args.iterations == 4000

    def test_defaults(self):
        parser = build_benchmark_parser()
        args = parser.parse_args(["--video", "c.mp4", "--out", "o"])
        # fps/iterations default to sensible values (not None)
        assert isinstance(args.fps, int)
        assert isinstance(args.iterations, int)
