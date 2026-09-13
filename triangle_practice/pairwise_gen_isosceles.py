"""is_isosceles_* のペアワイズテストケースを生成するスクリプト。

resident_tax_practice/pairwise_gen.py と同じ貪欲法だが、決定的な違いが一つある。
寡婦控除では各要素が関数の引数そのものだったので、生成した組み合わせは全て
そのままテストデータにできた。今回の3条件は3点の座標から**導出**されるため、
生成した組み合わせを実現する3点が存在しない場合がある。

そこで2回生成する:
  (1) 制約なし  — 8通り全てが取り得ると素朴に仮定した場合(ツールの素の出力)
  (2) 制約あり  — 格子点の総当たりで実際に実現可能と分かった行だけを候補にした場合

(1)は「机上では被覆できているのにテストが書けない」状態を、(2)は「そもそも
被覆不可能なペアがある」状態を、それぞれ数値で示す。
"""

import itertools

from isosceles_models import conditions_raw, conditions_sorted, feasibility_table

FACTOR_COUNT = 3
LEVELS = [True, False]

# 被覆すべきペア: (要素i, 値, 要素j, 値) の全通り = 3C2 * 2 * 2 = 12
ALL_PAIRS = {
    (i, vi, j, vj)
    for i, j in itertools.combinations(range(FACTOR_COUNT), 2)
    for vi in LEVELS
    for vj in LEVELS
}


def pairs_of(combo):
    return {
        (i, combo[i], j, combo[j])
        for i, j in itertools.combinations(range(FACTOR_COUNT), 2)
    }


def greedy_pairwise(candidates):
    """候補の組み合わせから、貪欲法でペアワイズの行を選ぶ。

    候補が制約で絞られている場合、全ペアを被覆しきれないことがある。その場合は
    「これ以上どの候補を足しても新しいペアが増えない」時点で打ち切る。
    """
    coverable = set()
    for combo in candidates:
        coverable |= pairs_of(combo)

    uncovered = set(coverable)
    chosen = []
    while uncovered:
        best_combo, best_new = None, 0
        for combo in candidates:
            new_count = len(pairs_of(combo) & uncovered)
            if new_count > best_new:
                best_new, best_combo = new_count, combo
        if best_combo is None:
            break
        chosen.append(best_combo)
        uncovered -= pairs_of(best_combo)
    return chosen, coverable


def report(label, names, condition_func):
    print(f"=== {label} ({', '.join(names)}) ===")

    all_combos = list(itertools.product(LEVELS, repeat=FACTOR_COUNT))
    naive_rows, _ = greedy_pairwise(all_combos)
    print(f"(1) 制約なしで生成: {len(naive_rows)}行  ← 理論下限の2x2=4行と一致するか")
    for row in naive_rows:
        print(f"      {fmt(row)}")

    counts = feasibility_table(condition_func, search_range=5)
    feasible = [combo for combo, count in counts.items() if count]
    unrealizable = [row for row in naive_rows if row not in feasible]
    print(f"    このうち実現する3点が存在しない行: {len(unrealizable)}行")
    for row in unrealizable:
        print(f"      {fmt(row)}  ← テストデータを作れない")

    constrained_rows, coverable = greedy_pairwise(feasible)
    print(f"(2) 実現可能な{len(feasible)}通りだけを候補にして生成: {len(constrained_rows)}行")
    for row in constrained_rows:
        print(f"      {fmt(row)}")
    print(f"    被覆できたペア: {len(coverable)} / {len(ALL_PAIRS)}")
    for pair in sorted(ALL_PAIRS - coverable):
        i, vi, j, vj = pair
        print(f"      被覆不可能: {names[i]}={fmt1(vi)} & {names[j]}={fmt1(vj)}")
    print()


def fmt1(value):
    return "T" if value else "F"


def fmt(combo):
    return "(" + ", ".join(fmt1(v) for v in combo) + ")"


if __name__ == "__main__":
    report("モデルA: sorted版", ("eq_ab", "eq_bc", "eq_ca"), conditions_sorted)
    report("モデルB: raw版", ("eq_12", "eq_23", "eq_31"), conditions_raw)
