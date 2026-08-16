# 非構造化データ入門: 平均色ベクトル×ユークリッド距離で「似ている画像」を判定する
#
# feature_extraction.pyで求めた平均色(3要素ベクトル)を使い、画像同士の距離を計算する。
# あえて「チェッカーボード模様の画像」と「その平均色と同じ単色画像」を混ぜることで、
# 平均色だけを見る手法の限界(配置情報が失われること)も確認する。

import math

import numpy as np
from PIL import Image

from feature_extraction import average_color, to_grayscale_array

OUTPUT_DIR = "similarity_samples"
IMAGE_SIZE = 8  # 8x8ピクセルの正方形画像を作る


def build_image(pixel_fn):
    """pixel_fn(y, x) -> (R,G,B) を使って IMAGE_SIZE x IMAGE_SIZE の画像を作る"""
    array = np.array(
        [[pixel_fn(y, x) for x in range(IMAGE_SIZE)] for y in range(IMAGE_SIZE)],
        dtype=np.uint8,
    )
    return Image.fromarray(array, mode="RGB")


def solid(color):
    return lambda y, x: color


def checkerboard(color_a, color_b):
    return lambda y, x: color_a if (y + x) % 2 == 0 else color_b


def left_right(color_left, color_right):
    return lambda y, x: color_left if x < IMAGE_SIZE // 2 else color_right


# 用意する画像: (ファイル名, 生成関数, 説明)
IMAGE_DEFS = [
    ("red.png", solid((200, 50, 50)), "赤系の単色"),
    ("red_light.png", solid((180, 60, 55)), "赤系の単色(redに近い色味)"),
    ("blue.png", solid((50, 50, 200)), "青系の単色(redとは離れた色味)"),
    ("checker_red_white.png", checkerboard((255, 0, 0), (255, 255, 255)),
     "赤と白のチェッカーボード模様(1ピクセル単位の細かい模様)"),
    ("half_red_white.png", left_right((255, 0, 0), (255, 255, 255)),
     "左半分が赤・右半分が白(ブロック境界と一致する粗い模様)"),
    ("pink.png", solid((255, 128, 128)), "checker/half_red_whiteと平均色がほぼ一致する単色ピンク"),
]

BLOCK_GRID = 2  # 2x2ブロックに分割(8x8画像なので1ブロック4x4ピクセル)


def block_average_vector(array, grid_size):
    """画像を grid_size x grid_size のブロックに分け、ブロックごとの平均色を並べたベクトルを返す"""
    height, width, _ = array.shape
    block_h, block_w = height // grid_size, width // grid_size

    vector = []
    for by in range(grid_size):
        for bx in range(grid_size):
            block = array[by * block_h:(by + 1) * block_h, bx * block_w:(bx + 1) * block_w]
            vector.extend(average_color(block))
    return np.array(vector)


def std_color(array):
    """RGB配列から、チャンネルごとの標準偏差を求める(3要素ベクトル)。
    画素値がどれだけばらついているかを表す。単色画像なら0、模様があれば0より大きくなる。"""
    return array.std(axis=(0, 1))


def edge_energy(gray_array):
    """グレースケール画像の縦横の隣接差分(絶対値)を合計し、模様の細かさ・境界の量を表す1つの数値にする。
    単色なら0、境界が多い/急な模様ほど大きくなる(単純な隣接差分によるエッジ検出)。"""
    gray_int = gray_array.astype(int)
    horizontal_diff = np.abs(np.diff(gray_int, axis=1))
    vertical_diff = np.abs(np.diff(gray_int, axis=0))
    return float(horizontal_diff.sum() + vertical_diff.sum())


def euclidean_distance(vec_a, vec_b):
    """3要素ベクトル同士のユークリッド距離"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))


def main():
    import os

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    whole_features = {}
    block_features = {}
    mean_std_features = {}
    mean_std_edge_features = {}
    for filename, pixel_fn, description in IMAGE_DEFS:
        image = build_image(pixel_fn)
        path = os.path.join(OUTPUT_DIR, filename)
        image.save(path)

        array = np.array(image)
        avg = average_color(array)
        std = std_color(array)
        edge = edge_energy(to_grayscale_array(image))
        whole_features[filename] = avg
        block_features[filename] = block_average_vector(array, BLOCK_GRID)
        mean_std_features[filename] = np.concatenate([avg, std])
        mean_std_edge_features[filename] = np.concatenate([avg, std, [edge]])
        print(
            f"{filename:22s} 平均色=({avg[0]:6.1f}, {avg[1]:6.1f}, {avg[2]:6.1f})  "
            f"標準偏差=({std[0]:5.1f}, {std[1]:5.1f}, {std[2]:5.1f})  "
            f"エッジ強度={edge:7.1f}  {description}"
        )

    print("\n--- 画像ペアごとのユークリッド距離(方式ごとの比較) ---")
    names = list(whole_features.keys())
    header = (
        f"{'画像A':22s} vs {'画像B':22s} {'全体平均':>10s} "
        f"{'ブロック分割':>12s} {'平均+標準偏差':>14s} {'+エッジ強度':>12s}"
    )
    print(header)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            whole_dist = euclidean_distance(whole_features[a], whole_features[b])
            block_dist = euclidean_distance(block_features[a], block_features[b])
            mean_std_dist = euclidean_distance(mean_std_features[a], mean_std_features[b])
            mean_std_edge_dist = euclidean_distance(
                mean_std_edge_features[a], mean_std_edge_features[b]
            )
            print(
                f"{a:22s} vs {b:22s} {whole_dist:10.1f} "
                f"{block_dist:12.1f} {mean_std_dist:14.1f} {mean_std_edge_dist:12.1f}"
            )


if __name__ == "__main__":
    main()
