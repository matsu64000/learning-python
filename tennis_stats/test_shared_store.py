"""shared_store.py のテスト。

中心は「同時に登録しても1件しか通らない」こと(楽観ロック+鍵)。
スレッドを実際に複数走らせ、threading.Barrier で「よーいドン」をそろえて
同じ第1試合の結果を一斉に登録させ、通ったのが1件だけであることを確かめる
"""

import random
import threading
import time

from shared_store import DoublesStore

FOUR = ["A", "B", "C", "D"]


def _started_store(players=FOUR, seed=0):
    store = DoublesStore(rng=random.Random(seed))
    for p in players:
        assert store.add_player(p) is None
    assert store.start() is None
    return store


# --- 登録・開始 -------------------------------------------------------------------
def test_add_player_rejects_duplicate_and_empty():
    store = DoublesStore()
    assert store.add_player("A") is None
    assert "すでに登録" in store.add_player("A")
    assert "入力してください" in store.add_player("")
    assert store.snapshot()["players"] == ["A"]


def test_start_needs_four_players():
    store = DoublesStore()
    for p in ["A", "B", "C"]:
        store.add_player(p)
    assert "4人以上" in store.start()
    store.add_player("D")
    assert store.start() is None
    assert store.snapshot()["current"] is not None


def test_add_player_after_start_is_rejected():
    store = _started_store()
    assert "始まっています" in store.add_player("E")


def test_remove_last_player_checks_expected_name():
    store = DoublesStore()
    store.add_player("A")
    store.add_player("B")
    # 画面では最後がAに見えていたが、その間に別の人がBを追加していた → 断る
    assert store.remove_last_player("A") is not None
    assert store.remove_last_player("B") is None
    assert store.snapshot()["players"] == ["A"]


# --- 結果の登録(楽観ロック) ---------------------------------------------------------
def test_record_result_with_correct_round():
    store = _started_store()
    assert store.record_result(1, [(6, 3)], "one_set") is None
    snap = store.snapshot()
    assert len(snap["history"]) == 1
    assert snap["current"] is not None  # 次の対戦カードが出ている


def test_record_result_with_stale_round_is_rejected():
    store = _started_store()
    assert store.record_result(1, [(6, 3)], "one_set") is None
    # 第1試合の画面のまま、もう1人が登録しようとした
    assert "先に登録" in store.record_result(1, [(6, 4)], "one_set")
    assert len(store.snapshot()["history"]) == 1


def test_record_result_after_finish_is_rejected():
    store = _started_store()
    store.finish()
    assert store.record_result(1, [(6, 3)], "one_set") is not None


class _SlowList(list):
    """append の前にわざと少し待つ list。

    「今も第1試合か」の確認から「履歴に追加」までの時間はふつう一瞬なので、
    鍵を外してもまず二重登録は起きず、このテストは鍵の有無を見分けられなかった
    (2026-10-18に鍵を外して200回試し、0回)。待ち時間で隙間を広げると、
    鍵なしでは20件全部が登録されるようになり、鍵の効果が観測できる
    """
    def append(self, x):
        time.sleep(0.01)
        super().append(x)


def test_concurrent_record_only_one_succeeds():
    store = _started_store()
    store._state["history"] = _SlowList()
    n = 20
    barrier = threading.Barrier(n)
    results = [None] * n

    def worker(i):
        barrier.wait()  # 全員がそろってから一斉に登録
        results[i] = store.record_result(1, [(6, i % 6)], "one_set")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(r is None for r in results) == 1
    assert len(store.snapshot()["history"]) == 1


# --- 版数 ------------------------------------------------------------------------
def test_version_increases_only_on_change():
    store = DoublesStore()
    v0 = store.version
    store.add_player("A")
    assert store.version == v0 + 1
    store.add_player("A")  # 重複で断られた → 変化なし
    assert store.version == v0 + 1


def test_snapshot_is_a_copy():
    store = DoublesStore()
    store.add_player("A")
    snap = store.snapshot()
    snap["players"].append("X")
    assert store.snapshot()["players"] == ["A"]


# --- メンバの入れ替わり ----------------------------------------------------------------
def test_remove_player_in_current_card_rebuilds_or_stops():
    store = _started_store(["A", "B", "C", "D", "E"])
    playing = store.snapshot()["current"]["team_a"][0]
    assert store.remove_player(playing) is None
    snap = store.snapshot()
    assert playing not in snap["current"]["team_a"] + snap["current"]["team_b"]
    # もう1人抜けて3人 → 対戦カードは出さない
    assert store.remove_player(snap["players"][0]) is None
    assert store.snapshot()["current"] is None
    assert "いません" in store.remove_player(playing)  # 2回目は断る


def test_add_player_midway_rests_this_round():
    store = _started_store()
    assert store.add_player_midway("E") is None
    assert "E" in store.snapshot()["current"]["resting"]


# --- 終了・リセット・バックアップ --------------------------------------------------------
def test_finish_and_reset():
    store = _started_store()
    store.record_result(1, [(6, 3)], "one_set")
    assert store.finish() is None
    assert store.finish() is None  # 2人が同時に押しても問題ない
    assert store.snapshot()["finished"] is True
    store.reset()
    snap = store.snapshot()
    assert snap["players"] == [] and snap["history"] == [] and snap["finished"] is False


def test_backup_round_trip():
    store = _started_store(["A", "B", "C", "D", "E"])
    store.record_result(1, [(6, 3)], "one_set")
    store.add_player_midway("F")
    text = store.to_backup()

    restored = DoublesStore(rng=random.Random(1))
    assert restored.restore_backup(text) is None
    a, b = store.snapshot(), restored.snapshot()
    for key in ["players", "left", "offsets", "history", "current", "finished"]:
        assert a[key] == b[key]
    # 読み戻した後も続きの試合を登録できる
    assert restored.record_result(2, [(4, 6)], "one_set") is None


def test_restore_rejects_wrong_file():
    store = DoublesStore()
    assert "読み込めません" in store.restore_backup("opponent,sets\nX,6-1")
    assert "ではありません" in store.restore_backup('{"format": "other"}')
    assert "壊れて" in store.restore_backup('{"format": "tenilog-doubles-v1"}')
