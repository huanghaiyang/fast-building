"""生成可离线使用的程序化 PBR 贴图。

基础套件：砖墙 / 混凝土 / 屋面瓦；
中世纪套件：灰泥抹面 / 石块砌体 / 木瓦屋面 / 橡木梁。

运行：
    D:\\thirdparty\\venvs\\fastbuild\\Scripts\\python.exe tools\\make_sample_textures.py

产物写入 data/texturesets/<id>/，包括 basecolor.png、normal.png、orm.png 与 set.json。
这些贴图完全由代码生成，可用于演示与端到端测试，不涉及第三方版权。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.textures import normal_from_height  # noqa: E402

# 演示贴图使用 512，兼顾细节与 GLB 体积（完整管线支持至 2048）
SIZE = 512


def _noise(seed: int, strength: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, strength, (SIZE, SIZE)).clip(-1.0, 1.0)


def _to_rgb(array: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="RGB")


def _to_gray(array: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), mode="L")


def brick() -> dict:
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    row_h, brick_w, mortar = 64, 208, 7
    row = yy // row_h
    offset = (row % 2) * (brick_w // 2)
    bx = (xx + offset) % brick_w
    by = yy % row_h
    is_mortar = (bx < mortar) | (by < mortar)

    brick_id = ((xx + offset) // brick_w + row * 17).astype(np.int64)
    rng = np.random.default_rng(brick_id)
    tint = rng.uniform(-16, 16, brick_id.shape)

    base = np.stack(
        [np.full_like(xx, 158.0), np.full_like(xx, 74.0), np.full_like(xx, 58.0)], axis=-1
    )
    base += tint[..., None] + _noise(11, 8.0)[..., None]
    mortar_color = np.array([198.0, 193.0, 184.0])
    base[is_mortar] = mortar_color + _noise(12, 5.0)[is_mortar][:, None]

    height = np.where(is_mortar, 0.32, 1.0) + _noise(13, 0.05)
    roughness = np.where(is_mortar, 0.88, 0.62) + _noise(14, 0.04)
    ao = np.where(is_mortar, 0.55, 0.98) + _noise(15, 0.02)
    metallic = np.zeros_like(height)

    return _save_set(
        "brick_red",
        "红砖外墙",
        tile_m=2.0,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def concrete() -> dict:
    xx, yy = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    smooth = (
        np.sin(xx / 53.0) * 0.5
        + np.sin(yy / 71.0 + 1.3) * 0.5
        + np.sin((xx + yy) / 137.0) * 0.35
    )
    grain = _noise(21, 5.0)
    value = 152.0 + smooth * 7.0 + grain
    base = np.stack([value, value * 0.995, value * 0.97], axis=-1)

    joint = ((xx % 512) < 4) | ((yy % 512) < 4)
    base[joint] = 118.0
    height = np.where(joint, 0.55, 1.0) + _noise(22, 0.02)
    roughness = np.where(joint, 0.9, 0.72) + _noise(23, 0.03)
    ao = np.where(joint, 0.6, 0.98)
    metallic = np.zeros((SIZE, SIZE))

    return _save_set(
        "concrete_gray",
        "清水混凝土",
        tile_m=2.5,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def roof_tile() -> dict:
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    row_h = 48
    wave = np.sin((yy % row_h) / row_h * np.pi)
    row_shadow = np.where((yy % row_h) < 6, 0.55, 1.0)
    column_wave = 0.5 + 0.5 * np.sin(xx / 26.0 * np.pi)

    base = np.stack(
        [
            np.full_like(xx, 116.0),
            np.full_like(xx, 58.0),
            np.full_like(xx, 46.0),
        ],
        axis=-1,
    )
    base *= (0.78 + 0.22 * column_wave)[..., None] * row_shadow[..., None]
    base += _noise(31, 4.0)[..., None]

    height = wave * 0.6 + 0.4 + _noise(32, 0.02)
    roughness = 0.58 + _noise(33, 0.05)
    ao = 0.75 + 0.25 * wave
    metallic = np.zeros((SIZE, SIZE))

    return _save_set(
        "roof_tile",
        "陶土屋面瓦",
        tile_m=2.0,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def plaster() -> dict:
    """奶油色灰泥抹面，适合木筋墙的填充面板。"""
    xx, yy = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    mottle = (
        np.sin(xx / 37.0) * 0.5
        + np.sin(yy / 43.0 + 0.7) * 0.5
        + np.sin((xx - yy) / 91.0) * 0.35
    )
    grain = _noise(41, 4.0)
    value = 226.0 + mottle * 6.0 + grain
    base = np.stack([value, value * 0.985, value * 0.94], axis=-1)

    height = 1.0 + _noise(42, 0.03)
    roughness = 0.9 + _noise(43, 0.02)
    ao = 0.98 + _noise(44, 0.01)
    metallic = np.zeros((SIZE, SIZE))

    return _save_set(
        "plaster_cream",
        "奶油灰泥",
        tile_m=2.0,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def stone() -> dict:
    """错缝石块砌体，用于中世纪石堡墙面与压顶。"""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    row_h, block_w, mortar = 74, 150, 6
    row = yy // row_h
    offset = (row % 2) * (block_w // 2)
    bx = (xx + offset) % block_w
    by = yy % row_h
    is_mortar = (bx < mortar) | (by < mortar)

    block_id = ((xx + offset) // block_w + row * 23).astype(np.int64)
    rng = np.random.default_rng(block_id)
    tint = rng.uniform(-14, 14, block_id.shape)

    base = np.stack(
        [np.full_like(xx, 168.0), np.full_like(xx, 162.0), np.full_like(xx, 150.0)], axis=-1
    )
    base += tint[..., None] + _noise(51, 7.0)[..., None]
    base[is_mortar] = np.array([132.0, 128.0, 120.0]) + _noise(52, 5.0)[is_mortar][:, None]

    height = np.where(is_mortar, 0.42, 1.0) + _noise(53, 0.03)
    roughness = np.where(is_mortar, 0.92, 0.76) + _noise(54, 0.03)
    ao = np.where(is_mortar, 0.58, 0.97) + _noise(55, 0.02)
    metallic = np.zeros_like(height)

    return _save_set(
        "stone_ashlar",
        "石块砌体",
        tile_m=2.5,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def shingle() -> dict:
    """木瓦屋面：横向层叠、竖向错缝。"""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    row_h, shingle_w, joint_w = 54, 86, 5
    row = yy // row_h
    offset = (row % 2) * (shingle_w // 2)
    joint = ((xx + offset) % shingle_w) < joint_w
    row_shadow = np.where((yy % row_h) < 6, 0.62, 1.0)
    taper = 0.86 + 0.14 * np.sin((yy % row_h) / row_h * np.pi)

    base = np.stack(
        [np.full_like(xx, 92.0), np.full_like(xx, 66.0), np.full_like(xx, 48.0)], axis=-1
    )
    base *= (row_shadow * taper)[..., None]
    base[joint] *= 0.7
    base += _noise(61, 4.0)[..., None]

    height = np.where(joint, 0.55, 1.0) * taper + _noise(62, 0.02)
    roughness = 0.82 + _noise(63, 0.04)
    ao = np.where(joint, 0.6, 0.96)
    metallic = np.zeros((SIZE, SIZE))

    return _save_set(
        "roof_shingle",
        "木瓦屋面",
        tile_m=2.0,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def timber() -> dict:
    """深色橡木梁，沿 U 方向拉出木纹。"""
    xx, yy = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    grain = (
        np.sin(xx / 6.0 + np.sin(yy / 23.0) * 1.6) * 0.5
        + np.sin(xx / 17.0 + 0.9) * 0.3
    )
    value = 74.0 + grain * 14.0 + _noise(71, 3.0)
    base = np.stack([value, value * 0.70, value * 0.48], axis=-1)

    height = 1.0 + grain * 0.06 + _noise(72, 0.02)
    roughness = 0.8 + _noise(73, 0.04)
    ao = 0.96 + _noise(74, 0.02)
    metallic = np.zeros((SIZE, SIZE))

    return _save_set(
        "timber_oak",
        "深色橡木",
        tile_m=1.5,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def _save_set(
    set_id: str,
    display_name: str,
    tile_m: float,
    basecolor: np.ndarray,
    height: np.ndarray,
    roughness: np.ndarray,
    ao: np.ndarray,
    metallic: np.ndarray,
) -> dict:
    target = ROOT / "data" / "texturesets" / set_id
    target.mkdir(parents=True, exist_ok=True)

    base_img = _to_rgb(basecolor)
    height_img = _to_gray(height * 255.0)
    rough_img = _to_gray(roughness * 255.0)
    ao_img = _to_gray(ao * 255.0)
    metal_img = _to_gray(metallic * 255.0)
    normal_img = normal_from_height(height_img, strength=2.2)

    base_img.save(target / "basecolor.png", optimize=True)
    normal_img.save(target / "normal.png", optimize=True)
    height_img.save(target / "height.png", optimize=True)

    orm = Image.merge("RGB", (ao_img, rough_img, metal_img))
    orm.save(target / "orm.png", optimize=True)

    meta = {
        "name": set_id,
        "display_name": display_name,
        "tile_m": tile_m,
        "resolution": SIZE,
        "license": "procedural-generated",
        "source": "generated by tools/make_sample_textures.py",
        "channels": {
            "basecolor": "basecolor.png",
            "normal": "normal.png",
            "orm": "orm.png",
            "height": "height.png",
        },
    }
    (target / "set.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"generated {set_id}")
    return meta


if __name__ == "__main__":
    brick()
    concrete()
    roof_tile()
    plaster()
    stone()
    shingle()
    timber()
