"""replicate_heatwaver.py — 用 Python 精确复刻 heatwaveR::detect_event 的 proto_event 逻辑，
在 R 与 Python 之间建立**可解释的桥梁**，从而精确定位两者的差异来源。

proto_event 的真实逻辑（读 heatwaveR 0.5.5 源码得到）：
  1. threshCriterion = (temp > thresh)
  2. 取 threshCriterion 的连续 TRUE 游程，仅保留 length >= minDuration(5) 的游程
  3. 游程之间的 FALSE 间隙长度 <= maxGap(2) 的，桥接为同一事件
  4. event = 桥接后的连续 TRUE 段 -> 这些就是最终事件；duration = 段跨度

注意第 2 步的关键含义：**间隙内的少样本天数只允许出现在 >=5 天的超标游程之间**，
而不是"任意外沿延伸"。这与 detect_thw.py 的实现并不等价。
"""
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, r"D:\2607compound\python")
from detect_events import detect_events_from_exceed  # noqa: E402

SUBSET_NC = r"D:\2607compound\results\intermediate\_smoke\eobs_small.nc"
R_SMALL = r"D:\2607compound\results\intermediate\_smoke\thw_small.csv"


def proto_event(exceed, min_duration=5, max_gap=2):
    """精确复刻 heatwaveR:::proto_event（joinAcrossGaps=TRUE）。

    返回 event 布尔数组（True 表示该日属于某个事件的跨度内）。
    """
    n = len(exceed)
    ex1 = _rle(exceed)
    # 步骤 2: 只保留长度 >= minDuration 的 TRUE 游程
    dur_crit = np.zeros(n, dtype=bool)
    pos = 0
    for val, length in zip(ex1["values"], ex1["lengths"]):
        if val and length >= min_duration:
            dur_crit[pos:pos + length] = True
        pos += length

    # 步骤 3: 桥接 <= maxGap 的 FALSE 间隙（仅限第一个合格游程之后的间隙）
    first = int(np.argmax(dur_crit)) if dur_crit.any() else None
    event = dur_crit.copy()
    if first is not None:
        ex2 = _rle(dur_crit)
        pos = 0
        for val, length in zip(ex2["values"], ex2["lengths"]):
            if (not val) and 1 <= length <= max_gap and pos > first:
                event[pos:pos + length] = True
            pos += length
        # 对照 heatwaveR: 只保留 index_end > proto_events$index_start[1] 的间隙
        # 且仅当存在满足 1<=duration<=maxGap 的间隙时才执行桥接
        gaps_ok = [(v, l) for v, l in zip(ex2["values"], ex2["lengths"])
                   if (not v) and 1 <= l <= max_gap]
        if not gaps_ok:
            event = dur_crit.copy()
    return event


def _rle(a):
    a = np.asarray(a).astype(bool)
    if a.size == 0:
        return {"values": np.array([], bool), "lengths": np.array([], int)}
    idx = np.flatnonzero(np.diff(a.astype(np.int8)) != 0) + 1
    starts = np.concatenate(([0], idx))
    ends = np.concatenate((idx, [a.size]))
    return {"values": a[starts], "lengths": ends - starts}


def to_events(event_arr):
    """把 event 布尔数组转成 (start, end_exclusive) 列表。"""
    out = []
    pos = 0
    for val, length in zip(_rle(event_arr)["values"], _rle(event_arr)["lengths"]):
        if val:
            out.append((pos, pos + length))
        pos += length
    return out


def doy_adj(times):
    t = pd.to_datetime(times)
    return np.where((t.dayofyear > 59) & ~t.is_leap_year, t.dayofyear + 1, t.dayofyear)


