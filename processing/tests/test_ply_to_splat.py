"""TDD tests for the 3DGS PLY -> antimatter15/splat binary converter."""

from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np
import pytest

from echoes.converters.ply_to_splat import (
    BYTES_PER_SPLAT,
    SH_C0,
    convert_ply_file_to_splat,
    encode_quaternion,
    opacity_to_alpha_u8,
    pack_splat_record,
    sh_dc_to_rgb_u8,
)


# ---------------------------------------------------------------------------
# Pure transform tests
# ---------------------------------------------------------------------------


class TestSHToRGB:
    def test_dc_zero_is_mid_grey(self):
        # 0.5 + SH_C0 * 0 = 0.5 -> 127 or 128 (rounded)
        assert sh_dc_to_rgb_u8(0.0) in {127, 128}

    def test_clamped_to_u8_range(self):
        assert sh_dc_to_rgb_u8(-10.0) == 0
        assert sh_dc_to_rgb_u8(+10.0) == 255

    def test_monotonic(self):
        vals = [sh_dc_to_rgb_u8(x) for x in [-2, -1, -0.5, 0, 0.5, 1, 2]]
        assert vals == sorted(vals)

    def test_matches_reference_formula(self):
        for f_dc in [-1.0, -0.3, 0.0, 0.3, 1.0]:
            expected = max(0, min(255, round((0.5 + SH_C0 * f_dc) * 255)))
            assert sh_dc_to_rgb_u8(f_dc) == expected


class TestOpacityToAlpha:
    def test_zero_logit_is_mid_alpha(self):
        assert opacity_to_alpha_u8(0.0) in {127, 128}

    def test_large_positive_saturates(self):
        assert opacity_to_alpha_u8(20.0) == 255

    def test_large_negative_is_zero(self):
        assert opacity_to_alpha_u8(-20.0) == 0

    def test_matches_sigmoid(self):
        for o in [-2.0, -0.5, 0.0, 0.5, 2.0]:
            expected = round((1 / (1 + math.exp(-o))) * 255)
            assert opacity_to_alpha_u8(o) == expected


class TestQuaternionEncoding:
    def test_normalized_identity(self):
        # Identity quaternion (1, 0, 0, 0) -> encoded as (255, 128, 128, 128)
        # because (1 * 128 + 128) = 256 clamped to 255
        r, x, y, z = encode_quaternion((1.0, 0.0, 0.0, 0.0))
        assert r == 255
        assert x == 128 and y == 128 and z == 128

    def test_unnormalized_input_is_normalized(self):
        # Any scalar multiple of the same quaternion produces same encoding.
        a = encode_quaternion((2.0, 0.0, 0.0, 0.0))
        b = encode_quaternion((1.0, 0.0, 0.0, 0.0))
        assert a == b

    def test_negative_component(self):
        # q = (0, -1, 0, 0) -> normalized same, second byte = (-1 * 128 + 128) = 0
        r, x, y, z = encode_quaternion((0.0, -1.0, 0.0, 0.0))
        assert x == 0
        assert r == 128

    def test_all_bytes_in_u8_range(self):
        import random

        random.seed(0)
        for _ in range(50):
            q = tuple(random.uniform(-1, 1) for _ in range(4))
            if all(v == 0 for v in q):
                continue
            for b in encode_quaternion(q):  # type: ignore[arg-type]
                assert 0 <= b <= 255


# ---------------------------------------------------------------------------
# Packed record
# ---------------------------------------------------------------------------


class TestPackSplatRecord:
    def test_record_is_32_bytes(self):
        record = pack_splat_record(
            position=(0.0, 0.0, 0.0),
            scale=(1.0, 1.0, 1.0),
            rgba=(255, 128, 64, 200),
            rotation_u8=(128, 128, 128, 255),
        )
        assert len(record) == BYTES_PER_SPLAT == 32

    def test_layout_position_then_scale_then_color_then_rot(self):
        record = pack_splat_record(
            position=(1.5, -2.0, 3.25),
            scale=(0.5, 0.25, 0.125),
            rgba=(10, 20, 30, 40),
            rotation_u8=(50, 60, 70, 80),
        )
        px, py, pz = struct.unpack_from("<fff", record, 0)
        sx, sy, sz = struct.unpack_from("<fff", record, 12)
        r, g, b, a = struct.unpack_from("<BBBB", record, 24)
        q0, q1, q2, q3 = struct.unpack_from("<BBBB", record, 28)
        assert (px, py, pz) == (1.5, -2.0, 3.25)
        assert (sx, sy, sz) == (0.5, 0.25, 0.125)
        assert (r, g, b, a) == (10, 20, 30, 40)
        assert (q0, q1, q2, q3) == (50, 60, 70, 80)


# ---------------------------------------------------------------------------
# End-to-end roundtrip
# ---------------------------------------------------------------------------


def _write_minimal_3dgs_ply(path: Path, n: int = 3) -> None:
    """Write a tiny synthetic 3DGS-style PLY (no SH beyond DC)."""
    from plyfile import PlyData, PlyElement

    dtype = [
        ("x", "f4"),
        ("y", "f4"),
        ("z", "f4"),
        ("f_dc_0", "f4"),
        ("f_dc_1", "f4"),
        ("f_dc_2", "f4"),
        ("opacity", "f4"),
        ("scale_0", "f4"),
        ("scale_1", "f4"),
        ("scale_2", "f4"),
        ("rot_0", "f4"),
        ("rot_1", "f4"),
        ("rot_2", "f4"),
        ("rot_3", "f4"),
    ]
    data = np.zeros(n, dtype=dtype)
    for i in range(n):
        data[i] = (
            float(i),
            float(i) * 2,
            float(i) * 3,
            0.0,
            0.0,
            0.0,
            0.0,
            math.log(0.1 + 0.01 * i),
            math.log(0.2 + 0.01 * i),
            math.log(0.3 + 0.01 * i),
            1.0,
            0.0,
            0.0,
            0.0,
        )
    el = PlyElement.describe(data, "vertex")
    PlyData([el], text=False).write(str(path))


def test_convert_ply_file_emits_correct_size(tmp_path: Path):
    ply = tmp_path / "scene.ply"
    splat = tmp_path / "scene.splat"
    _write_minimal_3dgs_ply(ply, n=5)

    n_written = convert_ply_file_to_splat(ply, splat)
    assert n_written == 5
    assert splat.stat().st_size == 5 * BYTES_PER_SPLAT


def test_convert_ply_file_positions_roundtrip(tmp_path: Path):
    ply = tmp_path / "scene.ply"
    splat = tmp_path / "scene.splat"
    _write_minimal_3dgs_ply(ply, n=4)

    convert_ply_file_to_splat(ply, splat)
    raw = splat.read_bytes()

    for i in range(4):
        offset = i * BYTES_PER_SPLAT
        x, y, z = struct.unpack_from("<fff", raw, offset)
        assert x == pytest.approx(float(i))
        assert y == pytest.approx(float(i) * 2)
        assert z == pytest.approx(float(i) * 3)


def test_convert_ply_file_scales_are_exponentiated(tmp_path: Path):
    ply = tmp_path / "scene.ply"
    splat = tmp_path / "scene.splat"
    _write_minimal_3dgs_ply(ply, n=2)

    convert_ply_file_to_splat(ply, splat)
    raw = splat.read_bytes()

    # First record's scale_0 was log(0.1), so decoded should be ~0.1
    sx, _sy, _sz = struct.unpack_from("<fff", raw, 12)
    assert sx == pytest.approx(0.1, rel=1e-4)
