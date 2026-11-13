"""中世纪街市陈设构件库。

一组可复用的「随手堆放的小东西」：木桶、木箱、麻袋、干草垛、书堆、陶罐、
藤篮、柴堆、靠墙木梯与立式招牌。它们不是建筑本体，但参考图里正是这些东西
把一栋房子读成「有人住、正在营业」，所以单独成库，由装配阶段按开关散布。

局部坐标约定：
- 立面构件（木梯、立式招牌）：X 沿墙、Y=0 为墙面（-Y 朝外）、Z 自地面起算；
- 落地陈设（桶/箱/袋/罐）：以 (cx, cy) 为轴心、z0 为落地面，Z 向上。

几何全部由旋转体截面（lathe）、轴向棱柱与任意朝向盒体拼成，不依赖 bpy，
也不做布尔运算；每个构件本身是封闭实体，便于质量校验。
"""

from __future__ import annotations

import math
import random

from ..meshkit import MeshBuilder

# 木桶/木箱/麻袋/陶罐的默认材质槽
WOOD = "trim"
HOOP = "iron"
CLOTH = "cloth"
CLAY = "clay"
STRAW = "thatch"
PAPER = "paper"
STONE = "stone"
GLOW = "glow"

BOOK_SLOTS = (PAPER, CLAY, "door", "leaf", GLOW)


# --------------------------------------------------------------------------- 几何原语
def _box_frame(
    builder: MeshBuilder,
    center: tuple[float, float, float],
    axes: tuple[tuple[float, float, float], ...],
    half: tuple[float, float, float],
    slot: str,
) -> None:
    """按任意正交基放置一个盒体（用于水轮叶片、斜撑这类非轴对齐构件）。"""
    axis_u, axis_v, axis_w = axes
    ha, hb, hc = half

    def point(su: float, sv: float, sw: float) -> tuple[float, float, float]:
        return (
            center[0] + axis_u[0] * ha * su + axis_v[0] * hb * sv + axis_w[0] * hc * sw,
            center[1] + axis_u[1] * ha * su + axis_v[1] * hb * sv + axis_w[1] * hc * sw,
            center[2] + axis_u[2] * ha * su + axis_v[2] * hb * sv + axis_w[2] * hc * sw,
        )

    corners = [
        point(-1, -1, -1),
        point(1, -1, -1),
        point(1, 1, -1),
        point(-1, 1, -1),
        point(-1, -1, 1),
        point(1, -1, 1),
        point(1, 1, 1),
        point(-1, 1, 1),
    ]
    for quad in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        builder.add_face([corners[index] for index in quad], slot)


def lathe(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    profile: list[tuple[float, float]],
    sides: int = 12,
    slot: str = WOOD,
    cap_bottom: bool = True,
    cap_top: bool = True,
    angle_offset: float = 0.0,
) -> None:
    """绕竖轴旋转一个 (高度, 半径) 截面，生成桶、罐、篮这类旋转体。"""
    rings: list[list[tuple[float, float, float]]] = []
    for dz, radius in profile:
        ring: list[tuple[float, float, float]] = []
        for index in range(sides):
            angle = angle_offset + 2.0 * math.pi * index / sides
            ring.append(
                (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius, z0 + dz)
            )
        rings.append(ring)

    for level in range(len(rings) - 1):
        low, high = rings[level], rings[level + 1]
        for index in range(sides):
            nxt = (index + 1) % sides
            builder.add_face([low[index], low[nxt], high[nxt], high[index]], slot)

    if cap_bottom:
        builder.add_face(list(reversed(rings[0])), slot)
    if cap_top:
        builder.add_face(rings[-1], slot)


def prism_y(
    builder: MeshBuilder,
    cx: float,
    cz: float,
    y0: float,
    y1: float,
    radius: float,
    sides: int = 8,
    slot: str = WOOD,
) -> None:
    """沿 Y 轴的棱柱：柴堆里的原木、水轮轴都用它。"""
    ring_a: list[tuple[float, float, float]] = []
    ring_b: list[tuple[float, float, float]] = []
    for index in range(sides):
        angle = 2.0 * math.pi * (index + 0.5) / sides
        x = cx + math.cos(angle) * radius
        z = cz + math.sin(angle) * radius
        ring_a.append((x, y0, z))
        ring_b.append((x, y1, z))
    for index in range(sides):
        nxt = (index + 1) % sides
        builder.add_face([ring_a[index], ring_a[nxt], ring_b[nxt], ring_b[index]], slot)
    builder.add_face(list(reversed(ring_a)), slot)
    builder.add_face(ring_b, slot)


