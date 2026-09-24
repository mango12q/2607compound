"""
fig1_compound_spatial.py — Figure 1: compound event spatial & time-series

版式（2026-09-23 重绘，对齐论文 Fig.1 原图 pdf_extract/fig1_p03.png）：
    a–i : 3×3 空间分布（9 个指定年份），色标置于右侧竖向，范围 5–50
    j–l : **与 a–i 同宽的一整行** 折线图（带数据点 + 红色虚线非线性趋势），
          y 轴 0–90，标题 "Compound Coastal Marine-Terrestrial Heatwave Days"
    m   : 独立行的大图（共现概率），色标置于其右侧
口径（方案 B，见 TECHNICAL_SPEC.md §3.6）：
    a–i / m 用**逐日共超标**（论文 L477）；j–l 用 **MHW 包络**（论文 L520）。
"""
import os
import json

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
from scipy.optimize import curve_fit

from config import INTERMEDIATE_DIR, FIGURES_DIR

# 论文 Fig.1 的色标范围（a–i 与 m）
CB_A_I = dict(vmin=5.0, vmax=50.0)
CB_M = dict(vmin=0.2, vmax=0.8)
CMAP_A_I = 'magma_r'      # 浅黄(5) → 橙 → 红 → 品红 → 黑(50)
CMAP_M = 'magma_r'

X_TICKS = list(range(1983, 2024, 3))


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


def _year_box(ax, year_or_text):
    """右上角年份标签框（论文样式）。"""
    ax.text(0.975, 0.965, str(year_or_text), transform=ax.transAxes,
            ha='right', va='top', fontsize=11, fontweight='bold', zorder=6,
            bbox=dict(boxstyle='round,pad=0.28', facecolor='white',
                      edgecolor='#999999', linewidth=0.6, alpha=0.95))


# 论文 a–i 中的地理标注：面板序号 → [(文字, 目标经度, 目标纬度, 文字偏移)]
GEO_NOTES = {
    0: [('Corsica', 9.0, 42.1, (-0.35, 0.42)), ('Sardinia', 9.0, 39.9, (-0.30, -0.45))],
    3: [('Western\nBlack Sea', 28.6, 43.4, (-0.55, 0.30))],
    4: [('Balearics', 2.9, 39.6, (-0.45, 0.28))],
    5: [('Ligurian\nCoast', 8.6, 44.0, (-0.62, 0.26))],
    7: [('Cantabrian', -4.0, 43.4, (-0.60, 0.30))],
    8: [('Andalusian', -5.0, 36.8, (-0.62, 0.30))],
}


def _geo_notes(ax, idx, fs=6):
    for text, lo, la, (dx, dy) in GEO_NOTES.get(idx, []):
        ax.annotate(text, xy=(lo, la), xytext=(lo + dx, la + dy),
                    fontsize=fs, ha='center', va='center', color='black', zorder=7,
                    arrowprops=dict(arrowstyle='-', color='black', lw=0.5,
                                    shrinkA=0, shrinkB=2))


def _convex_trend(ax, yr, vals, color='red', lw=1.6):
    """论文 j/l 的红色虚线非线性（二次）趋势。"""
    valid = np.isfinite(vals)
    if valid.sum() <= 3:
        return
    def _f(x, a, b, c):
        return a * (x - 1983) + b * (x - 1983) ** 2 + c
    popt, _ = curve_fit(_f, yr[valid], vals[valid],
                        bounds=([-np.inf, 0, -np.inf], [np.inf, np.inf, np.inf]),
                        maxfev=20000)
    ax.plot(yr, _f(yr, *popt), '--', color=color, linewidth=lw, zorder=5)


