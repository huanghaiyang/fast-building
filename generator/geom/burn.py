"""烧毁的半木构农舍。

参考图的三件事：

1. 灰泥墙大面积剥落，露出深色的木架与炭化底层；
2. 双坡屋顶只剩半边：一坡残留茅草、一坡残留石瓦，上部大面积缺失；
3. 露出的椽条、檩条与山墙木架全部烧成炭黑色，屋脊从中折断。

坐标约定与 build_gable_roof 一致：原点在檐口角部，x∈[0,width]、y∈[0,depth]，
z 为墙顶（檐口）标高。
"""

from __future__ import annotations

import math
import random

from ..meshkit import MeshBuilder
from .roof import _beam, _slab, _surface


# --------------------------------------------------------------------------- 剥落灰泥
def _prism(
    builder: MeshBuilder,
    points: list[tuple[float, float]],
    y0: float,
    y1: float,
    slot: str,
) -> None:
    """把 x-z 平面上的多边形挤成一块薄片，贴在墙面上。"""
    builder.add_face([(x, y0, z) for x, z in points], slot)
    builder.add_face([(x, y1, z) for x, z in reversed(points)], slot)
    for index in range(len(points)):
        a = points[index]
        b = points[(index + 1) % len(points)]
        builder.add_face(
            [(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])],
            slot,
        )


def build_scorch_patches(
    builder: MeshBuilder,
    width: float,
    height: float,
    openings,
    thickness: float,
    seed: int = 0,
    slot: str = "char",
) -> None:
    """在墙面上撒不规则的炭化斑块，读作剥落的灰泥与烧黑的木底。

    斑块用两三个低频正弦叠加出一个毛边轮廓，不再用交替长短半径（那样像星星）。
    """
    rnd = random.Random(f"{seed}:scorch")
    count = max(2, int(round(width * height * 0.14)))
    placed = 0
    attempts = 0
    while placed < count and attempts < count * 16:
        attempts += 1
        # 竖向偏长：剥落的灰泥沿木架柱距成条成片往下掉
        patch_w = rnd.uniform(0.55, min(1.9, width * 0.6))
        patch_h = rnd.uniform(0.8, min(2.4, height * 0.75))
        bottom_limit = patch_h * 0.5 + 0.16
        top_limit = height - patch_h * 0.5 - 0.08
        if top_limit <= bottom_limit:
            continue
        cx = rnd.uniform(patch_w * 0.5 + 0.06, width - patch_w * 0.5 - 0.06)
        # 下重上轻：火烧从地面往上蔓延
        cz = bottom_limit + (top_limit - bottom_limit) * rnd.random() ** 1.6
        left, right = cx - patch_w * 0.5, cx + patch_w * 0.5
        bottom, top = cz - patch_h * 0.5, cz + patch_h * 0.5
        blocked = False
        for op in openings:
            if (
                right > op.x0 - 0.05
                and left < op.x1 + 0.05
                and top > op.z0 - 0.05
                and bottom < op.z1 + 0.05
            ):
                blocked = True
                break
        if blocked:
            continue

        waves = [
            (rnd.uniform(0.18, 0.34), rnd.choice((2, 3)), rnd.uniform(0.0, math.tau))
            for _ in range(2)
        ]
        points: list[tuple[float, float]] = []
        sides = rnd.randint(9, 13)
        for index in range(sides):
            angle = math.tau * index / sides
            wobble = 1.0
            for amplitude, frequency, phase in waves:
                wobble += amplitude * math.sin(frequency * angle + phase)
            wobble *= rnd.uniform(0.94, 1.04)
            px = cx + math.cos(angle) * patch_w * 0.5 * wobble
            pz = cz + math.sin(angle) * patch_h * 0.5 * wobble
            points.append(
                (min(width - 0.02, max(0.02, px)), min(height - 0.02, max(0.03, pz)))
            )
        _prism(builder, points, -0.009, 0.009, slot)
        _prism(builder, points, thickness - 0.009, thickness + 0.009, slot)
        placed += 1