def ring_y(
    builder: MeshBuilder,
    cx: float,
    cz: float,
    y0: float,
    y1: float,
    outer: float,
    inner: float,
    sides: int = 24,
    slot: str = WOOD,
) -> None:
    """沿 Y 轴的圆环（水轮轮缘、桶箍）。"""
    for index in range(sides):
        angle_a = 2.0 * math.pi * index / sides
        angle_b = 2.0 * math.pi * (index + 1) / sides
        outer_a = (cx + math.cos(angle_a) * outer, cz + math.sin(angle_a) * outer)
        outer_b = (cx + math.cos(angle_b) * outer, cz + math.sin(angle_b) * outer)
        inner_a = (cx + math.cos(angle_a) * inner, cz + math.sin(angle_a) * inner)
        inner_b = (cx + math.cos(angle_b) * inner, cz + math.sin(angle_b) * inner)
        corners = [
            (outer_a[0], y0, outer_a[1]),
            (outer_b[0], y0, outer_b[1]),
            (outer_b[0], y1, outer_b[1]),
            (outer_a[0], y1, outer_a[1]),
        ]
        builder.add_face(corners, slot)
        builder.add_face(
            [
                (inner_b[0], y0, inner_b[1]),
                (inner_a[0], y0, inner_a[1]),
                (inner_a[0], y1, inner_a[1]),
                (inner_b[0], y1, inner_b[1]),
            ],
            slot,
        )
        # 内外圈之间的两侧环面
        builder.add_face(
            [
                (inner_a[0], y0, inner_a[1]),
                (inner_b[0], y0, inner_b[1]),
                (outer_b[0], y0, outer_b[1]),
                (outer_a[0], y0, outer_a[1]),
            ],
            slot,
        )
        builder.add_face(
            [
                (outer_a[0], y1, outer_a[1]),
                (outer_b[0], y1, outer_b[1]),
                (inner_b[0], y1, inner_b[1]),
                (inner_a[0], y1, inner_a[1]),
            ],
            slot,
        )


# --------------------------------------------------------------------------- 单个陈设
def add_barrel(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    radius: float = 0.30,
    height: float = 0.86,
    slot: str = WOOD,
    hoop_slot: str = HOOP,
    sides: int = 12,
) -> None:
    """木桶：中段鼓起的桶身 + 两道铁箍。"""
    profile = [
        (0.0, radius * 0.78),
        (height * 0.16, radius * 0.94),
        (height * 0.5, radius),
        (height * 0.84, radius * 0.94),
        (height, radius * 0.78),
    ]
    lathe(builder, cx, cy, z0, profile, sides=sides, slot=slot)
    for ratio in (0.18, 0.62):
        band_z = height * ratio
        lathe(
            builder,
            cx,
            cy,
            z0 + band_z,
            [(0.0, radius * 0.985), (height * 0.07, radius * 0.985)],
            sides=sides,
            slot=hoop_slot,
            cap_bottom=False,
            cap_top=False,
        )


def add_crate(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    size: float = 0.52,
    height: float = 0.0,
    slot: str = WOOD,
    rnd: random.Random | None = None,
) -> None:
    """木箱：箱体 + 四角压条 + 顶面木板条。"""
    height = height or size
    x0, x1 = cx - size * 0.5, cx + size * 0.5
    y0, y1 = cy - size * 0.5, cy + size * 0.5
    builder.add_box((x0, y0, z0), (x1, y1, z0 + height), slot)

    batten = 0.055
    for bx in (x0 - 0.012, x1 - batten + 0.012):
        for by in (y0 - 0.012, y1 - batten + 0.012):
            builder.add_box((bx, by, z0), (bx + batten, by + batten, z0 + height), slot)
    for band_z in (z0 + height * 0.18, z0 + height * 0.74):
        builder.add_box((x0 - 0.01, y0 - 0.01, band_z), (x1 + 0.01, y1 + 0.01, band_z + 0.05), slot)

    # 顶面木板条留缝，读成拼板箱盖
    planks = 3
    gap = 0.018
    span = (y1 - y0) - gap * (planks - 1)
    plank_w = span / planks
    for index in range(planks):
        py0 = y0 + index * (plank_w + gap)
        builder.add_box((x0 + 0.02, py0, z0 + height), (x1 - 0.02, py0 + plank_w, z0 + height + 0.035), slot)


