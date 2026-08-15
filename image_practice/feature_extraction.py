# 非構造化データ入門: 画像から特徴量(固定長の数値表現)を取り出す
#
# pixel_basics.pyで作った sample_image.png(2行4列, RGB)を題材に、
# 「生データ→特徴抽出→固定長の数値表現」の流れを確認する。

import numpy as np
from PIL import Image

IMAGE_PATH = "sample_image.png"


def to_grayscale_array(image):
    """RGB画像をグレースケール(明るさ1チャンネル)のnumpy配列に変換する"""
    gray_image = image.convert("L")  # Pillowが標準的な輝度計算式で変換してくれる
    return np.array(gray_image)


def average_color(array):
    """RGB配列から、チャンネルごとの平均値を求める(3要素の固定長ベクトル)"""
    return array.mean(axis=(0, 1))  # 行・列方向を潰し、チャンネルだけ残す


def main():
    image = Image.open(IMAGE_PATH)
    rgb_array = np.array(image)

    print(f"元データ(生データ): shape={rgb_array.shape}, dtype={rgb_array.dtype}")

    gray_array = to_grayscale_array(image)
    print(f"\nグレースケール変換後: shape={gray_array.shape}")
    print("値(明るさ0〜255):")
    print(gray_array)

    avg = average_color(rgb_array)
    print(f"\n平均色(特徴量ベクトル): R={avg[0]:.1f}, G={avg[1]:.1f}, B={avg[2]:.1f}")

    flat_vector = rgb_array.flatten()
    print(f"\n全ピクセルを1本のベクトルに展開(固定長の数値表現): 要素数={flat_vector.size}")
    print(flat_vector)


if __name__ == "__main__":
    main()
