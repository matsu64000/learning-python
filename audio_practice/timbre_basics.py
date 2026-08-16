# 非構造化データ入門: 倍音の構成比率と音量の時間変化(エンベロープ)で音色(timbre)を作る
#
# fft_basics.pyでは440Hzの単一サイン波を扱ったが、実際の楽器の音は
# 「基音+倍音(整数倍の周波数)」の重ね合わせであり、その配分と、音量が時間とともに
# どう変化するか(エンベロープ)の組み合わせが音色の違いを生む。
# ここでは「ピアノ風(倍音が多く、急速に減衰する)」と「オルガン風(倍音が少なく、持続する)」
# を単純化して合成し、聞き比べる。

import os

import numpy as np
import matplotlib.pyplot as plt

from fft_basics import SAMPLE_RATE, DURATION, save_wav, compute_spectrum, find_peaks

plt.rcParams["font.family"] = "Yu Gothic"

OUTPUT_DIR = "fft_output"
FUNDAMENTAL = 440  # ラの音(A4)
ZOOM_MS = 10

# (倍音の次数, 基音に対する強さ)。次数2倍音=880Hz, 3倍音=1320Hz...
PIANO_HARMONICS = [(1, 1.0), (2, 0.6), (3, 0.4), (4, 0.25), (5, 0.15), (6, 0.1)]
ORGAN_HARMONICS = [(1, 1.0), (2, 0.5), (3, 0.5), (4, 0.3), (6, 0.2)]


def envelope_piano(t, decay_rate=4.0):
    """打鍵直後にすぐ減衰していく、ピアノ的な音量変化"""
    return np.exp(-decay_rate * t)


def envelope_organ(t, attack_sec=0.01):
    """一定の音量を持続する、オルガン的な音量変化(クリック音防止の短い立ち上がりのみ付与)"""
    envelope = np.ones_like(t)
    attack_samples = int(SAMPLE_RATE * attack_sec)
    envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
    return envelope


def build_tone(harmonics, envelope_fn, freq=FUNDAMENTAL):
    """倍音を重ね合わせ、エンベロープをかけて1つの波形にする"""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    waveform = np.zeros_like(t)
    for order, amplitude in harmonics:
        waveform += amplitude * np.sin(2 * np.pi * freq * order * t)
    waveform *= envelope_fn(t)
    waveform /= np.max(np.abs(waveform))  # クリッピング防止のため-1〜1に正規化
    return waveform


def plot_tone(axes_row, waveform, freqs, magnitude, title):
    t = np.arange(len(waveform)) / SAMPLE_RATE
    zoom_samples = int(SAMPLE_RATE * ZOOM_MS / 1000)

    axes_row[0].plot(t, waveform)
    axes_row[0].set_title(f"{title}: 全体の音量変化(エンベロープ)")
    axes_row[0].set_xlabel("時間(秒)")
    axes_row[0].set_ylabel("振幅")

    axes_row[1].plot(t[:zoom_samples] * 1000, waveform[:zoom_samples])
    axes_row[1].set_title(f"{title}: 波形(先頭{ZOOM_MS}msだけ拡大)")
    axes_row[1].set_xlabel("時間(ms)")
    axes_row[1].set_ylabel("振幅")

    axes_row[2].plot(freqs, magnitude)
    axes_row[2].set_xlim(0, 3000)
    axes_row[2].set_title(f"{title}: 周波数領域(倍音の構成)")
    axes_row[2].set_xlabel("周波数(Hz)")
    axes_row[2].set_ylabel("強度")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    piano_tone = build_tone(PIANO_HARMONICS, envelope_piano)
    organ_tone = build_tone(ORGAN_HARMONICS, envelope_organ)

    save_wav(os.path.join(OUTPUT_DIR, "piano_like.wav"), piano_tone)
    save_wav(os.path.join(OUTPUT_DIR, "organ_like.wav"), organ_tone)

    fig, axes = plt.subplots(2, 3, figsize=(16, 7))

    for row, (waveform, harmonics, title) in enumerate([
        (piano_tone, PIANO_HARMONICS, "ピアノ風"),
        (organ_tone, ORGAN_HARMONICS, "オルガン風"),
    ]):
        freqs, magnitude = compute_spectrum(waveform)
        peaks = find_peaks(freqs, magnitude, threshold_ratio=0.05)
        expected = [FUNDAMENTAL * order for order, _ in harmonics]
        print(f"{title}: 想定した倍音(Hz)={expected}")
        print(f"{title}: 検出されたピーク(Hz)={[round(p) for p in peaks]}")
        plot_tone(axes[row], waveform, freqs, magnitude, title)

    fig.tight_layout()
    fig_path = os.path.join(OUTPUT_DIR, "timbre.png")
    fig.savefig(fig_path, dpi=120)
    print(f"\nグラフを保存しました: {fig_path}")
    print(f"WAVファイルも保存しました: {OUTPUT_DIR}/piano_like.wav, {OUTPUT_DIR}/organ_like.wav")


if __name__ == "__main__":
    main()
