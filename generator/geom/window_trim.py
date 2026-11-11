"""洞口木装修：窗框、十字窗棂、窗台与门槛石。

墙体现有的做法只在洞口里贴一层玻璃/门板，近景看是「墙上的洞」。参考图里的
小窗都带深色木框和十字窗棂，山墙下还有一道薄窗台，这里把这些贴面构件补上。

坐标与墙体完全一致（X 沿墙长、Y 0~thickness 为墙厚方向、Z 自墙脚起算），
所以可以直接复用同一个对象变换。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .arch import arch_rise, half_span, round_arch_rise
from .wall_panel import Opening

FRAME = 0.075
T_PROUD = 0.045
T_EMBED = 0.02
# 拱券石环：外沿比洞口半径再放大这么多，盖住条带近似留下的锯齿
RING_WIDTH = 0.20
RING_INNER = 0.11
RING_BLOCKS = 15


def _box(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z0: float,
    z1: float,
    slot: str,
) -> None:
    if x1 - x0 < 0.02 or z1 - z0 < 0.02:
        return
    builder.add_box((x0, y0, z0), (x1, y1, z1), slot)


def _round_arch_ring(
    builder: MeshBuilder,
    op: Opening,
    thickness: float,
    slot: str,
) -> None:
    """沿半圆券排一圈券石，同时把洞口的锯齿状内壁包成光滑拱腹。

    券石从墙面出挑 5 cm，并向洞内收进 RING_INNER，等于给拱线做了一道
    贯通墙厚的石券：外圈深浅交替像一块块券石，内圈则是平滑的拱腹，
    正好盖住矩形条带近似留下的台阶。
    """
    width = op.x1 - op.x0
    rise = round_arch_rise(width, op.z1 - op.z0)
    spring = op.z1 - rise
    if spring - op.z0 < 0.15:
        return

    cx = (op.x0 + op.x1) * 0.5
    a = width * 0.5
    y_front = -0.055
    y_back = max(0.02, thickness - 0.02)

    def point(t: float, offset: float) -> tuple[float, float]:
        return (cx + (a + offset) * math.cos(t), spring + (rise + offset) * math.sin(t))

    for index in range(RING_BLOCKS):
        t0 = math.pi * index / RING_BLOCKS
        t1 = math.pi * (index + 1) / RING_BLOCKS
        # 交替出挑深浅，读成一块块分开的券石
        outer = RING_WIDTH * (0.78 if index % 2 else 1.0)
        inner = -RING_INNER
        corners = [
            point(t0, inner),
            point(t0, outer),
            point(t1, outer),
            point(t1, inner),
        ]
        front = [(x, y_front, z) for x, z in corners]
        back = [(x, y_back, z) for x, z in corners]
        builder.add_face(front, slot)
        builder.add_face(list(reversed(back)), slot)
        for k in range(4):
            a0 = front[k]
            a1 = front[(k + 1) % 4]
            b0 = back[k]
            b1 = back[(k + 1) % 4]
            builder.add_face([a0, a1, b1, b0], slot)


def _pointed_arch_ring(
    builder: MeshBuilder,
    op: Opening,
    thickness: float,
    slot: str,
) -> None:
    """沿尖拱线排一圈券石；外圈深浅交替，内圈收进洞内盖住条带台阶。

    与半圆券的做法一致：券石贯通墙厚，起拱点以上把锯齿状的拱腹包圆。
    """
    width = op.x1 - op.x0
    rise = arch_rise(width, op.z1 - op.z0)
    spring = op.z1 - rise
    if spring - op.z0 < 0.15:
        return

    cx = (op.x0 + op.x1) * 0.5
    steps = 8
    outline: list[tuple[float, float]] = []
    for index in range(steps + 1):
        dz = rise * index / steps
        outline.append((cx - half_span(width, dz), spring + dz))
    for index in range(steps - 1, -1, -1):
        dz = rise * index / steps
        outline.append((cx + half_span(width, dz), spring + dz))

    y_front = -0.055
    y_back = max(0.02, thickness - 0.02)
    for index in range(len(outline) - 1):
        p0, p1 = outline[index], outline[index + 1]
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        length = math.hypot(dx, dz)
        if length < 1e-4:
            continue
        nx, nz = -dz / length, dx / length
        mx = (p0[0] + p1[0]) * 0.5 - cx
        mz = (p0[1] + p1[1]) * 0.5 - spring
        if nx * mx + nz * mz < 0.0:
            nx, nz = -nx, -nz

        outer = RING_WIDTH * (0.78 if index % 2 else 1.0)
        inner = -RING_INNER
        corners = [
            (p0[0] + nx * inner, p0[1] + nz * inner),
            (p0[0] + nx * outer, p0[1] + nz * outer),
            (p1[0] + nx * outer, p1[1] + nz * outer),
            (p1[0] + nx * inner, p1[1] + nz * inner),
        ]
        front = [(x, y_front, z) for x, z in corners]
        back = [(x, y_back, z) for x, z in corners]
        builder.add_face(front, slot)
        builder.add_face(list(reversed(back)), slot)
        for k in range(4):
            a0 = front[k]
            a1 = front[(k + 1) % 4]
            b0 = back[k]
            b1 = back[(k + 1) % 4]
            builder.add_face([a0, a1, b1, b0], slot)


def build_opening_trims(
    openings: list[Opening],
    thickness: float,
    tiles: dict[str, float],
    mullions: bool = True,
    sill: bool = True,
    slot: str = "trim",
    arched: bool = False,
    round_arch: bool = False,
    arch_ring: bool = False,
) -> MeshBuilder:
    builder = MeshBuilder(tiles)

    for op in openings:
        # 拱形洞口不做矩形上框与横窗棂，否则会压在拱头上；立框只做到起拱点
        head = op.z1
        if arched:
            rise = (
                round_arch_rise(op.x1 - op.x0, op.z1 - op.z0)
                if round_arch
                else arch_rise(op.x1 - op.x0, op.z1 - op.z0)
            )
            head = op.z1 - rise
            if head - op.z0 < 0.2:
                head = op.z1

        # 边框，略压在墙面上
        _box(builder, op.x0 - FRAME, op.x1 + FRAME, -T_PROUD, T_EMBED,
             op.z0 - FRAME, op.z0, slot)
        if not arched:
            _box(builder, op.x0 - FRAME, op.x1 + FRAME, -T_PROUD, T_EMBED,
                 op.z1, op.z1 + FRAME, slot)
        _box(builder, op.x0 - FRAME, op.x0, -T_PROUD, T_EMBED, op.z0, head, slot)
        _box(builder, op.x1, op.x1 + FRAME, -T_PROUD, T_EMBED, op.z0, head, slot)

        if arched and round_arch:
            _round_arch_ring(builder, op, thickness, slot)
        elif arched and arch_ring:
            _pointed_arch_ring(builder, op, thickness, slot)

        if op.kind == "door":
            # 门槛石
            _box(builder, op.x0 - FRAME - 0.05, op.x1 + FRAME + 0.05,
                 -0.42, 0.02, 0.0, 0.1, "stone")
            continue

        if mullions:
            cx = (op.x0 + op.x1) * 0.5
            cz = (op.z0 + op.z1) * 0.5
            # 窗棂嵌进洞内，接到玻璃面；尖拱窗只保留竖向中梃
            _box(builder, cx - 0.028, cx + 0.028, -T_PROUD, thickness * 0.5,
                 op.z0, head, slot)
            if not arched:
                _box(builder, op.x0, op.x1, -T_PROUD, thickness * 0.5,
                     cz - 0.026, cz + 0.026, slot)

        if sill:
            _box(builder, op.x0 - FRAME - 0.06, op.x1 + FRAME + 0.06,
                 -0.1, 0.02, op.z0 - 0.07, op.z0, slot)

    return builder
