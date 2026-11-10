"""中世纪砖石烟囱。"""

from __future__ import annotations

from ..meshkit import MeshBuilder


def build_chimney(
    width: float,
    depth: float,
    height: float,
    tiles: dict[str, float],
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    builder.add_box((-width * 0.5, -depth * 0.5, 0.0), (width * 0.5, depth * 0.5, height), "trim")
    # 压顶
    builder.add_box(
        (-width * 0.5 - 0.12, -depth * 0.5 - 0.12, height),
        (width * 0.5 + 0.12, depth * 0.5 + 0.12, height + 0.14),
        "trim",
    )
    return builder
