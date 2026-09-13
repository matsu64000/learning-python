# グラフ作成
#
# 【配色・レイアウトの方針】
#   気温(℃)と降水量(mm)は単位が違う指標なので、二軸グラフ(1つのグラフに左右2つの
#   y軸を重ねる形)にはしない。上下2段のsubplotに分け、x軸(日付)だけ共有する。
#   カラーは検証済みパレット(色覚多様性を考慮したチェック済みの配色)から、
#   系列の意味に関わらず「最高→平均→最低」の順で固定して使う(系列が入れ替わっても
#   同じ色を使い回さない)
#   Windows特有の注意: "MS Gothic"(ビットマップフォント)を指定すると日本語が
#   警告も無く描画されない問題に前回(audio_practice/fft_basics.py)遭遇済みのため、
#   アウトラインフォントの"Yu Gothic"を指定する

from datetime import date

import matplotlib
import matplotlib.pyplot as plt

matplotlib.rcParams["font.family"] = "Yu Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False  # Yu Gothicはマイナス記号非対応のため

# 検証済みパレット(dataviz skill references/palette.md)から使う色
COLOR_TEMP_MAX = "#eb6834"    # slot2 orange
COLOR_TEMP_MEAN = "#2a78d6"   # slot1 blue
COLOR_TEMP_MIN = "#1baf7a"    # slot3 aqua
COLOR_PRECIPITATION = "#86b6ef"  # 青の連続スケールの薄い段(降水量は補助系列)
COLOR_REFERENCE_LINE = "#898781"  # 田植え/出穂/収穫適期などの節目線(ミュートなインク)


def _to_date(date_str):
    return date.fromisoformat(date_str)


def _mark_event(ax, event_date, label):
    """田植え・出穂・収穫適期などの節目を、縦の破線とラベルで示す。

    ラベルはaxes内側の上端付近に収める(va="top"かつ軸の上限そのものではなく
    少し内側の高さ)。上限ぴったりに置くと、外側にあるグラフタイトルと文字が
    重なって読めなくなる(cumulative_2025.pngで実際に発生した)。
    """
    ax.axvline(_to_date(event_date), color=COLOR_REFERENCE_LINE, linestyle="--", linewidth=1)
    ymin, ymax = ax.get_ylim()
    label_y = ymax - (ymax - ymin) * 0.04
    ax.text(
        _to_date(event_date), label_y, label,
        color=COLOR_REFERENCE_LINE, fontsize=9, ha="left", va="top", rotation=0,
    )


def plot_season(daily_data, transplant_date, heading_date, maturity_date, location_label, out_path):
    """気温(最高・平均・最低)と降水量を、田植え・出穂・収穫適期の節目とともに描画する。"""
    dates = [_to_date(row["date"]) for row in daily_data]

    fig, (ax_temp, ax_precip) = plt.subplots(
        2, 1, figsize=(11, 6), sharex=True, height_ratios=[2, 1],
    )

    ax_temp.plot(dates, [r["temp_max"] for r in daily_data], color=COLOR_TEMP_MAX,
                 linewidth=2, solid_capstyle="round", label="最高気温")
    ax_temp.plot(dates, [r["temp_mean"] for r in daily_data], color=COLOR_TEMP_MEAN,
                 linewidth=2, solid_capstyle="round", label="平均気温")
    ax_temp.plot(dates, [r["temp_min"] for r in daily_data], color=COLOR_TEMP_MIN,
                 linewidth=2, solid_capstyle="round", label="最低気温")
    ax_temp.set_ylabel("気温 (℃)")
    ax_temp.legend(loc="upper left", frameon=False)
    ax_temp.set_title(f"{location_label} 日別気温・降水量")
    ax_temp.grid(True, color="#e1e0d9", linewidth=0.8)

    ax_precip.bar(dates, [r["precipitation"] for r in daily_data], color=COLOR_PRECIPITATION,
                  width=1.0)
    ax_precip.set_ylabel("降水量 (mm)")
    ax_precip.grid(True, color="#e1e0d9", linewidth=0.8)

    for ax, label in ((ax_temp, None), (ax_precip, None)):
        _mark_event(ax, transplant_date, "田植え")
        _mark_event(ax, heading_date, "出穂")
        if maturity_date:
            _mark_event(ax, maturity_date, "収穫適期(予測)")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_cumulative(series, heading_date, threshold_c, maturity_date, out_path):
    """出穂後の積算気温の推移を、閾値の水平線とともに描画する(単一系列なので凡例は省略)。"""
    dates = [_to_date(row["date"]) for row in series]
    values = [row["cumulative"] for row in series]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(dates, values, color=COLOR_TEMP_MEAN, linewidth=2, solid_capstyle="round")
    ax.axhline(threshold_c, color=COLOR_REFERENCE_LINE, linestyle="--", linewidth=1)
    ax.text(dates[0], threshold_c, f"成熟の目安 {threshold_c:.0f}℃", color=COLOR_REFERENCE_LINE,
            fontsize=9, va="bottom")

    if maturity_date:
        _mark_event(ax, maturity_date, "収穫適期(予測)")

    ax.set_ylabel("出穂後の積算気温 (℃・日)")
    ax.set_title(f"出穂({heading_date})からの積算気温")
    ax.grid(True, color="#e1e0d9", linewidth=0.8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
