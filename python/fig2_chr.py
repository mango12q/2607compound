"""
fig2_chr.py — Figure 2: Compound Heatwaves Ratio (CHR)

版式（2026-09-23 重绘，对齐论文 Fig.2 原图 pdf_extract/fig2_p04.png）：
    a) 上左：复合 MHW–THW 天数空间分布（2003–2023 平均），色标 6–20 "Heatwave days"
    b) 上右：stand-alone 陆地热浪天数空间分布（2003–2023 平均），共用 a 的色标
    c) 下左：CHR 时间序列（1983–2023），含**两段式**红色趋势线与 CHR 公式标注
    d) 下右：CHR 空间分布（2003–2023 平均），色标 0–5

统计口径：
    a/b 为区间**均值场**；d 为区间**总和之比**（论文 caption "ratio ... over the
    period 2003–2023" 的字面读法，见 复现报告.md D4）；c 为逐年 cos 加权总和之比。
"""
import os

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr

from config import INTERMEDIATE_DIR, FIGURES_DIR

CB_DAYS = dict(vmin=6.0, vmax=20.0)      # 论文 (a)/(b)
CB_CHR = dict(vmin=0.0, vmax=5.0)        # 论文 (d)
CMAP_DAYS = 'magma_r'
CMAP_CHR = 'viridis'

X_TICKS = list(range(1983, 2024, 4))
SEG1 = (1983, 2002)                       # 论文 (c) 的两段式趋势：1983–2002 持平
SEG2 = (2003, 2022)                       #                          2003–2022 上升


def _europe_axes(ax, frame_lw=0.6):
    """论文风格底图：陆地浅灰、海洋白、无网格线、无经纬刻度标签。"""
    ax.set_extent([-15, 45, 30, 72], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor='#d9d9d9', edgecolor='none', zorder=1)
    ax.add_feature(cfeature.OCEAN, facecolor='white', edgecolor='none', zorder=1)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.35, edgecolor='black', zorder=2)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(frame_lw)


def _map(ax, LON, LAT, data, cmap, cb, title, letter):
    _europe_axes(ax)
    d = np.asarray(data, dtype=float)
    m = np.isfinite(d) & (d > 0)
    sc = None
    if m.any():
        sc = ax.scatter(LON[m], LAT[m], c=d[m], cmap=cmap,
                        vmin=cb['vmin'], vmax=cb['vmax'], s=22, marker='o',
                        linewidths=0, transform=ccrs.PlateCarree(), zorder=4)
    ax.text(0.0, 1.045, f'{letter})', transform=ax.transAxes, ha='left',
            va='bottom', fontsize=13, fontweight='bold')
    ax.set_title(title, fontsize=12)
    return sc


