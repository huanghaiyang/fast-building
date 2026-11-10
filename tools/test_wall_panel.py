"""墙面板几何质量测试（纯 Python，无需 Blender）。

断言：
1. 实体面构成的封闭壳体每条边恰好被两个面共享（无破洞、无 T 型接缝）；
2. 包围盒与输入尺寸一致；
3. 玻璃/门扇等开放面片单独计入，不参与流形判定。

运行：
    D:\\thirdparty\\venvs\\fastbuild\\Scripts\\python.exe tools\\test_wall_panel.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generator.geom.wall_panel import Opening, build_wall_panel  # noqa: E402

TILES = {"facade": 2.0, "trim": 2.5, "glass": 1.0, "door": 2.0}


def check_manifold(name: str, width: float, height: float, openings: list[Opening]) -> bool:
    builder = build_wall_panel(width, height, 0.24, openings, TILES)
    edges: Counter[tuple[int, int]] = Counter()
    for face, slot in zip(builder.faces, builder.face_slots):
        if slot in ("glass", "door"):
            continue
        for i in range(len(face)):
            a, b = face[i], face[(i + 1) % len(face)]
            edges[(min(a, b), max(a, b))] += 1

    broken = [edge for edge, count in edges.items() if count != 2]
    xs = [vertex[0] for vertex in builder.verts]
    zs = [vertex[2] for vertex in builder.verts]
    bbox_ok = abs(min(xs)) < 1e-6 and abs(max(xs) - width) < 1e-6
    bbox_ok = bbox_ok and abs(min(zs)) < 1e-6 and abs(max(zs) - height) < 1e-6

    ok = not broken and bbox_ok and len(builder.faces) > 0
    open_faces = sum(1 for slot in builder.face_slots if slot in ("glass", "door"))
    print(
        f"[{'PASS' if ok else 'FAIL'}] {name}: 实体面 {len(edges)}, "
        f"非流形边 {len(broken)}, bbox {max(xs):.2f}×{max(zs):.2f}, 门窗面片 {open_faces}"
    )
    if not ok:
        print(f"  断裂边样例: {broken[:5]}")
    return ok


def main() -> int:
    cases = [
        ("无洞口实墙", 4.0, 2.8, []),
        (
            "单窗洞",
            4.0,
            2.8,
            [Opening(1.3, 2.7, 0.9, 2.5, "window")],
        ),
        (
            "门洞 + 窗洞",
            5.0,
            2.8,
            [
                Opening(0.4, 1.45, 0.0, 2.2, "door"),
                Opening(2.6, 4.0, 0.9, 2.5, "window"),
            ],
        ),
        (
            "顶到墙顶的窗洞",
            3.6,
            2.8,
            [Opening(0.8, 2.4, 1.0, 2.8, "window")],
        ),
        (
            "贴边窗洞",
            4.0,
            2.8,
            [Opening(0.0, 1.4, 0.9, 2.5, "window")],
        ),
    ]

    results = [check_manifold(*case) for case in cases]
    print(f"\n{sum(results)}/{len(results)} 用例通过")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