def plot_figure1(output_dir=None):
    if output_dir is None:
        output_dir = FIGURES_DIR
    os.makedirs(output_dir, exist_ok=True)

    ann_comp = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_compound_days.nc'))
    ann_thw = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_thw_days.nc'))
    da_comp = ann_comp['compound_mhw_thw']
    da_thw = ann_thw['compound_mhw_thw']

    lat, lon = da_comp.lat.values, da_comp.lon.values
    LON, LAT = np.meshgrid(lon, lat)

    # ---- Fig.1m: 共现概率 = 区间内复合总和 / 陆地热浪总和 ----
    comp_0323 = da_comp.sel(time=slice(2003, 2023)).sum(dim='time')
    thw_0323 = da_thw.sel(time=slice(2003, 2023)).sum(dim='time')
    prob_map = xr.where(thw_0323 > 0, comp_0323 / thw_0323, np.nan)

    target_years = [2003, 2006, 2010, 2012, 2018, 2019, 2020, 2022, 2023]
    top_idx = [int(np.where(da_comp.time.values == y)[0][0]) for y in target_years]

    # ---- j/k/l：MHW 包络口径（论文 L520）----
    env_path = os.path.join(os.path.dirname(INTERMEDIATE_DIR), 'tables', 'fig_jkl_envelope.json')
    with open(env_path, encoding='utf-8') as fh:
        env = json.load(fh)
    ts_spec = [
        ('j', 'Mediterranean &\nBlack Sea', 'fig1j_mediterranean',
         [1994, 2003, 2022], True),
        ('k', 'Baltic Sea', 'fig1k_baltic', [1990, 2006, 2020], False),
        ('l', 'European Coasts', 'fig1l_european',
         [1990, 2003, 2010, 2018, 2020, 2023], True),
    ]
    yr_ts = np.arange(1983, 2024)

    # ================= 画布 =================
    fig = plt.figure(figsize=(13.0, 17.4))
    outer = fig.add_gridspec(3, 1, height_ratios=[3.15, 1.15, 1.45], hspace=0.30,
                             left=0.045, right=0.955, top=0.988, bottom=0.022)
    proj = ccrs.PlateCarree()

    # ---------- a–i : 3×3 + 右侧竖向色标 ----------
    g_top = outer[0].subgridspec(3, 4, width_ratios=[1, 1, 1, 0.045],
                                 hspace=0.10, wspace=0.055)
    sc_ref = None
    for pi in range(9):
        r, c = divmod(pi, 3)
        ax = fig.add_subplot(g_top[r, c], projection=proj)
        _europe_axes(ax)
        data = da_comp.isel(time=top_idx[pi]).values.astype(float)
        m = data > 0
        if m.any():
            sc = ax.scatter(LON[m], LAT[m], c=data[m], cmap=CMAP_A_I,
                            vmin=CB_A_I['vmin'], vmax=CB_A_I['vmax'],
                            s=16, marker='o', linewidths=0,
                            transform=proj, zorder=4)
            sc_ref = sc_ref or sc
        ax.text(0.02, 0.985, f"({chr(ord('a') + pi)})", transform=ax.transAxes,
                ha='left', va='top', fontsize=11, fontweight='bold', zorder=6)
        _year_box(ax, target_years[pi])
        _geo_notes(ax, pi)

    cax = fig.add_subplot(g_top[:, 3])
    if sc_ref is not None:
        cb = fig.colorbar(sc_ref, cax=cax, extend='max')
        cb.set_label('Compound heatwave days', fontsize=9)
        cb.ax.tick_params(labelsize=8)

    # ---------- j–l : 整行折线图 ----------
    # 论文原图 y 轴为 0–90。我们的包络口径在 2020/2023 达 93–121，超出该量程，
    # 故统一扩到 0–130（保持每 10 一格、三面板同刻度，便于互比），不裁掉数据。
    ymax_common = 90.0
    for _l, _n, _k, _a, _t in ts_spec:
        ymax_common = max(ymax_common, float(np.nanmax(np.asarray(env[_k]['values'], float))))
    ymax_common = np.ceil(ymax_common / 10.0) * 10.0

    fig.text(0.50, 0.5070, 'Compound Coastal Marine-Terrestrial Heatwave Days',
             ha='center', va='center', fontsize=17)

    g_mid = outer[1].subgridspec(1, 3, wspace=0.28)
    for ti, (lbl, name, key, ann_years, with_trend) in enumerate(ts_spec):
        ax = fig.add_subplot(g_mid[ti])
        vals = np.asarray(env[key]['values'], dtype=float)
        ax.plot(yr_ts, vals, '-', color='#1b2f6e', linewidth=0.9,
                marker='o', markersize=3.2, markerfacecolor='#1b2f6e',
                markeredgecolor='#1b2f6e', zorder=4)
        if with_trend:                       # 论文：红虚线只出现在 j 与 l
            _convex_trend(ax, yr_ts, vals)
        ax.axhline(0, color='black', linewidth=0.6)
        for y in ann_years:
            i = int(np.where(yr_ts == y)[0][0])
            ax.annotate(str(y), xy=(y, vals[i]), xytext=(0, 9),
                        textcoords='offset points', fontsize=9, color='blue',
                        ha='center', zorder=6)
        ax.set_ylim(0, ymax_common)
        ax.set_yticks(range(0, int(ymax_common) + 1, 10))
        ax.set_xlim(1982, 2024)
        ax.set_xticks(X_TICKS)
        ax.set_xticklabels([str(t) for t in X_TICKS], rotation=60, fontsize=8)
        ax.tick_params(axis='y', labelsize=9)
        ax.grid(True, alpha=0.35, linestyle=':', linewidth=0.5)
        ax.set_xlabel('(1983-2023)', fontsize=9, labelpad=14)
        if ti == 0:
            ax.set_ylabel('Compound MHW/THW Days', fontsize=9)
        ax.legend([name.replace('\n', ' ')], loc='upper left', fontsize=9,
                  framealpha=0.95, handlelength=1.6)
        ax.text(0.965, 0.06, f'({lbl})', transform=ax.transAxes,
                ha='right', va='bottom', fontsize=13, fontweight='bold')

    # ---------- m : 独立大图 + 右侧色标 ----------
    g_bot = outer[2].subgridspec(1, 4, width_ratios=[0.42, 1, 0.045, 0.42],
                                 wspace=0.03)
    ax = fig.add_subplot(g_bot[0, 1], projection=proj)
    _europe_axes(ax)
    pv = prob_map.values.astype(float)
    ok = np.isfinite(pv) & (pv > 0)
    sc2 = None
    if ok.any():
        sc2 = ax.scatter(LON[ok], LAT[ok], c=pv[ok], cmap=CMAP_M,
                         vmin=CB_M['vmin'], vmax=CB_M['vmax'],
                         s=16, marker='o', linewidths=0, transform=proj, zorder=4)
    # 用相对本面板的 set_title，避免与上方 j–l 的 x 轴标签重叠
    ax.set_title('Co-occurrence Probability\n(mean over 2003-2023)',
                 fontsize=14, pad=10)
    ax.text(0.02, 0.985, '(m)', transform=ax.transAxes, ha='left', va='top',
            fontsize=11, fontweight='bold', zorder=6)
    if sc2 is not None:
        cax2 = fig.add_subplot(g_bot[0, 2])
        cb2 = fig.colorbar(sc2, cax=cax2, extend='max')
        cb2.set_label('Co-occurrence probability', fontsize=9)
        cb2.ax.tick_params(labelsize=8)

    import shutil
    import tempfile
    path = os.path.join(output_dir, 'fig1_compound_spatial.pdf')
    tmp = os.path.join(tempfile.gettempdir(), 'fig1_temp.pdf')
    fig.savefig(tmp, dpi=300)
    tmp_png = os.path.join(tempfile.gettempdir(), 'fig1_temp.png')
    fig.savefig(tmp_png, dpi=170)
    plt.close(fig)
    shutil.copy2(tmp, path)
    os.remove(tmp)
    shutil.copy2(tmp_png, os.path.join(output_dir, 'fig1_compound_spatial.png'))
    os.remove(tmp_png)
    print(f"Saved Figure 1 to: {path}")
    return path


