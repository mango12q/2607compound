"""check_new_anchors.py — 共超标新版管线 vs 论文锚点快速验证。"""
import numpy as np
import pandas as pd
import xarray as xr

INTER = r"D:\2607compound\results\intermediate"
comp = xr.open_dataset(rf"{INTER}\annual_compound_days.nc")["compound_mhw_thw"]
std = xr.open_dataset(rf"{INTER}\annual_standalone_days.nc")["standalone_thw"]
thw = xr.open_dataset(rf"{INTER}\annual_thw_days.nc")["compound_mhw_thw"]
lat, lon = comp.lat.values, comp.lon.values

REG = {"Med&BS": (30, 47, 5, 42), "Europe": (30, 72, -15, 45)}
for name, (la0, la1, lo0, lo1) in REG.items():
    la = (lat >= la0) & (lat <= la1)
    lo = (lon >= lo0) & (lon <= lo1)
    c = comp.isel(lat=np.where(la)[0], lon=np.where(lo)[0]).stack(pt=("lat", "lon"))
    s = std.isel(lat=np.where(la)[0], lon=np.where(lo)[0]).stack(pt=("lat", "lon"))
    t = thw.isel(lat=np.where(la)[0], lon=np.where(lo)[0]).stack(pt=("lat", "lon"))
    keep = t.sum("time").values > 0          # 只统计沿海配对格点
    c, s, t = c[:, keep], s[:, keep], t[:, keep]
    m22, m23 = c.sel(time=2022), c.sel(time=2023)
    early = c.sel(time=slice(1983, 1999))
    w = np.cos(np.deg2rad(c.lat.values))
    c23 = float((m23 * w).sum() / w.sum())
    s23 = float((s.sel(time=2023) * w).sum() / w.sum())
    ratio = (c.sel(time=slice(2003, 2023)).sum("time")
             / t.sel(time=slice(2003, 2023)).sum("time"))
    print(f"{name}:")
    print(f"  compound 80s-90s 均值={float(early.mean()):.2f}"
          f"  2022: mean={float(m22.mean()):.1f} maxcell={int(m22.max())}"
          f"  2023: mean={float(m23.mean()):.1f} maxcell={int(m23.max())}")
    print(f"  CHR2023(加权)={c23 / max(s23, 1e-9):.2f}"
          f"  cooc03-23: p50={float(ratio.median()):.3f}"
          f" p90={float(ratio.quantile(0.9)):.3f} max={float(ratio.max()):.3f}")
print("\n论文锚点: fig1j 80s<20 / 2022~78 / 2023~72 | fig2c 2023=3.5"
      " | fig1m 地中海 0.6-0.8, 西地中海>0.8")
