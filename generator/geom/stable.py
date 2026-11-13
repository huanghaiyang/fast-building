"""马厩的圆拱开间。

马厩立面的特征是一排并列的圆拱洞口：砖石拱券、木框、下半截挡马门、洞里伸出来的
草料架与草料。这里把「一个开间」做成独立构件，装配阶段按开间数量逐个摆放；
开间宽度就是墙板开间宽度，因此洞口位置与墙板预留的拱券洞完全对齐。

局部坐标与墙板一致：X 沿墙 0..span、Y=0 为墙外饰面（-Y 朝外）、Z 自墙脚起算。
"""

from __future__ import annotations

import math
import random

from ..meshkit import MeshBuilder
from .arch import _round_half, round_arch_rise
from .props import STRAW, WOOD, _box_frame
from .wall_panel import Opening

STONE = "stone"
IRON = "iron"

POST = 0.15
ARCH_SEGMENTS = 9
STALL_DOOR_H = 1.02


def _arch_points(op: Opening, inset: float, samples: int) -> list[tuple[float, float, float]]:
    """沿圆拱券线取一串点（起拱点到拱顶），用于扫掠拱券块。"""
    width = (op.x1 - op.x0) - inset * 2.0
    height = op.z1 - op.z0
    rise = round_arch_rise(width, height)
    spring = op.z1 - rise
    cx = (op.x0 + op.x1) * 0.5
    points: list[tuple[float, float, float]] = []
    for index in range(samples + 1):
        dz = rise * index / samples
        half = _round_half(width, rise, dz) + inset
        points.append((cx - half, 0.0, spring + dz))
    for index in range(samples, -1, -1):
        dz = rise * index / samples
        half = _round_half(width, rise, dz) + inset
        points.append((cx + half, 0.0, spring + dz))
    return points


def _sweep_along(
    builder: MeshBuilder,
    points: list[tuple[float, float, float]],
    y0: float,
    y1: float,
    depth: float,
    slot: str,
) -> None:
    """沿一串点扫一圈矩形截面的拱券块。"""
    for index in range(len(points) - 1):
        a, b = points[index], points[index + 1]
        dx, dz = b[0] - a[0], b[2] - a[2]
        length = math.hypot(dx, dz)
        if length < 1e-4:
            continue
        tangent = (dx / length, 0.0, dz / length)
        normal = (-tangent[2], 0.0, tangent[0])
        center = ((a[0] + b[0]) * 0.5, (y0 + y1) * 0.5, (a[2] + b[2]) * 0.5)
        _box_frame(
            builder,
            center,
            (tangent, (0.0, 1.0, 0.0), normal),
            (length * 0.52, (y1 - y0) * 0.5, depth * 0.5),
            slot,
        )


