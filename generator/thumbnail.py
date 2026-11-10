"""模块缩略图渲染。

用 Workbench 引擎把当前场景里的模块几何渲染成透明背景 PNG：
无需外部 HDR、无需 GPU 光追，单张渲染通常在 1 秒内完成，
贴图颜色仍来自材质 basecolor，能直观反映模块形态与材质。
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector

THUMB_WIDTH = 480
THUMB_HEIGHT = 360
LENS_MM = 50.0
SENSOR_MM = 36.0


def _scene_bounds() -> tuple[Vector, Vector]:
    low = Vector((1e18, 1e18, 1e18))
    high = Vector((-1e18, -1e18, -1e18))
    found = False
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        found = True
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            low.x, low.y, low.z = min(low.x, point.x), min(low.y, point.y), min(low.z, point.z)
            high.x = max(high.x, point.x)
            high.y = max(high.y, point.y)
            high.z = max(high.z, point.z)
    if not found:
        return Vector((0.0, 0.0, 0.0)), Vector((1.0, 1.0, 1.0))
    return low, high


def render_thumbnail(png_path: Path) -> Path:
    """以 3/4 视角渲染当前场景，输出 RGBA PNG。"""
    scene = bpy.context.scene
    low, high = _scene_bounds()
    center = (low + high) * 0.5
    size = high - low

    camera_data = bpy.data.cameras.new("THUMB_CAM")
    camera_data.lens = LENS_MM
    camera_data.sensor_width = SENSOR_MM
    camera_data.clip_start = 0.01
    camera = bpy.data.objects.new("THUMB_CAM", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    radius = max(size.length * 0.5, 0.4)
    # 以纵向视场角计算距离：纵向更窄，只用横向角会把宽扁构件裁掉
    fov_x = 2.0 * math.atan(SENSOR_MM / (2.0 * LENS_MM))
    fov_y = 2.0 * math.atan(math.tan(fov_x * 0.5) * THUMB_HEIGHT / THUMB_WIDTH)
    distance = radius / math.sin(fov_y * 0.5) * 0.98
    # 与前端预览一致的 3/4 视角：从前方（-Y）、右方（+X）、上方（+Z）看
    direction = Vector((0.92, -1.35, 0.82)).normalized()
    camera.location = center + direction * distance
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.clip_end = distance * 12.0

    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "TEXTURE"
    shading.show_shadows = True
    shading.shadow_intensity = 0.45
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.curvature_ridge_factor = 1.0
    shading.curvature_valley_factor = 1.2
    shading.show_specular_highlight = True
    scene.display.render_aa = "8"

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = True
    scene.render.resolution_x = THUMB_WIDTH
    scene.render.resolution_y = THUMB_HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(png_path)

    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(camera, do_unlink=True)
    return png_path
