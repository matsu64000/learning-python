"""isosceles_models.py に決定表・ペアワイズ・MC/DC の3手法を当てて比較する。

9/06に寡婦控除・ひとり親控除で同じ3手法を比較したときは、条件がそのまま関数の
引数だった。今回は条件が3点の座標から**導出**されるため、「条件ベクトルを決める」
ことと「テストデータを作る」ことが分離する。そこで生じる差を確認するのが狙い。

構成:
  第0部  前提の確認(2モデルは同じ仕様であること、実現可能な行はどれか)
  第1部  決定表
  第2部  ペアワイズ
  第3部  MC/DC
  第4部  3手法の比較の要約(このテスト群から言えることをassertの形で固定する)
"""

import itertools

import pytest

from isosceles_models import (
    conditions_raw,
    conditions_sorted,
    is_isosceles_raw,
    is_isosceles_sorted,
    iter_non_degenerate_triples,
    survey,
)

SEARCH_RANGE = 5
ALL_COMBOS = list(itertools.product([True, False], repeat=3))


@pytest.fixture(scope="module")
def surveys():
    """格子点の走査は重いので、モデルごとに1回だけ行って使い回す。"""
    return {
        "sorted": survey(conditions_sorted, SEARCH_RANGE),
        "raw": survey(conditions_raw, SEARCH_RANGE),
    }


def feasible_combos(surveys, model):
    return {combo for combo, (count, _) in surveys[model].items() if count}


def example_for(surveys, model, combo):
    count, points = surveys[model][combo]
    assert count, f"{combo} を実現する3点は存在しないため、テストデータを作れない"
    return points


# =============================================================================
# 第0部: 前提の確認
# =============================================================================

def test_two_models_are_equivalent_specifications():
    """2つのモデルは書き方が違うだけで、どんな入力にも同じ真偽を返す。

    これが成り立たないと以降の比較が「実装の違い」ではなく「仕様の違い」に
    なってしまうので、最初に総当たりで固定しておく。
    """
    for triple in iter_non_degenerate_triples(SEARCH_RANGE):
        assert is_isosceles_sorted(triple) == is_isosceles_raw(triple)


def test_sorted_model_has_only_three_feasible_rows(surveys):
    """モデルA: ソートで大小関係を正規化したせいで、8通り中3通りしか実現しない。

    eq_ca(最大辺 == 最小辺)がTrueになるには a2 <= b2 <= c2 かつ a2 == c2、
    つまり3辺すべてが等しい正三角形しかない。そして整数座標では正三角形が
    出現しない(triangle_area.py 参照)ため、eq_ca は**恒久的にFalse**になる。
    """
    assert feasible_combos(surveys, "sorted") == {
        (True, False, False),   # 二等辺: 最小 == 中間
        (False, True, False),   # 二等辺: 中間 == 最大
        (False, False, False),  # 不等辺
    }
    # eq_ca がTrueの行は、4通りすべてが実現不可能
    for combo in ALL_COMBOS:
        if combo[2]:
            assert surveys["sorted"][combo][0] == 0


def test_raw_model_has_four_feasible_rows(surveys):
    """モデルB: ソートしないと3条件が対等になり、4通りが実現する。

    実現しないのは「2つ以上がTrue」の4通りだけ。理由は2つあり、種類が違う:
      - 「ちょうど2つがTrue」の3通り: 等しさの推移律による**論理的な**不可能
        (d12==d23 かつ d23==d31 なら d31==d12 も必ず成立する)
      - 「3つともTrue」の1通り: 正三角形。整数座標という**入力ドメイン由来**の不可能
    """
    assert feasible_combos(surveys, "raw") == {
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (False, False, False),
    }


def test_exactly_two_true_is_impossible_by_transitivity(surveys):
    """「ちょうど2つがTrue」が不可能なのは推移律のため。座標の範囲に依らない。"""
    for combo in ALL_COMBOS:
        if sum(combo) == 2:
            assert surveys["raw"][combo][0] == 0
            assert surveys["sorted"][combo][0] == 0


# =============================================================================
# 第1部: 決定表
#
# 8通りを全部書き出し、実現可能な行はテストし、不可能な行は理由つきで
# 「不可能であること」自体をテストする。網羅できなかったのではなく、
# 網羅する対象が存在しないのだと、表の上で明示できるのが決定表の強み。
# =============================================================================

