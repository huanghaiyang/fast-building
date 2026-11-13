"""谷仓的双开木板大门。

参考图里仓库与马厩都有一樘顶天立地的双开板门：竖拼木板、三道横档、Z 形斜撑、
两路熟铁箍和一对门轴，门框两侧再压立柱与过梁。组件尺寸按门洞给定，装配阶段
直接摆在墙板已经挖出的门洞上，把原本那块平板门扇盖住。

局部坐标：X 沿墙 0..span、Y=0 为墙外饰面（-Y 朝外）、Z 自墙脚起算。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder
from .gallery import sweep_box
from .props import WOOD

LOG = "log"
IRON = "iron"
STONE = "stone"


def build_barn_door(
    span: float,
    height: float,
    tiles: dict[str, float],
    seed: int = 42,
    stone_threshold: bool = True,
) -> MeshBuilder:
    """双开仓门：门框 + 两扇拼板门 + 铁箍 + 石门槛。"""
    builder = MeshBuilder(tiles)
    if span < 0.8 or height < 1.2:
        return builder

    post = 0.16
    leaf_gap = 0.012
    half = (span - leaf_gap) * 0.5

    # 两侧门柱与过梁
    builder.add_box((-post, -0.14, 0.0), (0.0, 0.03, height + 0.14), LOG)
    builder.add_box((span, -0.14, 0.0), (span + post, 0.03, height + 0.14), LOG)
    builder.add_box((-post - 0.05, -0.17, height), (span + post + 0.05, 0.04, height + 0.16), LOG)
    # 柱脚石墩
    for x in (-post - 0.02, span - 0.02):
        builder.add_box((x, -0.16, 0.0), (x + post * 1.12, 0.04, 0.20), STONE)

    for leaf in (0, 1):
        x0 = leaf * (half + leaf_gap)
        x1 = x0 + half
        # 竖拼木板
        planks = max(4, int(round(half / 0.19)))
        plank_w = half / planks
        for index in range(planks):
            px = x0 + index * plank_w
            builder.add_box(
                (px + 0.006, -0.115, 0.06),
                (px + plank_w - 0.006, -0.055, height - 0.04),
                WOOD,
            )
        # 三道横档
        for frac in (0.16, 0.5, 0.84):
            rz = 0.06 + (height - 0.10) * frac
            builder.add_box((x0 + 0.005, -0.14, rz - 0.055), (x1 - 0.005, -0.10, rz + 0.055), LOG)
        # Z 形斜撑（每扇门一根主斜杆）
        if leaf == 0:
            sweep_box(
                builder,
                (x0 + 0.10, -0.15, 0.22),
                (x1 - 0.10, -0.10, height * 0.52),
                (0.0, 1.0, 0.0),
                0.11,
                0.05,
                LOG,
            )
            sweep_box(
                builder,
                (x0 + 0.10, -0.15, height * 0.52),
                (x1 - 0.10, -0.10, height - 0.18),
                (0.0, 1.0, 0.0),
                0.11,
                0.05,
                LOG,
            )
        else:
            sweep_box(
                builder,
                (x1 - 0.10, -0.15, 0.22),
                (x0 + 0.10, -0.10, height * 0.52),
                (0.0, 1.0, 0.0),
                0.11,
                0.05,
                LOG,
            )
            sweep_box(
                builder,
                (x1 - 0.10, -0.15, height * 0.52),
                (x0 + 0.10, -0.10, height - 0.18),
                (0.0, 1.0, 0.0),
                0.11,
                0.05,
                LOG,
            )

    # 熟铁箍：两路横贯两扇门的铁带 + 门轴
    for frac in (0.28, 0.72):
        bz = 0.10 + (height - 0.2) * frac
        builder.add_box((0.02, -0.135, bz - 0.042), (span - 0.02, -0.118, bz + 0.042), IRON)
        for x in (0.0, span * 0.5 - 0.03, span - 0.06):
            builder.add_box((x, -0.15, bz - 0.05), (x + 0.06, -0.128, bz + 0.05), IRON)
    # 每扇门两只门轴吊耳
    for leaf_x in (0.04, span - 0.12):
        for frac in (0.2, 0.6):
            bz = 0.10 + height * frac
            builder.add_box((leaf_x, -0.17, bz - 0.05), (leaf_x + 0.09, -0.13, bz + 0.05), IRON)

    # 门闩与拉手
    mid = span * 0.5
    builder.add_box((mid - 0.30, -0.16, height * 0.46), (mid + 0.30, -0.135, height * 0.46 + 0.075), IRON)
    builder.add_box((mid + 0.12, -0.19, height * 0.34), (mid + 0.20, -0.16, height * 0.34 + 0.26), IRON)

    if stone_threshold:
        builder.add_box((-0.14, -0.46, 0.0), (span + 0.14, 0.02, 0.12), STONE)
        builder.add_box((-0.02, -0.30, 0.12), (span + 0.02, 0.0, 0.19), STONE)
    return builder


def build_door_hood(
    span: float,
    height: float,
    tiles: dict[str, float],
) -> MeshBuilder:
    """仓门上的小披檐：两根斜撑托一块短坡瓦顶，遮住门楣。"""
    builder = MeshBuilder(tiles)
    depth = 0.86
    rise = 0.30
    z = height + 0.16
    over = 0.18
    for x in (-0.02, span + 0.02):
        builder.add_box((x - 0.05, -depth, z - 0.10), (x + 0.05, 0.0, z + 0.06), LOG)
    # 两个斜面（简单两片带厚度的斜板）
    for side, y0, y1 in ((1.0, -depth - over, -0.02),):
        top = [
            (span * 0.5 - 0.02, y0, z - 0.02),
            (span * 0.5 - 0.02, y1, z + rise),
            (span * 0.5 + 0.02, y1, z + rise),
            (span * 0.5 + 0.02, y0, z - 0.02),
        ]
        low = [(x, y, zz - 0.09) for x, y, zz in top]
        builder.add_face(top, "roof")
        builder.add_face(list(reversed(low)), "roof")
        for index in range(4):
            a, b = top[index], top[(index + 1) % 4]
            c, d = low[(index + 1) % 4], low[index]
            builder.add_face([a, b, c, d], "roof")
    # 斜撑
    for x in (0.06, span - 0.06):
        sweep_box(
            builder,
            (x, -0.02, z - 0.55),
            (x, -depth + 0.06, z - 0.04),
            (1.0, 0.0, 0.0),
            0.09,
            0.07,
            LOG,
        )
    return builder
