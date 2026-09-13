# 積算気温(degree-day)の3通りの計算方法
#
# 【背景】rice_growth.pyでは、Open-Meteoが返す「日平均気温」(実際には1時間ごとの
# 気温を1日分平均した、かなり精度の高い値)をそのまま積算した。しかし伝統的に
# 農業の現場では、観測できるのが1日の最高・最低気温(棒温度計の目盛りを毎日読む
# だけ)という制約が長く続いたため、「最高・最低からどう1日分の熱量を見積もるか」
# 自体が課題だった。ここではその歴史的制約を前提にした2つの近似法と、実測平均を
# 並べて比較する。
#
#   (1) 単純平均法: (最高+最低)/2 を日平均とみなし、基準温度を引く。
#       最も古典的で今でも広く使われる方法。実装は1行だが、後述の通り
#       系統的な偏りを持つ
#   (2) 正弦波補間法(Baskerville & Emin, 1969。通称BE法/シングルサイン法):
#       1日の気温変化を、最低気温(0時)→最高気温(正午)→最低気温(24時)と
#       なめらかに変化する正弦波とみなし、基準温度を上回っている時間帯だけを
#       積分して熱量を求める。最高・最低の2値だけで曲線の"面積"を扱う、
#       FORTRAN時代からある由緒正しい数値計算
#   (3) 実測平均法: Open-Meteoの日平均気温(1時間ごとの実測相当値の平均)を
#       そのまま使う。今回は「正解」に最も近いものとして扱う(ただしERA5は
#       実測ではなく再解析値である点は元々の注意点のまま)
#
# 【スコープ】
#   BE法は「シングルサイン法」(その日の最低→最高→翌日と同じ形で戻る、という
#   自己完結した近似)のみ実装する。前日の最高気温と当日の最低気温を別々の
#   半波としてつなぐ「ダブルサイン法」は、隣接日のデータを跨ぐ実装が必要に
#   なるため対象外とする
#   上限温度によるキャップ(暑すぎると生育が止まる、という「修正積算気温法」の
#   考え方)は今回組み込まない。基準温度(下限)のみを扱う

import math


def simple_average_dd(temp_max, temp_min, base_temp):
    """単純平均法: (最高+最低)/2 - 基準温度。基準を下回る日は0にクリップする。"""
    daily_mean = (temp_max + temp_min) / 2
    return max(0.0, daily_mean - base_temp)


def single_sine_dd(temp_max, temp_min, base_temp):
    """BE法(シングルサイン法)による1日分の積算気温。

    1日の気温を T(h) = M - W*cos(πh/12) (h=0〜24時、M=(最高+最低)/2、
    W=(最高-最低)/2) という正弦波で近似し、
        (1/24)∫[0,24] max(0, T(h) - base_temp) dh
    を閉じた式で計算する(Baskerville & Emin, 1969)。3つの場合分け:
      1. 最高気温が基準温度以下 → 1日中基準未満 → 0
      2. 最低気温が基準温度以上 → 1日中基準以上 → 単純平均法と同じ(M - base_temp)
      3. それ以外(基準温度を1日のうちにまたぐ) → 三角関数を使った面積計算
    """
    mean = (temp_max + temp_min) / 2
    amplitude = (temp_max - temp_min) / 2

    if temp_max <= base_temp:
        return 0.0
    if temp_min >= base_temp:
        return mean - base_temp

    # ここに来るのは temp_min < base_temp < temp_max の場合のみなので
    # amplitude > 0 が保証され、ゼロ除算の心配はない
    theta = math.asin((base_temp - mean) / amplitude)
    return (1 / math.pi) * ((mean - base_temp) * (math.pi / 2 - theta) + amplitude * math.cos(theta))


def true_mean_dd(temp_mean, base_temp):
    """実測(相当)の日平均気温をそのまま使う方法。基準を下回る日は0にクリップ。"""
    return max(0.0, temp_mean - base_temp)


def sine_curve_temperature(hour, temp_max, temp_min):
    """正弦波近似での、hour時(0〜24)における気温。単体テストの数値積分検証用。"""
    mean = (temp_max + temp_min) / 2
    amplitude = (temp_max - temp_min) / 2
    return mean - amplitude * math.cos(math.pi * hour / 12)


def cumulative_series(daily_data, start_date, daily_value_func):
    """start_date(を含む)以降について、daily_value_funcで日ごとの値を計算し積算する。

    rice_growth.cumulative_temperatureと同じ形の結果を返すが、「1日分の値を
    どう計算するか」を関数として外から渡せるようにした一般化版。同じ積算の
    骨組み(PERFORM UNTILに相当するループ)に、複数の計算方法を差し替えて
    乗せられる
    """
    from datetime import date

    start = date.fromisoformat(start_date)
    result = []
    cumulative = 0.0
    for row in daily_data:
        if date.fromisoformat(row["date"]) < start:
            continue
        daily_value = daily_value_func(row)
        cumulative += daily_value
        result.append({"date": row["date"], "daily_value": daily_value, "cumulative": cumulative})
    return result


def main():
    # 基準温度10℃をまたぐ日の例(最低5℃・最高15℃、平均はちょうど10℃)
    temp_max, temp_min, base_temp = 15.0, 5.0, 10.0
    print(f"単純平均法: {simple_average_dd(temp_max, temp_min, base_temp):.3f}")
    print(f"BE法      : {single_sine_dd(temp_max, temp_min, base_temp):.3f}")
    print("→ 平均がちょうど基準と同じでも、最高気温が基準を上回っていた時間帯の")
    print("  熱量をBE法だけが拾えている")


if __name__ == "__main__":
    main()
