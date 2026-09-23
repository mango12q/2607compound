"""
s1_calib.py — 标定 S1 面板的经纬度→像素映射

做法：面板是一张带黑色边框的欧洲地图。先检测边框，再假定经纬度范围
（与项目 fig2_chr.py 的 ax.set_extent([-15, 45, 30, 72]) 对照），
然后把地中海框（lat 30–47 / lon 5–42，= config.COASTAL_BUFFER_REGION）
画到面板上做目视校验。
"""
import os
import numpy as np
from PIL import Image, ImageDraw

Image.MAX_IMAGE_PIXELS = None
SRC = r"results\s1\s1_page2_xref2.png"
OUT = r"results\s1\panels"
os.makedirs(OUT, exist_ok=True)

COL_X = [(123, 1270), (1460, 2607), (2798, 3945), (4135, 5282)]
row_edges = np.linspace(29, 7996, 11).astype(int)
im = Image.open(SRC).convert("RGB")


def panel_bounds(year, pad=6):
    k = year - 1984
    r, c = divmod(k, 4)
    return (COL_X[c][0] - pad, row_edges[r] - pad,
            COL_X[c][1] + pad, row_edges[r + 1] + pad)


def detect_frame(crop_arr):
    """在面板裁片中找黑色边框：返回 (x0, x1, y0, y1) 像素（相对裁片）"""
    dark = crop_arr.max(axis=2) < 100
    H, W = dark.shape
    col_frac = dark.mean(axis=0)
    row_frac = dark.mean(axis=1)
    xs = np.where(col_frac > 0.5)[0]      # 竖框线：整列多为黑
    ys = np.where(row_frac > 0.5)[0]
    if len(xs) < 2 or len(ys) < 2:
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def geoms_for(year, extent=(-15.0, 45.0, 30.0, 72.0)):
    box = panel_bounds(year, pad=6)
    crop = im.crop(box)
    f = detect_frame(np.asarray(crop))
    return crop, f, extent


if __name__ == "__main__":
    for year in (2003, 2023):
        crop, f, extent = geoms_for(year)
        print(f"{year}: crop={crop.size}  frame(x0,x1,y0,y1)={f}")
        if f is None:
            continue
        x0, x1, y0, y1 = f
        W = x1 - x0
        H = y1 - y0
        lon0, lon1, lat0, lat1 = extent

        def ll2px(lon, lat):
            px = x0 + (lon - lon0) / (lon1 - lon0) * W
            py = y1 - (lat - lat0) / (lat1 - lat0) * H   # 上北下南
            return px, py

        # 画地中海框 lat 30–47 / lon 5–42
        d = ImageDraw.Draw(crop)
        for lon, lat, col in [(5, 30, (0, 128, 255)), (42, 47, (0, 128, 255))]:
            pass
        bx0, by0 = ll2px(5, 47)
        bx1, by1 = ll2px(42, 30)
        d.rectangle([bx0, by0, bx1, by1], outline=(0, 160, 255), width=4)
        # 标注若干地标
        for lon, lat, name in [(-9, 38.7, "Lisbon"), (12.5, 41.9, "Rome"),
                               (29, 41, "Istanbul"), (36.5, 36.2, "Levant"),
                               (-5.6, 36.0, "Gibraltar"), (24, 60, "Helsinki")]:
            px, py = ll2px(lon, lat)
            d.ellipse([px - 6, py - 6, px + 6, py + 6], outline=(0, 200, 0), width=3)
            d.text((px + 8, py - 8), name, fill=(0, 120, 0))
        out = os.path.join(OUT, f"calib_{year}.png")
        crop.save(out)
        print("  ->", out)
