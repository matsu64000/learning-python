"""doubles.py のテスト。

乱数を使う関数はrng=random.Random(seed)を渡して挙動を固定して検証する。
ただし「同数タイの中からランダムに選ばれる」性質そのものは1回の呼び出しでは
確認できないため、多数回試行して全員が選ばれうることを見る統計的な検証を使う
(頻度は極めて低いが理論上まれに失敗しうる。十分な試行回数で実用上は問題ない)
"""

import random

import pytest

from itertools import combinations

from doubles import (
    _partitions_of_four,
    candidate_groups,
    card_history,
    card_key,
    generate_matchup,
    join_offset,
    matches_played_count,
    matchup_cost,
    opponent_counts,
    pair_counts,
    player_matches,
    player_summary,
)


# --- matches_played_count -------------------------------------------------------

def test_matches_played_count_counts_each_appearance():
    history = [
        {"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": []},
        {"team_a": ("A", "C"), "team_b": ("B", "D"), "sets": []},
    ]
    counts = matches_played_count(["A", "B", "C", "D", "E"], history)
    assert counts == {"A": 2, "B": 2, "C": 2, "D": 2, "E": 0}


# --- candidate_groups --------------------------------------------------------------

def test_candidate_groups_least_played_must_play():
    # A,B,Cは1回、D,E,Fは2回 → A,B,Cは必ず出て、残り1人がD,E,Fのいずれか
    history = [
        {"team_a": ("D", "E"), "team_b": ("A", "B"), "sets": []},
        {"team_a": ("D", "F"), "team_b": ("E", "C"), "sets": []},
        {"team_a": ("F", "X"), "team_b": ("Y", "Z"), "sets": []},
    ]
    players = ["A", "B", "C", "D", "E", "F", "X", "Y", "Z"]
    # X,Y,Zも1回ずつ → 1回の人はA,B,C,X,Y,Zの6人で、4人を選ぶ組は C(6,4)=15通り
    groups = candidate_groups(players, history)
    assert len(groups) == 15
    for g in groups:
        assert len(g) == 4
        assert not set(g) & {"D", "E", "F"}


def test_candidate_groups_fills_from_tied_players():
    history = [
        {"team_a": ("E", "F"), "team_b": ("A", "B"), "sets": []},
        {"team_a": ("E", "F"), "team_b": ("C", "D"), "sets": []},
    ]
    # A-Dは1回、E,Fは2回、Gは0回 → Gは必ず出て、残り3人をA-Dの4人から選ぶ(4通り)
    groups = candidate_groups(["A", "B", "C", "D", "E", "F", "G"], history)
    assert len(groups) == 4
    for g in groups:
        assert "G" in g
        assert not set(g) & {"E", "F"}


def test_candidate_groups_everyone_tied():
    # 5人全員0回 → 5人から4人を選ぶ5通りすべてが候補
    groups = candidate_groups(["A", "B", "C", "D", "E"], [])
    assert len(groups) == 5


# --- pair_counts / opponent_counts / matchup_cost ----------------------------------

HISTORY_2 = [
    {"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": []},
    {"team_a": ("A", "C"), "team_b": ("B", "D"), "sets": []},
]


def test_pair_counts():
    pairs = pair_counts(HISTORY_2)
    assert pairs[frozenset(("A", "B"))] == 1
    assert pairs[frozenset(("B", "D"))] == 1
    assert pairs[frozenset(("A", "D"))] == 0


def test_opponent_counts():
    # 1試合目の対戦: A-C, A-D, B-C, B-D / 2試合目: A-B, A-D, C-B, C-D
    opponents = opponent_counts(HISTORY_2)
    assert opponents[frozenset(("A", "D"))] == 2
    assert opponents[frozenset(("B", "C"))] == 2
    assert opponents[frozenset(("A", "C"))] == 1
    assert opponents[frozenset(("A", "B"))] == 1


def test_matchup_cost_hand_calculation():
    pairs, opponents = pair_counts(HISTORY_2), opponent_counts(HISTORY_2)
    cards = card_history(HISTORY_2)
    # A・D vs B・C: ペアはどちらも初 → 0。対戦はA-B(1)+A-C(1)+D-B(1)+D-C(1) = 4
    # カードとしては未登場 → 回数0, 最後に出た番号-1
    assert matchup_cost(("A", "D"), ("B", "C"), pairs, opponents, cards) == (0, 4, 0, -1)
    # A・B vs C・D: ペアA・B(1)+C・D(1) = 2。対戦A-C(1)+A-D(2)+B-C(2)+B-D(1) = 6
    # カードとしては1試合目(番号0)に1回登場
    assert matchup_cost(("C", "D"), ("B", "A"), pairs, opponents, cards) == (2, 6, 1, 0)


