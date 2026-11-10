"""中世纪木筋墙（half-timbering）外露木构架。

木构架是贴在墙体外侧的装饰性实体梁：角柱、洞口两侧的边柱、上下横梁与
斜撑。梁的截面为矩形并略微凸出墙面（伸出 0.06 m），因此不会与墙板共面，
也不影响墙体本身的封闭性。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder
from .wall_panel import Opening

BEAM_W = 0.15
BEAM_PROUD = 0.06
BEAM_EMBED = 0.015
MIN_GAP = 0.12


def _box(builder: MeshBuilder, x0: float, x1: float, z0: float, z1: float) -> None:
    if x1 - x0 < 0.03 or z1 - z0 < 0.03:
        return
    builder.add_box((x0, -BEAM_PROUD, z0), (x1, BEAM_EMBED, z1), "trim")


def _bar(
    builder: MeshBuilder,
    x0: float,
    z0: float,
    x1: float,
    z1: float,
    bar_w: float = 0.13,
) -> None:
    """沿 XZ 平面任意方向的斜撑：沿垂直于走向的方向扫掠出矩形截面。"""
    dx, dz = x1 - x0, z1 - z0
    length = math.hypot(dx, dz)
    if length < 0.1:
        return
    nx, nz = -dz / length * bar_w * 0.5, dx / length * bar_w * 0.5
    corners = [
        (x0 + nx, z0 + nz),
        (x1 + nx, z1 + nz),
        (x1 - nx, z1 - nz),
        (x0 - nx, z0 - nz),
    ]
    y_front, y_back = -BEAM_PROUD, BEAM_EMBED
    front = [(x, y_front, z) for x, z in corners]
    back = [(x, y_back, z) for x, z in corners]
    builder.add_face(front, "trim")
    builder.add_face(list(reversed(back)), "trim")
    for index in range(4):
        a = corners[index]
        b = corners[(index + 1) % 4]
        builder.add_face(
            [
                (a[0], y_front, a[1]),
                (b[0], y_front, b[1]),
                (b[0], y_back, b[1]),
                (a[0], y_back, a[1]),
            ],
            "trim",
        )


def _gaps(width: float, openings: list[Opening]) -> list[tuple[float, float]]:
    """把墙面按洞口占位切成若干空白段，用于布置斜撑。"""
    blocked = sorted(
        (max(0.0, op.x0 - BEAM_W), min(width, op.x1 + BEAM_W)) for op in openings
    )
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in blocked:
        if start - cursor > MIN_GAP:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if width - cursor > MIN_GAP:
        gaps.append((cursor, width))
    return gaps


def build_timber_frame(
    width: float,
    height: float,
    openings: list[Opening],
    tiles: dict[str, float],
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    top = height - BEAM_W

    # 角柱与洞口边柱
    _box(builder, 0.0, BEAM_W, 0.0, height)
    _box(builder, width - BEAM_W, width, 0.0, height)
    for op in openings:
        _box(builder, op.x0 - 0.03 - BEAM_W, op.x0 - 0.03, 0.0, height)
        _box(builder, op.x1 + 0.03, op.x1 + 0.03 + BEAM_W, 0.0, height)

    # 上横梁通长；下横梁在落地洞口处断开
    _box(builder, 0.0, width, top, height)
    blocked = [op for op in openings if op.z0 < 0.2]
    cursor = 0.0
    for op in sorted(blocked, key=lambda item: item.x0):
        if op.x0 - cursor > 0.05:
            _box(builder, cursor, op.x0, 0.0, BEAM_W)
        cursor = max(cursor, op.x1)
    if width - cursor > 0.05:
        _box(builder, cursor, width, 0.0, BEAM_W)

    # 空白段内的 45° 斜撑
    gaps = _gaps(width, openings)
    for index, (start, end) in enumerate(gaps):
        span = end - start - 0.2
        if span < 0.45:
            continue
        run = min(span, height - BEAM_W * 2)
        left = index % 2 == 0
        x_from = start + 0.1 if left else end - 0.1 - run
        x_to = x_from + run
        _bar(builder, x_from, BEAM_W + 0.04, x_to, BEAM_W + 0.04 + run)
        # 反向短斜撑，形成对称的 V 形受力外观
        x2_from = start + 0.1 if not left else end - 0.1 - run
        _bar(builder, x2_from, height - BEAM_W - 0.04, x2_from + run, height - BEAM_W - 0.04 - run)

    return builder
