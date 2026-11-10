"""后端 API 的请求 / 响应模型。

字段与 ``generator/schema.py`` 中的 BuildingSpec 保持一一对应，
后端只做边界校验，真正的几何参数校验仍在 Blender 生成器内完成。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OpeningsSpec(BaseModel):
    """门窗洞口的默认尺寸（单位：米）。"""

    window_w: float = Field(1.4, ge=0.4, le=4.0)
    window_h: float = Field(1.6, ge=0.4, le=4.0)
    sill_h: float = Field(0.9, ge=0.0, le=2.0)
    door_w: float = Field(1.05, ge=0.6, le=3.0)
    door_h: float = Field(2.2, ge=1.6, le=4.0)


class MedievalSpec(BaseModel):
    """中世纪构件开关（默认关闭，保持既有生成结果不变）。"""

    timber_frame: bool = False
    arch_openings: bool = False
    jetty: bool = False
    crenellation: bool = False
    dormers: int = Field(0, ge=0, le=4)
    chimney: bool = False


class Footprint(BaseModel):
    """一次建筑生成请求。"""

    width: float = Field(12.0, ge=6.0, le=60.0)
    depth: float = Field(9.0, ge=6.0, le=40.0)
    bays: int = Field(3, ge=1, le=10)
    floors: int = Field(3, ge=1, le=10)
    floor_height: float = Field(3.0, ge=2.4, le=6.0)
    roof: Literal["flat", "gable"] = "gable"
    roof_pitch: float = Field(30.0, ge=5.0, le=60.0)
    style: str = "modern_villa"
    textureset: str = "brick_red"
    lod: int = Field(0, ge=0, le=1)
    seed: int = 42
    balcony: bool = True
    openings: OpeningsSpec = Field(default_factory=OpeningsSpec)
    medieval: MedievalSpec = Field(default_factory=MedievalSpec)


class GenerateResponse(BaseModel):
    job_id: str


class JobResult(BaseModel):
    glb: str | None = None
    meta: str | None = None
    stats: dict = Field(default_factory=dict)


class JobView(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed", "canceled"]
    stage: str = ""
    progress: float = 0.0
    logs: list[str] = Field(default_factory=list)
    error: str | None = None
    result: JobResult = Field(default_factory=JobResult)
    created_at: str = ""
    updated_at: str = ""
