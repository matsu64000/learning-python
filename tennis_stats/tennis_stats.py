# テニス試合結果集計

import csv


# 全角数字・各種ダッシュ記号 → 半角 の変換テーブル（表記ゆれの補正で使う）。
# ダッシュはハイフンマイナス以外にも、全角ハイフンや日本語入力で紛れ込みやすい
# 長音記号「ー」など、見た目が似ている文字を幅広く「-」に寄せる。
_CHAR_FIXUPS = {
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "－": "-",  # U+FF0D 全角ハイフンマイナス
    "‐": "-",  # U+2010 HYPHEN
    "‑": "-",  # U+2011 NON-BREAKING HYPHEN
    "‒": "-",  # U+2012 FIGURE DASH
    "–": "-",  # U+2013 EN DASH
    "—": "-",  # U+2014 EM DASH
    "―": "-",  # U+2015 HORIZONTAL BAR
    "−": "-",  # U+2212 MINUS SIGN
    "ー": "-",  # 長音記号（ハイフンと打ち間違えやすい）
}
_NORMALIZE_TABLE = str.maketrans(_CHAR_FIXUPS)


def normalize_score_text(text):
    """全角数字・各種ダッシュ記号を半角ハイフンに統一し、余分な空白を除去する"""
    normalized = text.translate(_NORMALIZE_TABLE)
    return "".join(ch for ch in normalized if not ch.isspace())


# 試合形式の定義。キー(CSVや画面内部で使う識別子)→
#   label     : 画面表示名
#   max_games : 1セットで選べるゲーム数の上限(スマホの数字選択欄の選択肢に使う)
#   max_sets  : 最大セット数(3セットマッチだけ3、他は1セットで固定)
# COBOLで言えば、判定ルールをIF文にベタ書きせず、形式コードで引くパラメータテーブル。
MATCH_FORMATS = {
    "one_set": {"label": "1セットマッチ", "max_games": 7, "max_sets": 1},
    "four_first": {"label": "4ゲーム先取", "max_games": 4, "max_sets": 1},
    "four_match": {"label": "4ゲームマッチ", "max_games": 4, "max_sets": 1},
    "free": {"label": "フリー", "max_games": 15, "max_sets": 1},
    # アマチュアでは稀だが、汎用性のために残す(画面の選択肢では最後に並ぶ)
    "three_set": {"label": "3セットマッチ", "max_games": 7, "max_sets": 3},
}
DEFAULT_FORMAT = "one_set"  # 1セット単位の判定で形式を指定しない場合はこれとみなす


def guess_format(set_count):
    """形式の指定がない試合(形式導入前のCSV・CLIの入力)の形式を、セット数から推定する。
    1セットなら1セットマッチ、2セット以上なら3セットマッチ"""
    return "one_set" if set_count <= 1 else "three_set"


def format_from_text(text):
    """CSVの形式欄の値(キー "four_first" でも表示名 "4ゲーム先取" でも可)を形式キーに変換する。
    空欄なら None(セット数から推定する、の意味)。どれにも当たらなければ ValueError"""
    text = (text or "").strip()
    if text == "":
        return None
    for key, spec in MATCH_FORMATS.items():
        if text in (key, spec["label"]):
            return key
    raise ValueError(f"未知の試合形式です: '{text}'")


def is_valid_set(own, opp, fmt=DEFAULT_FORMAT):
    """テニスの1セットとして存在しうるスコアかどうかを、試合形式 fmt に従って判定する。

    - one_set    : 6ゲーム先取。6-0〜6-4、7-5、7-6(タイブレーク)
    - three_set  : 1セットの中身は one_set と同じ(セット数の判定は check_set_count)
    - four_first : 4ゲーム先取。3-3の後はノーアドで1ゲーム勝負なので 4-0〜4-3
    - four_match : 合計4ゲームを必ず行う。2-2は引分
    - free       : 何ゲーム先取とも決めない。0-0(試合をしていない)以外は可
    """
    if own < 0 or opp < 0:
        return False
    hi, lo = max(own, opp), min(own, opp)
    if fmt in ("one_set", "three_set"):
        return (hi == 6 and lo <= 4) or (hi == 7 and lo in (5, 6))
    if fmt == "four_first":
        return hi == 4 and lo <= 3
    if fmt == "four_match":
        return own + opp == 4
    if fmt == "free":
        return hi > 0
    raise ValueError(f"未知の試合形式です: {fmt}")


def parse_set_token(token, fmt=DEFAULT_FORMAT):
    """1セット分のスコア文字列を検証・分類する。

    戻り値: (status, own, opp, note)
      status は "valid"（正常） / "corrected"（補正して採用） / "rejected"（却下）
    """
    original = token.strip()
    normalized = normalize_score_text(original)

    try:
        own_str, opp_str = normalized.split("-")
        own, opp = int(own_str), int(opp_str)
    except ValueError:
        return "rejected", None, None, f"スコア形式として解釈できません: '{original}'"

    if not is_valid_set(own, opp, fmt):
        return "rejected", own, opp, f"{MATCH_FORMATS[fmt]['label']}では存在しないセットスコアです: '{original}'"

    if normalized != original:
        return "corrected", own, opp, f"表記を補正しました: '{original}' → '{normalized}'"

    return "valid", own, opp, None


