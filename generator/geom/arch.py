"""中世纪拱形门窗。

两种拱型：

- 尖拱（arch_strips / add_opening_pane）：等边哥特拱，矢高约 0.866 × 跨度；
- 圆拱（round_arch_strips / add_round_arch_pane）：半圆券，矢高约 0.5 × 跨度，
  洞高不足时压成扁圆，读起来是罗曼式的石砌圆拱门。

为了不引入布尔运算，墙体开洞用若干条矩形带逼近拱头，玻璃/门扇则用一条
多边形面片沿圆弧勾勒，既保持墙体网格封闭，又能在视觉上读出拱形轮廓。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .wall_panel import Opening

# 等边尖拱矢高 / 跨度
ARCH_RISE_RATIO = math.sqrt(3.0) * 0.5
STRIP_COUNT = 14
MIN_STRIP = 0.04


def arch_rise(width: float, height: float) -> float:
    """返回拱头矢高；拱头最多占洞高的 60%，避免吞掉整个洞口。"""
    return max(0.18, min(ARCH_RISE_RATIO * width, height * 0.6))


def round_arch_rise(width: float, height: float) -> float:
    """半圆券矢高；洞高不足时按洞高压扁，最低保留 0.16 m。"""
    return max(0.16, min(width * 0.5, height * 0.65))


def _round_half(width: float, rise: float, dz: float) -> float:
    """圆拱在起拱点以上 dz 处的半宽（椭圆插值，dz 越大越窄）。"""
    t = min(1.0, max(0.0, dz / rise))
    return width * 0.5 * math.sqrt(max(0.0, 1.0 - t * t))


def half_span(width: float, dz: float) -> float:
    """起拱点以上 dz 处的半宽；两段圆弧相交处收敛为 0。"""
    return max(0.0, math.sqrt(max(width * width - dz * dz, 0.0)) - width * 0.5)


def arch_strips(op: Opening, steps: int = STRIP_COUNT) -> list[Opening]:
    """把一个尖拱洞口拆成矩形带，供无布尔墙面板切割使用。"""
    width = op.x1 - op.x0
    height = op.z1 - op.z0
    if width < 0.3 or height < 0.4:
        return [op]

    rise = arch_rise(width, height)
    spring = op.z1 - rise
    cx = (op.x0 + op.x1) * 0.5
    strips: list[Opening] = []
    if spring - op.z0 > 0.15:
        strips.append(Opening(op.x0, op.x1, op.z0, spring, op.kind))

    for index in range(steps):
        dz0 = rise * index / steps
        dz1 = rise * (index + 1) / steps
        half = half_span(width, (dz0 + dz1) * 0.5)
        if half * 2 < MIN_STRIP:
            continue
        strips.append(
            Opening(cx - half, cx + half, spring + dz0, min(spring + dz1, op.z1), op.kind)
        )
    return strips


def round_arch_strips(op: Opening, steps: int = 16) -> list[Opening]:
    """把一个半圆拱洞口拆成矩形带；拱头比尖拱平缓，条带可用满默认数量。"""
    width = op.x1 - op.x0
    height = op.z1 - op.z0
    if width < 0.3 or height < 0.4:
        return [op]

    rise = round_arch_rise(width, height)
    spring = op.z1 - rise
    cx = (op.x0 + op.x1) * 0.5
    strips: list[Opening] = []
    if spring - op.z0 > 0.15:
        strips.append(Opening(op.x0, op.x1, op.z0, spring, op.kind))

    for index in range(steps):
        dz0 = rise * index / steps
        dz1 = rise * (index + 1) / steps
        half = _round_half(width, rise, (dz0 + dz1) * 0.5)
        if half * 2 < MIN_STRIP:
            continue
        strips.append(
            Opening(cx - half, cx + half, spring + dz0, min(spring + dz1, op.z1), op.kind)
        )
    return strips


def _dedupe(points: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    result: list[tuple[float, float, float]] = []
    for point in points:
        if result and all(abs(point[i] - result[-1][i]) < 1e-5 for i in range(3)):
            continue
        result.append(point)
    return result


def _arched_pane(
    builder: MeshBuilder,
    op: Opening,
    thickness: float,
    rise: float,
    half_fn,
    samples: int,
    slot: str = "glass",
) -> None:
    """沿拱曲线勾勒的玻璃/门扇面片；rise 与半宽函数决定拱型。"""
    slot = "door" if op.kind == "door" else slot
    y = thickness * (0.45 if op.kind == "door" else 0.5)
    inset = 0.03
    x0, x1 = op.x0 + inset, op.x1 - inset
    z0 = op.z0 + inset
    z1 = op.z1
    width = x1 - x0
    if width < 0.06 or z1 - z0 < 0.08:
        return

    spring = z1 - rise
    if spring <= z0:
        builder.add_face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], slot)
        return

    cx = (x0 + x1) * 0.5
    points: list[tuple[float, float, float]] = [(x0, y, z0), (x0, y, spring)]
    for index in range(1, samples + 1):
        dz = rise * (index / samples) * 0.999
        points.append((cx - half_fn(width, dz), y, spring + dz))
    for index in range(samples, 0, -1):
        dz = rise * (index / samples) * 0.999
        points.append((cx + half_fn(width, dz), y, spring + dz))
    points.append((x1, y, spring))
    points.append((x1, y, z0))

    clean = _dedupe(points)
    if len(clean) >= 3:
        builder.add_face(clean, slot)


def add_opening_pane(
    builder: MeshBuilder,
    op: Opening,
    thickness: float,
    arched: bool = False,
    samples: int = 6,
    slot: str | None = None,
) -> None:
    """给洞口补玻璃或门扇面片；arched 为真时轮廓沿尖拱曲线。"""
    window_slot = slot or "glass"
    if not arched:
        inset = 0.03
        x0, x1 = op.x0 + inset, op.x1 - inset
        z0, z1 = op.z0 + inset, op.z1
        if x1 - x0 < 0.06 or z1 - z0 < 0.08:
            return
        y = thickness * (0.45 if op.kind == "door" else 0.5)
        pane_slot = "door" if op.kind == "door" else window_slot
        builder.add_face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], pane_slot)
        return

    width = op.x1 - op.x0 - 0.06
    _arched_pane(
        builder,
        op,
        thickness,
        arch_rise(width, op.z1 - op.z0),
        half_span,
        samples,
        slot=window_slot,
    )


def add_round_arch_pane(
    builder: MeshBuilder,
    op: Opening,
    thickness: float,
    samples: int = 10,
    slot: str = "glass",
) -> None:
    """给半圆券洞口补门扇/玻璃；弧度比尖拱圆润，采样点更多。"""
    width = op.x1 - op.x0 - 0.06
    rise = round_arch_rise(width, op.z1 - op.z0)

    def half_fn(span: float, dz: float) -> float:
        return _round_half(span, rise, dz)

    _arched_pane(builder, op, thickness, rise, half_fn, samples, slot=slot)

