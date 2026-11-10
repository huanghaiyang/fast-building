"""轻量网格构建工具。

设计原则：
- 几何用纯 Python 生成（不依赖 bpy.ops），便于测试与跨版本稳定；
- UV 一律按真实尺寸 / tile_m 计算，保证不同大小模块的贴图密度一致；
- 顶点按坐标去重，使封闭实体（墙体、楼板）保持流形，便于质量校验。
"""

from __future__ import annotations

import math

VERTEX_EPS = 1e-5


class MeshBuilder:
    """按面收集顶点、材质槽与 UV，最后一次性生成 Blender Mesh。"""

    def __init__(self, tiles: dict[str, float] | None = None) -> None:
        self.verts: list[tuple[float, float, float]] = []
        self.faces: list[list[int]] = []
        self.face_slots: list[str] = []
        self.face_uvs: list[list[tuple[float, float]]] = []
        self.tiles = tiles or {}
        self._index: dict[tuple[int, int, int], int] = {}

    # ------------------------------------------------------------------ 基础操作
    def _vert(self, p: tuple[float, float, float]) -> int:
        key = (
            int(round(p[0] / VERTEX_EPS)),
            int(round(p[1] / VERTEX_EPS)),
            int(round(p[2] / VERTEX_EPS)),
        )
        idx = self._index.get(key)
        if idx is not None:
            return idx
        idx = len(self.verts)
        self.verts.append((float(p[0]), float(p[1]), float(p[2])))
        self._index[key] = idx
        return idx

    def add_face(
        self,
        points: list[tuple[float, float, float]],
        slot: str = "facade",
        uvs: list[tuple[float, float]] | None = None,
    ) -> None:
        """添加一个多边形面；UV 缺省时按主法线轴做平面投影。

        顶点按 VERTEX_EPS 去重后可能出现连续重复索引，必须在这里剔除，
        否则会生成零面积面片，导致 Blender 的法线重算陷入死循环。
        """
        if len(points) < 3:
            return
        idxs: list[int] = []
        keep: list[int] = []
        for index, point in enumerate(points):
            vert = self._vert(point)
            if idxs and idxs[-1] == vert:
                continue
            idxs.append(vert)
            keep.append(index)
        if len(idxs) > 1 and idxs[0] == idxs[-1]:
            idxs.pop()
            keep.pop()
        if len(idxs) < 3:
            return

        clean_points = [points[i] for i in keep]
        normal = face_normal(clean_points)
        if normal == (0.0, 0.0, 0.0):
            return
        if uvs is None:
            uvs = planar_uvs(clean_points, self.tiles.get(slot, 2.0))
        elif len(uvs) == len(points):
            uvs = [uvs[i] for i in keep]

        self.faces.append(idxs)
        self.face_slots.append(slot)
        self.face_uvs.append(uvs)

    def add_quad(
        self,
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        p2: tuple[float, float, float],
        p3: tuple[float, float, float],
        slot: str = "facade",
    ) -> None:
        self.add_face([p0, p1, p2, p3], slot)

    def add_box(
        self,
        min_v: tuple[float, float, float],
        max_v: tuple[float, float, float],
        slot: str = "facade",
    ) -> None:
        """轴对齐长方体（6 个四边形），UV 按世界坐标平面投影。"""
        x0, y0, z0 = min_v
        x1, y1, z1 = max_v
        # 前后（±X）
        self.add_quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), slot)
        self.add_quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), slot)
        # 左右（±Y）
        self.add_quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), slot)
        self.add_quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), slot)
        # 顶底（±Z）
        self.add_quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), slot)
        self.add_quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), slot)

    # ------------------------------------------------------------------ 统计
    def tri_count(self) -> int:
        return sum(len(f) - 2 for f in self.faces)


def face_normal(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    """用 Newell 方法计算多边形法线，对非平面四边形也稳健。"""
    nx = ny = nz = 0.0
    count = len(points)
    for i in range(count):
        x0, y0, z0 = points[i]
        x1, y1, z1 = points[(i + 1) % count]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / length, ny / length, nz / length


def planar_uvs(
    points: list[tuple[float, float, float]], tile_m: float
) -> list[tuple[float, float]]:
    """按主法线轴投影出 UV，坐标以米为单位除以 tile_m。"""
    tile = max(0.05, tile_m)
    n = face_normal(points)
    ax = max(range(3), key=lambda i: abs(n[i]))
    uvs: list[tuple[float, float]] = []
    for x, y, z in points:
        if ax == 0:      # 法线沿 X，投影到 YZ 平面
            uvs.append((y / tile, z / tile))
        elif ax == 1:    # 法线沿 Y，投影到 XZ 平面
            uvs.append((x / tile, z / tile))
        else:            # 法线沿 Z，投影到 XY 平面
            uvs.append((x / tile, y / tile))
    return uvs
