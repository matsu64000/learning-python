# ダブルス対戦モード - プレイヤー登録→対戦カード決定→結果入力→個人集計のループ
#
# 【設計方針】
# 判定ロジック(classify_line)は既存のtennis_stats.pyをそのまま使う。対戦カードの
# 決定・個人集計はdoubles.pyに切り出し、このファイルは「画面の状態遷移」だけを
# 担当する(app.pyと同じ、ロジックとUIを分離する方針)
#
# 【仲間との共有(2026-10-18)】
# 対戦データ(メンバ・対戦履歴・対戦カードなど)は、shared_store.DoublesStore に置き、
# st.cache_resource で1つだけ作ったものを、アプリを開いている全員で使う。
# 以前は st.session_state に入れていたため、スマホごとに別のデータになっていた。
# - 書き換えはすべて store のメソッド経由(鍵をかけた中で行う)。失敗したら理由が返る
# - 画面は store.snapshot() のコピーを見て描く
# - 5秒ごとに版数(store.version)だけを確認し、変わっていたら画面全体を描き直す
#   (ほかの人の登録が、何もしなくても自分の画面に反映される)
# - 入力途中のスコア・試合形式・入力欄の開閉などは、今までどおり各自の session_state
#
# 【状態遷移】共有データで3段階を判断する:
#   1. 登録中(current is None かつ history が空) : プレイヤー登録を受け付ける
#   2. 進行中(finished が False) : 対戦カードの提示→結果入力の繰り返し。
#      結果を登録すると、すぐに次の対戦カードを自動で表示する(2026-10-03変更)。
#      「ここで終了する」ボタンはいつでも押せ、押すとその時点の対戦カードは破棄する
#   3. 終了(finished が True) : 最終の個人成績だけを表示する
#
# 【メンバーの入れ替わり(2026-10-12追加)】
# - 開始前: 入力ミスの訂正用に「最後の1人を削除する」
# - 途中で抜ける: 抜けた人は left に移し、組み合わせの対象からは外すが、
#   個人成績・対戦履歴には残す(履歴は消さない)。記録がまだない人は消すだけ
# - 途中から加わる: offsets に「下駄」(doubles.join_offset)を記録し、
#   他の人と同じペースで出場させる。抜けた人が同じ名前で戻った場合は成績を引き継ぐ
# - 4人を下回ったら対戦カードを出さず、終了(またはメンバー追加)を促す
#
# Streamlitは毎回スクリプトを上から実行するので、ボタンを押したときに呼ぶ関数は
# ボタンより上で定義しておく(下で定義した関数は、その時点ではまだ存在しない)

from datetime import datetime

import pandas as pd
import streamlit as st

from doubles import player_summary
from score_input import format_selector, read_scores, score_inputs
from shared_store import DoublesStore
from tennis_stats import MATCH_FORMATS, classify_sets

REFRESH_SECONDS = 5

st.set_page_config(page_title="ダブルス対戦 | てにろぐ君", page_icon="🎾")
st.title("🎾 ダブルス対戦")


@st.cache_resource
def get_store():
    """全員で共有する DoublesStore を1つだけ作る(2回目以降は同じものが返る)"""
    return DoublesStore()


store = get_store()
data = store.snapshot()
st.session_state.doubles_seen_version = data["version"]

players = data["players"]
left = data["left"]
history = data["history"]
current = data["current"]
finished = data["finished"]
started = bool(history) or current is not None


@st.fragment(run_every=REFRESH_SECONDS)
def _watch_for_updates():
    """数秒ごとにこの部分だけが動き、ほかの人の変更があれば画面全体を描き直す"""
    if store.version != st.session_state.get("doubles_seen_version"):
        st.rerun(scope="app")


_watch_for_updates()


def _done(error, success=None):
    """store の操作結果を次の画面に表示するよう覚えてから、画面を描き直す"""
    if error:
        st.session_state.doubles_error = error
    elif success:
        st.session_state.doubles_flash = success
    st.rerun()


