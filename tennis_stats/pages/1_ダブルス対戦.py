# ダブルス対戦モード - プレイヤー登録→対戦カード決定→結果入力→個人集計のループ
#
# 【設計方針】
# 判定ロジック(classify_line)は既存のtennis_stats.pyをそのまま使う。対戦カードの
# 決定・個人集計はdoubles.pyに切り出し、このファイルは「画面の状態遷移」だけを
# 担当する(app.pyと同じ、ロジックとUIを分離する方針)
#
# 【状態遷移】st.session_stateで3段階を管理する:
#   1. 登録中(doubles_current is None かつ doubles_history が空) : プレイヤー登録を受け付ける
#   2. 進行中(doubles_finished が False) : 対戦カードの提示→結果入力の繰り返し。
#      1試合終わるたびに「次の対戦を組む」か「ここで終了する」かを選べる
#   3. 終了(doubles_finished が True) : 最終の個人成績だけを表示する

import pandas as pd
import streamlit as st

from doubles import generate_matchup, player_summary
from tennis_stats import classify_line

st.set_page_config(page_title="ダブルス対戦", page_icon="🎾")
st.title("🎾 ダブルス対戦")

if "doubles_players" not in st.session_state:
    st.session_state.doubles_players = []
if "doubles_history" not in st.session_state:
    st.session_state.doubles_history = []
if "doubles_current" not in st.session_state:
    st.session_state.doubles_current = None
if "doubles_finished" not in st.session_state:
    st.session_state.doubles_finished = False

started = bool(st.session_state.doubles_history) or st.session_state.doubles_current is not None

# --- 1. プレイヤー登録 --------------------------------------------------------
st.header("プレイヤー登録")
if started:
    st.write("登録メンバー: " + "、".join(st.session_state.doubles_players))
    st.caption("対戦が始まったため登録は締め切りました。やり直す場合は下部のリセットから")
else:
    with st.form("player_form", clear_on_submit=True):
        name = st.text_input("プレイヤー名")
        add = st.form_submit_button("追加")
    if add:
        if not name:
            st.error("プレイヤー名を入力してください")
        elif name in st.session_state.doubles_players:
            st.warning(f"{name} はすでに登録されています")
        else:
            st.session_state.doubles_players.append(name)
            st.rerun()

    if st.session_state.doubles_players:
        st.write("登録済み(" + f"{len(st.session_state.doubles_players)}人" + "): "
                  + "、".join(st.session_state.doubles_players))
        if st.button("最後の1人を取り消す"):
            st.session_state.doubles_players.pop()
            st.rerun()

# --- 2. 対戦の進行 ------------------------------------------------------------
if not st.session_state.doubles_finished:
    if len(st.session_state.doubles_players) < 4:
        st.info("ダブルスには4人以上の登録が必要です")
    else:
        st.header("対戦")

        if st.session_state.doubles_current is None:
            col1, col2 = st.columns(2)
            if col1.button("次の対戦を組む", type="primary"):
                st.session_state.doubles_current = generate_matchup(
                    st.session_state.doubles_players, st.session_state.doubles_history,
                )
                st.rerun()
            if col2.button("ここで終了する"):
                st.session_state.doubles_finished = True
                st.rerun()
        else:
            matchup = st.session_state.doubles_current
            st.subheader(f"{'・'.join(matchup['team_a'])}  vs  {'・'.join(matchup['team_b'])}")
            if matchup["resting"]:
                st.caption("休み: " + "、".join(matchup["resting"]))

            with st.form("score_form"):
                sets_text = st.text_input(
                    f"セット結果（{'・'.join(matchup['team_a'])}側の視点、例: 6-3,4-6,6-2）"
                )
                submitted = st.form_submit_button("試合結果を登録")

            if submitted:
                result = classify_line(sets_text)
                if result["status"] == "rejected":
                    st.error("登録できませんでした: " + "; ".join(result["notes"]))
                else:
                    if result["status"] == "corrected":
                        st.warning("補正して登録しました: " + "; ".join(result["notes"]))
                    st.session_state.doubles_history.append({
                        "team_a": matchup["team_a"],
                        "team_b": matchup["team_b"],
                        "resting": matchup["resting"],
                        "sets": result["sets"],
                    })
                    st.session_state.doubles_current = None
                    st.rerun()
else:
    st.success("対戦を終了しました")

# --- 3. 個人成績 ---------------------------------------------------------------
if st.session_state.doubles_history:
    heading = "個人成績（最終結果）" if st.session_state.doubles_finished else "個人成績（ここまでの成績）"
    st.header(heading)

    summary = player_summary(st.session_state.doubles_players, st.session_state.doubles_history)
    table = pd.DataFrame([
        {
            "プレイヤー": p,
            "対戦数": s["matches_played"],
            "勝率": s["win_rate"],
            "ゲーム獲得率": s["game_win_rate"],
        }
        for p, s in summary.items()
    ]).sort_values("勝率", ascending=False)

    st.dataframe(
        table.style.format({"勝率": "{:.1%}", "ゲーム獲得率": "{:.1%}"}),
        use_container_width=True, hide_index=True,
    )

    with st.expander(f"対戦履歴（{len(st.session_state.doubles_history)}試合）"):
        for i, r in enumerate(st.session_state.doubles_history, start=1):
            sets_text = ",".join(f"{a}-{b}" for a, b in r["sets"])
            resting_note = f"（休み: {'、'.join(r['resting'])}）" if r["resting"] else ""
            st.write(f"第{i}試合: {'・'.join(r['team_a'])} vs {'・'.join(r['team_b'])} "
                      f"→ {sets_text}{resting_note}")

if st.session_state.doubles_players:
    st.divider()
    if st.button("すべてリセットして最初からやり直す"):
        st.session_state.doubles_players = []
        st.session_state.doubles_history = []
        st.session_state.doubles_current = None
        st.session_state.doubles_finished = False
        st.rerun()
