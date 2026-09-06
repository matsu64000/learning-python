"""judge_widow_or_single_parent_deduction のペアワイズテストケースを生成するスクリプト。

決定表(判定ロジックの優先順位構造を使う)と違い、ペアワイズは「どの2要素の値の
組み合わせも最低1回登場させる」という機械的な基準だけで組む。手作業では抜け漏れが
起きやすいため、貪欲法(各行を追加するたびに、まだ被覆していないペアを一番多く
カバーする組み合わせを選ぶ)で生成し、全ペアを被覆できたかをコードで検証する。
理論上の下限は最大レベル数同士の積(3値要素×2値要素=6行)だが、貪欲法は最小性を
保証しないため、この題材では8行になる。

test_individual_resident_tax.py の
test_judge_widow_or_single_parent_deduction_pairwise はここでの出力をもとに書いた。
"""

import itertools

FACTORS = [
    ("gender", ["male", "female"]),
    ("marital_status", ["divorced", "widowed", "unmarried"]),
    ("has_dependent_child", [False, True]),
    ("has_other_dependent_relative", [False, True]),
    ("total_income", [3_000_000, 5_500_000]),  # 500万円以下/超の代表値
    ("has_defacto_marriage_partner", [False, True]),
]

names = [n for n, _ in FACTORS]
level_lists = [v for _, v in FACTORS]
all_combos = list(itertools.product(*level_lists))

# 全ての2要素間の「値ペア」を列挙(これが被覆すべき対象)
all_pairs = set()
for i in range(len(FACTORS)):
    for j in range(i + 1, len(FACTORS)):
        for vi in level_lists[i]:
            for vj in level_lists[j]:
                all_pairs.add((i, vi, j, vj))

def pairs_of(combo):
    result = set()
    for i in range(len(FACTORS)):
        for j in range(i + 1, len(FACTORS)):
            result.add((i, combo[i], j, combo[j]))
    return result

uncovered = set(all_pairs)
chosen = []
while uncovered:
    best_combo, best_new = None, -1
    for combo in all_combos:
        new_count = len(pairs_of(combo) & uncovered)
        if new_count > best_new:
            best_new, best_combo = new_count, combo
    chosen.append(best_combo)
    uncovered -= pairs_of(best_combo)

print(f"総組み合わせ数: {len(all_combos)}")
print(f"被覆すべきペア総数: {len(all_pairs)}")
print(f"生成された行数: {len(chosen)}")
print()
for row in chosen:
    print(dict(zip(names, row)))

# 検証: 本当に全ペアを被覆できているか
covered = set()
for row in chosen:
    covered |= pairs_of(row)
assert covered == all_pairs, "カバレッジ漏れがあります"
print("\n検証OK: 全ペアを被覆済み")
