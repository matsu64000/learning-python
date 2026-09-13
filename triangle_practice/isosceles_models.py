# 「二等辺三角形か否か」を2通りの書き方で実装し、テスト技法を比較するための題材
#
# 【なぜこのファイルを作ったか】
# classify_triangle(triangle_area.py) を決定表・ペアワイズ・MC/DC で分析しようと
# したところ、あの関数の判定点はどれも単一条件(`len({a2,b2,c2})`の3分岐、
# `c2 == a2+b2`の3分岐)で、AND/ORで束ねた複合条件が一つも無いことに気づいた。
# MC/DCは「1つの判定に複数の条件が含まれる」場合に意味を持つ技法なので、
# 単一条件の判定では分岐網羅(C1)に退化してしまい、3手法の違いが現れない。
#
# そこで、判定の中身を明示的な複合条件として書き下した形に作り替える。
# 「二等辺三角形か否か」は、3辺の等しさに関する3つの真偽条件のORで表せる:
#
#     is_isosceles = eq_1 or eq_2 or eq_3
#
# ここで「どの2辺を比べるか」の決め方に2通りある。この2通りは**同じ仕様**
# (どんな入力に対しても同じ真偽を返す)だが、**テスト可能性が違う**。
# それを実測で確認するのがこのファイルの目的。
#
#   モデルA (sorted版):   3辺の2乗を昇順にソートしてから隣接比較 + 両端比較
#                         → classify_triangle が実際に採っている形
#   モデルB (raw版):      ソートせず、辺(1,2)(2,3)(3,1)をそのまま総当たり比較
#
# 【スコープ】
#   - 座標は整数のみ、退化三角形(同一直線上)は分析対象外として除外する
#     (classify_triangle が degenerate を先に切り分けてから分類するのに合わせる)
#   - 面積・角度は扱わない。辺の等しさの軸だけに絞る

import itertools

from triangle_area import Point, _signed_area_x2, _squared_distance


def squared_edges(points):
    """3点から、辺(p1p2), (p2p3), (p3p1)の長さの2乗を「渡された順のまま」返す。"""
    p1, p2, p3 = points
    return (
        _squared_distance(p1, p2),
        _squared_distance(p2, p3),
        _squared_distance(p3, p1),
    )


# --- モデルA: ソートしてから比較(classify_triangle と同じ構造) ---------------

def conditions_sorted(points):
    """モデルAの3条件 (eq_ab, eq_bc, eq_ca) を返す。

    3辺の2乗を昇順に並べて a2 <= b2 <= c2 とし、
      eq_ab: 最小辺 == 中間辺
      eq_bc: 中間辺 == 最大辺
      eq_ca: 最大辺 == 最小辺
    ソートで大小関係を正規化しているぶん、条件同士に順序の制約がかかる。
    """
    a2, b2, c2 = sorted(squared_edges(points))
    return (a2 == b2, b2 == c2, c2 == a2)


def is_isosceles_sorted(points):
    """モデルA: 二等辺(または正三角形)なら True。3条件のOR。"""
    eq_ab, eq_bc, eq_ca = conditions_sorted(points)
    return eq_ab or eq_bc or eq_ca


# --- モデルB: ソートせずそのまま比較 -----------------------------------------

def conditions_raw(points):
    """モデルBの3条件 (eq_12, eq_23, eq_31) を返す。

    渡された順の3辺をそのまま総当たりで比較する。大小関係を正規化しないので、
    どの条件も対等で、順序に由来する制約がかからない。
    """
    d12, d23, d31 = squared_edges(points)
    return (d12 == d23, d23 == d31, d31 == d12)


def is_isosceles_raw(points):
    """モデルB: 二等辺(または正三角形)なら True。3条件のOR。"""
    eq_12, eq_23, eq_31 = conditions_raw(points)
    return eq_12 or eq_23 or eq_31


# --- 条件ベクトルを「実際の3点」に翻訳するための探索 --------------------------
#
# ここが、9/06の寡婦控除の題材と決定的に違う点。
# 寡婦控除では条件(性別・婚姻状況…)がそのまま関数の引数だったので、決定表の
# 1行 = テストデータそのものだった。今回の条件は3点の座標から**導出**される
# ので、「(True, False, False) の行をテストする」と決めても、それを実現する
# 具体的な3点を別途探さなければテストが書けない。そして探して初めて
# 「その行は実現不可能だった」と分かる場合がある。

def iter_non_degenerate_triples(search_range):
    """指定範囲の格子点から、退化していない3点の組を列挙する。"""
    coords = range(-search_range, search_range + 1)
    points = [Point(x, y) for x in coords for y in coords]
    for triple in itertools.combinations(points, 3):
        if _signed_area_x2(*triple) != 0:
            yield list(triple)


def find_points_for(target_conditions, condition_func, search_range=5):
    """指定した条件ベクトルを実現する3点を探す。見つからなければ None。

    target_conditions: (bool, bool, bool)
    condition_func:    conditions_sorted か conditions_raw
    """
    for triple in iter_non_degenerate_triples(search_range):
        if condition_func(triple) == target_conditions:
            return triple
    return None


def feasibility_table(condition_func, search_range=5):
    """8通りの条件ベクトルそれぞれについて、出現回数を数え上げる。"""
    return {combo: count for combo, (count, _) in survey(condition_func, search_range).items()}


def survey(condition_func, search_range=5):
    """格子点を1回だけ走査し、8通りの条件ベクトルの {出現回数, 実例の3点} を集める。

    返り値: {(bool, bool, bool): (count, example_points or None)}
    テストから8通りを個別に探すと同じ走査を何度も繰り返すことになるため、
    1回の走査でまとめて集めておく。
    """
    result = {combo: (0, None) for combo in itertools.product([True, False], repeat=3)}
    for triple in iter_non_degenerate_triples(search_range):
        combo = condition_func(triple)
        count, example = result[combo]
        result[combo] = (count + 1, example if example is not None else triple)
    return result


def main():
    for label, condition_func, names in (
        ("モデルA: sorted版", conditions_sorted, ("eq_ab", "eq_bc", "eq_ca")),
        ("モデルB: raw版", conditions_raw, ("eq_12", "eq_23", "eq_31")),
    ):
        print(f"=== {label} ({', '.join(names)}) ===")
        counts = feasibility_table(condition_func, search_range=5)
        for combo, count in sorted(counts.items(), reverse=True):
            mark = "実現可能" if count else "★実現不可能"
            flags = ", ".join("T" if v else "F" for v in combo)
            print(f"  ({flags})  {count:>7}  {mark}")
        feasible = sum(1 for c in counts.values() if c)
        print(f"  → 8通り中 {feasible}通りだけが実現可能\n")


if __name__ == "__main__":
    main()
