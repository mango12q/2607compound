# Lead 独立复核 第八部分：复合链路与归因统计（独立于 baseline-stats-auditor）
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

BASE = r"D:\2607compound"
CESM_INT = os.path.join(BASE, "results", "intermediate", "cesm")
sys.path.insert(0, os.path.join(BASE, "python"))
import config as C  # noqa: E402
from compound_events import identify_compound_events, _pair_maps, _event_daily_mask  # noqa: E402


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


pairs = pd.read_csv(os.path.join(CESM_INT, "coastal_pairs_cesm.csv"))

hr("【L11】索引空间一致性：pairs.ocean_*_idx 与 mhw 事件表 lat_idx/lon_idx")
for f in ("mhw_ALL_001.csv", "mhw_x_ALL_001.csv", "mhw_XGHG_001.csv", "mhw_x_XGHG_001.csv"):
    d = pd.read_csv(os.path.join(CESM_INT, f))
    oi = set(zip(d.lat_idx, d.lon_idx))
    pi = set(zip(pairs.ocean_lat_idx, pairs.ocean_lon_idx))
    print(f"  {f:22s} 事件表点数={len(oi):4d}  pairs海点数={len(pi):4d}  "
          f"表⊆pairs? {oi <= pi}  表∖pairs={len(oi - pi)}  "
          f"lat_idx范围=[{d.lat_idx.min()},{d.lat_idx.max()}] "
          f"lon_idx范围=[{d.lon_idx.min()},{d.lon_idx.max()}]")
print(f"  pairs: 陆地 lat_idx 范围=[{pairs.land_lat_idx.min()},{pairs.land_lat_idx.max()}] "
      f"lon_idx=[{pairs.land_lon_idx.min()},{pairs.land_lon_idx.max()}]")
print(f"  pairs: 海洋 lat_idx 范围=[{pairs.ocean_lat_idx.min()},{pairs.ocean_lat_idx.max()}] "
      f"lon_idx=[{pairs.ocean_lon_idx.min()},{pairs.ocean_lon_idx.max()}]")
print("  ⇒ 关键：两类索引范围是否重叠（重叠则说明可能被混用）")

