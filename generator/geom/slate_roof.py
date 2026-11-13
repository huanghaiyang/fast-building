"""板岩（石瓦）弯坡屋顶。

参考图里的五栋中世纪街屋共用一个屋顶语汇：屋面是厚重的深灰石板瓦，檐口在
前后两端明显上翘，屋脊是一根粗大的通长木梁并探出山墙，檐下露出椽条与檩条。
普通 ``build_gable_roof`` 只给出两个平面坡面，读不出这些特征，所以单独成模块。

几何构成（不做布尔运算）：

1. 屋面基层：两片坡面各自沿进深方向剖分成网格，向上放样出一层带厚度的壳，
   檐口、屋脊、山墙三处端头都补侧壁，保证是封闭实体；
2. 石板瓦：按「瓦行 × 瓦列」铺一层浅盒，行与行之间错缝、每块有尺寸抖动，
   越靠近屋脊瓦片越小（仿石板上小下大的收分）；
3. 露明木构：脊梁（探出山墙并起翘的端头）、檩条、椽条、檐口封檐板、
   山墙博风板；
4. 山墙三角面：按屋面下皮切出的斜面贴面，材质取 ``gable_slot``。

局部坐标与 ``build_gable_roof`` 一致：X 为跨度方向（0..width），Y 为进深
（0..depth，屋脊沿 Y），Z 自檐口标高起算。
"""

from __future__ import annotations

import math
import random

from ..meshkit import MeshBuilder

# 翘檐强度：以半跨为基准的端头上翘量
LIFT_RATIO = 0.16
# 屋脊端头上翘相对檐口的比例
RIDGE_LIFT_RATIO = 0.45
# 石板瓦厚度与抬高量
SLATE_T = 0.055
SLATE_LIFT = 0.008


def _lift(t: float, amount: float) -> float:
    """端头上翘曲线：中段几乎水平，靠近两端迅速抬起。"""
    return amount * max(0.0, min(1.0, t)) ** 2.2


def ridge_lift(width: float, overhang: float, curve: float) -> float:
    """屋脊端头相对中段的抬升量，供烟囱/老虎窗定位使用。"""
    half = (width + 2.0 * overhang) * 0.5
    return LIFT_RATIO * half * max(0.0, min(1.0, curve)) * RIDGE_LIFT_RATIO


def ridge_height(width: float, overhang: float, pitch_deg: float, curve: float) -> float:
    """从檐口标高算起的屋脊高度（含端头抬升）。"""
    half = (width + 2.0 * overhang) * 0.5
    return math.tan(math.radians(pitch_deg)) * half + ridge_lift(width, overhang, curve)


def _plate(
    builder: MeshBuilder,
    quad: list[tuple[float, float, float]],
    normal: tuple[float, float],
    thickness: float,
    slot: str,
) -> None:
    """给一片四边形加上厚度（沿 XZ 法线方向向下），成为一个薄瓦片。"""
    nx, nz = normal
    inner = [(x - nx * thickness, y, z - nz * thickness) for x, y, z in quad]
    builder.add_face(quad, slot)
    builder.add_face(list(reversed(inner)), slot)
    for index in range(4):
        nxt = (index + 1) % 4
        builder.add_face([quad[index], quad[nxt], inner[nxt], inner[index]], slot)


