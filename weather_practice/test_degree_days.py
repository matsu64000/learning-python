"""degree_days.py のテスト。

境界値(同値クラス: 1日中基準未満/1日中基準以上/基準をまたぐ)に加え、今回は
「閉じた式で導いたBE法の面積計算が、力任せの数値積分と一致するか」という
検証を軸に据える。9/13の三角形(証明を小範囲の総当たりで裏取りする)と同じ
姿勢を、今度は離散的な組み合わせではなく連続関数の積分に対して行う。
"""

import math

import pytest

from degree_days import simple_average_dd, sine_curve_temperature, single_sine_dd, true_mean_dd


def _numeric_integration_dd(temp_max, temp_min, base_temp, steps=200_000):
    """正弦波近似を微小区間に分けて台形則で数値積分する(BE法の閉じた式の検算用)。"""
    total = 0.0
    dh = 24 / steps
    for i in range(steps):
        h = (i + 0.5) * dh  # 各区間の中点(中点則。台形則より実装がシンプル)
        temp = sine_curve_temperature(h, temp_max, temp_min)
        total += max(0.0, temp - base_temp) * dh
    return total / 24


# --- simple_average_dd ---------------------------------------------------------

def test_simple_average_whole_day_above_base():
    assert simple_average_dd(temp_max=20.0, temp_min=15.0, base_temp=10.0) == 7.5


def test_simple_average_whole_day_below_base():
    assert simple_average_dd(temp_max=8.0, temp_min=2.0, base_temp=10.0) == 0.0


def test_simple_average_clips_negative_to_zero_even_when_max_exceeds_base():
    # 最高気温(12)は基準(10)を超えているが、単純平均法は平均(7)しか見ないので0になる
    assert simple_average_dd(temp_max=12.0, temp_min=2.0, base_temp=10.0) == 0.0


# --- single_sine_dd: 3つの場合分けの境界 ---------------------------------------

def test_single_sine_whole_day_above_base_matches_simple_average():
    # 1日中基準以上なら、BE法は単純平均法と厳密に一致する(場合分け2)
    result = single_sine_dd(temp_max=20.0, temp_min=15.0, base_temp=10.0)
    assert result == pytest.approx(7.5)


def test_single_sine_whole_day_below_base_is_zero():
    assert single_sine_dd(temp_max=8.0, temp_min=2.0, base_temp=10.0) == 0.0


def test_single_sine_at_the_boundary_max_equals_base():
    # 境界値: 最高気温がちょうど基準温度と一致(場合分け1の端)
    assert single_sine_dd(temp_max=10.0, temp_min=5.0, base_temp=10.0) == 0.0


def test_single_sine_at_the_boundary_min_equals_base():
    # 境界値: 最低気温がちょうど基準温度と一致(場合分け2の端)
    result = single_sine_dd(temp_max=15.0, temp_min=10.0, base_temp=10.0)
    assert result == pytest.approx(2.5)


@pytest.mark.parametrize("temp_max, temp_min, base_temp", [
    (15.0, 5.0, 10.0),   # 平均がちょうど基準と一致するケース(手計算: 5/π)
    (20.0, 5.0, 10.0),   # 平均が基準より上のケース
    (14.0, 6.0, 10.0),   # 平均が基準よりわずかに上のケース
    (13.0, 7.0, 12.9),   # 基準が最高気温のすぐ下(またぐ幅が非常に狭いケース)
])
def test_single_sine_matches_numeric_integration_when_straddling_base(temp_max, temp_min, base_temp):
    closed_form = single_sine_dd(temp_max, temp_min, base_temp)
    numeric = _numeric_integration_dd(temp_max, temp_min, base_temp)
    assert closed_form == pytest.approx(numeric, abs=1e-3)


def test_single_sine_hand_calculation_for_straddling_case():
    # 本文コメントに書いた手計算(5/π)をそのままassertで固定する
    result = single_sine_dd(temp_max=15.0, temp_min=5.0, base_temp=10.0)
    assert result == pytest.approx(5 / math.pi)


# --- 単純平均法とBE法の大小関係(Jensenの不等式) --------------------------------

def test_single_sine_is_never_less_than_simple_average():
    """基準をまたぐ日は、BE法が単純平均法以上に必ずなる。

    max(0, x)は凸関数なので、Jensenの不等式より
      E[max(0, 気温(h)-基準)] >= max(0, E[気温(h)]-基準)
    が任意の気温変化について成り立つ。左辺がBE法(曲線全体を見て0未満を切り捨てて
    から平均)、右辺が単純平均法(先に平均してから0未満を切り捨てる)にちょうど
    対応する。「平均してから引き算」と「引き算してから平均」の順序を入れ替える
    と結果が変わり、後者(BE法)が必ず大きいか等しくなる、という一般的な性質の
    具体例
    """
    cases = [
        (15.0, 5.0, 10.0), (20.0, 5.0, 10.0), (12.0, 2.0, 10.0),
        (30.0, 0.0, 10.0), (11.0, 9.0, 10.0), (20.0, 15.0, 10.0),  # 最後の2つは非またぎ
    ]
    for temp_max, temp_min, base_temp in cases:
        simple = simple_average_dd(temp_max, temp_min, base_temp)
        sine = single_sine_dd(temp_max, temp_min, base_temp)
        assert sine >= simple - 1e-9, (temp_max, temp_min, base_temp, simple, sine)


# --- true_mean_dd ----------------------------------------------------------------

def test_true_mean_dd_clips_negative_to_zero():
    assert true_mean_dd(temp_mean=8.0, base_temp=10.0) == 0.0


def test_true_mean_dd_subtracts_base():
    assert true_mean_dd(temp_mean=15.0, base_temp=10.0) == 5.0