hr("【L12】独立复算 cmd_compound 的暴露时间（ALL 001 / XGHG 001，v2 tag='_x'）")
for exp, m in (("ALL", "001"), ("XGHG", "001")):
    t2m = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
    time_da = t2m["T2m"]
    nt = time_da.sizes["time"]
    t0 = pd.Timestamp(time_da.time.values[0])
    thw = pd.read_csv(os.path.join(CESM_INT, f"thw_x_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    mhw = pd.read_csv(os.path.join(CESM_INT, f"mhw_x_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    comp = identify_compound_events(mhw, thw, pairs, time_da.time)
    lpd = _pair_maps(pairs)
    om = {k: _event_daily_mask(g, nt, t0)
          for k, g in mhw.groupby(["lat_idx", "lon_idx"])}
    kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
    thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
    thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}
    cd = sd = td = 0
    for lk, ok_ in lpd.items():
        g = thw_by.get(lk)
        if g is None or len(g) == 0:
            continue
        lm = _event_daily_mask(g, nt, t0)
        td += int(lm.sum())
        mm = om.get(ok_)
        cd += int((lm & (mm if mm is not None else 0)).sum())
        sd += int((lm & ~(mm if mm is not None else np.zeros(nt, bool))).sum())
    ref = pd.read_csv(os.path.join(CESM_INT, "exposure_members_x.csv"))
    r = ref[(ref.exp == exp) & (ref.member == int(m))]
    print(f"  {exp} {m}: 复算 compound={cd:,} standalone={sd:,} thw={td:,}")
    if len(r):
        r = r.iloc[0]
        print(f"           落盘 compound={int(r.compound_days):,} "
              f"standalone={int(r.standalone_days):,} thw={int(r.thw_pair_days):,}  "
              f"一致? {int(r.compound_days)==cd and int(r.standalone_days)==sd and int(r.thw_pair_days)==td}")
    t2m.close()

hr("【L13】独立复算归因数字（v2）")
rows = []
for exp in ("ALL", "XGHG"):
    for m in ("001", "002", "003"):
        d = pd.read_csv(os.path.join(CESM_INT, f"annual_x_{exp}_{m}.csv"))
        d["member"] = m
        d["exp"] = exp
        rows.append(d)
A = pd.concat(rows)
print(f"  样本量: ALL={len(A[A.exp=='ALL'])}, XGHG={len(A[A.exp=='XGHG'])} "
      f"(20 成员全量时各 440)")
print(f"  Med 框配对数 = "
      f"{int((pairs.land_lat.between(30,47) & pairs.land_lon.between(5,42)).sum())} / 206")


def pr_boot(x, sa, sf, n=1000, seed=42):
    rng = np.random.default_rng(seed)

    def _pr(a, f):
        pf = float((f >= x).mean())
        return np.inf if pf == 0 else float((a >= x).mean()) / pf
    pt = _pr(sa, sf)
    b = np.array([_pr(sa[rng.integers(0, len(sa), len(sa))],
                      sf[rng.integers(0, len(sf), len(sf))]) for _ in range(n)])
    fin = b[np.isfinite(b)]
    lo, hi = np.percentile(fin, [5, 95]) if len(fin) else (np.nan, np.nan)
    return pt, (1 - 1 / pt if np.isfinite(pt) and pt > 0 else np.nan), lo, hi, len(b) - len(fin)


ann_obs = xr.open_dataset(C.ANNUAL_COMPOUND_NC)
var = list(ann_obs.data_vars)[0]
obs_pairs = pd.read_csv(C.COASTAL_PAIRS_CSV)
med_o = (obs_pairs.land_lat.between(30, 47) & obs_pairs.land_lon.between(5, 42)).values
po = obs_pairs[med_o]
sub = ann_obs[var].isel(lat=xr.DataArray(po.land_lat_idx.values, dims="p"),
                        lon=xr.DataArray(po.land_lon_idx.values, dims="p"))
arr = sub.transpose("time", "p").values
yrs = sub.time.values.astype(int)
mm = arr.mean(axis=1)
mx = arr.max(axis=1)
print(f"  观测 annual_compound_days.nc Med 框 2022: 区域均值={mm[list(yrs).index(2022)]:.1f} 天, "
      f"格点最大={mx[list(yrs).index(2022)]:.1f} 天")
print(f"    3 成员 × 22 年 = {len(A[A.exp=='ALL'])} 模型年/组")
for col, x in (("med_mean", mm[list(yrs).index(2022)]),
               ("med_max", mx[list(yrs).index(2022)])):
    sa = A[A.exp == "ALL"][col].values.astype(float)
    sf = A[A.exp == "XGHG"][col].values.astype(float)
    pt, far, lo, hi, ninf = pr_boot(x, sa, sf)
    p_all = float((sa >= x).mean())
    p_fix = float((sf >= x).mean())
    print(f"  [{col}] 阈值={x:.1f}天 P_ALL={p_all:.3f} P_fix={p_fix:.3f} "
          f"PR={pt if np.isfinite(pt) else float('inf'):.2f} FAR={far:.3f} "
          f"CI(PR)={lo:.1f}-{hi:.1f}  bootstrap中inf数={ninf}")
ann_obs.close()

hr("【L14】_pr_boot 在 p_fix=0 时的打印行为（cmd_attrib 的 f-string）")
try:
    far = float("nan")
    print("  f'{far:.2f}' ->", f"{far:.2f}")
    pt = np.inf
    far2 = 1 - 1 / pt if np.isfinite(pt) and pt > 0 else np.nan
    print(f"  point=inf 时 far={far2}, 打印 f'{far2:.2f}' -> {far2:.2f}")
except Exception as e:
    print("  异常:", e)

hr("【L15】复现报告 §11.6 的『22 年总暴露均值比 8.88』复算")
d = pd.read_csv(os.path.join(CESM_INT, "exposure_members_x.csv"))
for n in (22, 1):
    a = d[d.exp == "ALL"].compound_days.values.astype(float)
    f = d[d.exp == "XGHG"].compound_days.values.astype(float)
    print(f"  compound_days: ALL 均值={a.mean():,.0f} XGHG 均值={f.mean():,.0f} "
          f"比值={a.mean()/f.mean():.2f}   (报告写 8.88)")
    break
print(d.groupby("exp")[["compound_days", "standalone_days", "thw_pair_days"]].agg(["mean", "sum"]))
