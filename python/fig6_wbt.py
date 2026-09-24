r"""
fig6_wbt.py — 论文图 6：地中海海岸 100 km 缓冲区的湿热极端（WBT / SH）

★ 2026-09-24 第五轮：按 `pdf_extract/fig6_p08.png` **原图**重定面板语义
（`TECHNICAL_SPEC_PHASE_C.md` §C.4 把 a/b 写成"每根柱一年"是错的）

| 面板 | 原图内容 | 轴 |
|---|---|---|
| a | "Days with WBT ≥ 25.5 °C" —— **每年一条曲线** | x = 湿球温度 25.5–27.0 °C；y = 超阈天数（区域平均） |
| b | "Days with SH ≥ 19 gr/kg" —— 每年一条曲线 | x = 比湿 19.0–20.7 g/kg；y = 超阈天数 |
| c | "Return periods" —— 每年一条曲线 | x = 湿球温度 22–28 °C；y = 重现期（年，**对数**） |
| d–f | 2003 / 2022 / 2023 复合日**最大** WBT 空间场 | 离散色标 17–26 °C（<18 白、>25 黑），land-only |

样式（原图读数）：
  · 复合年 2003/2022/2023 = **粗实线**（红 / 橙 / 黑）；非复合年 = 细虚线，每年固定配色；
  · 图例置于 c 面板右侧，标题 "Year (Type)"，**3 列**排版，复合年标注 "(Comp. MHW-THW)"；
  · c 面板为对数 y 轴，标了 `60.0`（非复合年 2000）、`20.0`、`3.2`（2023）三个数值；
  · d–f 为地中海—欧洲陆地地图，海面浅蓝、无数据陆地白色，含海岸线与国界。

输入（`python python\phase5_humid.py all` 产出）
---------------------------------------------
    results/tables/fig6_stats.json          # exceedance_curves / rp_curves / groups / buffer
    results/intermediate/wbt_compound_{yr}.nc   # 6d–f 的 WBT 场（mean 与 max）

用法
----
    python python\\fig6_wbt.py
    python python\\fig6_wbt.py --outdir results/figures --dpi 300
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

FIG6_JSON = os.path.join(C.TABLES_DIR, "fig6_stats.json")

# 非复合年的固定配色（**逐像素取自论文原图**，与年份绑定，保证 a/b/c 三面板同色）
NONCOMPOUND_COLORS = {
    1984: "#dc0d15",   # (220,13,21)
    1986: "#f4a522",   # (244,165,34)
    1988: "#000000",
    1990: "#1919e6",   # (25,25,230)
    1991: "#fafc14",   # (250,252,20)
    1992: "#8f2525",   # (143,37,37)
    1993: "#7b7b79",   # (~123,123,121)
    1996: "#12760f",   # (18,118,15)
    2000: "#f523f5",   # (245,35,245)
    2004: "#fab2c0",   # (250,178,192)
    2008: "#710e76",   # (113,14,118)
    # S1 敏感性年份（不在论文图例里，仅在需要时使用）
    1985: "#a9a9a9", 1989: "#bcbd22", 1998: "#17becf", 1987: "#7f7f7f",
}
# 复合年：粗实线 + 圆点 marker（原图 2003 红 / 2022 橙 / 2023 黑）
COMPOUND_STYLE = {2003: ("#fb0200", 2.4), 2022: ("#fda308", 2.4),
                  2023: ("#000000", 2.4)}

# 图6d–f 的离散色标（原图读数：9 个 1 °C 宽的色块，17→26 °C，>26 归入黑色）
WBT_MAP_LEVELS = [17, 18, 19, 20, 21, 22, 23, 24, 25, 26]
WBT_MAP_COLORS = ["#f8f8f8", "#f8f858", "#f8e800", "#f8b000", "#f85000",
                  "#e80000", "#a00000", "#500000", "#000000"]
MAP_EXTENT = (-10.0, 40.5, 35.0, 62.0)      # 论文 d–f 取景（实测拟合 97.9–98.6 %）
SEA_COLOR = "#a8d8e0"                       # 原图海面 (168,216,224)


def _load_stats(path: str = None) -> dict:
    path = path or FIG6_JSON
    if not os.path.exists(path):
        raise SystemExit(
            f"找不到 {path}\n"
            f"  先跑：python python\\phase5_humid.py all\n"
            f"  （需要先下载 Phase 5 输入：run_phase5_downloads.bat）")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _years_in_order(stats: dict):
    """复合年在前（按年份），非复合年随后 —— 与论文图例一致。"""
    g = stats.get("groups", {})
    comp = list(g.get("compound_years", C.WBT_RP_YEARS))
    nonc = list(g.get("noncompound_paper11", C.WBT_NONCOMPOUND_YEARS))
    extra = [y for y in (g.get("paper_named_2000"),) if y and y not in nonc and y not in comp]
    return comp, sorted(set(nonc) | set(extra))


def _series_xy(block: dict, key_x: str, key_y: str):
    xs, ys = [], []
    for x, y in zip(block.get(key_x, []), block.get(key_y, [])):
        xs.append(np.nan if x is None else float(x))
        ys.append(np.nan if y is None else float(y))
    return np.asarray(xs), np.asarray(ys)


def make_figure(outdir: str = None, dpi: int = 300, only_curves: bool = False,
                stats_path: str = None, outname: str = None) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.colors import ListedColormap, BoundaryNorm

    stats = _load_stats(stats_path)
    # ⚠️ 用合成统计产物出图时**必须换文件名**，否则会覆盖真图、看起来像真实结果
    if outname is None:
        outname = ("fig6_wbt_synthetic_demo" if stats_path else "fig6_wbt")
    outdir = outdir or C.FIGURES_DIR
    os.makedirs(outdir, exist_ok=True)
    comp_years, noncomp_years = _years_in_order(stats)
    all_years = comp_years + noncomp_years

    fig = plt.figure(figsize=(12.5, 12.4))
    gs = fig.add_gridspec(3, 3, height_ratios=[1.0, 1.0, 0.95], hspace=0.42, wspace=0.30)

    # ── a：WBT 超阈频率 ────────────────────────────────────────────────
    axa = fig.add_subplot(gs[0, 0])
    _plot_exceedance(axa, stats, "wbt", all_years, comp_years,
                     "Days with WBT $\\geq$ 25.5$\\degree$C",
                     "Wet-bulb Temperature ($\\degree$C)", xlim=(25.45, 27.05))

    # ── b：SH 超阈频率 ────────────────────────────────────────────────
    axb = fig.add_subplot(gs[0, 1:])
    _plot_exceedance(axb, stats, "sh", all_years, comp_years,
                     "Days with SH $\\geq$ 19 gr/kg",
                     "Specific humidity (gr/kg)", xlim=(18.95, 20.75))

    # ── c：重现期曲线 ────────────────────────────────────────────────
    axc = fig.add_subplot(gs[1, 0:2])
    _plot_return_periods(axc, stats, all_years, comp_years)

    # ── 图例（c 面板右侧，3 列）──────────────────────────────────────
    axl = fig.add_subplot(gs[1, 2])
    axl.axis("off")
    handles = []
    for yr in all_years:
        if yr in COMPOUND_STYLE:
            col, lw = COMPOUND_STYLE[yr]
            handles.append(Line2D([], [], color=col, lw=lw,
                                  label=f"{yr} (Comp. MHW-THW)"))
        else:
            col = NONCOMPOUND_COLORS.get(yr, "#666666")
            handles.append(Line2D([], [], color=col, lw=1.2, ls="--", label=str(yr)))
    ncol = 3
    axl.legend(handles=handles, labels=[h.get_label() for h in handles],
               loc="upper left", ncol=ncol, fontsize=10, frameon=True,
               title="Year (Type)", title_fontsize=10)
    axl.text(0.0, 0.06, "Compound years: thick solid\n"
                        "Non-compound years: thin dash-dot\n"
                        "(year sets taken from the paper's Fig.6c legend)",
             transform=axl.transAxes, fontsize=8, va="top")

    # ── d–f：复合日最大 WBT 空间场 ────────────────────────────────────
    if not only_curves:
        _plot_maps(fig, gs, comp_years, ListedColormap, BoundaryNorm, plt)

    outs = []
    for ext in ("pdf", "png"):
        p = os.path.join(outdir, f"{outname}.{ext}")
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        outs.append(p)
    plt.close(fig)
    for p in outs:
        print(f"  -> {p}")

    # ── 锚点对照 ────────────────────────────────────────────────────
    print("\n[图6] 锚点对照（论文正文）")
    ad = stats.get("annual_days", {})
    w = ad.get("wbt25.5", {})
    if w:
        y23 = w.get("2023")
        nonc = [w[str(y)] if str(y) in w else w.get(y) for y in noncomp_years]
        nonc = [v for v in nonc if v is not None]
        print(f"  a) 2023 WBT≥25.5 天数 = "
              f"{'（缺）' if y23 is None else f'{y23:.1f}'}（论文 ≈40）")
        print(f"     非复合年（11 年）均值 = "
              f"{'（缺）' if not nonc else f'{np.mean(nonc):.1f}'}"
              f"　⚠️ 论文锚点 '<5 天' 经原图核对应读作 '≤8 天（11 年中 9 年 ≤4 天）'")
    rp = stats.get("rp_curves", {})
    for yr in (2023, 2000):
        blk = rp.get(str(yr)) or rp.get(int(yr))
        if blk:
            thr = blk.get("thresholds", [])
            if 26.0 in [float(t) for t in thr]:
                v = blk["rp"][[float(t) for t in thr].index(26.0)]
                print(f"  c) {yr} @26 °C 重现期 = "
                      f"{'∞/缺' if v is None else f'{v:.1f}'} 年"
                      f"（论文 {'≈3–4' if yr == 2023 else '≈60'}）")
    return outs[1]


def _plot_exceedance(ax, stats, key, years, comp_years, title, xlabel, xlim):
    block = (stats.get("exceedance_curves", {}) or {}).get(key, {}) or {}
    for yr in years:
        d = block.get(str(yr)) or block.get(yr)
        if not d:
            continue
        x = np.asarray(d["thresholds"], dtype=float)
        y = np.asarray([np.nan if v is None else v for v in d["days"]], dtype=float)
        if yr in COMPOUND_STYLE:
            col, lw = COMPOUND_STYLE[yr]
            ax.plot(x, y, color=col, lw=lw, marker="o", ms=4, zorder=5)
        else:
            ax.plot(x, y, color=NONCOMPOUND_COLORS.get(yr, "#666666"), lw=1.2,
                    ls="-.", zorder=3)
    ax.set_title(title, fontsize=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Exceedance frequency\n(Days)")
    ax.set_xlim(*xlim)
    ax.set_ylim(-2, 45)                       # 原图下沿在 0 以下，并画 y=0 实线
    ax.axhline(0.0, color="black", lw=0.9, zorder=2)
    ax.set_yticks(np.arange(0, 46, 5))
    ax.grid(True, color="#d9d9d9", lw=0.6)
    ax.set_axisbelow(True)


def _plot_return_periods(ax, stats, years, comp_years):
    block = stats.get("rp_curves", {}) or {}
    for yr in years:
        d = block.get(str(yr)) or block.get(yr)
        if not d:
            continue
        x = np.asarray(d["thresholds"], dtype=float)
        y = np.asarray([np.nan if v is None else v for v in d["rp"]], dtype=float)
        y = np.where(y > 0, y, np.nan)
        if yr in COMPOUND_STYLE:
            col, lw = COMPOUND_STYLE[yr]
            ax.plot(x, y, color=col, lw=lw, marker="o", ms=3.5, zorder=5)
        else:
            ax.plot(x, y, color=NONCOMPOUND_COLORS.get(yr, "#666666"), lw=1.2,
                    ls="-.", marker=".", ms=3, zorder=3)
    ax.set_yscale("log")
    ax.set_xlim(22, 28)
    ax.set_ylim(1.1, 150)                     # 原图只标 10¹/10²（10⁰ 落在轴外）
    ax.set_xlabel("Wet-bulb Temperature ($\\degree$C)")
    ax.set_ylabel("Return periods")
    ax.grid(True, which="major", color="#d9d9d9", lw=0.6)
    ax.grid(True, which="minor", color="#ececec", lw=0.4, ls=":")
    ax.set_axisbelow(True)
    # 论文原图标注的三个数值（位置按原图像素读数：≈25.3–25.7 °C 一带）
    ax.text(25.30, 60.0, "60.0", color="#f523f5", fontsize=12, fontweight="bold")
    ax.text(25.30, 20.0, "20.0", color="#f523f5", fontsize=12, fontweight="bold")
    ax.text(25.62, 3.2, "3.2", color="black", fontsize=12, fontweight="bold")


def _plot_maps(fig, gs, comp_years, ListedColormap, BoundaryNorm, plt):
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        import xarray as xr
    except Exception as exc:                                   # pragma: no cover
        print(f"  [warn] 无法绘制 d–f（{exc}）；跳过地图面板")
        return
    cmap = ListedColormap(WBT_MAP_COLORS)
    cmap.set_under("#ffffff")
    cmap.set_over("#000000")
    norm = BoundaryNorm(WBT_MAP_LEVELS, cmap.N)

    mappable = None
    for i, yr in enumerate(comp_years[:3]):
        ax = fig.add_subplot(gs[2, i], projection=ccrs.PlateCarree())
        path = os.path.join(C.INTERMEDIATE_DIR, f"wbt_compound_{yr}.nc")
        ax.set_extent(MAP_EXTENT, crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.OCEAN.with_scale("50m"), facecolor=SEA_COLOR,
                       zorder=0)
        ax.add_feature(cfeature.LAND.with_scale("50m"), facecolor="white", zorder=1)
        ax.add_feature(cfeature.BORDERS.with_scale("50m"), lw=0.4, edgecolor="k",
                       zorder=4)
        ax.add_feature(cfeature.COASTLINE.with_scale("50m"), lw=0.4, zorder=4)
        if os.path.exists(path):
            ds = xr.open_dataset(path)
            field = ds["wbt_max"] if "wbt_max" in ds else ds[list(ds.data_vars)[0]]
            mappable = ax.pcolormesh(field["lon"], field["lat"], field.values,
                                     cmap=cmap, norm=norm, shading="auto",
                                     transform=ccrs.PlateCarree(), zorder=3,
                                     rasterized=True)
        else:
            print(f"  [warn] 缺 {path}（先跑 phase5_humid.py stats）")
        ax.text(0.97, 0.97, str(yr), transform=ax.transAxes, fontsize=15,
                fontweight="bold", va="top", ha="right")
        ax.text(0.02, 0.97, f"{'def'[i]})", transform=ax.transAxes, fontsize=13,
                fontweight="bold", va="top", ha="left")

    if mappable is not None:
        # 共享水平色标（原图 9 个色块、白色分隔、无延伸箭头）
        cbar = fig.colorbar(mappable, ax=fig.axes[-3:], orientation="horizontal",
                            fraction=0.05, pad=0.05, aspect=45,
                            ticks=[18, 19, 20, 21, 22, 23, 24, 25],
                            drawedges=True)
        cbar.set_label("Wet-bulb Temperature ($\\degree$C)", fontsize=13)
        cbar.ax.tick_params(labelsize=12)
        cbar.dividers.set_color("white")
        cbar.dividers.set_linewidth(1.2)


def main(argv=None):
    p = argparse.ArgumentParser(description="论文图 6：WBT/SH 湿热极端")
    p.add_argument("--outdir", default=None)
    p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--stats", default=None,
                   help="fig6_stats.json 路径（默认 results/tables/fig6_stats.json）")
    p.add_argument("--only-curves", action="store_true",
                   help="只画 a–c（缺 WBT 场时用）")
    args = p.parse_args(argv)
    make_figure(outdir=args.outdir, dpi=args.dpi, only_curves=args.only_curves,
                stats_path=args.stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
