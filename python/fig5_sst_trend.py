r"""
fig5_sst_trend.py — 论文图 5：SST / 海洋蒸发 / 比湿 的 JAS 线性趋势

面板（按 `pdf_extract/fig5_p07.jpeg` 逐像素校准，2026-09-24 第五轮）
------------------------------------------------------------------
a  "Observed Trend in SST (OISSTv2)" / "(JAS; 1994-2023)"      色标 °C/decade，
   **12 个 0.1 宽色块覆盖 [−0.6, +0.6]**，刻度 0.5…−0.5，**无延伸箭头**
b  "Observed Trend in ocean evaporation" / "(JAS; 1991-2020)"  色标 cm/year/decade，
   12 个 2 宽色块覆盖 [−12, +12]，刻度 10…−10
c  "Observed trend in specific humidity" / "(JAS; 1994-2023)"  色标 g/kg/decade，
   14 个 0.05 宽色块覆盖 [−0.35, +0.35]，刻度 0.30…−0.30

版式：上行 a | b，下行 c **居中**；三个面板都**没有坐标轴/刻度/经纬网**；
a/b 的陆地是纯灰 RGB(182,182,182) 且**不画海岸线**；c 覆盖海陆并画**黑色海岸线+国界**；
地图范围统一为 **lon −15…43.5、lat 29…69**（原图拟合，非等经纬比，约 12–15 % 纵向拉伸）。

输入
----
    results/intermediate/sst_trend_jas_1994_2023.nc   变量 sst_trend
    results/intermediate/evap_trend_jas_1991_2020.nc  变量 evap_trend
    results/intermediate/sh_trend_jas_1994_2023.nc    变量 sh_trend
（由 `python python\phase5_humid.py stats` 生成）

用法
----
    python python\fig5_sst_trend.py
    python python\fig5_sst_trend.py --synthetic     # 用合成场验证版式（输出 *_synthetic_demo）
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

TREND_FILES = {
    "sst": (os.path.join(C.INTERMEDIATE_DIR, "sst_trend_jas_1994_2023.nc"), "sst_trend"),
    "evap": (os.path.join(C.INTERMEDIATE_DIR, "evap_trend_jas_1991_2020.nc"), "evap_trend"),
    "sh": (os.path.join(C.INTERMEDIATE_DIR, "sh_trend_jas_1994_2023.nc"), "sh_trend"),
}

# 原图色板（逐像素读取，暖→冷）：红 → 橙 → 黄 → 浅黄 → 绿 → 蓝
PALETTE_12 = [(131, 1, 6), (200, 1, 7), (253, 0, 10), (254, 150, 14),
              (255, 254, 45), (254, 254, 176), (171, 255, 179), (1, 254, 45),
              (1, 154, 81), (0, 0, 227), (0, 0, 195), (0, 0, 125)]
PALETTE_14 = [(133, 0, 5), (191, 0, 5), (254, 0, 10), (254, 81, 12),
              (253, 209, 20), (255, 255, 69), (254, 254, 190), (184, 255, 189),
              (40, 255, 72), (0, 212, 37), (2, 87, 147), (0, 0, 244),
              (0, 0, 190), (0, 0, 125)]

EXTENT = (-15.0, 43.5, 29.0, 69.0)     # 原图拟合：lon −15…43.5、lat 29…69
LAND_GREY = (182 / 255, 182 / 255, 182 / 255)

PANELS = (
    ("sst", "a", "Observed Trend in SST (OISSTv2)", "(JAS; 1994-2023)",
     "$\\degree$C/decade", -0.6, 0.6, 0.1, PALETTE_12, False),
    ("evap", "b", "Observed Trend in ocean evaporation", "(JAS; 1991-2020)",
     "cm/year/decade", -12.0, 12.0, 2.0, PALETTE_12, False),
    ("sh", "c", "Observed trend in specific humidity", "(JAS; 1994-2023)",
     "g/kg/decade", -0.35, 0.35, 0.05, PALETTE_14, True),
)


def _load_trend(key: str):
    path, var = TREND_FILES[key]
    if not os.path.exists(path):
        return None
    ds = xr.open_dataset(path)
    da = ds[var] if var in ds else ds[list(ds.data_vars)[0]]
    return da


def _synthetic(key: str):
    """合成趋势场（仅用于版式自检，不参与任何结论）。"""
    lat = np.arange(29.0, 69.01, 0.25)
    lon = np.arange(-15.0, 43.51, 0.25)
    lon2d, lat2d = np.meshgrid(lon, lat)
    base = {"sst": 0.35, "evap": 6.0, "sh": 0.18}[key]
    field = base * np.exp(-((lat2d - 40.0) / 12.0) ** 2) \
        + 0.15 * base * np.sin(np.deg2rad(lon2d * 3))
    return xr.DataArray(field.astype("float32"), dims=("lat", "lon"),
                        coords={"lat": lat, "lon": lon}, name=key)


def make_figure(outdir: str = None, dpi: int = 300, synthetic: bool = False) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    outdir = outdir or C.FIGURES_DIR
    os.makedirs(outdir, exist_ok=True)

    fig = plt.figure(figsize=(13.0, 9.6))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.0, 1.12], hspace=0.30, wspace=0.55)

    slots = {"a": gs[0, 0:2], "b": gs[0, 2:4], "c": gs[1, 1:3]}
    mappable = {}
    for key, letter, title, subtitle, unit, lo, hi, step, palette, draw_borders in PANELS:
        da = _synthetic(key) if synthetic else _load_trend(key)
        ax = fig.add_subplot(slots[letter], projection=ccrs.PlateCarree())
        ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
        ax.set_aspect("auto")                     # 原图非等经纬比（约 12–15 % 纵向拉伸）
        ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor=LAND_GREY,
                       zorder=1)
        if draw_borders:
            ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4,
                           edgecolor="k", zorder=4)
            ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.4,
                           edgecolor="k", zorder=4)
        if da is None:
            print(f"  [warn] 缺 {TREND_FILES[key][0]}；面板 {letter} 只画底图")
            ax.set_title(f"{title}\n{subtitle}", fontsize=12)
            ax.text(0.5, 0.5, "run: phase5_humid.py stats", transform=ax.transAxes,
                    ha="center", fontsize=8)
            continue

        levels = np.round(np.arange(lo, hi + step / 2, step), 6)
        # ⚠️ 原图色板是按"上→下"（红=高值 → 蓝=低值）读出的；ListedColormap 的
        #    索引 0 对应**最低**色块，故必须反转，否则红蓝互换。
        colors = [tuple(c / 255 for c in rgb) for rgb in reversed(palette)]
        cmap = ListedColormap(colors)
        norm = BoundaryNorm(levels, cmap.N)
        mm = ax.pcolormesh(da["lon"], da["lat"], da.values, cmap=cmap, norm=norm,
                           shading="auto", transform=ccrs.PlateCarree(), zorder=3,
                                     rasterized=True)
        mappable[letter] = mm
        ax.set_title(f"{title}\n{subtitle}", fontsize=12)
        ax.text(-0.02, 1.02, f"{letter})", transform=ax.transAxes, fontsize=14,
                fontweight="bold", va="bottom")
        ax.set_xticks([])
        ax.set_yticks([])

    # 色标：竖直、刻度在右（与原图一致）、无延伸箭头
    for letter, mm in mappable.items():
        ax = mm.axes
        _, _, _, _, unit, lo, hi, step, palette, _ = [p for p in PANELS
                                                      if p[1] == letter][0]
        cb = fig.colorbar(mm, ax=ax, orientation="vertical", fraction=0.046,
                          pad=0.03, ticks=np.round(np.arange(lo + step, hi, step), 6))
        cb.set_label(unit, fontsize=11)
        cb.ax.tick_params(labelsize=10)

    suffix = "_synthetic_demo" if synthetic else ""
    outs = []
    for ext in ("pdf", "png"):
        p = os.path.join(outdir, f"fig5_sst_trend{suffix}.{ext}")
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        outs.append(p)
    plt.close(fig)
    for p in outs:
        print(f"  -> {p}")

    if not synthetic:
        print("\n[图5] 锚点对照（论文正文）")
        for key, ref in (("sst", "≤ ~0.5 °C/decade"), ("evap", "局部 >10 cm/yr/decade"),
                         ("sh", "≈0.3 g/kg/decade")):
            da = _load_trend(key)
            if da is None:
                print(f"  {key}: 缺趋势场")
                continue
            v = np.asarray(da.values, dtype=float)
            print(f"  {key}: p95 = {np.nanpercentile(v, 95):+.3f}、"
                  f"max = {np.nanmax(v):+.3f}、median = {np.nanmedian(v):+.3f}"
                  f"　（论文 {ref}）")
    return outs[1]


def main(argv=None):
    p = argparse.ArgumentParser(description="论文图 5：SST / 蒸发 / 比湿 JAS 趋势")
    p.add_argument("--outdir", default=None)
    p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--synthetic", action="store_true",
                   help="用合成趋势场验证版式（输出 fig5_sst_trend_synthetic_demo.*）")
    args = p.parse_args(argv)
    make_figure(outdir=args.outdir, dpi=args.dpi, synthetic=args.synthetic)
    return 0


if __name__ == "__main__":
    sys.exit(main())
