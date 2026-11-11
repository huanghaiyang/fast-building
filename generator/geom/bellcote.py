"""石钟塔（bellcote / bell gable）。

立在屋脊上的石构钟架：带尖拱开口的薄墙、两侧凸出的小柱，顶端是残缺的
山尖石帽，用来还原废墟教堂正立面上那座断顶的钟塔。

局部坐标：X 沿塔宽（0..width）、Y 为厚度（0 为正面）、Z 自塔脚起算。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder
from .arch import arch_strips
from .wall_panel import Opening, build_wall_panel

WIDTH = 1.5
HEIGHT = 2.6
THICKNESS = 0.45


def build_bellcote(
    tiles: dict[str, float],
    width: float = WIDTH,
    height: float = HEIGHT,
    thickness: float = THICKNESS,
) -> MeshBuilder:
    # 主墙：尖拱开口，不补玻璃，从塔下能看穿
    cx = width * 0.5
    op = Opening(cx - 0.31, cx + 0.31, 0.95, min(height - 0.16, 2.35), "window")
    builder = build_wall_panel(
        width, height, thickness, arch_strips(op), tiles, glazing=False, edge_slot="stone"
    )

    # 两侧小柱：略凸出墙面
    for x0 in (0.0, width - 0.18):
        builder.add_box((x0, -0.05, 0.0), (x0 + 0.18, thickness + 0.02, height + 0.06), "stone")

    # 压顶石
    builder.add_box((-0.05, -0.07, height), (width + 0.05, thickness + 0.04, height + 0.12), "stone")

    # 破损山尖：不规则多边形沿厚度拉成棱柱
    top = height + 0.12
    profile = [
        (0.14, 0.0),
        (width - 0.14, 0.0),
        (width - 0.32, 0.34),
        (width - 0.62, 0.16),
        (width - 0.88, 0.56),
        (0.42, 0.24),
    ]
    front = [(x, -0.02, top + z) for x, z in profile]
    back = [(x, thickness + 0.02, top + z) for x, z in profile]
    builder.add_face(front, "stone")
    builder.add_face(list(reversed(back)), "stone")
    count = len(profile)
    for index in range(count):
        a = front[index]
        b = front[(index + 1) % count]
        builder.add_face([a, b, back[(index + 1) % count], back[index]], "stone")

    return builder
