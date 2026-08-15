# 公式API練習: TheSportsDBからNHL(アイスホッケー)のチーム一覧を取得する
#
# 無料テスト用キー「123」を使用(TheSportsDB公式ドキュメントに記載されている値)。
# 無料枠の制約: 30リクエスト/分、アプリストア公開不可、再配布不可、スクレイピング禁止。
# 参照: https://www.thesportsdb.com/documentation
#       https://www.thesportsdb.com/docs_terms_of_use.php

import requests

API_KEY = "123"
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"


def fetch_teams_by_league(league_name):
    """指定したリーグ名に所属するチーム一覧を辞書のリストとして取得する"""
    response = requests.get(
        f"{BASE_URL}/search_all_teams.php",
        params={"l": league_name},
        timeout=10,
    )
    response.raise_for_status()  # 200以外のステータスなら例外を発生させる
    data = response.json()

    teams = data.get("teams") or []  # 該当なしの場合、teamsがnullで返ってくる
    return [
        {
            "name": team["strTeam"],
            "formed_year": team["intFormedYear"],
            "stadium": team["strStadium"],
            "location": team["strLocation"],
        }
        for team in teams
    ]


def main():
    teams = fetch_teams_by_league("NHL")

    print(f"NHL: {len(teams)}チーム取得")
    for team in teams[:5]:
        print(f"{team['formed_year']}年設立 {team['name']} (本拠地: {team['location']})")


if __name__ == "__main__":
    main()
