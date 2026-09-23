"""s1_layout.py — 探测 S1 原图的面板网格（行/列留白投影）"""
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SRC = r"results\s1\s1_page2_xref2.png"

im = Image.open(SRC)
print("size:", im.size, "mode:", im.mode)
g = np.asarray(im.convert("L"), dtype=np.uint8)
H, W = g.shape
print("gray shape:", g.shape)

# "有内容" = 明显非白（阈值 245）
ink = g < 245
row_ink = ink.mean(axis=1)   # 每行有内容像素占比
col_ink = ink.mean(axis=0)   # 每列

print(f"总墨迹占比: {ink.mean():.4f}")


def bands(profile, thresh=0.01, min_gap=8):
    """返回内容区段 [(start, end), ...]（含端点），间隙 = profile < thresh 的连续段"""
    on = profile >= thresh
    segs = []
    i = 0
    n = len(on)
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            segs.append((i, j))
            i = j + 1
        else:
            i += 1
    # 合并被极小间隙分开的段
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] <= min_gap:
            merged[-1] = (merged[-1][0], s[1])
        else:
            merged.append(list(s))
    return [tuple(m) for m in merged]


rb = bands(row_ink, thresh=0.02, min_gap=6)
cb = bands(col_ink, thresh=0.02, min_gap=6)
print(f"\n行方向内容段 ({len(rb)}):")
for s, e in rb:
    print(f"  rows {s:5d}-{e:5d}  h={e-s+1:5d}")
print(f"\n列方向内容段 ({len(cb)}):")
for s, e in cb:
    print(f"  cols {s:5d}-{e:5d}  w={e-s+1:5d}")
