"""individual_resident_tax.py のテスト。

境界値分析(境界のすぐ内側/すぐ外側をペアで確認)を主軸にする。
- calc_basic_deduction: コード中に定数として書かれている境界(24,000,000等)
- classify_dependent: 年齢区分の境界(16/19/23/70歳)
- calc_exemption_thresholds / judge_exemption_status: 計算式から求まる境界
  (定数ではなく、まず閾値を計算してからそのすぐ内側/外側をテストする)
- calc_salary_deduction: 5段階速算表の境界(4箇所)
- calc_adjustment_reduction: 定数境界(200万円)に加え、min()/max()が効き始める
  境界(値同士の大小関係で決まる、コード中に定数として現れない境界)
"""

import pytest

from individual_resident_tax import (
    Dependent,
    calc_adjustment_reduction,
    calc_basic_deduction,
    calc_exemption_thresholds,
    calc_salary_deduction,
    classify_dependent,
    judge_exemption_status,
    judge_widow_or_single_parent_deduction,
)


# --- calc_basic_deduction: 逓減の境界(コード中の定数がそのまま境界) --------

@pytest.mark.parametrize("total_income, expected", [
    (24_000_000, 430_000),  # 逓減開始のすぐ内側(まだ満額)
    (24_000_001, 290_000),  # すぐ外側(1段階目の逓減)
    (24_500_000, 290_000),  # 2段階目の境界のすぐ内側
    (24_500_001, 150_000),  # すぐ外側
    (25_000_000, 150_000),  # 消失直前の境界のすぐ内側
    (25_000_001, 0),        # すぐ外側(基礎控除ゼロ)
])
def test_calc_basic_deduction_boundaries(total_income, expected):
    assert calc_basic_deduction(total_income) == expected


# --- classify_dependent: 年齢区分の境界 -----------------------------------

@pytest.mark.parametrize("age, expected", [
    (15, None),        # 年少扶養(控除対象外)のすぐ内側
    (16, "general"),   # すぐ外側(一般扶養に切り替わる)
    (18, "general"),   # 一般/特定の境界のすぐ内側
    (19, "specific"),  # すぐ外側
    (22, "specific"),  # 特定/一般の境界のすぐ内側
    (23, "general"),   # すぐ外側(再び一般扶養に戻る)
    (69, "general"),   # 一般/老人の境界のすぐ内側
    (70, "elderly"),   # すぐ外側(同居でない前提)
])
def test_classify_dependent_age_boundaries(age, expected):
    assert classify_dependent(Dependent(age=age)) == expected


def test_classify_dependent_elderly_cohabiting_flag():
    # 年齢だけでなく同居老親等フラグでも区分が変わる(数値境界とは別の同値クラス)
    assert classify_dependent(Dependent(age=70, is_lineal_ascendant_living_together=True)) \
        == "elderly_cohabiting"


# --- calc_exemption_thresholds: 扶養人数0人は2つの限度額が一致する ---------

def test_calc_exemption_thresholds_no_dependents_both_thresholds_equal():
    # 扶養親族がいない場合、「所得割のみ非課税」の帯が存在しない(2限度額が同額)
    thresholds = calc_exemption_thresholds(dependent_count=0)
    assert thresholds == {"per_capita": 450_000, "income": 450_000}


def test_calc_exemption_thresholds_with_dependent():
    thresholds = calc_exemption_thresholds(dependent_count=1)
    assert thresholds == {"per_capita": 1_010_000, "income": 1_120_000}


# --- judge_exemption_status: 計算された閾値そのものが境界 ------------------
# 扶養0人: 閾値(450,000円)は1本のみ
# 扶養1人: 閾値(1,010,000円・1,120,000円)の2本、間に「所得割のみ非課税」の帯がある

@pytest.mark.parametrize("total_income, dependent_count, expected", [
    (450_000, 0, "exempt_both"),        # 扶養0人の唯一の境界、すぐ内側
    (450_001, 0, "taxable"),            # すぐ外側
    (1_010_000, 1, "exempt_both"),      # 扶養1人、均等割側境界のすぐ内側
    (1_010_001, 1, "exempt_income_only"),  # すぐ外側(所得割のみ非課税の帯に入る)
    (1_120_000, 1, "exempt_income_only"),  # 所得割側境界のすぐ内側
    (1_120_001, 1, "taxable"),          # すぐ外側(通常課税)
])
def test_judge_exemption_status_boundaries(total_income, dependent_count, expected):
    assert judge_exemption_status(total_income, dependent_count) == expected


