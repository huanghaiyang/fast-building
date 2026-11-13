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
    # 植被：常春藤、墙根灌木与草丛
    ivy: bool = False
    # 藤蔓生长状态：覆盖度（每面墙几股）与爬升高度占墙高的比例
    ivy_coverage: float = 0.6
    ivy_height: float = 0.8
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
    # 茅草农舍：坡面中段的石瓦腰带、烟囱数量（双烟囱骑屋脊）
    shingle_band: bool = False
    chimney_count: int = 1
    # 塌毁石屋：残墙断口 + 瓦砾堆 + 烧焦梁架，整栋不生成楼板与屋顶
    collapsed: bool = False
    # 圆拱石屋废墟：半圆拱券、残墙顶、露明梁架与斜靠木板
    round_arch: bool = False
    wall_ruin: bool = False
    collapsed_beams: bool = False
    # 烧毁的木构农舍：灰泥剥落成炭斑，屋顶只剩一坡茅草一坡石瓦
    burnt: bool = False
    # 完好哥特礼拜堂：山墙玫瑰窗、扶壁小尖塔与山尖十字
    rose_window: bool = False
    pinnacles: bool = False
    # 童话茅草农舍：窗台花箱、山墙小窗与门口花盆壁灯
    window_boxes: bool = False
    gable_window: bool = False
    door_dressing: bool = False
    # 中世纪街市建筑（水磨坊 / 书店 / 杂货铺 / 谷仓 / 马厩）
    slate_roof: bool = False
    # 弯坡屋顶的翘檐幅度：0 为平直坡面，1 为檐口两端明显上翘
    roof_curve: float = 0.55
    water_wheel: bool = False
    # 商铺橱窗：下部大窗里排满书架（books）或陶器货架（goods），由样式 shop_kind 决定
    shopfront: bool = False
    # 立面横挂招牌板（书店/杂货铺门楣上方）
    shop_board: bool = False
    # 谷仓双开木板大门（带铁箍与斜撑）
    barn_door: bool = False
    # 马厩：首层正面做成一排圆拱开间，配半截门与草料架
    stable_bays: bool = False
    # 悬挑层下的托木与出挑搁栅端头
    jetty_brackets: bool = False
    # 沿墙陈设：木桶、木箱、麻袋、藤篮、陶罐、干草垛、书堆与柴堆
    street_props: bool = False
    # 靠墙木梯
    ladder: bool = False

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
            ivy=bool(data.get("ivy", False)),
            ivy_coverage=min(1.0, max(0.0, float(data.get("ivy_coverage", 0.6)))),
            ivy_height=min(1.0, max(0.05, float(data.get("ivy_height", 0.8)))),
            buttresses=bool(data.get("buttresses", False)),
            bellcote=bool(data.get("bellcote", False)),
            ruined_roof=bool(data.get("ruined_roof", False)),
            bell_tower=bool(data.get("bell_tower", False)),
            nave_roof=bool(data.get("nave_roof", False)),
            stepped_base=bool(data.get("stepped_base", False)),
            hoarding=bool(data.get("hoarding", False)),
            lookout=bool(data.get("lookout", False)),
            gallery=bool(data.get("gallery", False)),
            shop_sign=bool(data.get("shop_sign", False)),
            ridge_cap=bool(data.get("ridge_cap", False)),
            shingle_band=bool(data.get("shingle_band", False)),
            chimney_count=min(4, max(1, int(data.get("chimney_count", 1)))),
            collapsed=bool(data.get("collapsed", False)),
            burnt=bool(data.get("burnt", False)),
            round_arch=bool(data.get("round_arch", False)),
            wall_ruin=bool(data.get("wall_ruin", False)),
            collapsed_beams=bool(data.get("collapsed_beams", False)),
            rose_window=bool(data.get("rose_window", False)),
            pinnacles=bool(data.get("pinnacles", False)),
            window_boxes=bool(data.get("window_boxes", False)),
            gable_window=bool(data.get("gable_window", False)),
            door_dressing=bool(data.get("door_dressing", False)),
            slate_roof=bool(data.get("slate_roof", False)),
            roof_curve=min(1.0, max(0.0, float(data.get("roof_curve", 0.55)))),
            water_wheel=bool(data.get("water_wheel", False)),
            shopfront=bool(data.get("shopfront", False)),
            shop_board=bool(data.get("shop_board", False)),
            barn_door=bool(data.get("barn_door", False)),
            stable_bays=bool(data.get("stable_bays", False)),
            jetty_brackets=bool(data.get("jetty_brackets", False)),
            street_props=bool(data.get("street_props", False)),
            ladder=bool(data.get("ladder", False)),
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
    # 渲染质量：平滑着色与 Catmull-Clark 细分级别（0 表示不细分）
    smooth: bool = True
    subdiv: int = 1
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
            smooth=bool(data.get("smooth", True)),
            subdiv=int(data.get("subdiv", 1)),
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
        if self.subdiv not in (0, 1, 2):
            raise ValueError("subdiv 仅支持 0 / 1 / 2")
        if not (0 <= self.medieval.dormers <= 4):
            raise ValueError("dormers 需在 0 ~ 4 之间")


# 结构常量（单位：米）
WALL_THICKNESS = 0.24
SLAB_THICKNESS = 0.20