def _beam_path(
    builder: MeshBuilder,
    points: list[tuple[float, float, float]],
    width: float,
    height: float,
    slot: str,
) -> None:
    """沿折线扫掠矩形截面的木梁（脊梁/檩条/椽条/封檐板）。"""
    if len(points) < 2:
        return
    # 截面方向：世界 X / 世界 Z 的固定组合即可，梁本身是水平或近水平的
    for index in range(len(points) - 1):
        p0, p1 = points[index], points[index + 1]
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        dz = p1[2] - p0[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-4:
            continue
        # 沿梁方向的单位向量
        ux, uy, uz = dx / length, dy / length, dz / length
        # 取一个与梁方向垂直、尽量贴近水平面的截面方向
        sx, sy, sz = uy, -ux, 0.0
        slen = math.sqrt(sx * sx + sy * sy + sz * sz)
        if slen < 1e-4:
            sx, sy, sz = 1.0, 0.0, 0.0
        else:
            sx, sy, sz = sx / slen, sy / slen, sz / slen
        # 另一个截面方向 = 梁方向 × 截面方向
        tx = uy * sz - uz * sy
        ty = uz * sx - ux * sz
        tz = ux * sy - uy * sx
        tlen = math.sqrt(tx * tx + ty * ty + tz * tz) or 1.0
        tx, ty, tz = tx / tlen, ty / tlen, tz / tlen
        hw = width * 0.5
        hh = height * 0.5

        def corner(point, a: float, b: float):
            return (
                point[0] + sx * hw * a + tx * hh * b,
                point[1] + sy * hw * a + ty * hh * b,
                point[2] + sz * hw * a + tz * hh * b,
            )

        near = [corner(p0, 1, 1), corner(p0, -1, 1), corner(p0, -1, -1), corner(p0, 1, -1)]
        far = [corner(p1, 1, 1), corner(p1, -1, 1), corner(p1, -1, -1), corner(p1, 1, -1)]
        builder.add_face(near, slot)
        builder.add_face(list(reversed(far)), slot)
        for edge in range(4):
            nxt = (edge + 1) % 4
            builder.add_face([near[edge], near[nxt], far[nxt], far[edge]], slot)


def _gable_timber(
    builder: MeshBuilder,
    y: float,
    cx: float,
    half: float,
    z_base: float,
    z_apex: float,
    z_eave_wall: float,
    slot: str,
) -> None:
    """在山墙三角面上钉一套半木构：下弦、两道横梁、竖柱与角撑。"""
    depth = 0.075
    height = z_apex - z_base
    if height < 0.7:
        return

    def rake_at(dx: float) -> float:
        """山墙斜边在归一化横坐标 dx 处的高度。"""
        return z_base + height * (1.0 - min(1.0, abs(dx)))

    # 下弦（墙顶通长压梁）
    builder.add_box(
        (cx - half, y - depth, z_base),
        (cx + half, y + depth, z_base + 0.18),
        slot,
    )
    # 两道横梁：把三角面分成三段，越往上越短
    for frac in (0.34, 0.64):
        span = half * (1.0 - frac) + 0.05
        z = z_base + height * frac
        builder.add_box((cx - span, y - depth, z), (cx + span, y + depth, z + 0.13), slot)
    # 竖柱：中间一根通到脊，两侧各两根顶到斜边
    for dx in (-0.70, -0.36, 0.0, 0.36, 0.70):
        top = rake_at(dx) - 0.05
        builder.add_box(
            (cx + half * dx - 0.07, y - depth, z_base),
            (cx + half * dx + 0.07, y + depth, top),
            slot,
        )
    # 檐口角撑：从下弦两端斜撑到第二道横梁
    for sign in (-1.0, 1.0):
        _beam_path(
            builder,
            [
                (cx + sign * half * 0.94, y, z_base + 0.26),
                (cx + sign * half * 0.44, y, z_base + height * 0.62),
            ],
            0.10,
            0.13,
            slot,
        )
    # 脊端短柱：屋脊下方补一段，避免顶点空着
    if height > 1.4:
        builder.add_box(
            (cx - 0.09, y - depth, z_apex - 0.42),
            (cx + 0.09, y + depth, z_apex - 0.12),
            slot,
        )


def build_slate_roof(
    width: float,
    depth: float,
    z: float,
    pitch_deg: float,
    overhang: float,
    thickness: float,
    tiles: dict[str, float],
    seed: int = 0,
    curve: float = 0.55,
    slate_rows: int = 8,
    gable_slot: str = "facade",
    slate_slot: str = "roof",
    ridge_slot: str = "log",
    timber_slot: str = "trim",
    rafter_step: float = 0.66,
    gable_inset: float = 0.02,
    gable_timber: bool = True,
) -> MeshBuilder:
    """生成整片板岩弯坡屋顶（含山墙三角面）。"""
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:slate-roof")
    half = (width + 2.0 * overhang) * 0.5
    cx = width * 0.5
    y0 = -overhang
    y1 = depth + overhang
    span_y = y1 - y0
    yc = (y0 + y1) * 0.5
    pitch = math.tan(math.radians(pitch_deg))
    rise = pitch * half
    lift_eave = LIFT_RATIO * half * curve
    lift_ridge = lift_eave * RIDGE_LIFT_RATIO
    z_base = z + thickness

    def eave_z(y: float) -> float:
        t = abs(y - yc) / (span_y * 0.5) if span_y > 1e-6 else 0.0
        return z_base + _lift(t, lift_eave)

    def ridge_z(y: float) -> float:
        t = abs(y - yc) / (span_y * 0.5) if span_y > 1e-6 else 0.0
        return z_base + rise + _lift(t, lift_ridge)

    def surface(side: float, u: float, y: float) -> tuple[float, float, float]:
        ze = eave_z(y)
        zr = ridge_z(y)
        return (cx + side * half * (1.0 - u), y, ze + (zr - ze) * u)

    def slope_normal(side: float, y: float) -> tuple[float, float]:
        dz = ridge_z(y) - eave_z(y)
        length = math.hypot(dz, half) or 1.0
        return (side * dz / length, half / length)

    columns = max(4, int(round(span_y / 0.78)))
    ys = [y0 + span_y * index / columns for index in range(columns + 1)]

    # ---------------------------------------------------------------- 屋面基层
    shell_rows = 4
    for side in (-1.0, 1.0):
        grid_top: list[list[tuple[float, float, float]]] = []
        grid_bottom: list[list[tuple[float, float, float]]] = []
        for y in ys:
            nx, nz = slope_normal(side, y)
            top_row: list[tuple[float, float, float]] = []
            bottom_row: list[tuple[float, float, float]] = []
            for index in range(shell_rows + 1):
                u = index / shell_rows
                x, yy, zz = surface(side, u, y)
                top_row.append((x, yy, zz))
                bottom_row.append((x - nx * thickness, yy, zz - nz * thickness))
            grid_top.append(top_row)
            grid_bottom.append(bottom_row)

        for column in range(columns):
            for row in range(shell_rows):
                quad = [
                    grid_top[column][row],
                    grid_top[column + 1][row],
                    grid_top[column + 1][row + 1],
                    grid_top[column][row + 1],
                ]
                builder.add_face(quad, slate_slot)
                low = [
                    grid_bottom[column][row],
                    grid_bottom[column][row + 1],
                    grid_bottom[column + 1][row + 1],
                    grid_bottom[column + 1][row],
                ]
                builder.add_face(low, timber_slot)

        # 檐口端面（封檐板位置）与山墙端面，封闭基层
        for column in range(columns):
            a_top = grid_top[column][0]
            b_top = grid_top[column + 1][0]
            a_low = grid_bottom[column][0]
            b_low = grid_bottom[column + 1][0]
            builder.add_face([a_top, b_top, b_low, a_low], timber_slot)
        for column in (0, columns):
            for row in range(shell_rows):
                top_a = grid_top[column][row]
                top_b = grid_top[column][row + 1]
                low_a = grid_bottom[column][row]
                low_b = grid_bottom[column][row + 1]
                builder.add_face([top_a, low_a, low_b, top_b], slate_slot)

    # 屋脊下方：把两片坡面的下皮在脊线处连起来，避免中间留一条通缝
    for index in range(columns):
        y_mid = ys[index]
        builder.add_face(
            [
                (cx - thickness * 0.4, y_mid, ridge_z(y_mid) - thickness),
                (cx + thickness * 0.4, y_mid, ridge_z(y_mid) - thickness),
                (cx + thickness * 0.4, ys[index + 1], ridge_z(ys[index + 1]) - thickness),
                (cx - thickness * 0.4, ys[index + 1], ridge_z(ys[index + 1]) - thickness),
            ],
            timber_slot,
        )

    # ---------------------------------------------------------------- 石板瓦
    row_edges = [0.0]
    for index in range(1, slate_rows + 1):
        # 下小上大：靠近檐口的瓦行更宽（石板瓦的收分）
        frac = index / slate_rows
        row_edges.append(1.0 - (1.0 - frac) ** 1.22)
    row_edges[-1] = 1.0

    for side in (-1.0, 1.0):
        for row in range(slate_rows):
            u0, u1 = row_edges[row], row_edges[row + 1]
            # 每行错缝：行号决定起始偏移
            stagger = 0.5 if row % 2 else 0.0
            count = max(3, int(round(span_y / (0.42 + 0.05 * (slate_rows - row)))))
            for column in range(count):
                base = column + stagger
                ya = y0 + span_y * base / count
                yb = y0 + span_y * (base + 1.0) / count
                ya = max(y0, min(y1, ya + rnd.uniform(-0.012, 0.012)))
                yb = max(y0, min(y1, yb + rnd.uniform(-0.012, 0.012) - 0.028))
                if yb - ya < 0.05:
                    continue
                y_mid = (ya + yb) * 0.5
                nx, nz = slope_normal(side, y_mid)
                lift = SLATE_LIFT * (1.0 + rnd.uniform(0.0, 0.35))
                quad = []
                for u, y in ((u0, ya), (u0, yb), (u1, yb), (u1, ya)):
                    x, yy, zz = surface(side, u, y)
                    quad.append((x + nx * lift, yy, zz + nz * lift))
                _plate(builder, quad, (nx, nz), SLATE_T, slate_slot)

    # ---------------------------------------------------------------- 露明木构
    # 檐口封檐板：沿进深方向通长，跟着翘檐走
    for side in (-1.0, 1.0):
        path = []
        for y in ys:
            x, _, zz = surface(side, 0.0, y)
            path.append((x - side * 0.02, y, zz - 0.16))
        _beam_path(builder, path, 0.07, 0.30, timber_slot)

    # 檩条：每坡 3 道，探出山墙 0.12 m
    for side in (-1.0, 1.0):
        for u in (0.22, 0.52, 0.82):
            path = []
            for y in [y0 - 0.12] + ys + [y1 + 0.12]:
                x, _, zz = surface(side, u, max(y0, min(y1, y)))
                nx, nz = slope_normal(side, y)
                path.append((x - nx * (thickness + 0.09), y, zz - nz * (thickness + 0.09)))
            _beam_path(builder, path, 0.15, 0.17, timber_slot)

    # 椽条：沿坡向从檐口排到屋脊，贴在基层下皮
    rafter_count = max(3, int(round(span_y / rafter_step)))
    for index in range(rafter_count + 1):
        y = y0 + span_y * (index + 0.5) / rafter_count
        if y > y1:
            continue
        for side in (-1.0, 1.0):
            nx, nz = slope_normal(side, y)
            offset = thickness + 0.10
            eave = surface(side, 0.02, y)
            ridge = surface(side, 0.99, y)
            path = [
                (eave[0] - nx * offset, y, eave[2] - nz * offset),
                (ridge[0] - nx * offset, y, ridge[2] - nz * offset),
            ]
            _beam_path(builder, path, 0.09, 0.15, timber_slot)

    # 脊梁：通长、探出山墙，两端微微起翘（沿折线一次扫出来，避免拼接感）
    ridge_path = [(cx, y0 - 0.42, ridge_z(y0) - 0.12 + 0.16)]
    ridge_path.append((cx, y0 - 0.18, ridge_z(y0) - 0.02))
    for y in ys:
        ridge_path.append((cx, y, ridge_z(y) - 0.02))
    ridge_path.append((cx, y1 + 0.18, ridge_z(y1) - 0.02))
    ridge_path.append((cx, y1 + 0.42, ridge_z(y1) - 0.12 + 0.16))
    _beam_path(builder, ridge_path, 0.32, 0.28, ridge_slot)

    # 博风板：沿山墙两侧的斜边，压在石板瓦边缘
    for y_edge in (y0 + 0.03, y1 - 0.03):
        for side in (-1.0, 1.0):
            path = []
            for u in (0.0, 0.34, 0.68, 1.0):
                x, _, zz = surface(side, u, y_edge)
                nx, nz = slope_normal(side, y_edge)
                path.append((x + nx * 0.02, y_edge, zz + nz * 0.02))
            _beam_path(builder, path, 0.065, 0.19, timber_slot)

    # ---------------------------------------------------------------- 山墙三角面
    under_top = thickness + 0.02
    for y_face, flip in ((gable_inset, False), (depth - gable_inset, True)):
        ze = eave_z(y_face) - under_top
        zr = ridge_z(y_face) - under_top
        # 山墙面按墙宽收进，屋面挑出山墙一段，露出的椽条头正好在两者之间
        wall_half = width * 0.5
        z_at_eave = ze - (zr - ze) * ((half - wall_half) / half)
        points = [
            (cx - wall_half, y_face, z),
            (cx + wall_half, y_face, z),
            (cx + wall_half, y_face, z_at_eave),
            (cx, y_face, zr),
            (cx - wall_half, y_face, z_at_eave),
        ]
        builder.add_face(list(reversed(points)) if flip else points, gable_slot)
        if gable_timber:
            _gable_timber(
                builder,
                y_face + (-0.02 if flip else 0.02),
                cx,
                wall_half,
                z,
                zr,
                z_at_eave,
                timber_slot,
            )

    return builder
