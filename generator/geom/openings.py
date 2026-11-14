"""可开合的门扇 / 窗扇。

原点约定：几何以「合页边」为原点——
- X 从 0 沿洞口宽度方向延伸（mirror=True 时向 -X 延伸，用于右扇）；
- Z 从 0（洞口下沿）向上；
- Y 以 0 为中心、厚度向两侧展开。

装配时物体原点放在墙体外表面（局部 -Y 一侧），因此绕节点局部竖轴旋转时
只会向室外打开，不会穿进室内。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder

DOOR = "door"
TRIM = "trim"
GLASS = "glass"
IRON = "iron"


def _box(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z0: float,
    z1: float,
    slot: str,
    mirror: bool = False,
) -> None:
    """按需镜像 X 的小工具：右扇与左扇共用同一套建模代码。"""
    if mirror:
        x0, x1 = -x1, -x0
    builder.add_box((x0, y0, z0), (x1, y1, z1), slot)


def build_door_leaf(
    width: float,
    height: float,
    tiles: dict[str, float],
    thickness: float = 0.06,
) -> MeshBuilder:
    """木板门扇：竖向拼板 + 两道横撑 + 铁门把手（向室外一侧）。"""
    builder = MeshBuilder(tiles)
    w = max(width - 0.04, 0.3)
    h = max(height - 0.03, 0.6)
    half_t = thickness * 0.5

    planks = max(3, min(5, int(round(w / 0.26))))
    gap = 0.008
    plank_w = (w - gap * (planks - 1)) / planks
    for index in range(planks):
        x0 = index * (plank_w + gap)
        _box(builder, x0, x0 + plank_w, -half_t, half_t, 0.0, h, DOOR)

    # 外侧面（-Y）的上下横撑
    brace_h = min(0.16, h * 0.16)
    for z in (h * 0.16, h * 0.66):
        _box(builder, 0.02, w - 0.02, -half_t - 0.035, -half_t, z, z + brace_h, DOOR)

    # 铁门把手（室外侧）
    _box(
        builder,
        w - 0.16,
        w - 0.09,
        -half_t - 0.075,
        -half_t - 0.02,
        h * 0.46,
        h * 0.46 + 0.09,
        IRON,
    )
    return builder


def build_window_sash(
    width: float,
    height: float,
    tiles: dict[str, float],
    thickness: float = 0.055,
    mirror: bool = False,
    half: bool = False,
) -> MeshBuilder:
    """窗扇：四边木框 + 玻璃。

    - ``half=False``：独立单扇窗，中间一道竖梃（两格竖窗）；
    - ``half=True``：对开窗的其中一扇，中间一道横梃（两扇合并后呈田字四格）。
    """
    builder = MeshBuilder(tiles)
    w = max(width - 0.05, 0.2)
    h = max(height - 0.05, 0.25)
    half_t = thickness * 0.5
    frame = 0.06 if half else 0.07

    _box(builder, 0.0, w, -half_t, half_t, 0.0, frame, TRIM, mirror)
    _box(builder, 0.0, w, -half_t, half_t, h - frame, h, TRIM, mirror)
    _box(builder, 0.0, frame, -half_t, half_t, frame, h - frame, TRIM, mirror)
    _box(builder, w - frame, w, -half_t, half_t, frame, h - frame, TRIM, mirror)

    # 玻璃
    glass_t = 0.02
    _box(
        builder,
        frame,
        w - frame,
        -glass_t * 0.5,
        glass_t * 0.5,
        frame,
        h - frame,
        GLASS,
        mirror,
    )

    if half:
        # 对开扇：单道横梃，左右两扇合起来是田字四格
        mid_z = h * 0.5
        _box(
            builder,
            frame,
            w - frame,
            -half_t + 0.004,
            half_t - 0.004,
            mid_z - 0.024,
            mid_z + 0.024,
            TRIM,
            mirror,
        )
    else:
        # 单扇：只做竖梃，避免田字窗被单侧掀开
        mid_x = w * 0.5
        _box(
            builder,
            mid_x - 0.024,
            mid_x + 0.024,
            -half_t + 0.004,
            half_t - 0.004,
            frame,
            h - frame,
            TRIM,
            mirror,
        )
    return builder