def build_thresholds(arr, pct=90, half=5):
    """返回 (366, lat, lon) 的单日阈值与 11 天滑动窗口阈值。"""
    t = pd.to_datetime(arr.time.values)
    nt, nlat, nlon = arr.sizes["time"], arr.sizes["lat"], arr.sizes["lon"]
    vals = np.asarray(arr.values).reshape(nt, nlat * nlon)
    da = doy_adj(t)
    A = np.full((366, nlat * nlon), np.nan, np.float32)
    B = np.full((366, nlat * nlon), np.nan, np.float32)
    for d in range(1, 367):
        selA = da == d
        if selA.sum():
            A[d - 1] = np.nanpercentile(vals[selA], pct, axis=0)
        offs = ((d - 1 + np.arange(-half, half + 1)) % 366) + 1
        selB = np.isin(da, offs)
        if selB.sum():
            B[d - 1] = np.nanpercentile(vals[selB], pct, axis=0)
    return A.reshape(366, nlat, nlon), B.reshape(366, nlat, nlon)


def main():
    ds = xr.open_dataset(SUBSET_NC)
    t2m = ds["T2m"]
    dsp = t2m.sel(time=slice("1983-01-01", "2012-12-31"))
    A, B = build_thresholds(dsp)
    da = doy_adj(t2m.time.values)
    full = np.asarray(t2m.values)

    r = pd.read_csv(R_SMALL)
    r["event_start"] = pd.to_datetime(r.event_start)

    # ---------- 1. 单点严格校验：热浪R 输出 vs 复刻实现 ----------
    li, lo = 0, 24          # 子集本地索引
    ts = full[:, li, lo]
    th_win = B[da - 1, li, lo]
    exceed = (ts > th_win) & ~np.isnan(ts) & ~np.isnan(th_win)

    ev_rep = to_events(proto_event(exceed, 5, 2))
    r_pt = r[(r.lat_idx == 36) & (r.lon_idx == 178)]     # 全局索引对应点
    r_pt = r_pt.sort_values("event_start")
    dates = pd.to_datetime(t2m.time.values)

    print("=== 单点校验: 复刻 heatwaveR proto_event vs R 实际输出 ===")
    print(f"  复刻实现事件数: {len(ev_rep)}   R 实际: {len(r_pt)}")
    if len(r_pt) > 0:
        rep_starts = [str(dates[s].date()) for s, e in ev_rep]
        print(f"  起始日完全一致: {sum(a == str(b.date()) for a, b in zip(rep_starts, r_pt.event_start))}"
              f" / {len(r_pt)}")
        print("  复刻前 5:", rep_starts[:5])
        print("  R   前 5:", [str(d.date()) for d in r_pt.event_start.head(5)])

    # ---------- 2. 全子集: 四种组合的事件数 ----------
    pts = list(map(tuple, r[["lat_idx", "lon_idx"]].drop_duplicates().values))
    lat_g, lon_g = ds.lat.values, ds.lon.values
    glob = xr.open_dataset(r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc")
    GLAT, GLON = glob.lat.values, glob.lon.values
    glob.close()

    print("\n=== 全子集事件数（同一批格点）===")
    counts = {}
    for label, th, detect in (
        ("Python 现行(单日阈值 + detect_thw 逻辑)", A, "py"),
        ("单日阈值 + heatwaveR proto_event 逻辑", A, "hw"),
        ("11天窗口阈值 + heatwaveR proto_event 逻辑", B, "hw"),
        ("11天窗口阈值 + detect_thw 逻辑", B, "py"),
    ):
        tot = 0
        for (gli, glo) in pts:
            i = int(np.argmin(np.abs(lat_g - GLAT[gli])))
            j = int(np.argmin(np.abs(lon_g - GLON[glo])))
            if abs(lat_g[i] - GLAT[gli]) > 1e-6 or abs(lon_g[j] - GLON[glo]) > 1e-6:
                continue
            s = full[:, i, j]
            thr = th[da - 1, i, j]
            ex = (s > thr) & ~np.isnan(s) & ~np.isnan(thr)
            if detect == "py":
                tot += len(detect_events_from_exceed(ex, 5, 2))
            else:
                tot += len(to_events(proto_event(ex, 5, 2)))
        counts[label] = tot
        print(f"  {label:46s}: {tot:>8,}")
    print(f"  {'R heatwaveR 实际输出':46s}: {len(r):>8,}")
    print(f"  {'Python 实际输出':46s}: {582308:>8,}")


if __name__ == "__main__":
    main()