def plot_figure1_jkl_maxcell(output_dir=None):
    """补充图: 图1 j/k/l 的逐格点**最大值**版本。

    论文正文引述 Med 2022~78/2023~72 天, 但 90 分位阈值下 90% 的年份单点年
    THW 天数 <=~70 天, 78 天不可能是逐点区域均值; 论文曲线更接近格点最大值
    (或热点子区均值)。本图输出 max-cell 版本供与论文面板目视比对定稿。
    """
    import shutil
    import tempfile
    if output_dir is None:
        output_dir = FIGURES_DIR
    os.makedirs(output_dir, exist_ok=True)

    ann_comp = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_compound_days.nc'))
    da_comp = ann_comp['compound_mhw_thw']

    regions = [
        ('j', 'Mediterranean &\nBlack Sea', {'lat': (30, 47), 'lon': (5, 42)}),
        ('k', 'Baltic Sea',                 {'lat': (53, 66), 'lon': (10, 30)}),
        ('l', 'European Coasts',            {'lat': (30, 72), 'lon': (-15, 45)}),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(6, 9), sharex=True)
    for ax, (lbl, name, region) in zip(axes, regions):
        r = da_comp.sel(lat=slice(*region['lat']), lon=slice(*region['lon']))
        mask = r.mean(dim='time') > 0
        r_masked = r.where(mask)
        ts = r_masked.max(dim=['lat', 'lon'])
        yr = ts.time.values.astype(int)
        vals = ts.values
        ax.fill_between(yr, 0, vals, color='#d73027', alpha=0.6, step='mid')
        ax.plot(yr, vals, color='#d73027', linewidth=0.8, marker='.', markersize=2)
        ax.set_ylabel('Days/year', fontsize=8)
        ax.set_title(f"({lbl}) {name.replace(chr(10), ' ')} — max-cell compound days",
                     fontsize=9, fontweight='bold')
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.3)

    axes[-1].set_xlim(1983, 2023)
    axes[-1].set_xticks(range(1983, 2024, 5))
    fig.suptitle('Fig.1 j-l supplementary: per-cell MAXIMUM compound days\n'
                 '(paper quotes Med 2022~78 / 2023~72 days)', fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.94])

    path = os.path.join(output_dir, 'figS1_jkl_maxcell.pdf')
    tmp = os.path.join(tempfile.gettempdir(), 'figS1_temp.pdf')
    fig.savefig(tmp, dpi=300, bbox_inches='tight')
    tmp_png = os.path.join(tempfile.gettempdir(), 'figS1_temp.png')
    fig.savefig(tmp_png, dpi=200, bbox_inches='tight')
    plt.close(fig)
    shutil.copy2(tmp, path)
    os.remove(tmp)
    shutil.copy2(tmp_png, os.path.join(output_dir, 'figS1_jkl_maxcell.png'))
    os.remove(tmp_png)
    print(f"Saved Figure S1 (jkl max-cell) to: {path}")
    return path






