# ダブルス対戦の共有データ置き場 - 仲間のスマホ全員が同じデータを見るための仕組み(2026-10-18)
#
# 【なぜ必要か】
# 以前は st.session_state にすべてを入れていた。session_state はブラウザ(スマホ)ごとに
# 別々なので、COBOLでいえば「ファイルに書かずにWORKING-STORAGEだけで処理している」状態で、
# 仲間のスマホにはそれぞれ別のデータが見えていた。
# このファイルの DoublesStore は「全員が見る共有領域」(COMMON領域・マスタファイルの役)。
# 画面(doubles_page.py)は st.cache_resource で1つだけ作ったものを、全員で使い回す。
#
# 【共有するもの/しないもの】
# 共有する: メンバ、抜けたメンバ、途中参加の下駄、対戦履歴、表示中の対戦カード、終了したか
# 共有しない(各自の session_state に残す): 入力途中のスコア、試合形式の選択、
#   「抜ける/加わる」欄の開閉、完了メッセージ
#
# 【排他制御(楽観ロック)】
# Streamlitは利用者ごとに別のスレッドで動くので、2人がほぼ同時に登録すると
# 共有データを同時に書き換えてしまう。そこで:
# - 書き換える操作はすべて self._lock(鍵)をかけてから行う(COBOLのENQ/DEQ)
# - 試合結果の登録では「第何試合の結果か」を一緒に受け取り、鍵の中で
#   「今も本当にその試合か」を確かめてから登録する。先に別の人が登録していたら断る
#   (読んだ時点からレコードが変わっていないか確かめてからREWRITEするのと同じ)
# - 何か変わるたびに version(版数)を1つ増やす。画面側は数秒ごとに版数だけを見て、
#   変わっていたら描き直す
#
# 組み合わせ・集計のロジック(doubles.py)は一切変えず、ここから呼ぶだけにしている。
# Streamlitに依存しない普通のクラスにしたのは、pytestで直接テストするため
#
# 【バックアップ】
# 共有領域はアプリが再起動・休止すると消える(設計時に了承済み)。その備えとして
# to_backup()/restore_backup() で全体をJSON文字列に書き出し・読み戻しできる。
# CSV(1種類の表)ではなくJSONにしたのは、メンバ一覧・下駄・対戦履歴という
# 形の違うデータを1つのファイルにまとめるため(COBOLでいう「レコード種別が複数ある
# ファイル」を、そのまま入れ子の形で持てる)

import copy
import json
import random
import threading

from doubles import generate_matchup, join_offset

BACKUP_FORMAT = "tenilog-doubles-v1"


def _empty_state():
    return {
        "players": [],      # 今プレーしているメンバ
        "left": [],         # 途中で抜けたメンバ(成績は残す)
        "offsets": {},      # 途中参加の下駄
        "history": [],      # 対戦履歴(1試合1件)
        "current": None,    # 表示中の対戦カード
        "finished": False,  # 終了したか
    }


