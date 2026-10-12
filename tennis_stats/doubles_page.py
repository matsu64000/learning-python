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
#      結果を登録すると、すぐに次の対戦カードを自動で表示する(2026-10-03変更)。
#      「ここで終了する」ボタンはいつでも押せ、押すとその時点の対戦カードは破棄する
#   3. 終了(doubles_finished が True) : 最終の個人成績だけを表示する
#
# 【メンバーの入れ替わり(2026-10-12追加)】
# doubles_players は「今プレーしているメンバー」。
# - 開始前: 入力ミスの訂正用に「最後の1人を削除する」
# - 途中で抜ける: 抜けた人は doubles_left に移し、組み合わせの対象からは外すが、
#   個人成績・対戦履歴には残す(履歴は消さない)。記録がまだない人は消すだけ
# - 途中から加わる: doubles_offsets に「下駄」(doubles.join_offset)を記録し、
#   他の人と同じペースで出場させる。抜けた人が同じ名前で戻った場合は成績を引き継ぐ
# - 4人を下回ったら対戦カードを出さず、終了(またはメンバー追加)を促す
#
# Streamlitは毎回スクリプトを上から実行するので、ボタンを押したときに呼ぶ関数は
# ボタンより上で定義しておく(下で定義した関数は、その時点ではまだ存在しない)

import pandas as pd
import streamlit as st

from doubles import generate_matchup, join_offset, player_summary
from score_input import format_selector, score_inputs
from tennis_stats import MATCH_FORMATS, classify_sets

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
if "doubles_left" not in st.session_state:
    st.session_state.doubles_left = []
if "doubles_offsets" not in st.session_state:
    st.session_state.doubles_offsets = {}

started = bool(st.session_state.doubles_history) or st.session_state.doubles_current is not None
players = st.session_state.doubles_players


def _next_matchup():
    st.session_state.doubles_current = generate_matchup(
        players, st.session_state.doubles_history, offsets=st.session_state.doubles_offsets,
    )


def _remove_player(name):
    players.remove(name)
    # 記録が1試合でもあれば「抜けたメンバ」として成績を残す。まだ記録がなければ消すだけ
    if st.session_state.doubles_history:
        st.session_state.doubles_left.append(name)
    current = st.session_state.doubles_current
    if current is None:
        return
    # 表示中の対戦カードに入っていたら、残りのメンバーで組み直す(4人未満なら組まない)
    if name in current["team_a"] + current["team_b"]:
        if len(players) >= 4:
            _next_matchup()
        else:
            st.session_state.doubles_current = None
    else:
        current["resting"] = [p for p in current["resting"] if p != name]


def _add_player_midway(name):
    if name in st.session_state.doubles_left:
        st.session_state.doubles_left.remove(name)  # 抜けた人が戻ってきた
    players.append(name)
    st.session_state.doubles_offsets[name] = join_offset(
        name, players, st.session_state.doubles_history, st.session_state.doubles_offsets,
    )
    current = st.session_state.doubles_current
    if current is not None:
        current["resting"] = sorted(current["resting"] + [name])  # 今の試合は休み
    elif len(players) >= 4:
        _next_matchup()  # 4人を下回って止まっていたのを再開


def _name_error(name):
    if not name:
        return "プレイヤー名を入力してください"
    if name in players:
        return f"{name} はすでに登録されています"
    return None


# --- 1. プレイヤー登録 --------------------------------------------------------
st.header("プレイヤー登録")
if not started:
    with st.form("player_form", clear_on_submit=True):
        name = st.text_input("プレイヤー名")
        add = st.form_submit_button("追加")
    if add:
        error = _name_error(name)
        if error:
            st.error(error)
        else:
            players.append(name)
            st.rerun()

    if players:
        st.write(f"登録済み({len(players)}人): " + "、".join(players))
        if st.button("最後の1人を削除する"):
            players.pop()
            st.rerun()
elif not st.session_state.doubles_finished:
    st.write(f"メンバ({len(players)}人): " + "、".join(players))
    if st.session_state.doubles_left:
        st.caption("途中で抜けたメンバ: " + "、".join(st.session_state.doubles_left))

    # 「抜ける」「加わる」は、押したほうの入力欄だけを開く
    mode = st.session_state.get("doubles_member_mode")
    if mode is None:
        with st.container(horizontal=True):
            if st.button("抜けるメンバがいる場合"):
                st.session_state.doubles_member_mode = "leave"
                st.rerun()
            if st.button("加わるメンバがいる場合"):
                st.session_state.doubles_member_mode = "join"
                st.rerun()
    elif mode == "leave":
        leaving = st.selectbox(
            "抜けるメンバを選んでください", players,
            index=None, placeholder="選択", filter_mode=None,
        )
        if st.session_state.doubles_history:
            st.caption("抜けたメンバのここまでの成績と対戦履歴は残ります")
        with st.container(horizontal=True):
            if st.button("このメンバを抜く", type="primary", disabled=leaving is None):
                _remove_player(leaving)
                st.session_state.doubles_member_mode = None
                st.session_state.doubles_flash = f"{leaving} さんが抜けました"
                st.rerun()
            if st.button("やめる"):
                st.session_state.doubles_member_mode = None
                st.rerun()
    else:  # join
        if st.session_state.doubles_left:
            st.caption("抜けたメンバが戻る場合は、同じ名前で入力すると成績を引き継ぎます")
        joining = st.text_input("加わるメンバの名前")
        with st.container(horizontal=True):
            if st.button("このメンバを加える", type="primary"):
                error = _name_error(joining)
                if error:
                    st.error(error)
                else:
                    _add_player_midway(joining)
                    st.session_state.doubles_member_mode = None
                    st.session_state.doubles_flash = f"{joining} さんが加わりました"
                    st.rerun()
            if st.button("やめる"):
                st.session_state.doubles_member_mode = None
                st.rerun()

