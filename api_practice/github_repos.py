# 公式API練習: GitHub APIで自分のリポジトリ一覧を取得する(認証なし)
#
# GitHub APIは未認証でも使えるが、レート制限は60リクエスト/時間(認証すれば5,000/時間)。
# 参照: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

import requests

BASE_URL = "https://api.github.com"


def fetch_repos(username):
    """指定したユーザーの公開リポジトリ一覧を辞書のリストとして取得する"""
    response = requests.get(f"{BASE_URL}/users/{username}/repos", timeout=10)
    response.raise_for_status()  # 200以外のステータスなら例外を発生させる
    repos = response.json()

    return [
        {
            "name": repo["name"],
            "description": repo["description"],
            "default_branch": repo["default_branch"],
            "private": repo["private"],
        }
        for repo in repos
    ]


def main():
    username = "matsu64000"
    repos = fetch_repos(username)

    print(f"{username}の公開リポジトリ: {len(repos)}件")
    for repo in repos:
        visibility = "private" if repo["private"] else "public"
        print(f"- {repo['name']} ({visibility}, branch: {repo['default_branch']})")


if __name__ == "__main__":
    main()
