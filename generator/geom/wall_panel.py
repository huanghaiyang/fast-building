"""无布尔运算的墙面板生成。

核心思路：把墙面看成「矩形挖矩形洞」，按洞口的 x/z 边界切成网格单元，
只为实体单元生成前/后面；当单元的四邻是洞口或墙外时生成侧壁。
这样既不会产生布尔运算的脏几何，也能自然得到窗洞侧壁与墙端封口。

坐标约定（局部空间）：
- X：墙长度方向；
- Y：厚度方向，0 为外侧饰面，thickness 为内侧；
- Z：高度方向。

残墙模式（top_profile）在此之上再给每段 X 一个不同的墙顶高度：
墙顶因此变成参差的断口，网格仍然只由直边单元组成。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..meshkit import MeshBuilder


@dataclass(frozen=True)
class Opening:
    """墙面上的矩形洞口（局部坐标，单位米）。"""

    x0: float
    x1: float
    z0: float
    z1: float
    kind: str = "window"  # window | door


def _merge_close(values: set[float], eps: float = 2e-4) -> list[float]:
    """合并间距小于 eps 的坐标，避免生成零厚度的网格单元。"""
    merged: list[float] = []
    for value in sorted(values):
        if merged and value - merged[-1] < eps:
            continue
        merged.append(value)
    return merged


def build_wall_panel(
    width: float,
    height: float,
    thickness: float,
    openings: list[Opening],
    tiles: dict[str, float],
    glazing: bool = True,
    edge_slot: str = "trim",
    top_profile: list[tuple[float, float, float]] | None = None,
    window_slot: str = "glass",
) -> MeshBuilder:
    builder = MeshBuilder(tiles)

    clean: list[Opening] = []
    for op in openings:
        x0 = max(0.03, min(op.x0, width - 0.03))
        x1 = max(x0 + 0.02, min(op.x1, width - 0.03))
        z0 = max(0.0, min(op.z0, height - 0.05))
        z1 = max(z0 + 0.02, min(op.z1, height - 0.0))
        if x1 - x0 < 0.02 or z1 - z0 < 0.02:
            continue
        clean.append(Opening(x0, x1, z0, z1, op.kind))

    xs = {0.0, width}
    zs = {0.0, height}
    for op in clean:
        xs.update((op.x0, op.x1))
        zs.update((op.z0, op.z1))

    # 残墙：把每段墙顶高度并进网格，保证每个单元完整落在断口的一侧
    profile = [
        (max(0.0, x0), min(width, x1), min(height, max(0.25, top)))
        for x0, x1, top in (top_profile or [])
    ]
    for x0, x1, top in profile:
        xs.update((x0, x1))
        zs.add(top)
    xs_sorted = _merge_close(xs)
    zs_sorted = _merge_close(zs)

    def top_at(x: float) -> float:
        for x0, x1, top in profile:
            if x0 - 1e-4 <= x <= x1 + 1e-4:
                return top
        return height

    def in_grid(ix: int, iz: int) -> bool:
        return 0 <= ix < len(xs_sorted) - 1 and 0 <= iz < len(zs_sorted) - 1

    def is_solid(ix: int, iz: int) -> bool:
        if not in_grid(ix, iz):
            return False
        cx = (xs_sorted[ix] + xs_sorted[ix + 1]) * 0.5
        cz = (zs_sorted[iz] + zs_sorted[iz + 1]) * 0.5
        if cz > top_at(cx):
            return False
        for op in clean:
            if op.x0 < cx < op.x1 and op.z0 < cz < op.z1:
                return False
        return True

    def side_slot(ix: int, iz: int) -> str:
        """墙板外缘（转角、墙顶、墙脚）用外墙材质，只有洞口侧壁才用 edge_slot。"""
        return "facade" if not in_grid(ix, iz) else edge_slot

    for ix in range(len(xs_sorted) - 1):
        x0, x1 = xs_sorted[ix], xs_sorted[ix + 1]
        for iz in range(len(zs_sorted) - 1):
            if not is_solid(ix, iz):
                continue
            z0, z1 = zs_sorted[iz], zs_sorted[iz + 1]

            # 前表面（外侧，y=0）与后表面（室内，y=thickness）
            builder.add_face(
                [(x0, 0.0, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x0, 0.0, z1)],
                "facade",
            )
            builder.add_face(
                [(x1, thickness, z0), (x0, thickness, z0), (x0, thickness, z1), (x1, thickness, z1)],
                "facade",
            )

            # 四邻：墙板外缘（转角、墙顶墙脚）用外墙材质封口，只有洞口才用 edge_slot
            if not is_solid(ix - 1, iz):
                builder.add_face(
                    [(x0, 0.0, z0), (x0, thickness, z0), (x0, thickness, z1), (x0, 0.0, z1)],
                    side_slot(ix - 1, iz),
                )
            if not is_solid(ix + 1, iz):
                builder.add_face(
                    [(x1, thickness, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x1, thickness, z1)],
                    side_slot(ix + 1, iz),
                )
            if not is_solid(ix, iz - 1):
                builder.add_face(
                    [(x0, 0.0, z0), (x1, 0.0, z0), (x1, thickness, z0), (x0, thickness, z0)],
                    side_slot(ix, iz - 1),
                )
            if not is_solid(ix, iz + 1):
                builder.add_face(
                    [(x0, thickness, z1), (x1, thickness, z1), (x1, 0.0, z1), (x0, 0.0, z1)],
                    side_slot(ix, iz + 1),
                )

    if glazing:
        for op in clean:
            mx = 0.03
            mz = 0.03
            gx0, gx1 = op.x0 + mx, op.x1 - mx
            gz0, gz1 = op.z0 + mz, op.z1 - mz
            if gx1 - gx0 < 0.06 or gz1 - gz0 < 0.06:
                continue
            y = thickness * (0.45 if op.kind == "door" else 0.5)
            slot = "door" if op.kind == "door" else window_slot
            builder.add_face(
                [(gx0, y, gz0), (gx1, y, gz0), (gx1, y, gz1), (gx0, y, gz1)],
                slot,
            )

    return builder


def ruin_top_profile(
    width: float,
    height: float,
    openings: list[Opening],
    key: str,
    min_keep: float = 0.62,
) -> list[tuple[float, float, float]]:
    """残墙顶轮廓：转角压得高、中段塌得低，偶发塌到半墙的深缺口。

    返回 (x0, x1, top) 分段；洞口上沿会自动抬到过梁高度，避免窗洞顶悬空。
    """
    rnd = random.Random(f"{key}:ruin-top")
    count = max(4, int(round(width / 0.66)))
    segments: list[list[float]] = []
    level = height * rnd.uniform(0.9, 0.98)
    for index in range(count):
        x0 = width * index / count
        x1 = width * (index + 1) / count
        edge = min(index, count - 1 - index)
        # 靠近墙角的一两片保留较多，中段塌得更狠
        cap = 1.0 - (1.0 - min_keep) * min(1.0, edge / 1.6)
        target = height * cap * rnd.uniform(0.9, 1.02)
        level = level * 0.35 + target * 0.65
        top = min(height, max(height * 0.45, level))
        if rnd.random() < 0.16:
            top = max(height * 0.45, top - rnd.uniform(0.5, 1.0))
        segments.append([x0, x1, top])

    for op in openings:
        need = min(height, op.z1 + 0.3)
        for segment in segments:
            if segment[1] > op.x0 - 0.3 and segment[0] < op.x1 + 0.3:
                segment[2] = max(segment[2], need)

    return [(x0, x1, top) for x0, x1, top in segments]