SORTED_DECISION_TABLE = [
    # (条件ベクトル, 期待する判定, 実現可能か, 実現不可能な場合の理由)
    ((True,  True,  True),  True,  False, "正三角形。整数座標では出現しない"),
    ((True,  True,  False), True,  False, "推移律違反(a2==b2 かつ b2==c2 なら c2==a2)"),
    ((True,  False, True),  True,  False, "推移律違反"),
    ((True,  False, False), True,  True,  ""),
    ((False, True,  True),  True,  False, "推移律違反"),
    ((False, True,  False), True,  True,  ""),
    ((False, False, True),  True,  False, "ソートにより a2<=c2。a2==c2 なら3辺が等しくなり正三角形"),
    ((False, False, False), False, True,  ""),
]

RAW_DECISION_TABLE = [
    ((True,  True,  True),  True,  False, "正三角形。整数座標では出現しない"),
    ((True,  True,  False), True,  False, "推移律違反"),
    ((True,  False, True),  True,  False, "推移律違反"),
    ((True,  False, False), True,  True,  ""),
    ((False, True,  True),  True,  False, "推移律違反"),
    ((False, True,  False), True,  True,  ""),
    ((False, False, True),  True,  True,  ""),
    ((False, False, False), False, True,  ""),
]


@pytest.mark.parametrize("conditions, expected, realizable, reason", SORTED_DECISION_TABLE)
def test_decision_table_sorted(surveys, conditions, expected, realizable, reason):
    count, points = surveys["sorted"][conditions]
    if not realizable:
        assert count == 0, f"実現不可能なはずの行が実現した: {conditions}"
        return
    assert conditions_sorted(points) == conditions
    assert is_isosceles_sorted(points) is expected


@pytest.mark.parametrize("conditions, expected, realizable, reason", RAW_DECISION_TABLE)
def test_decision_table_raw(surveys, conditions, expected, realizable, reason):
    count, points = surveys["raw"][conditions]
    if not realizable:
        assert count == 0, f"実現不可能なはずの行が実現した: {conditions}"
        return
    assert conditions_raw(points) == conditions
    assert is_isosceles_raw(points) is expected


# =============================================================================
# 第2部: ペアワイズ
#
# pairwise_gen_isosceles.py が生成した行をそのまま使う。生成器は条件の意味を
# 一切理解せず「どの2要素の値の組み合わせも1回は出す」だけで組む。
# =============================================================================

PAIRWISE_SORTED = [
    (True,  False, False),
    (False, True,  False),
    (False, False, False),
]

PAIRWISE_RAW = [
    (True,  False, False),
    (False, True,  False),
    (False, False, True),
]


@pytest.mark.parametrize("conditions", PAIRWISE_SORTED)
def test_pairwise_sorted(surveys, conditions):
    points = example_for(surveys, "sorted", conditions)
    assert is_isosceles_sorted(points) is any(conditions)


@pytest.mark.parametrize("conditions", PAIRWISE_RAW)
def test_pairwise_raw(surveys, conditions):
    points = example_for(surveys, "raw", conditions)
    assert is_isosceles_raw(points) is any(conditions)


def test_pairwise_raw_never_exercises_the_false_outcome():
    """モデルBのペアワイズ3行は、判定結果がすべてTrue。Falseを一度も試していない。

    貪欲法は「未被覆のペアが増えるか」だけを見るので、不等辺((F,F,F))の行は
    「新しいペアを増やさない」という理由で落ちる。ペアワイズは自分の基準を
    100%満たしているのに、判定の出口の片方をまったく通っていない。
    網羅基準を満たすことと、意味のあるテストであることは別だという実例。
    """
    assert all(any(conditions) for conditions in PAIRWISE_RAW)


def test_pairwise_sorted_happens_to_include_the_false_outcome():
    """一方モデルAのペアワイズには(F,F,F)が入る。狙ったわけではなく偶然。

    モデルAでは実現可能な行が3つしかなく、eq_ab=(F)とeq_bc=(F)の同時出現という
    ペアを埋められるのが(F,F,F)だけだったため、結果的に残った。
    実現可能な行が「多い」モデルBの方が悪いテストになるという逆転が起きている。
    """
    assert not any(PAIRWISE_SORTED[-1])


# =============================================================================
# 第3部: MC/DC
#
# MC/DCは「各条件が、他の条件を固定したまま単独で判定結果を変えられること」を
# 示す技法。OR結合なので、全条件Falseの行を基準に、1つずつTrueに倒した行と
# ペアにすればよい。理論上の最小行数は 条件数+1 = 4行。
# =============================================================================

ALL_FALSE = (False, False, False)


