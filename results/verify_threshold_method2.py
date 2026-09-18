"""verify_threshold_method2.py — 在子集上隔离阈值算法，解释 R/Python 差异。

在**同一批格点、同一套事件检测逻辑**下只替换阈值：
  A) Python 现行: 逐 dayofyear 的 30 年单日 90th 分位数（无窗口）
  B) heatwaveR  : 11 天滑动窗口内的 330 个样本 90th 分位数
并统计"超阈值日数"，直接解释为何 R 的事件/HW 日更少。
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, r"D:\2607compound\python")
from detect_events import detect_events_from_exceed  # noqa: E402

SUBSET_NC = r"D:\2607compound\results\intermediate\_smoke\eobs_small.nc"
R_CSV = r"D:\2607compound\results\intermediate\_smoke\thw_small.csv"
PY_CSV = r"D:\2607compound\results\intermediate\thw_events.csv.bak"
OUT = r"D:\2607compound\results\tables"
os.makedirs(OUT, exist_ok=True)

CLIM_YEARS = (1983, 2012)
MIN_DUR, MAX_GAP, PCT = 5, 2, 90

# 全局 E-OBS 网格坐标（用于把全局索引翻译成子集本地索引）
_g = xr.open_dataset(r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc")
GLOBAL_LAT = _g.lat.values
GLOBAL_LON = _g.lon.values
_g.close()


def build_thresholds(arr, pct=PCT, half=5):
    """返回 (366, lat, lon) 的两套阈值：单日 DOY 与 11 天滑动窗口。

    闰年处理：统一映射到"含 2/29 的 366 日历"，平年 3/1 之后 +1，
    与 heatwaveR 内部 doy 约定一致。
    """
    time = pd.to_datetime(arr.time.values)
    nt, nlat, nlon = arr.sizes["time"], arr.sizes["lat"], arr.sizes["lon"]
    vals = np.asarray(arr.values).reshape(nt, nlat * nlon)

    doy = time.dayofyear
    leap = time.is_leap_year
    doy_adj = np.where((doy > 59) & ~leap, doy + 1, doy)   # 1..366

    # A) 单日
    A = np.full((366, nlat * nlon), np.nan, dtype=np.float32)
    for d in range(1, 367):
        sel = doy_adj == d
        if sel.sum() == 0:
            continue
        A[d - 1] = np.nanpercentile(vals[sel], pct, axis=0)

    # B) 11 天滑动窗口（环形）
    B = np.full((366, nlat * nlon), np.nan, dtype=np.float32)
    for d in range(1, 367):
        offs = ((d - 1 + np.arange(-half, half + 1)) % 366) + 1
        sel = np.isin(doy_adj, offs)
        if sel.sum() == 0:
            continue
        B[d - 1] = np.nanpercentile(vals[sel], pct, axis=0)

    return A.reshape(366, nlat, nlon), B.reshape(366, nlat, nlon), doy_adj


def run(ds, thresh, points, label, return_exceed=False):
    """points 为全局 (lat_idx, lon_idx)；本函数内部换算成 ds 的局部索引。"""
    lat_g = ds.lat.values
    lon_g = ds.lon.values
    t2m = ds["T2m"].values
    doy = ds["time"].dt.dayofyear.values
    leap = ds["time"].dt.is_leap_year.values
    doy_adj = np.where((doy > 59) & ~leap, doy + 1, doy)
    rows, nex = [], 0
    for (gli, glo) in points:
        li = int(np.argmin(np.abs(lat_g - GLOBAL_LAT[gli])))
        lo = int(np.argmin(np.abs(lon_g - GLOBAL_LON[glo])))
        if abs(lat_g[li] - GLOBAL_LAT[gli]) > 1e-6 or abs(lon_g[lo] - GLOBAL_LON[glo]) > 1e-6:
            continue
        ts = t2m[:, li, lo]
        if np.isnan(ts).sum() > len(ts) - 730:
            continue
        th = thresh[doy_adj - 1, li, lo]
        with np.errstate(invalid="ignore"):
            exceed = (ts > th) & ~np.isnan(ts) & ~np.isnan(th)
        nex += int(exceed.sum())
        for s, e in detect_events_from_exceed(exceed, MIN_DUR, MAX_GAP):
            rows.append((gli, glo, s, e, e - s))
    df = pd.DataFrame(rows, columns=["lat_idx", "lon_idx", "i0", "i1", "duration"])
    print(f"  {label:36s}: {len(df):>8,} events, total dur {int(df.duration.sum()) if len(df) else 0:>9,}, "
          f"exceed days {nex:>9,}")
    return (df, nex) if return_exceed else df


def main():
    r = pd.read_csv(R_CSV)
    py_all = pd.read_csv(PY_CSV)
    pts = list(map(tuple, r[["lat_idx", "lon_idx"]].drop_duplicates().values))

    ds = xr.open_dataset(SUBSET_NC)[["T2m"]]
    sub_pts = set(pts)
    py = py_all[py_all[["lat_idx", "lon_idx"]].apply(tuple, axis=1).isin(sub_pts)]
    print(f"Subset: {len(pts):,} points, R {len(r):,} events, Py {len(py):,} events")

    dsp = ds.sel(time=slice(f"{CLIM_YEARS[0]}-01-01", f"{CLIM_YEARS[1]}-12-31"))
    print(f"Clim window: {dsp.time.size:,} days")
    A, B, _ = build_thresholds(dsp["T2m"])
    diff = B - A
    print(f"\n阈值 B(滑动窗口) - A(单日): mean {np.nanmean(diff):+.3f} degC, "
          f"median {np.nanmedian(diff):+.3f}, std {np.nanstd(diff):.3f}")
    print(f"  B < A 的比例: {100*np.nanmean(diff < 0):.1f}%")

    print("\n=== 相同格点、相同事件逻辑，只换阈值 ===")
    a, ex_a = run(ds, A, pts, "A) Python 单日 DOY", True)
    b, ex_b = run(ds, B, pts, "B) heatwaveR 11 天窗口", True)
    print(f"  {'R) heatwaveR 实际输出':36s}: {len(r):>8,} events, "
          f"total dur {int(r.duration.sum()):>9,}")
    print(f"  {'Python 实际输出(同格点)':34s}: {len(py):>8,} events, "
          f"total dur {int(py.duration.sum()):>9,}")
    print(f"\n  超阈值日数 A/B = {ex_a/ex_b:.3f}")

    for name, df in (("A_singleday", a), ("B_sliding", b)):
        df["year"] = pd.to_datetime(ds.time.values)[df.i0.values].year
    ra = a.groupby("year").size().rename("A_singleday")
    rb = b.groupby("year").size().rename("B_sliding")
    rr = r.assign(year=pd.to_datetime(r.event_start).dt.year).groupby("year").size().rename("R_heatwaveR")
    rp = py.assign(year=pd.to_datetime(py.event_start).dt.year).groupby("year").size().rename("Py_actual")
    ann = pd.concat([ra, rb, rr, rp], axis=1).fillna(0).astype(int)
    print("\n=== 年度事件数 ===")
    print(ann.to_string())

    def corr(x, y):
        return float(np.corrcoef(x, y)[0, 1])
    print(f"\ncorr(B_sliding, R_actual)  = {corr(ann.B_sliding, ann.R_heatwaveR):.4f}")
    print(f"corr(B_sliding, Py_actual) = {corr(ann.B_sliding, ann.Py_actual):.4f}")
    print(f"corr(A_singleday, Py_actual) = {corr(ann.A_singleday, ann.Py_actual):.4f}")
    print(f"corr(R_actual, Py_actual)  = {corr(ann.R_heatwaveR, ann.Py_actual):.4f}")

    a.to_csv(os.path.join(OUT, "thw_py_singleday_subset.csv"), index=False)
    b.to_csv(os.path.join(OUT, "thw_py_slidingwindow_subset.csv"), index=False)
    ann.to_csv(os.path.join(OUT, "thw_threshold_method_annual.csv"))
    print(f"\nSaved to {OUT}")


if __name__ == "__main__":
    main()