def plot_figure2(output_dir=None):
    if output_dir is None:
        output_dir = FIGURES_DIR
    os.makedirs(output_dir, exist_ok=True)

    ann_comp = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_compound_days.nc'))
    ann_std = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_standalone_days.nc'))
    da_comp = ann_comp['compound_mhw_thw']
    da_std = ann_std['standalone_thw']

    lat, lon = da_comp.lat.values, da_comp.lon.values
    LON, LAT = np.meshgrid(lon, lat)

    # (a)/(b) 2003–2023 均值场
    comp_mean = da_comp.sel(time=slice(2003, 2023)).mean(dim='time').values.astype(float)
    std_mean = da_std.sel(time=slice(2003, 2023)).mean(dim='time').values.astype(float)

    # (d) 区间总和之比（论文 caption 字面口径）
    c_sum = da_comp.sel(time=slice(2003, 2023)).sum(dim='time')
    s_sum = da_std.sel(time=slice(2003, 2023)).sum(dim='time')
    chr_map = xr.where(s_sum > 0, c_sum / s_sum, np.nan).values.astype(float)

    # (c) 逐年 cos 加权总和之比
    years = da_comp.time.values.astype(int)
    c_ts = da_comp.sel(lat=slice(30, 72), lon=slice(-15, 45))
    s_ts = da_std.sel(lat=slice(30, 72), lon=slice(-15, 45))
    w = np.cos(np.deg2rad(c_ts.lat))
    chr_ts = ((c_ts * w).sum(dim=['lat', 'lon'])
              / (s_ts * w).sum(dim=['lat', 'lon'])).values

    # ================= 画布：论文 2×2 =================
    fig = plt.figure(figsize=(13.0, 7.75))
    outer = fig.add_gridspec(2, 1, height_ratios=[1.02, 1.0], hspace=0.30,
                             left=0.035, right=0.935, top=0.925, bottom=0.085)
    proj = ccrs.PlateCarree()

    # ---------- 上排：a、b + 共用色标 ----------
    g_top = outer[0].subgridspec(1, 3, width_ratios=[1, 1, 0.042], wspace=0.10)
    ax_a = fig.add_subplot(g_top[0, 0], projection=proj)
    sc_a = _map(ax_a, LON, LAT, comp_mean, CMAP_DAYS, CB_DAYS,
                'Compound Marine-Terrestrial Heatwave Days\n(mean over 2003-2023)', 'a')
    ax_b = fig.add_subplot(g_top[0, 1], projection=proj)
    _map(ax_b, LON, LAT, std_mean, CMAP_DAYS, CB_DAYS,
         'Stand-alone Terrestrial Heatwave Days\n(mean over 2003-2023)', 'b')
    if sc_a is not None:
        cax = fig.add_subplot(g_top[0, 2])
        cb = fig.colorbar(sc_a, cax=cax, extend='max')
        cb.set_label('Heatwave days', fontsize=10)
        cb.ax.tick_params(labelsize=9)

    # ---------- 下排：c（时序）、d（空间）+ 色标 ----------
    g_bot = outer[1].subgridspec(1, 3, width_ratios=[1, 1, 0.042], wspace=0.10)

    ax_c = fig.add_subplot(g_bot[0, 0])
    ax_c.plot(years, chr_ts, '-', color='#1b2f6e', linewidth=0.9,
              marker='o', markersize=3.6, markerfacecolor='#1b2f6e',
              markeredgecolor='#1b2f6e', zorder=4)
    # 论文：红色趋势为**两段式直线**（1983–2002 持平；2003–2022 上升）
    for (y0, y1) in (SEG1, SEG2):
        sel = (years >= y0) & (years <= y1) & np.isfinite(chr_ts)
        if sel.sum() >= 2:
            k, b = np.polyfit(years[sel], chr_ts[sel], 1)
            ax_c.plot([y0, y1], [k * y0 + b, k * y1 + b], '-', color='red',
                      linewidth=2.0, zorder=5)
    for y in (2003, 2018, 2023):
        i = int(np.where(years == y)[0][0])
        ax_c.annotate(str(y), xy=(y, chr_ts[i]), xytext=(-6, 9),
                      textcoords='offset points', fontsize=11, color='blue',
                      ha='center', zorder=6)
    ax_c.set_xlim(1982, 2024)
    ax_c.set_xticks(X_TICKS)
    ax_c.set_xticklabels([str(t) for t in X_TICKS], fontsize=9)
    ax_c.set_ylim(0, 3.6)
    ax_c.set_yticks(np.arange(0, 3.6, 0.5))
    ax_c.tick_params(axis='y', labelsize=9)
    ax_c.set_ylabel('Compound Heatwaves Ratio (CHR)', fontsize=10)
    ax_c.set_xlabel('years (1983-2023)', fontsize=10)
    ax_c.grid(True, alpha=0.35, linestyle='-', linewidth=0.4)
    ax_c.set_title('Compound Heatwaves Ratio (CHR)', fontsize=12)
    ax_c.text(0.0, 1.045, 'c)', transform=ax_c.transAxes, ha='left', va='bottom',
              fontsize=13, fontweight='bold')
    # 公式标注（论文原图样式）
    ax_c.text(0.03, 0.90,
              r'$CHR\ =\ \dfrac{\mathrm{Compound\ HW\ days}}'
              r'{\mathrm{stand\_alone\ THW\ days}}$',
              transform=ax_c.transAxes, fontsize=11, va='top', ha='left',
              bbox=dict(boxstyle='square,pad=0.25', facecolor='white',
                        edgecolor='none', alpha=0.85), zorder=6)

    ax_d = fig.add_subplot(g_bot[0, 1], projection=proj)
    sc_d = _map(ax_d, LON, LAT, chr_map, CMAP_CHR, CB_CHR,
                'Compound Heatwaves Ratio (CHR)\n(mean over 2003-2023)', 'd')
    if sc_d is not None:
        cax2 = fig.add_subplot(g_bot[0, 2])
        cb2 = fig.colorbar(sc_d, cax=cax2)
        cb2.set_label('Compound Heatwaves Ratio (CHR)', fontsize=9)
        cb2.ax.tick_params(labelsize=9)

    import shutil
    import tempfile
    path = os.path.join(output_dir, 'fig2_chr.pdf')
    tmp = os.path.join(tempfile.gettempdir(), 'fig2_temp.pdf')
    fig.savefig(tmp, dpi=300)
    tmp_png = os.path.join(tempfile.gettempdir(), 'fig2_temp.png')
    fig.savefig(tmp_png, dpi=190)
    plt.close(fig)
    try:
        shutil.copy2(tmp, path)
    except PermissionError:
        path = os.path.join(output_dir, 'fig2_chr_new.pdf')
        shutil.copy2(tmp, path)
        print("NOTE: fig2_chr.pdf 被占用(可能在预览中打开), 已另存 fig2_chr_new.pdf")
    os.remove(tmp)
    png_path = os.path.join(output_dir, 'fig2_chr.png')
    try:
        shutil.copy2(tmp_png, png_path)
    except PermissionError:
        png_path = os.path.join(output_dir, 'fig2_chr_new.png')
        shutil.copy2(tmp_png, png_path)
    os.remove(tmp_png)
    print(f"Saved Figure 2 to: {path}")
    return path
