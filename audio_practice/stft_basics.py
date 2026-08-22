# 非構造化データ入門: STFT(短時間フーリエ変換)で音の「時間変化」を可視化する
#
# fft_basics.pyの1回だけのFFTは、信号全体に「どんな周波数が含まれるか」は教えてくれるが、
# 「いつ」その周波数が鳴っていたかは分からない(時間情報が一括変換の過程で失われる)。
# これは image_practice/color_similarity.py で「平均色だけでは配置情報が失われる」と
# 気づいたのと同じ構造: 全体を一括で要約すると、要約に使わなかった軸(色の配置/音の時刻)が
# 消える。STFTは、波形を短い窓(window)で区切りながらFFTを繰り返しかける
# (COBOL的に言えば、全件一括のPERFORM ではなく、窓をずらしながら繰り返す PERFORM VARYING に近い)
# ことで、時間軸を保ったまま周波数を見えるようにする。

import os

import numpy as np
import matplotlib.pyplot as plt

from fft_basics import SAMPLE_RATE, DURATION, save_wav, compute_spectrum

plt.rcParams["font.family"] = "Yu Gothic"

OUTPUT_DIR = "fft_output"


def generate_sequential_tones(freq1, freq2, duration=DURATION):
    """前半freq1, 後半freq2を鳴らす(時刻によって周波数が切り替わる信号)"""
    half_samples = int(SAMPLE_RATE * duration / 2)
    t = np.linspace(0, duration / 2, half_samples, endpoint=False)
    wave1 = np.sin(2 * np.pi * freq1 * t)
    wave2 = np.sin(2 * np.pi * freq2 * t)
    return np.concatenate([wave1, wave2])


def generate_chirp(f0, f1, duration=DURATION):
    """周波数がf0からf1へ連続的に変化する信号(チャープ)"""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    sweep_rate = (f1 - f0) / duration
    # 瞬時周波数を時刻tで積分した位相。周波数が一定なら2*pi*f*tに一致する
    phase = 2 * np.pi * (f0 * t + sweep_rate * t ** 2 / 2)
    return np.sin(phase)


def compute_stft(waveform, window_size=1024, hop_size=256):
    """窓をずらしながらFFTを繰り返し、時刻ごとの周波数強度(スペクトログラム)を作る"""
    window = np.hanning(window_size)  # 窓の端で波形を滑らかにゼロへ近づけ、切り出しの歪みを抑える
    n_frames = 1 + (len(waveform) - window_size) // hop_size
    freqs = np.fft.rfftfreq(window_size, d=1 / SAMPLE_RATE)
    spectrogram = np.zeros((len(freqs), n_frames))

    for i in range(n_frames):
        start = i * hop_size
        frame = waveform[start:start + window_size] * window
        spectrum = np.fft.rfft(frame)
        spectrogram[:, i] = np.abs(spectrum) / window_size

    times = (np.arange(n_frames) * hop_size + window_size / 2) / SAMPLE_RATE
    return times, freqs, spectrogram


def to_db(spectrogram, floor_db=-80):
    """振幅を対数(dB)スケールに変換する(人の音量感覚に近く、表示レンジも扱いやすい)"""
    db = 20 * np.log10(spectrogram + 1e-10)
    return np.maximum(db, floor_db)


def plot_comparison(axes_row, waveform, title):
    """時間領域の波形・一括FFT(時刻情報なし)・STFT(時刻情報あり)を並べて、失われる情報を見せる"""
    t = np.arange(len(waveform)) / SAMPLE_RATE
    axes_row[0].plot(t, waveform)
    axes_row[0].set_title(f"{title}: 波形(時間領域)")
    axes_row[0].set_xlabel("時間(秒)")
    axes_row[0].set_ylabel("振幅")

    freqs, magnitude = compute_spectrum(waveform)
    axes_row[1].plot(freqs, magnitude)
    axes_row[1].set_xlim(0, 2500)
    axes_row[1].set_title(f"{title}: 一括FFT(いつ鳴ったかは分からない)")
    axes_row[1].set_xlabel("周波数(Hz)")
    axes_row[1].set_ylabel("強度")

    times, stft_freqs, spectrogram = compute_stft(waveform)
    db = to_db(spectrogram)
    axes_row[2].imshow(
        db, origin="lower", aspect="auto", cmap="magma",
        extent=[times[0], times[-1], stft_freqs[0], stft_freqs[-1]],
        vmin=-80, vmax=0,
    )
    axes_row[2].set_ylim(0, 2500)
    axes_row[2].set_title(f"{title}: STFT(時刻ごとの周波数が見える)")
    axes_row[2].set_xlabel("時間(秒)")
    axes_row[2].set_ylabel("周波数(Hz)")


def plot_window_tradeoff(chirp):
    """窓サイズによる時間分解能/周波数分解能のトレードオフを、同じチャープで比較する"""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, window_size in zip(axes, [256, 4096]):
        times, freqs, spectrogram = compute_stft(chirp, window_size=window_size, hop_size=window_size // 4)
        db = to_db(spectrogram)
        ax.imshow(
            db, origin="lower", aspect="auto", cmap="magma",
            extent=[times[0], times[-1], freqs[0], freqs[-1]],
            vmin=-80, vmax=0,
        )
        ax.set_ylim(0, 2500)
        ax.set_title(f"窓サイズ={window_size}サンプル({window_size / SAMPLE_RATE * 1000:.1f}ms)")
        ax.set_xlabel("時間(秒)")
        ax.set_ylabel("周波数(Hz)")
    fig.suptitle("窓サイズのトレードオフ: 短い窓=時間はくっきり/周波数はぼやける、長い窓はその逆")
    fig.tight_layout()
    return fig


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    sequential = generate_sequential_tones(440, 880)  # ラ→高いラ、0.5秒で切り替え
    chirp = generate_chirp(200, 2000)  # 200Hzから2000Hzへ1秒かけて連続的に上昇

    save_wav(os.path.join(OUTPUT_DIR, "sequential_440_880hz.wav"), sequential)
    save_wav(os.path.join(OUTPUT_DIR, "chirp_200_2000hz.wav"), chirp)

    fig, axes = plt.subplots(2, 3, figsize=(15, 7))
    plot_comparison(axes[0], sequential, "440Hz→880Hz切り替え")
    plot_comparison(axes[1], chirp, "200Hz→2000Hzチャープ")
    fig.tight_layout()
    fig_path = os.path.join(OUTPUT_DIR, "stft_comparison.png")
    fig.savefig(fig_path, dpi=120)
    print(f"比較グラフを保存しました: {fig_path}")

    tradeoff_fig = plot_window_tradeoff(chirp)
    tradeoff_path = os.path.join(OUTPUT_DIR, "stft_window_tradeoff.png")
    tradeoff_fig.savefig(tradeoff_path, dpi=120)
    print(f"窓サイズ比較グラフを保存しました: {tradeoff_path}")

    print(f"WAVファイルも保存しました: {OUTPUT_DIR}/sequential_440_880hz.wav, {OUTPUT_DIR}/chirp_200_2000hz.wav")


if __name__ == "__main__":
    main()