# --- 1. プレイヤー登録 --------------------------------------------------------
st.header("プレイヤー登録")
if not started:
    with st.form("player_form", clear_on_submit=True):
        name = st.text_input("プレイヤー名")
        add = st.form_submit_button("追加")
    if add:
        _done(store.add_player(name))

    if players:
        st.write(f"登録済み({len(players)}人): " + "、".join(players))
        if st.button("最後の1人を削除する"):
            _done(store.remove_last_player(players[-1]))
elif not finished:
    st.write(f"メンバ({len(players)}人): " + "、".join(players))
    if left:
        st.caption("途中で抜けたメンバ: " + "、".join(left))

    # 「抜ける」「追加する」は、押したほうの入力欄だけを開く
    mode = st.session_state.get("doubles_member_mode")
    if mode is None:
        with st.container(horizontal=True):
            if st.button("抜けるメンバがいる場合"):
                st.session_state.doubles_member_mode = "leave"
                st.rerun()
            if st.button("メンバを追加する場合"):
                st.session_state.doubles_member_mode = "join"
                st.rerun()
    elif mode == "leave":
        leaving = st.selectbox(
            "抜けるメンバを選んでください", players,
            index=None, placeholder="選択", filter_mode=None,
        )
        if history:
            st.caption("抜けたメンバのここまでの成績と対戦履歴は残ります")
        with st.container(horizontal=True):
            if st.button("以降の試合でこのメンバを外す", type="primary", disabled=leaving is None):
                st.session_state.doubles_member_mode = None
                _done(store.remove_player(leaving), f"{leaving} さんを以降の試合から外しました")
            if st.button("やめる"):
                st.session_state.doubles_member_mode = None
                st.rerun()
    else:  # join
        if left:
            st.caption("抜けたメンバが戻る場合は、同じ名前で入力すると成績を引き継ぎます")
        joining = st.text_input("追加するメンバの名前")
        with st.container(horizontal=True):
            if st.button("このメンバを追加する", type="primary"):
                error = store.add_player_midway(joining)
                if error is None:
                    st.session_state.doubles_member_mode = None
                _done(error, f"{joining} さんを追加しました")
            if st.button("やめる"):
                st.session_state.doubles_member_mode = None
                st.rerun()

if "doubles_error" in st.session_state:
    st.error(st.session_state.pop("doubles_error"))
if "doubles_flash" in st.session_state:
    st.success(st.session_state.pop("doubles_flash"))


def _score_key(round_no):
    return f"doubles_{round_no - 1}"


def _submit_result(shown_round, fmt):
    """結果登録ボタンの on_click。画面を描き直す前に呼ばれるので、
    shown_round は「入力していた人の画面に出ていた試合番号」のまま届く"""
    result = classify_sets(read_scores(_score_key(shown_round), fmt), fmt)
    if result["status"] == "rejected":
        st.session_state.doubles_error = "登録できませんでした: " + "; ".join(result["notes"])
        return
    # 第何試合の結果かを一緒に渡す。ほかの人が先に登録していたら断られる
    error = store.record_result(shown_round, result["sets"], fmt)
    if error:
        st.session_state.doubles_error = error


def _finish_button(label, **kwargs):
    """終了は全員の画面に効くので、押したら確認を1回はさむ"""
    if st.session_state.get("doubles_confirm") == "finish":
        st.warning("対戦を終了すると、全員の画面で対戦が終わります。終了しますか？")
        with st.container(horizontal=True):
            if st.button("終了する", type="primary"):
                st.session_state.doubles_confirm = None
                _done(store.finish())
            if st.button("やめる", key="cancel_finish"):
                st.session_state.doubles_confirm = None
                st.rerun()
    elif st.button(label, **kwargs):
        st.session_state.doubles_confirm = "finish"
        st.rerun()


