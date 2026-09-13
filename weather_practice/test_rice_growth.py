"""rice_growth.py のテスト。

積算処理そのものは前回までのtennis_stats/individual_resident_taxと同じ「純粋関数
+境界値」路線。今回は「外部APIの戻り値をどう模したテストデータにするか」が新しい
論点で、fetch_weather.fetch_daily_weatherの戻り値の形をそのままダミーで組み立てる
(実際のAPI呼び出しはしない。ネットワーク越しのテストは不安定になるため)。
"""

import pytest

from rice_growth import cumulative_temperature, predict_maturity


def _daily(date, temp_mean):
    """テスト用に、fetch_daily_weatherの戻り値の最小限の形を組み立てる。"""
    return {"date": date, "temp_max": temp_mean + 5, "temp_min": temp_mean - 5,
            "temp_mean": temp_mean, "precipitation": 0.0}


# --- cumulative_temperature ---------------------------------------------------

def test_cumulative_temperature_accumulates_from_start_date_inclusive():
    daily_data = [_daily("2025-08-01", 20.0), _daily("2025-08-02", 25.0), _daily("2025-08-03", 30.0)]
    result = cumulative_temperature(daily_data, "2025-08-02")
    assert result == [
        {"date": "2025-08-02", "daily_value": 25.0, "cumulative": 25.0},
        {"date": "2025-08-03", "daily_value": 30.0, "cumulative": 55.0},
    ]


def test_cumulative_temperature_excludes_days_before_start():
    daily_data = [_daily("2025-08-01", 100.0)]  # start_dateより前。含まれないことを確認
    result = cumulative_temperature(daily_data, "2025-08-02")
    assert result == []


def test_cumulative_temperature_applies_base_temp():
    # 有効積算温度(base_temp引き)の経路。基準温度10℃なら25℃の日は15℃分だけ積算
    daily_data = [_daily("2025-08-01", 25.0)]
    result = cumulative_temperature(daily_data, "2025-08-01", base_temp=10.0)
    assert result == [{"date": "2025-08-01", "daily_value": 15.0, "cumulative": 15.0}]


# --- predict_maturity ---------------------------------------------------------

def test_predict_maturity_returns_matured_when_threshold_reached_exactly():
    # 境界値: 累計がちょうど閾値と一致する日(>=の="等しい"側)
    daily_data = [_daily("2025-08-01", 25.0), _daily("2025-08-02", 25.0)]
    result = predict_maturity(daily_data, "2025-08-01", threshold_c=50.0)
    assert result == {
        "status": "matured", "maturity_date": "2025-08-02",
        "days_after_heading": 1, "cumulative_at_maturity": 50.0,
    }


def test_predict_maturity_not_yet_reached_just_below_threshold():
    # 境界値の反対側: 閾値のすぐ手前で終わるデータ
    daily_data = [_daily("2025-08-01", 25.0), _daily("2025-08-02", 24.9)]
    result = predict_maturity(daily_data, "2025-08-01", threshold_c=50.0)
    assert result == {"status": "not_yet_matured", "cumulative_so_far": 49.9, "last_date": "2025-08-02"}


def test_predict_maturity_stops_at_first_day_threshold_is_reached():
    # 閾値到達後もデータが続く場合、最初に到達した日を返す(それ以降は見ない)
    daily_data = [_daily("2025-08-01", 30.0), _daily("2025-08-02", 30.0), _daily("2025-08-03", 30.0)]
    result = predict_maturity(daily_data, "2025-08-01", threshold_c=50.0)
    assert result["maturity_date"] == "2025-08-02"  # 08-03まで待たない


def test_predict_maturity_raises_when_no_data_on_or_after_heading_date():
    daily_data = [_daily("2025-07-31", 25.0)]  # 出穂日より前のデータしか無い
    with pytest.raises(ValueError):
        predict_maturity(daily_data, heading_date="2025-08-01")
