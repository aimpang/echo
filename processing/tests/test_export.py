"""TDD tests for per-frame manifest building."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from echoes.fourdgs.export import (
    MANIFEST_VERSION,
    build_manifest_dict,
    pair_plys_with_times,
    write_manifest_file,
)


class TestPairPlysWithTimes:
    def test_equal_lengths(self):
        plys = [Path("a.ply"), Path("b.ply")]
        times = [0.0, 1.0]
        assert pair_plys_with_times(plys, times) == [
            (Path("a.ply"), 0.0),
            (Path("b.ply"), 1.0),
        ]

    def test_interpolates_times_when_fewer_times_than_plys(self):
        plys = [Path(f"{i}.ply") for i in range(5)]
        times = [0.0, 2.0]  # only two — spread evenly across the 5 frames
        pairs = pair_plys_with_times(plys, times)
        assert [p[0] for p in pairs] == plys
        assert pairs[0][1] == pytest.approx(0.0)
        assert pairs[-1][1] == pytest.approx(2.0)
        # Middle frame ~ 1.0s
        assert pairs[2][1] == pytest.approx(1.0)

    def test_truncates_extra_times(self):
        plys = [Path("a.ply")]
        times = [0.0, 1.0, 2.0]
        assert pair_plys_with_times(plys, times) == [(Path("a.ply"), 0.0)]

    def test_empty(self):
        assert pair_plys_with_times([], []) == []


class TestBuildManifestDict:
    def test_shape(self):
        entries = [("a.splat", 0.0), ("b.splat", 0.5)]
        data = build_manifest_dict(entries, duration_seconds=0.5)
        assert data["version"] == MANIFEST_VERSION
        assert data["durationSeconds"] == 0.5
        assert data["frames"] == [
            {"url": "a.splat", "timeSeconds": 0.0},
            {"url": "b.splat", "timeSeconds": 0.5},
        ]

    def test_empty_manifest(self):
        data = build_manifest_dict([], duration_seconds=0.0)
        assert data["frames"] == []


class TestWriteManifestFile:
    def test_round_trip_json(self, tmp_path: Path):
        entries = [("a.splat", 0.0), ("b.splat", 1.0)]
        out = tmp_path / "manifest.json"
        write_manifest_file(out, entries, duration_seconds=1.0)
        loaded = json.loads(out.read_text())
        assert loaded["frames"][1] == {"url": "b.splat", "timeSeconds": 1.0}
