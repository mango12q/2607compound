"""inspect_oisst.py — 摸清 OISST 文件结构与现有 MHW 检测的口径。"""
import os
import sys

import numpy as np
import xarray as xr

sys.path.insert(0, r"D:\2607compound\python")

OISST = r"E:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc"

print("=" * 74)
print("A. OISST 文件结构")
print("=" * 74)
ds = xr.open_dataset(OISST)
print(ds)
print()
v = list(ds.data_vars)[0]
print(f"  主变量: {v}   dims={ds[v].dims}  dtype={ds[v].dtype}")
print(f"  sizes: {dict(ds.sizes)}")
for c in list(ds.coords):
    cv = ds[c].values
    if cv.ndim == 1 and cv.size > 1:
        print(f"  coord {c}: n={cv.size}  {cv[0]} .. {cv[-1]}  step={cv[1]-cv[0]:.4f}")
print(f"  attrs: {dict(ds[v].attrs)}")
print(f"  time: {str(ds.time.values[0])[:10]} .. {str(ds.time.values[-1])[:10]} "
      f"n={ds.time.size}")
ds.close()

print("\n" + "=" * 74)
print("B. 现有 MHW 检测的口径（detect_mhw.py）")
print("=" * 74)
import detect_mhw  # noqa: E402
import inspect
src = inspect.getsource(detect_mhw)
for kw in ["ocean_mask", "isel(time=0)", "clim", "dayofyear", "quantile",
           "OISST", "lat_vals", "lon_vals"]:
    hits = [i + 1 for i, l in enumerate(src.splitlines()) if kw in l]
    print(f"  '{kw:14s}' 出现于行 {hits[:8]}")

print("\n" + "=" * 74)
print("C. 现有 MHW 结果与海洋格点掩码")
print("=" * 74)
import pandas as pd  # noqa: E402
from config import INTERMEDIATE_DIR  # noqa: E402
mhw = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "mhw_events.csv"))
print(f"  mhw_events.csv: {len(mhw):,} events")
print(f"  columns: {list(mhw.columns)}")
print(f"  lat_idx {mhw.lat_idx.min()}..{mhw.lat_idx.max()}  "
      f"lon_idx {mhw.lon_idx.min()}..{mhw.lon_idx.max()}")
print(f"  lat {mhw.lat.min():.2f}..{mhw.lat.max():.2f}  "
      f"lon {mhw.lon.min():.2f}..{mhw.lon.max():.2f}")
print(f"  points: {mhw.groupby(['lat_idx','lon_idx']).ngroups:,}")
pairs = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "coastal_pairs.csv"))
print(f"\n  coastal_pairs ocean 格点索引范围:")
print(f"    ocean_lat_idx {pairs.ocean_lat_idx.min()}..{pairs.ocean_lat_idx.max()}")
print(f"    ocean_lon_idx {pairs.ocean_lon_idx.min()}..{pairs.ocean_lon_idx.max()}")
print(f"    ocean_lat {pairs.ocean_lat.min():.2f}..{pairs.ocean_lat.max():.2f}")
print(f"    ocean_lon {pairs.ocean_lon.min():.2f}..{pairs.ocean_lon.max():.2f}")
