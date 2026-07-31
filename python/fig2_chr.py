"""
fig2_chr.py — Figure 2: CHR analysis
Panel a: spatial map of mean compound MHW-THW days (2003-2023)
Panel b: spatial map of standalone THW days (2003-2023 mean)
Panel c: CHR time-series (1983-2023)
Panel d: spatial map of mean CHR (2003-2023)
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
    gl.top_labels = False; gl.right_labels = False
    gl.xlabel_style = {'size': 5}; gl.ylabel_style = {'size': 5}


def _scatter_map(ax, lon, lat, data, cmap, vmax, vmin=0, title=None, s=3):
    """Scatter plot on Europe map, colored by value."""
    LON, LAT = np.meshgrid(lon, lat)
    mask = data > 0
    if mask.any():
        sc = ax.scatter(LON[mask], LAT[mask], c=data[mask],
                        cmap=cmap, vmin=vmin, vmax=vmax, s=s,
                        transform=ccrs.PlateCarree(), edgecolors='none')
        if title:
            ax.set_title(title, fontsize=9, fontweight='bold', pad=2)
        return sc
    return None


def plot_figure2(output_dir=None):
    if output_dir is None:
        output_dir = FIGURES_DIR
    os.makedirs(output_dir, exist_ok=True)

    ann_comp = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_compound_days.nc'))
    ann_std  = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'annual_standalone_days.nc'))
    chr_ds   = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, 'CHR_annual.nc'))

    da_comp = ann_comp['compound_mhw_thw']
    da_std  = ann_std['standalone_thw']
    da_chr  = chr_ds[list(chr_ds.data_vars)[0]]

    lat, lon = da_comp.lat.values, da_comp.lon.values
    years = da_comp.time.values.astype(int)

    # Mean fields over 2003-2023
    comp_mean = da_comp.sel(time=slice(2003, 2023)).mean(dim='time').values.astype(float)
    std_mean  = da_std.sel(time=slice(2003, 2023)).mean(dim='time').values.astype(float)
    chr_map   = da_chr.sel(time=slice(2003, 2023)).mean(dim='time').values.astype(float)

    # Europe-wide mean CHR time-series (1983-2023)
    de = da_chr.sel(lat=slice(30, 72), lon=slice(-15, 45))
    w = np.cos(np.deg2rad(de.lat))
    chr_ts = de.weighted(w).mean(dim=['lat', 'lon']).values

    # Fixed vmax to match paper color scales
    vmax_comp = 20   # compound days: paper shows >20 in some regions
    vmax_std  = 20   # standalone days: same color scale as compound (0-20)
    vmax_chr  = 5    # CHR: paper shows 0-5 range

    proj = ccrs.PlateCarree()
    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(2, 4, hspace=0.4, wspace=0.28,
                          left=0.05, right=0.97, bottom=0.08, top=0.93,
                          width_ratios=[1, 1, 0.9, 0.12])

    # ---- a: mean compound days map ----
    ax = fig.add_subplot(gs[0, 0], projection=proj)
    _europe_axes(ax)
    sc = _scatter_map(ax, lon, lat, comp_mean, 'YlOrRd', vmax_comp,
                      title='(a) Compound Marine-Terrestrial\nHeatwave Days\n(mean over 2003\u20132023)')
    if sc:
        cbar = fig.colorbar(sc, ax=ax, orientation='horizontal', pad=0.05, aspect=20, shrink=0.85)
        cbar.set_label('Days/year', fontsize=7)
        cbar.ax.tick_params(labelsize=6)

    # ---- b: mean standalone days map ----
    ax = fig.add_subplot(gs[0, 1], projection=proj)
    _europe_axes(ax)
    sc = _scatter_map(ax, lon, lat, std_mean, 'YlOrRd', vmax_std,
                      title='(b) Stand-alone Terrestrial\nHeatwave Days\n(mean over 2003\u20132023)')
    if sc:
        cbar = fig.colorbar(sc, ax=ax, orientation='horizontal', pad=0.05, aspect=20, shrink=0.85)
        cbar.set_label('Days/year', fontsize=7)
        cbar.ax.tick_params(labelsize=6)

    # ---- c: CHR time-series (line chart) ----
    ax = fig.add_subplot(gs[0, 2])
    ax.fill_between(years, 0, chr_ts, color='#d73027', alpha=0.5, step='mid')
    ax.plot(years, chr_ts, color='#d73027', linewidth=1, marker='.', markersize=3)
    ax.axhline(1, color='gray', linestyle='--', linewidth=0.7, alpha=0.6)
    ax.set_ylabel('CHR', fontsize=9)
    ax.set_title('(c) CHR time-series (1983\u20132023)', fontsize=9, fontweight='bold')
    ax.tick_params(labelsize=7)
    ax.set_xlim(years[0], years[-1])
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.3)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(5))

    # ---- d: mean CHR map ----
    ax = fig.add_subplot(gs[1, :3], projection=proj)
    _europe_axes(ax)
    sc = _scatter_map(ax, lon, lat, chr_map, 'RdYlBu', vmax_chr,
                      title='(d) Mean CHR (2003\u20132023)')
    if sc:
        cbar = fig.colorbar(sc, ax=ax, orientation='horizontal', pad=0.06, aspect=30, shrink=0.85)
        cbar.set_label('CHR', fontsize=8)
        cbar.ax.tick_params(labelsize=7)

    import shutil, tempfile
    path = os.path.join(output_dir, 'fig2_chr.pdf')
    tmp = os.path.join(tempfile.gettempdir(), 'fig2_temp.pdf')
    fig.savefig(tmp, dpi=300, bbox_inches='tight')
    plt.close(fig)
    shutil.copy2(tmp, path)
    os.remove(tmp)
    print(f"Saved Figure 2 to: {path}")
    return path
