"""哥特石扶壁（buttress）。

贴在墙外侧的阶梯状石墩：加宽的基座 + 收分墩身 + 向外排水的压顶斜面。
坐标与墙体一致（X 沿墙长、Y=0 为外墙面、Z 自墙脚起算），可直接复用墙体变换。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder

WIDTH = 0.52
PROUD = 0.38
BASE_H = 0.58


def build_buttress(
    height: float,
    tiles: dict[str, float],
    width: float = WIDTH,
    proud: float = PROUD,
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    half = width * 0.5
    shaft_top = max(BASE_H + 0.2, height - 0.42)

    # 基座略宽略厚，墩身向上收分
    builder.add_box(
        (-half - 0.06, -proud - 0.09, 0.0),
        (half + 0.06, 0.02, BASE_H),
        "stone",
    )
    builder.add_box((-half, -proud, BASE_H), (half, 0.02, shaft_top), "stone")

    # 压顶：外沿低、贴墙一侧高，形成排水斜面
    x0, x1 = -half, half
    y_front, y_back = -proud, 0.02
    front = [(x0, y_front, shaft_top), (x1, y_front, shaft_top)]
    back = [(x1, y_back, height), (x0, y_back, height)]
    builder.add_face([front[0], front[1], back[0], back[1]], "stone")
    for x in (x0, x1):
        builder.add_face(
            [
                (x, y_front, shaft_top),
                (x, y_back, height),
                (x, y_back, shaft_top),
            ],
            "stone",
        )
    return builder


def build_pinnacle(
    tiles: dict[str, float],
    height: float = 1.5,
    width: float = 0.5,
    slot: str = "stone",
) -> MeshBuilder:
    """完好的扶壁小尖塔：座石 + 墩身 + 两级收分 + 方锥尖顶 + 顶饰。

    局部坐标：以塔心为原点，z=0 为扶壁顶面。
    """
    builder = MeshBuilder(tiles)
    half = width * 0.5
    base_h = 0.14
    shaft_h = max(0.20, height * 0.30)

    # 座石略宽，压在扶壁压顶上
    builder.add_box(
        (-half * 1.18, -half * 1.18, 0.0), (half * 1.18, half * 1.18, base_h), slot
    )
    builder.add_box((-half, -half, base_h), (half, half, base_h + shaft_h), slot)

    z = base_h + shaft_h
    # 两级收分，把方形墩身过渡到锥体
    for scale, level in ((0.86, height * 0.10), (0.68, height * 0.12)):
        s = half * scale
        builder.add_box((-s, -s, z), (s, s, z + level), slot)
        z += level

    # 方锥尖顶
    s = half * 0.68
    apex = max(z + 0.36, height)
    corners = [(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)]
    for index in range(4):
        builder.add_face(
            [corners[index], corners[(index + 1) % 4], (0.0, 0.0, apex)], slot
        )

    # 顶饰：细石柱 + 短横臂
    builder.add_box((-0.045, -0.045, apex - 0.06), (0.045, 0.045, apex + 0.20), slot)
    builder.add_box(
        (-0.15, -0.03, apex + 0.11), (0.15, 0.03, apex + 0.17), slot
    )
    return builder


def build_finial_cross(
    tiles: dict[str, float],
    height: float = 0.66,
    slot: str = "stone",
) -> MeshBuilder:
    """山尖上的石十字：小座 + 立柱 + 横臂。z=0 为山墙尖。"""
    builder = MeshBuilder(tiles)
    builder.add_box((-0.10, -0.10, 0.0), (0.10, 0.10, 0.13), slot)
    builder.add_box((-0.052, -0.052, 0.13), (0.052, 0.052, height), slot)
    builder.add_box(
        (-0.20, -0.034, height * 0.62), (0.20, 0.034, height * 0.70), slot
    )
    return builder
