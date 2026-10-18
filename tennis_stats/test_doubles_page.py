"""doubles_page.py(画面)のテスト。Streamlitのテスト機能 AppTest で画面を動かす。

2つの AppTest は「2人のスマホ」の代わり。同じプロセスの中で動くので、
st.cache_resource の共有データ(DoublesStore)を2人で共有する。

ブラウザ2画面で確かめようとすると、5秒ごとの自動更新が先に来るかどうかで結果が
変わってしまい、「ほぼ同時に押した」状況を狙って作れなかった。AppTest なら
「Bさんの画面を描き直さないまま登録ボタンを押す」を確実に再現できる
"""

import streamlit as st
from streamlit.testing.v1 import AppTest

PAGE = "doubles_page.py"


def _new_phone():
    return AppTest.from_file(PAGE, default_timeout=10).run()


def _click(at, label):
    next(b for b in at.button if b.label == label).click().run()


def _setup_round1(at):
    for name in ["田中", "佐藤", "鈴木", "高橋"]:
        at.text_input[0].input(name)
        _click(at, "追加")
    _click(at, "対戦を開始する")
    _click(at, "この形式で決定")


def _enter_score(at, own, opp):
    at.selectbox[0].set_value(own)
    at.selectbox[1].set_value(opp)


def setup_function():
    st.cache_resource.clear()  # テストごとに共有データを空にする


def test_players_added_on_one_phone_appear_on_another():
    a, b = _new_phone(), _new_phone()
    a.text_input[0].input("田中")
    _click(a, "追加")
    b.run()  # Bさんの画面が描き直された(自動更新の代わり)
    assert any("田中" in m.value for m in b.markdown)


def test_same_round_registered_twice_only_first_counts():
    a = _new_phone()
    _setup_round1(a)
    b = _new_phone()
    _click(b, "この形式で決定")  # 試合形式はスマホごとに選ぶ

    # 2人とも第1試合の画面でスコアを入力
    _enter_score(a, 6, 2)
    _enter_score(b, 4, 6)

    # Bさんが先に登録
    _click(b, "結果を登録して次の試合へ")
    # Aさんは画面が描き直される前(第1試合のまま)に登録ボタンを押す
    _click(a, "結果を登録して次の試合へ")

    assert any("先に登録しました" in e.value for e in a.error)
    history = [m.value for m in a.markdown if "第1試合 [" in m.value]
    assert len(history) == 1 and "4-6" in history[0]  # Bさんの結果だけが残る
    assert not any("第2試合 [" in m.value for m in a.markdown)  # 第2試合として登録されていない


def test_reset_needs_confirmation():
    a = _new_phone()
    a.text_input[0].input("田中")
    _click(a, "追加")
    _click(a, "すべてリセットして最初からやり直す")
    assert any("田中" in m.value for m in a.markdown)  # まだ消えていない
    _click(a, "リセットする")
    assert not any("田中" in m.value for m in a.markdown)
