"""s1_contact.py — 生成候选年份的接触表（contact sheet），供逐格目视判读"""
import os
import csv

import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
SRC = r"results\s1\s1_page2_xref2.png"
OUT = r"results\s1"

# 精确的列/行内容带（由 s1_layout.py 的投影结果整理）
COL_X = [(123, 1270), (1460, 2607), (2798, 3945), (4135, 5282)]
ROW_Y = [(29, 732), (836, 1539), (1643, 2346), (2449, 3153), (3256, 3960),
         (4063, 4767), (4870, 5574), (5677, 6381), (6484, 7188), (7291, 7995)]

im = Image.open(SRC).convert("RGB")


def panel(year):
    k = year - 1984
    r, c = divmod(k, 4)
    return im.crop((COL_X[c][0], ROW_Y[r][0], COL_X[c][1], ROW_Y[r][1]))


def sheet(years, cols, out_name, tile_w=560, label_h=26):
    tiles = [(y, panel(y)) for y in years]
    ar = tiles[0][1].height / tiles[0][1].width
    tile_h = int(tile_w * ar)
    rows = (len(tiles) + cols - 1) // cols
    pad = 8
    W = cols * tile_w + (cols + 1) * pad
    H = rows * (tile_h + label_h) + (rows + 1) * pad
    canvas = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(canvas)
    for i, (y, t) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = pad + c * (tile_w + pad)
        yy = pad + r * (tile_h + label_h + pad)
        canvas.paste(t.resize((tile_w, tile_h), Image.LANCZOS), (x, yy))
        d.rectangle([x - 1, yy - 1, x + tile_w, yy + tile_h], outline=(150, 150, 150))
        d.text((x + 4, yy + tile_h + 4), str(y), fill=(0, 0, 0))
    p = os.path.join(OUT, out_name)
    canvas.save(p)
    print(f"-> {p}  {canvas.size}")
    return p


# 读回量化结果，取活动最弱的 15 年
stats = list(csv.DictReader(open(os.path.join(OUT, "s1_panel_stats.csv"), encoding="utf-8")))
for s in stats:
    s["n_colored"] = int(s["n_colored"])
low = sorted(stats, key=lambda s: s["n_colored"])[:15]
low_years = sorted(int(s["year"]) for s in low)
print("低活动 15 年:", low_years)

sheet(low_years, 4, "sheet_low15.png")
sheet([2003, 2022, 2023, 2018, 1990, 1997, 1994, 1999], 4, "sheet_reference.png")