# --------------------------------------------------------------------------- 山墙木架
def _gable_truss(
    builder: MeshBuilder,
    x_left: float,
    cx: float,
    x_right: float,
    z: float,
    rise: float,
    y: float,
    rnd: random.Random,
    slot: str,
) -> None:
    """露天的山墙木架：竖杆、系梁与斜撑，高度参差像被火烧断。"""
    span = x_right - x_left
    studs = 7
    for index in range(1, studs):
        frac = index / studs
        x = x_left + span * frac
        triangle = rise * (1.0 - abs(frac - 0.5) * 2.0)
        top = z + max(0.3, triangle * rnd.uniform(0.5, 0.98))
        builder.add_box((x - 0.065, y - 0.065, z - 0.14), (x + 0.065, y + 0.065, top), slot)

    collar_z = z + rise * 0.42
    builder.add_box(
        (cx - span * 0.32, y - 0.075, collar_z),
        (cx + span * 0.32, y + 0.075, collar_z + 0.13),
        slot,
    )
    # 斜撑：从墙顶斜向系梁两端
    for sign in (-1.0, 1.0):
        p0 = (cx + sign * span * 0.44, y, z + 0.16)
        p1 = (cx + sign * span * 0.29, y, collar_z)
        dx, dz = p1[0] - p0[0], p1[2] - p0[2]
        length = math.hypot(dx, dz) or 1.0
        _beam(
            builder,
            p0,
            p1,
            (0.0, 1.0, 0.0),
            (-dz / length, 0.0, dx / length),
            0.085,
            0.11,
            slot,
        )

    # 断在屋架里的残柱：几根竖杆捅出去，是烧塌后最醒目的特征
    for _ in range(2):
        x = cx + rnd.uniform(-span * 0.12, span * 0.12)
        top = z + rise * rnd.uniform(0.55, 0.95)
        builder.add_box(
            (x - 0.05, y - 0.05, collar_z), (x + 0.05, y + 0.05, top + 0.16), slot
        )


