"""资源类接口：健康检查、模块库、风格预设、PBR 贴图集。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import BLENDER_EXE, MODULES_DIR, STYLES_DIR
from ..services import textures

router = APIRouter(prefix="/api", tags=["resources"])

_blender_version: str | None = None


def _read_json_dir(directory: Path) -> list[dict]:
    items: list[dict] = []
    if not directory.exists():
        return items
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data.setdefault("id", path.stem)
        items.append(data)
    return items


@router.get("/health")
def health() -> dict:
    """返回服务与 Blender 的可用状态。"""
    global _blender_version
    exists = BLENDER_EXE.exists()
    if exists and _blender_version is None:
        try:
            completed = subprocess.run(
                [str(BLENDER_EXE), "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                creationflags=0x08000000,
            )
            first_line = (completed.stdout or "").splitlines()
            _blender_version = first_line[0].strip() if first_line else "unknown"
        except (OSError, subprocess.SubprocessError):
            _blender_version = "unknown"
    return {
        "ok": exists,
        "blender": {"path": str(BLENDER_EXE), "version": _blender_version},
    }


@router.get("/modules")
def list_modules() -> list[dict]:
    return _read_json_dir(MODULES_DIR)


@router.get("/styles")
def list_styles() -> list[dict]:
    return _read_json_dir(STYLES_DIR)


@router.get("/texturesets")
def list_texturesets() -> list[dict]:
    return textures.list_sets()


@router.post("/texturesets")
async def upload_textureset(
    name: str = Form(...),
    tile_m: float = Form(2.0),
    license_text: str = Form(""),
    source: str = Form(""),
    basecolor: UploadFile | None = File(None),
    normal: UploadFile | None = File(None),
    roughness: UploadFile | None = File(None),
    metallic: UploadFile | None = File(None),
    ao: UploadFile | None = File(None),
    height: UploadFile | None = File(None),
) -> dict:
    """上传一组 PBR 通道图，后端完成尺寸统一与 ORM 打包。"""
    if not (0.05 <= tile_m <= 50):
        raise HTTPException(status_code=400, detail="tile_m 需在 0.05 ~ 50 之间")

    uploads = {
        "basecolor": basecolor,
        "normal": normal,
        "roughness": roughness,
        "metallic": metallic,
        "ao": ao,
        "height": height,
    }
    files: dict[str, bytes] = {}
    for channel, upload in uploads.items():
        if upload is None:
            continue
        raw = await upload.read()
        if not raw:
            continue
        if len(raw) > 40 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{channel} 贴图超过 40MB 限制")
        files[channel] = raw

    if not files:
        raise HTTPException(status_code=400, detail="至少需要上传一个通道贴图")

    try:
        meta = textures.build_textureset(
            name=name,
            files=files,
            tile_m=tile_m,
            license_text=license_text,
            source=source,
        )
    except Exception as exc:  # 图片解码失败等
        raise HTTPException(status_code=400, detail=f"贴图处理失败: {exc}") from exc

    meta["id"] = meta["name"]
    meta["preview"] = f"/tex/{meta['name']}/basecolor.png"
    return meta
