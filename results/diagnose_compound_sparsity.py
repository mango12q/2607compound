"""diagnose_compound_sparsity.py — 为什么 compound 只有 0.2 天/年？

图1(a-i)、图2(a) 要复现的是"compound 天数的空间分布"。
如果 compound 常年为 0，那再好的检测方法也画不出一张有内容的图。
本脚本定位 compound 稀疏的结构性原因。
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, r"D:\2607compound\python")
from config import INTERMEDIATE_DIR  # noqa: E402


def main():
    pairs = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "coastal_pairs.csv"))
    print("=" * 74)
    print("A. 沿海配对（compound 检测的作用域）")
    print("=" * 74)
    print(f"  配对数: {len(pairs):,}")
    print(f"  land  格点: {pairs.groupby(['land_lat_idx','land_lon_idx']).ngroups:,}")
    print(f"  ocean 格点: {pairs.groupby(['ocean_lat_idx','ocean_lon_idx']).ngroups:,}")
    print(f"  land 纬度范围: {pairs.land_lat.min():.2f} .. {pairs.land_lat.max():.2f}")
    print(f"  land 经度范围: {pairs.land_lon.min():.2f} .. {pairs.land_lon.max():.2f}")
    print(f"  dist_deg 分布:\n{pairs.dist_deg.describe().round(3).to_string()}")

    mhw = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "mhw_events.csv"),
                      usecols=["lat_idx", "lon_idx", "event_start", "event_end"])
    print(f"\n  MHW 事件: {len(mhw):,}, 覆盖格点 {mhw.groupby(['lat_idx','lon_idx']).ngroups:,}")

    # MHW 事件覆盖到的 ocean 配对格点
    oce = pairs[["ocean_lat_idx", "ocean_lon_idx"]].drop_duplicates()
    oce["key"] = list(zip(oce.ocean_lat_idx, oce.ocean_lon_idx))
    mhw["key"] = list(zip(mhw.lat_idx, mhw.lon_idx))
    mhw_keys = set(mhw.key.unique())
    hit = oce.key.isin(mhw_keys).sum()
    print(f"  配对中的 ocean 格点 {len(oce):,} 个，其中 {hit:,} 个有 MHW 事件 "
          f"({100*hit/len(oce):.1f}%)")

    print("\n" + "=" * 74)
    print("B. compound 结果的空间分布")
    print("=" * 74)
    c = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, "annual_compound_days.nc"))
    s = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, "annual_standalone_days.nc"))
    da_c = c["compound_mhw_thw"]
    da_s = s["standalone_thw"]

    tot_c = da_c.sum("time")
    tot_s = da_s.sum("time")
    alive = (tot_s > 0)
    print(f"  standalone 有值的格点: {int(alive.sum()):,}")
    print(f"  compound   有值的格点: {int((tot_c > 0).sum()):,}")
    print(f"  compound / standalone 格点数比: "
          f"{float((tot_c>0).sum())/max(float(alive.sum()),1):.3f}")

    # 逐格点 41 年总 compound 天数分布
    v = tot_c.values[tot_c.values > 0]
    if v.size:
        print(f"\n  有 compound 的格点，41 年合计天数分布:")
        print(f"    n={v.size:,}  mean={v.mean():.1f}  median={np.median(v):.1f}  "
              f"max={v.max():.0f}")
        print(f"    === 1 天(仅出现过一次) 的格点占比: {100*np.mean(v <= 1):.1f}%")
        print(f"    === 2-5 天 的格点占比: {100*np.mean((v > 1) & (v <= 5)):.1f}%")
        print(f"    >= 50 天 的格点占比: {100*np.mean(v >= 50):.1f}%")

    print("\n" + "=" * 74)
    print("C. 若 compound 常年为 0，图1/图2 会是什么样")
    print("=" * 74)
    ann_tot = da_c.sum(dim=["lat", "lon"]).values
    print("  逐年 compound 总天数（全域求和）:")
    yrs = da_c.time.values.astype(int)
    for y, t in zip(yrs, ann_tot):
        bar = "#" * int(min(t / max(ann_tot.max(), 1) * 40, 40))
        print(f"    {y}: {t:>8.0f}  {bar}")
    zero_years = int((ann_tot == 0).sum())
    print(f"\n  compound 全域总和为 0 的年份: {zero_years} / {len(yrs)}")
    print(f"  -> 图1(j-l) 的年度序列会出现 {zero_years} 个零点，"
          f"图1(a-i) 的 9 个年份面板中 0 值面板取决于所选年份")


if __name__ == "__main__":
    main()
