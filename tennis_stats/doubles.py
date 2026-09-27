# ダブルスの対戦カード自動生成・個人単位の集計
#
# 【設計方針】
# - 対戦のたびにパートナー・対戦相手が変わるダブルスの回り持ちを、乱数で決める。
#   「試合数が一番少ない4人が優先的にプレーする」(公平にプレー機会を回す)、
#   「直前の対戦とは同じ組み合わせにならない」の2つを満たすようにする
# - 個人単位の集計は、既存のtennis_stats.win_rate/game_win_rateをそのまま使う。
#   1回戦を「チームA視点の記録」1件として保存し、そこから各プレイヤー視点の
#   {"opponent":..., "sets":...} 形式に変換し直すことで、シングルス用に作った
#   集計ロジックを一切変更せずに個人成績を出せる(8/09の「判定・集計ロジックは
#   入力元非依存」という原則を、チーム戦にも広げた形)
#
# 【乱数のテスト容易性】乱数を使う関数はすべて rng 引数(既定値は random モジュール)
# を受け取る設計にした。テストからは random.Random(seed) を渡すことで、
# 挙動を固定して検証できる(cumulative_series が集計関数を外から渡せるようにした
# のと同じ「差し替え可能にする」設計)

import random

from tennis_stats import game_win_rate, win_rate


def matches_played_count(players, history):
    """各プレイヤーのこれまでの対戦数(休みを除く)を数える。"""
    counts = {p: 0 for p in players}
    for round_ in history:
        for p in round_["team_a"] + round_["team_b"]:
            counts[p] += 1
    return counts


def select_players_for_round(players, history, rng=random):
    """今回プレーする4人を選ぶ。

    これまでの対戦数が少ない人を優先的に選ぶ(=対戦数が多い人から休みになる)。
    対戦数が同じ人が複数いる場合は、その中からランダムに選ぶ
    (先に全体をシャッフルしてから対戦数で安定ソートすることで実現している。
    Pythonのsortは安定ソートなので、同じキーの要素はシャッフル後の順序のまま残る)
    """
    counts = matches_played_count(players, history)
    shuffled = list(players)
    rng.shuffle(shuffled)
    ranked = sorted(shuffled, key=lambda p: counts[p])
    return ranked[:4]


def _partitions_of_four(four_players):
    """4人を2人ずつの2チームに分ける3通りの組み合わせを返す。

    各要素は (チームの2人の組, もう一方のチームの2人の組) の
    frozenset のペア。順序や表記ゆれを気にせず「同じ組み合わせか」を
    比較できるようにするため、tupleではなくfrozensetを使う
    """
    a, b, c, d = four_players
    return [
        (frozenset((a, b)), frozenset((c, d))),
        (frozenset((a, c)), frozenset((b, d))),
        (frozenset((a, d)), frozenset((b, c))),
    ]


def generate_matchup(players, history, rng=random):
    """次のダブルス対戦カードを1つ決める。

    戻り値: {"team_a": (name, name), "team_b": (name, name), "resting": [name, ...]}
    (team_a/team_bの2人は表示上安定するよう名前順に並べる。どちらがteam_a/team_bに
    なるかは意味を持たないラベルにすぎない)
    """
    if len(players) < 4:
        raise ValueError("ダブルスには4人以上のプレイヤーが必要です")

    chosen = select_players_for_round(players, history, rng=rng)
    resting = sorted(p for p in players if p not in chosen)

    candidates = _partitions_of_four(chosen)
    if history:
        previous = history[-1]
        previous_partition = {frozenset(previous["team_a"]), frozenset(previous["team_b"])}
        narrowed = [c for c in candidates if {c[0], c[1]} != previous_partition]
        # chosenの4人が前回と全く同じ場合のみ候補が減る。1人でも入れ替わっていれば
        # 3通り全てが「前回と別の組み合わせ」になるので、narrowedは空にならない
        if narrowed:
            candidates = narrowed

    team_a_set, team_b_set = rng.choice(candidates)
    return {
        "team_a": tuple(sorted(team_a_set)),
        "team_b": tuple(sorted(team_b_set)),
        "resting": resting,
    }


def player_matches(player, history):
    """指定したプレイヤーの視点で、win_rate/game_win_rateがそのまま使える
    {"opponent": ..., "sets": [...]} 形式のlistに変換する。

    チームBの選手の場合、setsの(own, opp)を(opp, own)に入れ替えて、
    「自分たちのチーム視点」に揃え直す
    """
    result = []
    for round_ in history:
        if player in round_["team_a"]:
            opponents = round_["team_b"]
            sets = round_["sets"]
        elif player in round_["team_b"]:
            opponents = round_["team_a"]
            sets = [(opp, own) for own, opp in round_["sets"]]
        else:
            continue  # この回は休み
        result.append({"opponent": "・".join(opponents), "sets": sets})
    return result


def player_summary(players, history):
    """全プレイヤーの個人成績(対戦数・勝率・ゲーム獲得率)をまとめる。"""
    summary = {}
    for p in players:
        matches = player_matches(p, history)
        summary[p] = {
            "matches_played": len(matches),
            "win_rate": win_rate(matches),
            "game_win_rate": game_win_rate(matches),
        }
    return summary
