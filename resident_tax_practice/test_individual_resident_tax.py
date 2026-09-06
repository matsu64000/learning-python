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
