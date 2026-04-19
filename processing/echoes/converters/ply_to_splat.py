"""
Convert a 3D Gaussian Splatting .ply file into the 32-byte-per-splat binary
format used by antimatter15/splat and consumed by @react-three/drei's <Splat>.

Packed record layout (32 bytes per splat, little-endian):
  offset 0..11   position (f32 x, y, z)
  offset 12..23  scale    (f32 sx, sy, sz)           -- linear (exp of PLY scale_i)
  offset 24..27  color    (u8 r, g, b, a)            -- a = sigmoid(opacity)*255
  offset 28..31  rotation (u8 encoded quaternion)    -- (normalize(q) * 128 + 128)
"""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np

BYTES_PER_SPLAT = 32

# Zeroth-order SH coefficient — converts f_dc to linear RGB:
#   rgb = clamp(0.5 + SH_C0 * f_dc, 0, 1)
SH_C0 = 0.28209479177387814


def _clamp_u8(v: float) -> int:
    if v <= 0:
        return 0
    if v >= 255:
        return 255
    return int(round(v))


def sh_dc_to_rgb_u8(f_dc: float) -> int:
    return _clamp_u8((0.5 + SH_C0 * f_dc) * 255.0)


def opacity_to_alpha_u8(opacity_logit: float) -> int:
    if opacity_logit > 20:
        sig = 1.0
    elif opacity_logit < -20:
        sig = 0.0
    else:
        sig = 1.0 / (1.0 + math.exp(-opacity_logit))
    return _clamp_u8(sig * 255.0)


def encode_quaternion(
    q: Tuple[float, float, float, float],
) -> Tuple[int, int, int, int]:
    w, x, y, z = q
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm == 0:
        return (128, 128, 128, 128)
    inv = 1.0 / norm
    return (
        _clamp_u8(w * inv * 128.0 + 128.0),
        _clamp_u8(x * inv * 128.0 + 128.0),
        _clamp_u8(y * inv * 128.0 + 128.0),
        _clamp_u8(z * inv * 128.0 + 128.0),
    )


def pack_splat_record(
    position: Tuple[float, float, float],
    scale: Tuple[float, float, float],
    rgba: Tuple[int, int, int, int],
    rotation_u8: Tuple[int, int, int, int],
) -> bytes:
    return struct.pack(
        "<fff fff BBBB BBBB",
        position[0],
        position[1],
        position[2],
        scale[0],
        scale[1],
        scale[2],
        rgba[0] & 0xFF,
        rgba[1] & 0xFF,
        rgba[2] & 0xFF,
        rgba[3] & 0xFF,
        rotation_u8[0] & 0xFF,
        rotation_u8[1] & 0xFF,
        rotation_u8[2] & 0xFF,
        rotation_u8[3] & 0xFF,
    )


def convert_ply_file_to_splat(ply_path: Path, splat_path: Path) -> int:
    """Read a 3DGS PLY, write the .splat binary. Returns splat count written."""
    from plyfile import PlyData

    plydata = PlyData.read(str(ply_path))
    vertex = plydata["vertex"]
    n = len(vertex.data)

    positions = np.stack(
        [vertex["x"], vertex["y"], vertex["z"]], axis=-1
    ).astype(np.float32, copy=False)

    scales = np.exp(
        np.stack(
            [vertex["scale_0"], vertex["scale_1"], vertex["scale_2"]],
            axis=-1,
        ).astype(np.float32, copy=False)
    )

    # Sort by 'importance' (opacity * scale magnitude) so early splats dominate
    # the streamed rendering. This mirrors antimatter15/splat's convention.
    opacity = vertex["opacity"].astype(np.float32, copy=False)
    f_dc_0 = vertex["f_dc_0"].astype(np.float32, copy=False)
    f_dc_1 = vertex["f_dc_1"].astype(np.float32, copy=False)
    f_dc_2 = vertex["f_dc_2"].astype(np.float32, copy=False)
    rot_0 = vertex["rot_0"].astype(np.float32, copy=False)
    rot_1 = vertex["rot_1"].astype(np.float32, copy=False)
    rot_2 = vertex["rot_2"].astype(np.float32, copy=False)
    rot_3 = vertex["rot_3"].astype(np.float32, copy=False)

    splat_path.parent.mkdir(parents=True, exist_ok=True)
    with open(splat_path, "wb") as out:
        for i in range(n):
            rgba = (
                sh_dc_to_rgb_u8(float(f_dc_0[i])),
                sh_dc_to_rgb_u8(float(f_dc_1[i])),
                sh_dc_to_rgb_u8(float(f_dc_2[i])),
                opacity_to_alpha_u8(float(opacity[i])),
            )
            rot_u8 = encode_quaternion(
                (
                    float(rot_0[i]),
                    float(rot_1[i]),
                    float(rot_2[i]),
                    float(rot_3[i]),
                )
            )
            record = pack_splat_record(
                position=(
                    float(positions[i, 0]),
                    float(positions[i, 1]),
                    float(positions[i, 2]),
                ),
                scale=(
                    float(scales[i, 0]),
                    float(scales[i, 1]),
                    float(scales[i, 2]),
                ),
                rgba=rgba,
                rotation_u8=rot_u8,
            )
            out.write(record)

    return n


def convert_many(ply_paths: Iterable[Path], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []
    for ply in ply_paths:
        splat = out_dir / f"{ply.stem}.splat"
        convert_ply_file_to_splat(ply, splat)
        out_paths.append(splat)
    return out_paths
