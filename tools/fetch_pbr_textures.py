"""从 AmbientCG 批量下载 CC0 真实 PBR 贴图，并转换为平台贴图集格式。

AmbientCG（https://ambientcg.com）素材全部为 CC0 公共领域授权，可免费商用。
本脚本按类别抓取热门材质，取 1K-JPG 包中的 Color / NormalGL / Roughness /
AmbientOcclusion（部分材质含 Metalness），交给后端的 ``build_textureset``
统一打包为 basecolor.png + normal.png + orm.png（R=AO, G=Roughness, B=Metallic）。

用法：
    D:\\thirdparty\\venvs\\fastbuild\\Scripts\\python.exe tools\\fetch_pbr_textures.py
    ... --size 1024                # 更高清（GLB 会明显变大）
    ... --per-category 2           # 每类抓取数量（用于快速试跑）
    ... --only Bricks113A,Wood051  # 只抓指定素材

已存在的贴图集默认跳过，可加 --force 重新下载。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.textures import build_textureset  # noqa: E402

API = "https://ambientcg.com/api/v2/full_json"
VIEW_URL = "https://ambientcg.com/view?id={asset}"
LICENSE = "CC0 1.0 Universal（AmbientCG 公共领域素材，可免费商用）"
HEADERS = {"User-Agent": "FastBuildingTextureFetcher/1.0 (+local tool)"}

# 类别 -> (抓取数量, tile_m, 中文用途)
CATEGORIES: dict[str, tuple[int, float, str]] = {
    "Bricks": (4, 2.0, "砖墙"),
    "Plaster": (4, 2.0, "灰泥抹面"),
    "Rock": (5, 2.5, "天然石材"),
    "PavingStones": (3, 3.0, "铺地石"),
    "RoofingTiles": (5, 2.0, "屋面瓦"),
    "Planks": (4, 1.5, "木板"),
    "Wood": (4, 1.5, "原木梁"),
}

# zip 内文件后缀 -> build_textureset 的通道名
CHANNELS = {
    "_Color": "basecolor",
    "_NormalGL": "normal",
    "_Roughness": "roughness",
    "_AmbientOcclusion": "ao",
    "_Metalness": "metallic",
}


def fetch_json(url: str, attempts: int = 3) -> dict:
    for index in range(attempts):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - 网络抖动统一重试
            if index == attempts - 1:
                raise
            time.sleep(1.5 * (index + 1))
    return {}


def fetch_bytes(url: str, attempts: int = 3) -> bytes:
    for index in range(attempts):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except Exception:  # noqa: BLE001
            if index == attempts - 1:
                raise
            time.sleep(2.0 * (index + 1))
    return b""


def list_assets(category: str, limit: int) -> list[dict]:
    url = (
        f"{API}?type=Material&category={category}&sort=popular"
        f"&limit={limit}&include=downloadData"
    )
    data = fetch_json(url)
    return data.get("foundAssets") or []


def find_zip_url(asset: dict) -> str | None:
    """取 1K-JPG 压缩包（体积最小，后续再降采样）。"""
    folders = asset.get("downloadFolders") or {}
    for folder in folders.values():
        categories = (folder.get("downloadFiletypeCategories") or {}).get("zip") or {}
        for item in categories.get("downloads") or []:
            if item.get("attribute") == "1K-JPG":
                return item.get("downloadLink") or item.get("fullDownloadPath")
    return None


def extract_channels(raw: bytes) -> dict[str, bytes]:
    """从 zip 中按后缀取出各通道图像字节。"""
    picked: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for entry in archive.namelist():
            name = Path(entry).name
            suffix = Path(name).suffix.lower()
            if suffix not in (".jpg", ".jpeg", ".png"):
                continue
            if "NormalDX" in name:
                continue
            for marker, channel in CHANNELS.items():
                if marker in name and channel not in picked:
                    picked[channel] = archive.read(entry)
                    break
    return picked


def downscale(files: dict[str, bytes], size: int) -> dict[str, bytes]:
    """把各通道重采样到目标方形尺寸，控制 GLB 体积。"""
    result: dict[str, bytes] = {}
    for channel, raw in files.items():
        image = Image.open(io.BytesIO(raw))
        image = image.convert("RGB" if channel == "basecolor" else "L")
        if image.size != (size, size):
            image = image.resize((size, size), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        result[channel] = buffer.getvalue()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 AmbientCG CC0 PBR 贴图")
    parser.add_argument("--size", type=int, default=512, help="贴图边长（默认 512）")
    parser.add_argument("--per-category", type=int, default=0, help="覆盖每类抓取数量")
    parser.add_argument("--only", default="", help="只抓指定素材 ID，逗号分隔")
    parser.add_argument("--force", action="store_true", help="已存在时重新下载")
    args = parser.parse_args()

    size = max(256, min(args.size, 2048))
    only = {item.strip() for item in args.only.split(",") if item.strip()}

    plan: list[tuple[str, dict]] = []
    if only:
        for asset_id in only:
            data = fetch_json(
                f"{API}?type=Material&id={asset_id}&include=downloadData", attempts=2
            )
            for asset in data.get("foundAssets") or []:
                plan.append(("Bricks", asset))
    else:
        for category, (count, _tile, _label) in CATEGORIES.items():
            limit = args.per_category or count
            for asset in list_assets(category, limit):
                plan.append((category, asset))

    print(f"计划处理 {len(plan)} 个素材，目标尺寸 {size}px")
    done = skipped = failed = 0

    for category, asset in plan:
        asset_id = asset.get("assetId") or ""
        if not asset_id:
            continue
        target = ROOT / "data" / "texturesets" / asset_id
        if target.exists() and not args.force and (target / "set.json").exists():
            print(f"  跳过 {asset_id}（已存在）")
            skipped += 1
            continue

        tile_m = CATEGORIES.get(category, (0, 2.0, ""))[1]
        label = CATEGORIES.get(category, (0, 2.0, ""))[2]
        zip_url = find_zip_url(asset)
        if not zip_url:
            print(f"  跳过 {asset_id}（无 1K-JPG 包）")
            failed += 1
            continue

        print(f"  下载 {asset_id} ({category}/{label}) ...", flush=True)
        try:
            raw = fetch_bytes(zip_url)
            files = extract_channels(raw)
            if "basecolor" not in files:
                print(f"    失败：缺少 Color 通道")
                failed += 1
                continue
            files = downscale(files, size)
            meta = build_textureset(
                name=asset_id,
                files=files,
                tile_m=tile_m,
                license_text=LICENSE,
                source=VIEW_URL.format(asset=asset_id),
            )
            # 补充用途与原始名称，便于前端展示与风格配置
            set_json = target / "set.json"
            data = json.loads(set_json.read_text(encoding="utf-8"))
            data["display_name"] = f"{asset.get('displayName') or asset_id}（{label}）"
            data["category"] = category
            set_json.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"    完成：{meta['resolution']}px -> {target.name}")
            done += 1
        except Exception as exc:  # noqa: BLE001 - 单个失败不影响整体
            print(f"    失败：{type(exc).__name__}: {exc}")
            failed += 1

    print(f"完成 {done} 个，跳过 {skipped} 个，失败 {failed} 个")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
