"""山墙尖拱窗（lancet）。

山墙面是屋顶自带的三角面，无法像墙板那样挖洞；这里改为「贴面」做法：
石窗台 + 两侧石边框 + 沿拱线扫出的石券边 + 内凹一层的玻璃面，近看是一扇
嵌在三角山墙里的哥特细长窗，远看轮廓清晰。

局部坐标：
- X：以窗中心为 0；
- Y：0 为山墙面，负方向朝外（与墙板约定一致，可直接复用对象变换）；
- Z：0 为窗台底面。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .arch import arch_rise, half_span

JAMB = 0.13
BAND = 0.15
PROUD = 0.075
EMBED = 0.015
GLASS_INSET = 0.02


def _outline(cx: float, width: float, spring: float, rise: float, samples: int = 9):
    """尖拱轮廓：左立边 -> 左半拱 -> 顶点 -> 右半拱 -> 右立边。"""
    points = [(cx - width * 0.5, spring)]
    for index in range(1, samples + 1):
        dz = rise * index / samples
        points.append((cx - half_span(width, dz), spring + dz))
    for index in range(samples - 1, 0, -1):
        dz = rise * index / samples
        points.append((cx + half_span(width, dz), spring + dz))
    points.append((cx + width * 0.5, spring))
    return points


def _band(
    builder: MeshBuilder,
    p0: tuple[float, float],
    p1: tuple[float, float],
    center: tuple[float, float],
    band: float,
    slot: str,
) -> None:
    """沿一段轮廓线向外扫出一块厚度为 band 的石券（矩形截面，Y 向拉伸）。"""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dz)
    if length < 1e-4:
        return
    # 法线取背离拱心的方向，保证券边加在洞口外侧
    nx, nz = -dz / length, dx / length
    mx, mz = (p0[0] + p1[0]) * 0.5 - center[0], (p0[1] + p1[1]) * 0.5 - center[1]
    if nx * mx + nz * mz < 0.0:
        nx, nz = -nx, -nz
    corners = [
        (p0[0], p0[1]),
        (p1[0], p1[1]),
        (p1[0] + nx * band, p1[1] + nz * band),
        (p0[0] + nx * band, p0[1] + nz * band),
    ]
    front = [(x, -PROUD, z) for x, z in corners]
    back = [(x, EMBED, z) for x, z in corners]
    builder.add_face(front, slot)
    builder.add_face(list(reversed(back)), slot)
    for index in range(4):
        a = corners[index]
        b = corners[(index + 1) % 4]
        builder.add_face(
            [(a[0], -PROUD, a[1]), (b[0], -PROUD, b[1]), (b[0], EMBED, b[1]), (a[0], EMBED, a[1])],
            slot,
        )


def build_lancet(
    tiles: dict[str, float],
    width: float,
    height: float,
    slot: str = "stone",
    glass_slot: str = "glass",
    lights: int = 2,
) -> MeshBuilder:
    """一扇嵌在山墙里的尖拱窗；width 为洞口净宽，height 为窗台到拱顶。"""
    builder = MeshBuilder(tiles)
    if width < 0.4 or height < 0.8:
        return builder

    cx = 0.0
    rise = arch_rise(width, height)
    spring = height - rise

    # 玻璃面：轮廓沿拱线，略收进石框内，读成有厚度的窗洞
    glass: list[tuple[float, float, float]] = [(cx - width * 0.5 + 0.03, -GLASS_INSET, 0.04)]
    for index in range(1, 9):
        dz = rise * index / 9 * 0.995
        glass.append((cx - half_span(width, dz) * 0.94, -GLASS_INSET, spring + dz))
    for index in range(8, 0, -1):
        dz = rise * index / 9 * 0.995
        glass.append((cx + half_span(width, dz) * 0.94, -GLASS_INSET, spring + dz))
    glass.append((cx + width * 0.5 - 0.03, -GLASS_INSET, 0.04))
    builder.add_face(glass, glass_slot)

    # 窗台
    builder.add_box(
        (-width * 0.5 - JAMB - 0.06, -PROUD - 0.03, -0.14),
        (width * 0.5 + JAMB + 0.06, EMBED, 0.02),
        slot,
    )
    # 两侧立框
    for sign in (-1.0, 1.0):
        x_in = cx + sign * width * 0.5
        x_out = x_in + sign * JAMB
        builder.add_box(
            (min(x_in, x_out), -PROUD, -0.02),
            (max(x_in, x_out), EMBED, spring),
            slot,
        )

    # 拱券：沿轮廓向外扫一圈石边，两端与立框搭接
    outline = _outline(cx, width, spring, rise)
    center = (cx, spring)
    for index in range(len(outline) - 1):
        _band(builder, outline[index], outline[index + 1], center, BAND, slot)

    # 竖中梃：把窗口分成两联，压在玻璃前面
    if lights >= 2:
        builder.add_box(
            (cx - 0.028, -0.055, 0.0),
            (cx + 0.028, -GLASS_INSET - 0.005, spring + rise * 0.45),
            slot,
        )

    return builder
