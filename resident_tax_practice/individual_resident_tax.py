# 個人住民税(所得割+均等割)の試算プログラム
#
# 対象: 令和7年度の個人住民税(=令和6年中の給与収入に対して課税)。帳票作成は対象外で、
# 収入・扶養等の入力から税額を計算するロジックのみを扱う。
#
# 出典(2026-08-22時点でWebFetch/WebSearchにより確認、いずれも各自治体・国の公開ページ):
#   - 税率(市6%・県4%)、均等割(市3,000円+県1,000円+森林環境税1,000円=5,000円)、
#     基礎控除43万円の逓減、給与所得控除の速算表: 春日市・鎌ケ谷市の令和7年度住民税ページ
#   - 扶養控除の区分別金額、調整控除の人的控除差額表、非課税限度額の算式: 狛江市の住民税ページ
#
# 【このプログラムのスコープ・既知の制約(判定ロジック層の対象外事項)】
#   対象所得: 給与所得のみ(事業所得・不動産所得等は非対応)
#   対象控除: 基礎控除・給与所得控除・社会保険料控除(実額)・扶養控除(人的)のみ
#     -> 配偶者控除・配偶者特別控除、医療費控除、生命保険料控除などは非対応
#   非課税限度額の判定: 非対応(本来は所得が一定以下なら均等割・所得割とも非課税になるが、
#     ここでは常に課税される前提で計算する)
#   自治体独自の超過課税: 非対応(均等割は総務省の標準額のみを用いる。実際は自治体の条例で
#     上乗せされることがある。例: 福岡県は森林環境税相当を県民税に500円上乗せしている)
#   給与所得控除(収入660万円未満の区間): 所得税法別表第5(1,000円刻みの参照表)ではなく、
#     国の速算式で近似している。制度上は表参照が正式であり、本コードの結果は僅かに
#     ずれる場合がある
#   調整控除の人的控除差額(基礎控除分): 合計所得2,400万円超の高所得ケースの扱いは未検証

from dataclasses import dataclass, field


CITY_INCOME_TAX_RATE = 0.06   # 市町村民税(所得割)
PREFECTURE_INCOME_TAX_RATE = 0.04  # 道府県民税(所得割)

CITY_PER_CAPITA_LEVY = 3000       # 市町村民税均等割
PREFECTURE_PER_CAPITA_LEVY = 1000  # 道府県民税均等割
FOREST_ENVIRONMENT_TAX = 1000     # 森林環境税(国税だが均等割とあわせて徴収される)

# 扶養区分ごとの住民税上の控除額
DEPENDENT_DEDUCTIONS = {
    "general": 330_000,             # 一般扶養親族(16〜18歳、23〜69歳)
    "specific": 450_000,            # 特定扶養親族(19〜22歳)
    "elderly": 380_000,             # 老人扶養親族(70歳以上)
    "elderly_cohabiting": 450_000,  # 同居老親等(70歳以上の直系尊属と同居)
}

# 調整控除の計算に使う、所得税と住民税の人的控除額の差
PERSONAL_DEDUCTION_DIFF = {
    "basic": 50_000,
    "general": 50_000,
    "specific": 180_000,
    "elderly": 100_000,
    "elderly_cohabiting": 130_000,
}


@dataclass
class Dependent:
    age: int
    is_lineal_ascendant_living_together: bool = False  # 70歳以上の同居直系尊属か


@dataclass
class TaxpayerInput:
    salary_income: int  # 給与収入額(年間、円)
    social_insurance_premium: int  # 社会保険料の年間支払額(円)
    dependents: list = field(default_factory=list)  # list[Dependent]


def classify_dependent(dependent):
    """年齢と同居老親等の情報から、扶養控除の区分を判定する(該当なしはNone)"""
    age = dependent.age
    if age < 16:
        return None  # 年少扶養親族は住民税・所得税とも控除対象外
    if age >= 70:
        return "elderly_cohabiting" if dependent.is_lineal_ascendant_living_together else "elderly"
    if 19 <= age <= 22:
        return "specific"
    return "general"  # 16〜18歳、23〜69歳


def calc_salary_deduction(income):
    """給与収入額から給与所得控除額を求める(令和2年分以降の速算式)"""
    if income <= 1_625_000:
        return 550_000
    elif income <= 1_800_000:
        return income * 40 // 100 - 100_000
    elif income <= 3_600_000:
        return income * 30 // 100 + 80_000
    elif income <= 6_600_000:
        return income * 20 // 100 + 440_000
    elif income <= 8_500_000:
        return income * 10 // 100 + 1_100_000
    else:
        return 1_950_000


def calc_basic_deduction(total_income):
    """合計所得金額に応じた住民税の基礎控除額(高所得ほど逓減し、消失する)"""
    if total_income <= 24_000_000:
        return 430_000
    elif total_income <= 24_500_000:
        return 290_000
    elif total_income <= 25_000_000:
        return 150_000
    else:
        return 0


