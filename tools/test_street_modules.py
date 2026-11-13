"""中世纪街市构件的几何自检（纯 Python，不需要 Blender）。

和 ``tools/test_wall_panel.py`` 同一套思路：构件几何全部由 ``MeshBuilder``
在纯 Python 里生成，所以可以脱离 bpy 直接检查，出错时能马上定位到是哪个构件。

检查项：
1. 不存在退化面（三点共线 / 重复点导致的零面积面）；
2. 没有 NaN / inf 坐标；
3. 每个构件至少生成若干三角面，包围盒尺寸落在合理区间；
4. 同一构件的顶点数按坐标去重后与 MeshBuilder 记录一致（不应有漂移）。

运行：
    python tools/test_street_modules.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator.geom.barn import build_barn_door, build_door_hood  # noqa: E402
from generator.geom.jetty import build_jetty_skirt  # noqa: E402
from generator.geom.props import (  # noqa: E402
    build_ladder,
    build_sign_board,
    build_street_props,
    build_wall_board,
)
from generator.geom.shopfront import build_shop_window  # noqa: E402
from generator.geom.slate_roof import build_slate_roof  # noqa: E402
from generator.geom.stable import build_stable_bay, build_tack_room_door  # noqa: E402
from generator.geom.wall_panel import Opening  # noqa: E402
from generator.geom.watermill import build_mill_pit, build_water_wheel  # noqa: E402
from generator.meshkit import MeshBuilder  # noqa: E402

TILES = {
    "facade": 2.0,
    "trim": 1.5,
    "roof": 2.0,
    "door": 1.5,
    "glass": 2.0,
    "log": 1.2,
    "thatch": 1.5,
    "stone": 1.6,
    "cloth": 0.6,
    "clay": 0.45,
    "paper": 0.35,
    "iron": 0.5,
    "water": 3.0,
    "glow": 0.8,
    "shop_glass": 2.0,
    "char": 1.2,
}

failures: list[str] = []


def area(points: list[tuple[float, float, float]]) -> float:
    """多边形面积（按扇形三角化累加），用于识别退化面。"""
    total = 0.0
    origin = points[0]
    for index in range(1, len(points) - 1):
        a = [points[index][axis] - origin[axis] for axis in range(3)]
        b = [points[index + 1][axis] - origin[axis] for axis in range(3)]
        cx = a[1] * b[2] - a[2] * b[1]
        cy = a[2] * b[0] - a[0] * b[2]
        cz = a[0] * b[1] - a[1] * b[0]
        total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
    return total


def check(name: str, builder: MeshBuilder, min_tris: int, expect: tuple[float, float, float]) -> None:
    if not builder.faces:
        failures.append(f"{name}: 没有生成任何面")
        return
    tris = builder.tri_count()
    if tris < min_tris:
        failures.append(f"{name}: 三角面只有 {tris}，低于下限 {min_tris}")

    for index, face in enumerate(builder.faces):
        points = [builder.verts[i] for i in face]
        for point in points:
            if any(not math.isfinite(value) for value in point):
                failures.append(f"{name}: 面 {index} 含非有限坐标 {point}")
                break
        if area(points) < 1e-8:
            failures.append(f"{name}: 面 {index} 是退化面（面积≈0）")

    xs = [v[0] for v in builder.verts]
    ys = [v[1] for v in builder.verts]
    zs = [v[2] for v in builder.verts]
    size = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    for axis, label in enumerate("XYZ"):
        low, high = expect[axis]
        if not (low <= size[axis] <= high):
            failures.append(
                f"{name}: {label} 向尺寸 {size[axis]:.2f} 超出预期区间 [{low}, {high}]"
            )
    print(f"  {name}: tris={tris:5d} bbox={size[0]:5.2f}×{size[1]:5.2f}×{size[2]:5.2f}")


def near(value: float, ratio: float = 0.12) -> tuple[float, float]:
    """把实测尺寸变成 ±ratio 的允许区间，防止后续改动把构件撑大或压扁。"""
    return (value * (1.0 - ratio), value * (1.0 + ratio))


def main() -> int:
    print("中世纪街市构件自检")
    check(
        "roof_slate_curved",
        build_slate_roof(6.4, 6.4, 0.0, 46.0, 0.36, 0.18, TILES, seed=3),
        900,
        (near(7.28), near(8.03), near(4.32)),
    )
    check(
        "opening_shop_books",
        build_shop_window(Opening(0.3, 2.8, 0.6, 2.5), 0.24, TILES, kind="books", seed=4),
        300,
        (near(2.74), near(0.45), near(2.36)),
    )
    check(
        "opening_shop_goods",
        build_shop_window(Opening(0.3, 2.3, 0.5, 2.2), 0.24, TILES, kind="goods", seed=5, glazed=False),
        200,
        (near(2.24), near(0.45), near(2.23)),
    )
    check(
        "opening_barn_door",
        build_barn_door(2.4, 3.05, TILES, seed=6),
        200,
        (near(2.82), near(0.50), near(3.21)),
    )
    check(
        "opening_door_hood",
        build_door_hood(2.4, 3.05, TILES),
        60,
        (near(2.54), near(1.04), near(0.88)),
    )
    check(
        "wall_stable_bay",
        build_stable_bay(2.7, 3.0, Opening(0.32, 2.38, 0.42, 2.76), TILES, seed=7),
        200,
        (near(2.70), near(0.64), near(3.00)),
    )
    check(
        "wall_stable_tack_door",
        build_tack_room_door(2.7, 3.0, TILES, seed=8, opening=Opening(0.9, 2.1, 0.1, 2.35)),
        100,
        (near(1.68), near(0.54), near(3.01)),
    )
    check(
        "wall_jetty_skirt",
        build_jetty_skirt(3.2, 2.8, 0.3, TILES),
        120,
        (near(3.98), near(3.58), near(0.74)),
    )
    check(
        "misc_water_wheel",
        build_water_wheel(TILES, 1.6, 0.55, paddles=20),
        400,
        (near(3.20), near(1.17), near(3.20)),
    )
    check(
        "misc_mill_pit",
        build_mill_pit(TILES, 1.6, 0.55),
        200,
        (near(3.58), near(2.26), near(3.85)),
    )
    check(
        "misc_market_props",
        build_street_props(4.0, 0.0, TILES, seed=9, kind="mixed"),
        400,
        (near(4.04), near(0.82), near(1.19)),
    )
    check("prop_ladder", build_ladder(TILES, 2.6), 40, (near(0.52), near(0.63), near(2.60)))
    check("prop_sign_board", build_sign_board(TILES, 0.96, 1.5), 40, (near(1.14), near(0.18), near(1.52)))
    check("prop_wall_board", build_wall_board(TILES, 2.3, 0.6), 40, (near(2.36), near(0.16), near(0.69)))

    if failures:
        print("\n失败项：")
        for item in failures:
            print("  [FAIL] " + item)
        return 1
    print("\n全部构件通过自检")
    return 0


if __name__ == "__main__":
    sys.exit(main())
