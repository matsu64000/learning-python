# テニス試合結果集計 - 画面の入口(目次)
#
# アプリを開いたときに最初に出す画面と、サイドバーのメニューの並びをここで決める。
# 実際に集まったメンバーでダブルスを回す使い方が中心なので、ダブルス対戦を
# 最初の画面(default=True)にし、シングルスの集計はメニューから選ぶ形にした(2026-10-03)。
# 以前はpages/フォルダに置いたファイルが自動でメニューになる方式だったが、
# それだと最初の画面がapp.py(シングルス)に固定されるため、st.navigationで明示的に指定する
#
# 実行方法: streamlit run app.py

import streamlit as st

# ブラウザの自動翻訳を止める(2026-10-12)。Streamlitはページの言語を「英語(lang="en")」と
# 宣言するため、スマホのChromeが英語のページと判断して日本語を「翻訳」し、
# 「抜く」→「抜け出す」、「フリー」→「自由な」のように文言が崩れていた。
# ページの言語を日本語にし、翻訳しない印(translate="no")を付ける
st.html(
    """<script>
    const root = window.parent.document.documentElement;
    root.lang = "ja";
    root.setAttribute("translate", "no");
    root.classList.add("notranslate");
    </script>""",
    unsafe_allow_javascript=True,
)

page = st.navigation([
    st.Page("doubles_page.py", title="ダブルス対戦", icon="🎾", default=True),
    st.Page("singles_page.py", title="シングルス集計", icon="📊"),
])
page.run()