if "doubles_flash" in st.session_state:
    st.success(st.session_state.pop("doubles_flash"))

# --- 2. 対戦の進行 ------------------------------------------------------------
if not st.session_state.doubles_finished:
    if started and len(players) < 4:
        st.warning(f"メンバが{len(players)}人になり、4人を下回ったため対戦を続けられません。"
                   "終了して成績を確認してください(メンバが加われば再開できます)")
        if st.button("終了して成績を見る", type="primary", width="stretch"):
            st.session_state.doubles_current = None
            st.session_state.doubles_finished = True
            st.rerun()
    elif len(players) < 4:
        st.info("ダブルスには4人以上の登録が必要です")
    elif not started:
        if st.button("対戦を開始する", type="primary", width="stretch"):
            _next_matchup()
            st.rerun()
    else:
        round_no = len(st.session_state.doubles_history) + 1
        st.header(f"第{round_no}試合")

        matchup = st.session_state.doubles_current
        st.subheader(f"{'・'.join(matchup['team_a'])}  vs  {'・'.join(matchup['team_b'])}")
        if matchup["resting"]:
            st.caption("休み: " + "、".join(matchup["resting"]))

        fmt = format_selector(key="doubles_format")
        submitted = False
        if fmt is not None:
            with st.form("score_form"):
                sets = score_inputs(
                    "・".join(matchup["team_a"]), "・".join(matchup["team_b"]),
                    # 試合ごとに別の key にして、前の試合の入力値を持ち越さない
                    key=f"doubles_{len(st.session_state.doubles_history)}", fmt=fmt,
                )
                submitted = st.form_submit_button(
                    "結果を登録して次の試合へ", type="primary", width="stretch",
                )

        if submitted:
            result = classify_sets(sets, fmt)
            if result["status"] == "rejected":
                st.error("登録できませんでした: " + "; ".join(result["notes"]))
            else:
                st.session_state.doubles_history.append({
                    "team_a": matchup["team_a"],
                    "team_b": matchup["team_b"],
                    "resting": matchup["resting"],
                    "sets": result["sets"],
                    "format": fmt,
                })
                _next_matchup()
                st.rerun()

        st.divider()
        if st.button("ここで終了して成績を見る", width="stretch"):
            st.session_state.doubles_current = None
            st.session_state.doubles_finished = True
            st.rerun()
else:
    st.success("対戦を終了しました")

# --- 3. 個人成績 ---------------------------------------------------------------
# 並び順は 勝ち数 → セット差 の多い順。表の列が多いので、スマホでは横スクロールになる
if st.session_state.doubles_history:
    heading = "個人成績（最終結果）" if st.session_state.doubles_finished else "個人成績（ここまでの成績）"
    st.header(heading)

    summary = player_summary(
        st.session_state.doubles_players + st.session_state.doubles_left,
        st.session_state.doubles_history,
    )
    table = pd.DataFrame([
        {
            "プレイヤー": p + ("（抜け）" if p in st.session_state.doubles_left else ""),
            "試合": s["matches_played"],
            "勝": s["wins"],
            "負": s["losses"],
            "分": s["draws"],
            "得セット": s["sets_won"],
            "失セット": s["sets_lost"],
            "セット差": s["set_diff"],
            "勝率": s["win_rate"],
            "ゲーム獲得率": s["game_win_rate"],
        }
        for p, s in summary.items()
    ]).sort_values(["勝", "セット差"], ascending=False)

    st.dataframe(
        table.style.format({"セット差": "{:+d}", "勝率": "{:.1%}", "ゲーム獲得率": "{:.1%}"}),
        width="stretch", hide_index=True,
    )

    with st.expander(f"対戦履歴（{len(st.session_state.doubles_history)}試合）"):
        for i, r in enumerate(st.session_state.doubles_history, start=1):
            sets_text = ",".join(f"{a}-{b}" for a, b in r["sets"])
            resting_note = f"（休み: {'、'.join(r['resting'])}）" if r["resting"] else ""
            fmt_label = MATCH_FORMATS[r.get("format", "one_set")]["label"]
            st.write(f"第{i}試合 [{fmt_label}]: {'・'.join(r['team_a'])} vs {'・'.join(r['team_b'])} "
                      f"→ {sets_text}{resting_note}")

if st.session_state.doubles_players or st.session_state.doubles_left:
    st.divider()
    if st.button("すべてリセットして最初からやり直す"):
        st.session_state.doubles_players = []
        st.session_state.doubles_history = []
        st.session_state.doubles_current = None
        st.session_state.doubles_finished = False
        st.session_state.doubles_format = None
        st.session_state.doubles_left = []
        st.session_state.doubles_offsets = {}
        st.session_state.doubles_member_mode = None
        st.rerun()
