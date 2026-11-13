"""悬挑楼层的托木裙带（jetty）。

半木构街屋的二层往往整体向外挑出一截：楼板压在底层的墙身上，挑出部分靠一排
斜撑托木和出挑的搁栅端头顶住。``assemble`` 里的 ``jetty`` 只是把楼板与墙体
逐层外扩，立面看上去还是「悬空的一层」，所以这里补一圈托木：

- 挑檐封边梁：贴着楼板外缘一圈，压住挑出部分的端头；
- 托木：沿墙按开间分界布置，水平顶块 + 斜撑，撑在底层墙面上；
- 搁栅端头：从楼板边缘探出来的方木端头，一排收头。

局部坐标：X 0..width、Y 0..depth（均取悬挑后该层的轮廓），Z=0 为楼板底面，
构件全部向 -Z 方向长出来。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder
from .gallery import sweep_box

LOG = "log"
WOOD = "trim"


def build_jetty_skirt(
    width: float,
    depth: float,
    step: float,
    tiles: dict[str, float],
    spacing: float = 0.92,
) -> MeshBuilder:
    """一圈托木：封边梁 + 托木 + 斜撑 + 搁栅端头。"""
    builder = MeshBuilder(tiles)
    if step <= 0.02:
        return builder

    band = 0.26
    beam_z0 = -0.20
    inner = step

    def corbel(x: float, y: float, axis: str) -> None:
        """一块托木：墙上的水平顶块 + 一根斜撑，axis 决定贴在哪个面。"""
        if axis == "front":
            builder.add_box((x - 0.07, y - inner, beam_z0), (x + 0.07, 0.02, -0.02), WOOD)
            sweep_box(
                builder,
                (x, y - inner - 0.02, -0.62),
                (x, y - 0.04, beam_z0 + 0.02),
                (1.0, 0.0, 0.0),
                0.10,
                0.09,
                WOOD,
            )
        elif axis == "back":
            builder.add_box((x - 0.07, depth - 0.02, beam_z0), (x + 0.07, depth + inner, -0.02), WOOD)
            sweep_box(
                builder,
                (x, depth + inner + 0.02, -0.62),
                (x, depth + 0.04, beam_z0 + 0.02),
                (1.0, 0.0, 0.0),
                0.10,
                0.09,
                WOOD,
            )

    def corbel_side(y: float, x: float, axis: str) -> None:
        if axis == "left":
            builder.add_box((x - inner, y - 0.07, beam_z0), (0.02, y + 0.07, -0.02), WOOD)
            sweep_box(
                builder,
                (x - inner - 0.02, y, -0.62),
                (x - 0.04, y, beam_z0 + 0.02),
                (0.0, 1.0, 0.0),
                0.10,
                0.09,
                WOOD,
            )
        else:
            builder.add_box((width - 0.02, y - 0.07, beam_z0), (width + inner, y + 0.07, -0.02), WOOD)
            sweep_box(
                builder,
                (width + inner + 0.02, y, -0.62),
                (width + 0.04, y, beam_z0 + 0.02),
                (0.0, 1.0, 0.0),
                0.10,
                0.09,
                WOOD,
            )

    # 封边梁：四边一圈
    builder.add_box((-0.04, -0.06, beam_z0), (width + 0.04, 0.04, 0.02), LOG)
    builder.add_box((-0.04, depth - 0.04, beam_z0), (width + 0.04, depth + 0.06, 0.02), LOG)
    builder.add_box((-0.06, -0.04, beam_z0), (0.04, depth + 0.04, 0.02), LOG)
    builder.add_box((width - 0.04, -0.04, beam_z0), (width + 0.06, depth + 0.04, 0.02), LOG)

    # 托木：前后按 X 均匀，两侧按 Y 均匀（转角处留出位置给四角托木）
    count_x = max(2, int(round(width / spacing)))
    xs = [width * (index + 0.5) / count_x for index in range(count_x)]
    for x in xs:
        corbel(x, 0.0, "front")
        corbel(x, 0.0, "back")
    count_y = max(2, int(round(depth / spacing)))
    ys = [depth * (index + 0.5) / count_y for index in range(count_y)]
    for y in ys:
        corbel_side(y, 0.0, "left")
        corbel_side(y, 0.0, "right")

    # 四角：45° 方向的斜撑托木，收住转角
    for cx, cy, sx, sy in (
        (0.0, 0.0, -1.0, -1.0),
        (width, 0.0, 1.0, -1.0),
        (0.0, depth, -1.0, 1.0),
        (width, depth, 1.0, 1.0),
    ):
        builder.add_box(
            (min(cx, cx + sx * inner) - 0.09, min(cy, cy + sy * inner) - 0.09, beam_z0),
            (max(cx, cx + sx * inner) + 0.09, max(cy, cy + sy * inner) + 0.09, -0.02),
            WOOD,
        )

    # 搁栅端头：从楼板边缘探出来的一排方木
    joist = 0.085
    for x in xs:
        builder.add_box((x - joist * 0.5, -0.16, -0.03), (x + joist * 0.5, 0.02, 0.10), LOG)
        builder.add_box((x - joist * 0.5, depth - 0.02, -0.03), (x + joist * 0.5, depth + 0.16, 0.10), LOG)
    for y in ys:
        builder.add_box((-0.16, y - joist * 0.5, -0.03), (0.02, y + joist * 0.5, 0.10), LOG)
        builder.add_box((width - 0.02, y - joist * 0.5, -0.03), (width + 0.16, y + joist * 0.5, 0.10), LOG)
    return builder
