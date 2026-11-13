"""后端 API 的请求 / 响应模型。

字段与 ``generator/schema.py`` 中的 BuildingSpec 保持一一对应，
后端只做边界校验，真正的几何参数校验仍在 Blender 生成器内完成。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OpeningsSpec(BaseModel):
    """门窗洞口的默认尺寸（单位：米）。"""

    window_w: float = Field(1.4, ge=0.12, le=4.0)
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
    # 乡土构件（茅草顶原木农舍）
    log_walls: bool = False
    thatch_roof: bool = False
    stone_plinth: bool = False
    porch: bool = False
    # 植被：常春藤、墙根灌木与草丛
    ivy: bool = False
    # 藤蔓生长状态：覆盖度（每面墙几股）与爬升高度占墙高的比例
    ivy_coverage: float = Field(0.6, ge=0.0, le=1.0)
    ivy_height: float = Field(0.8, ge=0.05, le=1.0)
    # 哥特石构与废墟
    buttresses: bool = False
    bellcote: bool = False
    ruined_roof: bool = False
    # 废墟教堂：西端方形钟塔、屋脊沿长轴的残破坡顶与崩缺山墙
    bell_tower: bool = False
    nave_roof: bool = False
    # 石砌瞭望塔：阶梯石基、塔顶悬挑木挑廊、挑廊上的木构瞭望棚
    stepped_base: bool = False
    hoarding: bool = False
    lookout: bool = False
    # 破败半木构客栈：环绕木廊、悬挑店招、悬山脊梁与封檐板
    gallery: bool = False
    shop_sign: bool = False
    ridge_cap: bool = False
    # 茅草农舍：坡面中段的石瓦腰带、烟囱数量（>1 时骑屋脊分列两端）
    shingle_band: bool = False
    chimney_count: int = Field(1, ge=1, le=4)
    # 塌毁石屋：残墙断口 + 瓦砾堆 + 焦木梁架
    collapsed: bool = False
    # 烧毁的木构农舍：炭化墙斑与半覆屋顶
    burnt: bool = False
    # 完好哥特礼拜堂：山墙玫瑰窗、扶壁小尖塔与山尖十字
    rose_window: bool = False
    pinnacles: bool = False
    # 童话茅草农舍：窗台花箱、山墙小窗与门口花盆壁灯
    window_boxes: bool = False
    gable_window: bool = False
    door_dressing: bool = False
    # 圆拱石屋废墟：半圆拱券、残墙顶、露明梁架与斜靠木板
    round_arch: bool = False
    wall_ruin: bool = False
    collapsed_beams: bool = False
    # 中世纪街市建筑（水磨坊 / 书店 / 杂货铺 / 谷仓 / 马厩）
    slate_roof: bool = False
    roof_curve: float = Field(0.55, ge=0.0, le=1.0)
    water_wheel: bool = False
    shopfront: bool = False
    shop_board: bool = False
    barn_door: bool = False
    stable_bays: bool = False
    jetty_brackets: bool = False
    street_props: bool = False
    ladder: bool = False


class Footprint(BaseModel):
    """一次建筑生成请求。"""

    width: float = Field(12.0, ge=4.0, le=60.0)
    depth: float = Field(9.0, ge=4.0, le=40.0)
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
    # 几何质量：平滑着色与 Catmull-Clark 细分级别（0 表示不细分）
    smooth: bool = True
    subdiv: int = Field(1, ge=0, le=2)
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
