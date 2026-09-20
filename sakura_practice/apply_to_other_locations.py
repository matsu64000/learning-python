# 東京(靖国神社)で較正したDTS法パラメータを、そのまま他地点に「移植」してみる
#
# 【この実験の狙い】
#   calibrate_and_validate.pyのDTS閾値は「東京の観測データに対してだけ」較正した
#   値。チルデイ必要日数・DTS閾値は本来、地点(気候)ごとに異なるはず。
#   その東京専用パラメータを、そのまま別の地点の気温データに当てはめたら
#   どれくらいズレるか(移植誤差)を実測で確認する
#
# 【地点の選び方】
#   南魚沼市には気象庁の公式観測地点(実測開花日)が無い。そこで:
#     - 新潟市: 気象庁の公式観測地点があり、実測開花日(2016-2026)と比較できる
#       → 移植誤差を「日数」で定量化できる
#     - 南魚沼市: 実測が無いので予測日を出すだけ(検証は不可能)。ただし新潟市との
#       予測日の差を見れば、内陸・山間部(標高が高く寒い)による遅れの傾向は
#       考察できる

from datetime import date
from pathlib import Path

from calibrate_and_validate import (
    ACTUAL_BLOOM_DATES as TOKYO_ACTUAL_BLOOM_DATES, CHILL_START_MONTH_DAY, CHILL_THRESHOLD,
    DATA_END, DATA_START, LATITUDE as TOKYO_LAT, LONGITUDE as TOKYO_LON, _mae, evaluate_candidate,
)
from fetch_weather import fetch_daily_weather
from plot_sakura import plot_transplant_comparison
from sakura_bloom import find_dormancy_break_date, predict_bloom_date

OUTPUT_DIR = Path(__file__).parent / "output"

# calibrate_and_validate.pyの結果、検証MAEが最小だった候補(2026-09-13時点)
REQUIRED_CHILL_DAYS = 25

NIIGATA_LAT, NIIGATA_LON = 37.8954, 139.0183          # 新潟地方気象台(公式観測地点)
MINAMIUONUMA_LAT, MINAMIUONUMA_LON = 37.0655, 138.8760  # 南魚沼市役所(weather_practiceと同じ地点)

# 気象庁「さくらの開花日」(新潟、2016-2026年、公式観測)
NIIGATA_ACTUAL_BLOOM_DATES = {
    2016: "2016-04-03", 2017: "2017-04-08", 2018: "2018-04-03", 2019: "2019-04-05",
    2020: "2020-04-01", 2021: "2021-03-29", 2022: "2022-04-08", 2023: "2023-03-27",
    2024: "2024-04-06", 2025: "2025-04-06", 2026: "2026-03-31",
}

TARGET_YEARS = sorted(NIIGATA_ACTUAL_BLOOM_DATES)


def apply_transplanted_model(daily_data, required_chill_days, dts_threshold, years):
    """東京較正済みのパラメータをそのまま使い、休眠打破日→予測開花日を求める。"""
    dormancy_breaks = {}
    predictions = {}
    for year in years:
        chill_start = f"{year - 1}-{CHILL_START_MONTH_DAY}"
        search_end = f"{year}-04-30"
        dormancy_break = find_dormancy_break_date(
            daily_data, chill_start, required_chill_days, CHILL_THRESHOLD, search_end,
        )
        dormancy_breaks[year] = dormancy_break
        if dormancy_break is None:
            predictions[year] = None
            continue
        result = predict_bloom_date(daily_data, dormancy_break, dts_threshold)
        predictions[year] = result.get("bloom_date")
    return dormancy_breaks, predictions


def _days_diff(d1, d2):
    return (date.fromisoformat(d1) - date.fromisoformat(d2)).days


