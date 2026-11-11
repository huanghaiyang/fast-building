"""厚茅草双坡屋顶。

与瓦屋顶的三角棱柱不同，茅草屋顶强调「厚」与「大出檐」：
- 坡面是有竖向厚度的实心棱柱，檐口加半圆压边，形成圆润的草边；
- 坡面 UV 的 V 轴严格顺坡（从屋脊垂到檐口），草茎方向才正确；
- 山墙三角面略微内凹，四周由坡面端封边包住，形成裁切草边的厚度；
- 两侧沿坡向加深色博风板，遮住山墙与坡面的接缝；
- 屋脊压一根半埋的深色原木脊梁，两端略微出挑。
"""

from __future__ import annotations

import math

from ..meshkit import MeshBuilder


def add_slope(
    builder: MeshBuilder,
    x_eave: float,
    x_ridge: float,
    y0: float,
    y1: float,
    z_eave: float,
    rise: float,
    thickness: float,
    slot: str = "thatch",
) -> None:
    """添加一个带竖向厚度的坡面棱柱（檐口在 x_eave，屋脊在 x_ridge）。"""
    tile = max(builder.tiles.get(slot, 1.2), 0.05)
    slope_len = math.hypot(x_ridge - x_eave, rise)
    z_eave_top = z_eave + thickness
    z_ridge_top = z_eave + thickness + rise
    z_ridge_bot = z_eave + rise

    eb0 = (x_eave, y0, z_eave)
    eb1 = (x_eave, y1, z_eave)
    et0 = (x_eave, y0, z_eave_top)
    et1 = (x_eave, y1, z_eave_top)
    rt0 = (x_ridge, y0, z_ridge_top)
    rt1 = (x_ridge, y1, z_ridge_top)
    rb0 = (x_ridge, y0, z_ridge_bot)
    rb1 = (x_ridge, y1, z_ridge_bot)

    u0, u1 = y0 / tile, y1 / tile
    v_top, v_eave = slope_len / tile, z_eave / tile
    t = thickness / tile

    # 上表面：U 沿檐口方向，V 顺坡（草茎从脊部垂向檐口）
    builder.add_face(
        [et0, rt0, rt1, et1], slot, uvs=[(u0, 0.0), (u0, v_top), (u1, v_top), (u1, 0.0)]
    )
    # 下表面
    builder.add_face(
        [eb0, eb1, rb1, rb0], slot, uvs=[(u0, 0.0), (u1, 0.0), (u1, v_top), (u0, v_top)]
    )
    # 檐口立面
    builder.add_face(
        [eb0, eb1, et1, et0],
        slot,
        uvs=[(u0, v_eave), (u1, v_eave), (u1, v_eave + t), (u0, v_eave + t)],
    )
    # 山墙端封边（草层厚度方向的裁切面）
    builder.add_face(
        [eb0, et0, rt0, rb0],
        slot,
        uvs=[(0.0, 0.0), (0.0, t), (v_top, t), (v_top, 0.0)],
    )
    builder.add_face(
        [eb1, rb1, rt1, et1],
        slot,
        uvs=[(0.0, 0.0), (v_top, 0.0), (v_top, t), (0.0, t)],
    )
    # 脊部不封口：两坡在此共线，补面会与对侧坡面重合，形成重复面


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(a):
    length = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