class DoublesStore:
    def __init__(self, rng=random):
        self._lock = threading.Lock()
        self._rng = rng
        self._state = _empty_state()
        self.version = 0

    # --- 読み出し ----------------------------------------------------------------
    def snapshot(self):
        """今の共有データのコピーを返す。画面側がコピーをいじっても共有データは変わらない"""
        with self._lock:
            state = copy.deepcopy(self._state)
            state["version"] = self.version
            return state

    # --- 内部の補助(鍵をかけた中から呼ぶ) -----------------------------------------
    def _changed(self):
        self.version += 1

    def _started(self):
        return bool(self._state["history"]) or self._state["current"] is not None

    def _next_matchup(self):
        s = self._state
        s["current"] = generate_matchup(s["players"], s["history"], rng=self._rng, offsets=s["offsets"])

    def _name_error(self, name):
        if not name:
            return "プレイヤー名を入力してください"
        if name in self._state["players"]:
            return f"{name} はすでに登録されています"
        return None

    # --- 書き換え操作。どれも失敗したら理由の文字列、成功したら None を返す --------------
    def add_player(self, name):
        """開始前のプレイヤー登録"""
        with self._lock:
            if self._started():
                return "対戦がすでに始まっています。画面を最新にしてください"
            error = self._name_error(name)
            if error:
                return error
            self._state["players"].append(name)
            self._changed()
            return None

    def remove_last_player(self, expected_name):
        """開始前、最後に登録した1人を削除する。
        別の人が先に追加・削除していたら、意図しない人を消さないよう断る"""
        with self._lock:
            players = self._state["players"]
            if self._started() or not players or players[-1] != expected_name:
                return "ほかの人が先に変更しました。画面を確認してからもう一度操作してください"
            players.pop()
            self._changed()
            return None

    def start(self):
        with self._lock:
            if self._started():
                return "対戦はすでに始まっています"
            if len(self._state["players"]) < 4:
                return "ダブルスには4人以上の登録が必要です"
            self._next_matchup()
            self._changed()
            return None

    def record_result(self, round_no, sets, fmt):
        """第 round_no 試合の結果を登録し、次の対戦カードを出す(楽観ロック)"""
        with self._lock:
            s = self._state
            if s["finished"] or s["current"] is None or len(s["history"]) + 1 != round_no:
                return f"第{round_no}試合はほかの人が先に登録しました(または終了しています)。最新の画面を確認してください"
            current = s["current"]
            s["history"].append({
                "team_a": current["team_a"],
                "team_b": current["team_b"],
                "resting": current["resting"],
                "sets": sets,
                "format": fmt,
            })
            self._next_matchup()
            self._changed()
            return None

    def remove_player(self, name):
        """対戦中に抜けるメンバ。記録が1試合でもあれば「抜けたメンバ」として成績を残す"""
        with self._lock:
            s = self._state
            if name not in s["players"]:
                return f"{name} さんはすでにメンバにいません"
            s["players"].remove(name)
            if s["history"]:
                s["left"].append(name)
            current = s["current"]
            if current is not None:
                # 表示中の対戦カードに入っていたら、残りのメンバで組み直す(4人未満なら組まない)
                if name in list(current["team_a"]) + list(current["team_b"]):
                    if len(s["players"]) >= 4:
                        self._next_matchup()
                    else:
                        s["current"] = None
                else:
                    current["resting"] = [p for p in current["resting"] if p != name]
            self._changed()
            return None

    def add_player_midway(self, name):
        """対戦中に加わるメンバ。抜けた人が同じ名前で戻れば成績を引き継ぐ"""
        with self._lock:
            s = self._state
            error = self._name_error(name)
            if error:
                return error
            if name in s["left"]:
                s["left"].remove(name)
            s["players"].append(name)
            s["offsets"][name] = join_offset(name, s["players"], s["history"], s["offsets"])
            current = s["current"]
            if current is not None:
                current["resting"] = sorted(current["resting"] + [name])  # 今の試合は休み
            elif len(s["players"]) >= 4 and not s["finished"]:
                self._next_matchup()  # 4人を下回って止まっていたのを再開
            self._changed()
            return None

    def finish(self):
        with self._lock:
            if self._state["finished"]:
                return None  # ほかの人が先に終了していても、結果は同じなので断らない
            self._state["current"] = None
            self._state["finished"] = True
            self._changed()
            return None

    def reset(self):
        with self._lock:
            self._state = _empty_state()
            self._changed()
            return None

    # --- バックアップ --------------------------------------------------------------
    def to_backup(self):
        with self._lock:
            return json.dumps({"format": BACKUP_FORMAT, **self._state}, ensure_ascii=False, indent=1)

    def restore_backup(self, text):
        """バックアップ(JSON文字列)から共有データを丸ごと置き換える"""
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "バックアップファイルとして読み込めませんでした"
        if not isinstance(data, dict) or data.get("format") != BACKUP_FORMAT:
            return "てにろぐ君のダブルスのバックアップファイルではありません"
        try:
            state = _restore_state(data)
        except (KeyError, TypeError, ValueError):
            return "バックアップファイルの中身が壊れています"
        with self._lock:
            self._state = state
            self._changed()
            return None


def _restore_state(data):
    """JSONでは tuple が list になるので、元の形(tuple)に戻す"""
    def round_(r):
        return {
            "team_a": tuple(r["team_a"]),
            "team_b": tuple(r["team_b"]),
            "resting": list(r["resting"]),
            "sets": [tuple(x) for x in r["sets"]],
            "format": r.get("format", "one_set"),
        }

    current = data["current"]
    if current is not None:
        current = {"team_a": tuple(current["team_a"]), "team_b": tuple(current["team_b"]),
                   "resting": list(current["resting"])}
    return {
        "players": list(data["players"]),
        "left": list(data["left"]),
        "offsets": {k: int(v) for k, v in data["offsets"].items()},
        "history": [round_(r) for r in data["history"]],
        "current": current,
        "finished": bool(data["finished"]),
    }