# --- 2. 対戦の進行 ------------------------------------------------------------
if not finished:
    if started and len(players) < 4:
        st.warning(f"メンバが{len(players)}人になり、4人を下回ったため対戦を続けられません。"
                   "終了して成績を確認してください(メンバが加われば再開できます)")
        _finish_button("終了して成績を見る", type="primary", width="stretch")
    elif len(players) < 4:
        st.info("ダブルスには4人以上の登録が必要です")
    elif not started:
        if st.button("対戦を開始する", type="primary", width="stretch"):
            _done(store.start())
    else:
        round_no = len(history) + 1
        st.header(f"第{round_no}試合")

        st.subheader(f"{'・'.join(current['team_a'])}  vs  {'・'.join(current['team_b'])}")
        if current["resting"]:
            st.caption("休み: " + "、".join(current["resting"]))

        fmt = format_selector(key="doubles_format")
        if fmt is not None:
            with st.form("score_form"):
                score_inputs(
                    "・".join(current["team_a"]), "・".join(current["team_b"]),
                    # 試合ごとに別の key にして、前の試合の入力値を持ち越さない
                    key=_score_key(round_no), fmt=fmt,
                )
                # 「画面に出ていた試合番号」をボタンに覚えさせる(args)。
                # 以前は押した後の描き直しで試合番号を数え直していたため、ちょうどその間に
                # ほかの人が登録すると「次の試合」として扱われてしまい、楽観ロックが
                # 効いていなかった(2026-10-18、ブラウザ2画面での確認で発覚)
                st.form_submit_button(
                    "結果を登録して次の試合へ", type="primary", width="stretch",
                    on_click=_submit_result, args=(round_no, fmt),
                )

        st.divider()
        _finish_button("ここで終了して成績を見る", width="stretch")
else:
    st.success("対戦を終了しました")

# --- 3. 個人成績 ---------------------------------------------------------------
# 並び順は 勝ち数 → セット差 の多い順。表の列が多いので、スマホでは横スクロールになる
if history:
    heading = "個人成績（最終結果）" if finished else "個人成績（ここまでの成績）"
    st.header(heading)

    summary = player_summary(players + left, history)
    table = pd.DataFrame([
        {
            "プレイヤー": p + ("（抜け）" if p in left else ""),
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

    with st.expander(f"対戦履歴（{len(history)}試合）"):
        for i, r in enumerate(history, start=1):
            sets_text = ",".join(f"{a}-{b}" for a, b in r["sets"])
            resting_note = f"（休み: {'、'.join(r['resting'])}）" if r["resting"] else ""
            fmt_label = MATCH_FORMATS[r.get("format", "one_set")]["label"]
            st.write(f"第{i}試合 [{fmt_label}]: {'・'.join(r['team_a'])} vs {'・'.join(r['team_b'])} "
                      f"→ {sets_text}{resting_note}")

# --- 4. バックアップ(途中経過の保存・再開) ---------------------------------------
# 共有データはアプリの再起動・休止で消えるので、その備え
st.divider()
with st.expander("途中経過の保存・再開"):
    st.caption("アプリが再起動するとデータが消えることがあります。"
               "ときどき保存しておくと、消えたときに保存した時点から再開できます")
    if players or left:
        st.download_button(
            "途中経過をファイルに保存する", data=store.to_backup(),
            file_name=f"tenilog_doubles_{datetime.now():%Y%m%d_%H%M}.json",
            mime="application/json",
        )
    uploaded = st.file_uploader("保存したファイルから再開する", type=["json"])
    if uploaded is not None:
        st.warning("再開すると、今の全員の画面のデータが、このファイルの内容に置き換わります")
        if st.button("このファイルの内容で再開する", type="primary"):
            _done(store.restore_backup(uploaded.getvalue().decode("utf-8", errors="replace")),
                  "保存したファイルから再開しました")

# --- 5. リセット ------------------------------------------------------------------
if players or left:
    if st.session_state.get("doubles_confirm") == "reset":
        st.warning("リセットすると、全員の画面のメンバ・対戦履歴・成績がすべて消えます。リセットしますか？")
        with st.container(horizontal=True):
            if st.button("リセットする", type="primary"):
                st.session_state.doubles_confirm = None
                st.session_state.doubles_member_mode = None
                _done(store.reset())
            if st.button("やめる", key="cancel_reset"):
                st.session_state.doubles_confirm = None
                st.rerun()
    elif st.button("すべてリセットして最初からやり直す"):
        st.session_state.doubles_confirm = "reset"
        st.rerun()
