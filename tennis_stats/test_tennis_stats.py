"""tennis_stats.py のテスト。

構造カバレッジ(C0/C1)を目標にせず、仕様に対する同値分割・境界値分析でケースを設計する。
- is_valid_set: 境界値分析(妥当な境界のすぐ内側/すぐ外側)
- parse_set_token: 同値クラス(valid / corrected / rejected-format / rejected-value)
- classify_line: 複数セットにまたがる集約ロジックの組み合わせ・優先順位
- classify_sets: 数字選択入力(スマホ画面)向け。同値クラス(全セット妥当/未選択/存在しないスコア/空)
- input_matches_from_csv: 既存サンプルCSVでの回帰確認
"""

from pathlib import Path

import pytest

from tennis_stats import (
    classify_line,
    check_set_count,
    classify_sets,
    format_from_text,
    match_result,
    matches_from_csv_rows,
    set_counts,
    input_matches_from_csv,
    is_valid_set,
    parse_set_token,
)

# pytestをどのディレクトリから実行しても、このテストファイルと同じ場所にある
# サンプルCSVを指せるように、__file__基準の絶対パスにしておく。
DATA_DIR = Path(__file__).parent


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


@pytest.mark.parametrize("token", [
    "6－3",   # 全角ハイフンマイナス(U+FF0D)
    "6–3",    # ENダッシュ(U+2013)
    "6—3",    # EMダッシュ(U+2014)
    "6−3",    # マイナス記号(U+2212)
    "6ー3",   # 長音記号(ハイフンと打ち間違えやすい)
])
def test_parse_set_token_corrected_dash_variants(token):
    status, own, opp, note = parse_set_token(token)
    assert status == "corrected"
    assert (own, opp) == (6, 3)
    assert "6-3" in note


@pytest.mark.parametrize("token", [
    "6 -3",
    "6- 3",
    "6 - 3",
])
def test_parse_set_token_corrected_internal_whitespace(token):
    status, own, opp, note = parse_set_token(token)
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
    result = classify_line("６-３,6-4")
    assert result["status"] == "corrected"
    assert result["sets"] == [(6, 3), (6, 4)]


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


# --- classify_sets: 同値クラス ------------------------------------------
# 1セットの妥当性はis_valid_setで境界値分析済みなので、ここでは
# 「試合全体としての集約(1つでもダメなら全体却下)」と「未選択の扱い」を確認する

def test_classify_sets_all_valid():
    result = classify_sets([(6, 3), (4, 6), (7, 6)])
    assert result == {"status": "valid", "sets": [(6, 3), (4, 6), (7, 6)], "notes": []}


def test_classify_sets_unselected_rejects_whole_match():
    # 第2セットの「相手」側を選び忘れた
    result = classify_sets([(6, 3), (4, None)])
    assert result["status"] == "rejected"
    assert result["sets"] == []
    assert result["notes"] == ["第2セットのスコアが選択されていません"]


def test_classify_sets_invalid_score_rejects_whole_match():
    # 6-5は数字としては選べるが、テニスのセットとしては存在しない
    result = classify_sets([(6, 5), (6, 2)])
    assert result["status"] == "rejected"
    assert result["sets"] == []
    assert result["notes"] == ["第1セットは3セットマッチでは存在しないセットスコアです: '6-5'"]


def test_classify_sets_reports_every_bad_set():
    # 問題のあるセットが複数あれば、すべて一度に知らせる(何度も直させない)
    result = classify_sets([(None, None), (6, 6)])
    assert len(result["notes"]) == 2


def test_classify_sets_empty():
    result = classify_sets([])
    assert result["status"] == "rejected"


# --- input_matches_from_csv: 既存サンプルCSVでの回帰確認 -----------------

def test_input_matches_from_csv_clean_sample_has_no_logs():
    matches, corrected_log, rejected_log = input_matches_from_csv(DATA_DIR / "sample_matches.csv")
    assert len(matches) > 0
    assert corrected_log == []
    # 10/12に3セットマッチの試合単位の判定を入れた結果、「6-1,6-4,5-7」(2-0で勝負が
    # ついた後に第3セットがある)が却下されるようになった。サンプルは書き換えず、検知を確認する
    assert [(r["opponent"], r["notes"]) for r in rejected_log] == [
        ("シナー", ["2セット先取で勝敗が決まった後に第3セットがあります"]),
    ]


