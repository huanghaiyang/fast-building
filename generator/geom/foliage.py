"""乡土植被：爬墙常春藤、墙根灌木与草丛。

参考图里的农舍靠墙脚的花丛和爬上墙面的常春藤撑起「有人住」的质感，纯几何
也能表达个大概：

- 叶片用朝外的菱形面片，沿一条左右摆动的藤蔓自下而上铺开，面片离墙 3~7 cm，
  有高差才不会被墙板 z-fighting 吃掉；
- 灌木用几个低面数球体拼成不规则团块，再撒几片浅色小花；
- 草丛是成组的三角面片，只做近景轮廓。

植被全部做成一个对象、世界坐标直接生成，不参与墙体的分间装配，也不写入
collision 或结构统计。
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from ..meshkit import MeshBuilder


@dataclass(frozen=True)
class _Wall:
    """墙面局部坐标系：u 沿墙长、out 为外法线方向、z 为高度。"""

    ox: float
    oy: float
    ux: float
    uy: float
    nx: float
    ny: float
    length: float

    def at(self, u: float, out: float, z: float) -> tuple[float, float, float]:
        return (
            self.ox + self.ux * u + self.nx * out,
            self.oy + self.uy * u + self.ny * out,
            z,
        )


def _walls(width: float, depth: float) -> list[_Wall]:
    """四面外墙；u × z 与每个面的外法线同向，叶片朝向才正确。"""
    return [
        _Wall(0.0, 0.0, 1.0, 0.0, 0.0, -1.0, width),
        _Wall(width, depth, -1.0, 0.0, 0.0, 1.0, width),
        _Wall(0.0, depth, 0.0, -1.0, -1.0, 0.0, depth),
        _Wall(width, 0.0, 0.0, 1.0, 1.0, 0.0, depth),
    ]


def _leaf(
    builder: MeshBuilder,
    wall: _Wall,
    u: float,
    z: float,
    size: float,
    out: float,
    slot: str = "leaf",
) -> None:
    builder.add_face(
        [
            wall.at(u - size, out, z),
            wall.at(u, out + 0.012, z - size * 0.85),
            wall.at(u + size, out, z),
            wall.at(u, out + 0.012, z + size * 0.85),
        ],
        slot,
    )


def _ivy_band(
    builder: MeshBuilder,
    wall: _Wall,
    u0: float,
    spread: float,
    height: float,
    rnd: random.Random,
) -> None:
    """从墙脚向上蔓延的一股常春藤。"""
    u = u0
    z = 0.12
    path: list[tuple[float, float]] = [(u, z)]
    while z < height * 0.86:
        u = max(u0 - spread * 0.4, min(u0 + spread * 0.4, u + rnd.uniform(-0.1, 0.1)))
        for _ in range(rnd.randint(3, 4)):
            _leaf(
                builder,
                wall,
                u + rnd.uniform(-spread, spread) * 0.6,
                z + rnd.uniform(-0.08, 0.08),
                rnd.uniform(0.07, 0.11),
                0.022 + rnd.uniform(0.0, 0.03),
            )
        z += rnd.uniform(0.09, 0.14)
        path.append((u, z))

    # 藤茎：沿路径的窄条，让散叶读成一条向上攀爬的藤
    half = 0.018
    for (u_a, z_a), (u_b, z_b) in zip(path, path[1:]):
        builder.add_face(
            [
                wall.at(u_a - half, 0.016, z_a),
                wall.at(u_a + half, 0.016, z_a),
                wall.at(u_b + half, 0.016, z_b),
                wall.at(u_b - half, 0.016, z_b),
            ],
            "leaf",
        )


def _sphere(
    builder: MeshBuilder,
    center: tuple[float, float, float],
    radius: float,
    slot: str = "leaf",
    segments: int = 6,
    rings: int = 4,
) -> None:
    cx, cy, cz = center
    grid: list[list[tuple[float, float, float]]] = []
    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        rz = math.cos(phi) * radius
        rr = math.sin(phi) * radius
        row = []
        for seg in range(segments):
            theta = 2.0 * math.pi * seg / segments
            row.append((cx + math.cos(theta) * rr, cy + math.sin(theta) * rr, cz + rz))
        grid.append(row)
    for ring in range(rings):
        for seg in range(segments):
            a = grid[ring][seg]
            b = grid[ring][(seg + 1) % segments]
            c = grid[ring + 1][(seg + 1) % segments]
            d = grid[ring + 1][seg]
            builder.add_face([a, b, c, d], slot)


def _shrub(
    builder: MeshBuilder,
    wall: _Wall,
    u: float,
    scale: float,
    rnd: random.Random,
) -> None:
    """墙根一团灌木：3~4 个球体堆出轮廓，顶上撒几片浅色花。"""
    base_r = 0.42 * scale
    blobs = rnd.randint(4, 5)
    for _ in range(blobs):
        r = base_r * rnd.uniform(0.72, 1.05)
        center = wall.at(
            u + rnd.uniform(-0.5, 0.5) * scale,
            rnd.uniform(0.2, 0.5) * scale,
            r * 0.82,
        )
        _sphere(builder, center, r, "leaf")

    for _ in range(rnd.randint(3, 6)):
        du = rnd.uniform(-0.45, 0.45) * scale
        dout = rnd.uniform(0.18, 0.42) * scale
        dz = rnd.uniform(0.42, 0.72) * scale
        _leaf(builder, wall, u + du, dz, rnd.uniform(0.055, 0.085), dout, "flower")

    # 草丛：两片交叉的三角面
    for _ in range(rnd.randint(2, 3)):
        du = rnd.uniform(-0.55, 0.55) * scale
        tip_u = du + rnd.uniform(-0.12, 0.12)
        builder.add_face(
            [
                wall.at(u + du - 0.06, 0.06, 0.0),
                wall.at(u + du + 0.06, 0.06, 0.0),
                wall.at(u + tip_u, 0.14, rnd.uniform(0.22, 0.38)),
            ],
            "leaf",
        )


def build_vegetation(
    width: float,
    depth: float,
    wall_height: float,
    seed: int = 42,
    door: tuple[float, float] | None = None,
    ivy: bool = True,
    shrubs: bool = True,
    ivy_coverage: float = 0.6,
    ivy_height: float = 0.8,
) -> MeshBuilder:
    """沿建筑四周生成植被。

    door 为正面门洞的（中心, 宽度），用于避让；ivy_coverage 控制每面墙爬几股藤
    （0 只剩一股，1 满四面各四股），ivy_height 控制藤蔓最高爬到墙高的比例。
    """
    builder = MeshBuilder({})
    rnd = random.Random(seed)
    walls = _walls(width, depth)

    for index, wall in enumerate(walls):
        skip: list[tuple[float, float]] = []
        if index == 0 and door is not None:
            door_cx, door_w = door
            skip.append((door_cx - door_w * 0.5 - 0.5, door_cx + door_w * 0.5 + 0.5))

        def blocked(u: float) -> bool:
            return any(start <= u <= end for start, end in skip)

        if ivy and ivy_coverage > 0.04:
            bands = max(1, min(4, int(round(1 + ivy_coverage * 3))))
            margin = 0.5
            usable = max(0.6, wall.length - margin * 2)
            for band in range(bands):
                anchor = margin + usable * (band + 0.5) / bands + rnd.uniform(-0.25, 0.25)
                if blocked(anchor):
                    continue
                reach = wall_height * ivy_height * rnd.uniform(0.75, 1.0)
                _ivy_band(builder, wall, anchor, 0.3 + ivy_coverage * 0.25, reach, rnd)

        if shrubs:
            spacing = 1.9
            count = max(2, int(wall.length / spacing))
            for slot in range(count):
                u = wall.length * (slot + 0.5) / count + rnd.uniform(-0.2, 0.2)
                if blocked(u):
                    continue
                _shrub(builder, wall, u, rnd.uniform(0.85, 1.15), rnd)

    return builder
