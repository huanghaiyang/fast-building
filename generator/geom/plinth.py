"""毛石勒脚。

沿建筑四周生成一圈毛石基座：正面按门洞位置留缺口，可选在门前加一级石阶。
局部坐标与楼板/屋顶一致（0..width / 0..depth）。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder


def _segments(
    start: float, end: float, gaps: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """按缺口切分一段区间。"""
    result: list[tuple[float, float]] = []
    cursor = start
    for g0, g1 in sorted(gaps):
        g0 = max(start, g0)
        g1 = min(end, g1)
        if g1 <= g0:
            continue
        if g0 - cursor > 0.05:
            result.append((cursor, g0))
        cursor = max(cursor, g1)
    if end - cursor > 0.05:
        result.append((cursor, end))
    return result


def build_plinth(
    width: float,
    depth: float,
    top_z: float,
    height: float,
    thickness: float,
    tiles: dict[str, float],
    gaps: list[tuple[float, float]] | None = None,
    step: tuple[float, float] | None = None,
) -> MeshBuilder:
    """毛石勒脚环带；gaps 为正面需要避开门洞的 X 区间。"""
    builder = MeshBuilder(tiles)
    margin = 0.10
    z0 = top_z - height
    y_front0, y_front1 = -margin, -margin + thickness
    y_back0, y_back1 = depth + margin - thickness, depth + margin
    x_left0, x_left1 = -margin, -margin + thickness
    x_right0, x_right1 = width + margin - thickness, width + margin

    for a, b in _segments(-margin, width + margin, list(gaps or [])):
        builder.add_box((a, y_front0, z0), (b, y_front1, top_z), "stone")
    builder.add_box((-margin, y_back0, z0), (width + margin, y_back1, top_z), "stone")
    builder.add_box((x_left0, y_front1, z0), (x_left1, y_back0, top_z), "stone")
    builder.add_box((x_right0, y_front1, z0), (x_right1, y_back0, top_z), "stone")

    if step is not None:
        sx0, sx1 = step
        builder.add_box((sx0, -0.62, z0), (sx1, -margin, z0 + height * 0.62), "stone")
    return builder
