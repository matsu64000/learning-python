# 積算気温による稲(コシヒカリ)の収穫適期予測
#
# 【スコープ・設計判断】
#   対象品種: コシヒカリ(中生品種)を前提とする。他品種への係数調整は非対応
#   移植(田植え)日: プログラムへの入力値。実際の田植え日をそのまま渡す想定
#   出穂日: プログラムへの入力値(実測 or 地域の栽培暦の目安)。移植日から出穂日
#     までの日数・積算気温で出穂日そのものを予測するモデルは、必要な基準温度や
#     係数が品種・地域・移植/直播の別でばらつきが大きく確立した単純な式が
#     見当たらなかったため、今回は対象外(既知の出穂日を前提とする)
#   出穂日→収穫適期(成熟期): 出穂後の日平均気温をそのまま(基準温度を引かずに)
#     積算し、約1000℃に達した日を成熟期(刈取り適期の目安)とする。これは
#     農研機構(naro.go.jp)や複数の県農業普及センターの資料で示されている
#     中生品種の代表的な目安(実際には品種により950〜1050℃程度で幅がある)
#   気温データ: 日平均気温(temperature_2m_mean)をそのまま使う。生育限界温度
#     (例: 10℃)を下回った日を積算から除外する「有効積算温度」の考え方は、
#     出穂後の生育期(初夏〜秋)では下回る日がほとんど無いため今回は簡略化して
#     省略(積算気温そのものを使う)
#
# 【COBOL/FORTRANとの対比】
#   累積処理は古いプログラムと同じ「PERFORM UNTIL 累計 >= 目標値」の構造。
#   違いは、Pythonではリストを走査してタプルのlistを返せるので、途中経過
#   (何月何日時点で何度まで積み上がっていたか)を丸ごと保持したまま返せること。
#   FORTRANで同じことをすると、途中経過を残すには配列を別途用意する必要があった。

from datetime import date


def _parse_date(date_str):
    return date.fromisoformat(date_str)


def cumulative_temperature(daily_data, start_date, base_temp=0.0):
    """start_date(を含む)以降の日平均気温を、start_dateからの経過日数とともに積算する。

    引数:
      daily_data: fetch_weather.fetch_daily_weatherが返す形式のlist
                  (date昇順であることを前提とする)
      start_date: "YYYY-MM-DD"。この日を1日目として積算を開始する
      base_temp:  基準温度。日平均気温からこの値を引いた分だけ積算する
                  (有効積算温度の考え方。既定0.0なら気温をそのまま積算)

    返り値: [{"date":..., "daily_value": 当日の(気温-base_temp), "cumulative": 累計}, ...]
      start_date より前の日は含めない。
    """
    start = _parse_date(start_date)
    result = []
    cumulative = 0.0
    for row in daily_data:
        if _parse_date(row["date"]) < start:
            continue
        daily_value = row["temp_mean"] - base_temp
        cumulative += daily_value
        result.append({"date": row["date"], "daily_value": daily_value, "cumulative": cumulative})
    return result


def predict_maturity(daily_data, heading_date, threshold_c=1000.0):
    """出穂日からの積算気温をもとに、成熟期(収穫適期)を予測する。

    返り値:
      {"status": "matured", "maturity_date": "YYYY-MM-DD",
       "days_after_heading": int, "cumulative_at_maturity": float}
        - データの範囲内で閾値に到達した場合
      {"status": "not_yet_matured", "cumulative_so_far": float,
       "last_date": "YYYY-MM-DD"}
        - データの終端まで到達しても閾値に届かなかった場合(進行中のシーズンなど)
    """
    series = cumulative_temperature(daily_data, heading_date, base_temp=0.0)
    if not series:
        raise ValueError(f"出穂日({heading_date})以降のデータがありません")

    heading = _parse_date(heading_date)
    for row in series:
        if row["cumulative"] >= threshold_c:
            days_after = (_parse_date(row["date"]) - heading).days
            return {
                "status": "matured",
                "maturity_date": row["date"],
                "days_after_heading": days_after,
                "cumulative_at_maturity": row["cumulative"],
            }

    return {
        "status": "not_yet_matured",
        "cumulative_so_far": series[-1]["cumulative"],
        "last_date": series[-1]["date"],
    }


def main():
    # 動作確認用のダミーデータ(出穂後、日平均25℃が続けば40日で1000℃に到達する)
    daily_data = [
        {"date": f"2025-08-{day:02d}", "temp_max": 30.0, "temp_min": 20.0,
         "temp_mean": 25.0, "precipitation": 0.0}
        for day in range(1, 32)
    ] + [
        {"date": f"2025-09-{day:02d}", "temp_max": 28.0, "temp_min": 18.0,
         "temp_mean": 25.0, "precipitation": 0.0}
        for day in range(1, 15)
    ]
    result = predict_maturity(daily_data, heading_date="2025-08-01", threshold_c=1000.0)
    print(result)


if __name__ == "__main__":
    main()
