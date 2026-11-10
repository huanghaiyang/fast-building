"""PBR 贴图集的规范化与 ORM 打包。

约定（与 glTF / three.js 对齐）：
- ``basecolor.png``：sRGB 颜色；
- ``normal.png``：切线空间法线（Non-Color）；
- ``orm.png``：R=AO、G=Roughness、B=Metallic，单张贴图承载三个通道，
  避免 Blender 导出器因源图尺寸/来源不同而拆成多张、造成 GLB 体积膨胀；
- ``height.png``：仅存档，glTF 不支持视差贴图，不参与导出。

所有贴图统一为 2 的幂尺寸（最长边 2048），方形。
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageFile

from ..config import MAX_TEXTURE_SIZE, TEXTURES_DIR

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = 64_000_000


def slugify(name: str) -> str:
    """把用户输入的名字转成安全的目录名（仅 ASCII 字母数字、下划线、短横线）。"""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return cleaned or "textureset"


def _pow2(value: int) -> int:
    value = max(16, min(value, MAX_TEXTURE_SIZE))
    return 1 << (value - 1).bit_length()


def _open_image(raw: bytes) -> Image.Image:
    return Image.open(io.BytesIO(raw))


def _square_gray(raw: bytes, size: int, fill: int) -> Image.Image:
    img = _open_image(raw).convert("L").resize((size, size), Image.LANCZOS)
    if img.getextrema() == (fill, fill):
        return img
    return img


def _square_rgb(raw: bytes, size: int, fill: tuple[int, int, int]) -> Image.Image:
    img = _open_image(raw).convert("RGB").resize((size, size), Image.LANCZOS)
    if img.getextrema() == ((fill[0], fill[0]), (fill[1], fill[1]), (fill[2], fill[2])):
        return img
    return img


def normal_from_height(height: Image.Image, strength: float = 2.0) -> Image.Image:
    """用 Sobel 梯度从高度图推导切线空间法线，作为缺省法线图的兜底。"""
    h = np.asarray(height.convert("L"), dtype=np.float32) / 255.0
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * strength
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * strength
    nx, ny, nz = -dx, -dy, np.ones_like(h)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / length, ny / length, nz / length
    rgb = np.stack([nx * 0.5 + 0.5, ny * 0.5 + 0.5, nz * 0.5 + 0.5], axis=-1)
    return Image.fromarray((rgb * 255).astype(np.uint8), mode="RGB")


def pack_orm(
    ao: Image.Image | None,
    roughness: Image.Image | None,
    metallic: Image.Image | None,
    size: int,
) -> Image.Image:
    """把 AO / Roughness / Metallic 三个灰度通道打包为 glTF 风格的 ORM 图。"""
    r = np.full((size, size), 255, dtype=np.uint8)
    g = np.full((size, size), 180, dtype=np.uint8)
    b = np.full((size, size), 0, dtype=np.uint8)
    if ao is not None:
        r = np.asarray(ao.resize((size, size), Image.LANCZOS), dtype=np.uint8)
    if roughness is not None:
        g = np.asarray(roughness.resize((size, size), Image.LANCZOS), dtype=np.uint8)
    if metallic is not None:
        b = np.asarray(metallic.resize((size, size), Image.LANCZOS), dtype=np.uint8)
    return Image.fromarray(np.stack([r, g, b], axis=-1), mode="RGB")


def build_textureset(
    name: str,
    files: dict[str, bytes],
    tile_m: float = 2.0,
    license_text: str = "",
    source: str = "",
) -> dict:
    """接收原始通道字节流，输出规范化的贴图目录并返回元数据。

    ``files`` 的键为 basecolor / normal / roughness / metallic / ao / height，
    缺失的通道使用合理默认值（AO=1、Roughness=0.7、Metallic=0）。
    """
    set_id = slugify(name)
    target = TEXTURES_DIR / set_id
    target.mkdir(parents=True, exist_ok=True)

    # 以 basecolor 的尺寸为基准，统一所有通道
    if "basecolor" in files:
        base_ref = _open_image(files["basecolor"])
        size = _pow2(max(base_ref.size))
    else:
        size = 1024

    basecolor = None
    if "basecolor" in files:
        basecolor = _square_rgb(files["basecolor"], size, (128, 128, 128))
    else:
        # 单色兜底，保证预览不是一片纯黑
        basecolor = Image.new("RGB", (size, size), (168, 168, 164))

    height = None
    if "height" in files:
        height = _square_gray(files["height"], size, 0)

    if "normal" in files:
        normal = _square_rgb(files["normal"], size, (128, 128, 255))
    elif height is not None:
        normal = normal_from_height(height)
    else:
        normal = Image.new("RGB", (size, size), (128, 128, 255))

    ao = _square_gray(files["ao"], size, 255) if "ao" in files else None
    roughness = (
        _square_gray(files["roughness"], size, 180) if "roughness" in files else None
    )
    metallic = _square_gray(files["metallic"], size, 0) if "metallic" in files else None
    orm = pack_orm(ao, roughness, metallic, size)

    basecolor.save(target / "basecolor.png", optimize=True)
    normal.save(target / "normal.png", optimize=True)
    orm.save(target / "orm.png", optimize=True)
    if height is not None:
        height.save(target / "height.png", optimize=True)

    meta = {
        "name": set_id,
        "display_name": name,
        "tile_m": float(tile_m),
        "resolution": size,
        "license": license_text,
        "source": source,
        "channels": {
            "basecolor": "basecolor.png",
            "normal": "normal.png",
            "orm": "orm.png",
            "height": "height.png" if height is not None else None,
        },
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    (target / "set.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def read_set(set_id: str) -> dict | None:
    meta_path = TEXTURES_DIR / set_id / "set.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_sets() -> list[dict]:
    result: list[dict] = []
    if not TEXTURES_DIR.exists():
        return result
    for child in sorted(TEXTURES_DIR.iterdir()):
        if not child.is_dir():
            continue
        meta = read_set(child.name)
        if meta is None:
            continue
        preview = child / "basecolor.png"
        meta = dict(meta)
        meta["id"] = child.name
        meta["preview"] = f"/tex/{child.name}/{preview.name}" if preview.exists() else None
        result.append(meta)
    return result