def test_input_matches_from_csv_dirty_sample_separates_corrected_and_rejected():
    matches, corrected_log, rejected_log = input_matches_from_csv(DATA_DIR / "sample_matches_dirty.csv")
    assert len(corrected_log) > 0
    assert len(rejected_log) > 0
    # rejectedにされた行は集計(matches)に含まれていないことを確認
    assert len(matches) + len(rejected_log) == sum(1 for _ in open(
        DATA_DIR / "sample_matches_dirty.csv", encoding="utf-8-sig")) - 1  # ヘッダー分を引く


# --- match_result: 勝ち/負け/引分の3つの同値クラス -----------------------------

@pytest.mark.parametrize("sets, expected", [
    ([(6, 3), (6, 4)], "win"),
    ([(3, 6), (6, 4), (2, 6)], "loss"),
    ([(6, 3), (4, 6)], "draw"),   # 1-1(集計関数としては引分。入力時の判定では却下される)
    ([(6, 3)], "win"),            # 1セットマッチ
])
def test_match_result(sets, expected):
    assert match_result({"opponent": "X", "sets": sets}) == expected


# --- 試合形式(2026-10-12追加): 形式ごとの境界値分析 ---------------------------
# 形式を指定しない呼び出しは従来通り1セットマッチ扱い(上の既存テストがそのまま回帰確認になる)

@pytest.mark.parametrize("own, opp, expected", [
    # 4ゲーム先取: 4-0〜4-3が妥当。3-3の後はノーアドで4-3決着なので5-3や4-4は無い
    (4, 0, True), (4, 3, True), (3, 4, True),
    (3, 3, False),   # 決着していない
    (4, 4, False),   # 4-3で終わるので存在しない
    (5, 3, False),   # 2ゲーム差まで延長はしない
    (6, 4, False),   # 6ゲーム先取のスコア
])
def test_is_valid_set_four_first(own, opp, expected):
    assert is_valid_set(own, opp, "four_first") is expected


@pytest.mark.parametrize("own, opp, expected", [
    # 4ゲームマッチ: 合計がちょうど4ゲーム
    (4, 0, True), (3, 1, True), (2, 2, True), (0, 4, True),
    (3, 0, False),   # 合計3(すぐ内側の外れ)
    (3, 2, False),   # 合計5(すぐ外側の外れ)
])
def test_is_valid_set_four_match(own, opp, expected):
    assert is_valid_set(own, opp, "four_match") is expected


@pytest.mark.parametrize("own, opp, expected", [
    # フリー: 0-0以外は何でも可。引分(3-3)や大差(10-2)もあり得る
    (1, 0, True), (3, 3, True), (10, 2, True),
    (0, 0, False),
    (-1, 2, False),
])
def test_is_valid_set_free(own, opp, expected):
    assert is_valid_set(own, opp, "free") is expected


def test_is_valid_set_unknown_format_raises():
    with pytest.raises(ValueError):
        is_valid_set(6, 4, "five_first")


def test_four_match_two_all_is_draw():
    # 2-2のセットは取ったセットにも落としたセットにも数えない → 0-0で引分
    match = {"opponent": "A", "sets": [(2, 2)]}
    assert set_counts(match) == (0, 0)
    assert match_result(match) == "draw"


def test_draw_set_is_not_counted_as_lost_in_multi_set_match():
    # 2-2 を「落としたセット」に数えると 1-1 の引分になってしまう(10/12に修正したバグ)
    match = {"opponent": "A", "sets": [(3, 1), (2, 2)]}
    assert set_counts(match) == (1, 0)
    assert match_result(match) == "win"


def test_classify_sets_uses_format():
    assert classify_sets([(4, 3)], "four_first")["status"] == "valid"
    result = classify_sets([(4, 3)])  # 1セットマッチでは存在しない
    assert result["status"] == "rejected"
    assert result["notes"] == ["第1セットは1セットマッチでは存在しないセットスコアです: '4-3'"]


