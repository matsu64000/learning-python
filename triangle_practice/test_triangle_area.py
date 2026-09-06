"""triangle_area.py のテスト。

まず正常系・境界的な同値クラス(退化三角形、2点一致、型/個数エラー)で
動作確認する。決定表・ペアワイズ・MC/DCによる体系的な比較は、この関数に
複合条件が出てきた段階で別途行う想定。
"""

import itertools

import pytest

from triangle_area import Point, calc_triangle_area, classify_triangle


def test_right_triangle_area():
    points = [Point(0, 0), Point(4, 0), Point(0, 3)]
    assert calc_triangle_area(points) == {"status": "valid", "area": 6.0}


def test_area_with_half_fraction():
    # 面積が整数にならない例(0.5は2進浮動小数点で誤差なく表現できる)
    points = [Point(0, 0), Point(1, 0), Point(0, 1)]
    assert calc_triangle_area(points) == {"status": "valid", "area": 0.5}


def test_point_order_does_not_change_area():
    # 3点の順序(時計回り/反時計回り)によらず面積の絶対値は同じ
    clockwise = [Point(0, 0), Point(0, 3), Point(4, 0)]
    counterclockwise = [Point(0, 0), Point(4, 0), Point(0, 3)]
    assert calc_triangle_area(clockwise) == calc_triangle_area(counterclockwise)


def test_collinear_points_are_degenerate():
    points = [Point(0, 0), Point(1, 1), Point(2, 2)]
    assert calc_triangle_area(points) == {"status": "degenerate", "area": 0.0}


def test_two_identical_points_are_degenerate():
    # 2点が一致する場合も外積が0になり、同一直線上と同じ扱いになる
    points = [Point(0, 0), Point(0, 0), Point(1, 1)]
    assert calc_triangle_area(points) == {"status": "degenerate", "area": 0.0}


def test_all_three_points_identical_are_degenerate():
    points = [Point(5, 5), Point(5, 5), Point(5, 5)]
    assert calc_triangle_area(points) == {"status": "degenerate", "area": 0.0}


@pytest.mark.parametrize("points", [
    [Point(0, 0), Point(1, 0)],                          # 2点しかない
    [Point(0, 0), Point(1, 0), Point(0, 1), Point(1, 1)],  # 4点ある
])
def test_wrong_number_of_points_raises_value_error(points):
    with pytest.raises(ValueError):
        calc_triangle_area(points)


@pytest.mark.parametrize("points", [
    [(0, 0), (1, 0), (0, 1)],                       # Point型でなくtupleのまま
    [Point(0.5, 0), Point(1, 0), Point(0, 1)],      # xがfloat
    [Point(0, 0), Point(1, True), Point(0, 1)],     # yがbool(intのサブクラス)
])
def test_invalid_point_type_raises_type_error(points):
    with pytest.raises(TypeError):
        calc_triangle_area(points)


# --- classify_triangle: 辺の等しさ(edge_type)x角度(angle_type)の2軸 ----------
# 整数座標では正三角形(equilateral)が理論上出現しない(格子点上の正三角形は
# 面積が有理数と無理数の両方でなければならず矛盾するため)。この性質を、
# 証明だけでなく小範囲の総当たりで実際に確認してから、到達可能な2x3=6通りの
# 組み合わせをそれぞれテストする。

def test_equilateral_never_occurs_with_integer_coordinates():
    # -5〜5の範囲で3点の全組み合わせを試しても、edge_typeがequilateralに
    # なることは一度もない(数学的な証明の、小規模での実地確認)
    coords = range(-5, 6)
    points = [Point(x, y) for x in coords for y in coords]
    found_equilateral = any(
        classify_triangle([p1, p2, p3]).get("edge_type") == "equilateral"
        for p1, p2, p3 in itertools.combinations(points, 3)
    )
    assert not found_equilateral


def test_classify_triangle_degenerate():
    points = [Point(0, 0), Point(1, 1), Point(2, 2)]
    assert classify_triangle(points) == {"status": "degenerate"}


@pytest.mark.parametrize("points, expected", [
    # 直角二等辺三角形
    ([Point(0, 0), Point(2, 0), Point(0, 2)], {"edge_type": "isosceles", "angle_type": "right"}),
    # 直角不等辺三角形(3-4-5)
    ([Point(0, 0), Point(4, 0), Point(0, 3)], {"edge_type": "scalene", "angle_type": "right"}),
    # 鋭角二等辺三角形
    ([Point(0, 0), Point(4, 0), Point(2, 3)], {"edge_type": "isosceles", "angle_type": "acute"}),
    # 鋭角不等辺三角形
    ([Point(0, 0), Point(5, 0), Point(1, 4)], {"edge_type": "scalene", "angle_type": "acute"}),
    # 鈍角二等辺三角形
    ([Point(0, 0), Point(4, 0), Point(2, 1)], {"edge_type": "isosceles", "angle_type": "obtuse"}),
    # 鈍角不等辺三角形
    ([Point(0, 0), Point(5, 0), Point(1, 1)], {"edge_type": "scalene", "angle_type": "obtuse"}),
])
def test_classify_triangle_edge_x_angle_combinations(points, expected):
    result = classify_triangle(points)
    assert result == {"status": "valid", **expected}
