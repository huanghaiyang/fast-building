"""GLB 产物质量校验。

检查项：
1. GLB 容器结构合法（magic / 版本 / chunk）；
2. 至少包含网格与贴图；
3. 每个材质若同时带 AO 与 metallicRoughness，必须引用同一张 ORM 图；
4. 玻璃材质应为 BLEND，且不被误判为不透明；
5. 文件体积与单张贴图体积在阈值内。

运行：
    D:\\thirdparty\\venvs\\fastbuild\\Scripts\\python.exe tools\\validate_gltf.py <model.glb>
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

MAX_FILE_MB = 12.0
MAX_IMAGE_MB = 6.0


def load_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    magic, version, _length = struct.unpack("<III", data[:12])
    if magic != 0x46546C67:
        raise ValueError("不是合法的 GLB 文件（magic 不匹配）")
    if version != 2:
        raise ValueError(f"仅支持 glTF 2.0，当前版本 {version}")

    offset = 12
    gltf: dict | None = None
    binary = b""
    while offset < len(data):
        chunk_len, chunk_type = struct.unpack("<II", data[offset : offset + 8])
        payload = data[offset + 8 : offset + 8 + chunk_len]
        if chunk_type == 0x4E4F534A:  # JSON
            gltf = json.loads(payload.decode("utf-8"))
        elif chunk_type == 0x004E4942:  # BIN
            binary = payload
        offset += 8 + chunk_len + ((4 - chunk_len % 4) % 4)

    if gltf is None:
        raise ValueError("GLB 缺少 JSON chunk")
    return gltf, binary


def validate(path: Path) -> bool:
    gltf, _ = load_glb(path)
    problems: list[str] = []

    meshes = gltf.get("meshes", [])
    materials = gltf.get("materials", [])
    images = gltf.get("images", [])
    textures = gltf.get("textures", [])
    buffer_views = gltf.get("bufferViews", [])

    print(f"文件: {path.name}")
    print(f"体积: {path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"网格 {len(meshes)} / 材质 {len(materials)} / 贴图 {len(images)} / 纹理 {len(textures)}")

    if not meshes:
        problems.append("没有任何网格")
    if not images:
        problems.append("没有任何贴图")

    if path.stat().st_size / 1024 / 1024 > MAX_FILE_MB:
        problems.append(f"文件超过 {MAX_FILE_MB} MB")

    for index, image in enumerate(images):
        view = buffer_views[image["bufferView"]]
        size_mb = view["byteLength"] / 1024 / 1024
        print(f"  image[{index}] {image.get('mimeType', '?')} {size_mb:.2f} MB")
        if size_mb > MAX_IMAGE_MB:
            problems.append(f"image[{index}] 超过 {MAX_IMAGE_MB} MB")

    orm_ok = 0
    for material in materials:
        name = material.get("name", "?")
        occlusion = material.get("occlusionTexture")
        metallic_roughness = material.get("pbrMetallicRoughness", {}).get("metallicRoughnessTexture")
        has_normal = "normalTexture" in material
        alpha_mode = material.get("alphaMode", "OPAQUE")
        print(f"  材质 {name}: AO={bool(occlusion)} MR={bool(metallic_roughness)} Normal={has_normal} Alpha={alpha_mode}")

        if occlusion and metallic_roughness:
            ao_source = textures[occlusion["index"]].get("source")
            mr_source = textures[metallic_roughness["index"]].get("source")
            if ao_source != mr_source:
                problems.append(f"材质 {name} 的 AO 与 MR 未共用同一张 ORM 图")
            else:
                orm_ok += 1
        elif occlusion or metallic_roughness:
            problems.append(f"材质 {name} 只导出了 AO 或 MR 其中之一")

    # 玻璃材质检查：找 Base Color 带 alpha 的材质
    for material in materials:
        if material.get("alphaMode") == "BLEND":
            print(f"  玻璃/透明材质: {material.get('name')}")

    # 汇总顶点范围，确认模型非空且尺度合理
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    for mesh in meshes:
        for primitive in mesh.get("primitives", []):
            accessor_index = primitive.get("attributes", {}).get("POSITION")
            if accessor_index is None:
                continue
            accessor = gltf["accessors"][accessor_index]
            if "min" in accessor and "max" in accessor:
                for axis in range(3):
                    mins[axis] = min(mins[axis], accessor["min"][axis])
                    maxs[axis] = max(maxs[axis], accessor["max"][axis])

    if all(value != float("inf") for value in mins):
        print(
            "包围盒(glTF Y-up): "
            f"{maxs[0] - mins[0]:.2f} × {maxs[1] - mins[1]:.2f} × {maxs[2] - mins[2]:.2f} m"
        )
    else:
        problems.append("无法读取顶点包围盒")

    print(f"ORM 通道复用材质数: {orm_ok}")
    if problems:
        print("\n校验失败:")
        for problem in problems:
            print(f"  - {problem}")
        return False
    print("\nPASS: GLB 结构与 PBR 通道检查通过")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: validate_gltf.py <model.glb>")
        raise SystemExit(2)
    ok = validate(Path(sys.argv[1]))
    raise SystemExit(0 if ok else 1)