def check_set_count(sets, fmt):
    """試合全体としてセット数が形式に合っているかを判定し、問題点のリストを返す(問題なしなら空)。
    1セットごとのスコアが妥当であることを前提にする(is_valid_set で確認済みのもの)。

    - 3セットマッチ以外 : 1セットで固定
    - 3セットマッチ     : 2セット先取。2-0で終わったら第3セットは無く、1-1なら第3セットが必要
    """
    label = MATCH_FORMATS[fmt]["label"]
    if MATCH_FORMATS[fmt]["max_sets"] == 1:
        if len(sets) != 1:
            return [f"{label}は1セットで入力してください({len(sets)}セットあります)"]
        return []

    if len(sets) < 2:
        return [f"{label}は2セット以上必要です"]
    if len(sets) > 3:
        return [f"{label}は3セットまでです({len(sets)}セットあります)"]
    won_first_two = sum(1 for own, opp in sets[:2] if own > opp)
    if len(sets) == 2 and won_first_two == 1:
        return ["1-1のため第3セットが必要です"]
    if len(sets) == 3 and won_first_two != 1:
        return ["2セット先取で勝敗が決まった後に第3セットがあります"]
    return []


def classify_line(line, fmt=None):
    """1行（1試合）分のスコアをまとめて検証・分類する。

    1セットでも却下（rejected）があれば、その試合全体を却下扱いとし
    （sets は空になる）、隔離レポート側でまとめて確認できるようにする。
    fmt を省略した場合は、セット数から形式を推定する(guess_format)。
    """
    tokens = line.split(",")
    if fmt is None:
        fmt = guess_format(len(tokens))
    sets = []
    notes = []
    overall = "valid"
    for token in tokens:
        status, own, opp, note = parse_set_token(token, fmt)
        if note:
            notes.append(note)
        if status == "rejected":
            overall = "rejected"
        elif status == "corrected" and overall == "valid":
            overall = "corrected"
        if status != "rejected":
            sets.append((own, opp))

    if overall != "rejected":
        count_notes = check_set_count(sets, fmt)
        if count_notes:
            notes.extend(count_notes)
            overall = "rejected"

    if overall == "rejected":
        sets = []

    return {"status": overall, "sets": sets, "notes": notes}


def classify_sets(sets, fmt=None):
    """数字で選択済みの(own, opp)の並びを、classify_lineと同じ形で検証・分類する。

    スマホ画面のように文字ではなく数字を選んで入力する場合は、表記ゆれ
    （全角数字・ダッシュ記号）が起こり得ないので "corrected" にはならない。
    未選択のセットは None で渡される想定で、1つでもあれば試合全体を却下する。
    1セット分の妥当性判定はclassify_lineと同じis_valid_setを使う（判定の共通化）。

    3セットマッチの画面では第3セットの欄が常に出ているので、末尾の「両方とも未選択」の
    セットは入力されなかったものとして取り除いてから判定する。
    """
    sets = list(sets)
    while len(sets) > 1 and sets[-1] == (None, None):
        sets.pop()
    if fmt is None:
        fmt = guess_format(len(sets))
    notes = []
    for i, (own, opp) in enumerate(sets, start=1):
        if own is None or opp is None:
            notes.append(f"第{i}セットのスコアが選択されていません")
        elif not is_valid_set(own, opp, fmt):
            notes.append(f"第{i}セットは{MATCH_FORMATS[fmt]['label']}では存在しないセットスコアです: '{own}-{opp}'")

    if not sets:
        notes.append("セットが1つもありません")

    if not notes:
        notes = check_set_count(sets, fmt)

    if notes:
        return {"status": "rejected", "sets": [], "notes": notes}
    return {"status": "valid", "sets": sets, "notes": []}


def input_matches():
    """キーボードから対話的に試合結果を読み込む。

    1セット入力するたびにその場で判定する。rejectedならエラーを伝えて
    同じ行を再入力させ、correctedなら補正内容を伝えた上で採用する
    （CSV側と同じclassify_lineを使い、判定ロジックは共通化している）。
    """
    print("対戦相手の名前を入力してください（1行に1人、入力終了は空行）")
    opponents = []
    while True:
        name = input("対戦相手名: ").strip()
        if name == "":
            break
        opponents.append(name)

    matches = []
    for opponent in opponents:
        print(f"--- {opponent} との対戦結果 ---")
        print("スコアを 6-3,4-6,6-2 のように入力してください（この相手との入力終了は空行）")
        while True:
            line = input(f"{opponent} 戦のスコア: ").strip()
            if line == "":
                break

            result = classify_line(line)
            if result["status"] == "rejected":
                print("入力エラー: " + "; ".join(result["notes"]))
                print("もう一度入力してください")
                continue

            if result["status"] == "corrected":
                print("補正して採用しました: " + "; ".join(result["notes"]))

            matches.append({"opponent": opponent, "sets": result["sets"]})

    return matches


