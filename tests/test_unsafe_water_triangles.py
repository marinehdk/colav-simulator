"""DT 视景"不安全水域"红区:补集三角化(backend CDT)的几何契约。

2D 海图保持画布 evenodd 填充不动;DT 视景改由后端一次性下发补集 CDT 三角
(local [north, east]),web 原样转发,Unity 平铺半透明红网格。
"""

from __future__ import annotations

from shapely import wkt
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from gui_server.replay_artifacts import _HAZARD_TRIANGLE_CAP, _unsafe_water_triangles

BBOX = (0.0, 0.0, 4000.0, 3000.0)  # e_min, n_min, e_max, n_max
ORIGIN_E, ORIGIN_N = 100.0, 200.0
# 安全走廊(含一个岛洞):走廊可航,岛洞与走廊外皆不安全。
CORRIDOR_WITH_ISLAND = wkt.loads(
    """POLYGON((1000 500, 3000 500, 3000 2500, 1000 2500, 1000 500),
              (1800 1300, 2200 1300, 2200 1700, 1800 1700, 1800 1300))"""
)


def _union_local(triangles: list[list[list[float]]]) -> Polygon:
    # 顶点为 local [north, east];转绝对 (east, north) 后取并集用于采样。
    return unary_union(
        [Polygon([(n + ORIGIN_N, e + ORIGIN_E) for e, n in tri]) for tri in triangles]
    )


def test_complement_excludes_corridor_and_keeps_island_hole() -> None:
    cover = _union_local(_unsafe_water_triangles(CORRIDOR_WITH_ISLAND, BBOX, ORIGIN_E, ORIGIN_N))
    assert not cover.covers(Point(2000, 1000))    # 走廊内 = 可航,不画红
    assert cover.covers(Point(2000, 1500))        # 岛洞 = 不安全,画红
    assert cover.covers(Point(500, 1500))         # 走廊左带
    assert cover.covers(Point(3500, 500))         # 走廊右下
    assert cover.covers(Point(2000, 2700))        # 走廊上方


def test_area_matches_bbox_minus_safe_water_within_simplification() -> None:
    cover = _union_local(_unsafe_water_triangles(CORRIDOR_WITH_ISLAND, BBOX, ORIGIN_E, ORIGIN_N))
    expected = 4000 * 3000 - (2000 * 2000 - 400 * 400)
    assert abs(cover.area - expected) / expected < 0.02


def test_triangle_shape_and_budget_hold() -> None:
    triangles = _unsafe_water_triangles(CORRIDOR_WITH_ISLAND, BBOX, ORIGIN_E, ORIGIN_N)
    assert 0 < len(triangles) <= _HAZARD_TRIANGLE_CAP
    assert all(len(tri) == 3 and all(len(v) == 2 for v in tri) for tri in triangles)
    # local 坐标落在平移后的 bbox 内(容 1 m 数值裕度):[north, east]。
    assert all(
        BBOX[1] - ORIGIN_N - 1 <= c[0] <= BBOX[3] - ORIGIN_N + 1
        and BBOX[0] - ORIGIN_E - 1 <= c[1] <= BBOX[2] - ORIGIN_E + 1
        for tri in triangles
        for c in tri
    )


def test_empty_or_missing_safe_water_yields_no_hazard() -> None:
    from shapely.geometry import MultiPolygon

    assert _unsafe_water_triangles(None, BBOX, ORIGIN_E, ORIGIN_N) == []
    assert _unsafe_water_triangles(MultiPolygon(), BBOX, ORIGIN_E, ORIGIN_N) == []
    # 安全水域铺满 bbox = 无不安全区。
    full = wkt.loads("POLYGON((0 0, 4000 0, 4000 3000, 0 3000, 0 0))")
    assert _unsafe_water_triangles(full, BBOX, ORIGIN_E, ORIGIN_N) == []
