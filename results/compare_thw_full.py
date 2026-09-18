"""compare_thw_full.py — R(heatwaveR) 与 Python 全量 THW 检测结果的逐格点对比。

对比口径（严格对齐，否则结论无效）：
  * 只在两者**都处理过**的格点集合上交集比较
    - Python 侧格点 = land_mask（t=0 非 NaN）
    - R 侧格点 = 24 个时相并集且有效日数 >= 730
  * R 的 lat_idx/lon_idx 已用坐标反查映射为全局 0-based，与 xarray 约定一致
  * 指数衰减：先比对同一格点的年度事件数，再比对事件级重叠
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, r"D:\2607compound\python")

R_CSV = r"D:\2607compound\results\intermediate\thw_events_R.csv"
PY_CSV = r"D:\2607compound\results\intermediate\thw_events.csv.bak"
EOBS = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"
OUT = r"D:\2607compound\results\tables"

os.makedirs(OUT, exist_ok=True)


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size < 2 or np.std(a) == 0 or np.std(b) == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def main():
    print("Loading events...")
    r = pd.read_csv(R_CSV)
    py = pd.read_csv(PY_CSV)
    r["event_start"] = pd.to_datetime(r.event_start)
    r["event_end"] = pd.to_datetime(r.event_end)
    py["event_start"] = pd.to_datetime(py.event_start)
    py["event_end"] = pd.to_datetime(py.event_end)

    print(f"R  events: {len(r):,}   points: {r.groupby(['lat_idx','lon_idx']).ngroups:,}")
    print(f"Py events: {len(py):,}   points: {py.groupby(['lat_idx','lon_idx']).ngroups:,}")

    # ---- 索引一致性自检 ----
    ri = r[["lat_idx", "lon_idx", "lat", "lon"]].drop_duplicates()
    pi = py[["lat_idx", "lon_idx", "lat", "lon"]].drop_duplicates()
    chk = ri.merge(pi, on=["lat_idx", "lon_idx"], suffixes=("_r", "_py"), how="inner")
    bad = (np.abs(chk.lat_r - chk.lat_py) > 1e-6) | (np.abs(chk.lon_r - chk.lon_py) > 1e-6)
    print(f"\n[check] index->coord agreement: {len(chk)-bad.sum():,}/{len(chk):,}"
          + ("  <<< MISMATCH" if bad.sum() else "  OK"))

    # ---- 与 E-OBS 全局网格的索引自检 ----
    ds = xr.open_dataset(EOBS)
    lat_g, lon_g = ds.lat.values, ds.lon.values
    for name, df in (("R", ri), ("Py", pi)):
        dlat = np.abs(lat_g[df.lat_idx.values] - df.lat.values).max()
        dlon = np.abs(lon_g[df.lon_idx.values] - df.lon.values).max()
        print(f"[check] {name}: max |lat_idx->lat - lat| = {dlat:.2e}, "
              f"max |lon_idx->lon - lon| = {dlon:.2e}")
        assert dlat < 1e-6 and dlon < 1e-6, f"{name} index/coord mismatch"

    # ---- 交集格点 ----
    r_pts = set(map(tuple, ri[["lat_idx", "lon_idx"]].values))
    py_pts = set(map(tuple, pi[["lat_idx", "lon_idx"]].values))
    common = sorted(r_pts & py_pts)
    print(f"\nPoints: R only {len(r_pts-py_pts):,}   Py only {len(py_pts-r_pts):,}   "
          f"common {len(common):,}")

    def sub(df):
        return df[df[["lat_idx", "lon_idx"]].apply(tuple, axis=1).isin(set(common))]

    rc, pc = sub(r), sub(py)
    print(f"Events on common points: R {len(rc):,}   Py {len(pc):,}   "
          f"ratio R/Py = {len(rc)/len(pc):.3f}")

    # ---- 逐格点事件数 ----
    cnt = pd.concat([
        rc.groupby(["lat_idx", "lon_idx"]).size().rename("R"),
        pc.groupby(["lat_idx", "lon_idx"]).size().rename("Py"),
    ], axis=1).fillna(0)
    cnt["ratio"] = cnt.R / cnt.Py.replace(0, np.nan)
    print("\n=== 逐格点事件数 ===")
    print(f"  median R/Py = {cnt.ratio.median():.3f}   mean = {cnt.ratio.mean():.3f}   "
          f"corr = {pearson(cnt.R, cnt.Py):.3f}")
    print(f"  R>Py: {(cnt.R>cnt.Py).sum():,}   R<Py: {(cnt.R<cnt.Py).sum():,}   "
          f"equal: {(cnt.R==cnt.Py).sum():,}")

    # ---- 时长分布（检验"Python 把一次热浪切碎"假设）----
    print("\n=== 事件时长 (days) ===")
    dur = pd.DataFrame({
        "R": rc.duration.describe(percentiles=[.25, .5, .75, .9]),
        "Py": pc.duration.describe(percentiles=[.25, .5, .75, .9]),
    })
    print(dur.round(2).to_string())
    print(f"  R  总热浪日 : {int(rc.duration.sum()):,}")
    print(f"  Py 总热浪日 : {int(pc.duration.sum()):,}   "
          f"ratio = {rc.duration.sum()/pc.duration.sum():.3f}")

    # ---- 事件级重叠（逐格点计算，避免 24 亿行笛卡尔积爆内存）----
    key = ["lat_idx", "lon_idx"]
    print("\n=== 事件级重叠（逐格点）===")
    tot_r = tot_py = 0
    r_hit = py_hit = 0
    exact = 0
    frac_sum = 0.0
    frac_n = 0
    frac_max = 0
    ovl_days = []
    rc_g = {k: v for k, v in rc.groupby(key, sort=False)}
    pc_g = {k: v for k, v in pc.groupby(key, sort=False)}
    for k, g in rc_g.items():
        h = pc_g.get(k)
        if h is None:
            continue
        tot_r += len(g)
        tot_py += len(h)
        gs, ge = g.event_start.values, g.event_end.values
        hs, he = h.event_start.values, h.event_end.values
        # 逐事件求与对面事件集合的区间重叠
        for i in range(len(g)):
            lo = np.searchsorted(hs, ge[i], side="right")
            cand = slice(max(0, lo - len(h)), lo)
            ov = (np.minimum(ge[i], he[cand])
                  - np.maximum(gs[i], hs[cand])).astype("timedelta64[D]").astype(int) + 1
            n = int((ov > 0).sum())
            if n > 0:
                r_hit += 1
                if gs[i] in set(hs[cand][ov > 0]):
                    exact += 1
                frac_sum += n
                frac_n += 1
                frac_max = max(frac_max, n)
                ovl_days.append(int(ov.max()))
        for j in range(len(h)):
            lo = np.searchsorted(gs, he[j], side="right")
            cand = slice(max(0, lo - len(g)), lo)
            ov = (np.minimum(he[j], ge[cand])
                  - np.maximum(hs[j], gs[cand])).astype("timedelta64[D]").astype(int) + 1
            if (ov > 0).any():
                py_hit += 1

    print(f"  R  事件被 >=1 个 Py 事件覆盖 : {r_hit:,} / {tot_r:,} ({100*r_hit/tot_r:.1f}%)")
    print(f"     其中起始日完全一致       : {exact:,} ({100*exact/tot_r:.1f}%)")
    print(f"  Py 事件被 >=1 个 R  事件覆盖 : {py_hit:,} / {tot_py:,} ({100*py_hit/tot_py:.1f}%)")
    print(f"  每个被覆盖的 R 事件平均对应 Py 事件数: {frac_sum/max(frac_n,1):.2f} "
          f"(最大 {frac_max})")
    if ovl_days:
        print(f"  最大区间重叠天数: {max(ovl_days)}")

    # ---- 年度序列 ----
    ra = rc.assign(year=rc.event_start.dt.year).groupby("year").size().rename("R")
    pa = pc.assign(year=pc.event_start.dt.year).groupby("year").size().rename("Py")
    ry = rc.assign(year=rc.event_start.dt.year).groupby("year").duration.sum().rename("R_days")
    py_ = pc.assign(year=pc.event_start.dt.year).groupby("year").duration.sum().rename("Py_days")
    ann = pd.concat([ra, pa, ry, py_], axis=1).fillna(0).astype(int)
    ann["R/Py"] = (ann.R / ann.Py.replace(0, np.nan)).round(3)
    ann.to_csv(os.path.join(OUT, "thw_R_vs_python_annual.csv"))
    print("\n=== 年度对比 ===")
    print(ann.to_string())
    print(f"\n  年度相关系数: 事件数 corr = {pearson(ann.R, ann.Py):.4f}, "
          f"热浪日 corr = {pearson(ann.R_days, ann.Py_days):.4f}")
    print(f"  R  前 8 峰值年: {list(ann.R.nlargest(8).index)}")
    print(f"  Py 前 8 峰值年: {list(ann.Py.nlargest(8).index)}")
    print(f"  R  前 8 (热浪日): {list(ann.R_days.nlargest(8).index)}")
    print(f"  Py 前 8 (热浪日): {list(ann.Py_days.nlargest(8).index)}")

    cnt.reset_index().to_csv(os.path.join(OUT, "thw_R_vs_python_perpoint.csv"), index=False)
    print(f"\nSaved tables to {OUT}")


if __name__ == "__main__":
    main()
