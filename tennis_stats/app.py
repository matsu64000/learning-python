# テニス試合結果集計 - 画面の入口(目次)
#
# アプリを開いたときに最初に出す画面と、サイドバーのメニューの並びをここで決める。
# 実際に集まったメンバーでダブルスを回す使い方が中心なので、ダブルス対戦を
# 最初の画面(default=True)にし、シングルスの集計はメニューから選ぶ形にした(2026-10-03)。
# 以前はpages/フォルダに置いたファイルが自動でメニューになる方式だったが、
# それだと最初の画面がapp.py(シングルス)に固定されるため、st.navigationで明示的に指定する
#
# 2026-10-12: アプリ名を「てにろぐ君」とし、ロゴ(assets/のSVG)と「このアプリの紹介」画面を追加
#
# 実行方法: streamlit run app.py

import hashlib
import hmac
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"
AUTH_COOKIE = "tenilog_auth"
AUTH_COOKIE_DAYS = 30

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

# ロゴは全画面の左上に出る(サイドバーを閉じたとき・スマホでは小さいアイコン版)
st.logo(str(ASSETS / "logo_wide.svg"), icon_image=str(ASSETS / "logo_icon.svg"), size="large")


# --- 合言葉の入口(2026-10-18) ------------------------------------------------------
# インターネットに公開すると、URLを知っている人は誰でも開けてしまう。仲間の名前が
# 見えないように、最初に合言葉を聞く。
# - 合言葉そのものは Streamlit の Secrets(サーバ側の設定、passphrase という名前)に置き、
#   GitHubには載せない。手元では .streamlit/secrets.toml(.gitignore対象)に書く
# - 合っていたら、そのスマホに「合言葉の指紋」(ハッシュ値)をクッキーとして30日間残し、
#   次からは聞かない。クッキーには合言葉そのものは入れない。合言葉を変えると指紋も
#   変わるので、全員にもう一度聞くことになる
# - Secrets に合言葉が設定されていなければ、入口は出さない(手元での開発用)
def _configured_passphrase():
    try:
        return st.secrets.get("passphrase")
    except Exception:  # secrets.toml が無いとき
        return None


def _fingerprint(passphrase):
    return hashlib.sha256(f"tenilog:{passphrase}".encode("utf-8")).hexdigest()


def _passphrase_gate():
    """合言葉が確認できていれば True。まだなら入力欄を出して False"""
    passphrase = _configured_passphrase()
    if not passphrase:
        return True
    expected = _fingerprint(passphrase)

    if st.session_state.pop("auth_set_cookie", False):
        # 合言葉が合った直後の1回だけ、ブラウザにクッキーを書く
        st.html(
            f"""<script>
            window.parent.document.cookie =
                "{AUTH_COOKIE}={expected}; max-age={AUTH_COOKIE_DAYS * 86400}; path=/; samesite=strict";
            </script>""",
            unsafe_allow_javascript=True,
        )
    if st.session_state.get("auth_ok") or hmac.compare_digest(
        st.context.cookies.get(AUTH_COOKIE, ""), expected
    ):
        st.session_state.auth_ok = True
        return True

    st.title("🎾 てにろぐ君")
    with st.form("passphrase_form"):
        entered = st.text_input("合言葉", type="password")
        ok = st.form_submit_button("入る", type="primary")
    if ok:
        if hmac.compare_digest(_fingerprint(entered), expected):
            st.session_state.auth_ok = True
            st.session_state.auth_set_cookie = True
            st.rerun()
        st.error("合言葉が違います")
    return False


if not _passphrase_gate():
    st.stop()

page = st.navigation([
    st.Page("doubles_page.py", title="ダブルス対戦", icon="🎾", default=True),
    st.Page("singles_page.py", title="シングルス集計", icon="📊"),
    st.Page("intro_page.py", title="このアプリの紹介", icon="💡"),
])
page.run()
