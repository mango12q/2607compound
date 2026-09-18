"""pinpoint_diff.py — 精确定位 detect_thw.py 与 heatwaveR 差异的机制。

候选机制（待检验）：
  M1 阈值算法      : 单日 DOY 分位数 vs 11 天滑动窗口      -> 已排除为主因（~4%）
  M2 minDuration 口径: detect_thw.py 用"事件跨度"(含间隙) >= 5，
                     heatwaveR 用"超标日游程"(不含间隙) >= 5
  M3 间隙桥接规则   : detect_thw.py 允许事件末尾/开头的外沿间隙，
                     heatwaveR 只桥接两个"已合格(>=5天)游程"之间的间隙
"""
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, r"D:\2607compound\python")
from detect_events import detect_events_from_exceed  # noqa: E402

SUBSET_NC = r"D:\2607compound\results\intermediate\_smoke\eobs_small.nc"
R_SMALL = r"D:\2607compound\results\intermediate\_smoke\thw_small.csv"


def _rle(a):
    a = np.asarray(a).astype(bool)
    if a.size == 0:
        return np.array([], bool), np.array([], int)
    idx = np.flatnonzero(np.diff(a.astype(np.int8)) != 0) + 1
    starts = np.concatenate(([0], idx))
    ends = np.concatenate((idx, [a.size]))
    return a[starts], ends - starts


def proto_event(exceed, min_duration=5, max_gap=2):
    """heatwaveR:::proto_event 的精确复刻。"""
    n = len(exceed)
    vals1, lens1 = _rle(exceed)
    dur_crit = np.zeros(n, bool)
    pos = 0
    for v, l in zip(vals1, lens1):
        if v and l >= min_duration:
            dur_crit[pos:pos + l] = True
        pos += l
    if not dur_crit.any():
        return dur_crit
    first = int(np.argmax(dur_crit))
    vals2, lens2 = _rle(dur_crit)
    gaps = [(p, l) for p, (v, l) in
            zip(np.cumsum(np.concatenate(([0], lens2[:-1]))), zip(vals2, lens2))
            if (not v) and 1 <= l <= max_gap and p > first]
    event = dur_crit.copy()
    if gaps:
        for p, l in gaps:
            event[p:p + l] = True
    return event


def to_events(arr):
    vals, lens = _rle(arr)
    out, pos = [], 0
    for v, l in zip(vals, lens):
        if v:
            out.append((pos, pos + l))
        pos += l
    return out


def thw_strict(exceed, min_duration=5, max_gap=2):
    """M2 检验用: 与 detect_thw.py 同结构，但 minDuration 只数"实际超标日"。

    detect_thw.py: end_idx - start_idx >= min_duration       (跨度, 含间隙)
    本实现      : n_exceed      >= min_duration               (超标日数)
    """
    events = []
    in_event = False
    start = gap = last = -1
    nex = 0
    for i, e in enumerate(exceed):
        if e:
            if not in_event:
                in_event, start, gap, nex = True, i, 0, 1
            else:
                gap, nex = 0, nex + 1
            last = i
        else:
            if in_event:
                gap += 1
                if gap > max_gap:
                    end = i - gap + 1
                    if nex >= min_duration:
                        events.append((start, end))
                    in_event = False
    if in_event and nex >= min_duration:
        events.append((start, last + 1))
    return events


def doy_adj(times):
    t = pd.to_datetime(times)
    return np.where((t.dayofyear > 59) & ~t.is_leap_year, t.dayofyear + 1, t.dayofyear)


def build_thresholds(arr, pct=90, half=5):
    t = pd.to_datetime(arr.time.values)
    nt, nlat, nlon = arr.sizes["time"], arr.sizes["lat"], arr.sizes["lon"]
    vals = np.asarray(arr.values).reshape(nt, nlat * nlon)
    da = doy_adj(t)
    A = np.full((366, nlat * nlon), np.nan, np.float32)
    B = np.full((366, nlat * nlon), np.nan, np.float32)
    with np.errstate(all="ignore"):
        for d in range(1, 367):
            sA = da == d
            if sA.sum():
                A[d - 1] = np.nanpercentile(vals[sA], pct, axis=0)
            offs = ((d - 1 + np.arange(-half, half + 1)) % 366) + 1
            sB = np.isin(da, offs)
            if sB.sum():
                B[d - 1] = np.nanpercentile(vals[sB], pct, axis=0)
    return A.reshape(366, nlat, nlon), B.reshape(366, nlat, nlon)


def main():
    ds = xr.open_dataset(SUBSET_NC)
    t2m = ds["T2m"]
    A, B = build_thresholds(t2m.sel(time=slice("1983-01-01", "2012-12-31")))
    da = doy_adj(t2m.time.values)
    full = np.asarray(t2m.values)

    r = pd.read_csv(R_SMALL)
    pts = list(map(tuple, r[["lat_idx", "lon_idx"]].drop_duplicates().values))
    lat_g, lon_g = ds.lat.values, ds.lon.values
    g = xr.open_dataset(r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc")
    GLAT, GLON = g.lat.values, g.lon.values
    g.close()

    def run(th, fn):
        tot = 0
        for gli, glo in pts:
            i = int(np.argmin(np.abs(lat_g - GLAT[gli])))
            j = int(np.argmin(np.abs(lon_g - GLON[glo])))
            if abs(lat_g[i] - GLAT[gli]) > 1e-6 or abs(lon_g[j] - GLON[glo]) > 1e-6:
                continue
            s = full[:, i, j]
            thr = th[da - 1, i, j]
            ex = (s > thr) & ~np.isnan(s) & ~np.isnan(thr)
            tot += len(fn(ex))
        return tot

    print("=== 消融实验: 阈值 x 最小持续时间的计数口径 (同一批 3922 格点) ===")
    rows = [
        ("单日DOY 阈值", "跨度>=5 (detect_thw.py)", A, lambda e: detect_events_from_exceed(e, 5, 2)),
        ("单日DOY 阈值", "超标日>=5 (heatwaveR proto_event)", A, lambda e: to_events(proto_event(e, 5, 2))),
        ("单日DOY 阈值", "超标日>=5 (等价游程实现)", A, lambda e: thw_strict(e, 5, 2)),
        ("11天窗口 阈值", "跨度>=5 (detect_thw.py)", B, lambda e: detect_events_from_exceed(e, 5, 2)),
        ("11天窗口 阈值", "超标日>=5 (heatwaveR proto_event)", B, lambda e: to_events(proto_event(e, 5, 2))),
        ("11天窗口 阈值", "超标日>=5 (等价游程实现)", B, lambda e: thw_strict(e, 5, 2)),
    ]
    ref = {"R heatwaveR 实际": 292364, "Python 实际": 582308}
    for thname, mname, th, fn in rows:
        n = run(th, fn)
        print(f"  {thname:12s} x {mname:36s}: {n:>8,}")
    print()
    for k, v in ref.items():
        print(f"  {k:52s}: {v:>8,}")


if __name__ == "__main__":
    main()