def add_sack(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    radius: float = 0.24,
    height: float = 0.52,
    slot: str = CLOTH,
    rnd: random.Random | None = None,
) -> None:
    """麻袋：底部圆鼓、上口收束，袋口系一圈绳。"""
    jitter = rnd.uniform(-0.06, 0.06) if rnd else 0.0
    profile = [
        (0.0, radius * 0.72),
        (height * 0.10, radius * 0.96),
        (height * 0.55, radius * (1.0 + jitter)),
        (height * 0.78, radius * 0.84),
        (height * 0.90, radius * 0.34),
        (height, radius * 0.22),
    ]
    lathe(builder, cx, cy, z0, profile, sides=10, slot=slot)
    lathe(
        builder,
        cx,
        cy,
        z0 + height * 0.87,
        [(0.0, radius * 0.36), (0.045, radius * 0.36)],
        sides=10,
        slot=WOOD,
        cap_bottom=False,
        cap_top=False,
    )


def add_hay_bale(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    width: float = 0.92,
    height: float = 0.52,
    depth: float = 0.56,
    slot: str = STRAW,
    rnd: random.Random | None = None,
) -> None:
    """干草垛：方草捆 + 四角倒棱 + 几簇支棱出来的草茎。"""
    x0, x1 = cx - width * 0.5, cx + width * 0.5
    y0, y1 = cy - depth * 0.5, cy + depth * 0.5
    chamfer = min(0.09, height * 0.2)
    builder.add_box((x0, y0, z0), (x1, y1, z0 + height), slot)
    # 上一圈略小的顶盖，读成被压扁的圆角草捆
    builder.add_box(
        (x0 + chamfer, y0 + chamfer, z0 + height),
        (x1 - chamfer, y1 - chamfer, z0 + height + 0.05),
        slot,
    )
    rnd = rnd or random.Random(7)
    for _ in range(10):
        sx = rnd.uniform(x0 + 0.06, x1 - 0.06)
        sz = rnd.uniform(z0 + 0.08, z0 + height - 0.04)
        length = rnd.uniform(0.06, 0.13)
        side = -1.0 if rnd.random() < 0.5 else 1.0
        sy = y0 if side < 0 else y1
        builder.add_box(
            (sx - 0.012, min(sy, sy + side * length), sz),
            (sx + 0.012, max(sy, sy + side * length), sz + 0.024),
            slot,
        )


def add_book_stack(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    rnd: random.Random | None = None,
    count: int = 5,
    max_width: float = 0.44,
) -> None:
    """书堆：一摞厚薄不一的书，偶尔横竖交替，脊背颜色跳着用几个槽。"""
    rnd = rnd or random.Random(11)
    z = z0
    for index in range(count):
        width = rnd.uniform(max_width * 0.62, max_width)
        depth = rnd.uniform(0.16, 0.26)
        height = rnd.uniform(0.035, 0.062)
        if index % 3 == 2:
            width, depth = depth, width
        ox = rnd.uniform(-0.035, 0.035)
        oy = rnd.uniform(-0.03, 0.03)
        slot = BOOK_SLOTS[index % len(BOOK_SLOTS)]
        builder.add_box(
            (cx - width * 0.5 + ox, cy - depth * 0.5 + oy, z),
            (cx + width * 0.5 + ox, cy + depth * 0.5 + oy, z + height),
            slot,
        )
        # 书页侧面：比封皮浅一条，让书读起来有厚度
        builder.add_box(
            (cx - width * 0.5 + ox + 0.008, cy - depth * 0.5 + oy + 0.004, z),
            (cx + width * 0.5 + ox - 0.008, cy + depth * 0.5 + oy - 0.004, z + height * 0.55),
            PAPER,
        )
        z += height


