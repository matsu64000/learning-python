"""doubles.py のテスト。

乱数を使う関数はrng=random.Random(seed)を渡して挙動を固定して検証する。
ただし「同数タイの中からランダムに選ばれる」性質そのものは1回の呼び出しでは
確認できないため、多数回試行して全員が選ばれうることを見る統計的な検証を使う
(頻度は極めて低いが理論上まれに失敗しうる。十分な試行回数で実用上は問題ない)
"""

import random

import pytest

from doubles import (
    _partitions_of_four,
    generate_matchup,
    matches_played_count,
    player_matches,
    player_summary,
    select_players_for_round,
)


# --- matches_played_count -------------------------------------------------------

def test_matches_played_count_counts_each_appearance():
    history = [
        {"team_a": ("A", "B"), "team_b": ("C", "D"), "sets": []},
        {"team_a": ("A", "C"), "team_b": ("B", "D"), "sets": []},
    ]
    counts = matches_played_count(["A", "B", "C", "D", "E"], history)
    assert counts == {"A": 2, "B": 2, "C": 2, "D": 2, "E": 0}


# --- select_players_for_round ----------------------------------------------------

def test_select_players_for_round_picks_least_played_four():
    # E, Fは2回ずつ対戦済み、A-Dは1回ずつ → 対戦数が少ないA-Dが選ばれるはず
    history = [
        {"team_a": ("E", "F"), "team_b": ("A", "B"), "sets": []},
        {"team_a": ("E", "F"), "team_b": ("C", "D"), "sets": []},
    ]
    result = select_players_for_round(["A", "B", "C", "D", "E", "F"], history)
    assert set(result) == {"A", "B", "C", "D"}


def test_select_players_for_round_breaks_ties_randomly():
    # 5人全員が対戦数0(完全に同数)のとき、複数回実行すれば「休む1人」は
    # 統計的に色々な人になるはず(常に同じ人が休むなら公平とは言えない)
    players = ["A", "B", "C", "D", "E"]
    resting_people_seen = set()
    for seed in range(200):
        chosen = select_players_for_round(players, [], rng=random.Random(seed))
        resting = set(players) - set(chosen)
        resting_people_seen |= resting
    assert resting_people_seen == set(players)


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