@pytest.mark.parametrize("text, expected", [
    ("", None),                 # 形式導入前のCSV(列が空・無い)→ セット数から推定
    (None, None),
    ("four_first", "four_first"),
    ("4ゲームマッチ", "four_match"),  # 表示名でも受け付ける
    (" フリー ", "free"),
])
def test_format_from_text(text, expected):
    assert format_from_text(text) == expected


def test_format_from_text_unknown_raises():
    with pytest.raises(ValueError):
        format_from_text("5ゲーム先取")


# --- セット数の判定(10/12追加): 3セットマッチ以外は1セット固定、3セットマッチは2セット先取 ---

@pytest.mark.parametrize("sets, fmt, expected", [
    ([(6, 4)], "one_set", []),
    ([(6, 4), (6, 3)], "one_set", ["1セットマッチは1セットで入力してください(2セットあります)"]),
    ([(2, 2), (3, 1)], "four_match", ["4ゲームマッチは1セットで入力してください(2セットあります)"]),
    ([(6, 4), (6, 3)], "three_set", []),                 # 2-0
    ([(6, 4), (3, 6), (7, 5)], "three_set", []),         # 1-1から第3セット
    ([(6, 4)], "three_set", ["3セットマッチは2セット以上必要です"]),
    ([(6, 4), (3, 6)], "three_set", ["1-1のため第3セットが必要です"]),
    ([(6, 1), (6, 4), (5, 7)], "three_set", ["2セット先取で勝敗が決まった後に第3セットがあります"]),
])
def test_check_set_count(sets, fmt, expected):
    assert check_set_count(sets, fmt) == expected


def test_classify_sets_three_set_drops_blank_third_set():
    # 画面では第3セットの欄が常に出ている。2-0なら空欄のままでよい
    result = classify_sets([(6, 4), (6, 3), (None, None)], "three_set")
    assert result == {"status": "valid", "sets": [(6, 4), (6, 3)], "notes": []}


def test_classify_sets_three_set_requires_third_set_when_one_all():
    result = classify_sets([(6, 4), (3, 6), (None, None)], "three_set")
    assert result["notes"] == ["1-1のため第3セットが必要です"]


def test_classify_sets_three_set_half_filled_third_set_is_unselected():
    # 第3セットの片方だけ選んだ場合は「入力されなかった」とはみなさない
    result = classify_sets([(6, 4), (3, 6), (6, None)], "three_set")
    assert result["notes"] == ["第3セットのスコアが選択されていません"]


def test_classify_line_guesses_format_from_set_count():
    assert classify_line("6-4")["status"] == "valid"            # 1セットマッチ
    assert classify_line("6-4,3-6,6-2")["status"] == "valid"    # 3セットマッチ
    assert classify_line("6-4,3-6")["notes"] == ["1-1のため第3セットが必要です"]


def test_matches_from_csv_rows_with_format_column():
    rows = [
        {"opponent": "A", "sets": "4-3", "format": "4ゲーム先取"},
        {"opponent": "B", "sets": "2-2", "format": "four_match"},
        {"opponent": "C", "sets": "6-4"},                          # format列なし→1セットマッチ
        {"opponent": "F", "sets": "6-4,6-2"},                      # format列なし→3セットマッチ
        {"opponent": "G", "sets": "6-4,6-2", "format": "3セットマッチ"},
        {"opponent": "D", "sets": "4-3", "format": ""},            # 空欄→1セットマッチで却下
        {"opponent": "E", "sets": "6-4", "format": "謎の形式"},
    ]
    matches, corrected, rejected = matches_from_csv_rows(rows)
    assert [(m["opponent"], m["format"]) for m in matches] == [
        ("A", "four_first"), ("B", "four_match"), ("C", "one_set"),
        ("F", "three_set"), ("G", "three_set"),
    ]
    assert [r["opponent"] for r in rejected] == ["D", "E"]
    assert rejected[1]["notes"] == ["未知の試合形式です: '謎の形式'"]
