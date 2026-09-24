"""
figS1_annual_maps.py — 论文 **Supplementary Fig. S1**：1984–2023 年际空间分布组图（4×10 = 40 面板）

论文出处与判读依据
------------------
* Fig.6 caption / 正文："The selection of both compound and non-compound years is based on our
  detection results for 1984–2023 shown in Supplementary Figure S1."
* 本地补充材料实测：1 张大图（6015×8024 px），**4 行 × 10 列 = 40 个年度面板**，年份 1984–2023；
  色标为连续型、上限 **50 天**、无延伸箭头（见 `results/方法与证据.md` §3）。

⚠️ 与本项目既有的 `figS1_jkl_maxcell.*` **不是同一张图**：后者是图1j–l 的"格点最大值"替代口径，
   命名沿用了旧编号。本脚本产出的才是论文的 Supplementary Fig. S1。

数据
----
    results/intermediate/annual_compound_days.nc   变量 compound_mhw_thw (year, lat, lon)
    （由 `python python\\run_all.py` 的 Phase 3 生成）

用法
----
    python python\\figS1_annual_maps.py
    python python\\figS1_annual_maps.py --var compound_mhw_thw --vmax 50 --years 1984 2023
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

ANNUAL_NC = os.path.join(C.INTERMEDIATE_DIR, "annual_compound_days.nc")
EXTENT = (-15.0, 43.5, 29.0, 69.0)      # 与论文图1/图5 一致的欧洲—地中海框


def make_figure(outdir: str = None, var: str = "compound_mhw_thw", vmax: float = 50.0,
                years=(1984, 2023), dpi: int = 200) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    if not os.path.exists(ANNUAL_NC):
        raise SystemExit(f"找不到 {ANNUAL_NC}\n  先跑：python python\\run_all.py")
    ds = xr.open_dataset(ANNUAL_NC)
    key = var if var in ds else list(ds.data_vars)[0]
    da = ds[key]
    yrs = [y for y in range(int(years[0]), int(years[1]) + 1)
           if y in set(np.asarray(da["time"]).astype(int))]
    if not yrs:
        raise SystemExit(f"{ANNUAL_NC} 里没有 {years[0]}–{years[1]} 的年份")

    nrow, ncol = 4, 10
    fig = plt.figure(figsize=(ncol * 2.0, nrow * 1.8))
    gs = fig.add_gridspec(nrow, ncol + 1, width_ratios=[1] * ncol + [0.12],
                          wspace=0.06, hspace=0.10)
    levels = np.linspace(0, float(vmax), 21)
    mappable = None
    for i, yr in enumerate(yrs[: nrow * ncol]):
        ax = fig.add_subplot(gs[i // ncol, i % ncol], projection=ccrs.PlateCarree())
        ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
        ax.set_aspect("auto")
        ax.add_feature(cfeature.LAND.with_scale("110m"), facecolor="#e8e8e8",
                       zorder=0)
        f = da.sel(time=yr)
        # 无复合日的格点留白（否则整片浅黄会盖掉细窄的海岸带信号）
        f = f.where(f > 0)
        mappable = ax.pcolormesh(f["lon"], f["lat"], f.values, cmap="YlOrRd",
                                 vmin=0, vmax=float(vmax), shading="auto",
                                 transform=ccrs.PlateCarree(), zorder=2,
                                 rasterized=True)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(str(int(yr)), fontsize=9, pad=1.5)

    cax = fig.add_subplot(gs[:, -1])
    cb = fig.colorbar(mappable, cax=cax)
    cb.set_label("Compound coastal heatwave days", fontsize=9)
    cb.ax.tick_params(labelsize=8)
    fig.suptitle("Supplementary Fig. S1 — annual compound marine–terrestrial "
                 "heatwave days, 1984–2023", fontsize=11, y=0.995)

    outdir = outdir or C.FIGURES_DIR
    os.makedirs(outdir, exist_ok=True)
    outs = []
    for ext in ("pdf", "png"):
        p = os.path.join(outdir, f"figS1_paper_annual_maps.{ext}")
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        outs.append(p)
    plt.close(fig)
    for p in outs:
        print(f"  -> {p}")

    # 与论文"非复合年"口径的对照（论文 Fig.6c 图例的 11 年）
    med = (da["lat"].to_series().between(30, 47).values[:, None]
           & da["lon"].to_series().between(5, 42).values[None, :])
    tot = {int(y): float(np.nansum(np.where(med, da.sel(time=y).values, np.nan)))
           for y in yrs}
    zero = [y for y, v in tot.items() if v == 0]
    print(f"\n[图S1] 地中海&黑海框内年复合日总量 = 0 的年份（本项目检测结果）："
          f"{zero if zero else '无'}")
    print(f"        论文 Fig.6c 图例的 11 个非复合年：{list(C.WBT_NONCOMPOUND_YEARS)}")
    print("        ⚠️ 论文 S1 的年份判读与论文 Fig.6c 图例并不同源；本脚本只出图，不做年份裁定。")
    return outs[1]


def main(argv=None):
    p = argparse.ArgumentParser(description="论文 Supplementary Fig. S1（1984–2023 年际组图）")
    p.add_argument("--outdir", default=None)
    p.add_argument("--var", default="compound_mhw_thw")
    p.add_argument("--vmax", type=float, default=50.0,
                   help="色标上限（论文 S1 实测为 50 天，连续型、无延伸箭头）")
    p.add_argument("--years", nargs=2, type=int, default=(1984, 2023))
    p.add_argument("--dpi", type=int, default=200)
    args = p.parse_args(argv)
    make_figure(outdir=args.outdir, var=args.var, vmax=args.vmax,
                years=tuple(args.years), dpi=args.dpi)
    return 0


if __name__ == "__main__":
    sys.exit(main())
