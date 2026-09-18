"""figure_sensitivity.py — 检验换成 R 检测后，图1/图2 的图形会不会变。

核心思路：图1(j-l) 与图2(c) 画的是**年度序列的形状**，
图1(a-i)/图2(a,b,d) 画的是**空间格局**（且图1色标是自适应 95 分位、图2色标是固定值）。
因此要分别判断：
  * 形状：用"归一化年度序列"（各年 / 各自均值）比较，形状一致 => 峰值年标注/趋势线不变
  * 量级：绝对值会变，图2 的固定色标与 0-90 的 y 轴会受影响
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


def annual_counts(csv, region=None):
    df = pd.read_csv(csv, usecols=["event_start", "duration", "lat", "lon"])
    df["event_start"] = pd.to_datetime(df.event_start)
    if region is not None:
        lo0, lo1, la0, la1 = region
        df = df[df.lon.between(lo0, lo1) & df.lat.between(la0, la1)]
    g = df.assign(year=df.event_start.dt.year).groupby("year")
    return g.size().rename("events"), g.duration.sum().rename("days")


def norm(s):
    return s / s.mean()


def main():
    print("=" * 74)
    print("1. THW 年度序列：R vs Python（欧洲域 30-72N, -15-45E）")
    print("=" * 74)
    reg = (-15, 45, 30, 72)
    r_ev, r_dy = annual_counts(R_CSV, reg)
    p_ev, p_dy = annual_counts(PY_CSV, reg)
    ann = pd.concat([r_dy.rename("R_days"), p_dy.rename("Py_days"),
                     r_ev.rename("R_events"), p_ev.rename("Py_events")], axis=1)
    ann["R/Py_days"] = (ann.R_days / ann.Py_days).round(3)
    print(ann.to_string())
    print(f"\n  均值: R {ann.R_days.mean():.0f} 天/年   Python {ann.Py_days.mean():.0f} 天/年"
          f"   -> 量级比 {ann.R_days.mean()/ann.Py_days.mean():.3f}")
    print(f"  年度相关(热浪日): {ann.R_days.corr(ann.Py_days):.4f}")
    print(f"  R/Py 逐年比值的稳定性: min {ann['R/Py_days'].min():.3f}, "
          f"max {ann['R/Py_days'].max():.3f}, std {ann['R/Py_days'].std():.3f}")

    print("\n" + "=" * 74)
    print("2. 归一化形状对比（各年 ÷ 各自均值）——决定图1(j-l)/图2(c) 的图形")
    print("=" * 74)
    nr, np_ = norm(ann.R_days), norm(ann.Py_days)
    cmp_ = pd.DataFrame({"R_norm": nr.round(3), "Py_norm": np_.round(3)})
    cmp_["diff"] = (cmp_.R_norm - cmp_.Py_norm).round(3)
    print(cmp_.to_string())
    print(f"\n  归一化序列相关: {nr.corr(np_):.4f}")
    print(f"  归一化后最大偏差: {cmp_['diff'].abs().max():.3f}"
          f"  (占均值 {100*cmp_['diff'].abs().max():.1f}%)")
    print(f"  R  前 5 峰值年(归一化): {list(nr.nlargest(5).index)}")
    print(f"  Py 前 5 峰值年(归一化): {list(np_.nlargest(5).index)}")

    print("\n" + "=" * 74)
    print("3. 现有 compound 序列与 R/Python THW 序列的一致性")
    print("=" * 74)
    try:
        c = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, "annual_compound_days.nc"))
        da = c["compound_mhw_thw"]
        w = np.cos(np.deg2rad(da.lat))
        comp = da.weighted(w).mean(dim=["lat", "lon"]).to_pandas()
        comp.index = comp.index.astype(int)
        comp = comp.reindex(ann.index)
        print(f"  corr(compound, THW_Python_days) = {comp.corr(ann.Py_days):.4f}")
        print(f"  corr(compound, THW_R_days)      = {comp.corr(ann.R_days):.4f}")
        print(f"  corr(compound_norm, R_norm)     = {norm(comp).corr(nr):.4f}")
        print(f"  compound 均值: {comp.mean():.2f} 天/年")
    except Exception as e:
        print(f"  (跳过: {e})")

    print("\n" + "=" * 74)
    print("4. 图2 固定色标的影响（论文量级 vs 现有数据）")
    print("=" * 74)
    try:
        c = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, "annual_compound_days.nc"))
        s = xr.open_dataset(os.path.join(INTERMEDIATE_DIR, "annual_standalone_days.nc"))
        cm = c["compound_mhw_thw"].sel(time=slice(2003, 2023)).mean("time")
        sm = s["standalone_thw"].sel(time=slice(2003, 2023)).mean("time")
        print(f"  compound 2003-2023 均值域平均: {float(cm.weighted(np.cos(np.deg2rad(cm.lat))).mean()):.2f} 天")
        print(f"  compound 空间最大           : {float(cm.max()):.2f} 天  (图2a 色标 vmax=20)")
        print(f"  standalone 空间最大         : {float(sm.max()):.2f} 天  (图2b 色标 vmax=20)")
        print(f"  compound > 20 的格点占比    : {100*float((cm > 20).mean()):.2f}%")
        print(f"  standalone > 20 的格点占比  : {100*float((sm > 20).mean()):.2f}%")
    except Exception as e:
        print(f"  (跳过: {e})")


if __name__ == "__main__":
    main()
