# 三角形の面積計算プログラム
#
# 対象: 3点(x, y)から三角形の面積を求める。テスト技法(境界値分析・同値分割・
# 決定表・ペアワイズ・MC/DC)の教材としてよく使われる古典的な例題。
#
# 【スコープ・設計判断】
#   座標の型: 整数のみ(float混在は非対応)。整数計算に閉じることで、同一直線上
#     判定(面積0)を浮動小数点誤差なしに厳密に行える
#   同一直線上の3点(退化三角形): 型・個数の誤りとは違い、数学的には正当な入力
#     なのでプログラムの使い方の誤りとして例外にはしない。statusで区別して返す
#     (2点が一致するケースも、外積が0になるため同じ"degenerate"に含まれる特殊形)
#   座標の値の範囲: 特に制限しない。Pythonの整数は多倍長なのでオーバーフローの
#     心配がない(COBOL/FORTRANのPIC句・固定長整数と違う点)

from dataclasses import dataclass


@dataclass
class Point:
    x: int
    y: int


def _validate_points(points):
    """3点の個数・型を検証する(プログラムの使い方の誤りは例外で早期に落とす)"""
    if len(points) != 3:
        raise ValueError(f"3点を渡してください(渡された数: {len(points)})")
    for p in points:
        if not isinstance(p, Point):
            raise TypeError(f"Point型を渡してください: {p!r}")
        for axis, value in (("x", p.x), ("y", p.y)):
            # bool は int のサブクラスなので isinstance(value, int) だけでは
            # True/False をすり抜けてしまう。明示的に除外する
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{axis}は整数のみ有効です: {value!r}")


def _signed_area_x2(p1, p2, p3):
    """符号付き面積の2倍をシューレース公式(外積)で求める。

    傾き(slope)の一致で同一直線上を判定する方法は、辺が垂直なときゼロ除算に
    なる弱点がある。外積なら除算が不要で、3点が同一直線上のとき厳密に0になる。
    """
    return (p2.x - p1.x) * (p3.y - p1.y) - (p3.x - p1.x) * (p2.y - p1.y)


def calc_triangle_area(points):
    """3点(list[Point]、ちょうど3点)から三角形の面積を求める。

    返り値:
      {"status": "valid", "area": <float>}   - 正常な三角形
      {"status": "degenerate", "area": 0.0}  - 3点が同一直線上(2点が一致する
                                                場合を含む)、三角形にならない
    型・個数の誤りは例外(ValueError/TypeError)。同一直線上は数学的には正当な
    入力なので例外にせず、statusで区別する。
    """
    _validate_points(points)
    p1, p2, p3 = points
    area_x2 = _signed_area_x2(p1, p2, p3)
    if area_x2 == 0:
        return {"status": "degenerate", "area": 0.0}
    return {"status": "valid", "area": abs(area_x2) / 2}


def _squared_distance(p1, p2):
    """2点間の距離の2乗。平方根を取らないことで整数計算に閉じ、誤差を避ける。"""
    return (p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2


def classify_triangle(points):
    """3点から三角形の種類を、辺の等しさ(edge_type)と角度(angle_type)の2軸で判定する。

    返り値:
      {"status": "degenerate"}  - 同一直線上(calc_triangle_areaのdegenerateと同じ)
      {"status": "valid", "edge_type": ..., "angle_type": ...}
        edge_type: "equilateral"(正三角形) / "isosceles"(二等辺) / "scalene"(不等辺)
        angle_type: "right"(直角) / "acute"(鋭角) / "obtuse"(鈍角)

    辺の長さそのもの(平方根)ではなく、辺の長さの2乗のまま比較する:
      - 等しさの判定: 平方は単調増加関数なので、2乗のままでも大小関係・等しさの
        判定結果は変わらない
      - 角度の判定: 余弦定理より、最大辺の2乗と残り2辺の2乗の和を比較すれば、
        平方根なしで直角/鋭角/鈍角を判定できる(最大辺に対応する角が最大の角なので、
        最大辺だけ確認すれば十分)
    座標が整数のため、辺の長さの2乗も必ず整数になり、この比較に浮動小数点誤差は
    一切入らない。

    【到達不能な分岐について】座標を整数に限定したことで、edge_type="equilateral"
    は理論上決して出現しない。格子点(整数座標)上の3点で正三角形を作ると、面積が
    シューレース公式より必ず有理数になる一方、正三角形の面積公式(√3/4)×辺長²は
    辺長²が正の整数である限り無理数になり、両立しないため(証明の概略)。
    分類ロジック自体は一般的な形(3辺の2乗を比較するだけ)で書くのが自然なため
    equilateralの分岐は残すが、この入力ドメインでは構造的にテストで到達できない。
    """
    area_result = calc_triangle_area(points)
    if area_result["status"] == "degenerate":
        return {"status": "degenerate"}

    p1, p2, p3 = points
    a2, b2, c2 = sorted([
        _squared_distance(p1, p2),
        _squared_distance(p2, p3),
        _squared_distance(p3, p1),
    ])  # 昇順。c2が最大辺の2乗

    edge_type = {1: "equilateral", 2: "isosceles", 3: "scalene"}[len({a2, b2, c2})]

    if c2 == a2 + b2:
        angle_type = "right"
    elif c2 < a2 + b2:
        angle_type = "acute"
    else:
        angle_type = "obtuse"

    return {"status": "valid", "edge_type": edge_type, "angle_type": angle_type}


def main():
    cases = [
        ("直角三角形(3-4-5系、脚4と3)", [Point(0, 0), Point(4, 0), Point(0, 3)]),
        ("面積が整数にならない例", [Point(0, 0), Point(1, 0), Point(0, 1)]),
        ("同一直線上(退化)", [Point(0, 0), Point(1, 1), Point(2, 2)]),
        ("2点が一致(退化の特殊形)", [Point(0, 0), Point(0, 0), Point(1, 1)]),
    ]
    for title, points in cases:
        result = calc_triangle_area(points)
        print(f"{title}: {result}")

    print()
    type_cases = [
        ("直角二等辺三角形", [Point(0, 0), Point(2, 0), Point(0, 2)]),
        ("鋭角不等辺三角形", [Point(0, 0), Point(5, 0), Point(1, 4)]),
        ("鈍角二等辺三角形", [Point(0, 0), Point(4, 0), Point(2, 1)]),
    ]
    for title, points in type_cases:
        print(f"{title}: {classify_triangle(points)}")


if __name__ == "__main__":
    main()
