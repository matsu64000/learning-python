# Webスクレイピング練習: scrapethissite.com のホッケーチーム成績表を取得する
#
# 対象サイトは「スクレイピング練習用」に公開されているサンドボックスなので、
# 練習で取得すること自体は問題ない(参照: https://www.scrapethissite.com/pages/forms/)。

import time

import requests
from bs4 import BeautifulSoup

URL = "https://www.scrapethissite.com/pages/forms/"
REQUEST_INTERVAL_SECONDS = 0.5  # 練習用サイトとはいえ連続アクセスは間隔を空けるのが礼儀


def fetch_html(url):
    """指定したURLのHTMLを文字列として取得する"""
    response = requests.get(url, timeout=10)
    response.raise_for_status()  # 200以外のステータスなら例外を発生させる
    return response.text


def parse_teams(html):
    """HTMLから1チーム1シーズン分の成績を辞書のリストとして取り出す"""
    soup = BeautifulSoup(html, "html.parser")
    teams = []

    for row in soup.select("tr.team"):
        teams.append({
            "name": row.select_one(".name").get_text(strip=True),
            "year": row.select_one(".year").get_text(strip=True),
            "wins": row.select_one(".wins").get_text(strip=True),
            "losses": row.select_one(".losses").get_text(strip=True),
        })

    return teams


def fetch_all_teams():
    """空ページに行き着くまでpage_numを1から増やして全ページ分を集める"""
    teams = []
    page_num = 1

    while True:
        html = fetch_html(f"{URL}?page_num={page_num}")
        page_teams = parse_teams(html)
        if not page_teams:
            break

        teams.extend(page_teams)
        print(f"{page_num}ページ目: {len(page_teams)}チーム取得")
        page_num += 1
        time.sleep(REQUEST_INTERVAL_SECONDS)

    return teams


def main():
    teams = fetch_all_teams()

    print(f"\n合計{len(teams)}チーム分のデータを取得しました")
    for team in teams[:5]:
        print(f"{team['year']}年 {team['name']}: {team['wins']}勝{team['losses']}敗")


if __name__ == "__main__":
    main()
