"""sakura_bloom.py のテスト。

境界値・基本ケースに加え、実装中に実際に踏んだ不具合(find_dormancy_break_date が
search_end_date無指定だと暖冬の年に翌冬まで探し続けてしまう)の回帰テストを含む。
"""

import math

import pytest

from sakura_bloom import (
    dts_value, find_dormancy_break_date, implied_dts_threshold, is_chill_day,
    predict_bloom_date, predict_bloom_simple_rule,
)


def _daily(date, temp_mean, temp_max=None):
    return {"date": date, "temp_max": temp_max if temp_max is not None else temp_mean + 5,
            "temp_min": temp_mean - 5, "temp_mean": temp_mean, "precipitation": 0.0}


# --- is_chill_day / dts_value ---------------------------------------------------

def test_is_chill_day_boundary():
    assert is_chill_day(5.0, chill_threshold=5.0) is True   # 境界: 等しい場合も含む
    assert is_chill_day(5.1, chill_threshold=5.0) is False


def test_dts_value_equals_one_at_reference_temperature():
    # 288.2K(≈15.05℃)がDTS=1.0になる基準温度
    assert dts_value(288.2 - 273.15) == pytest.approx(1.0)


def test_dts_value_is_monotonically_increasing_with_temperature():
    temps = [-5.0, 0.0, 10.0, 20.0, 30.0]
    values = [dts_value(t) for t in temps]
    assert values == sorted(values)


# --- find_dormancy_break_date ---------------------------------------------------

def test_find_dormancy_break_date_counts_from_start_date():
    daily_data = [_daily("2024-10-01", 3.0), _daily("2024-10-02", 3.0), _daily("2024-10-03", 3.0)]
    result = find_dormancy_break_date(daily_data, "2024-10-01", required_chill_days=2, chill_threshold=5.0)
    assert result == "2024-10-02"


def test_find_dormancy_break_date_ignores_days_above_threshold():
    daily_data = [_daily("2024-10-01", 3.0), _daily("2024-10-02", 20.0), _daily("2024-10-03", 3.0)]
    result = find_dormancy_break_date(daily_data, "2024-10-01", required_chill_days=2, chill_threshold=5.0)
    assert result == "2024-10-03"  # 10/2は暖かい日なのでカウントされない


def test_find_dormancy_break_date_returns_none_when_never_reached():
    daily_data = [_daily("2024-10-01", 20.0)]
    assert find_dormancy_break_date(daily_data, "2024-10-01", required_chill_days=5) is None


def test_find_dormancy_break_date_stops_at_search_end_date_regression():
    """回帰テスト: search_end_date指定時、届かなければ次の冬まで探しに行かず打ち切る。

    実装中に実際に踏んだ不具合: 暖冬でその冬に必要チルデイ数へ届かなかった場合、
    search_end_date無指定だと、気温の高い春・夏(チルデイ0)を素通りして翌年の冬まで
    数え続けてしまい、明後日year(翌年12月など)の日付を誤って返していた
    """
    daily_data = (
        [_daily(f"2024-10-{d:02d}", 8.0) for d in range(1, 32)]  # 暖冬: 閾値5℃を超え続ける
        + [_daily(f"2025-0{m}-{d:02d}", 15.0) for m in (1, 2, 3) for d in range(1, 29)]  # 春
        + [_daily(f"2025-12-{d:02d}", 3.0) for d in range(1, 20)]  # 翌年の冬(ここでやっと閾値以下)
    )
    # search_end_date無指定なら、翌年12月まで探しに行って見つけてしまう(修正前の挙動)
    unbounded = find_dormancy_break_date(daily_data, "2024-10-01", required_chill_days=5, chill_threshold=5.0)
    assert unbounded is not None and unbounded.startswith("2025-12")

    # search_end_dateを指定すれば、その日までに届かない場合は正しくNoneになる
    bounded = find_dormancy_break_date(
        daily_data, "2024-10-01", required_chill_days=5, chill_threshold=5.0, search_end_date="2025-04-30",
    )
    assert bounded is None


# --- predict_bloom_date ----------------------------------------------------------

def test_predict_bloom_date_reaches_threshold():
    # dts_value(20.0) ≈ 1.7447。2日で閾値3.0を超える
    daily_data = [_daily("2025-03-01", 20.0), _daily("2025-03-02", 20.0)]
    result = predict_bloom_date(daily_data, "2025-03-01", dts_threshold=3.0)
    assert result["status"] == "bloomed"
    assert result["bloom_date"] == "2025-03-02"


def test_predict_bloom_date_not_yet_reached():
    daily_data = [_daily("2025-03-01", 0.0)]
    result = predict_bloom_date(daily_data, "2025-03-01", dts_threshold=100.0)
    assert result["status"] == "not_yet_bloomed"


# --- implied_dts_threshold --------------------------------------------------------

def test_implied_dts_threshold_matches_cumulative_at_actual_date():
    daily_data = [_daily("2025-03-01", 20.0), _daily("2025-03-02", 20.0), _daily("2025-03-03", 20.0)]
    implied = implied_dts_threshold(daily_data, "2025-03-01", actual_bloom_date="2025-03-02")
    assert implied == pytest.approx(2 * dts_value(20.0))


def test_implied_dts_threshold_raises_when_actual_date_before_dormancy_break():
    daily_data = [_daily("2025-03-02", 20.0), _daily("2025-03-03", 20.0)]
    with pytest.raises(ValueError):
        implied_dts_threshold(daily_data, dormancy_break_date="2025-03-02", actual_bloom_date="2025-03-01")


# --- predict_bloom_simple_rule (600℃の法則) --------------------------------------

def test_predict_bloom_simple_rule_uses_max_temp_from_feb1_by_default():
    daily_data = [_daily(f"2025-02-{d:02d}", 10.0, temp_max=15.0) for d in range(1, 5)]
    # 最高気温15℃を4日積算すると60。閾値を60に設定すれば4日目に到達する
    result = predict_bloom_simple_rule(daily_data, year=2025, threshold=60.0)
    assert result == {"status": "bloomed", "bloom_date": "2025-02-04", "cumulative": 60.0}


def test_predict_bloom_simple_rule_ignores_other_years():
    daily_data = [_daily("2024-02-01", 100.0, temp_max=100.0), _daily("2025-02-01", 10.0, temp_max=10.0)]
    result = predict_bloom_simple_rule(daily_data, year=2025, threshold=5.0)
    # 2024年分(100℃)が混ざっていても無視され、2025年分だけで積算される
    assert result == {"status": "bloomed", "bloom_date": "2025-02-01", "cumulative": 10.0}
