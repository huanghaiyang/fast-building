"""可开合的门扇 / 窗扇。

原点约定：几何以「合页边」为原点——
- X 从 0 向洞宽方向延伸；
- Z 从 0（洞口下沿）向上；
- Y 以 0 为中心、厚度向两侧展开（装配时物体放到墙体厚度中线）。

这样在 GLB 里只要绕节点局部竖轴旋转，门/窗就会绕合页开合，
无需额外骨骼或动画数据（前端按 extras 里的 fb_kind / fb_open_deg 驱动）。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder

DOOR = "door"
TRIM = "trim"
GLASS = "glass"
IRON = "iron"


def build_door_leaf(
    width: float,
    height: float,
    tiles: dict[str, float],
    thickness: float = 0.06,
) -> MeshBuilder:
    """木板门扇：竖向拼板 + 两道横撑 + 铁门把手。"""
    builder = MeshBuilder(tiles)
    w = max(width - 0.04, 0.3)
    h = max(height - 0.03, 0.6)
    half_t = thickness * 0.5

    planks = max(3, min(5, int(round(w / 0.26))))
    gap = 0.008
    plank_w = (w - gap * (planks - 1)) / planks
    for index in range(planks):
        x0 = index * (plank_w + gap)
        builder.add_box((x0, -half_t, 0.0), (x0 + plank_w, half_t, h), DOOR)

    # 外侧面（局部 -Y 为室外侧）的上下横撑
    brace_h = min(0.16, h * 0.16)
    for z in (h * 0.16, h * 0.66):
        builder.add_box((0.02, -half_t - 0.035, z), (w - 0.02, -half_t, z + brace_h), DOOR)

    # 铁门把手
    builder.add_box(
        (w - 0.16, -half_t - 0.075, h * 0.46),
        (w - 0.09, -half_t - 0.02, h * 0.46 + 0.09),
        IRON,
    )
    return builder


def build_window_sash(
    width: float,
    height: float,
    tiles: dict[str, float],
    thickness: float = 0.055,
) -> MeshBuilder:
    """窗扇：四边木框 + 中挺十字 + 玻璃。"""
    builder = MeshBuilder(tiles)
    w = max(width - 0.05, 0.25)
    h = max(height - 0.05, 0.25)
    half_t = thickness * 0.5
    frame = 0.07

    # 四边框
    builder.add_box((0.0, -half_t, 0.0), (w, half_t, frame), TRIM)
    builder.add_box((0.0, -half_t, h - frame), (w, half_t, h), TRIM)
    builder.add_box((0.0, -half_t, frame), (frame, half_t, h - frame), TRIM)
    builder.add_box((w - frame, -half_t, frame), (w, half_t, h - frame), TRIM)

    # 玻璃
    glass_t = 0.02
    builder.add_box(
        (frame, -glass_t * 0.5, frame),
        (w - frame, glass_t * 0.5, h - frame),
        GLASS,
    )

    # 中挺十字
    mid_x = w * 0.5
    builder.add_box(
        (mid_x - 0.025, -half_t + 0.004, frame),
        (mid_x + 0.025, half_t - 0.004, h - frame),
        TRIM,
    )
    mid_z = h * 0.5
    builder.add_box(
        (frame, -half_t + 0.004, mid_z - 0.025),
        (w - frame, half_t - 0.004, mid_z + 0.025),
        TRIM,
    )
    return builder
