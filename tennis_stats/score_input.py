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

import streamlit as st

GAME_OPTIONS = list(range(8))  # 1セットのゲーム数として選べる値(0〜7)


def set_count_selector(key):
    """何セット分の入力欄を出すかを選ぶ。フォームの外に置くこと
    (フォーム内のウィジェットは「登録」を押すまで画面に反映されないため)"""
    return st.radio(
        "セット数", [1, 2, 3], horizontal=True, key=key,
        format_func=lambda n: f"{n}セット",
    )


def score_inputs(set_count, own_label, opp_label, key):
    """セット数分の入力欄を表示し、[(own, opp), ...]を返す。
    未選択の欄は None のまま返す(classify_sets側で却下する)"""
    sets = []
    for i in range(set_count):
        st.markdown(f"**第{i + 1}セット**")
        with st.container(horizontal=True, wrap=False):
            own = st.selectbox(
                own_label, GAME_OPTIONS, index=None, placeholder="選択",
                filter_mode=None, key=f"{key}_own_{i}",
            )
            opp = st.selectbox(
                opp_label, GAME_OPTIONS, index=None, placeholder="選択",
                filter_mode=None, key=f"{key}_opp_{i}",
            )
        sets.append((own, opp))
    return sets

