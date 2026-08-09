"""tennis_stats.py のテスト。

構造カバレッジ(C0/C1)を目標にせず、仕様に対する同値分割・境界値分析でケースを設計する。
- is_valid_set: 境界値分析(妥当な境界のすぐ内側/すぐ外側)
- parse_set_token: 同値クラス(valid / corrected / rejected-format / rejected-value)
- classify_line: 複数セットにまたがる集約ロジックの組み合わせ・優先順位
- input_matches_from_csv: 既存サンプルCSVでの回帰確認
"""

import pytest

from tennis_stats import (
    classify_line,
    input_matches_from_csv,
    is_valid_set,
    parse_set_token,
)


# --- is_valid_set: 境界値分析 -----------------------------------------
# hi==6 は lo<=4 まで妥当、hi==7 は lo が5か6のときのみ妥当。
# 「妥当な境界のすぐ内側」と「すぐ外側」をペアで確認する。

@pytest.mark.parametrize("own, opp", [
    (6, 4),   # hi=6,lo=4: 妥当な境界のちょうど内側
    (6, 0),   # hi=6,lo=0: 6-0という現実にありうる最大差
    (7, 5),   # hi=7,lo=5: 7-5の境界
    (7, 6),   # hi=7,lo=6: 7-6(タイブレーク)の境界
    (4, 6),   # 向きが逆でも(own,opp)の順序に依存しないことを確認
])
def test_is_valid_set_valid_boundaries(own, opp):
    assert is_valid_set(own, opp) is True


@pytest.mark.parametrize("own, opp", [
    (6, 5),   # hi=6,lo=5: 6-4の境界のすぐ外側(存在しないスコア)
    (7, 4),   # hi=7,lo=4: 7-5の境界のすぐ外側
    (6, 6),   # hi=6,lo=6: タイスコア
    (7, 7),   # hi=7,lo=7: タイスコア
    (5, 3),   # hi=5: 6でも7でもない
    (8, 6),   # hi=8: 範囲外
])
def test_is_valid_set_invalid_boundaries(own, opp):
    assert is_valid_set(own, opp) is False


# --- parse_set_token: 同値クラス ---------------------------------------

def test_parse_set_token_valid():
    status, own, opp, note = parse_set_token("6-3")
    assert status == "valid"
    assert (own, opp) == (6, 3)
    assert note is None


def test_parse_set_token_corrected_zenkaku():
    status, own, opp, note = parse_set_token("６-３")
    assert status == "corrected"
    assert (own, opp) == (6, 3)
    assert "6-3" in note


def test_parse_set_token_rejected_format():
    status, own, opp, note = parse_set_token("7-x")
    assert status == "rejected"
    assert own is None and opp is None


def test_parse_set_token_rejected_too_many_parts():
    status, own, opp, note = parse_set_token("6-3-1")
    assert status == "rejected"


def test_parse_set_token_rejected_value():
    status, own, opp, note = parse_set_token("6-6")
    assert status == "rejected"
    assert (own, opp) == (6, 6)  # 数値としては解釈できるが、スコアとして無効


def test_parse_set_token_strips_whitespace():
    status, own, opp, note = parse_set_token(" 6-3 ")
    assert status == "valid"
    assert (own, opp) == (6, 3)


# --- classify_line: 集約ロジックの組み合わせ・優先順位 -------------------

def test_classify_line_all_valid():
    result = classify_line("6-3,4-6,7-5")
    assert result["status"] == "valid"
    assert result["sets"] == [(6, 3), (4, 6), (7, 5)]


def test_classify_line_corrected_upgrades_from_valid():
    result = classify_line("６-３,4-6")
    assert result["status"] == "corrected"
    assert result["sets"] == [(6, 3), (4, 6)]


def test_classify_line_one_rejected_rejects_whole_match():
    result = classify_line("6-3,6-6")
    assert result["status"] == "rejected"
    assert result["sets"] == []  # 有効だった6-3も含めて集計対象から外れる


def test_classify_line_rejected_takes_priority_over_corrected():
    # correctedがrejectedより後に来ても、rejectedの判定が上書きされないことを確認
    result = classify_line("6-6,６-３")
    assert result["status"] == "rejected"
    assert result["sets"] == []


def test_classify_line_rejected_before_corrected_still_rejects():
    # 逆順(corrected→rejected)でも同じ結果になることを確認
    result = classify_line("６-３,6-6")
    assert result["status"] == "rejected"
    assert result["sets"] == []


# --- input_matches_from_csv: 既存サンプルCSVでの回帰確認 -----------------

def test_input_matches_from_csv_clean_sample_has_no_logs():
    matches, corrected_log, rejected_log = input_matches_from_csv("sample_matches.csv")
    assert len(matches) > 0
    assert corrected_log == []
    assert rejected_log == []


def test_input_matches_from_csv_dirty_sample_separates_corrected_and_rejected():
    matches, corrected_log, rejected_log = input_matches_from_csv("sample_matches_dirty.csv")
    assert len(corrected_log) > 0
    assert len(rejected_log) > 0
    # rejectedにされた行は集計(matches)に含まれていないことを確認
    assert len(matches) + len(rejected_log) == sum(1 for _ in open(
        "sample_matches_dirty.csv", encoding="utf-8-sig")) - 1  # ヘッダー分を引く
