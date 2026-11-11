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


# --------------------------------------------------------------------------- 玫瑰窗
ROSE_SEGMENTS = 16
ROSE_FOILS = 8
ROSE_Y_FRONT = -0.075
ROSE_Y_BACK = 0.02


def _slab(
    builder: MeshBuilder,
    corners: list[tuple[float, float]],
    slot: str,
    y_front: float = ROSE_Y_FRONT,
    y_back: float = ROSE_Y_BACK,
) -> None:
    """把 XZ 平面上的四边形沿墙厚方向拉成一块石板。"""
    front = [(x, y_front, z) for x, z in corners]
    back = [(x, y_back, z) for x, z in corners]
    builder.add_face(front, slot)
    builder.add_face(list(reversed(back)), slot)
    for index in range(4):
        a = front[index]
        b = front[(index + 1) % 4]
        a2 = back[index]
        b2 = back[(index + 1) % 4]
        builder.add_face([a, b, b2, a2], slot)


def _ring(
    builder: MeshBuilder,
    cx: float,
    cz: float,
    radius: float,
    width: float,
    slot: str,
    segments: int = ROSE_SEGMENTS,
    alternate: float = 0.0,
    y_front: float = ROSE_Y_FRONT,
    y_back: float = ROSE_Y_BACK,
) -> None:
    """圆环石券；alternate > 0 时相邻券石外沿深浅交替，读成一块块分开的石头。"""
    inner = max(0.02, radius - width)
    for index in range(segments):
        t0 = 2.0 * math.pi * index / segments
        t1 = 2.0 * math.pi * (index + 1) / segments
        outer = radius - (alternate if index % 2 else 0.0)
        corners = [
            (cx + inner * math.cos(t0), cz + inner * math.sin(t0)),
            (cx + outer * math.cos(t0), cz + outer * math.sin(t0)),
            (cx + outer * math.cos(t1), cz + outer * math.sin(t1)),
            (cx + inner * math.cos(t1), cz + inner * math.sin(t1)),
        ]
        _slab(builder, corners, slot, y_front, y_back)


def _bar(
    builder: MeshBuilder,
    a: tuple[float, float],
    b: tuple[float, float],
    half: float,
    slot: str,
) -> None:
    """两点之间的窄石条（窗棂/辐条）。"""
    dx, dz = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dz)
    if length < 1e-4:
        return
    nx, nz = -dz / length * half, dx / length * half
    corners = [
        (a[0] - nx, a[1] - nz),
        (a[0] + nx, a[1] + nz),
        (b[0] + nx, b[1] + nz),
        (b[0] - nx, b[1] - nz),
    ]
    _slab(builder, corners, slot)


def build_rose_window(
    tiles: dict[str, float],
    radius: float,
    slot: str = "stone",
    glass_slot: str = "glass",
    foils: int = ROSE_FOILS,
) -> MeshBuilder:
    """嵌在山墙里的圆形玫瑰窗：外圈券石 + 八瓣窗棂 + 深色玻璃。

    局部坐标与尖拱窗一致：X 以窗心为 0，Y=0 为山墙面（负方向朝外），
    Z=0 为窗心。
    """
    builder = MeshBuilder(tiles)
    if radius < 0.45:
        return builder

    ring_w = max(0.12, radius * 0.17)
    # 玻璃：退进石券内圈，读成一圈有厚度的洞口
    glass: list[tuple[float, float, float]] = []
    r_glass = radius - ring_w + 0.02
    for index in range(32):
        t = 2.0 * math.pi * index / 32
        glass.append((r_glass * math.cos(t), -0.018, r_glass * math.sin(t)))
    builder.add_face(glass, glass_slot)

    # 外券：深色玻璃外一圈券石，再压一道薄薄的出挑线脚
    _ring(builder, 0.0, 0.0, radius, ring_w, slot, alternate=ring_w * 0.24)
    _ring(
        builder,
        0.0,
        0.0,
        radius + 0.09,
        0.07,
        slot,
        y_front=ROSE_Y_FRONT - 0.03,
        y_back=ROSE_Y_FRONT + 0.02,
    )

    # 窗棂：中心圆盘 + 放射辐条 + 辐条之间的圆形花瓣
    hub = radius * 0.20
    _ring(builder, 0.0, 0.0, hub, hub * 0.42, slot, segments=10, y_front=-0.06)
    petal_r = radius * 0.14
    orbit = radius * 0.60
    spoke_end = radius - ring_w * 0.55
    for index in range(foils):
        t = 2.0 * math.pi * index / foils
        _bar(
            builder,
            (hub * 0.6 * math.cos(t), hub * 0.6 * math.sin(t)),
            (spoke_end * math.cos(t), spoke_end * math.sin(t)),
            max(0.024, radius * 0.022),
            slot,
        )
        px, pz = orbit * math.cos(t + math.pi / foils), orbit * math.sin(t + math.pi / foils)
        _ring(builder, px, pz, petal_r, petal_r * 0.42, slot, segments=8, y_front=-0.055)

    return builder
