# テニス試合結果集計 - Streamlitによるブラウザ入力・集計表示のUI
#
# 【設計方針】
# ボタン操作やCSVアップロードといった「入力の見せ方」が変わっても、判定ロジック
# (classify_line)・集計ロジック(win_rate等)は一切変更しない。tennis_stats.pyの
# 関数をそのままインポートして使う。CLI(tennis_stats.py)とUI(このファイル)は、
# 同じエンティティ(試合結果の妥当性・集計方法)に対する別々の「境界での見せ方」
# でしかない、という8/09に整理した設計原則がそのまま活きている
#
# 【状態管理】Streamlitはユーザー操作のたびにスクリプト全体を再実行する
# (COBOLのバッチのように毎回頭から流れ直す)ため、登録済みの試合データは
# st.session_state(ブラウザのセッション中だけ保持される辞書)に貯める。
# ブラウザを閉じると消えるので、CSVダウンロード/アップロードで永続化する
#
# 実行方法: streamlit run app.py (入口のapp.pyから、メニューで「シングルス集計」を選ぶ)

import csv
import io

import pandas as pd
import streamlit as st

from score_input import format_selector, score_inputs
from tennis_stats import (
    MATCH_FORMATS,
    classify_sets,
    game_win_rate,
    match_result,
    matches_from_csv_rows,
    win_rate,
    win_rate_by_opponent,
)

st.set_page_config(page_title="テニス試合結果集計", page_icon="🎾")
st.title("🎾 テニス試合結果集計")

if "matches" not in st.session_state:
    st.session_state.matches = []


RESULT_LABELS = {"win": "勝ち", "loss": "負け", "draw": "引分"}


def _sets_to_text(sets):
    return ",".join(f"{own}-{opp}" for own, opp in sets)


# --- 1試合ずつ登録 -----------------------------------------------------------
# スマホでの入力を想定し、セット結果は数字を選ぶ方式(score_input.py)。
# 入力エラーのときに選んだ数字が消えないよう clear_on_submit は使わず、
# 成功したときだけ入力欄の key の通し番号(form_no)を進めて空の欄に作り直す。
# 再実行すると成功メッセージも消えてしまうので、st.session_state に
# 一時的に預けて次の実行で表示する
st.header("試合結果を登録")
if "form_no" not in st.session_state:
    st.session_state.form_no = 0
form_no = st.session_state.form_no

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

fmt = format_selector(key="singles_format")
submitted = False
if fmt is not None:
    with st.form("match_form"):
        opponent = st.text_input("対戦相手", key=f"singles_opponent_{form_no}")
        sets = score_inputs("自分", "相手", key=f"singles_{form_no}", fmt=fmt)
        submitted = st.form_submit_button("登録", type="primary", width="stretch")

if submitted:
    if not opponent:
        st.error("対戦相手を入力してください")
    else:
        result = classify_sets(sets, fmt)
        if result["status"] == "rejected":
            st.error("登録できませんでした: " + "; ".join(result["notes"]))
        else:
            st.session_state.matches.append(
                {"opponent": opponent, "sets": result["sets"], "format": fmt})
            st.session_state.flash = f"{opponent} 戦を登録しました"
            st.session_state.form_no += 1
            st.rerun()

# --- CSVからまとめて読み込み --------------------------------------------------
st.header("CSVから読み込み")
uploaded = st.file_uploader("opponent,sets列(任意でformat列)を持つCSVファイル", type="csv")
if uploaded is not None:
    text = uploaded.getvalue().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    new_matches, corrected_log, rejected_log = matches_from_csv_rows(reader)
    st.session_state.matches.extend(new_matches)
    st.success(f"{len(new_matches)}試合を取り込みました")

    if corrected_log:
        with st.expander(f"補正して採用したデータ（{len(corrected_log)}件）"):
            for item in corrected_log:
                st.write(f"{item['row']}行目 ({item['opponent']}, 元データ: {item['raw']}): "
                         + "; ".join(item["notes"]))

    if rejected_log:
        with st.expander(f"却下したデータ（{len(rejected_log)}件、集計対象外）"):
            for item in rejected_log:
                st.write(f"{item['row']}行目 ({item['opponent']}, 元データ: {item['raw']}): "
                         + "; ".join(item["notes"]))

# --- 登録済み試合の一覧・集計 --------------------------------------------------
st.header("登録済み試合・集計結果")

if not st.session_state.matches:
    st.info("まだ試合が登録されていません")
else:
    table = pd.DataFrame([
        {
            "対戦相手": m["opponent"],
            "形式": MATCH_FORMATS[m.get("format", "one_set")]["label"],
            "セット結果": _sets_to_text(m["sets"]),
            "勝敗": RESULT_LABELS[match_result(m)],
        }
        for m in st.session_state.matches
    ])
    st.dataframe(table, width="stretch")

    col1, col2, col3 = st.columns(3)
    col1.metric("総試合数", len(st.session_state.matches))
    col2.metric("勝率", f"{win_rate(st.session_state.matches):.1%}")
    col3.metric("ゲーム獲得率", f"{game_win_rate(st.session_state.matches):.1%}")

    st.subheader("対戦相手別勝率")
    rate_by_opponent = win_rate_by_opponent(st.session_state.matches)
    chart_df = pd.DataFrame({"勝率": rate_by_opponent})
    st.bar_chart(chart_df, color="#2a78d6")  # dataviz検証済みパレット slot1 blue

    st.subheader("CSVとして保存")
    export_df = pd.DataFrame([
        {"opponent": m["opponent"], "sets": _sets_to_text(m["sets"]),
         "format": MATCH_FORMATS[m.get("format", "one_set")]["label"]}
        for m in st.session_state.matches
    ])
    st.download_button(
        "CSVをダウンロード",
        data=export_df.to_csv(index=False),
        file_name="matches.csv",
        mime="text/csv",
    )

    if st.button("登録済みデータをすべて削除"):
        st.session_state.matches = []
        st.rerun()
