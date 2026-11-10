"""无布尔运算的墙面板生成。

核心思路：把墙面看成「矩形挖矩形洞」，按洞口的 x/z 边界切成网格单元，
只为实体单元生成前/后面；当单元的四邻是洞口或墙外时生成侧壁。
这样既不会产生布尔运算的脏几何，也能自然得到窗洞侧壁与墙端封口。

坐标约定（局部空间）：
- X：墙长度方向；
- Y：厚度方向，0 为外侧饰面，thickness 为内侧；
- Z：高度方向。
"""

from __future__ import annotations

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
) -> MeshBuilder:
    builder = MeshBuilder(tiles)

    clean: list[Opening] = []
    for op in openings:
        x0 = max(0.03, min(op.x0, width - 0.03))
        x1 = max(x0 + 0.05, min(op.x1, width - 0.03))
        z0 = max(0.0, min(op.z0, height - 0.05))
        z1 = max(z0 + 0.05, min(op.z1, height - 0.0))
        if x1 - x0 < 0.1 or z1 - z0 < 0.1:
            continue
        clean.append(Opening(x0, x1, z0, z1, op.kind))

    xs = {0.0, width}
    zs = {0.0, height}
    for op in clean:
        xs.update((op.x0, op.x1))
        zs.update((op.z0, op.z1))
    xs_sorted = _merge_close(xs)
    zs_sorted = _merge_close(zs)

    def is_solid(ix: int, iz: int) -> bool:
        if ix < 0 or iz < 0 or ix >= len(xs_sorted) - 1 or iz >= len(zs_sorted) - 1:
            return False
        cx = (xs_sorted[ix] + xs_sorted[ix + 1]) * 0.5
        cz = (zs_sorted[iz] + zs_sorted[iz + 1]) * 0.5
        for op in clean:
            if op.x0 < cx < op.x1 and op.z0 < cz < op.z1:
                return False
        return True

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

            # 四邻：邻单元不存在（墙外）或为洞口时，补侧壁
            if not is_solid(ix - 1, iz):
                builder.add_face(
                    [(x0, 0.0, z0), (x0, thickness, z0), (x0, thickness, z1), (x0, 0.0, z1)],
                    "trim",
                )
            if not is_solid(ix + 1, iz):
                builder.add_face(
                    [(x1, thickness, z0), (x1, 0.0, z0), (x1, 0.0, z1), (x1, thickness, z1)],
                    "trim",
                )
            if not is_solid(ix, iz - 1):
                builder.add_face(
                    [(x0, 0.0, z0), (x1, 0.0, z0), (x1, thickness, z0), (x0, thickness, z0)],
                    "trim",
                )
            if not is_solid(ix, iz + 1):
                builder.add_face(
                    [(x0, thickness, z1), (x1, thickness, z1), (x1, 0.0, z1), (x0, 0.0, z1)],
                    "trim",
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
            slot = "door" if op.kind == "door" else "glass"
            builder.add_face(
                [(gx0, y, gz0), (gx1, y, gz0), (gx1, y, gz1), (gx0, y, gz1)],
                slot,
            )

    return builder