# --- calc_salary_deduction: 5段階速算表の境界(4箇所) -------------------------
# 速算表は境界をまたいでも値が連続するように作られているため、境界のすぐ内側と
# すぐ外側で同じ値になるペアが多い(設計として正しく連続していることの確認になる)。

@pytest.mark.parametrize("income, expected", [
    (1_625_000, 550_000),      # 定額控除の上限、すぐ内側
    (1_625_001, 550_000),      # すぐ外側(速算式に切り替わるが値は連続)
    (1_800_000, 620_000),      # 1段階目/2段階目の境界、すぐ内側
    (1_800_001, 620_000),      # すぐ外側
    (3_600_000, 1_160_000),    # 2段階目/3段階目の境界、すぐ内側
    (3_600_001, 1_160_000),    # すぐ外側
    (6_600_000, 1_760_000),    # 3段階目/4段階目の境界、すぐ内側
    (6_600_001, 1_760_000),    # すぐ外側
    (8_500_000, 1_950_000),    # 4段階目/上限の境界、すぐ内側
    (8_500_001, 1_950_000),    # すぐ外側(以降は定額)
])
def test_calc_salary_deduction_boundaries(income, expected):
    assert calc_salary_deduction(income) == expected


# --- calc_adjustment_reduction ----------------------------------------------
# 境界は3種類混在する:
#   (a) コード中の定数境界: total_income=25,000,000円(対象外になる上限)、
#       taxable_income=2,000,000円(計算式が切り替わる境界)
#   (b) min()が効き始める境界: personal_deduction_diff_total と taxable_income の
#       大小関係で決まる(定数としては現れない)
#   (c) max(...,0)で0に張り付く境界: diff_total - (taxable_income - 2,000,000) の
#       符号が変わる点(これも計算しないと分からない境界)

@pytest.mark.parametrize(
    "taxable_income, total_income, diff_total, expected",
    [
        # (a) total_income=25,000,000円の境界(taxable_income=1,000,000円で固定)
        (1_000_000, 25_000_000, 500_000, {"city": 15_000, "prefecture": 10_000}),
        (1_000_000, 25_000_001, 500_000, {"city": 0, "prefecture": 0}),
        # (a) taxable_income=2,000,000円の境界(diff_total=400,000円で固定)
        (2_000_000, 1_000_000, 400_000, {"city": 12_000, "prefecture": 8_000}),
        (2_000_001, 1_000_000, 400_000, {"city": 11_999, "prefecture": 7_999}),
        # (b) min(diff_total, taxable_income)が効き始める境界
        #     (taxable_income=1,000,000円で固定、diff_totalを前後させる)
        (1_000_000, 1_000_000, 999_999, {"city": 29_999, "prefecture": 19_999}),
        (1_000_000, 1_000_000, 1_000_000, {"city": 30_000, "prefecture": 20_000}),
        (1_000_000, 1_000_000, 1_000_001, {"city": 30_000, "prefecture": 20_000}),
        # (c) max(...,0)で0に張り付く境界
        #     (taxable_income=2,500,000円で固定、diff_total - 500,000円の符号が変わる点。
        #     符号が変わった直後の値は//100の丸めで0と区別がつかないため、
        #     floorが外れて実際に計算されることまで確認できる値を最後に置く)
        (2_500_000, 1_000_000, 499_999, {"city": 0, "prefecture": 0}),   # 符号変化前(floorで0)
        (2_500_000, 1_000_000, 500_000, {"city": 0, "prefecture": 0}),   # ちょうど境界(計算上も0)
        (2_500_000, 1_000_000, 534_000, {"city": 1_020, "prefecture": 680}),  # floorが外れ計算値になる
    ],
)
def test_calc_adjustment_reduction_boundaries(taxable_income, total_income, diff_total, expected):
    assert calc_adjustment_reduction(taxable_income, total_income, diff_total) == expected