def add_pot(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    radius: float = 0.18,
    height: float = 0.42,
    slot: str = CLAY,
) -> None:
    """陶罐：小底、鼓腹、收颈、外翻口沿。"""
    profile = [
        (0.0, radius * 0.55),
        (height * 0.12, radius * 0.82),
        (height * 0.42, radius),
        (height * 0.72, radius * 0.62),
        (height * 0.86, radius * 0.46),
        (height, radius * 0.60),
    ]
    lathe(builder, cx, cy, z0, profile, sides=12, slot=slot)


def add_basket(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    radius: float = 0.25,
    height: float = 0.30,
    slot: str = STRAW,
) -> None:
    """藤篮：上大下小的敞口筐 + 一圈口沿 + 提手。"""
    profile = [
        (0.0, radius * 0.68),
        (height * 0.6, radius * 0.9),
        (height, radius),
    ]
    lathe(builder, cx, cy, z0, profile, sides=12, slot=slot, cap_top=False)
    lathe(
        builder,
        cx,
        cy,
        z0 + height - 0.02,
        [(0.0, radius * 1.02), (0.05, radius * 1.02)],
        sides=12,
        slot=WOOD,
        cap_bottom=False,
        cap_top=False,
    )
    # 提手：两道竖直板拼成半圆
    for angle in (0.0, math.pi):
        ox = math.cos(angle) * radius * 0.82
        _box_frame(
            builder,
            (cx + ox, cy, z0 + height + 0.10),
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            (0.018, 0.018, 0.12),
            WOOD,
        )


def add_log_pile(
    builder: MeshBuilder,
    cx: float,
    cy: float,
    z0: float,
    length: float = 0.86,
    radius: float = 0.10,
    rows: int = 3,
    rnd: random.Random | None = None,
) -> None:
    """柴堆：沿 Y 轴码放的圆木金字塔，端头朝向街面。"""
    rnd = rnd or random.Random(5)
    y0 = cy - length * 0.5
    y1 = cy + length * 0.5
    for row in range(rows):
        count = rows - row
        z = z0 + radius * (1.0 + row * 1.72)
        for index in range(count):
            offset = (index - (count - 1) * 0.5) * radius * 2.1
            r = radius * rnd.uniform(0.9, 1.05)
            prism_y(builder, cx + offset, z, y0 + rnd.uniform(-0.03, 0.03), y1, r, sides=7, slot="log")


def build_ladder(
    tiles: dict[str, float],
    height: float = 2.7,
    width: float = 0.52,
    lean: float = 0.55,
    slot: str = WOOD,
) -> MeshBuilder:
    """靠墙木梯：两根梯梃斜靠在墙面（y=0），横档等距。

    局部坐标：X 沿墙 0..width，Y 从墙面 (-lean 为地面脚点) 向 0，Z 自地面起算。
    """
    builder = MeshBuilder(tiles)
    rail = 0.07
    for x in (0.0, width - rail):
        # 梯梃：用两段盒体拼出斜靠的姿态（box 只能轴对齐，这里按高度分段）
        segments = 6
        for index in range(segments):
            z0 = height * index / segments
            z1 = height * (index + 1) / segments
            y0 = -lean * (1.0 - index / segments)
            y1 = -lean * (1.0 - (index + 1) / segments)
            points = [
                (x, y0, z0),
                (x + rail, y0, z0),
                (x + rail, y1, z1),
                (x, y1, z1),
            ]
            # 截面：沿 y 方向的薄板
            builder.add_face(points, slot)
            builder.add_face(
                [(p[0], p[1] + 0.05, p[2]) for p in points], slot
            )
            for edge in range(4):
                a = points[edge]
                b = points[(edge + 1) % 4]
                builder.add_face(
                    [a, b, (b[0], b[1] + 0.05, b[2]), (a[0], a[1] + 0.05, a[2])],
                    slot,
                )
    rungs = max(3, int(height / 0.32))
    for index in range(1, rungs):
        z = height * index / rungs
        y = -lean * (1.0 - index / rungs)
        builder.add_box((0.03, y - 0.10, z - 0.025), (width - 0.03, y - 0.055, z + 0.025), slot)
    return builder


