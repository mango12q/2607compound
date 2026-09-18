"""chr_robustness.py — 检测方法对 CHR（图2 的核心量）的影响。

CHR = compound / standalone。关键问题：
  分子(compound) 与分母(standalone) 的比例关系是否随检测方法改变？
  若 R 与 Python 的整体缩放因子约掉，CHR 就稳健；否则 CHR 会被方法学污染。
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, r"D:\2607compound\python")
from config import INTERMEDIATE_DIR  # noqa: E402

R_CSV = r"D:\2607compound\results\intermediate\thw_events_R.csv"
PY_CSV = r"D:\2607compound\results\intermediate\thw_events.csv.bak"


def main():
    pairs = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "coastal_pairs.csv"))
    land_keys = set(zip(pairs.land_lat_idx, pairs.land_lon_idx))

    def land_days(csv, label):
        df = pd.read_csv(csv, usecols=["event_start", "duration", "lat_idx", "lon_idx"])
        df["event_start"] = pd.to_datetime(df.event_start)
        df["key"] = list(zip(df.lat_idx, df.lon_idx))
        df = df[df.key.isin(land_keys)]
        g = df.assign(year=df.event_start.dt.year).groupby("year").duration.sum()
        print(f"  {label:28s}: {len(df):>9,} events on coastal land, "
              f"{g.sum():>10,} THW-days")
        return g.rename(label)

    print("=" * 74)
    print("A. 沿海陆地格点上的 standalone THW 日数（CHR 的分母）")
    print("=" * 74)
    r_days = land_days(R_CSV, "R_days")
    p_days = land_days(PY_CSV, "Py_days")

    c = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, "annual_compound_days.nc"))
    da_c = c["compound_mhw_thw"]
    comp = (da_c.sum(dim=["lat", "lon"])).to_pandas()
    comp.index = comp.index.astype(int)

    ann = pd.concat([comp.rename("compound"), r_days, p_days], axis=1).dropna()
    ann["CHR_R"] = (ann.compound / ann.R_days).round(4)
    ann["CHR_Py"] = (ann.compound / ann.Py_days).round(4)
    ann["CHR_R/CHR_Py"] = (ann.CHR_R / ann.CHR_Py).round(3)

    print("\n" + "=" * 74)
    print("B. CHR 对比（分子相同，分母换成 R / Python）")
    print("=" * 74)
    print(ann.to_string())

    print(f"\n  CHR_R  均值 {ann.CHR_R.mean():.4f}   范围 {ann.CHR_R.min():.4f} .. {ann.CHR_R.max():.4f}")
    print(f"  CHR_Py 均值 {ann.CHR_Py.mean():.4f}   范围 {ann.CHR_Py.min():.4f} .. {ann.CHR_Py.max():.4f}")
    print(f"  两者年均值比 CHR_R / CHR_Py = {ann.CHR_R.mean()/ann.CHR_Py.mean():.3f}")
    print(f"  CHR_R 与 CHR_Py 的年度相关 = {ann.CHR_R.corr(ann.CHR_Py):.4f}")
    print(f"  逐年比值 std = {ann['CHR_R/CHR_Py'].std():.4f} "
          f"(越小说明 CHR 对检测方法越稳健)")

    # 趋势对比
    yr = ann.index.values
    for col in ["CHR_R", "CHR_Py"]:
        sl, ic = np.polyfit(yr, ann[col].values, 1)
        print(f"  {col} 线性趋势: {sl*10:+.5f} /10年")

    print("\n" + "=" * 74)
    print("C. 分母本身的稳健性：standalone 日数 R/Py 比值")
    print("=" * 74)
    ratio = (ann.R_days / ann.Py_days)
    print(f"  年均 R/Py = {ann.R_days.mean()/ann.Py_days.mean():.3f}")
    print(f"  逐年 R/Py: min {ratio.min():.3f}, max {ratio.max():.3f}, std {ratio.std():.3f}")
    print("  -> 若比值恒定，CHR 的分子分母同比例缩放，CHR 对检测方法稳健")

    print("\n" + "=" * 74)
    print("D. MHW 侧的口径检查（CHR 的分子来自 MHW）")
    print("=" * 74)
    mhw = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "mhw_events.csv"),
                      usecols=["event_start", "duration", "lat_idx", "lon_idx"])
    mhw["event_start"] = pd.to_datetime(mhw.event_start)
    print(f"  MHW 事件数: {len(mhw):,}, 总热浪日: {int(mhw.duration.sum()):,}")
    print(f"  MHW 平均时长: {mhw.duration.mean():.2f} 天")
    print("  ⚠️ detect_mhw.py 与 detect_thw.py 共用同一套判据")
    print("     (跨度>=5 含间隙)，因此 MHW 也有同向偏差。")
    print("     分子(MHW)与分母(THW)虽同向缩放，但**缩放因子不同**，")
    print("     故 CHR 仍会被方法学影响 —— 这是必须统一口径的核心理由。")


if __name__ == "__main__":
    main()