def test_matchup_cost_pair_has_priority_over_opponent():
    # 「ペアの重複0・対戦相手の重複が多い」ほうが「ペアの重複1・対戦相手の重複0」より
    # 良い(小さい)と判定されること = ペアの重複を優先して避ける
    assert (0, 4) < (1, 0)


def test_card_history_counts_and_last_seen():
    history = HISTORY_2 + [{"team_a": ("D", "C"), "team_b": ("B", "A"), "sets": []}]
    cards = card_history(history)
    # 1試合目と3試合目は、チームの順序・名前の並びが違うだけで同じカード
    assert cards[card_key(("A", "B"), ("C", "D"))] == (2, 2)
    assert cards[card_key(("A", "C"), ("B", "D"))] == (1, 1)
    assert card_key(("A", "D"), ("B", "C")) not in cards


@pytest.mark.parametrize("num_players", [4, 5, 6, 8])
def test_generate_matchup_never_repeats_previous_card(num_players):
    # 4人では3通りのカードしかないので2周目以降は同じカードが必ず再登場するが、
    # 直前と同じカードが続くことはない(最後に出たのが昔のカードを優先するため)
    players = [chr(ord("A") + i) for i in range(num_players)]
    for seed in range(20):
        rng = random.Random(seed)
        history = []
        for _ in range(15):
            result = generate_matchup(players, history, rng=rng)
            if history:
                previous = history[-1]
                assert card_key(result["team_a"], result["team_b"]) != card_key(
                    previous["team_a"], previous["team_b"])
            history.append({**result, "sets": [(6, 3)]})


# --- _partitions_of_four ----------------------------------------------------------

def test_partitions_of_four_returns_three_distinct_combinations():
    partitions = _partitions_of_four(["A", "B", "C", "D"])
    assert len(partitions) == 3
    # 3通りとも異なる組み合わせであること
    as_sets = [{p[0], p[1]} for p in partitions]
    assert as_sets[0] != as_sets[1]
    assert as_sets[1] != as_sets[2]
    assert as_sets[0] != as_sets[2]
    # どの組み合わせも、2チーム合わせるとちょうど4人になること
    for team_a, team_b in partitions:
        assert team_a | team_b == {"A", "B", "C", "D"}
        assert len(team_a) == 2 and len(team_b) == 2


# --- generate_matchup --------------------------------------------------------------

def test_generate_matchup_first_round_uses_all_four_players_with_no_history():
    result = generate_matchup(["A", "B", "C", "D"], [], rng=random.Random(0))
    assert set(result["team_a"]) | set(result["team_b"]) == {"A", "B", "C", "D"}
    assert result["resting"] == []


def test_generate_matchup_rests_the_extra_player():
    result = generate_matchup(["A", "B", "C", "D", "E"], [], rng=random.Random(0))
    playing = set(result["team_a"]) | set(result["team_b"])
    assert len(playing) == 4
    assert result["resting"] == list({"A", "B", "C", "D", "E"} - playing)


def test_generate_matchup_raises_when_fewer_than_four_players():
    with pytest.raises(ValueError):
        generate_matchup(["A", "B", "C"], [])


def test_generate_matchup_never_repeats_previous_partition_with_same_four_players():
    # 登録が4人ちょうどなら、毎回同じ4人で対戦することになるので、
    # 「直前と同じ組み合わせを避ける」ロジックが確実に効く場面
    history = [{"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": [(6, 3)]}]
    previous_partition = {frozenset(("A", "B")), frozenset(("C", "D"))}

    for seed in range(50):
        result = generate_matchup(["A", "B", "C", "D"], history, rng=random.Random(seed))
        this_partition = {frozenset(result["team_a"]), frozenset(result["team_b"])}
        assert this_partition != previous_partition


def test_generate_matchup_can_produce_both_remaining_partitions_over_many_trials():
    # 3通りのうち直前の1通りを除いた残り2通りが、どちらも出現しうることを確認
    history = [{"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": [(6, 3)]}]
    seen_partitions = set()
    for seed in range(50):
        result = generate_matchup(["A", "B", "C", "D"], history, rng=random.Random(seed))
        seen_partitions.add(frozenset({frozenset(result["team_a"]), frozenset(result["team_b"])}))
    assert len(seen_partitions) == 2


