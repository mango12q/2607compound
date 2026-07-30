"""
fig2_chr.py — Figure 2: CHR analysis
Panel a: compound days per year (stacked by coastal region)
Panel b: standalone days per year (stacked by coastal region)
Panel c: CHR time-series
Panel d: CHR spatial map (mean over the period)
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr
import pandas as pd

from config import INTERMEDIATE_DIR, FIGURES_DIR, EUROPEAN_COASTS


def _europe_axes(ax):
    ax.set_extent([-15, 45, 30, 72], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='none', zorder=1)
    ax.add_feature(cfeature.OCEAN, facecolor='white', edgecolor='none', zorder=1)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor='gray', zorder=2)
    ax.add_feature(cfeature.BORDERS, linewidth=0.2, edgecolor='gray', alpha=0.5, zorder=2)
    gl = ax.gridlines(draw_labels=True, linewidth=0.2, color='gray', alpha=0.4)
    gl.top_labels = False; gl.right_labels = False
    gl.xlabel_style = {'size': 6}; gl.ylabel_style = {'size': 6}


def _region_mask(lat, lon, region):
    b = EUROPEAN_COASTS[region]
    return ((lat >= b['lat'][0]) & (lat <= b['lat'][1]) &
            (lon >= b['lon'][0]) & (lon <= b['lon'][1]))


def plot_figure2(output_dir=None):
    if output_dir is None:
        output_dir = FIGURES_DIR
    os.makedirs(output_dir, exist_ok=True)

    ann_comp = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_compound_days.nc'))
    ann_std  = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_standalone_days.nc'))
    chr_ds   = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'CHR_annual.nc'))
    cooc     = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'cooccurrence_prob_annual.nc'))

    da_comp = ann_comp['compound_mhw_thw']
    da_std  = ann_std['standalone_thw']
    da_chr  = chr_ds['__xarray_dataarray_variable__']
    lat, lon = da_comp.lat.values, da_comp.lon.values
    years   = da_comp.time.values

    # Regional sums
    regions = list(EUROPEAN_COASTS.keys())
    comp_reg, std_reg = {}, {}
    for r in regions:
        m = _region_mask(lat[:, None], lon[None, :], r)
        comp_reg[r] = da_comp.values[:, m].sum(axis=1)
        std_reg[r]  = da_std.values[:, m].sum(axis=1)

    # Europe-wide mean CHR time-series
    w = np.cos(np.deg2rad(da_comp.lat))
    chr_ts = da_chr.sel(lat=slice(30, 72), lon=slice(-15, 45)) \
        .weighted(w.sel(lat=slice(30, 72))).mean(dim=['lat', 'lon']).values

    # CHR mean map
    chr_map = da_chr.mean(dim='time')

    fig = plt.figure(figsize=(14, 10))
    gs = fig.add_gridspec(2, 3, hspace=0.35, wspace=0.3,
                          left=0.06, right=0.97, bottom=0.08, top=0.95)
    colors = {'Mediterranean': '#e41a1c', 'BlackSea': '#377eb8',
              'Baltic': '#4daf4a', 'Atlantic': '#984ea3'}
    x = np.arange(len(years))
    bar_width = 0.7

    # ---- a: compound days (stacked bars) ----
    ax = fig.add_subplot(gs[0, 0])
    bottom = np.zeros(len(years))
    for r in regions:
        ax.bar(x, comp_reg[r], bar_width, bottom=bottom,
               label=r, color=colors[r], alpha=0.85, edgecolor='white', linewidth=0.1)
        bottom += comp_reg[r]
    ax.set_ylabel('Compound days', fontsize=9)
    ax.set_title('(a) Annual compound days by region', fontsize=10, fontweight='bold')
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=6, loc='upper left')
    ax.set_xlim(-0.5, len(years) - 0.5)

    # ---- b: standalone days (stacked bars) ----
    ax = fig.add_subplot(gs[0, 1])
    bottom = np.zeros(len(years))
    for r in regions:
        ax.bar(x, std_reg[r], bar_width, bottom=bottom,
               label=r, color=colors[r], alpha=0.85, edgecolor='white', linewidth=0.1)
        bottom += std_reg[r]
    ax.set_ylabel('Standalone days', fontsize=9)
    ax.set_title('(b) Annual standalone days by region', fontsize=10, fontweight='bold')
    ax.tick_params(labelsize=7)
    ax.set_xlim(-0.5, len(years) - 0.5)
    ax.set_yticklabels([])

    # ---- c: CHR time-series ----
    ax = fig.add_subplot(gs[0, 2])
    ax.fill_between(years, 0, chr_ts, color='#d73027', alpha=0.5, step='mid')
    ax.plot(years, chr_ts, color='#d73027', linewidth=1, marker='.', markersize=3)
    ax.axhline(1, color='gray', linestyle='--', linewidth=0.7, alpha=0.6)
    ax.set_ylabel('CHR', fontsize=9)
    ax.set_title('(c) CHR time-series (Europe coastal)', fontsize=10, fontweight='bold')
    ax.tick_params(labelsize=7)
    ax.set_xlim(years[0], years[-1])

    # ---- d: CHR spatial map ----
    ax = fig.add_subplot(gs[1, :], projection=ccrs.PlateCarree())
    chr_raw = chr_map.values.astype(float).copy()
    vmax = float(np.nanpercentile(chr_raw[chr_raw > 0], 95))
    chr_data = np.ma.masked_where(chr_raw <= 0, chr_raw)
    im = ax.pcolormesh(lon, lat, chr_data, cmap='YlOrRd',
                       vmin=0, vmax=vmax, transform=ccrs.PlateCarree())
    _europe_axes(ax)
    ax.set_title('(d) Mean CHR (1984–2022)', fontsize=10, fontweight='bold', pad=4)
    cbar = fig.colorbar(im, ax=ax, orientation='horizontal', pad=0.06, aspect=35, shrink=0.8)
    cbar.set_label('CHR', fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    path = os.path.join(output_dir, 'fig2_chr.pdf')
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved Figure 2 to: {path}")
    return path
