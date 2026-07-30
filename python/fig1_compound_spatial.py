"""
fig1_compound_spatial.py — Figure 1: compound event spatial & time-series
Panels a-i: annual compound heatwave days (9 selected years)
Panels j-l: annual spatially-weighted mean time-series
Panel   m:  co-occurrence probability spatial map
"""
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import xarray as xr

from config import INTERMEDIATE_DIR, FIGURES_DIR


def _europe_axes(ax):
    ax.set_extent([-15, 45, 30, 72], crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor='lightgray', edgecolor='none', zorder=1)
    ax.add_feature(cfeature.OCEAN, facecolor='white', edgecolor='none', zorder=1)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.3, edgecolor='gray', zorder=2)
    ax.add_feature(cfeature.BORDERS, linewidth=0.2, edgecolor='gray', alpha=0.5, zorder=2)
    gl = ax.gridlines(draw_labels=True, linewidth=0.2, color='gray', alpha=0.4)
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 5}
    gl.ylabel_style = {'size': 5}


def plot_figure1(output_dir=None):
    if output_dir is None:
        output_dir = FIGURES_DIR
    os.makedirs(output_dir, exist_ok=True)

    ann_comp = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_compound_days.nc'))
    ann_std  = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_standalone_days.nc'))
    ann_thw  = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_thw_days.nc'))
    cooc     = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'cooccurrence_prob_annual.nc'))
    da_comp  = ann_comp['compound_mhw_thw']
    da_std   = ann_std['standalone_thw']
    da_thw   = ann_thw['compound_mhw_thw']

    lat, lon = da_comp.lat.values, da_comp.lon.values
    prob_map = da_comp.mean(dim='time')

    # Specific years matching the paper
    target_years = [2003, 2006, 2010, 2012, 2018, 2019, 2020, 2021, 2022]
    top_idx = [int(np.where(da_comp.time.values == y)[0][0]) for y in target_years]
    top_years = np.array(target_years)

    # Time-series over Europe (lat 30-72, lon -15-45)
    de = da_comp.sel(lat=slice(30, 72), lon=slice(-15, 45))
    w = np.cos(np.deg2rad(de.lat))
    ts_comp = de.weighted(w).mean(dim=['lat', 'lon']).values
    ts_std  = da_std.sel(lat=slice(30, 72), lon=slice(-15, 45)).weighted(w).mean(dim=['lat', 'lon']).values
    ts_thw  = da_thw.sel(lat=slice(30, 72), lon=slice(-15, 45)).weighted(w).mean(dim=['lat', 'lon']).values
    yr_ts = de.time.values

    fig = plt.figure(figsize=(18, 14))
    gs = fig.add_gridspec(3, 5, hspace=0.3, wspace=0.25,
                          left=0.04, right=0.98, bottom=0.06, top=0.96)
    proj = ccrs.PlateCarree()

    # vmax for colorbar
    vmax = float(np.percentile(da_comp.values[da_comp.values > 0], 95))

    # ---- a-i: 9 spatial maps in 3×3 (left side, cols 0-2) ----
    LON, LAT = np.meshgrid(lon, lat)
    sc_handles = []
    for pi in range(9):
        row, col = divmod(pi, 3)
        ax = fig.add_subplot(gs[row, col], projection=proj)
        _europe_axes(ax)
        data = da_comp.isel(time=top_idx[pi]).values.astype(float)
        mask = data > 0
        if mask.any():
            sc = ax.scatter(LON[mask], LAT[mask], c=data[mask],
                            cmap='YlOrRd', vmin=0, vmax=vmax, s=3,
                            transform=ccrs.PlateCarree(), edgecolors='none')
            sc_handles.append(sc)
        label = chr(ord('a') + pi)
        ax.set_title(f'({label}) {top_years[pi]}', fontsize=8, fontweight='bold', pad=2)

    # colorbar for spatial maps
    if sc_handles:
        cax = fig.add_axes([0.32, 0.02, 0.35, 0.012])
        cbar = fig.colorbar(sc_handles[0], cax=cax, orientation='horizontal')
        cbar.set_label('Compound days / year', fontsize=7)
        cbar.ax.tick_params(labelsize=6)

    # ---- j-l: 3 time-series (col 3) ----
    ts_list = [
        ('j', 'Compound days', ts_comp, '#d73027'),
        ('k', 'Standalone days', ts_std, '#4575b4'),
        ('l', 'Total THW days', ts_thw, '#fdae61'),
    ]
    for ti, (lbl, name, ts, color) in enumerate(ts_list):
        ax = fig.add_subplot(gs[ti, 3])
        ax.fill_between(yr_ts, 0, ts, color=color, alpha=0.6, step='mid')
        ax.plot(yr_ts, ts, color=color, linewidth=0.7, marker='.', markersize=2)
        ax.set_ylabel('Days/yr', fontsize=7)
        ax.set_title(f'({lbl}) {name}', fontsize=8, fontweight='bold')
        ax.tick_params(labelsize=6)
        ax.set_xlim(yr_ts[0], yr_ts[-1])
        ax.yaxis.set_major_locator(mticker.MaxNLocator(4))
        if ti < 2:
            ax.set_xticklabels([])

    # ---- m: co-occurrence probability (col 4, spans rows 0-1) ----
    ax = fig.add_subplot(gs[0:2, 4], projection=proj)
    _europe_axes(ax)
    prob_data = prob_map.values.astype(float)
    prob_mask = prob_data > 0
    if prob_mask.any():
        sc2 = ax.scatter(LON[prob_mask], LAT[prob_mask], c=prob_data[prob_mask],
                         cmap='RdYlBu', vmin=0, vmax=0.3, s=3,
                         transform=ccrs.PlateCarree(), edgecolors='none')
        ax.set_title('(m) Co-occurrence\nprobability', fontsize=8, fontweight='bold', pad=2)
        cbar2 = fig.colorbar(sc2, ax=ax, orientation='horizontal', pad=0.06, aspect=25, shrink=0.85)
        cbar2.set_label('Probability', fontsize=6)
        cbar2.ax.tick_params(labelsize=5)
    else:
        ax.set_title('(m) Co-occurrence\nprobability (no data)', fontsize=8, fontweight='bold', pad=2)

    # ---- 3rd row col 4: empty or note ----
    ax = fig.add_subplot(gs[2, 4])
    ax.axis('off')

    import shutil, tempfile
    path = os.path.join(output_dir, 'fig1_compound_spatial.pdf')
    tmp = os.path.join(tempfile.gettempdir(), 'fig1_temp.pdf')
    fig.savefig(tmp, dpi=300, bbox_inches='tight')
    plt.close(fig)
    shutil.copy2(tmp, path)
    os.remove(tmp)
    print(f"Saved Figure 1 to: {path}")
    return path
