# 「単純平均法・BE法が実測平均法より系統的に高く出る」理由の掘り下げ
#
# 【背景】compare_degree_day_methods.py(9/13)で、南魚沼市2025年のデータでは
# 単純平均法・BE法(どちらも最高・最低の2値だけを使う近似)が、Open-Meteoの
# 日平均気温を使った実測平均法より高く出ることを確認した。仮説は「1日の気温変化が
# 対称な正弦波ではなく、非対称(日の出後は急上昇・夜間は緩やかに下降)なため」。
#
# 【検証方法】degree_days.pyのhourly_integrated_dd(1時間ごとの実測相当値24点を
# そのまま積算する、最も正確な方法)を新たな"正解"として追加する。あわせて、
# 季節を通じた「典型的な1日の気温カーブの形」を、実測の時間別データと
# BE法が仮定する正弦波とで直接重ねて比較する

from collections import defaultdict

from degree_days import (
    cumulative_series,
    hourly_integrated_dd,
    simple_average_dd,
    single_sine_dd,
    sine_curve_temperature,
    true_mean_dd,
)
from fetch_weather import fetch_daily_weather, fetch_hourly_temperature
from plot_weather import plot_diurnal_shape, plot_method_comparison

LOCATION_LABEL = "新潟県南魚沼市"
LATITUDE, LONGITUDE = 37.0655, 138.8760
SEASON_START = "2025-04-01"
SEASON_END = "2025-10-31"
BASE_TEMP = 10.0


def average_diurnal_shape(hourly_by_date):
    """各日の(その時刻の気温 - その日の平均気温)を時刻ごとに平均する。

    絶対値ではなく「その日の平均からのズレ」を使うことで、季節を通じた
    寒暖の違いを均し、1日の中での気温変化の"形"だけを取り出せる
    (COBOL的に言えば、日々のレコードを正規化してから項目ごとに集計する処理)
    """
    sums = defaultdict(float)
    counts = defaultdict(int)
    for temps in hourly_by_date.values():
        if len(temps) != 24:
            continue  # 欠測がある日はスキップ
        day_mean = sum(temps) / len(temps)
        for hour, t in enumerate(temps):
            sums[hour] += t - day_mean
            counts[hour] += 1
    return {hour: sums[hour] / counts[hour] for hour in sorted(sums)}


def find_peak_and_trough_hour(shape):
    """平均カーブの形から、気温が最も高い/低い時刻を求める。"""
    peak_hour = max(shape, key=shape.get)
    trough_hour = min(shape, key=shape.get)
    return peak_hour, trough_hour


def main():
    print(f"{LOCATION_LABEL} の時間別気温を取得中(1時間ごと、{SEASON_START}〜{SEASON_END})...")
    hourly_by_date = fetch_hourly_temperature(LATITUDE, LONGITUDE, SEASON_START, SEASON_END)
    daily_data = fetch_daily_weather(LATITUDE, LONGITUDE, SEASON_START, SEASON_END)
    print(f"取得件数: {len(hourly_by_date)}日分(時間別) / {len(daily_data)}日分(日次)\n")

    # --- 1. 典型的な1日の気温カーブの形: 実測 vs BE法が仮定する正弦波 ---
    real_shape = average_diurnal_shape(hourly_by_date)
    peak_hour, trough_hour = find_peak_and_trough_hour(real_shape)
    print(f"実測データでの平均カーブ: 最高は{peak_hour}時頃、最低は{trough_hour}時頃")
    print("(BE法の正弦波モデルは、最低=0時/24時、最高=12時と仮定している)")

    amplitude = (real_shape[peak_hour] - real_shape[trough_hour]) / 2
    sine_shape = {
        hour: sine_curve_temperature(hour, amplitude, -amplitude) for hour in range(24)
    }

    rise_hours = peak_hour - trough_hour if peak_hour > trough_hour else peak_hour + 24 - trough_hour
    fall_hours = 24 - rise_hours
    print(f"上昇にかかる時間: 約{rise_hours}時間 / 下降にかかる時間: 約{fall_hours}時間"
          f"  (対称な正弦波なら両方12時間のはず)\n")

    # --- 2. 積算気温の季節合計: 4手法で比較(hourly_integrated_ddを新たな正解として追加) ---
    simple_series = cumulative_series(
        daily_data, SEASON_START,
        lambda row: simple_average_dd(row["temp_max"], row["temp_min"], BASE_TEMP),
    )
    sine_series = cumulative_series(
        daily_data, SEASON_START,
        lambda row: single_sine_dd(row["temp_max"], row["temp_min"], BASE_TEMP),
    )
    true_mean_series = cumulative_series(
        daily_data, SEASON_START,
        lambda row: true_mean_dd(row["temp_mean"], BASE_TEMP),
    )

    hourly_series = []
    hourly_cumulative = 0.0
    for row in daily_data:
        temps = hourly_by_date.get(row["date"])
        if temps is None or len(temps) != 24:
            continue
        daily_value = hourly_integrated_dd(temps, BASE_TEMP)
        hourly_cumulative += daily_value
        hourly_series.append({"date": row["date"], "daily_value": daily_value, "cumulative": hourly_cumulative})
    hourly_series_last = hourly_series[-1]["cumulative"]

    print(f"季節合計(基準{BASE_TEMP:.0f}℃、{SEASON_START}〜{SEASON_END}):")
    print(f"  単純平均法    : {simple_series[-1]['cumulative']:.1f}")
    print(f"  BE法          : {sine_series[-1]['cumulative']:.1f}")
    print(f"  実測平均法    : {true_mean_series[-1]['cumulative']:.1f}"
          "  (Open-Meteoの日平均気温ベース)")
    print(f"  時間別積算法  : {hourly_series_last:.1f}"
          f"  ({len(hourly_series)}日分、1時間ごとの実測相当値を直接積算した「正解」)")

    print(f"\n各手法と時間別積算法(正解)との差:")
    for label, series in (("単純平均法", simple_series), ("BE法", sine_series), ("実測平均法", true_mean_series)):
        diff = series[-1]["cumulative"] - hourly_series_last
        print(f"  {label}: {diff:+.1f}")

    from pathlib import Path
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    shape_path = output_dir / "diurnal_shape_2025.png"
    plot_diurnal_shape(real_shape, sine_shape, LOCATION_LABEL, shape_path)
    print(f"\n典型的な1日の気温カーブ比較グラフを保存: {shape_path}")

    comparison_path = output_dir / "method_comparison_with_hourly_2025.png"
    plot_method_comparison(
        {
            "単純平均法": simple_series, "BE法": sine_series,
            "実測平均法": true_mean_series, "時間別積算法(正解)": hourly_series,
        },
        BASE_TEMP, LOCATION_LABEL, comparison_path,
    )
    print(f"4手法比較グラフを保存: {comparison_path}")


if __name__ == "__main__":
    main()
