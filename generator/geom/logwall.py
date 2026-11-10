"""原木叠砌墙（log cabin）。

局部坐标：X 沿墙长，Y 从 0（室外）到 2r（室内），Z 向上。

构造思路：
- 每行一根沿 X 的圆木，行距略小于直径，保证行间压叠不漏缝；
- 墙端圆木出挑，与垂直方向的墙交错，形成原木屋特有的转角咬合；
- 洞口处按行断开圆木，再补深色木框与门扇/玻璃，不做布尔运算。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .arch import add_opening_pane
from .wall_panel import Opening

LOG_RADIUS = 0.13
LOG_SEGMENTS = 10
ROW_RATIO = 1.78  # 行距 / 半径，约 0.03 m 的压叠量
FRAME_W = 0.075


def _add_log(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    z_center: float,
    radius: float,
    slot: str,
    cap_left: bool,
    cap_right: bool,
) -> None:
    """一根沿 X 的圆木；UV 的 U 轴对齐木纹方向（圆木轴向）。"""
    if x1 - x0 < 0.04:
        return
    tile = builder.tiles.get(slot, 2.0)
    arc = 2.0 * math.pi * radius
    ring = [
        (
            radius * math.cos(2.0 * math.pi * i / LOG_SEGMENTS),
            radius * math.sin(2.0 * math.pi * i / LOG_SEGMENTS),
        )
        for i in range(LOG_SEGMENTS)
    ]
    for i in range(LOG_SEGMENTS):
        y0, z0 = ring[i]
        y1, z1 = ring[(i + 1) % LOG_SEGMENTS]
        u0 = arc * i / LOG_SEGMENTS / tile
        u1 = arc * (i + 1) / LOG_SEGMENTS / tile
        builder.add_face(
            [
                (x0, radius + y0, z_center + z0),
                (x1, radius + y0, z_center + z0),
                (x1, radius + y1, z_center + z1),
                (x0, radius + y1, z_center + z1),
            ],
            slot,
            uvs=[(x0 / tile, u0), (x1 / tile, u0), (x1 / tile, u1), (x0 / tile, u1)],
        )
    if cap_left:
        builder.add_face([(x0, radius + y, z_center + z) for y, z in ring], slot)
    if cap_right:
        builder.add_face([(x1, radius + y, z_center + z) for y, z in ring], slot)


def _row_spans(
    width: float, z_center: float, radius: float, openings: list[Opening]
) -> list[tuple[float, float, bool, bool]]:
    """把一行圆木按洞口切成若干段，返回 (起点, 终点, 左端需封口, 右端需封口)。"""
    active = [
        op
        for op in openings
        if op.z0 <= z_center + radius * 0.9
        and op.z1 >= z_center - radius * 0.9
        and op.x1 > 0.0
        and op.x0 < width
    ]
    spans: list[tuple[float, float, bool, bool]] = []
    cursor = 0.0
    for op in sorted(active, key=lambda item: item.x0):
        x0 = max(0.0, op.x0)
        x1 = min(width, op.x1)
        if x1 - x0 < 0.02:
            continue
        if x0 - cursor > 0.04:
            spans.append((cursor, x0, cursor > 0.001, True))
        cursor = max(cursor, x1)
    if width - cursor > 0.04:
        spans.append((cursor, width, cursor > 0.001, False))
    return spans


def _add_frame(builder: MeshBuilder, op: Opening, thickness: float) -> None:
    """洞口木框：竖框 + 楣 + 窗台；门洞不设窗台。"""
    builder.add_box(
        (op.x0 - FRAME_W, 0.0, op.z1),
        (op.x1 + FRAME_W, thickness, op.z1 + FRAME_W),
        "trim",
    )
    builder.add_box((op.x0 - FRAME_W, 0.0, op.z0), (op.x0, thickness, op.z1), "trim")
    builder.add_box((op.x1, 0.0, op.z0), (op.x1 + FRAME_W, thickness, op.z1), "trim")
    if op.kind != "door":
        builder.add_box(
            (op.x0 - FRAME_W - 0.03, -0.06, op.z0 - 0.09),
            (op.x1 + FRAME_W + 0.03, thickness, op.z0),
            "trim",
        )


def build_log_wall(
    width: float,
    height: float,
    openings: list[Opening],
    tiles: dict[str, float],
    radius: float = LOG_RADIUS,
    protrude_left: float = 0.0,
    protrude_right: float = 0.0,
) -> MeshBuilder:
    """生成一面原木墙；protrude_* 为墙端圆木出挑长度。"""
    builder = MeshBuilder(tiles)
    thickness = radius * 2.0
    step = radius * ROW_RATIO

    clean: list[Opening] = []
    for op in openings:
        x0 = max(0.05, min(op.x0, width - 0.05))
        x1 = max(x0 + 0.05, min(op.x1, width - 0.05))
        z0 = max(0.0, min(op.z0, height - 0.05))
        z1 = max(z0 + 0.05, min(op.z1, height))
        if x1 - x0 < 0.2 or z1 - z0 < 0.2:
            continue
        clean.append(Opening(x0, x1, z0, z1, op.kind))

    rows = max(1, int(math.floor((height - 2.0 * radius) / step)) + 1)
    top = radius
    for index in range(rows):
        z_center = radius + index * step
        if z_center + radius > height + 0.01:
            break
        top = z_center + radius
        for xa, xb, cut_left, cut_right in _row_spans(width, z_center, radius, clean):
            x0 = xa - (protrude_left if xa <= 0.001 else 0.0)
            x1 = xb + (protrude_right if xb >= width - 0.001 else 0.0)
            _add_log(
                builder,
                x0,
                x1,
                z_center,
                radius,
                "log",
                cut_left or x0 < -0.001,
                cut_right or x1 > width + 0.001,
            )

    # 墙顶压梁，补齐最后一行圆木到墙高之间的空隙
    if height - top > 0.02:
        builder.add_box((0.0, 0.0, top), (width, thickness, height), "trim")

    for op in clean:
        _add_frame(builder, op, thickness)
        add_opening_pane(builder, op, thickness, arched=False)
    return builder
