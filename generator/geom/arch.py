"""中世纪尖拱（等边哥特拱）门窗。

几何依据：等边尖拱以对侧起拱点为圆心、跨度为半径，矢高约为 0.866 × 跨度。
为了不引入布尔运算，墙体开洞用若干条矩形带逼近拱头，玻璃/门扇则用一条
多边形面片沿两段圆弧勾勒，既保持墙体网格封闭，又能在视觉上读出尖拱轮廓。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .wall_panel import Opening

# 等边尖拱矢高 / 跨度
ARCH_RISE_RATIO = math.sqrt(3.0) * 0.5
STRIP_COUNT = 6
MIN_STRIP = 0.08


def arch_rise(width: float, height: float) -> float:
    """返回拱头矢高；拱头最多占洞高的 60%，避免吞掉整个洞口。"""
    return max(0.18, min(ARCH_RISE_RATIO * width, height * 0.6))


def _half_span(width: float, dz: float) -> float:
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
        half = _half_span(width, (dz0 + dz1) * 0.5)
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


def add_opening_pane(
    builder: MeshBuilder,
    op: Opening,
    thickness: float,
    arched: bool = False,
    samples: int = 6,
) -> None:
    """给洞口补玻璃或门扇面片；arched 为真时轮廓沿尖拱曲线。"""
    slot = "door" if op.kind == "door" else "glass"
    y = thickness * (0.45 if op.kind == "door" else 0.5)
    inset = 0.03
    x0, x1 = op.x0 + inset, op.x1 - inset
    z0 = op.z0 + inset
    z1 = op.z1
    if x1 - x0 < 0.06 or z1 - z0 < 0.08:
        return

    if not arched:
        builder.add_face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], slot)
        return

    width = x1 - x0
    rise = arch_rise(width, z1 - z0)
    spring = z1 - rise
    cx = (x0 + x1) * 0.5
    points: list[tuple[float, float, float]] = [(x0, y, z0), (x0, y, spring)]
    for index in range(1, samples + 1):
        dz = rise * (index / samples) * 0.999
        points.append((cx - _half_span(width, dz), y, spring + dz))
    for index in range(samples, 0, -1):
        dz = rise * (index / samples) * 0.999
        points.append((cx + _half_span(width, dz), y, spring + dz))
    points.append((x1, y, spring))
    points.append((x1, y, z0))

    clean = _dedupe(points)
    if len(clean) >= 3:
        builder.add_face(clean, slot)
