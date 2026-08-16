# 非構造化データ入門: 音声(1次元の時系列)をFFTで周波数成分に分解する
#
# 画像編で「空間周波数」を扱ったのと対になる話。音声は時間軸上に並んだ振幅値であり、
# 生の波形(時間領域)を見ただけでは、混ざっている音の高さ(周波数)は分からない。
# フーリエ変換で周波数領域に変換して、初めて成分が見える。

import wave

import numpy as np
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Yu Gothic"  # Windowsで日本語ラベルが文字化けするのを防ぐ

OUTPUT_DIR = "fft_output"
SAMPLE_RATE = 44100  # 1秒間に44100回サンプリング(CD音質と同じ)
DURATION = 1.0  # 秒
ZOOM_MS = 10  # 波形を目で見るために拡大表示する範囲(ミリ秒)


def generate_sine(freq, amplitude=1.0):
    """指定した周波数(Hz)のサイン波を1つ生成する"""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return amplitude * np.sin(2 * np.pi * freq * t)


def save_wav(path, waveform):
    """振幅-1.0〜1.0のfloat配列を16bit PCMのWAVファイルとして保存する"""
    int16_waveform = np.int16(waveform * 32767)
    with wave.open(path, "w") as wav_file:
        wav_file.setnchannels(1)  # モノラル
        wav_file.setsampwidth(2)  # 16bit = 2byte
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(int16_waveform.tobytes())


def compute_spectrum(waveform):
    """波形(時間領域)をFFTで周波数領域に変換し、周波数ごとの強度(振幅)を返す"""
    spectrum = np.fft.rfft(waveform)  # 実数信号用のFFT
    freqs = np.fft.rfftfreq(len(waveform), d=1 / SAMPLE_RATE)
    magnitude = np.abs(spectrum) / len(waveform)  # 波形の長さで正規化
    return freqs, magnitude


def find_peaks(freqs, magnitude, threshold_ratio=0.2, max_freq=3000):
    """最大強度に対してthreshold_ratio以上の強度を持つ周波数を、ピークとして抽出する"""
    limit = magnitude.max() * threshold_ratio
    peak_freqs = freqs[(magnitude >= limit) & (freqs <= max_freq)]
    # 近接した周波数ビンをまとめる(同じピークの山を1本として扱う)
    peaks = []
    for f in peak_freqs:
        if not peaks or f - peaks[-1] > 20:
            peaks.append(f)
    return peaks


def plot_signal(ax_time, ax_freq, waveform, freqs, magnitude, title):
    zoom_samples = int(SAMPLE_RATE * ZOOM_MS / 1000)
    t_ms = np.arange(zoom_samples) / SAMPLE_RATE * 1000

    ax_time.plot(t_ms, waveform[:zoom_samples])
    ax_time.set_title(f"{title}: 時間領域(波形, 先頭{ZOOM_MS}msだけ表示)")
    ax_time.set_xlabel("時間(ms)")
    ax_time.set_ylabel("振幅")

    ax_freq.plot(freqs, magnitude)
    ax_freq.set_xlim(0, 3000)
    ax_freq.set_title(f"{title}: 周波数領域(FFT)")
    ax_freq.set_xlabel("周波数(Hz)")
    ax_freq.set_ylabel("強度")


def main():
    import os

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    single_tone = generate_sine(440)  # ラの音(A4)単体
    mixed_tone = generate_sine(440) * 0.6 + generate_sine(1000) * 0.6  # 440Hz + 1000Hzを混合

    save_wav(os.path.join(OUTPUT_DIR, "single_440hz.wav"), single_tone)
    save_wav(os.path.join(OUTPUT_DIR, "mixed_440_1000hz.wav"), mixed_tone)

    fig, axes = plt.subplots(2, 2, figsize=(12, 7))

    for row, (waveform, title) in enumerate([
        (single_tone, "440Hz単体"),
        (mixed_tone, "440Hz+1000Hz混合"),
    ]):
        freqs, magnitude = compute_spectrum(waveform)
        peaks = find_peaks(freqs, magnitude)
        print(f"{title}: 検出されたピーク周波数(Hz) = {[round(p) for p in peaks]}")
        plot_signal(axes[row][0], axes[row][1], waveform, freqs, magnitude, title)

    fig.tight_layout()
    fig_path = os.path.join(OUTPUT_DIR, "spectrum.png")
    fig.savefig(fig_path, dpi=120)
    print(f"\nグラフを保存しました: {fig_path}")
    print(f"WAVファイルも保存しました: {OUTPUT_DIR}/single_440hz.wav, {OUTPUT_DIR}/mixed_440_1000hz.wav")


if __name__ == "__main__":
    main()
