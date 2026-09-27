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
# 実行方法: streamlit run app.py

import csv
import io

import pandas as pd
import streamlit as st

from tennis_stats import (
    classify_line,
    did_win,
    game_win_rate,
    matches_from_csv_rows,
    win_rate,
    win_rate_by_opponent,
)

st.set_page_config(page_title="テニス試合結果集計", page_icon="🎾")
st.title("🎾 テニス試合結果集計")

if "matches" not in st.session_state:
    st.session_state.matches = []


def _sets_to_text(sets):
    return ",".join(f"{own}-{opp}" for own, opp in sets)


# --- 1試合ずつ登録 -----------------------------------------------------------
st.header("試合結果を登録")
with st.form("match_form", clear_on_submit=True):
    opponent = st.text_input("対戦相手")
    sets_text = st.text_input("セット結果（例: 6-3,4-6,6-2）")
    submitted = st.form_submit_button("登録")

if submitted:
    if not opponent or not sets_text:
        st.error("対戦相手とセット結果の両方を入力してください")
    else:
        result = classify_line(sets_text)
        if result["status"] == "rejected":
            st.error("登録できませんでした: " + "; ".join(result["notes"]))
        else:
            if result["status"] == "corrected":
                st.warning("補正して登録しました: " + "; ".join(result["notes"]))
            else:
                st.success(f"{opponent} 戦を登録しました")
            st.session_state.matches.append({"opponent": opponent, "sets": result["sets"]})

# --- CSVからまとめて読み込み --------------------------------------------------
st.header("CSVから読み込み")
uploaded = st.file_uploader("opponent,sets列を持つCSVファイル", type="csv")
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
            "セット結果": _sets_to_text(m["sets"]),
            "勝敗": "勝ち" if did_win(m) else "負け",
        }
        for m in st.session_state.matches
    ])
    st.dataframe(table, use_container_width=True)

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
        {"opponent": m["opponent"], "sets": _sets_to_text(m["sets"])}
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
