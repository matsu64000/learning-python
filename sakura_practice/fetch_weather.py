# weather_practice/fetch_weather.pyと同じ実装。プロジェクト内の各practiceフォルダを
# 独立させる方針(tennis_stats/resident_tax_practice/triangle_practice等と同じ)に
# 合わせて、ここにも複製している。詳しいAPIの説明はweather_practice側のコメント参照。

import requests

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
]


def fetch_daily_weather(latitude, longitude, start_date, end_date, timezone="Asia/Tokyo"):
    """指定した地点・期間の日次気象データを取得する。返り値の形はweather_practiceと同じ。"""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": timezone,
    }
    response = requests.get(ARCHIVE_API_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if payload.get("error"):
        raise ValueError(f"Open-Meteo APIがエラーを返しました: {payload.get('reason')}")

    daily = payload["daily"]
    return [
        {
            "date": date, "temp_max": temp_max, "temp_min": temp_min,
            "temp_mean": temp_mean, "precipitation": precipitation,
        }
        for date, temp_max, temp_min, temp_mean, precipitation in zip(
            daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"],
            daily["temperature_2m_mean"], daily["precipitation_sum"],
        )
    ]