def independence_pair(index):
    """条件indexだけを反転させたペア(基準行, 反転行)を返す。"""
    flipped = list(ALL_FALSE)
    flipped[index] = True
    return ALL_FALSE, tuple(flipped)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_mcdc_raw_each_condition_is_independently_shown(surveys, index):
    """モデルB: 3条件すべてについて、単独で結果を変えるペアが実際に作れる。"""
    base, flipped = independence_pair(index)
    base_points = example_for(surveys, "raw", base)
    flipped_points = example_for(surveys, "raw", flipped)

    assert is_isosceles_raw(base_points) is False
    assert is_isosceles_raw(flipped_points) is True


def test_mcdc_raw_is_achieved_at_the_theoretical_minimum(surveys):
    """モデルB: 必要な行は基準1 + 反転3 = 4行。条件数+1という理論下限ちょうど。

    9/06の寡婦控除では is_widowed / is_divorced が両立不可能だったため下限の
    4行では足りず5行必要だった。今回は下限で足りる。同じMC/DCでも、条件同士に
    制約があるかどうかで結果が変わる。
    """
    used_rows = {ALL_FALSE} | {independence_pair(i)[1] for i in range(3)}
    assert len(used_rows) == 4
    assert used_rows <= feasible_combos(surveys, "raw")


def test_mcdc_sorted_is_unachievable_for_the_third_condition(surveys):
    """モデルA: eq_ca は単独で結果を変えるペアが作れず、MC/DC 100%が達成不能。

    eq_ca がTrueになる行は8通り中4通りあるが、そのすべてが実現不可能。
    つまり eq_ca を反転させたテストデータが1つも存在しない。これは
    「テストを書き忘れた」のでも「頑張れば書ける」のでもなく、入力ドメインの
    数学的性質から**原理的に**達成できないという種類の未達成。
    """
    _, flipped = independence_pair(2)  # (False, False, True)
    assert surveys["sorted"][flipped][0] == 0

    # eq_ab, eq_bc の2条件については問題なくペアが作れる(達成不能なのは eq_ca だけ)
    for index in (0, 1):
        base, flipped = independence_pair(index)
        assert is_isosceles_sorted(example_for(surveys, "sorted", base)) is False
        assert is_isosceles_sorted(example_for(surveys, "sorted", flipped)) is True


def test_sorted_model_third_condition_is_redundant_code():
    """MC/DC達成不能の正体: モデルAの eq_ca は、そもそも書く必要のない条件。

    ソートで a2 <= b2 <= c2 を保証しているので、eq_ca(c2 == a2)がTrueなら
    必ず eq_ab も eq_bc もTrueになる。つまり eq_ca は OR の結果に一切影響しない。
    MC/DCが「この条件は単独で結果を変えられない」と言っているのは、
    テスト不足の指摘ではなく**冗長なコードがある**という設計上の指摘だった。
    """
    for triple in iter_non_degenerate_triples(SEARCH_RANGE):
        eq_ab, eq_bc, eq_ca = conditions_sorted(triple)
        assert (eq_ab or eq_bc) == (eq_ab or eq_bc or eq_ca)
        # eq_ca が単独でTrueになることは決してない
        assert not (eq_ca and not (eq_ab and eq_bc))


# =============================================================================
# 第4部: 3手法の比較の要約
# =============================================================================

def test_summary_row_counts_and_coverage(surveys):
    """3手法が要求する行数と、それぞれが取りこぼすものを一覧で固定する。

                     モデルA(sorted)        モデルB(raw)
      決定表         8行中3行が実現可能     8行中4行が実現可能
      ペアワイズ     3行(12ペア中7ペア)     3行(12ペア中9ペア)
      MC/DC          達成不能               4行(理論下限)
    """
    assert len(feasible_combos(surveys, "sorted")) == 3
    assert len(feasible_combos(surveys, "raw")) == 4
    assert len(PAIRWISE_SORTED) == 3
    assert len(PAIRWISE_RAW) == 3

    # 決定表は実現可能な行を全部通るが、ペアワイズは通るとは限らない
    assert set(PAIRWISE_SORTED) == feasible_combos(surveys, "sorted")
    assert set(PAIRWISE_RAW) < feasible_combos(surveys, "raw")


def test_summary_all_techniques_agree_on_the_verdict(surveys):
    """どの手法で選んだ行でも、判定結果そのものは当然一致する。

    手法が違うのは「どの入力を選ぶか」と「なぜそれを選んだと説明できるか」で
    あって、期待値の計算方法ではない。
    """
    for model, condition_func, predicate in (
        ("sorted", conditions_sorted, is_isosceles_sorted),
        ("raw", conditions_raw, is_isosceles_raw),
    ):
        for combo in feasible_combos(surveys, model):
            points = example_for(surveys, model, combo)
            assert condition_func(points) == combo
            assert predicate(points) is any(combo)
