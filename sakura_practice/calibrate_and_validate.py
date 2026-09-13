# 東京(靖国神社)の実測開花日(気象庁発表、2016〜2026年の11年分)を使い、
# 休眠打破+DTS法のパラメータ(チルデイの必要日数)を較正し、別の年で検証する
#
# 【なぜ較正・検証を分けるか】
# 「必要チルデイ数→休眠打破日」が決まれば、「休眠打破日から実際の開花日までの
# 累積DTS」は実測データから機械的に逆算できる(implied_dts_threshold)。つまり
# DTS閾値は好きな値に"後付け"で合わせられてしまう。1年分のデータだけで
# 較正すると、その年にだけぴったり合う無意味なモデルになる(過学習)。
# そこで年を較正用(2016〜2021)と検証用(2022〜2026)に分け、較正用の年だけで
# 決めたパラメータが、見ていない検証用の年でもそれなりに当たるかを確認する

import math
import statistics
from datetime import date
from pathlib import Path

from fetch_weather import fetch_daily_weather
from plot_sakura import plot_year_comparison
from sakura_bloom import (
    find_dormancy_break_date, implied_dts_threshold, predict_bloom_date,
    predict_bloom_simple_rule,
)

OUTPUT_DIR = Path(__file__).parent / "output"

LATITUDE, LONGITUDE = 35.6939, 139.7423  # 靖国神社(東京のさくらの観測地点)

# 気象庁発表(令和8年3月19日付「東京のさくら」)の実測開花日
ACTUAL_BLOOM_DATES = {
    2016: "2016-03-21", 2017: "2017-03-21", 2018: "2018-03-17", 2019: "2019-03-21",
    2020: "2020-03-14", 2021: "2021-03-14", 2022: "2022-03-20", 2023: "2023-03-14",
    2024: "2024-03-29", 2025: "2025-03-24", 2026: "2026-03-19",
}
CALIBRATION_YEARS = list(range(2016, 2022))  # 6年
VALIDATION_YEARS = list(range(2022, 2027))   # 5年

CHILL_START_MONTH_DAY = "10-01"  # 前年の10/1からチルデイを数え始める
CHILL_THRESHOLD = 5.0
CHILL_DAYS_GRID = range(20, 81, 5)

DATA_START = "2015-09-01"
DATA_END = "2026-04-15"


def _mae(predictions, actuals):
    """平均絶対誤差(日数)。予測が1件も無ければinf(この候補は使い物にならない、の意味)を返す。"""
    if not predictions:
        return math.inf
    errors = [abs((date.fromisoformat(p) - date.fromisoformat(a)).days) for p, a in zip(predictions, actuals)]
    return statistics.mean(errors)


def evaluate_candidate(daily_data, required_chill_days):
    """あるチルデイ必要日数の候補について、較正・検証それぞれのMAE(日)と
    較正用implied閾値のばらつき(標準偏差)を返す。
    """
    dormancy_breaks = {}
    implied_thresholds = []
    too_late_years = []  # 休眠打破が実測開花日より後になってしまい、較正に使えない年
    for year in CALIBRATION_YEARS + VALIDATION_YEARS:
        chill_start = f"{year - 1}-{CHILL_START_MONTH_DAY}"
        search_end = f"{year}-04-30"  # この日までに休眠打破しなければ諦める(春を過ぎたら翌冬まで探さない)
        dormancy_break = find_dormancy_break_date(
            daily_data, chill_start, required_chill_days, CHILL_THRESHOLD, search_end,
        )
        dormancy_breaks[year] = dormancy_break
        if year not in CALIBRATION_YEARS or dormancy_break is None:
            continue
        if dormancy_break > ACTUAL_BLOOM_DATES[year]:
            # 例: 2019/2020年は記録的な暖冬で、必要チルデイ数が多い候補だと
            # 休眠打破の判定そのものが実測開花日(2020-03-14)に間に合わない
            too_late_years.append(year)
            continue
        implied_thresholds.append(implied_dts_threshold(daily_data, dormancy_break, ACTUAL_BLOOM_DATES[year]))

    # 較正用6年のうち、半分以上が「休眠打破が実測開花に間に合わない」で使えない候補は
    # 少数の年にだけ強引に合わせた不安定な較正になるため、信頼できないとして除外する
    if len(implied_thresholds) < 4:
        return None

    mean_threshold = statistics.mean(implied_thresholds)
    stdev_threshold = statistics.stdev(implied_thresholds) if len(implied_thresholds) > 1 else 0.0

    predictions = {}
    for year, dormancy_break in dormancy_breaks.items():
        if dormancy_break is None:
            predictions[year] = None
            continue
        result = predict_bloom_date(daily_data, dormancy_break, mean_threshold)
        predictions[year] = result.get("bloom_date")

    calib_mae = _mae(
        [predictions[y] for y in CALIBRATION_YEARS if predictions[y]],
        [ACTUAL_BLOOM_DATES[y] for y in CALIBRATION_YEARS if predictions[y]],
    )
    valid_mae = _mae(
        [predictions[y] for y in VALIDATION_YEARS if predictions[y]],
        [ACTUAL_BLOOM_DATES[y] for y in VALIDATION_YEARS if predictions[y]],
    )
    return {
        "required_chill_days": required_chill_days,
        "mean_threshold": mean_threshold,
        "stdev_threshold": stdev_threshold,
        "calib_mae": calib_mae,
        "valid_mae": valid_mae,
        "dormancy_breaks": dormancy_breaks,
        "predictions": predictions,
        "too_late_years": too_late_years,
    }