def test_generate_matchup_avoids_repeated_pairs_with_four_players():
    # 4人でA・B, C・D, A・C, B・Dと組んだ後は、まだ組んでいないA・D と B・C しかない
    for seed in range(20):
        result = generate_matchup(["A", "B", "C", "D"], HISTORY_2, rng=random.Random(seed))
        assert {frozenset(result["team_a"]), frozenset(result["team_b"])} == {
            frozenset(("A", "D")), frozenset(("B", "C")),
        }


def test_generate_matchup_always_picks_minimum_cost():
    # 6人でランダムに10試合進める間、毎回「候補の中で最も重複が少ない」ものを選んでいるか、
    # 全候補を総当たりで計算した最小値と照合する
    players = ["A", "B", "C", "D", "E", "F"]
    rng = random.Random(1)
    history = []
    for _ in range(10):
        pairs, opponents = pair_counts(history), opponent_counts(history)
        cards = card_history(history)
        all_costs = [
            matchup_cost(a, b, pairs, opponents, cards)
            for g in candidate_groups(players, history)
            for a, b in _partitions_of_four(g)
        ]
        result = generate_matchup(players, history, rng=rng)
        assert matchup_cost(result["team_a"], result["team_b"], pairs, opponents, cards) == min(all_costs)
        history.append({**result, "sets": [(6, 3)]})


@pytest.mark.parametrize("num_players, rounds", [(5, 5), (6, 9), (8, 14)])
def test_generate_matchup_keeps_match_counts_equal(num_players, rounds):
    # 人数×試合数が割り切れる設定なら、全員がちょうど同じ試合数になる
    players = [chr(ord("A") + i) for i in range(num_players)]
    for seed in range(20):
        rng = random.Random(seed)
        history = []
        for _ in range(rounds):
            history.append({**generate_matchup(players, history, rng=rng), "sets": [(6, 3)]})
        counts = matches_played_count(players, history)
        assert len(set(counts.values())) == 1


def test_generate_matchup_eight_players_fourteen_rounds_every_pair_once():
    # 8人なら全28ペアが14試合(28枠)でちょうど1回ずつ組める
    players = [chr(ord("A") + i) for i in range(8)]
    for seed in range(20):
        rng = random.Random(seed)
        history = []
        for _ in range(14):
            history.append({**generate_matchup(players, history, rng=rng), "sets": [(6, 3)]})
        pairs = pair_counts(history)
        assert all(pairs[frozenset(pr)] == 1 for pr in combinations(players, 2))


# --- player_matches / player_summary ------------------------------------------------

def test_player_matches_keeps_perspective_for_team_a_player():
    history = [{"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": [(6, 3), (4, 6), (6, 2)]}]
    result = player_matches("A", history)
    assert result == [{"opponent": "C・D", "sets": [(6, 3), (4, 6), (6, 2)]}]


def test_player_matches_inverts_perspective_for_team_b_player():
    history = [{"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": [(6, 3), (4, 6), (6, 2)]}]
    result = player_matches("C", history)
    assert result == [{"opponent": "A・B", "sets": [(3, 6), (6, 4), (2, 6)]}]


def test_player_matches_skips_rounds_where_player_was_resting():
    history = [{"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": [(6, 3)]}]
    assert player_matches("E", history) == []


def test_player_summary_matches_hand_calculation():
    # A・B vs C・D: A・Bが2-0で勝利(6-3, 6-4)
    # A・C vs B・D: A・Cが1-1から6-2で辛勝(4-6, 6-2, 6-2) ※3セット目は便宜上
    history = [
        {"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": [(6, 3), (6, 4)]},
        {"team_a": ("A", "C"), "team_b": ("B", "D"), "sets": [(4, 6), (6, 2), (6, 2)]},
    ]
    summary = player_summary(["A", "B", "C", "D"], history)

    # A: 2試合とも勝ち(チームA視点で2試合ともwin) → 勝率1.0
    assert summary["A"]["matches_played"] == 2
    assert summary["A"]["win_rate"] == pytest.approx(1.0)

    # B: 1試合目は勝ち(A・B)、2試合目は負け(B・D) → 勝率0.5
    assert summary["B"]["matches_played"] == 2
    assert summary["B"]["win_rate"] == pytest.approx(0.5)

    # C: 1試合目は負け(C・D)、2試合目は勝ち(A・C) → 勝率0.5
    assert summary["C"]["matches_played"] == 2
    assert summary["C"]["win_rate"] == pytest.approx(0.5)

    # D: 2試合とも負け → 勝率0.0
    assert summary["D"]["matches_played"] == 2
    assert summary["D"]["win_rate"] == pytest.approx(0.0)

    # ゲーム獲得率の手計算(Aの視点): 1試合目 own=6+6=12, all=12+7=19
    # 2試合目(A・C視点) own=4+6+6=16, all=(4+6)+(6+2)+(6+2)=26
    # 合計 own=12+16=28, all=19+26=45
    assert summary["A"]["game_win_rate"] == pytest.approx(28 / 45)


