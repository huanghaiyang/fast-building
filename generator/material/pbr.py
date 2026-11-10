"""PBR 材质库。

约定每套贴图集包含：
- ``basecolor.png``（sRGB）
- ``normal.png``（切线空间法线）
- ``orm.png``（R=AO / G=Roughness / B=Metallic，Non-Color）

ORM 单图三通道是 glTF 的推荐做法，也能让 Blender 导出器复用同一张纹理，
避免因通道来源不同而拆成多张图导致 GLB 体积膨胀。
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy

DEFAULT_TILES = {
    "facade": 2.0,
    "trim": 2.0,
    "roof": 2.0,
    "door": 2.0,
    "glass": 2.0,
    # 茅草农舍构件：圆木、茅草、毛石
    "log": 0.9,
    "thatch": 1.2,
    "stone": 1.6,
}

FALLBACK_COLORS = {
    "facade": (0.52, 0.50, 0.46, 1.0),
    "trim": (0.68, 0.67, 0.63, 1.0),
    "roof": (0.28, 0.13, 0.10, 1.0),
    "door": (0.09, 0.07, 0.06, 1.0),
    "glass": (0.55, 0.72, 0.80, 0.32),
    "log": (0.30, 0.18, 0.10, 1.0),
    "thatch": (0.62, 0.46, 0.18, 1.0),
    "stone": (0.44, 0.43, 0.40, 1.0),
}


class MaterialLibrary:
    """按槽位提供 Blender 材质，并记录各槽的真实贴图尺寸（tile_m）。"""

    def __init__(self, data_dir: Path, chosen_set: str, style: dict) -> None:
        self.data_dir = data_dir
        self.textures_dir = data_dir / "texturesets"
        self.chosen_set = chosen_set
        self.slot_sets = self._resolve_slot_sets(style)
        self.tiles = self._resolve_tiles()
        self._materials: dict[str, bpy.types.Material] = {}
        self._gltf_group = self._ensure_gltf_group()

    # ------------------------------------------------------------------ 贴图集选择
    def _set_exists(self, set_id: str | None) -> bool:
        if not set_id:
            return False
        return (self.textures_dir / set_id / "set.json").exists()

    def _resolve_slot_sets(self, style: dict) -> dict[str, str]:
        palette = style.get("palette") or {}
        facade = self.chosen_set
        if not self._set_exists(facade):
            facade = ""

        def pick(key: str) -> str:
            candidate = palette.get(key)
            return candidate if self._set_exists(candidate) else facade

        mapping = {
            "facade": facade,
            "trim": pick("trim"),
            "roof": pick("roof"),
            # 入户门默认使用深色实体材质，不跟随外墙贴图
            "door": palette.get("door") if self._set_exists(palette.get("door")) else "",
            "glass": "",
            # 茅草农舍专用槽位；未配置时回退到纯色材质
            "log": pick("log"),
            "thatch": pick("thatch"),
            "stone": pick("stone"),
        }
        return mapping

    def _resolve_tiles(self) -> dict[str, float]:
        tiles = dict(DEFAULT_TILES)
        cache: dict[str, float] = {}
        for slot, set_id in self.slot_sets.items():
            if not set_id:
                continue
            if set_id not in cache:
                meta_path = self.textures_dir / set_id / "set.json"
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    cache[set_id] = float(meta.get("tile_m", 2.0))
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    cache[set_id] = 2.0
            tiles[slot] = cache[set_id]
        return tiles

    def texture_summary(self) -> dict[str, str]:
        return {slot: set_id for slot, set_id in self.slot_sets.items() if set_id}

    # ------------------------------------------------------------------ 材质获取
    def get(self, slot: str) -> bpy.types.Material:
        if slot == "glass":
            key = "glass"
        elif slot == "door" and not self.slot_sets.get("door"):
            key = "door_plain"
        else:
            set_id = self.slot_sets.get(slot)
            key = f"set:{set_id}" if set_id else f"plain:{slot}"

        cached = self._materials.get(key)
        if cached is not None:
            return cached

        if key == "glass":
            mat = self._create_glass()
        elif key == "door_plain":
            mat = self._create_plain("door")
        elif key.startswith("set:"):
            mat = self._create_textured(key[4:], slot)
        else:
            mat = self._create_plain(slot)
        self._materials[key] = mat
        return mat

    def _create_plain(self, slot: str) -> bpy.types.Material:
        mat = bpy.data.materials.new(f"FB_{slot}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        color = FALLBACK_COLORS.get(slot, (0.6, 0.6, 0.6, 1.0))
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color
            bsdf.inputs["Roughness"].default_value = 0.8
            bsdf.inputs["Metallic"].default_value = 0.0
        mat.use_backface_culling = False
        return mat

    def _create_glass(self) -> bpy.types.Material:
        mat = bpy.data.materials.new("FB_glass")
        mat.use_nodes = True
        mat.use_backface_culling = False
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = FALLBACK_COLORS["glass"]
            bsdf.inputs["Alpha"].default_value = 0.32
            bsdf.inputs["Roughness"].default_value = 0.06
            bsdf.inputs["Metallic"].default_value = 0.0
            if "IOR" in bsdf.inputs:
                bsdf.inputs["IOR"].default_value = 1.45
        # Blender 4.2+ 使用 surface_render_method；旧版本使用 blend_method
        if hasattr(mat, "surface_render_method"):
            try:
                mat.surface_render_method = "BLENDED"
            except (TypeError, ValueError):
                pass
        if hasattr(mat, "blend_method"):
            try:
                mat.blend_method = "BLEND"
            except (TypeError, ValueError):
                pass
        return mat

    def _create_textured(self, set_id: str, slot: str) -> bpy.types.Material:
        directory = self.textures_dir / set_id
        base_image = self._load_image(directory / "basecolor.png", "sRGB")
        normal_image = self._load_image(directory / "normal.png", "Non-Color")
        orm_image = self._load_image(directory / "orm.png", "Non-Color")

        mat = bpy.data.materials.new(f"PBR_{set_id}")
        mat.use_nodes = True
        mat.use_backface_culling = False
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        bsdf = nodes.get("Principled BSDF")

        if base_image and bsdf:
            tex = nodes.new("ShaderNodeTexImage")
            tex.image = base_image
            tex.location = (-620, 320)
            links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

        if normal_image and bsdf:
            tex_n = nodes.new("ShaderNodeTexImage")
            tex_n.image = normal_image
            tex_n.location = (-620, 20)
            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (-320, 20)
            normal_map.inputs["Strength"].default_value = 1.0
            links.new(tex_n.outputs["Color"], normal_map.inputs["Color"])
            links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

        if orm_image and bsdf:
            tex_o = nodes.new("ShaderNodeTexImage")
            tex_o.image = orm_image
            tex_o.location = (-620, -280)
            separate = nodes.new("ShaderNodeSeparateColor")
            separate.location = (-340, -280)
            links.new(tex_o.outputs["Color"], separate.inputs["Color"])
            # glTF 约定：G=Roughness，B=Metallic，R=Occlusion
            links.new(separate.outputs["Green"], bsdf.inputs["Roughness"])
            links.new(separate.outputs["Blue"], bsdf.inputs["Metallic"])
            group_node = nodes.new("ShaderNodeGroup")
            group_node.node_tree = self._gltf_group
            group_node.location = (-120, -420)
            if "Occlusion" in group_node.inputs:
                links.new(separate.outputs["Red"], group_node.inputs["Occlusion"])

        return mat

    # ------------------------------------------------------------------ 工具方法
    def _load_image(self, path: Path, colorspace: str) -> bpy.types.Image | None:
        if not path.exists():
            return None
        image = bpy.data.images.load(str(path), check_existing=True)
        try:
            image.colorspace_settings.name = colorspace
        except TypeError:
            pass
        return image

    @staticmethod
    def _ensure_gltf_group() -> bpy.types.NodeTree:
        """创建导出器识别的 ``glTF Material Output`` 节点组（用于 AO 输出）。"""
        name = "glTF Material Output"
        group = bpy.data.node_groups.get(name)
        if group is None:
            group = bpy.data.node_groups.new(name, "ShaderNodeTree")
        existing = {item.name for item in group.interface.items_tree}
        for socket_name in ("Occlusion", "Thickness", "Dispersion", "Iridescence Factor"):
            if socket_name not in existing:
                try:
                    group.interface.new_socket(socket_name, socket_type="NodeSocketFloat")
                except (TypeError, ValueError):
                    pass
        if not any(node.bl_idname == "NodeGroupInput" for node in group.nodes):
            group.nodes.new("NodeGroupInput")
        if not any(node.bl_idname == "NodeGroupOutput" for node in group.nodes):
            group.nodes.new("NodeGroupOutput")
        return group
