"""山墙木筋（gable half-timbering）。

半木构农舍最显眼的特征在山墙：三角草泥面被外露木构架切成几块。这里沿用
墙身木筋的做法——构件是贴在墙体外侧的实体梁，靠自身厚度与墙板错开，不做
布尔运算。

构件组成（自下而上）：
- 底部通长系梁；
- 沿两条坡边的斜梁，兼作博风板内侧的收边；
- 屋脊下方垂下的中柱；
- 约四成高处的横撑，把山墙分成上下两格；
- 系梁两端斜向横撑的短斜撑，形成参考图里的 A 形受力外观。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder

BEAM_W = 0.14
BEAM_PROUD = 0.05
BEAM_EMBED = 0.02


def _box(builder: MeshBuilder, x0: float, x1: float, z0: float, z1: float) -> None:
    if x1 - x0 < 0.03 or z1 - z0 < 0.03:
        return
    builder.add_box((x0, -BEAM_PROUD, z0), (x1, BEAM_EMBED, z1), "trim")


def _bar(
    builder: MeshBuilder,
    x0: float,
    z0: float,
    x1: float,
    z1: float,
    bar_w: float = 0.13,
) -> None:
    """XZ 平面内任意方向的斜梁：沿走向的垂直方向扫出矩形截面。"""
    dx, dz = x1 - x0, z1 - z0
    length = math.hypot(dx, dz)
    if length < 0.1:
        return
    nx, nz = -dz / length * bar_w * 0.5, dx / length * bar_w * 0.5
    corners = [
        (x0 + nx, z0 + nz),
        (x1 + nx, z1 + nz),
        (x1 - nx, z1 - nz),
        (x0 - nx, z0 - nz),
    ]
    front = [(x, -BEAM_PROUD, z) for x, z in corners]
    back = [(x, BEAM_EMBED, z) for x, z in corners]
    builder.add_face(front, "trim")
    builder.add_face(list(reversed(back)), "trim")
    for index in range(4):
        a = corners[index]
        b = corners[(index + 1) % 4]
        builder.add_face(
            [
                (a[0], -BEAM_PROUD, a[1]),
                (b[0], -BEAM_PROUD, b[1]),
                (b[0], BEAM_EMBED, b[1]),
                (a[0], BEAM_EMBED, a[1]),
            ],
            "trim",
        )


def build_gable_frame(span: float, rise: float, tiles: dict[str, float]) -> MeshBuilder:
    """三角山墙木构架；局部坐标 X 沿山墙宽度、Z 自檐口起算、Y 向外为负。"""
    builder = MeshBuilder(tiles)
    if span < 1.2 or rise < 0.5:
        return builder
    cx = span * 0.5

    # 系梁
    _box(builder, 0.0, span, 0.0, BEAM_W)
    # 中柱：从系梁顶到脊下
    _box(builder, cx - BEAM_W * 0.5, cx + BEAM_W * 0.5, BEAM_W, rise - 0.05)
    # 两条坡边由屋顶自带的博风板收边，这里不再叠一根同位置的斜梁

    # 横撑
    collar_z = rise * 0.4
    half_at = cx * (1.0 - collar_z / rise)
    if half_at > 0.3:
        _box(builder, cx - half_at, cx + half_at, collar_z - BEAM_W * 0.5, collar_z + BEAM_W * 0.5)
        # 斜撑：系梁上距中线 1.3 倍横撑半宽处 -> 横撑端部
        foot = min(cx - BEAM_W, half_at * 1.3)
        _bar(builder, cx - foot, BEAM_W, cx - half_at, collar_z - BEAM_W * 0.5)
        _bar(builder, cx + foot, BEAM_W, cx + half_at, collar_z - BEAM_W * 0.5)

    return builder