def build_sign_board(
    tiles: dict[str, float],
    width: float = 0.96,
    height: float = 1.52,
    slot: str = WOOD,
    board_slot: str = "door",
) -> MeshBuilder:
    """立式招牌：两根立柱 + 中间横板 + 顶帽，板面刻一排小方块当字号。

    局部坐标：X 沿墙 0..width，Y=0 为墙面（-Y 朝外），Z 自地面起算。
    """
    builder = MeshBuilder(tiles)
    post = 0.085
    out = -0.24
    for x in (0.02, width - post - 0.02):
        builder.add_box((x, out - post * 0.5, 0.0), (x + post, out + post * 0.5, height), slot)
    board_h = height * 0.52
    board_z0 = height * 0.34
    builder.add_box(
        (-0.06, out - 0.115, board_z0),
        (width + 0.06, out - 0.02, board_z0 + board_h),
        board_slot,
    )
    # 上下压条
    for z in (board_z0 - 0.06, board_z0 + board_h):
        builder.add_box((-0.08, out - 0.13, z), (width + 0.08, out - 0.01, z + 0.06), slot)
    # 顶帽
    builder.add_box((-0.09, out - 0.14, height - 0.05), (width + 0.09, out - 0.005, height + 0.02), slot)
    # 板面字号：一排小方块
    glyphs = 4
    gw = (width - 0.24) / glyphs
    for index in range(glyphs):
        gx = 0.12 + index * gw
        builder.add_box(
            (gx + gw * 0.18, out - 0.135, board_z0 + board_h * 0.28),
            (gx + gw * 0.70, out - 0.115, board_z0 + board_h * 0.72),
            PAPER,
        )
    return builder


def build_wall_board(
    tiles: dict[str, float],
    width: float = 2.30,
    height: float = 0.62,
    slot: str = WOOD,
    board_slot: str = "door",
) -> MeshBuilder:
    """门楣横招牌：贴着立面横挂的木板招牌，两侧短托木。

    局部坐标：X 沿墙 0..width，Y=0 为墙面（-Y 朝外），Z=0 为招牌底边。
    """
    builder = MeshBuilder(tiles)
    builder.add_box((0.0, -0.10, 0.0), (width, -0.04, height), board_slot)
    for z in (-0.055, height - 0.02):
        builder.add_box((-0.03, -0.12, z), (width + 0.03, -0.02, z + 0.06), slot)
    for x in (width * 0.16, width * 0.84):
        builder.add_box((x - 0.035, -0.16, height * 0.5), (x + 0.035, 0.0, height * 0.5 + 0.07), slot)
    # 板面刻字：一排深色小方块
    glyphs = max(3, int(width / 0.46))
    gw = (width - 0.30) / glyphs
    for index in range(glyphs):
        gx = 0.15 + index * gw
        builder.add_box(
            (gx + gw * 0.20, -0.115, height * 0.26),
            (gx + gw * 0.72, -0.10, height * 0.74),
            PAPER if index % 2 == 0 else GLOW,
        )
    return builder


