"""用旧 raw+trim 与 新 gdex 两个 SST 来源，各自重建海岸配对，比对是否一致。

目的：新 gdex 件的 KMT 被 `_mask_sst_box` 一起掩膜成 NaN（框外），旧件 KMT 是全球全值。
      KMT>0 的"湿格点"数量因此从 86 212 掉到 4 263。要确认这**不改变** 206 对配对结果。
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import binary_erosion, generate_binary_structure
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
import config as C

ATM = os.path.join(C.CESM_PROC_DIR, "TREFHT_all_001_2000-2021_europe.nc")
SST_OLD = os.path.join(
    C.CESM_PROC_DIR,
    "b.e11.B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.SST.18500102-20051231_2000-2021.nc")
SST_NEW = os.path.join(C.CESM_PROC_DIR, "sst_all_001_2000-2021.nc")
CACHED = os.path.join(C.INTERMEDIATE_DIR, "cesm", "coastal_pairs_cesm.csv")


def build(sst_f):
    ref = xr.open_dataset(ATM)
    atm_lat = ref.lat.values.astype(float)
    atm_lon = ref.lon.values.astype(float)
    ref.close()
    ds = xr.open_dataset(sst_f)
    kmt = ds["KMT"].values
    tlat = ds["TLAT"].values.astype(float)
    tlon = ds["TLONG"].values.astype(float)
    ds.close()

    wet_rows, wet_cols = np.where(kmt > 0)
    dlat = float(np.abs(np.diff(atm_lat).mean()))
    dlon = float(np.abs(np.diff(atm_lon).mean()))
    tlon180 = np.where(tlon > 180, tlon - 360, tlon)
    wlat = tlat[wet_rows, wet_cols]
    wlon = tlon180[wet_rows, wet_cols]
    ii = np.abs(wlat[:, None] - atm_lat[None, :]).argmin(axis=1)
    jj = np.abs(wlon[:, None] - atm_lon[None, :]).argmin(axis=1)
    ok = (np.abs(wlat - atm_lat[ii]) <= 0.75 * dlat) & (np.abs(wlon - atm_lon[jj]) <= 0.75 * dlon)
    land_mask = np.ones((len(atm_lat), len(atm_lon)), dtype=np.int8)
    land_mask[ii[ok], jj[ok]] = 0
    eroded = binary_erosion(land_mask, structure=generate_binary_structure(2, 1))
    edge_idx = np.argwhere((land_mask == 1) & (~eroded))
    cos_w = np.cos(np.deg2rad(wlat))
    tree = cKDTree(np.column_stack([wlat, wlon * cos_w]))
    rows = []
    for i, j in edge_idx:
        lat0, lon0 = float(atm_lat[i]), float(atm_lon[j])
        q = np.array([[lat0, lon0 * np.cos(np.deg2rad(lat0))]])
        dist, pos = tree.query(q, k=1)
        if dist[0] > C.MAX_PAIR_DIST_DEG:
            continue
        orow, ocol = wet_rows[pos[0]], wet_cols[pos[0]]
        rows.append((int(i), int(j), int(orow), int(ocol), lat0, lon0,
                     float(tlat[orow, ocol]), float(tlon180[orow, ocol]), float(dist[0])))
    df = pd.DataFrame(rows, columns=["land_lat_idx", "land_lon_idx", "ocean_lat_idx",
                                     "ocean_lon_idx", "land_lat", "land_lon",
                                     "ocean_lat", "ocean_lon", "dist_deg"])
    return df, len(wet_rows), int((land_mask == 0).sum()), len(edge_idx)


out = {}
for tag, f in (("old", SST_OLD), ("new", SST_NEW)):
    df, nwet, nocean, nedge = build(f)
    out[tag] = df
    print(f"[{tag}] {os.path.basename(f)[:46]:46s} 湿点 {nwet:6d} f09海格 {nocean:4d} 边缘 {nedge:4d} → 配对 {len(df)}")

cached = pd.read_csv(CACHED)
print(f"\n[cached] {os.path.basename(CACHED)} → 配对 {len(cached)}")


def cmp(a, b, name):
    if len(a) != len(b):
        print(f"  {name}: 行数不同 {len(a)} vs {len(b)}")
        return
    ka = a[["land_lat_idx", "land_lon_idx"]].values
    kb = b[["land_lat_idx", "land_lon_idx"]].values
    same_land = bool((ka == kb).all())
    ka2 = a[["ocean_lat_idx", "ocean_lon_idx"]].values
    kb2 = b[["ocean_lat_idx", "ocean_lon_idx"]].values
    same_ocean = bool((ka2 == kb2).all())
    print(f"  {name}: 行数相同 {len(a)}；陆索引相同 {same_land}；海索引相同 {same_ocean}"
          + ("" if same_ocean else f"；不同 {int((ka2 != kb2).any(axis=1).sum())} 行"))


print("\n=== 比对 ===")
cmp(out["old"], out["new"], "old vs new")
cmp(cached, out["new"], "cached vs new")
cmp(cached, out["old"], "cached vs old")