def calc_adjustment_reduction(taxable_income, total_income, personal_deduction_diff_total):
    """所得税と住民税の人的控除差額に基づく調整控除(市町村民税分・道府県民税分)を計算する"""
    if total_income > 25_000_000:
        return {"city": 0, "prefecture": 0}

    if taxable_income <= 2_000_000:
        base = min(personal_deduction_diff_total, taxable_income)
    else:
        base = max(personal_deduction_diff_total - (taxable_income - 2_000_000), 0)

    return {
        "city": base * 3 // 100,
        "prefecture": base * 2 // 100,
    }


def calculate_resident_tax(taxpayer):
    """令和7年度個人住民税(所得割+均等割)を計算し、内訳を辞書で返す"""
    salary_deduction = calc_salary_deduction(taxpayer.salary_income)
    total_income = max(taxpayer.salary_income - salary_deduction, 0)  # 給与所得金額

    dependent_categories = [
        category
        for category in (classify_dependent(d) for d in taxpayer.dependents)
        if category is not None
    ]
    dependent_deduction = sum(DEPENDENT_DEDUCTIONS[c] for c in dependent_categories)
    basic_deduction = calc_basic_deduction(total_income)

    income_deductions_total = basic_deduction + taxpayer.social_insurance_premium + dependent_deduction

    # 課税標準額(課税所得金額)は1,000円未満切り捨て
    taxable_income = max(total_income - income_deductions_total, 0) // 1000 * 1000

    personal_deduction_diff_total = PERSONAL_DEDUCTION_DIFF["basic"] + sum(
        PERSONAL_DEDUCTION_DIFF[c] for c in dependent_categories
    )
    adjustment = calc_adjustment_reduction(taxable_income, total_income, personal_deduction_diff_total)

    # 所得割額は市町村民税分・道府県民税分それぞれ100円未満切り捨て、マイナスは0円
    city_income_levy = max(int(taxable_income * CITY_INCOME_TAX_RATE) - adjustment["city"], 0) // 100 * 100
    prefecture_income_levy = (
        max(int(taxable_income * PREFECTURE_INCOME_TAX_RATE) - adjustment["prefecture"], 0) // 100 * 100
    )

    per_capita_levy_total = CITY_PER_CAPITA_LEVY + PREFECTURE_PER_CAPITA_LEVY + FOREST_ENVIRONMENT_TAX
    income_levy_total = city_income_levy + prefecture_income_levy
    resident_tax_total = income_levy_total + per_capita_levy_total

    return {
        "salary_deduction": salary_deduction,
        "total_income": total_income,
        "basic_deduction": basic_deduction,
        "dependent_deduction": dependent_deduction,
        "income_deductions_total": income_deductions_total,
        "taxable_income": taxable_income,
        "adjustment_reduction": adjustment,
        "city_income_levy": city_income_levy,
        "prefecture_income_levy": prefecture_income_levy,
        "income_levy_total": income_levy_total,
        "city_per_capita_levy": CITY_PER_CAPITA_LEVY,
        "prefecture_per_capita_levy": PREFECTURE_PER_CAPITA_LEVY,
        "forest_environment_tax": FOREST_ENVIRONMENT_TAX,
        "per_capita_levy_total": per_capita_levy_total,
        "resident_tax_total": resident_tax_total,
    }


def print_breakdown(title, taxpayer, result):
    print(f"\n===== {title} =====")
    print(f"給与収入: {taxpayer.salary_income:,}円 / 社会保険料: {taxpayer.social_insurance_premium:,}円 "
          f"/ 扶養親族: {len(taxpayer.dependents)}人")
    print(f"給与所得控除: {result['salary_deduction']:,}円 -> 給与所得金額: {result['total_income']:,}円")
    print(f"所得控除合計: {result['income_deductions_total']:,}円 "
          f"(基礎控除{result['basic_deduction']:,}円 + 社会保険料控除{taxpayer.social_insurance_premium:,}円 "
          f"+ 扶養控除{result['dependent_deduction']:,}円)")
    print(f"課税標準額: {result['taxable_income']:,}円")
    print(f"調整控除: 市{result['adjustment_reduction']['city']:,}円 / 県{result['adjustment_reduction']['prefecture']:,}円")
    print(f"所得割: 市{result['city_income_levy']:,}円 + 県{result['prefecture_income_levy']:,}円 "
          f"= {result['income_levy_total']:,}円")
    print(f"均等割: 市{result['city_per_capita_levy']:,}円 + 県{result['prefecture_per_capita_levy']:,}円 "
          f"+ 森林環境税{result['forest_environment_tax']:,}円 = {result['per_capita_levy_total']:,}円")
    print(f"個人住民税額(合計): {result['resident_tax_total']:,}円")


def main():
    single = TaxpayerInput(
        salary_income=5_000_000,
        social_insurance_premium=750_000,
        dependents=[],
    )
    print_breakdown("独身・給与収入500万円・扶養なし", single, calculate_resident_tax(single))

    with_dependents = TaxpayerInput(
        salary_income=4_500_000,
        social_insurance_premium=700_000,
        dependents=[Dependent(age=17), Dependent(age=20)],  # 一般扶養1人 + 特定扶養1人
    )
    print_breakdown("給与収入450万円・扶養2人(一般+特定)", with_dependents, calculate_resident_tax(with_dependents))


if __name__ == "__main__":
    main()
