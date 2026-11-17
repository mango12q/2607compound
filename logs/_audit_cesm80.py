"""体检 80 个 CESM 切片产物：时间轴 / 网格 / 有限点图样 / 206 个海岸配对点是否全在。

目的：确认「2000-2021 + 欧洲框 + 海洋 9.2% 子网格」这套切片对 Phase 6 是充分的。
判据：
  1. 每个文件 time 覆盖 2000-01-01..2021-12-31（all 海洋 8029 天、其余 8030）；
  2. atm 网格 (time,49,51) 且 lat/lon 单调、落在 CESM_EUROPE_LAT/LON 内；
     ocn 网格 (time,384,320)，有限点只在 slab 内，slab 外全 NaN；
  3. 206 个海岸配对点（陆 + 海）在**每个文件的第 0 天**都有限；
  4. 不同年份之间有限点图样不变（抽 day 0 / day 3650 比掩膜）。
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
import config as C

PROC = C.CESM_PROC_DIR
PAIRS = os.path.join(C.INTERMEDIATE_DIR, "cesm", "coastal_pairs_cesm.csv")

pairs = pd.read_csv(PAIRS)
oc = pairs[["ocean_lat_idx", "ocean_lon_idx"]].values
ld = pairs[["land_lat_idx", "land_lon_idx"]].values
print(f"配对: {len(pairs)} 对；海点索引 lat {oc[:,0].min()}..{oc[:,0].max()} lon {oc[:,1].min()}..{oc[:,1].max()}")
print(f"      陆点索引 lat {ld[:,0].min()}..{ld[:,0].max()} lon {ld[:,1].min()}..{ld[:,1].max()}")

bad = []
files = sorted(glob.glob(os.path.join(PROC, "*_2000-2021.nc")))
files = [f for f in files if os.path.basename(f).startswith(("trefht_", "sst_"))]
print(f"待检文件: {len(files)}\n")

for fp in files:
    name = os.path.basename(fp)
    var = "TREFHT" if name.startswith("trefht_") else "SST"
    ds = xr.open_dataset(fp)
    nt = ds.sizes["time"]
    t0, t1 = str(ds.time.values[0])[:10], str(ds.time.values[-1])[:10]
    a = ds[var]
    d0 = np.asarray(a.isel(time=0).values)
    fin0 = np.isfinite(d0)
    # 时间轴连续性：noleap 日历缺 2 月 29 日 ⇒ 闰年 2/28→3/1 的 Δ=2 是**正常**的
    tt = pd.to_datetime(ds.time.values)
    dd = np.diff(tt.values.astype("datetime64[D]").astype(int))
    leap_ok = (dd == 2) & (pd.Series(tt[:-1]).dt.strftime("%m-%d").values == "02-28") \
        & (pd.Series(tt[1:]).dt.strftime("%m-%d").values == "03-01") \
        & pd.Series(tt[:-1]).dt.is_leap_year.values
    # 已知源数据缺口：B20TRC5CNBDRD 海洋段 1 止于 2006-01-01、段 2 首日 2006-01-03（论文数据本身）
    src_gap = (dd == 2) & (pd.Series(tt[:-1]).dt.strftime("%Y-%m-%d").values == "2006-01-01") \
        & (pd.Series(tt[1:]).dt.strftime("%Y-%m-%d").values == "2006-01-03") \
        & np.array(["_all_" in os.path.basename(fp)] * len(dd))
    gaps = int(((dd != 1) & ~leap_ok & ~src_gap).sum())
    nsrc = int(src_gap.sum())
    nleap = int(leap_ok.sum())
    if var == "TREFHT":
        lat, lon = a["lat"].values, a["lon"].values
        ok_shape = a.shape[1:] == (49, 51)
        ok_geo = (lat.min() >= C.CESM_EUROPE_LAT[0] - 1e-6 and lat.max() <= C.CESM_EUROPE_LAT[1] + 1e-6
                  and lon.min() >= C.CESM_EUROPE_LON[0] - 1e-6 and lon.max() <= C.CESM_EUROPE_LON[1] + 1e-6)
        pr_fin = int(np.isfinite(d0[ld[:, 0], ld[:, 1]]).sum())
        extra = f"lat {lat.min():.2f}..{lat.max():.2f} lon {lon.min():.2f}..{lon.max():.2f}"
        ok_grid = ok_shape and ok_geo
    else:
        ok_shape = a.shape[1:] == (384, 320)
        slab = np.zeros(a.shape[1:], bool)
        slab[266:384, 11:107] = True
        outside = int((fin0 & ~slab).sum())
        empty = int((~fin0 & slab).sum())
        pr_fin = int(np.isfinite(d0[oc[:, 0], oc[:, 1]]).sum())
        d3 = np.asarray(a.isel(time=min(3650, nt - 1)).values)
        same = bool((np.isfinite(d3) == fin0).all())
        extra = f"slab内有限 {int(fin0.sum())} 外溢 {outside} 空 {empty} 图样恒定 {same}"
        ok_grid = ok_shape and outside == 0
    nfin = int(fin0.sum())
    nan_all = int(np.isnan(np.asarray(a.isel(time=slice(0, 3)).values)).sum())
    n_sample = 3 * d0.size
    flags = []
    if nt not in (8029, 8030):
        flags.append(f"time={nt}")
    if gaps:
        flags.append(f"断点={gaps}")
    if not ok_grid:
        flags.append("网格/范围不符")
    if pr_fin != len(pairs):
        flags.append(f"配对有限={pr_fin}/{len(pairs)}")
    if nan_all == n_sample:
        flags.append("全 NaN")
    if flags:
        bad.append((name, flags))
    print(f"{name:38s} n={nt:5d} {t0}..{t1} 有限/天={nfin:6d} {extra} 配对={pr_fin}/{len(pairs)} 闰日跳={nleap} 源缺日={nsrc}"
          + ("   ⚠ " + "；".join(flags) if flags else "   OK"))
    ds.close()

print("\n" + "=" * 70)
print(f"文件总数 {len(files)}；异常 {len(bad)}")
for n, f in bad:
    print("  ⚠", n, f)


