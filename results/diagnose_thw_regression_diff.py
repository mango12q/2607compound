"""diagnose_thw_regression_diff.py — 回归不一致时定位差异性质。

判定逻辑：
  A) 若 v2 与基准在**共同格点上的逐点事件数完全一致**，且差异只表现为
     "基准缺失了若干完整格点"，再看这些缺失点是否落满完整的检测块
     （~144 点、60x12 带内）—— 是则说明基准当年被 return-in-tryCatch
     bug 清空了块（v2 更正确），而不是检测逻辑有差异。
  B) 若共同格点上事件数也有差异 —— 检测逻辑真的不同，停下来查。

用法: python diagnose_thw_regression_diff.py
"""
import os
import sys

import numpy as np
import pandas as pd

BASE = r"D:\2607compound\results\intermediate\thw_events_R.csv"
NEW = r"D:\2607compound\results\intermediate\thw_events_R_v2.csv"
LON_BAND, LAT_BAND = 60, 12   # 与检测器分块参数一致


def per_point(df):
    g = df.groupby(["lat_idx", "lon_idx"]).agg(
        n_events=("event_no", "size"), n_days=("duration", "sum"))
    return g


def main():
    b = pd.read_csv(BASE, usecols=["event_no", "duration", "lat_idx", "lon_idx"])
    v = pd.read_csv(NEW, usecols=["event_no", "duration", "lat_idx", "lon_idx"])
    print(f"baseline: {len(b):,} events / {b.groupby(['lat_idx','lon_idx']).ngroups:,} pts")
    print(f"v2      : {len(v):,} events / {v.groupby(['lat_idx','lon_idx']).ngroups:,} pts")

    pb, pv = per_point(b), per_point(v)
    common = pb.index.intersection(pv.index)
    only_b = pb.index.difference(pv.index)
    only_v = pv.index.difference(pb.index)
    print(f"\ncommon points: {len(common):,}")
    print(f"only in baseline: {len(only_b):,}")
    print(f"only in v2      : {len(only_v):,}")

    ok = True
    if len(common):
        diff_n = (pb.loc[common, "n_events"] != pv.loc[common, "n_events"]).sum()
        diff_d = (pb.loc[common, "n_days"] != pv.loc[common, "n_days"]).sum()
        print(f"common points with different event counts: {diff_n:,}")
        print(f"common points with different day sums    : {diff_d:,}")
        ok &= diff_n == 0 and diff_d == 0

    # 缺失点是否构成完整检测块（nuked-chunk 签名）
    def chunk_ids(idx):
        li = np.array([i[0] for i in idx])   # lat_idx (0-based)
        lo = np.array([i[1] for i in idx])   # lon_idx
        # R 侧 cand 列是 (lon 1-based, lat 1-based); band = floor((idx)/band)
        return pd.Series(
            [f"{a}_{s}" for a, s in zip(lo // LON_BAND, li // LAT_BAND)],
            index=idx)

    for name, idx in (("only-in-baseline", only_b), ("only-in-v2", only_v)):
        if len(idx) == 0:
            continue
        cid = chunk_ids(idx)
        sizes = cid.value_counts()
        full = sizes[sizes >= 100]   # 一个完整块约 144 点
        print(f"\n{name}: {len(idx):,} pts across {len(sizes)} chunk-bands; "
              f"bands with >=100 pts: {len(full)}")
        print(sizes.head(10).to_string())
    print("\nVERDICT:", "A) baseline lost chunks / v2 superset -> v2 authoritative"
          if (ok and len(only_b) == 0 and len(only_v) > 0)
          else ("IDENTICAL" if ok and len(only_b) == 0 and len(only_v) == 0
                else "B) real per-point differences -> STOP and investigate"))
    sys.exit(0)


if __name__ == "__main__":
    main()
