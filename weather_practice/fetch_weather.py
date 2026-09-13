# 外部気象データの取得(Open-Meteo Historical Weather API)
#
# 【データソースについて】
# 気象庁の実測アメダスデータ(大昔のFORTRANプログラムで使っていたのと同じもの)も
# 検討したが、正式に文書化された「API」ではなく、地点コード・要素コードを組んだ
# 複雑なPOSTパラメータをブラウザの画面遷移から逆算する必要がある、非公式に近い
# 呼び出し方式(scraping_practice/hockey_stats.pyと同系統の「規約に明記されていない
# 挙動に依存する」やり方)だった。
# 今回は「APIとして使う」練習を優先し、認証不要・ドキュメント完備の
# Open-Meteo Historical Weather API (https://open-meteo.com/en/docs/historical-weather-api)
# を採用した。ただし提供されるのは実測値ではなく ERA5 再解析(モデルによる格子点推定値)
# のため、最寄りのアメダス観測点そのものの値とは多少ずれる点に注意。
#
# 【利用条件】非商用利用は認証不要・無料。1940-01-01〜当日までのデータを取得可能
# (範囲外を指定すると {"error": true, "reason": "..."} 形式のJSONが返る)。

import requests

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
]


def fetch_daily_weather(latitude, longitude, start_date, end_date, timezone="Asia/Tokyo"):
    """指定した地点・期間の日次気象データを取得する。

    引数:
      latitude, longitude: float。地点の緯度・経度
      start_date, end_date: "YYYY-MM-DD"形式の文字列(両端を含む)
      timezone: IANAタイムゾーン名。日付の区切りに使われる(日本時間の0時区切りに
                したいので既定は"Asia/Tokyo")

    返り値: 日付順の辞書のlist。各要素:
      {"date": "YYYY-MM-DD", "temp_max": float, "temp_min": float,
       "temp_mean": float, "precipitation": float}

    APIがエラーを返した場合(期間が1940-01-01〜当日の範囲外など)はValueErrorを送出。
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": timezone,
    }
    response = requests.get(ARCHIVE_API_URL, params=params, timeout=30)
    response.raise_for_status()  # HTTPレベルのエラー(5xxなど)はここで例外になる
    payload = response.json()

    if payload.get("error"):
        raise ValueError(f"Open-Meteo APIがエラーを返しました: {payload.get('reason')}")

    daily = payload["daily"]
    return [
        {
            "date": date,
            "temp_max": temp_max,
            "temp_min": temp_min,
            "temp_mean": temp_mean,
            "precipitation": precipitation,
        }
        for date, temp_max, temp_min, temp_mean, precipitation in zip(
            daily["time"],
            daily["temperature_2m_max"],
            daily["temperature_2m_min"],
            daily["temperature_2m_mean"],
            daily["precipitation_sum"],
        )
    ]


def main():
    # 南魚沼市役所の緯度経度
    latitude, longitude = 37.0655, 138.8760
    data = fetch_daily_weather(latitude, longitude, "2025-05-01", "2025-05-05")
    for row in data:
        print(row)


if __name__ == "__main__":
    main()
