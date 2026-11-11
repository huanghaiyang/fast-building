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
