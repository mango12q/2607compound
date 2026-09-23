"""
s1_quantify.py — 逐面板量化 Supplementary Fig. S1 的复合热浪活动强度

S1 版式：4 列 × 10 行 = 40 个年度面板（1984–2023，左→右、上→下）。
每格为欧洲地图，沿海格点按 "Compound THW-MHW days"（色标 5 → 50 天）着色。
色标为 magma 系：浅黄(5) → 橙 → 红 → 品红 → 黑(50)。
陆地灰底、海洋/背景白、海岸线与边框黑。

⚠️ 指标设计要点：
  仅用"饱和度"会把色标**最深的格子**（高值，接近黑）误判为海岸线而漏掉，
  使高值年被系统性低估（实测 2003 因此掉出前 15，明显反常）。
  故指标 = 彩色像素 ∪ 暗像素，再用形态学开运算去掉 1–3 px 的细线
  （海岸线/边框）。各面板地图轮廓完全相同，残余基线一致，排序可比。
"""
import os
import csv

import numpy as np
from PIL import Image
from scipy import ndimage

Image.MAX_IMAGE_PIXELS = None
SRC = r"results\s1\s1_page2_xref2.png"
OUT = r"results\s1"

COL_X = [(123, 1270), (1460, 2607), (2798, 3945), (4135, 5282)]
NROW, NCOL, YEAR0 = 10, 4, 1984

arr = np.asarray(Image.open(SRC).convert("RGB"))
H, W, _ = arr.shape
print("image:", arr.shape)

# 面板行：等分（已核对与 10 个内容带一致）
row_edges = np.linspace(29, 7996, NROW + 1).astype(int)
rows = [(int(row_edges[k]), int(row_edges[k + 1])) for k in range(NROW)]

STRUCT = np.ones((3, 3), bool)

records = []
for r, (ys, ye) in enumerate(rows):
    for c, (xs, xe) in enumerate(COL_X):
        year = YEAR0 + r * NCOL + c
        p = arr[ys:ye, xs:xe, :].astype(np.int16)
        mx, mn = p.max(axis=2), p.min(axis=2)
        sat = mx - mn
        colored = sat > 40
        dark = mx < 120
        mask = colored | dark
        mask = ndimage.binary_opening(mask, structure=STRUCT)   # 去细线
        mask = ndimage.binary_closing(mask, structure=STRUCT)
        n = int(mask.sum())
        records.append(dict(
            year=year, row=r, col=c,
            n_cells=n, frac=n / mask.size,
            n_colored=int(colored.sum()), n_dark=int(dark.sum()),
            mean_sat=float(sat[colored].mean()) if colored.any() else 0.0,
        ))

csv_path = os.path.join(OUT, "s1_panel_stats.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    wtr = csv.DictWriter(f, fieldnames=list(records[0].keys()))
    wtr.writeheader()
    wtr.writerows(records)
print("->", csv_path)

by_year = {d["year"]: d for d in records}
order = sorted(records, key=lambda d: -d["n_cells"])

print("\n=== 全部 40 年，按活动强度降序 ===")
print(f"{'rank':>4} {'year':>6} {'cells':>8} {'frac':>9}")
for i, d in enumerate(order, 1):
    print(f"{i:>4} {d['year']:>6} {d['n_cells']:>8} {d['frac']:>9.5f}")

print("\n=== 论文事件年校验 ===")
for y in (2003, 2022, 2023):
    rank = [i for i, d in enumerate(order, 1) if d["year"] == y][0]
    print(f"  {y}: rank {rank:>2}/40   cells={by_year[y]['n_cells']}")

print("\n=== 完全空白年（0 彩色像素 = 无任何复合日）===")
blank = sorted(d["year"] for d in records if d["n_colored"] == 0)
print(" ", blank)

print("\n=== 活动最弱的 15 年（候选非复合年）===")
for d in order[-15:]:
    print(f"  {d['year']}  cells={d['n_cells']:>7}  colored={d['n_colored']:>7}")
