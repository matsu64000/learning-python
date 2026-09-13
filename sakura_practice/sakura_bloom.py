# 桜(ソメイヨシノ)の開花予想: 休眠打破(チルデイ) + DTS法(温度変換日数)
#
# 【rice_growth.py(積算気温1本のモデル)との構造的な違い】
#   米のモデルは「出穂日(入力値)→積算気温→閾値到達で成熟」という1段階の
#   線形モデルだった。桜のモデルは2段階:
#     フェーズ1 休眠打破: 秋以降、日平均気温が一定以下(チル閾値)の日を
#       「チルデイ」として数え、必要日数に達した日を休眠打破日とする
#       (COBOL対比: PERFORM UNTIL 該当日数カウント >= 必要日数)
#     フェーズ2 発育(DTS法): 休眠打破日以降、日平均気温をDTS(温度変換日数)
#       という指数関数(アレニウス型反応速度式と同じ形)で変換した値を積算し、
#       閾値に達した日を開花日とする
#         DTS = exp(9500*(t-288.2)/(t*288.2))  (tは日平均気温を絶対温度[K]にした値)
#   フェーズ1の結果(休眠打破日)がフェーズ2の起算日になる、という「前段の出力が
#   後段の入力になる」パイプライン構造が、単純な1段階積算とは質的に違う
#
# 【パラメータの扱い】
#   チルデイの必要日数・チル閾値・DTS閾値は、本来は観測地点ごとに実測データへ
#   厳密に較正されるべきパラメータ(青野靖之・小元敬男 1990年の研究等に基づく)。
#   この学習用実装では、気象庁が公表している東京(靖国神社)の実測開花日
#   (2016〜2026年、11年分)を使い、calibrate_and_validate.pyで較正する

import math
from datetime import date


def is_chill_day(temp_mean, chill_threshold=5.0):
    """日平均気温がチル閾値以下なら、休眠打破に寄与する「チルデイ」とみなす。"""
    return temp_mean <= chill_threshold


def find_dormancy_break_date(daily_data, chill_start_date, required_chill_days, chill_threshold=5.0,
                              search_end_date=None):
    """chill_start_date以降のチルデイを数え、必要日数に達した日を返す。到達しなければNone。

    search_end_date(既定None=無制限)を指定すると、その日を過ぎても必要日数に
    達しなければNoneを返して探索を打ち切る。指定しないと、暖冬で必要日数に
    届かなかった場合に春・夏(チルデイが0の期間)を素通りして翌年の冬まで
    数え続けてしまう(暖冬の年をテストして実際に踏んだ不具合)
    """
    start = date.fromisoformat(chill_start_date)
    end = date.fromisoformat(search_end_date) if search_end_date else None
    count = 0
    for row in daily_data:
        d = date.fromisoformat(row["date"])
        if d < start:
            continue
        if end is not None and d > end:
            return None
        if is_chill_day(row["temp_mean"], chill_threshold):
            count += 1
            if count >= required_chill_days:
                return row["date"]
    return None


def dts_value(temp_mean_celsius):
    """日平均気温(摂氏)からDTS(温度変換日数)を計算する。

    t = 絶対温度(K)。288.2K(≈15.05℃)を基準に、気温が高いほど1日あたりの
    "発育の進み"が急激に大きくなる非線形の式
    """
    t = temp_mean_celsius + 273.15
    return math.exp(9500 * (t - 288.2) / (t * 288.2))


def cumulative_dts_series(daily_data, start_date):
    """start_date(を含む)以降のDTSを日付ごとに積算する。"""
    start = date.fromisoformat(start_date)
    result = []
    cumulative = 0.0
    for row in daily_data:
        if date.fromisoformat(row["date"]) < start:
            continue
        cumulative += dts_value(row["temp_mean"])
        result.append({"date": row["date"], "cumulative": cumulative})
    return result


def predict_bloom_date(daily_data, dormancy_break_date, dts_threshold):
    """休眠打破日からDTSを積算し、閾値に達した日を開花日として予測する。"""
    series = cumulative_dts_series(daily_data, dormancy_break_date)
    for row in series:
        if row["cumulative"] >= dts_threshold:
            return {"status": "bloomed", "bloom_date": row["date"], "cumulative_dts": row["cumulative"]}
    last = series[-1]["cumulative"] if series else 0.0
    return {"status": "not_yet_bloomed", "cumulative_dts": last}


def predict_bloom_full_model(daily_data, chill_start_date, required_chill_days, chill_threshold, dts_threshold,
                              search_end_date=None):
    """休眠打破日の判定から開花日予測までを一気通貫で行う(フェーズ1→フェーズ2)。"""
    dormancy_break_date = find_dormancy_break_date(
        daily_data, chill_start_date, required_chill_days, chill_threshold, search_end_date,
    )
    if dormancy_break_date is None:
        return {"status": "dormancy_not_broken"}
    result = predict_bloom_date(daily_data, dormancy_break_date, dts_threshold)
    result["dormancy_break_date"] = dormancy_break_date
    return result


def implied_dts_threshold(daily_data, dormancy_break_date, actual_bloom_date):
    """「休眠打破日から実際の開花日までの累積DTS」を返す。

    「この年、この休眠打破日なら、閾値がちょうどこの値だったら実測と一致する」
    という値。calibrate_and_validate.pyでの較正に使う
    """
    series = cumulative_dts_series(daily_data, dormancy_break_date)
    for row in series:
        if row["date"] == actual_bloom_date:
            return row["cumulative"]
    raise ValueError(f"実測開花日({actual_bloom_date})のデータが見つかりません")


def predict_bloom_simple_rule(daily_data, year, threshold=600.0, temp_field="temp_max",
                               start_month_day="02-01"):
    """比較用の古典的な経験則(既定は「600℃の法則」: 2/1から日最高気温を積算)。

    休眠打破のモデリングを一切せず、毎年決まった日(2/1)から積算を始める点が
    DTS法との最大の違い(すでに休眠打破済みという前提を暗黙に置いている)
    """
    start = date.fromisoformat(f"{year}-{start_month_day}")
    cumulative = 0.0
    for row in daily_data:
        d = date.fromisoformat(row["date"])
        if d < start or d.year != year:
            continue
        cumulative += row[temp_field]
        if cumulative >= threshold:
            return {"status": "bloomed", "bloom_date": row["date"], "cumulative": cumulative}
    return {"status": "not_yet_bloomed", "cumulative": cumulative}
