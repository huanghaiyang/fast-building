"""中世纪垛口女儿墙（crenellation）。

由连续的矮护墙带 + 等距垛齿组成，沿平屋顶四周布置；全部是轴对齐实体盒，
不需要布尔运算，也不会与屋面产生共面。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder

BAND_H = 0.42
MERLON_H = 0.52
MERLON_W = 0.78
CRENEL_W = 0.46
THICKNESS = 0.30


def _merlons(
    builder: MeshBuilder,
    start: float,
    end: float,
    z: float,
    horizontal: bool,
    x_offset: float = 0.0,
    y_offset: float = 0.0,
) -> None:
    span = end - start
    if span < MERLON_W:
        return
    count = max(1, int((span + CRENEL_W) // (MERLON_W + CRENEL_W)))
    step = span / count
    width = min(MERLON_W, step - CRENEL_W) if step - CRENEL_W > 0.25 else step * 0.6
    for index in range(count):
        center = start + step * (index + 0.5)
        a, b = center - width * 0.5, center + width * 0.5
        if horizontal:
            builder.add_box(
                (a + x_offset, -THICKNESS + y_offset, z),
                (b + x_offset, y_offset, z + MERLON_H),
                "trim",
            )
        else:
            builder.add_box(
                (-THICKNESS + x_offset, a + y_offset, z),
                (x_offset, b + y_offset, z + MERLON_H),
                "trim",
            )


def build_crenellated_parapet(
    width: float,
    depth: float,
    z: float,
    tiles: dict[str, float],
    overhang: float = 0.45,
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    x0, x1 = -overhang, width + overhang
    y0, y1 = -overhang, depth + overhang

    # 连续护墙带：前后各一条，左右各一条（左右内缩避免角部重叠）
    builder.add_box((x0, y0, z), (x1, y0 + THICKNESS, z + BAND_H), "trim")
    builder.add_box((x0, y1 - THICKNESS, z), (x1, y1, z + BAND_H), "trim")
    builder.add_box((x0, y0 + THICKNESS, z), (x0 + THICKNESS, y1 - THICKNESS, z + BAND_H), "trim")
    builder.add_box((x1 - THICKNESS, y0 + THICKNESS, z), (x1, y1 - THICKNESS, z + BAND_H), "trim")

    top = z + BAND_H
    _merlons(builder, x0 + THICKNESS, x1 - THICKNESS, top, True)
    _merlons(builder, x0 + THICKNESS, x1 - THICKNESS, top, True, y_offset=y1)
    _merlons(builder, y0 + THICKNESS, y1 - THICKNESS, top, False)
    _merlons(builder, y0 + THICKNESS, y1 - THICKNESS, top, False, x_offset=x1)

    return builder
