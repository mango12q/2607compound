"""compare_thw_regression.py — detect_events.R(land) vs detect_thw.R 回归对比。

基准: results/intermediate/thw_events_R.csv      (detect_thw.R, 1,635,196 事件)
新版: results/intermediate/thw_events_R_v2.csv   (detect_events.R, 统一检测器)

★ 2025-09-18 注：字符串级比较会因两版脚本的可选序列化习惯不同而误报
  （旧版 event_start 为 Date 直写不带引号、duration 为 double "5.0"；
  新版 as.character 带引号、duration 为 integer "5"）。
  因此本版比较的是**解析后的值**：日期 -> datetime64，duration/强度 -> float64，
  索引 -> int。值完全一致即为回归通过。

用法: python compare_thw_regression.py
"""
import os
import sys
import time

import numpy as np
import pandas as pd

BASE = r"D:\2607compound\results\intermediate\thw_events_R.csv"
NEW = r"D:\2607compound\results\intermediate\thw_events_R_v2.csv"
KEY = ["lat_idx", "lon_idx", "event_start", "event_end", "duration",
       "intensity_mean", "intensity_max"]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_typed(path):
    df = pd.read_csv(path)
    df["event_start"] = pd.to_datetime(df.event_start)
    df["event_end"] = pd.to_datetime(df.event_end)
    for c in ("duration", "intensity_mean", "intensity_max"):
        df[c] = df[c].astype("float64")
    for c in ("event_no", "lat_idx", "lon_idx"):
        df[c] = df[c].astype("int64")
    return df


def main():
    for p in (BASE, NEW):
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        log(f"{os.path.basename(p)}: {os.path.getsize(p)/1e6:.1f} MB")

    b = load_typed(BASE)
    v = load_typed(NEW)
    log(f"baseline rows: {len(b):,}   new rows: {len(v):,}")
    ok = len(b) == len(v)

    log("sorting by key for value comparison...")
    b = b.sort_values(KEY).reset_index(drop=True)
    v = v.sort_values(KEY).reset_index(drop=True)

    for c in KEY:
        if len(b) != len(v):
            break
        same = b[c].equals(v[c]) if b[c].dtype.kind in "iM" else \
            np.array_equal(b[c].values, v[c].values, equal_nan=True)
        if not same:
            ndiff = int((b[c].values != v[c].values).sum()) \
                if b[c].dtype.kind not in "M" else \
                int((b[c].values != v[c].values).sum())
            log(f"FAIL column {c}: {ndiff:,} differing rows")
            bad = np.where(b[c].values != v[c].values)[0][:3]
            for i in bad:
                log(f"  row {i}: base={b[c].iloc[i]!r} new={v[c].iloc[i]!r}")
            ok = False
        else:
            log(f"column {c}: identical")

    # 附加统计（帮助确认量级）
    log(f"mean duration: base {b.duration.mean():.4f} vs new {v.duration.mean():.4f}")
    log(f"points: base {b.groupby(['lat_idx','lon_idx']).ngroups:,} "
        f"vs new {v.groupby(['lat_idx','lon_idx']).ngroups:,}")

    log("=" * 60)
    log(f"REGRESSION {'PASS' if ok else 'FAIL'}")
    log("=" * 60)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