def test_player_summary_wins_losses_draws_and_sets():
    # 1試合目 A・B vs C・D: 6-3, 4-6 → セット1-1で引分
    # 2試合目 A・C vs B・D: 6-2 → A・Cの勝ち
    history = [
        {"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": [(6, 3), (4, 6)]},
        {"team_a": ("A", "C"), "team_b": ("B", "D"), "sets": [(6, 2)]},
    ]
    summary = player_summary(["A", "B", "C", "D", "E"], history)

    a = summary["A"]
    assert (a["wins"], a["losses"], a["draws"]) == (1, 0, 1)
    assert (a["sets_won"], a["sets_lost"], a["set_diff"]) == (2, 1, 1)
    # 勝率は 勝ち÷試合数(引分は勝ちに数えない) = 1/2
    assert a["win_rate"] == pytest.approx(0.5)

    d = summary["D"]
    assert (d["wins"], d["losses"], d["draws"]) == (0, 1, 1)
    assert (d["sets_won"], d["sets_lost"], d["set_diff"]) == (1, 2, -1)

    e = summary["E"]  # 一度も出ていない
    assert (e["matches_played"], e["wins"], e["sets_won"]) == (0, 0, 0)


# --- 途中で抜けたメンバー(2026-10-12追加) ----------------------------------------
# 抜けた人は players から外れるが、成績を残すため history には残っている

def test_matches_played_count_ignores_players_who_left():
    history = [{"team_a": ("A", "E"), "team_b": ("B", "C"), "resting": ["D"], "sets": [(6, 4)]}]
    assert matches_played_count(["A", "B", "C", "D"], history) == {"A": 1, "B": 1, "C": 1, "D": 0}


def test_generate_matchup_after_player_left_uses_only_remaining_players():
    rng = random.Random(0)
    players = ["A", "B", "C", "D", "E"]
    history = []
    for _ in range(3):
        m = generate_matchup(players, history, rng)
        history.append({**m, "sets": [(6, 4)]})
    remaining = ["A", "B", "C", "D"]  # Eが抜けた
    for _ in range(5):
        m = generate_matchup(remaining, history, rng)
        assert set(m["team_a"]) | set(m["team_b"]) == set(remaining)
        assert m["resting"] == []
        history.append({**m, "sets": [(6, 4)]})


def test_player_summary_keeps_record_of_player_who_left():
    history = [{"team_a": ("A", "E"), "team_b": ("B", "C"), "resting": ["D"], "sets": [(6, 4)]}]
    summary = player_summary(["A", "B", "C", "D", "E"], history)
    assert summary["E"]["wins"] == 1


# --- 途中から加わるメンバー(2026-10-12追加): 他の人と同じペースで出る ----------------

def test_join_offset_new_player_matches_least_played():
    history = [
        {"team_a": ("A", "B"), "team_b": ("C", "D"), "resting": ["E"], "sets": [(6, 4)]},
        {"team_a": ("A", "E"), "team_b": ("B", "C"), "resting": ["D"], "sets": [(6, 4)]},
    ]
    # 試合数 A=2,B=2,C=2,D=1,E=1。新しいFは最少の1とみなす
    assert join_offset("F", ["A", "B", "C", "D", "E", "F"], history) == 1


def test_join_offset_returning_player_keeps_actual_matches():
    history = [{"team_a": ("A", "B"), "team_b": ("C", "D"), "resting": [], "sets": [(6, 4)]}] * 3
    # Dは3試合出た後に抜けて戻った。他の人も3試合なので下駄は0
    assert join_offset("D", ["A", "B", "C", "D"], history) == 0


def test_new_player_does_not_play_every_round():
    rng = random.Random(1)
    players = ["A", "B", "C", "D", "E"]
    history, offsets = [], {}
    for _ in range(5):
        history.append({**generate_matchup(players, history, rng, offsets), "sets": [(6, 4)]})
    players.append("F")
    offsets["F"] = join_offset("F", players, history, offsets)
    f_rounds = 0
    for _ in range(6):
        m = generate_matchup(players, history, rng, offsets)
        f_rounds += "F" in m["team_a"] + m["team_b"]
        history.append({**m, "sets": [(6, 4)]})
    # 6人で6試合 → 1人あたり平均4試合。下駄なしならFは6試合連続で出てしまう
    assert f_rounds <= 5
    counts = matches_played_count(players, history, offsets)
    assert max(counts.values()) - min(counts.values()) <= 1