def matches_from_csv_rows(rows):
    """csv.DictReaderと同じ形(1行=opponent/setsを持つdict)のイテレータから、
    試合結果を検証・分類する。

    ファイルパスを直接受け取るinput_matches_from_csvと、Webアプリの
    アップロードファイルのように既にテキストとして読み込み済みのデータの
    両方から共通で使えるよう、「ファイルを開く処理」と「行を分類する処理」を分離した
    （8/09に整理した「判定ロジックは入力元非依存」という原則を、ファイルI/O自体にも広げた形）
    """
    matches = []
    corrected_log = []
    rejected_log = []

    for row_no, row in enumerate(rows, start=2):  # 1行目はヘッダーなので2から
        # format列は任意(形式導入前のCSVにはない)。無ければセット数から推定する
        try:
            fmt = format_from_text(row.get("format"))
        except ValueError as e:
            rejected_log.append({
                "row": row_no,
                "opponent": row["opponent"],
                "raw": row["sets"],
                "notes": [str(e)],
            })
            continue
        if fmt is None:
            fmt = guess_format(len(row["sets"].split(",")))

        result = classify_line(row["sets"], fmt)

        if result["status"] == "rejected":
            rejected_log.append({
                "row": row_no,
                "opponent": row["opponent"],
                "raw": row["sets"],
                "notes": result["notes"],
            })
            continue

        if result["status"] == "corrected":
            corrected_log.append({
                "row": row_no,
                "opponent": row["opponent"],
                "raw": row["sets"],
                "notes": result["notes"],
            })

        matches.append({"opponent": row["opponent"], "sets": result["sets"], "format": fmt})

    return matches, corrected_log, rejected_log


def input_matches_from_csv(filepath):
    """CSVファイルから試合結果を読み込む。

    妥当なスコアだけでなく、全角数字などの表記ゆれは補正して採用し、
    存在しないスコア等は却下して集計対象から外す（隔離）。
    補正・却下したデータは corrected_log / rejected_log に記録し、
    元の生データ（raw）を残すことで、あとから内容を追えるようにする。
    """
    with open(filepath, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return matches_from_csv_rows(reader)


def set_counts(match):
    """1試合の(取ったセット数, 落としたセット数)を返す。
    4ゲームマッチの2-2のような同点のセットは、どちらにも数えない"""
    sets_won = 0
    sets_lost = 0
    for own, opp in match["sets"]:
        if own > opp:
            sets_won += 1
        elif own < opp:
            sets_lost += 1
    return sets_won, sets_lost


def match_result(match):
    """1試合の結果を "win" / "loss" / "draw" で返す。

    2セットマッチの1-1や、4ゲームマッチの2-2(1セットのみ)のように、
    取ったセット数と落としたセット数が同じなら引分。
    (did_winは勝ちか否かの2値なので、引分も「勝ちではない」側に入ってしまう)
    """
    sets_won, sets_lost = set_counts(match)
    if sets_won > sets_lost:
        return "win"
    if sets_won < sets_lost:
        return "loss"
    return "draw"


def did_win(match):
    return match_result(match) == "win"


def win_rate(target_matches):
    if not target_matches:
        return 0.0
    wins = sum(1 for m in target_matches if did_win(m))
    return wins / len(target_matches)


def win_rate_by_opponent(target_matches):
    grouped = {}
    for m in target_matches:
        grouped.setdefault(m["opponent"], []).append(m)
    return {name: win_rate(ms) for name, ms in grouped.items()}


def game_win_rate(target_matches):
    own_total = 0
    all_total = 0
    for m in target_matches:
        for own, opp in m["sets"]:
            own_total += own
            all_total += own + opp
    if all_total == 0:
        return 0.0
    return own_total / all_total


def main():
    print("入力方法を選んでください")
    print("1: キーボードから対話入力")
    print("2: CSVファイルから読み込み")
    choice = input("番号を入力: ").strip()

    if choice == "2":
        filepath = input("CSVファイルのパスを入力してください: ").strip()
        matches, corrected_log, rejected_log = input_matches_from_csv(filepath)

        if corrected_log:
            print("--- 補正して採用したデータ ---")
            for item in corrected_log:
                print(f"{item['row']}行目 ({item['opponent']}, 元データ: {item['raw']}): "
                      + "; ".join(item["notes"]))

        if rejected_log:
            print("--- 却下したデータ（集計対象外） ---")
            for item in rejected_log:
                print(f"{item['row']}行目 ({item['opponent']}, 元データ: {item['raw']}): "
                      + "; ".join(item["notes"]))
    else:
        matches = input_matches()

    print(f"総試合数: {len(matches)}試合")
    print(f"勝率: {win_rate(matches):.1%}")

    print("--- 対戦相手別勝率 ---")
    for name, rate in win_rate_by_opponent(matches).items():
        print(f"{name}: {rate:.1%}")

    print(f"ゲーム獲得率: {game_win_rate(matches):.1%}")


if __name__ == "__main__":
    main()