def add_tube(
    builder: MeshBuilder,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    slot: str = "thatch",
    segments: int = 8,
) -> None:
    """任意方向的圆管，用于茅草山墙的厚重滚边。"""
    axis = _normalize((end[0] - start[0], end[1] - start[1], end[2] - start[2]))
    ref = (0.0, 1.0, 0.0) if abs(axis[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _normalize(_cross(axis, ref))
    v = _cross(axis, u)
    tile = builder.tiles.get(slot, 2.0)
    length = math.dist(start, end)
    arc = 2.0 * math.pi * radius

    offsets = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        cr, sr = math.cos(angle) * radius, math.sin(angle) * radius
        offsets.append((u[0] * cr + v[0] * sr, u[1] * cr + v[1] * sr, u[2] * cr + v[2] * sr))

    for i in range(segments):
        o0 = offsets[i]
        o1 = offsets[(i + 1) % segments]
        u0 = arc * i / segments / tile
        u1 = arc * (i + 1) / segments / tile
        builder.add_face(
            [
                (start[0] + o0[0], start[1] + o0[1], start[2] + o0[2]),
                (end[0] + o0[0], end[1] + o0[1], end[2] + o0[2]),
                (end[0] + o1[0], end[1] + o1[1], end[2] + o1[2]),
                (start[0] + o1[0], start[1] + o1[1], start[2] + o1[2]),
            ],
            slot,
            uvs=[(0.0, u0), (length / tile, u0), (length / tile, u1), (0.0, u1)],
        )
    for point in (start, end):
        builder.add_face(
            [(point[0] + o[0], point[1] + o[1], point[2] + o[2]) for o in offsets], slot
        )


def add_cylinder_y(
    builder: MeshBuilder,
    y0: float,
    y1: float,
    x_center: float,
    z_center: float,
    radius: float,
    slot: str = "thatch",
    segments: int = 8,
) -> None:
    """沿 Y 的半圆压边（檐口、门廊檐口用），UV 的草纹沿 Y 展开。"""
    if y1 - y0 < 0.02:
        return
    tile = builder.tiles.get(slot, 2.0)
    arc = 2.0 * math.pi * radius
    ring = [
        (
            radius * math.cos(2.0 * math.pi * i / segments),
            radius * math.sin(2.0 * math.pi * i / segments),
        )
        for i in range(segments)
    ]
    for i in range(segments):
        x0, z0 = ring[i]
        x1, z1 = ring[(i + 1) % segments]
        u0 = arc * i / segments / tile
        u1 = arc * (i + 1) / segments / tile
        builder.add_face(
            [
                (x_center + x0, y0, z_center + z0),
                (x_center + x0, y1, z_center + z0),
                (x_center + x1, y1, z_center + z1),
                (x_center + x1, y0, z_center + z1),
            ],
            slot,
            uvs=[(y0 / tile, u0), (y1 / tile, u0), (y1 / tile, u1), (y0 / tile, u1)],
        )
    for y in (y0, y1):
        builder.add_face([(x_center + x, y, z_center + z) for x, z in ring], slot)


def _rake_board(
    builder: MeshBuilder,
    x_eave: float,
    z_eave: float,
    x_ridge: float,
    z_ridge: float,
    y_a: float,
    y_b: float,
    board_w: float,
    slot: str = "trim",
) -> None:
    """沿坡向的博风板：在 XZ 平面内偏屋脊方向一条板，沿 Y 拉出厚度。"""
    dx, dz = x_ridge - x_eave, z_ridge - z_eave
    length = math.hypot(dx, dz) or 1.0
    # 指向屋面内侧：X 朝屋脊、Z 向下，板条正好压在坡面边缘下方
    sx = 1.0 if dx >= 0.0 else -1.0
    nx, nz = sx * abs(dz) / length, -abs(dx) / length

    def pts(y: float) -> list[tuple[float, float, float]]:
        return [
            (x_eave, y, z_eave),
            (x_ridge, y, z_ridge),
            (x_ridge + nx * board_w, y, z_ridge + nz * board_w),
            (x_eave + nx * board_w, y, z_eave + nz * board_w),
        ]

    a = pts(y_a)
    b = pts(y_b)
    builder.add_face(a, slot)  # 正面
    builder.add_face([b[3], b[2], b[1], b[0]], slot)  # 背面
    builder.add_face([a[0], a[1], b[1], b[0]], slot)  # 外沿
    builder.add_face([a[3], b[3], b[2], a[2]], slot)  # 内沿
    builder.add_face([a[0], b[0], b[3], a[3]], slot)  # 檐口端
    builder.add_face([a[1], a[2], b[2], b[1]], slot)  # 脊端


def _gable_window(
    builder: MeshBuilder,
    x_center: float,
    z_center: float,
    width: float,
    height: float,
    y_face: float,
    tiles: dict[str, float],
) -> None:
    """山墙小草窗：深色木框 + 内凹玻璃。"""
    frame = 0.07
    y_out = y_face - 0.07
    y_in = y_face + 0.02
    left = x_center - width * 0.5
    right = x_center + width * 0.5
    bottom = z_center - height * 0.5
    top = z_center + height * 0.5
    builder.add_box((left - frame, y_out, bottom - frame), (right + frame, y_in, bottom), "trim")
    builder.add_box((left - frame, y_out, top), (right + frame, y_in, top + frame), "trim")
    builder.add_box((left - frame, y_out, bottom), (left, y_in, top), "trim")
    builder.add_box((right, y_out, bottom), (right + frame, y_in, top), "trim")
    # 中竖梃
    builder.add_box(
        (x_center - 0.03, y_out + 0.01, bottom),
        (x_center + 0.03, y_in, top),
        "trim",
    )
    builder.add_face(
        [
            (left, y_out + 0.04, bottom),
            (right, y_out + 0.04, bottom),
            (right, y_out + 0.04, top),
            (left, y_out + 0.04, top),
        ],
        "glass",
    )


def _shingle_band(
    builder: MeshBuilder,
    x_eave: float,
    z_eave: float,
    x_ridge: float,
    z_ridge: float,
    y0: float,
    y1: float,
    t0: float,
    t1: float,
    side: int,
    slot: str = "roof",
) -> None:
    """在坡面中段压一条石瓦腰带。

    瓦片是错缝叠铺的薄板，沿坡面法线抬起 2~4 cm 压在茅草上；每片瓦的下沿
    补一条厚度侧壁，远看才有石板叠压的层次，而不是一层贴图。
    """
    dx, dz = x_ridge - x_eave, z_ridge - z_eave
    length = math.hypot(dx, dz) or 1.0
    ux, uz = dx / length, dz / length
    nx, nz = -uz, ux
    if nx * side < 0.0:
        nx, nz = -nx, -nz

    def point(t: float, lift: float, y: float) -> tuple[float, float, float]:
        return (
            x_eave + dx * t + nx * lift,
            y,
            z_eave + dz * t + nz * lift,
        )

    span = (t1 - t0) * length
    rows = max(2, int(round(span / 0.34)))
    for row in range(rows):
        ta = t0 + (t1 - t0) * row / rows
        tb = t0 + (t1 - t0) * (row + 1) / rows
        lift = 0.026 + 0.002 * row
        # 错缝：偶数排向右偏半片
        y = y0 + (row % 2) * 0.22 - 0.44
        index = 0
        while y < y1:
            width = 0.44 * (0.82 + ((row * 7 + index * 5) % 6) * 0.06)
            ya = max(y0 + 0.02, y)
            yb = min(y1 - 0.02, y + width - 0.012)
            y += width
            index += 1
            if yb - ya < 0.06:
                continue
            a = point(ta, lift, ya)
            b = point(ta, lift, yb)
            c = point(tb, lift, yb)
            d = point(tb, lift, ya)
            if side < 0:
                builder.add_face([a, b, c, d], slot)
            else:
                builder.add_face([b, a, d, c], slot)
            # 下沿厚度侧壁
            builder.add_face([d, c, point(tb, 0.0, yb), point(tb, 0.0, ya)], slot)


def _eave_fringe(
    builder: MeshBuilder,
    x_eave: float,
    y0: float,
    y1: float,
    z_eave: float,
    depth: float,
    outward: float,
    slot: str = "thatch",
) -> None:
    """檐口垂下的草束：一排长短不一的三角面，只做剪影。

    茅草屋面真正的收口是一排没被压进草捆的散草，平直做过去会像一块切齐的
    板材。三角面不封背面，靠材质双面渲染，控制在两百个面以内。
    """
    step = 0.17
    count = max(2, int((y1 - y0) / step))
    for index in range(count):
        ya = y0 + (y1 - y0) * index / count
        yb = y0 + (y1 - y0) * (index + 1) / count
        if yb - ya < 0.04:
            continue
        length = depth * (0.5 + 0.5 * ((index * 7) % 5) / 4.0)
        top = z_eave + 0.03
        mid = (ya + yb) * 0.5
        x_top = x_eave + outward * 0.015
        x_tip = x_eave + outward * 0.07
        tri = [
            (x_top, ya + 0.012, top),
            (x_top, yb - 0.012, top),
            (x_tip, mid, z_eave - length),
        ]
        builder.add_face(tri, slot)
        builder.add_face(list(reversed(tri)), slot)


def build_thatch_roof(
    width: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    thickness: float,
    tiles: dict[str, float],
    gable_slot: str = "thatch",
    gable_window: tuple[float, float, float, float] | None = None,
    gable_overhang: float = 0.18,
    fringe: float = 0.0,
    thatch_ridge: bool = False,
    shingle_band: tuple[float, float] | None = None,
    band_slot: str = "roof",
) -> MeshBuilder:
    """厚茅草双坡屋顶；局部坐标与 build_gable_roof 一致。

    gable_overhang 是山墙方向的挑出量，刻意做得比檐口 overhang 小：
    山墙草面贴近墙体，才不会像一块悬空的草板。
    """
    builder = MeshBuilder(tiles)
    half = width * 0.5 + overhang
    cx = width * 0.5
    x_left = cx - half
    x_right = cx + half
    y0 = -gable_overhang
    y1 = depth + gable_overhang
    rise = math.tan(math.radians(pitch_deg)) * half

    add_slope(builder, x_left, cx, y0, y1, z, rise, thickness, "thatch")
    add_slope(builder, x_right, cx, y0, y1, z, rise, thickness, "thatch")

    # 山墙三角略微内凹，让坡面端封边形成一圈草层厚度的边
    z_top = z + thickness
    z_ridge = z_top + rise
    inset = 0.006
    gable_tile = max(tiles.get(gable_slot, 1.2), 0.05)

    def gable(y: float) -> None:
        builder.add_face(
            [
                (x_left, y, z_top),
                (cx, y, z_ridge),
                (x_right, y, z_top),
                (x_right, y, z),
                (x_left, y, z),
            ],
            gable_slot,
            uvs=[
                (0.0, z_top / gable_tile),
                (half / gable_tile, z_ridge / gable_tile),
                (2 * half / gable_tile, z_top / gable_tile),
                (2 * half / gable_tile, z / gable_tile),
                (0.0, z / gable_tile),
            ],
        )

    gable(y0 + inset)
    gable(y1 - inset)

    # 檐口半圆压边
    lip = thickness * 0.5
    add_cylinder_y(builder, y0, y1, x_left, z + lip, lip, "thatch")
    add_cylinder_y(builder, y0, y1, x_right, z + lip, lip, "thatch")

    # 坡面中段的石瓦腰带：t 从檐口(0)到屋脊(1)
    if shingle_band is not None:
        t0, t1 = shingle_band
        band_y0, band_y1 = y0 + 0.05, y1 - 0.05
        _shingle_band(builder, x_left, z_top, cx, z_ridge, band_y0, band_y1, t0, t1, -1, band_slot)
        _shingle_band(builder, x_right, z_top, cx, z_ridge, band_y0, band_y1, t0, t1, 1, band_slot)

    # 散草：檐口下方垂下的长短草束
    if fringe > 0.0:
        _eave_fringe(builder, x_left, y0, y1, z, fringe, -1.0)
        _eave_fringe(builder, x_right, y0, y1, z, fringe, 1.0)

    # 博风板：两侧山墙沿坡向的深色木板，同时封住山墙与坡面的接缝
    board_w = 0.15
    _rake_board(builder, x_left, z, cx, z_ridge, y0 - 0.05, y0 + 0.004, board_w, "trim")
    _rake_board(builder, x_right, z, cx, z_ridge, y0 - 0.05, y0 + 0.004, board_w, "trim")
    _rake_board(builder, x_left, z, cx, z_ridge, y1 - 0.004, y1 + 0.05, board_w, "trim")
    _rake_board(builder, x_right, z, cx, z_ridge, y1 - 0.004, y1 + 0.05, board_w, "trim")

    # 檐口封檐板：把山墙下缘与墙体之间的挑空遮住，避免出现一条黑缝
    for y_a, y_b in ((y0, 0.0), (y1, depth)):
        builder.add_box((x_left, y_a, z - 0.13), (x_right, y_b, z), "trim")

    # 屋脊：木脊梁或压成草卷，两端略微出挑
    if thatch_ridge:
        add_cylinder_y(builder, y0 - 0.10, y1 + 0.10, cx, z_ridge - 0.03, 0.16, "thatch", segments=10)
    else:
        builder.add_box(
            (cx - 0.07, y0 - 0.10, z_ridge - 0.06),
            (cx + 0.07, y1 + 0.10, z_ridge + 0.055),
            "trim",
        )

    if gable_window is not None:
        wx, wz, ww, wh = gable_window
        _gable_window(builder, wx, wz, ww, wh, y0, tiles)
    return builder
