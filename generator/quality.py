"""几何质量：平滑着色与细分曲面。

纯 Python 几何生成出来的是平面着色网格，圆木、拱券、烟囱这类圆柱截面在近景
会读成多棱柱。这里按二面角把相邻面聚成平滑组，再可选地套一层 Catmull-Clark
细分：

- 超过 ``SHARP_ANGLE_DEG`` 的二面角视为硬边，保持锐利并写入 crease，
  让细分只磨圆本来就有曲率的部位，墙面、台阶、勒脚仍然方正；
- 只有真正处在连续曲面上的面才标记平滑。一块四周全是硬边的大平面（屋坡、
  墙板）如果也平滑，顶点法线会把相邻硬边的方向插值进来，整片板出现渐变和
  波纹，反而比平面着色更脏；
- 平滑/锐边/crease 直接写 mesh 属性，不做 bmesh 往返，避免动到 UV。
"""

from __future__ import annotations

import math

import bpy

SHARP_ANGLE_DEG = 38.0

_smooth_enabled = True
_subdiv_levels = 0


def configure(smooth: bool = True, subdiv: int = 0) -> None:
    """设置本进程后续构件的着色与细分级别（0 表示不细分）。"""
    global _smooth_enabled, _subdiv_levels
    _smooth_enabled = bool(smooth)
    _subdiv_levels = max(0, min(int(subdiv), 2))


def apply(obj: bpy.types.Object) -> None:
    """对单个对象应用平滑着色，并按需套用细分曲面修改器。"""
    if not _smooth_enabled and _subdiv_levels == 0:
        return
    if _smooth_enabled:
        _mark_smooth(obj)
    if _subdiv_levels > 0:
        _subdivide(obj, _subdiv_levels)


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _mark_smooth(obj: bpy.types.Object) -> None:
    """按二面角标记平滑面与锐边。"""
    mesh = obj.data
    mesh.update()
    normals = [polygon.normal.copy() for polygon in mesh.polygons]

    edge_faces: dict[tuple[int, int], list[int]] = {}
    for index, polygon in enumerate(mesh.polygons):
        verts = polygon.vertices
        for i in range(len(verts)):
            key = _edge_key(verts[i], verts[i - 1])
            edge_faces.setdefault(key, []).append(index)

    limit = math.cos(math.radians(SHARP_ANGLE_DEG))
    sharp: list[bool] = []
    for edge in mesh.edges:
        a, b = edge.vertices
        faces = edge_faces.get(_edge_key(a, b), [])
        if len(faces) != 2:
            sharp.append(True)
            continue
        sharp.append(normals[faces[0]].dot(normals[faces[1]]) < limit)

    smooth_faces = [False] * len(mesh.polygons)
    for edge_index, edge in enumerate(mesh.edges):
        if sharp[edge_index]:
            continue
        for face_index in edge_faces.get(_edge_key(*edge.vertices), []):
            smooth_faces[face_index] = True

    sharp_attr = mesh.attributes.get("sharp_edge")
    if sharp_attr is None:
        sharp_attr = mesh.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    sharp_attr.data.foreach_set("value", sharp)

    crease_attr = mesh.attributes.get("crease_edge")
    if crease_attr is None:
        crease_attr = mesh.attributes.new("crease_edge", "FLOAT", "EDGE")
    crease_attr.data.foreach_set("value", [1.0 if flag else 0.0 for flag in sharp])

    mesh.polygons.foreach_set("use_smooth", smooth_faces)
    mesh.update()


def _subdivide(obj: bpy.types.Object, levels: int) -> None:
    """套用并立即烘焙细分修改器，好让细分结果重新参与锐边判定。"""
    modifier = obj.modifiers.new("Subdivision", "SUBSURF")
    modifier.subdivision_type = "CATMULL_CLARK"
    modifier.levels = levels
    modifier.render_levels = levels
    modifier.use_creases = True
    if hasattr(modifier, "quality"):
        modifier.quality = 3

    with bpy.context.temp_override(
        object=obj,
        active_object=obj,
        selected_objects=[obj],
        selected_editable_objects=[obj],
    ):
        bpy.ops.object.modifier_apply(modifier=modifier.name)

    # 细分把平面切成了更多面且锐边属性不会被继承，重新标记一次
    _mark_smooth(obj)
