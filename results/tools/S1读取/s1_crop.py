"""s1_crop.py — 裁出关键年份面板原图，用于目视核对与坐标标定"""
import os
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SRC = r"results\s1\s1_page2_xref2.png"
OUT = r"results\s1\panels"
os.makedirs(OUT, exist_ok=True)

COL_X = [(123, 1270), (1460, 2607), (2798, 3945), (4135, 5282)]
row_edges = np.linspace(29, 7996, 11).astype(int)

im = Image.open(SRC).convert("RGB")

def crop_year(year, pad=6):
    k = year - 1984
    r, c = divmod(k, 4)
    ys, ye = row_edges[r], row_edges[r + 1]
    xs, xe = COL_X[c]
    box = (max(xs - pad, 0), max(ys - pad, 0), min(xe + pad, im.width), min(ye + pad, im.height))
    return im.crop(box)

for y in (1985, 2003, 2022, 2023):
    p = crop_year(y)
    f = os.path.join(OUT, f"panel_{y}.png")
    p.save(f)
    print(f"{y}: {p.size}  -> {f}")

# 拼一张 2x2 对照图（放大 1.6 倍便于看标注）
tiles = [crop_year(y) for y in (1985, 2003, 2022, 2023)]
tw = max(t.width for t in tiles)
th = max(t.height for t in tiles)
s = 1.6
canvas = Image.new("RGB", (int(tw * s * 2) + 30, int(th * s * 2) + 30), "white")
for i, t in enumerate(tiles):
    r, c = divmod(i, 2)
    t2 = t.resize((int(t.width * s), int(t.height * s)), Image.LANCZOS)
    canvas.paste(t2, (10 + c * (int(tw * s) + 10), 10 + r * (int(th * s) + 10)))
out = os.path.join(OUT, "compare_1985_2003_2022_2023.png")
canvas.save(out)
print("->", out, canvas.size)
