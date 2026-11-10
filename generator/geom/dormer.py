"""中世纪老虎窗（gable dormer）。

局部坐标：+X 为朝向室外的方向，窗面位于 x=0，窗体向 -X（屋面内侧）延伸。
外观为带小双坡顶的箱体 + 正面玻璃，坡顶脊线平行于主屋脊。
"""

from __future__ import annotations

from ..meshkit import MeshBuilder


def build_gable_dormer(
    body_w: float,
    body_h: float,
    body_d: float,
    tiles: dict[str, float],
) -> MeshBuilder:
    builder = MeshBuilder(tiles)
    y0, y1 = -body_w * 0.5, body_w * 0.5
    zt = body_h
    inner = -body_d
    # 山墙坡度约 50°，与主屋面接近
    cap = max(0.3, body_w * 0.6)

    # 窗体
    builder.add_box((inner, y0, 0.0), (0.0, y1, zt), "facade")

    # 小双坡屋顶：屋脊沿 X 方向（垂直主屋脊），三角形山墙朝向室外
    ridge_front = (0.0, 0.0, zt + cap)
    ridge_back = (inner, 0.0, zt + cap)
    builder.add_face(
        [(0.0, y0, zt), (inner, y0, zt), ridge_back, ridge_front], "roof"
    )
    builder.add_face(
        [(inner, y1, zt), (0.0, y1, zt), ridge_front, ridge_back], "roof"
    )
    builder.add_face([(0.0, y1, zt), (0.0, y0, zt), ridge_front], "facade")
    builder.add_face([(inner, y0, zt), (inner, y1, zt), ridge_back], "facade")
    # 坡面已完全覆盖窗体顶面，无需再生成顶面

    # 窗框：四根细压条（木筋风格下为深色木框，石堡风格下为石框）
    fw = 0.07
    fy0, fy1 = y0 + 0.09, y1 - 0.09
    fz0, fz1 = 0.14, zt - 0.13
    fx0, fx1 = 0.01, 0.055
    builder.add_box((fx0, fy0, fz0), (fx1, fy1, fz0 + fw), "trim")
    builder.add_box((fx0, fy0, fz1 - fw), (fx1, fy1, fz1), "trim")
    builder.add_box((fx0, fy0, fz0), (fx1, fy0 + fw, fz1), "trim")
    builder.add_box((fx0, fy1 - fw, fz0), (fx1, fy1, fz1), "trim")

    # 正面玻璃（略微外凸避免与窗面共面）
    if body_w > 0.5 and zt > 0.6:
        gx = 0.06
        gy0, gy1 = fy0 + fw, fy1 - fw
        gz0, gz1 = fz0 + fw, fz1 - fw
        builder.add_face(
            [(gx, gy0, gz0), (gx, gy1, gz0), (gx, gy1, gz1), (gx, gy0, gz1)],
            "glass",
        )
    return builder