# --- judge_widow_or_single_parent_deduction: 決定表による削減 ---------------
# 複合条件(独立した要素をAND/ORで束ねた判定)の練習題材。6要素の全組み合わせは
# 2(性別)x3(婚姻状況)x2(子)x2(他の扶養親族)x2(所得500万円以下)x2(事実婚)=96通りだが、
# 判定順序(早期リターンの順序)をそのまま行にした決定表で8行に削減できる。
# "-"はdon't care(この行の結果に効かない要素)。判定順に意味があるので、上の行から
# 順に「最初に一致した行」が採用される(COBOLのEVALUATE / WHEN OTHERと同じ考え方)。
#
#   Rule 事実婚 所得>500万 子あり 女性  婚姻状況  他扶養親族  結果            該当組合せ数
#    1    Y      -         -     -     -         -          none            48
#    2    N      Y         -     -     -         -          none            24
#    3    N      N         Y     -     -         -          single_parent   12
#    4    N      N         N     男    -         -          none             6
#    5    N      N         N     女    死別      -          widow            2
#    6    N      N         N     女    離婚      Y          widow            1
#    7    N      N         N     女    離婚      N          none             1
#    8    N      N         N     女    未婚      -          none             2
#                                                            合計            96 (全組合せと一致)
#
# 各行の代表値は、don't careの部分にあえて「判定順が違っていたら別の結果になる値」を
# 選ぶ(例: Rule1は事実婚以外を全て"single_parentになりそうな値"にしておき、事実婚の
# 判定が本当に最優先で効くことまで確認する)。8/9のテニス集計で「rejectedがcorrectedより
# 優先」を確認したのと同じ、優先順位のテストという考え方。

@pytest.mark.parametrize(
    "gender, marital_status, has_child, has_other_relative, total_income, has_defacto, expected",
    [
        # Rule1: 事実婚があれば、他が全てsingle_parent向きの値でもnone
        ("female", "unmarried", True, True, 1_000_000, True, "none"),
        # Rule2: 所得500万円超なら、他が全てsingle_parent向きの値でもnone
        ("female", "divorced", True, True, 5_000_001, False, "none"),
        # Rule3: 子がいれば、婚姻状況・他の扶養親族に関わらずsingle_parent
        #        (女性・死別・他の扶養親族ありという、widowにもなり得そうな値を敢えて使う)
        ("female", "widowed", True, True, 1_000_000, False, "single_parent"),
        # Rule4: 男性なら、婚姻状況・他の扶養親族に関わらずnone(寡婦控除は女性のみ)
        ("male", "widowed", False, True, 1_000_000, False, "none"),
        # Rule5: 女性+死別なら、他の扶養親族に関わらずwidow(扶養親族不問)
        ("female", "widowed", False, False, 1_000_000, False, "widow"),
        # Rule6: 女性+離婚+他の扶養親族ありでwidow
        ("female", "divorced", False, True, 1_000_000, False, "widow"),
        # Rule7: 女性+離婚だが他の扶養親族なしはnone
        ("female", "divorced", False, False, 1_000_000, False, "none"),
        # Rule8: 女性+未婚は、他の扶養親族の有無に関わらずnone(離婚・死別のみが寡婦控除の対象)
        ("female", "unmarried", False, True, 1_000_000, False, "none"),
    ],
)
def test_judge_widow_or_single_parent_deduction_decision_table(
    gender, marital_status, has_child, has_other_relative, total_income, has_defacto, expected
):
    result = judge_widow_or_single_parent_deduction(
        gender, marital_status, has_child, has_other_relative, total_income, has_defacto
    )
    assert result == expected


# --- judge_widow_or_single_parent_deduction: ペアワイズ ---------------------
# 決定表と違い、判定ロジックの構造(優先順位)は使わず、「どの2要素の値の組み合わせも
# 最低1回は登場させる」という機械的な基準だけで組む。6要素・レベル数(2,3,2,2,2,2)の
# 全ペア数は70組。手作業では抜け漏れが起きやすいため、貪欲法(各行を追加するたびに
# 「まだ被覆していないペアを一番多くカバーする組み合わせ」を選ぶ)で生成し、
# 全ペアを被覆できているかをコードで検証した(pairwise_gen.py参照。理論上の下限は
# 3値要素と2値要素の積である6行だが、貪欲法は最小性を保証しないため、この題材では
# 8行になった)。
# 決定表の8行とは異なる観点の8行になっている点に注目(例えば「男性+死別+子あり+
# 事実婚あり」のように、決定表では1行にまとめられる要素同士の"意外な組み合わせ"を
# 拾っている)。

