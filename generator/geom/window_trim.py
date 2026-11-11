"""洞口木装修：窗框、十字窗棂、窗台与门槛石。

墙体现有的做法只在洞口里贴一层玻璃/门板，近景看是「墙上的洞」。参考图里的
小窗都带深色木框和十字窗棂，山墙下还有一道薄窗台，这里把这些贴面构件补上。

坐标与墙体完全一致（X 沿墙长、Y 0~thickness 为墙厚方向、Z 自墙脚起算），
所以可以直接复用同一个对象变换。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder
from .arch import arch_rise
from .wall_panel import Opening

FRAME = 0.075
T_PROUD = 0.045
T_EMBED = 0.02


def _box(
    builder: MeshBuilder,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z0: float,
    z1: float,
    slot: str,
) -> None:
    if x1 - x0 < 0.02 or z1 - z0 < 0.02:
        return
    builder.add_box((x0, y0, z0), (x1, y1, z1), slot)


def build_opening_trims(
    openings: list[Opening],
    thickness: float,
    tiles: dict[str, float],
    mullions: bool = True,
    sill: bool = True,
    slot: str = "trim",
    arched: bool = False,
) -> MeshBuilder:
    builder = MeshBuilder(tiles)

    for op in openings:
        # 尖拱洞口不做矩形上框与横窗棂，否则会压在拱头上；立框只做到起拱点
        head = op.z1
        if arched:
            head = op.z1 - arch_rise(op.x1 - op.x0, op.z1 - op.z0)
            if head - op.z0 < 0.2:
                head = op.z1

        # 边框，略压在墙面上
        _box(builder, op.x0 - FRAME, op.x1 + FRAME, -T_PROUD, T_EMBED,
             op.z0 - FRAME, op.z0, slot)
        if not arched:
            _box(builder, op.x0 - FRAME, op.x1 + FRAME, -T_PROUD, T_EMBED,
                 op.z1, op.z1 + FRAME, slot)
        _box(builder, op.x0 - FRAME, op.x0, -T_PROUD, T_EMBED, op.z0, head, slot)
        _box(builder, op.x1, op.x1 + FRAME, -T_PROUD, T_EMBED, op.z0, head, slot)

        if op.kind == "door":
            # 门槛石
            _box(builder, op.x0 - FRAME - 0.05, op.x1 + FRAME + 0.05,
                 -0.42, 0.02, 0.0, 0.1, "stone")
            continue

        if mullions:
            cx = (op.x0 + op.x1) * 0.5
            cz = (op.z0 + op.z1) * 0.5
            # 窗棂嵌进洞内，接到玻璃面；尖拱窗只保留竖向中梃
            _box(builder, cx - 0.028, cx + 0.028, -T_PROUD, thickness * 0.5,
                 op.z0, head, slot)
            if not arched:
                _box(builder, op.x0, op.x1, -T_PROUD, thickness * 0.5,
                     cz - 0.026, cz + 0.026, slot)

        if sill:
            _box(builder, op.x0 - FRAME - 0.06, op.x1 + FRAME + 0.06,
                 -0.1, 0.02, op.z0 - 0.07, op.z0, slot)

    return builder