def build_stable_bay(
    span: float,
    height: float,
    opening: Opening,
    tiles: dict[str, float],
    seed: int = 42,
    hay: bool = True,
    door: bool = True,
) -> MeshBuilder:
    """一个马厩开间：立柱、拱券、挡马门、草料架与草料。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:stable:{opening.x0:.2f}")
    x0, x1 = opening.x0, opening.x1
    z0, z1 = opening.z0, opening.z1

    # 两侧立柱：从墙脚顶到过梁
    for px in (max(0.0, x0 - POST - 0.02), min(span - POST, x1 + 0.02)):
        builder.add_box((px, -0.10, 0.0), (px + POST, 0.02, height), WOOD)
        # 柱脚石墩
        builder.add_box((px - 0.03, -0.13, 0.0), (px + POST + 0.03, 0.03, 0.22), STONE)

    # 过梁：横跨整开间
    builder.add_box((0.0, -0.12, height - 0.20), (span, 0.02, height), WOOD)

    # 拱券：沿券线铺一圈券石
    points = _arch_points(opening, 0.055, ARCH_SEGMENTS)
    _sweep_along(builder, points, -0.10, 0.03, 0.13, STONE)
    # 起拱线：一道横木压住券脚
    rise = round_arch_rise(x1 - x0 - 0.11, z1 - z0)
    spring = z1 - rise
    builder.add_box((x0 - 0.06, -0.12, spring - 0.07), (x1 + 0.06, 0.02, spring + 0.03), WOOD)

    if door:
        # 下半截挡马门：竖板 + 两道横档
        leaf_z1 = min(spring - 0.04, STALL_DOOR_H)
        if leaf_z1 > 0.5:
            planks = max(4, int(round((x1 - x0) / 0.17)))
            plank_w = (x1 - x0) / planks
            for index in range(planks):
                px = x0 + index * plank_w
                builder.add_box(
                    (px + 0.006, -0.115, 0.10),
                    (px + plank_w - 0.006, -0.065, leaf_z1),
                    WOOD,
                )
            for frac in (0.22, 0.78):
                rz = 0.10 + (leaf_z1 - 0.10) * frac
                builder.add_box((x0, -0.13, rz - 0.035), (x1, -0.055, rz + 0.035), WOOD)
            # 门闩与合页
            builder.add_box((x0 + 0.04, -0.14, leaf_z1 - 0.10), (x0 + 0.30, -0.125, leaf_z1 - 0.06), IRON)
            for px in (x0 + 0.02, x1 - 0.10):
                builder.add_box((px, -0.145, leaf_z1 * 0.5 - 0.04), (px + 0.08, -0.13, leaf_z1 * 0.5 + 0.04), IRON)
            # 门槛石
            builder.add_box((x0 - 0.05, -0.34, 0.0), (x1 + 0.05, 0.02, 0.10), STONE)

    # 洞内背板：压到墙厚之外，透出暗色，读成马厩内部的阴影
    builder.add_face(
        [
            (x0 + 0.03, 0.235, z0 + 0.02),
            (x1 - 0.03, 0.235, z0 + 0.02),
            (x1 - 0.03, 0.235, z1 - 0.06),
            (x0 + 0.03, 0.235, z1 - 0.06),
        ],
        "char",
    )

    if hay:
        # 草料架：洞里立两根立柱 + 三道横杆 + 竖棂
        rack_z0 = STALL_DOOR_H + 0.06
        rack_z1 = min(spring + rise * 0.55, rack_z0 + 0.95)
        if rack_z1 - rack_z0 > 0.3:
            for px in (x0 + 0.12, x1 - 0.26):
                builder.add_box((px, -0.30, rack_z0), (px + 0.10, -0.20, rack_z1), WOOD)
            bars = 3
            for index in range(bars):
                bz = rack_z0 + (rack_z1 - rack_z0) * (index + 0.5) / bars
                builder.add_box((x0 + 0.10, -0.31, bz - 0.035), (x1 - 0.10, -0.22, bz + 0.035), WOOD)
            slats = max(4, int((x1 - x0) / 0.20))
            for index in range(slats):
                sx = x0 + 0.14 + (x1 - x0 - 0.3) * index / max(1, slats - 1)
                builder.add_box((sx - 0.022, -0.30, rack_z0), (sx + 0.022, -0.24, rack_z1), WOOD)
            # 草料：从架子后面探出来的草束
            for _ in range(6):
                hx = rnd.uniform(x0 + 0.18, x1 - 0.18)
                hz = rnd.uniform(rack_z0 + 0.1, rack_z1 - 0.1)
                builder.add_box(
                    (hx - 0.06, -0.40, hz - 0.05),
                    (hx + 0.06, -0.28, hz + 0.05),
                    STRAW,
                )
    return builder


def build_tack_room_door(
    span: float,
    height: float,
    tiles: dict[str, float],
    seed: int = 42,
    opening: Opening | None = None,
) -> MeshBuilder:
    """马厩端的鞍具房门：木板门 + 门框 + 小方窗。

    给出 ``opening`` 时按墙板已经挖出的门洞对齐，否则按开间居中估算。
    """
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:tack-door")
    if opening is not None:
        x0, x1 = opening.x0, opening.x1
        door_w = x1 - x0
        z0 = opening.z0
        z1 = opening.z1
    else:
        door_w = min(1.35, span * 0.62)
        cx = span * 0.5
        x0, x1 = cx - door_w * 0.5, cx + door_w * 0.5
        z0 = 0.12
        z1 = min(height - 0.55, 2.35)
    z0 = max(0.02, min(z0, 0.4))
    cx = (x0 + x1) * 0.5

    builder.add_box((x0, -0.10, z0), (x1, 0.02, z1), WOOD)
    planks = max(5, int(door_w / 0.18))
    for index in range(planks):
        px = x0 + index * door_w / planks
        builder.add_box(
            (px + 0.008, -0.115, z0 + 0.04),
            (px + door_w / planks - 0.008, -0.095, z1 - 0.04),
            WOOD,
        )
    for frac in (0.18, 0.82):
        bz = z0 + (z1 - z0) * frac
        builder.add_box((x0 - 0.03, -0.13, bz - 0.04), (x1 + 0.03, -0.10, bz + 0.04), WOOD)
    for frac in (0.3, 0.7):
        bz = z0 + (z1 - z0) * frac
        builder.add_box((x0 - 0.04, -0.14, bz - 0.03), (x0 + 0.16, -0.12, bz + 0.03), IRON)
        builder.add_box((x1 - 0.16, -0.14, bz - 0.03), (x1 + 0.04, -0.12, bz + 0.03), IRON)
    # 门上方小方窗
    wx0, wx1 = cx - 0.34, cx + 0.34
    wz0 = min(height - 0.45, z1 + 0.22)
    builder.add_box((wx0 - 0.05, -0.12, wz0 - 0.05), (wx1 + 0.05, 0.0, wz0 + 0.05), WOOD)
    builder.add_face(
        [(wx0, -0.11, wz0 + 0.03), (wx1, -0.11, wz0 + 0.03), (wx1, -0.11, wz0 + 0.42), (wx0, -0.11, wz0 + 0.42)],
        "glow",
    )
    builder.add_box((wx0 - 0.06, -0.13, wz0 + 0.38), (wx1 + 0.06, 0.0, wz0 + 0.46), WOOD)
    for px in (wx0 - 0.06, wx1 - 0.02):
        builder.add_box((px, -0.13, wz0 + 0.03), (px + 0.08, 0.0, wz0 + 0.42), WOOD)
    builder.add_box((cx - 0.03, -0.14, wz0 + 0.03), (cx + 0.03, -0.02, wz0 + 0.42), WOOD)
    # 石阶
    builder.add_box((x0 - 0.24, -0.52, 0.0), (x1 + 0.24, 0.0, 0.14), STONE)
    builder.add_box((x0 - 0.12, -0.34, 0.14), (x1 + 0.12, 0.0, 0.22), STONE)
    return builder