# --------------------------------------------------------------------------- 烧毁屋顶
def build_burnt_roof(
    width: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    tiles: dict[str, float],
    seed: int = 0,
    thatch_slot: str = "thatch",
    tile_slot: str = "roof",
    frame_slot: str = "char",
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    half = (width + 2.0 * overhang) * 0.5
    cx = width * 0.5
    y0, y1 = -overhang, depth + overhang
    rise = math.tan(math.radians(pitch_deg)) * half
    x_left, x_right = cx - half, cx + half
    ridge_z = z + rise
    slope_len = math.hypot(half, rise)
    rnd = random.Random(f"{seed}:burnt")

    # 折断的屋脊：中段断开，两端各留一截
    break_y = y0 + (y1 - y0) * rnd.uniform(0.38, 0.55)
    for a, b in ((y0, break_y), (break_y + 0.85, y1)):
        builder.add_box(
            (cx - 0.11, a, ridge_z - 0.2), (cx + 0.11, b, ridge_z + 0.06), frame_slot
        )

    # 柱网：沿屋脊方向切分，相邻单元共用抖动后的顶点，避免出现裂缝
    columns = max(5, int(round((y1 - y0) / 0.75)))
    edges = [y0]
    for index in range(1, columns):
        edges.append(y0 + (y1 - y0) * index / columns + rnd.uniform(-0.1, 0.1))
    edges.append(y1)

    rows = (0.0, 0.18, 0.38, 0.6, 0.8, 1.0)
    grid: dict[tuple[int, int], tuple[float, float]] = {}
    for ci in range(columns + 1):
        for ri in range(len(rows)):
            u = edges[ci] + (rnd.uniform(-0.11, 0.11) if 0 < ci < columns else 0.0)
            v = rows[ri] + (rnd.uniform(-0.035, 0.035) if 0 < ri < len(rows) - 1 else 0.0)
            grid[(ci, ri)] = (u, v)

    # 椽条：沿坡面等距排布，整体压到覆盖层以下
    side = (0.0, 1.0, 0.0)
    for direction in (1.0, -1.0):
        x_eave = x_right if direction > 0 else x_left
        nx, nz = direction * rise / slope_len, half / slope_len
        drop = 0.33
        ix, iz = -nx * drop, -nz * drop
        for ci in range(columns + 1):
            u = edges[ci]
            _beam(
                builder,
                (x_eave + ix, u, z + iz),
                (cx + ix, u, ridge_z + iz),
                side,
                (nx, 0.0, nz),
                0.09,
                0.17,
                frame_slot,
            )
        # 檩条：两道横梁压在椽条上
        for v in (0.32, 0.62):
            _beam(
                builder,
                _surface(x_eave + ix, cx + ix, z + iz, rise, y0, v),
                _surface(x_eave + ix, cx + ix, z + iz, rise, y1, v),
                side,
                (nx, 0.0, nz),
                0.11,
                0.13,
                frame_slot,
            )

    # 残存的覆盖层：左坡茅草、右坡石瓦。檐口尚存，往上被烧掉，边界是一条起伏的撕裂线
    covers = (
        (-1.0, thatch_slot, 0.26, 0.55, 0.22, 0.9),
        (1.0, tile_slot, 0.10, 0.62, 0.18, 0.82),
    )
    for direction, slot, thickness, base, amplitude, top in covers:
        x_eave = x_left if direction < 0 else x_right
        nx = direction * rise / slope_len
        nz = half / slope_len
        inward = (-nx, -nz)
        phase_a, phase_b = rnd.uniform(0.0, math.tau), rnd.uniform(0.0, math.tau)
        # 沿屋脊方向起伏的残留边界，越到屋脊越多缺口
        edge = {}
        for ci in range(columns):
            u = (edges[ci] + edges[min(columns, ci + 1)]) * 0.5
            edge[ci] = min(
                top,
                max(
                    0.12,
                    base
                    + amplitude * math.sin(u * 1.5 + phase_a)
                    + amplitude * 0.45 * math.sin(u * 3.9 + phase_b),
                ),
            )
        # 先整片判定保留，再据此只为露头的边补侧壁，避免相邻板产生重合面
        keep = []
        for ci in range(columns):
            column = []
            for ri in range(len(rows) - 1):
                v_center = (grid[(ci, ri)][1] + grid[(ci, ri + 1)][1]) * 0.5
                column.append(
                    v_center <= edge[ci] + rnd.uniform(-0.08, 0.08)
                    and rnd.random() > 0.12
                )
            keep.append(column)
        for ci in range(columns):
            for ri in range(len(rows) - 1):
                if not keep[ci][ri]:
                    continue
                corners = [
                    _surface(x_eave, cx, z, rise, *grid[(ci, ri)]),
                    _surface(x_eave, cx, z, rise, *grid[(ci + 1, ri)]),
                    _surface(x_eave, cx, z, rise, *grid[(ci + 1, ri + 1)]),
                    _surface(x_eave, cx, z, rise, *grid[(ci, ri + 1)]),
                ]
                exposed = (
                    ri == 0 or not keep[ci][ri - 1],
                    ci == columns - 1 or not keep[ci + 1][ri],
                    ri == len(rows) - 2 or not keep[ci][ri + 1],
                    ci == 0 or not keep[ci - 1][ri],
                )
                _slab(builder, corners, inward, thickness, slot, exposed)

                # 茅草撕裂边：在覆盖边缘挂几撮低垂的草片
                if direction < 0 and ri == 2 and rnd.random() < 0.5:
                    u = (edges[ci] + edges[ci + 1]) * 0.5
                    point = _surface(x_eave, cx, z, rise, u, grid[(ci, ri + 1)][1])
                    builder.add_box(
                        (point[0] - 0.14, u - 0.16, point[2] - 0.32),
                        (point[0] + 0.12, u + 0.16, point[2] + 0.03),
                        slot,
                    )

    # 前后山墙：灰泥三角面 + 外侧炭黑木架
    _prism(
        builder,
        [(x_left, z - 0.04), (x_right, z - 0.04), (cx, ridge_z - 0.04)],
        -0.02,
        0.05,
        "facade",
    )
    _prism(
        builder,
        [(x_left, z - 0.04), (cx, ridge_z - 0.04), (x_right, z - 0.04)],
        depth - 0.05,
        depth + 0.02,
        "facade",
    )
    _gable_truss(builder, x_left, cx, x_right, z, rise, -0.14, rnd, frame_slot)
    _gable_truss(builder, x_left, cx, x_right, z, rise, depth + 0.14, rnd, frame_slot)

    # 山墙两侧的封檐斜梁，压住屋面与木架的接缝
    for y in (-0.18, depth + 0.18):
        for direction in (1.0, -1.0):
            x_eave = x_right if direction > 0 else x_left
            _beam(
                builder,
                (x_eave, y, z + 0.02),
                (cx, y, ridge_z + 0.02),
                side,
                (direction * rise / slope_len, 0.0, half / slope_len),
                0.15,
                0.12,
                frame_slot,
            )
    return builder
