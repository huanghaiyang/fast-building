"""悬挑店招（hanging shop sign）。

客栈门旁从墙面挑出一根木臂，臂端用两根吊杆挂一块木牌，臂下补一根斜撑。
局部坐标：y=0 为墙面（向外为负），z=0 为挑臂顶面。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder
from .gallery import sweep_box

ARM_OUT = 1.04
ARM_THICK = 0.12
BOARD_W = 0.84
BOARD_H = 0.70
BOARD_TOP = -0.28


def build_shop_sign(tiles: dict[str, float]) -> MeshBuilder:
    builder = MeshBuilder(tiles)

    # 挑臂：从墙面伸出
    builder.add_box((-0.07, -ARM_OUT, 0.0), (0.07, 0.02, ARM_THICK), "trim")
    # 斜撑：墙面低处撑到挑臂中段
    sweep_box(
        builder,
        (0.0, -0.04, -0.62),
        (0.0, -0.66, -0.03),
        (1.0, 0.0, 0.0),
        0.09,
        0.09,
        "trim",
    )

    # 两根吊杆把木牌吊在臂端
    for x in (-0.30, 0.26):
        builder.add_box((x, -0.99, BOARD_TOP), (x + 0.045, -0.93, 0.0), "trim")

    # 木牌 + 上下压条
    builder.add_box(
        (-BOARD_W * 0.5, -1.0, BOARD_TOP - BOARD_H),
        (BOARD_W * 0.5, -0.94, BOARD_TOP),
        "door",
    )
    builder.add_box(
        (-BOARD_W * 0.5 - 0.02, -1.02, BOARD_TOP - 0.07),
        (BOARD_W * 0.5 + 0.02, -0.92, BOARD_TOP),
        "trim",
    )
    builder.add_box(
        (-BOARD_W * 0.5 - 0.02, -1.02, BOARD_TOP - BOARD_H),
        (BOARD_W * 0.5 + 0.02, -0.92, BOARD_TOP - BOARD_H + 0.07),
        "trim",
    )
    return builder