# --------------------------------------------------------------------------- 沿墙陈设簇
def build_street_props(
    width: float,
    z0: float,
    tiles: dict[str, float],
    seed: int = 42,
    kind: str = "mixed",
    door: tuple[float, float] | None = None,
    sides: tuple[bool, bool] = (True, True),
) -> MeshBuilder:
    """沿立面堆一圈陈设。

    ``kind`` 决定主题：``books`` 多书堆，``goods`` 多陶罐麻袋，``stable`` 多草垛，
    其余为混合。所有件都贴在 y ∈ [-0.92, -0.30] 的窄带里，既不穿进毛石勒脚，
    也不会盖住门洞（``door`` 给出 (中心 X, 宽度) 用于让位）。
    """
    builder = MeshBuilder(tiles)
    rnd = random.Random(f"{seed}:props:{kind}")
    left_gate = 0.35
    right_gate = width - 0.35
    door_cx, door_w = door if door else (width * 0.5, 0.0)

    def blocked(x: float, half: float = 0.34) -> bool:
        return abs(x - door_cx) < door_w * 0.5 + half

    def spot(prefer_left: bool) -> float:
        for _ in range(24):
            low, high = (left_gate, door_cx - door_w * 0.5 - 0.4) if prefer_left else (
                door_cx + door_w * 0.5 + 0.4,
                right_gate,
            )
            if high - low < 0.3:
                low, high = left_gate, right_gate
            x = rnd.uniform(low, high)
            if not blocked(x):
                return x
        return width * 0.5

    # 主件：按主题排队（参考图里墙根往往堆到七八件才够热闹）
    lineup: list[str] = []
    if kind == "books":
        lineup = ["books", "crate", "books", "barrel", "books", "sack", "books", "basket"]
    elif kind == "goods":
        lineup = ["barrel", "pot", "crate", "sack", "pot", "barrel", "basket", "sack"]
    elif kind == "stable":
        lineup = ["hay", "barrel", "hay", "crate", "barrel", "hay", "crate", "sack"]
    else:
        lineup = ["barrel", "crate", "sack", "basket", "barrel", "crate", "pot", "sack"]

    corners = [(width * 0.055, True), (width * 0.945, False)]
    spots = [
        (spot(True), True),
        (spot(False), False),
        (spot(True), True),
        (spot(False), False),
        (spot(True), True),
        (spot(False), False),
    ]
    index = 0
    for x, prefer_left in corners + spots:
        if index >= len(lineup):
            break
        item = lineup[index % len(lineup)]
        # 让开毛石勒脚（外皮 -0.26），桶口半径较大，整体再往外挪一点
        y = -0.60 - rnd.uniform(0.0, 0.10)
        if item == "barrel":
            add_barrel(builder, x, y, z0, radius=rnd.uniform(0.30, 0.38), height=rnd.uniform(0.86, 1.04))
        elif item == "crate":
            size = rnd.uniform(0.50, 0.68)
            add_crate(builder, x, y, z0, size=size, rnd=rnd)
            if rnd.random() < 0.45:
                add_crate(builder, x + size * 0.15, y - size * 0.1, z0 + size, size * 0.72, rnd=rnd)
        elif item == "sack":
            add_sack(builder, x, y, z0, radius=rnd.uniform(0.26, 0.32), height=rnd.uniform(0.54, 0.70), rnd=rnd)
        elif item == "basket":
            add_basket(builder, x, y, z0, radius=rnd.uniform(0.24, 0.32), height=rnd.uniform(0.30, 0.40))
        elif item == "pot":
            add_pot(builder, x, y, z0, radius=rnd.uniform(0.18, 0.26), height=rnd.uniform(0.42, 0.60))
            add_pot(builder, x + 0.34, y + 0.06, z0, radius=rnd.uniform(0.13, 0.19), height=rnd.uniform(0.30, 0.44))
        elif item == "books":
            add_book_stack(builder, x, y, z0, rnd=rnd, count=rnd.randint(3, 6))
            if rnd.random() < 0.6:
                add_book_stack(builder, x + rnd.uniform(-0.18, 0.18), y - 0.2, z0, rnd=rnd, count=rnd.randint(2, 4))
        elif item == "hay":
            add_hay_bale(builder, x, y, z0, width=rnd.uniform(0.92, 1.14), height=rnd.uniform(0.50, 0.62))
            if rnd.random() < 0.5:
                add_hay_bale(
                    builder,
                    x + rnd.uniform(-0.12, 0.12),
                    y + 0.1,
                    z0 + 0.5,
                    width=rnd.uniform(0.6, 0.78),
                    height=rnd.uniform(0.36, 0.46),
                    depth=0.44,
                )
        index += 1

    # 柴堆与零散小物：左右两端各一堆，保证转角不空
    if sides[0]:
        add_log_pile(builder, width * 0.055, -0.62, z0, length=0.8, radius=0.10, rows=3, rnd=rnd)
    if sides[1]:
        add_log_pile(builder, width * 0.945, -0.62, z0, length=0.74, radius=0.095, rows=2, rnd=rnd)
    return builder
