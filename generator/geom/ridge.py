"""屋脊压梁与山墙封檐板（悬山收头）。

参考图里屋脊上压着一根粗木脊梁，两端探出山墙；山墙两侧的坡边缘各有一块
沿坡向的木封檐板（博风板）。这些构件贴在瓦面外侧，不做布尔运算。

局部坐标与 ``build_gable_roof`` 一致：X 为跨度方向，Y 为进深方向，
z 为檐口所在高度。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .gallery import sweep_box


def build_ridge_cap(
    width: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    thickness: float,
    tiles: dict[str, float],
    extend: float = 0.6,
) -> MeshBuilder:
    """屋脊压梁（两端出挑）+ 四周封檐板。"""
    builder = MeshBuilder(tiles)
    half = (width + 2 * overhang) * 0.5
    cx = width * 0.5
    rise = math.tan(math.radians(pitch_deg)) * half
    z_top = z + thickness
    z_ridge = z_top + rise
    y0 = -overhang - extend
    y1 = depth + overhang + extend

    # 脊梁压在屋脊上，两端伸出山墙形成悬山挑头
    builder.add_box((cx - 0.10, y0, z_ridge - 0.05), (cx + 0.10, y1, z_ridge + 0.17), "trim")
    # 挑头端面加两块小垫木，避免梁头过于单薄
    for y in (y0, y1 - 0.12):
        builder.add_box((cx - 0.14, y, z_ridge - 0.09), (cx + 0.14, y + 0.12, z_ridge + 0.07), "trim")

    # 前后山墙两侧的封檐板，沿坡向贴住瓦边
    for y in (-overhang - 0.05, depth + overhang + 0.05):
        sweep_box(
            builder,
            (cx - half - 0.05, y, z_top - 0.04),
            (cx, y, z_ridge + 0.02),
            (0.0, 1.0, 0.0),
            0.16,
            0.20,
            "trim",
        )
        sweep_box(
            builder,
            (cx, y, z_ridge + 0.02),
            (cx + half + 0.05, y, z_top - 0.04),
            (0.0, 1.0, 0.0),
            0.16,
            0.20,
            "trim",
        )
    return builder
