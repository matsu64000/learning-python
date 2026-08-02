# 町丁目ごとの人口を集計するサンプル

wards = [
    ("中央地区", 12500),
    ("北町", 8300),
    ("南台", 15200),
    ("西が丘", 6100),
    ("東新町", 11000),
]

total = 0
for name, population in wards:
    total += population

average = total / len(wards)

print(f"合計人口: {total}人")
print(f"平均人口: {average:.1f}人")

print("--- 基準(10,000人)超過の町丁目 ---")
for name, population in wards:
    if population > 10000:
        print(f"{name}: {population}人")
