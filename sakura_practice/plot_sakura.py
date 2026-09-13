# グラフ作成(dataviz方針: 検証済みパレット、二軸グラフを避ける、実績は中立色)

import math
from datetime import date

import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams["font.family"] = "Yu Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False

COLOR_ACTUAL = "#0b0b0b"     # 実績(観測値)は中立なプライマリインク
COLOR_DTS = "#2a78d6"        # slot1 blue
COLOR_SIMPLE_RULE = "#eb6834"  # slot2 orange


def _days_since_feb1(date_str):
    d = date.fromisoformat(date_str)
    return (d - date(d.year, 2, 1)).days


def plot_year_comparison(years, actual_dates, dts_predictions, simple_predictions, out_path):
    """年ごとに、実績・DTS法・600℃の法則の開花日(2/1からの日数)を折れ線で比較する。"""
    actual_days = [_days_since_feb1(actual_dates[y]) for y in years]
    dts_days = [
        _days_since_feb1(dts_predictions[y]) if dts_predictions.get(y) else math.nan
        for y in years
    ]
    simple_days = [_days_since_feb1(simple_predictions[y]) for y in years]

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(years, actual_days, color=COLOR_ACTUAL, linewidth=2, marker="o", markersize=8,
            solid_capstyle="round", label="実績(気象庁観測)")
    # Noneの箇所(休眠打破が判定できず予測不能)は線を切る
    ax.plot(years, dts_days, color=COLOR_DTS, linewidth=2, marker="o", markersize=8,
            solid_capstyle="round", label="DTS法(休眠打破+DTS法)")
    ax.plot(years, simple_days, color=COLOR_SIMPLE_RULE, linewidth=2, marker="o", markersize=8,
            solid_capstyle="round", label="600℃の法則")

    for i, day in enumerate(dts_days):
        if math.isnan(day):
            ax.annotate("予測不能", (years[i], actual_days[i]), textcoords="offset points",
                        xytext=(0, 12), ha="center", fontsize=8, color=COLOR_DTS)

    ax.set_xticks(years)
    ax.set_ylabel("2/1からの日数")
    ax.set_title("東京(靖国神社)の桜の開花日: 実績 vs 予測")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(True, color="#e1e0d9", linewidth=0.8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
