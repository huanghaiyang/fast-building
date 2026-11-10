"""直跑楼梯：用一组踏步方块拼出楼梯实体。

MVP 只生成一部从一层通往二层的室内楼梯；上层楼板不做洞口，
楼梯顶部与楼板底面相接，从建筑外部看具备完整的空间关系。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder


def build_straight_stair(
    x0: float,
    y0: float,
    width: float,
    total_rise: float,
    total_run: float,
    base_z: float,
    tiles: dict[str, float],
) -> tuple[MeshBuilder, int]:
    """返回楼梯网格与踏步数量。"""
    builder = MeshBuilder(tiles)
    steps = max(4, int(round(total_rise / 0.18)))
    rise = total_rise / steps
    going = total_run / steps

    for i in range(steps):
        # 每级踏步都是从地面起算的实体块，块间界面被相邻块遮挡
        builder.add_box(
            (x0, y0 + i * going, base_z),
            (x0 + width, y0 + (i + 1) * going, base_z + (i + 1) * rise - 0.002),
            "trim",
        )
    return builder, steps
