# セット結果の入力部品 - スマホでも押しやすい「数字を選ぶ」入力欄
#
# シングルス(singles_page.py)とダブルス(doubles_page.py)の両方から使う共通部品。
# COBOLのCOPY句のように、同じ入力欄の定義を1か所にまとめている。
#
# 【スマホ向けの工夫】
# - 文字入力(6-3,4-6)ではなく、セットごとに0〜7の数字を選ぶ方式にした。
#   キーボードの数字・記号切り替えが不要になり、打ち間違いも起こらない
# - selectboxは filter_mode=None で検索入力を止めている。止めないと、
#   タップしただけでスマホのキーボードが出てきて画面が隠れてしまう
# - 「自分」と「相手」の欄は横並びの容器(container(horizontal=True, wrap=False))に入れる。
#   st.columnsは画面幅が狭いと縦に積み重なってしまうため使わない
#
# 【登録後に入力欄を空に戻す方法】
# 呼び出し側で key に通し番号を含め、登録が成功したら番号を進める。
# Streamlitは key が変わると別の入力欄とみなして新しく作り直すので、空の状態に戻る。
# (session_stateから値を消す方法では、ブラウザ側に残った値が送り直されて消えなかった)
#
# 入力値の妥当性判定はここでは行わず、tennis_stats.classify_setsに任せる
# (画面部品と判定ロジックの分離)
#
# 【試合形式(2026-10-12追加)】
# 最初に1回だけ形式を選び、以降の試合はその形式を引き継ぐ。途中で形式が変わったときだけ
# 「試合形式を変更」を押して選び直す(何度でも可)。形式は1試合ごとに記録する。

import streamlit as st

from tennis_stats import MATCH_FORMATS


def _format_label(fmt):
    return MATCH_FORMATS[fmt]["label"]


def format_selector(key):
    """現在の試合形式を返す。まだ決まっていない(または変更中の)ときは選択画面を出して None を返す。
    呼び出し側は None の間はスコア入力欄を出さないこと。

    st.session_state[key] に決定済みの形式、[key + "_editing"] に「変更中か」を保持する
    """
    editing_key = f"{key}_editing"
    current = st.session_state.get(key)

    if current is None or st.session_state.get(editing_key):
        st.markdown("**試合形式を選んでください**" if current is None
                    else "**新しい試合形式を選んでください**")
        options = list(MATCH_FORMATS)
        choice = st.radio(
            "試合形式", options, format_func=_format_label, label_visibility="collapsed",
            index=options.index(current) if current else 0, key=f"{key}_choice",
        )
        with st.container(horizontal=True):
            if st.button("この形式で決定", type="primary", key=f"{key}_ok"):
                st.session_state[key] = choice
                st.session_state[editing_key] = False
                st.rerun()
            if current is not None and st.button("取り消し", key=f"{key}_cancel"):
                st.session_state[editing_key] = False
                st.rerun()
        return None

    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown(f"試合形式: **{_format_label(current)}**")
        if st.button("試合形式を変更", key=f"{key}_change"):
            st.session_state[editing_key] = True
            st.rerun()
    return current


def score_inputs(own_label, opp_label, key, fmt):
    """試合形式の最大セット数分の入力欄を表示し、[(own, opp), ...]を返す。
    未選択の欄は None のまま返す(classify_sets側で却下する)。
    セット数は形式で決まる(3セットマッチは3セット分、他は1セット)ので、選択欄は出さない。
    選べるゲーム数は試合形式ごとの上限まで(1セットマッチなら0〜7、4ゲーム系なら0〜4)"""
    set_count = MATCH_FORMATS[fmt]["max_sets"]
    game_options = list(range(MATCH_FORMATS[fmt]["max_games"] + 1))
    # 形式を変えたら選択肢が変わるので、key に形式を含めて入力欄を作り直す
    key = f"{key}_{fmt}"
    sets = []
    for i in range(set_count):
        if set_count == 1:
            pass  # 1セットで固定の形式では「第1セット」の見出しは不要
        elif i == 2:
            st.markdown("**第3セット**(1-1のときだけ入力)")
        else:
            st.markdown(f"**第{i + 1}セット**")
        with st.container(horizontal=True, wrap=False):
            own = st.selectbox(
                own_label, game_options, index=None, placeholder="選択",
                filter_mode=None, key=f"{key}_own_{i}",
            )
            opp = st.selectbox(
                opp_label, game_options, index=None, placeholder="選択",
                filter_mode=None, key=f"{key}_opp_{i}",
            )
        sets.append((own, opp))
    return sets

