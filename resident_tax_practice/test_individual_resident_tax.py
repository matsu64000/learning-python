"""individual_resident_tax.py のテスト。

境界値分析(境界のすぐ内側/すぐ外側をペアで確認)を主軸にする。
- calc_basic_deduction: コード中に定数として書かれている境界(24,000,000等)
- classify_dependent: 年齢区分の境界(16/19/23/70歳)
- calc_exemption_thresholds / judge_exemption_status: 計算式から求まる境界
  (定数ではなく、まず閾値を計算してからそのすぐ内側/外側をテストする)
"""

import pytest

from individual_resident_tax import (
    Dependent,
    calc_basic_deduction,
    calc_exemption_thresholds,
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
