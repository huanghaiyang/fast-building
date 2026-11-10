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


def thatch_straw() -> dict:
    """金色茅草：宽度随机的竖草 + 大尺度色块 + 低对比压层。"""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    rng = np.random.default_rng(101)

    # 草茎：随机宽度的竖条并做轻微平滑，避免出现等距的规则条纹
    widths = rng.integers(1, 4, SIZE // 2)
    cols = np.repeat(rng.normal(0.0, 1.0, SIZE // 2), widths)[:SIZE]
    if cols.size < SIZE:
        cols = np.pad(cols, (0, SIZE - cols.size), mode="wrap")
    padded = np.concatenate([cols[-4:], cols, cols[:4]])
    cols = np.convolve(padded, np.ones(5) / 5.0, mode="same")[4:-4]
    cols = (cols - cols.mean()) / (cols.std() + 1e-6)
    fibre = cols[None, :] * 0.62 + np.sin(xx / 13.0 + 1.1) * 0.18

    # 草束：更宽的成把草，让近景能读出「一束一束」的草
    coarse_cols = np.repeat(rng.normal(0.0, 1.0, 48), SIZE // 48 + 1)[:SIZE]
    coarse_cols = np.convolve(
        np.concatenate([coarse_cols[-10:], coarse_cols, coarse_cols[:10]]),
        np.ones(21) / 21.0,
        mode="same",
    )[10:-10]
    coarse = (coarse_cols - coarse_cols.mean()) / (coarse_cols.std() + 1e-6)

    # 大尺度色块：多组随机频率正弦叠加，既有自然团块感又能无缝平铺
    clump = np.zeros((SIZE, SIZE))
    for _ in range(56):
        kx = int(rng.integers(1, 8))
        ky = int(rng.integers(1, 8))
        amp = rng.uniform(0.6, 2.2) / (kx + ky)
        phase = rng.uniform(0.0, 2.0 * np.pi)
        clump += amp * np.sin(2.0 * np.pi * (kx * xx + ky * yy) / SIZE + phase)
    clump *= 3.0

    # 压层：每层约 0.4 m，边界用窄高斯压暗，对比刻意压低
    drift = np.sin(2.0 * np.pi * xx * 2 / SIZE) * 8.0 + np.sin(
        2.0 * np.pi * xx * 5 / SIZE + 1.3
    ) * 4.0
    layer = ((yy + drift) % 168.0) / 168.0
    layer_shadow = 1.0 - 0.10 * np.exp(-layer * 168.0 / 16.0)

    value = (
        226.0 + fibre * 22.0 + coarse[None, :] * 9.0 + clump + _noise(103, 3.0)
    ) * layer_shadow
    warm = 0.86 + clump / 300.0
    base = np.stack([value, value * warm, value * (warm - 0.38)], axis=-1)

    height = (
        (0.45 + 0.55 * layer)
        + fibre * 0.07
        + coarse[None, :] * 0.03
        + clump / 500.0
        + _noise(104, 0.02)
    )
    roughness = np.minimum(0.94 + _noise(105, 0.02), 1.0)
    ao = np.clip(layer_shadow, 0.78, 1.0)
    metallic = np.zeros_like(height)

    return _save_set(
        "thatch_straw",
        "金色茅草",
        tile_m=1.5,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def log_bark() -> dict:
    """原木树皮：纹理沿 U 方向拉长，UV 的 U 轴对齐圆木轴向。"""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    grain = (
        np.sin(yy / 7.5 + np.sin(xx / 47.0) * 2.4) * 0.5
        + np.sin(yy / 19.0 + 0.6) * 0.3
    )
    knot = np.sin(xx / 83.0 + np.sin(yy / 37.0) * 1.8)
    # 纵向裂缝沿原木轴向（与木纹同向）
    crack = (np.abs(np.sin(yy / 57.0 + np.sin(xx / 29.0) * 1.3)) > 0.986).astype(float)
    value = 118.0 + grain * 24.0 + knot * 7.0 + _noise(111, 5.0) - crack * 34.0
    base = np.stack([value, value * 0.84, value * 0.72], axis=-1)

    height = 1.0 + grain * 0.09 - crack * 0.34 + _noise(112, 0.02)
    roughness = 0.86 + _noise(113, 0.03)
    ao = 0.93 - crack * 0.28 + _noise(114, 0.01)
    metallic = np.zeros_like(height)

    return _save_set(
        "log_bark",
        "原木树皮",
        tile_m=0.9,
        basecolor=base,
        height=height,
        roughness=roughness,
        ao=ao,
        metallic=metallic,
    )


def stone_rubble() -> dict:
    """毛石勒脚：抖动网格的 Voronoi 石块 + 均匀灰缝，边界不规则且可无缝平铺。"""
    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)
    cell = 64
    n = SIZE // cell
    rng = np.random.default_rng(121)
    jx = rng.uniform(0.12, 0.88, (n, n)) * cell
    jy = rng.uniform(0.12, 0.88, (n, n)) * cell
    tint = rng.uniform(-9.0, 9.0, (n, n))

    gx = (xx // cell).astype(np.int64)
    gy = (yy // cell).astype(np.int64)
    stack = np.empty((9, SIZE, SIZE), dtype=np.float64)
    ids = np.empty((9, SIZE, SIZE), dtype=np.int64)
    slot = 0
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cgx = (gx + ox) % n
            cgy = (gy + oy) % n
            sx = (gx + ox) * cell + jx[cgy, cgx]
            sy = (gy + oy) * cell + jy[cgy, cgx]
            stack[slot] = np.hypot(xx - sx, yy - sy)
            ids[slot] = cgy * n + cgx
            slot += 1

    order = np.argsort(stack, axis=0)
    d1 = np.take_along_axis(stack, order[0:1], axis=0)[0]
    d2 = np.take_along_axis(stack, order[1:2], axis=0)[0]
    stone_id = np.take_along_axis(ids, order[0:1], axis=0)[0]
    flat = stone_id % (n * n)
    tint_map = tint.reshape(-1)[flat]

    # 到 Voronoi 边界的距离：灰缝宽度均匀，石块轮廓自然
    edge = (d2 - d1) * 0.5
    is_stone = edge > 2.6
    dome = np.clip(edge / 22.0, 0.0, 1.0)

    value = 118.0 + tint_map + _noise(123, 6.0) + dome * 16.0
    base = np.stack([value, value * 0.985, value * 0.95], axis=-1)
    base[~is_stone] = np.array([92.0, 90.0, 85.0]) + _noise(124, 4.0)[~is_stone][:, None]
    # 苔藓与雨渍：低频色差，避免整面石头过于均匀
    dirt = (np.sin(xx / 197.0 + yy / 151.0) * 0.5 + 0.5) * 14.0
    base[..., 1] += np.where(is_stone, dirt * 0.55, dirt * 0.25)

    height = np.where(is_stone, 0.32 + 0.68 * dome, 0.16) + _noise(125, 0.02)
    roughness = np.where(is_stone, 0.86, 0.94) + _noise(126, 0.02)
    ao = np.where(is_stone, 0.72 + 0.28 * dome, 0.55)
    metallic = np.zeros_like(height)

    return _save_set(
        "stone_rubble",
        "毛石砌体",
        tile_m=1.6,
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
    thatch_straw()
    log_bark()
    stone_rubble()
