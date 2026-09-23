# -*- coding: utf-8 -*-
"""Lead 独立复核 第二部分：T2m 阈值 bug 的影响量化 + _run_events 判别用例。只读。"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

BASE = r"D:\2607compound"
CESM_INT = os.path.join(BASE, "results", "intermediate", "cesm")
sys.path.insert(0, os.path.join(BASE, "python"))
from phase6_cesm import _run_events  # noqa: E402


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# --------------------------------------------------------------------------
hr("【L5】_run_events 桥接/过滤顺序（合成判别用例）")
cases = {
    "3超+2空+3超 (跨度8)": [1, 1, 1, 0, 0, 1, 1, 1],
    "1超+2空+4超 (跨度7)": [1, 0, 0, 1, 1, 1, 1],
    "2超+2空+2超 (跨度6)": [1, 1, 0, 0, 1, 1],
    "1超+1空+3超 (跨度5)": [1, 0, 1, 1, 1],
    "4超+3空+4超 (间隙>2)": [1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1],
    "5超 单段": [1, 1, 1, 1, 1],
    "4超 单段(<5)": [1, 1, 1, 1],
    "1超+2空+1超 (跨度4)": [1, 0, 0, 1],
}
for k, v in cases.items():
    ev = _run_events(np.array(v, dtype=np.int8), None)
    print(f"  {k:24s} -> {str(ev):30s} 事件数={len(ev)}")
print("  判读：原代码=先桥接原始游程再按总跨度>=5 过滤 ⇒ 前两例各算 1 个事件。")

# --------------------------------------------------------------------------
hr("【L6】T2m 阈值 bug 的影响量化：成员 001 的 THW 事件/超标天数")
pairs = pd.read_csv(os.path.join(CESM_INT, "coastal_pairs_cesm.csv"))
pj = pairs.land_lat_idx.values
pi = pairs.land_lon_idx.values


def load_mat(exp, ms):
    out = []
    for m in ms:
        ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
        da = ds["T2m"].isel(lat=xr.DataArray(pj, dims="p"), lon=xr.DataArray(pi, dims="p"))
        out.append((da.transpose("time", "p").values.astype(np.float64),
                    pd.DatetimeIndex(da.time.values)))
        ds.close()
    return out


ms3 = ("001", "002", "003")
xghg = load_mat("XGHG", ms3)
doy_all = np.concatenate([t.dayofyear.values for _, t in xghg])
mat = np.concatenate([v for v, _ in xghg], axis=0)
mat_by_doy = {d: mat[doy_all == d] for d in np.arange(1, 366)}

thrB = np.full((366, mat.shape[1]), np.nan)
for d in np.arange(1, 366):
    win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
    thrB[d - 1] = np.nanpercentile(
        np.concatenate([mat_by_doy[w] for w in win], axis=0), 90, axis=0)

z = np.load(os.path.join(CESM_INT, "thresh_t2m_xghg.npz"))
thr_bug = z["thresh"]

all1 = load_mat("ALL", ("001",))[0]
arr, time = all1
doy = time.dayofyear.values
nt = arr.shape[0]

print(f"成员 ALL 001: {nt} 天 × {arr.shape[1]} 陆点, "
      f"日期 {time[0].date()} ~ {time[-1].date()}")

for name, thr in (("现状(bug, 全域单条)", thr_bug), ("修正(窗内合并,逐点)", thrB)):
    n_ev, n_day = 0, 0
    for p in range(arr.shape[1]):
        x = arr[:, p] > thr[doy - 1, p]
        x[np.isnan(arr[:, p])] = False
        for a, b in _run_events(x, time):
            n_ev += 1
            n_day += b - a + 1
    print(f"  {name:24s} THW 事件={n_ev:6d}  超阈天数={n_day:7d}  "
          f"(点均 {n_day/arr.shape[1]:.1f} 天/{nt/365:.0f}年)")

# 现存 v2 事件表对照（同口径但用 bug 阈值跑出来的）
for tag, f in (("XGHG 001", "thw_x_XGHG_001.csv"), ("ALL 001", "thw_x_ALL_001.csv")):
    d = pd.read_csv(os.path.join(CESM_INT, f))
    print(f"  已落盘 {tag:9s} ({f}): 事件={len(d)}  时长和={int(d.duration.sum())}")

# --------------------------------------------------------------------------
hr("【L7】同上，但用 XGHG 成员自检（in-sample 池 + bug 阈值）")
for m in ms3:
    seg = load_mat("XGHG", (m,))[0]
    a2, t2 = seg
    d2 = t2.dayofyear.values
    out = []
    for name, thr in (("bug", thr_bug), ("fixed", thrB)):
        n_ev = n_day = 0
        for p in range(a2.shape[1]):
            x = a2[:, p] > thr[d2 - 1, p]
            x[np.isnan(a2[:, p])] = False
            for aa, bb in _run_events(x, t2):
                n_ev += 1
                n_day += bb - aa + 1
        out.append((n_ev, n_day))
    print(f"  XGHG {m}: bug 事件={out[0][0]:6d} 天数={out[0][1]:7d} | "
          f"fixed 事件={out[1][0]:6d} 天数={out[1][1]:7d} | "
          f"倍数={out[1][1]/max(out[0][1],1):5.2f}x")