@pytest.mark.parametrize(
    "gender, marital_status, has_child, has_other_relative, total_income, has_defacto, expected",
    [
        ("male", "divorced", False, False, 3_000_000, False, "none"),
        ("male", "widowed", True, True, 5_500_000, True, "none"),
        ("female", "unmarried", False, False, 5_500_000, True, "none"),
        ("female", "unmarried", True, True, 3_000_000, False, "single_parent"),
        ("female", "divorced", False, True, 3_000_000, True, "none"),
        ("female", "widowed", False, False, 3_000_000, False, "widow"),
        ("male", "divorced", True, False, 5_500_000, False, "none"),
        ("male", "unmarried", False, False, 3_000_000, False, "none"),
    ],
)
def test_judge_widow_or_single_parent_deduction_pairwise(
    gender, marital_status, has_child, has_other_relative, total_income, has_defacto, expected
):
    result = judge_widow_or_single_parent_deduction(
        gender, marital_status, has_child, has_other_relative, total_income, has_defacto
    )
    assert result == expected


# --- judge_widow_or_single_parent_deduction: MC/DC --------------------------
# 決定表・ペアワイズと違い、「その条件1つだけを変えたら結果が変わる」ペアを、
# 5つの決定点それぞれについて作る。D1〜D4は単一条件の決定(if1個)なので、
# ペアはそのままdon't careを埋めた2行で済む(実質、決定表の"優先順位を証明する
# 意地悪な値"と同じもの)。D5だけが本当の複合条件:
#   is_widow = (marital_status=="widowed") or (marital_status=="divorced" and has_other_relative)
# ここではA=is_widowed, B=is_divorced, C=has_other_relativeの3条件に対して、
# それぞれ単独の効果を示すペアを用意する。ただしAとBは同じmarital_status(3値)から
# 導かれ両立しないため、理論上の最小N+1=4行では済まず、5行必要になる
# (A/Bを独立な2つの真偽値として作れない、という制約がそのまま行数に表れる)。
#
# 決定点   ペアの意図                          行の組
#  D1      事実婚あり/なしだけを変える          R1  / R2
#  D2      所得500万円境界だけを変える          R2  / R3
#  D3      子の有無だけを変える                R2  / R6
#  D4      性別だけを変える(死別で意地悪に)     R7  / R8
#  D5-A    死別/未婚だけを変える(他扶養親族=無)  R8  / RowQ
#  D5-B    離婚/未婚だけを変える(他扶養親族=有)  RowR / R6
#  D5-C    他扶養親族の有無だけを変える(離婚固定) RowR / RowU
#
# 7ペア・14行分の「単独条件の効果」を、行の使い回しにより9行で満たせる
# (決定表・ペアワイズと同じく8行前後に収まり、件数だけ見ると差が小さいが、
# 「なぜこの9行なのか」の説明力が全く違う)。

@pytest.mark.parametrize(
    "gender, marital_status, has_child, has_other_relative, total_income, has_defacto, expected",
    [
        ("female", "unmarried", True, True, 5_000_000, True, "none"),        # R1: D1=True
        ("female", "unmarried", True, True, 5_000_000, False, "single_parent"),  # R2: D1=False(基準行)
        ("female", "unmarried", True, True, 5_000_001, False, "none"),       # R3: D2=True(所得超過)
        ("female", "unmarried", False, True, 5_000_000, False, "none"),      # R6: D3=False(子なし)
        ("male", "widowed", False, False, 5_000_000, False, "none"),         # R7: D4=True(男性)
        ("female", "widowed", False, False, 5_000_000, False, "widow"),      # R8: D4=False(女性)+D5-A
        ("female", "unmarried", False, False, 5_000_000, False, "none"),     # RowQ: D5-A対
        ("female", "divorced", False, True, 5_000_000, False, "widow"),      # RowR: D5-B/D5-C
        ("female", "divorced", False, False, 5_000_000, False, "none"),      # RowU: D5-C対
    ],
)
def test_judge_widow_or_single_parent_deduction_mcdc(
    gender, marital_status, has_child, has_other_relative, total_income, has_defacto, expected
):
    result = judge_widow_or_single_parent_deduction(
        gender, marital_status, has_child, has_other_relative, total_income, has_defacto
    )
    assert result == expected
