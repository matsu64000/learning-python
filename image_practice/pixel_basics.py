# 非構造化データ入門: Pillow/numpyで小さな画像を自作し、ピクセル値の構造を確認する
#
# 目的: 画像は結局「決まった形の行列に並んだ数値の塊」であることを、
# 値を自分で指定した小さな画像を使って手を動かして確認する。

import numpy as np
from PIL import Image

OUTPUT_PATH = "sample_image.png"

# 2行4列、各ピクセルの色をRGBで明示的に指定
PIXELS = [
    [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)],       # 1行目: 赤,緑,青,黄
    [(0, 0, 0), (128, 128, 128), (255, 255, 255), (0, 255, 255)],  # 2行目: 黒,灰,白,シアン
]


def build_image():
    """指定したピクセル値から小さな画像を作る"""
    array = np.array(PIXELS, dtype=np.uint8)  # shape: (高さ2, 幅4, チャンネル3)
    return Image.fromarray(array, mode="RGB")


def main():
    image = build_image()
    image.save(OUTPUT_PATH)
    print(f"{OUTPUT_PATH} を保存しました（サイズ: {image.size}, モード: {image.mode}）")

    array = np.array(image)
    print(f"\nnumpy配列の形状(shape): {array.shape}")  # (高さ, 幅, チャンネル数)
    print(f"データ型(dtype): {array.dtype}")

    print("\n1ピクセルずつの値:")
    for y in range(array.shape[0]):
        for x in range(array.shape[1]):
            r, g, b = array[y, x]
            print(f"  (行{y}, 列{x}): R={r}, G={g}, B={b}")


if __name__ == "__main__":
    main()
