# 南魚沼市の気象データから、コシヒカリの収穫適期を予測する
#
# 実行すると:
#   1. Open-Meteoから2025年の生育期間(4/1〜10/31)の日次気象データを取得
#   2. 出穂日からの積算気温をもとに収穫適期(成熟期)を予測
#   3. 気温・降水量のグラフと、積算気温のグラフをそれぞれPNGで保存
#
# 田植え日(5/15)・出穂日(8/5)は、南魚沼地域のコシヒカリ栽培暦の目安値
# (田植え5/5〜5/20、出穂8月上旬)から代表的な1日を仮定した値。実際の年・圃場に
# よって前後する。rice_growth.pyのモジュール冒頭コメントに記載の通り、出穂日
# そのものを気温から予測するモデルは今回のスコープ外。

from pathlib import Path

from fetch_weather import fetch_daily_weather
from plot_weather import plot_cumulative, plot_season
from rice_growth import cumulative_temperature, predict_maturity

LOCATION_LABEL = "新潟県南魚沼市"
LATITUDE, LONGITUDE = 37.0655, 138.8760

SEASON_START = "2025-04-01"
SEASON_END = "2025-10-31"
TRANSPLANT_DATE = "2025-05-15"
HEADING_DATE = "2025-08-05"
MATURITY_THRESHOLD_C = 1000.0

OUTPUT_DIR = Path(__file__).parent / "output"


def main():
    print(f"{LOCATION_LABEL}({LATITUDE}, {LONGITUDE}) の気象データを取得中...")
    daily_data = fetch_daily_weather(LATITUDE, LONGITUDE, SEASON_START, SEASON_END)
    print(f"取得件数: {len(daily_data)}日分 ({daily_data[0]['date']} 〜 {daily_data[-1]['date']})")

    result = predict_maturity(daily_data, HEADING_DATE, MATURITY_THRESHOLD_C)
    print()
    print(f"田植え日: {TRANSPLANT_DATE}")
    print(f"出穂日  : {HEADING_DATE}")
    if result["status"] == "matured":
        print(f"予測収穫適期: {result['maturity_date']}"
              f"(出穂から{result['days_after_heading']}日、積算気温{result['cumulative_at_maturity']:.1f}℃)")
        maturity_date = result["maturity_date"]
    else:
        print(f"取得期間内では成熟に到達せず(データ終端{result['last_date']}時点で"
              f"積算気温{result['cumulative_so_far']:.1f}℃)")
        maturity_date = None

    OUTPUT_DIR.mkdir(exist_ok=True)

    season_path = OUTPUT_DIR / "season_2025.png"
    plot_season(daily_data, TRANSPLANT_DATE, HEADING_DATE, maturity_date, LOCATION_LABEL, season_path)
    print(f"\n気温・降水量グラフを保存: {season_path}")

    cumulative_series = cumulative_temperature(daily_data, HEADING_DATE)
    cumulative_path = OUTPUT_DIR / "cumulative_2025.png"
    plot_cumulative(cumulative_series, HEADING_DATE, MATURITY_THRESHOLD_C, maturity_date, cumulative_path)
    print(f"積算気温グラフを保存: {cumulative_path}")


if __name__ == "__main__":
    main()
