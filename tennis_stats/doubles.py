# ダブルスの対戦カード自動生成・個人単位の集計
#
# 【設計方針】
# - 対戦のたびにパートナー・対戦相手が変わるダブルスの回り持ちを、乱数で決める。
#   次の優先順位で「なるべく公平な」組み合わせを選ぶ(2026-10-03に強化):
#     1. 試合数が少ない人を必ず優先して出す(誰もがほぼ同じ試合数になる)
#     2. その範囲で、これまでに組んだことのあるペアの繰り返しを避ける
#     3. さらに、これまでに対戦したことのある相手との繰り返しを避ける
#     4. 同点なら、過去にまったく同じ対戦カードが出た回数が少ないものを選ぶ
#     5. さらに同点なら、そのカードが最後に出たのがより昔のものを選ぶ
#        (直前の試合と同じカードが続くのを避ける。4・5は2026-10-03追加)
#   それでも同点の候補が複数あれば、その中からランダムに選ぶ
#   (9/27版は「直前の1試合と同じ組み合わせだけ避ける」だったが、
#    全試合を通じた回数を数える方式に変えた)
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
from collections import Counter
from itertools import combinations

from tennis_stats import game_win_rate, match_result, set_counts, win_rate


def matches_played_count(players, history):
    """各プレイヤーのこれまでの対戦数(休みを除く)を数える。"""
    counts = {p: 0 for p in players}
    for round_ in history:
        for p in round_["team_a"] + round_["team_b"]:
            counts[p] += 1
    return counts


def candidate_groups(players, history):
    """今回プレーする4人の候補(試合数の少ない人を優先した組)をすべて返す。

    例: 試合数が A=1,B=1,C=1,D=2,E=2,F=2 なら、A・B・Cは必ず出て、
    残り1人をD・E・Fから選ぶ → 候補は {A,B,C,D} {A,B,C,E} {A,B,C,F} の3通り。
    どの1人を選ぶかは、ペア・対戦相手の重複が少なくなるかで後から決める
    """
    counts = matches_played_count(players, history)
    threshold = sorted(counts.values())[3]  # 4番目に少ない試合数
    must_play = [p for p in players if counts[p] < threshold]
    tied = [p for p in players if counts[p] == threshold]
    need = 4 - len(must_play)
    return [must_play + list(extra) for extra in combinations(tied, need)]


def pair_counts(history):
    """これまでに同じチームで組んだ回数を、2人の組(frozenset)ごとに数える"""
    counter = Counter()
    for round_ in history:
        counter[frozenset(round_["team_a"])] += 1
        counter[frozenset(round_["team_b"])] += 1
    return counter


def opponent_counts(history):
    """これまでに対戦相手になった回数を、2人の組(frozenset)ごとに数える"""
    counter = Counter()
    for round_ in history:
        for a in round_["team_a"]:
            for b in round_["team_b"]:
                counter[frozenset((a, b))] += 1
    return counter


def card_key(team_a, team_b):
    """対戦カード(2チームの組)を、チームの順序や2人の並び順に関係なく比較できる形にする"""
    return frozenset((frozenset(team_a), frozenset(team_b)))


def card_history(history):
    """対戦カードごとに (これまでに出た回数, 最後に出た試合の番号) を返す"""
    stats = {}
    for i, round_ in enumerate(history):
        key = card_key(round_["team_a"], round_["team_b"])
        count, _ = stats.get(key, (0, -1))
        stats[key] = (count + 1, i)
    return stats


def matchup_cost(team_a, team_b, pairs, opponents, cards=None):
    """組み合わせの「重複の多さ」をタプルで返す:
    (ペアの重複回数, 対戦相手の重複回数, 同じカードが出た回数, そのカードが最後に出た試合番号)

    タプルの大小比較は先頭の要素から順に比べる(辞書順)ので、
    min()で選ぶと「ペアの重複が少ないこと」が優先され、ペアが同点のときだけ
    対戦相手の重複で比べる…という優先順位を、タプルの並び順で表現している。
    最後の要素は、一度も出ていないカードなら-1、出ていれば番号が大きい(最近)ほど不利
    """
    pair_repeat = pairs[frozenset(team_a)] + pairs[frozenset(team_b)]
    opponent_repeat = sum(opponents[frozenset((a, b))] for a in team_a for b in team_b)
    card_count, last_seen = (cards or {}).get(card_key(team_a, team_b), (0, -1))
    return (pair_repeat, opponent_repeat, card_count, last_seen)


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

    1. candidate_groupsで試合数の少ない人を優先した4人組の候補を作る
    2. 各候補について2チームへの分け方3通りを並べ、matchup_costで重複の多さを計算
    3. 重複が最も少ない組み合わせの中からランダムに1つ選ぶ

    戻り値: {"team_a": (name, name), "team_b": (name, name), "resting": [name, ...]}
    (team_a/team_bの2人は表示上安定するよう名前順に並べる。どちらがteam_a/team_bに
    なるかは意味を持たないラベルにすぎない)
    """
    if len(players) < 4:
        raise ValueError("ダブルスには4人以上のプレイヤーが必要です")

    pairs = pair_counts(history)
    opponents = opponent_counts(history)
    cards = card_history(history)

    scored = []
    for group in candidate_groups(players, history):
        for team_a, team_b in _partitions_of_four(group):
            scored.append((matchup_cost(team_a, team_b, pairs, opponents, cards), team_a, team_b))

    best_cost = min(cost for cost, _, _ in scored)
    best = [(a, b) for cost, a, b in scored if cost == best_cost]
    team_a_set, team_b_set = rng.choice(best)

    playing = team_a_set | team_b_set
    return {
        "team_a": tuple(sorted(team_a_set)),
        "team_b": tuple(sorted(team_b_set)),
        "resting": sorted(p for p in players if p not in playing),
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
    """全プレイヤーの個人成績(対戦数・勝敗・得失セット・勝率・ゲーム獲得率)をまとめる。

    勝敗(match_result)や得失セット(set_counts)も、シングルス用の関数に
    個人視点へ変換した試合を渡すだけで求めている
    """
    summary = {}
    for p in players:
        matches = player_matches(p, history)
        results = Counter(match_result(m) for m in matches)
        sets_won = sum(set_counts(m)[0] for m in matches)
        sets_lost = sum(set_counts(m)[1] for m in matches)
        summary[p] = {
            "matches_played": len(matches),
            "wins": results["win"],
            "losses": results["loss"],
            "draws": results["draw"],
            "sets_won": sets_won,
            "sets_lost": sets_lost,
            "set_diff": sets_won - sets_lost,
            "win_rate": win_rate(matches),
            "game_win_rate": game_win_rate(matches),
        }
    return summary