def main():
    print("東京(靖国神社)の気象データを取得し、較正済みパラメータを再現中...")
    tokyo_data = fetch_daily_weather(TOKYO_LAT, TOKYO_LON, DATA_START, DATA_END)
    tokyo_result = evaluate_candidate(tokyo_data, REQUIRED_CHILL_DAYS)
    dts_threshold = tokyo_result["mean_threshold"]
    print(f"必要チルデイ数={REQUIRED_CHILL_DAYS}日, DTS閾値={dts_threshold:.2f} "
          f"(東京での検証MAE={tokyo_result['valid_mae']:.2f}日)\n")

    print("新潟市の気象データを取得中...")
    niigata_data = fetch_daily_weather(NIIGATA_LAT, NIIGATA_LON, DATA_START, DATA_END)
    niigata_breaks, niigata_pred = apply_transplanted_model(
        niigata_data, REQUIRED_CHILL_DAYS, dts_threshold, TARGET_YEARS,
    )

    print("南魚沼市の気象データを取得中...")
    minamiuonuma_data = fetch_daily_weather(MINAMIUONUMA_LAT, MINAMIUONUMA_LON, DATA_START, DATA_END)
    minamiuonuma_breaks, minamiuonuma_pred = apply_transplanted_model(
        minamiuonuma_data, REQUIRED_CHILL_DAYS, dts_threshold, TARGET_YEARS,
    )

    print("\n新潟市: 東京較正パラメータそのままでの予測 vs 実測(気象庁公式)")
    print(f"{'年':>6} {'休眠打破日':>12} {'実測開花日':>12} {'予測開花日':>12} {'誤差(日)':>10} "
          f"{'南魚沼予測':>12} {'新潟との差(日)':>14}")
    for year in TARGET_YEARS:
        break_date = niigata_breaks[year] or "-"
        actual = NIIGATA_ACTUAL_BLOOM_DATES[year]
        pred = niigata_pred[year] or "-"
        error = f"{_days_diff(pred, actual):+d}" if niigata_pred[year] else "-"
        mu_pred = minamiuonuma_pred[year] or "-"
        mu_diff = f"{_days_diff(mu_pred, pred):+d}" if niigata_pred[year] and minamiuonuma_pred[year] else "-"
        print(f"{year:>6} {break_date:>12} {actual:>12} {pred:>12} {error:>10} {mu_pred:>12} {mu_diff:>14}")

    predictable_years = [y for y in TARGET_YEARS if niigata_pred[y]]
    unpredictable_years = [y for y in TARGET_YEARS if not niigata_pred[y]]
    transplant_mae = _mae(
        [niigata_pred[y] for y in predictable_years],
        [NIIGATA_ACTUAL_BLOOM_DATES[y] for y in predictable_years],
    )
    print(f"\n新潟市への移植誤差(MAE): {transplant_mae:.2f}日 "
          f"(東京自身での検証MAE {tokyo_result['valid_mae']:.2f}日 の"
          f" {transplant_mae / tokyo_result['valid_mae']:.1f}倍)")
    if unpredictable_years:
        print(f"休眠打破が判定不能だった年: {unpredictable_years}")

    both_predictable = [y for y in TARGET_YEARS if niigata_pred[y] and minamiuonuma_pred[y]]
    offsets = [_days_diff(minamiuonuma_pred[y], niigata_pred[y]) for y in both_predictable]
    avg_offset = sum(offsets) / len(offsets)
    print(f"\n南魚沼市の予測開花日は、新潟市の予測より平均{avg_offset:+.1f}日"
          f"({'遅い' if avg_offset > 0 else '早い'})"
          f"(実測なし、検証不可。標高差・内陸性による傾向の参考値)")

    OUTPUT_DIR.mkdir(exist_ok=True)
    chart_path = OUTPUT_DIR / "transplant_comparison.png"
    plot_transplant_comparison(
        TARGET_YEARS, NIIGATA_ACTUAL_BLOOM_DATES, niigata_pred, minamiuonuma_pred, chart_path,
    )
    print(f"\n比較グラフを保存: {chart_path}")


if __name__ == "__main__":
    main()
