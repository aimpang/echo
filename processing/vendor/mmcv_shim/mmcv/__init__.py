"""Shim that exposes mmengine's Config under the legacy `mmcv` name.

4DGaussians only calls `mmcv.Config.fromfile`, which is identical in mmengine.
Installing real mmcv requires a from-source build that's incompatible with
modern setuptools; mmengine is the maintained successor and pure Python.
"""

from mmengine import Config  # noqa: F401

__all__ = ["Config"]
