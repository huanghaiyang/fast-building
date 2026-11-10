"""楼板生成。

楼板是简单的长方体；如果指定了楼梯洞口，则拆成四块互不重叠的板，
避免使用布尔运算，也方便后续做流形校验。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder


def build_slab(
    width: float,
    depth: float,
    z: float,
    thickness: float,
    tiles: dict[str, float],
    hole: tuple[float, float, float, float] | None = None,
) -> MeshBuilder:
    """生成一块楼板。

    ``hole`` 为 ``(x0, y0, x1, y1)`` 的楼梯洞口；为 ``None`` 时生成整块板。
    """
    builder = MeshBuilder(tiles)
    z0, z1 = z, z + thickness

    if hole is None:
        builder.add_box((0.0, 0.0, z0), (width, depth, z1), "trim")
        return builder

    hx0, hy0, hx1, hy1 = hole
    hx0 = max(0.1, min(hx0, width - 0.1))
    hx1 = max(hx0 + 0.2, min(hx1, width - 0.1))
    hy0 = max(0.1, min(hy0, depth - 0.1))
    hy1 = max(hy0 + 0.2, min(hy1, depth - 0.1))

    # 四块板：左右两条 + 中间前后两段
    builder.add_box((0.0, 0.0, z0), (hx0, depth, z1), "trim")
    builder.add_box((hx1, 0.0, z0), (width, depth, z1), "trim")
    builder.add_box((hx0, 0.0, z0), (hx1, hy0, z1), "trim")
    builder.add_box((hx0, hy1, z0), (hx1, depth, z1), "trim")
    return builder
