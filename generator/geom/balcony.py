"""阳台：悬挑楼板 + 三面栏杆。"""

from __future__ import annotations

from ..meshkit import MeshBuilder


def build_balcony(
    x0: float,
    x1: float,
    y_front: float,
    z: float,
    depth: float,
    tiles: dict[str, float],
    rail_height: float = 1.0,
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    y_back = y_front - depth
    slab_thickness = 0.16

    builder.add_box(
        (x0, y_back, z),
        (x1, y_front, z + slab_thickness),
        "trim",
    )

    rail_t = 0.06
    top = z + slab_thickness + rail_height
    # 前栏杆
    builder.add_box(
        (x0, y_front - rail_t, z + slab_thickness),
        (x1, y_front, top),
        "trim",
    )
    # 两侧栏杆
    builder.add_box(
        (x0, y_back, z + slab_thickness),
        (x0 + rail_t, y_front, top),
        "trim",
    )
    builder.add_box(
        (x1 - rail_t, y_back, z + slab_thickness),
        (x1, y_front, top),
        "trim",
    )
    return builder
