"""s1_overview.py — 生成 S1 缩略图与分块预览，便于目视确认版式"""
import os
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
SRC = r"results\s1\s1_page2_xref2.png"
OUT = r"results\s1"

im = Image.open(SRC)

# 整图缩略（宽 1400）
w = 1400
h = int(im.height * w / im.width)
im.resize((w, h), Image.LANCZOS).save(os.path.join(OUT, "overview_w1400.png"))
print("overview:", w, h)

# 顶部标题区
im.crop((0, 0, im.width, 900)).resize((1400, int(900 * 1400 / im.width)), Image.LANCZOS) \
  .save(os.path.join(OUT, "header.png"))
print("header crop saved")

# 第一行面板（含色标）
im.crop((0, 800, im.width, 1650)).resize((1400, int(850 * 1400 / im.width)), Image.LANCZOS) \
  .save(os.path.join(OUT, "row1.png"))
print("row1 crop saved")
