# 積算気温の3手法(単純平均法・BE法・実測平均法)を、実データで比較する
#
# 【狙い】degree_days.pyのテストで示した性質(BE法は単純平均法以上に必ずなる、
# 差が生じるのは基準温度を1日のうちにまたぐ日だけ)を、実際の南魚沼市のデータで
# 確認する。理屈の上での証明(Jensenの不等式)と数値積分での裏取りは既に済んで
# いるので、ここでは「現実のデータでは、どのくらいの頻度で・どのくらいの大きさで
# 差が出るのか」を見る

from pathlib import Path

from degree_days import cumulative_series, simple_average_dd, single_sine_dd, true_mean_dd
from fetch_weather import fetch_daily_weather
from plot_weather import plot_daily_divergence, plot_method_comparison

LOCATION_LABEL = "新潟県南魚沼市"
LATITUDE, LONGITUDE = 37.0655, 138.8760
SEASON_START = "2025-04-01"
SEASON_END = "2025-10-31"
BASE_TEMP = 10.0  # 多くの作物で使われる代表的な生育限界温度の目安

OUTPUT_DIR = Path(__file__).parent / "output"


def find_straddling_dates(daily_data, base_temp):
    """その日の最低気温と最高気温が基準温度をまたいでいる日の一覧を返す。"""
    return [
        row["date"] for row in daily_data
        if row["temp_min"] < base_temp < row["temp_max"]
    ]


def main():
    print(f"{LOCATION_LABEL} の気象データを取得中...")
    daily_data = fetch_daily_weather(LATITUDE, LONGITUDE, SEASON_START, SEASON_END)
    print(f"取得件数: {len(daily_data)}日分\n")

    simple_series = cumulative_series(
        daily_data, SEASON_START,
        lambda row: simple_average_dd(row["temp_max"], row["temp_min"], BASE_TEMP),
    )
    sine_series = cumulative_series(
        daily_data, SEASON_START,
        lambda row: single_sine_dd(row["temp_max"], row["temp_min"], BASE_TEMP),
    )
    true_series = cumulative_series(
        daily_data, SEASON_START,
        lambda row: true_mean_dd(row["temp_mean"], BASE_TEMP),
    )

    print(f"季節末({SEASON_END})時点の積算気温(基準{BASE_TEMP:.0f}℃):")
    print(f"  単純平均法: {simple_series[-1]['cumulative']:.1f}")
    print(f"  BE法      : {sine_series[-1]['cumulative']:.1f}"
          f"  (単純平均法との差: +{sine_series[-1]['cumulative'] - simple_series[-1]['cumulative']:.1f})")
    print(f"  実測平均法: {true_series[-1]['cumulative']:.1f}")

    straddling_dates = find_straddling_dates(daily_data, BASE_TEMP)
    print(f"\n基準温度({BASE_TEMP:.0f}℃)を1日のうちにまたいだ日: {len(straddling_dates)}日"
          f" / 全{len(daily_data)}日")

    # 単純平均法とBE法の日ごとの差が大きい日トップ5
    diffs = [
        (s["date"], sine["daily_value"] - simple["daily_value"])
        for s, sine, simple in zip(daily_data, sine_series, simple_series)
    ]
    diffs.sort(key=lambda x: x[1], reverse=True)
    print("\n単純平均法とBE法の差が大きい日 トップ5:")
    for date, diff in diffs[:5]:
        row = next(r for r in daily_data if r["date"] == date)
        straddling = row["temp_min"] < BASE_TEMP < row["temp_max"]
        print(f"  {date}: 差 +{diff:.2f}℃・日  "
              f"(最低{row['temp_min']:.1f}℃/最高{row['temp_max']:.1f}℃, またいだ日: {straddling})")

    OUTPUT_DIR.mkdir(exist_ok=True)

    comparison_path = OUTPUT_DIR / "method_comparison_2025.png"
    plot_method_comparison(
        {"単純平均法": simple_series, "BE法": sine_series, "実測平均法": true_series},
        BASE_TEMP, LOCATION_LABEL, comparison_path,
    )
    print(f"\n手法比較グラフを保存: {comparison_path}")

    divergence_path = OUTPUT_DIR / "method_divergence_2025.png"
    plot_daily_divergence(sine_series, simple_series, "BE法 - 単純平均法", straddling_dates, divergence_path)
    print(f"日々の差グラフを保存: {divergence_path}")


if __name__ == "__main__":
    main()
