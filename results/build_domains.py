"""build_domains.py — 生成 R 检测用的域点清单。

海洋侧：只需 coastal_pairs.csv 里实际参与 compound 判定的 1,434 个 OISST 格点
        （OISST 全球 15.9 G 格点，只测需要的点可以把检测从数小时压到数分钟）。
陆地侧：用全网格（由 detect_events.R 自动判定候选点），保证后续空间图可用。
"""
import os

import numpy as np
import pandas as pd
import xarray as xr

INTER = r"D:\2607compound\results\intermediate"
OUT = os.path.join(INTER, "domains_ocean_pairs.csv")

pairs = pd.read_csv(os.path.join(INTER, "coastal_pairs.csv"))
oce = pairs[["ocean_lat_idx", "ocean_lon_idx", "ocean_lat", "ocean_lon"]].drop_duplicates()
print(f"coastal_pairs: {len(pairs):,} pairs -> {len(oce):,} unique ocean grid points")
print(f"  ocean_lat {oce.ocean_lat.min():.3f} .. {oce.ocean_lat.max():.3f}")
print(f"  ocean_lon {oce.ocean_lon.min():.3f} .. {oce.ocean_lon.max():.3f}")

# OISST 的 ocean_lon 若落在 0..360，转成 -180..180（与裁剪后文件一致）
olon = np.where(oce.ocean_lon.values > 180, oce.ocean_lon.values - 360, oce.ocean_lon.values)
print(f"  after wrap: {olon.min():.3f} .. {olon.max():.3f}")

# 验证这些点确实落在裁剪后的 OISST 域内
CLIP = r"E:\2607compound\data\OISST\oisst_v2.1_eur_1983_2023.nc"
df = pd.DataFrame({"lat": oce.ocean_lat.values, "lon": olon})
if os.path.exists(CLIP):
    ds = xr.open_dataset(CLIP)
    clat, clon = ds.lat.values, ds.lon.values
    print(f"  clipped OISST: lon {clon.min():.3f}..{clon.max():.3f}, "
          f"lat {clat.min():.3f}..{clat.max():.3f}")
    # 最近邻误差
    li = np.abs(clat[None, :] - df.lat.values[:, None]).argmin(axis=1)
    lj = np.abs(clon[None, :] - df.lon.values[:, None]).argmin(axis=1)
    dlat = np.abs(clat[li] - df.lat.values)
    dlon = np.abs(clon[lj] - df.lon.values)
    print(f"  nearest grid error: lat max {dlat.max():.3f}, lon max {dlon.max():.3f}")
    inside = (df.lat.between(clat.min(), clat.max())
              & df.lon.between(clon.min(), clon.max()))
    print(f"  points inside clipped domain: {int(inside.sum()):,} / {len(df):,}")
    if not inside.all():
        print("  OUTSIDE points:")
        print(df[~inside].to_string())
    ds.close()

df = df.round(4)
df.to_csv(OUT, index=False)
print(f"\nwrote {OUT}: {len(df):,} points")
