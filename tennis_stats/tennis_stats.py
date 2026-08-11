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


def is_valid_set(own, opp):
    """テニスの1セットとして存在しうるスコアかどうかを判定する"""
    hi, lo = max(own, opp), min(own, opp)
    if hi == 6 and lo <= 4:
        return True
    if hi == 7 and lo in (5, 6):
        return True
    return False


def parse_set_token(token):
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

    if not is_valid_set(own, opp):
        return "rejected", own, opp, f"存在しないセットスコアです: '{original}'"

    if normalized != original:
        return "corrected", own, opp, f"表記を補正しました: '{original}' → '{normalized}'"

    return "valid", own, opp, None


def classify_line(line):
    """1行（1試合）分のスコアをまとめて検証・分類する。

    1セットでも却下（rejected）があれば、その試合全体を却下扱いとし
    （sets は空になる）、隔離レポート側でまとめて確認できるようにする。
    """
    sets = []
    notes = []
    overall = "valid"
    for token in line.split(","):
        status, own, opp, note = parse_set_token(token)
        if note:
            notes.append(note)
        if status == "rejected":
            overall = "rejected"
        elif status == "corrected" and overall == "valid":
            overall = "corrected"
        if status != "rejected":
            sets.append((own, opp))

    if overall == "rejected":
        sets = []

    return {"status": overall, "sets": sets, "notes": notes}


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


def input_matches_from_csv(filepath):
    """CSVから試合結果を読み込む。

    妥当なスコアだけでなく、全角数字などの表記ゆれは補正して採用し、
    存在しないスコア等は却下して集計対象から外す（隔離）。
    補正・却下したデータは corrected_log / rejected_log に記録し、
    元の生データ（raw）を残すことで、あとから内容を追えるようにする。
    """
    matches = []
    corrected_log = []
    rejected_log = []

    with open(filepath, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_no, row in enumerate(reader, start=2):  # 1行目はヘッダーなので2から
            result = classify_line(row["sets"])

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

            matches.append({"opponent": row["opponent"], "sets": result["sets"]})

    return matches, corrected_log, rejected_log


def did_win(match):
    sets_won = 0
    sets_lost = 0
    for own, opp in match["sets"]:
        if own > opp:
            sets_won += 1
        else:
            sets_lost += 1
    return sets_won > sets_lost


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
