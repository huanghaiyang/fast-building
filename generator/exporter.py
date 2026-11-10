"""GLB 导出封装。

只保留 Blender 各版本都稳定的导出参数，并通过 RNA 属性过滤避免版本差异导致的
``TypeError``。
"""

from __future__ import annotations

from pathlib import Path

import bpy


def export_glb(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    desired = {
        "filepath": str(target),
        "export_format": "GLB",
        "use_selection": False,
        "export_apply": True,
        "export_yup": True,
        "export_texcoords": True,
        "export_normals": True,
        "export_materials": "EXPORT",
        "export_extras": True,
        "export_image_format": "AUTO",
        "export_cameras": False,
        "export_lights": False,
        "export_animations": False,
    }

    available = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    kwargs = {key: value for key, value in desired.items() if key in available or key == "filepath"}
    bpy.ops.export_scene.gltf(**kwargs)
    return target
