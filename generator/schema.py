"""生成器的数据模型。

该模块不依赖 bpy，方便在普通 Python 环境下做参数校验与单元测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Openings:
    window_w: float = 1.4
    window_h: float = 1.6
    sill_h: float = 0.9
    door_w: float = 1.05
    door_h: float = 2.2

    @classmethod
    def from_dict(cls, data: dict | None) -> "Openings":
        data = data or {}
        return cls(
            window_w=float(data.get("window_w", 1.4)),
            window_h=float(data.get("window_h", 1.6)),
            sill_h=float(data.get("sill_h", 0.9)),
            door_w=float(data.get("door_w", 1.05)),
            door_h=float(data.get("door_h", 2.2)),
        )


@dataclass
class Medieval:
    """中世纪构件开关；全部默认关闭，不影响既有风格。"""

    timber_frame: bool = False
    arch_openings: bool = False
    jetty: bool = False
    crenellation: bool = False
    dormers: int = 0
    chimney: bool = False
    # 乡土构件（茅草顶原木农舍）
    log_walls: bool = False
    thatch_roof: bool = False
    stone_plinth: bool = False
    porch: bool = False

    @classmethod
    def from_dict(cls, data: dict | None) -> "Medieval":
        data = data or {}
        return cls(
            timber_frame=bool(data.get("timber_frame", False)),
            arch_openings=bool(data.get("arch_openings", False)),
            jetty=bool(data.get("jetty", False)),
            crenellation=bool(data.get("crenellation", False)),
            dormers=int(data.get("dormers", 0)),
            chimney=bool(data.get("chimney", False)),
            log_walls=bool(data.get("log_walls", False)),
            thatch_roof=bool(data.get("thatch_roof", False)),
            stone_plinth=bool(data.get("stone_plinth", False)),
            porch=bool(data.get("porch", False)),
        )


@dataclass
class Spec:
    """一次建筑生成的完整参数（与后端 Footprint 对齐）。"""

    width: float = 12.0
    depth: float = 9.0
    bays: int = 3
    floors: int = 3
    floor_height: float = 3.0
    roof: str = "gable"
    roof_pitch: float = 30.0
    style: str = "modern_villa"
    textureset: str = "brick_red"
    lod: int = 0
    seed: int = 42
    balcony: bool = True
    openings: Openings = field(default_factory=Openings)
    medieval: Medieval = field(default_factory=Medieval)

    @classmethod
    def from_dict(cls, data: dict) -> "Spec":
        spec = cls(
            width=float(data.get("width", 12.0)),
            depth=float(data.get("depth", 9.0)),
            bays=int(data.get("bays", 3)),
            floors=int(data.get("floors", 3)),
            floor_height=float(data.get("floor_height", 3.0)),
            roof=str(data.get("roof", "gable")),
            roof_pitch=float(data.get("roof_pitch", 30.0)),
            style=str(data.get("style", "modern_villa")),
            textureset=str(data.get("textureset", "brick_red")),
            lod=int(data.get("lod", 0)),
            seed=int(data.get("seed", 42)),
            balcony=bool(data.get("balcony", True)),
            openings=Openings.from_dict(data.get("openings")),
            medieval=Medieval.from_dict(data.get("medieval")),
        )
        spec.validate()
        return spec

    def validate(self) -> None:
        if not (4.0 <= self.width <= 80.0):
            raise ValueError("width 需在 4 ~ 80 米之间")
        if not (4.0 <= self.depth <= 50.0):
            raise ValueError("depth 需在 4 ~ 50 米之间")
        if not (1 <= self.bays <= 12):
            raise ValueError("bays 需在 1 ~ 12 之间")
        if not (1 <= self.floors <= 12):
            raise ValueError("floors 需在 1 ~ 12 之间")
        if not (2.2 <= self.floor_height <= 6.0):
            raise ValueError("floor_height 需在 2.2 ~ 6 米之间")
        if self.roof not in ("flat", "gable"):
            raise ValueError("roof 仅支持 flat / gable")
        if not (0.0 < self.roof_pitch < 70.0):
            raise ValueError("roof_pitch 需在 0 ~ 70 度之间")
        if self.lod not in (0, 1):
            raise ValueError("lod 仅支持 0 / 1")
        if not (0 <= self.medieval.dormers <= 4):
            raise ValueError("dormers 需在 0 ~ 4 之间")


# 结构常量（单位：米）
WALL_THICKNESS = 0.24
SLAB_THICKNESS = 0.20