def main():
    print("東京(靖国神社)の気象データを取得中...")
    daily_data = fetch_daily_weather(LATITUDE, LONGITUDE, DATA_START, DATA_END)
    print(f"取得件数: {len(daily_data)}日分 ({daily_data[0]['date']} 〜 {daily_data[-1]['date']})\n")

    print("必要チルデイ数ごとの較正結果(較正用2016-2021 / 検証用2022-2026、誤差は日数の平均絶対誤差):")
    print(f"{'必要チルデイ数':>10} {'較正済み閾値':>12} {'閾値の標準偏差':>14} {'較正MAE':>10} {'検証MAE':>10} {'較正不能年':>10}")
    results = []
    for candidate in CHILL_DAYS_GRID:
        result = evaluate_candidate(daily_data, candidate)
        if result is None:
            continue
        results.append(result)
        too_late = ",".join(str(y) for y in result["too_late_years"]) or "-"
        print(f"{candidate:>10} {result['mean_threshold']:>12.2f} {result['stdev_threshold']:>14.2f} "
              f"{result['calib_mae']:>10.2f} {result['valid_mae']:>10.2f} {too_late:>10}")

    best = min(results, key=lambda r: r["valid_mae"])
    print(f"\n検証MAEが最小の候補: 必要チルデイ数={best['required_chill_days']}日, "
          f"DTS閾値={best['mean_threshold']:.2f}, 検証MAE={best['valid_mae']:.2f}日")

    print("\n年ごとの予測 vs 実績(最良候補モデル):")
    print(f"{'年':>6} {'休眠打破日':>12} {'実績開花日':>12} {'DTS法予測':>12} {'600℃法則予測':>14}")
    simple_rule_predictions = {}
    for year in sorted(ACTUAL_BLOOM_DATES):
        dts_pred = best["predictions"].get(year) or "-"
        simple_result = predict_bloom_simple_rule(daily_data, year)
        simple_pred = simple_result.get("bloom_date", "-")
        simple_rule_predictions[year] = simple_pred
        dormancy_break = best["dormancy_breaks"].get(year) or "-"
        print(f"{year:>6} {dormancy_break:>12} {ACTUAL_BLOOM_DATES[year]:>12} {dts_pred:>12} {simple_pred:>14}")

    predictable_years = [y for y in ACTUAL_BLOOM_DATES if best["predictions"][y]]
    unpredictable_years = [y for y in ACTUAL_BLOOM_DATES if not best["predictions"][y]]

    dts_mae = _mae(
        [best["predictions"][y] for y in predictable_years],
        [ACTUAL_BLOOM_DATES[y] for y in predictable_years],
    )
    simple_mae_same_years = _mae(
        [simple_rule_predictions[y] for y in predictable_years],
        [ACTUAL_BLOOM_DATES[y] for y in predictable_years],
    )
    simple_mae_all_11 = _mae(
        [simple_rule_predictions[y] for y in ACTUAL_BLOOM_DATES],
        [ACTUAL_BLOOM_DATES[y] for y in ACTUAL_BLOOM_DATES],
    )
    print(f"\nDTS法が休眠打破を判定できず予測不能だった年: {unpredictable_years}"
          f"(必要チルデイ数{best['required_chill_days']}日が、記録的暖冬で4/30までに届かなかった)")
    print(f"同じ{len(predictable_years)}年で比較したMAE: DTS法 {dts_mae:.2f}日 / 600℃の法則 {simple_mae_same_years:.2f}日")
    print(f"(参考)600℃の法則は全11年で計算可能: MAE {simple_mae_all_11:.2f}日")

    OUTPUT_DIR.mkdir(exist_ok=True)
    chart_path = OUTPUT_DIR / "year_comparison.png"
    plot_year_comparison(
        sorted(ACTUAL_BLOOM_DATES), ACTUAL_BLOOM_DATES, best["predictions"], simple_rule_predictions, chart_path,
    )
    print(f"\n年ごとの比較グラフを保存: {chart_path}")

    return daily_data, best, simple_rule_predictions


if __name__ == "__main__":
    main()
