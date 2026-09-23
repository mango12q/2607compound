# Lead 独立复核 第九部分：--members 截断 与 SST 时间标签偏置
import os
import sys

import numpy as np
import xarray as xr

BASE = r"D:\2607compound"
PROC = os.path.join(BASE, "data", "CESM1-LE", "proc")
sys.path.insert(0, os.path.join(BASE, "python"))
import config as C  # noqa: E402
import phase6_cesm as P  # noqa: E402

print("=" * 78)
print("【L16】--members N 的实际作用域")
print("=" * 78)
print(f"  C.CESM_ALL_MEMBERS     = {C.CESM_ALL_MEMBERS}")
print(f"  C.CESM_P0_MEMBERS      = {C.CESM_P0_MEMBERS}")
print(f"  MEMBERS_P0 (=ALL[:P0]) = {P.MEMBERS_P0}")
for n in (3, 20):
    print(f"  MEMBERS_P0[:{n}]       = {P.MEMBERS_P0[:n]}   -> 实际成员数 {len(P.MEMBERS_P0[:n])}")
print("  ⇒ --members 20 与 --members 3 完全等价：静默只跑 3 个成员。")

print()
print("=" * 78)
print("【L17】时间标签：CAM TREFHT vs POP nday1 SST")
print("=" * 78)
for f, lab in (
        ("TREFHT_all_001_2000-2021_europe.nc", "CAM TREFHT (ALL 001)"),
        ("b.e11.B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.SST.18500102-20051231_2000-2021.nc",
         "POP SST (ALL 001, 20C 段)"),
        ("b.e11.BRCP85C5CNBDRD.f09_g16.001.pop.h.nday1.SST.20060102-20801231_2000-2021.nc",
         "POP SST (ALL 001, RCP 段)"),
        ("b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.20060101-20801231_2000-2021.nc",
         "CAM TREFHT (XGHG 001, 第2段)")):
    p = os.path.join(PROC, f)
    if not os.path.exists(p):
        print(f"  !! 缺 {f}")
        continue
    ds = xr.open_dataset(p, decode_times=False)
    tv = ds["time"].values
    units = ds["time"].attrs.get("units", "?")
    cal = ds["time"].attrs.get("calendar", "?")
    has_b = "time_bounds" in ds.variables or "time_bnds" in ds.variables
    print(f"\n  {lab}")
    print(f"    ntime={len(tv)}  units={units!r}  calendar={cal!r}  time_bounds? {has_b}")
    print(f"    首 3 个原始 time 值 = {tv[:3]}")
    print(f"    末 3 个原始 time 值 = {tv[-3:]}")
    for bn in ("time_bounds", "time_bnds"):
        if bn in ds.variables:
            b = ds[bn].values
            print(f"    {bn}[0] = {b[0]}   {bn}[1] = {b[1]}   {bn}[-1] = {b[-1]}")
    ds.close()

print()
print("=" * 78)
print("【L18】用解码后的时间序列确认日期是否连续、SST 是否缺 1 天")
print("=" * 78)
import pandas as pd  # noqa: E402
for f, lab in (
        ("TREFHT_all_001_2000-2021_europe.nc", "CAM TREFHT ALL 001"),
        ("b.e11.BRCP85C5CNBDRD.f09_g16.001.pop.h.nday1.SST.20060102-20801231_2000-2021.nc",
         "POP SST ALL 001 RCP 段")):
    ds = xr.open_dataset(os.path.join(PROC, f))
    t = pd.DatetimeIndex(ds.time.values)
    gaps = np.diff(t.values).astype("timedelta64[D]").astype(int)
    print(f"  {lab}: n={len(t)}  {t[0].date()} ~ {t[-1].date()}  "
          f"步长唯一值={np.unique(gaps)}  非 1 天处={int((gaps != 1).sum())}")
    if (gaps != 1).sum():
        idx = np.flatnonzero(gaps != 1)[:5]
        for i in idx:
            print(f"      异常: {t[i].date()} -> {t[i+1].date()} (相隔 {gaps[i]} 天)")
    ds.close()

print()
print("=" * 78)
print("【L19】SST 段拼接后是否缺 2006-01-01 / 总天数")
print("=" * 78)
segs = P.find_sst_segments("ALL", "001")
print(f"  find_sst_segments('ALL','001') -> {len(segs)} 段")
tot = 0
allt = []
for f in segs:
    ds = xr.open_dataset(os.path.join(PROC, os.path.basename(f)))
    t = pd.DatetimeIndex(ds.time.values)
    allt.append(t)
    print(f"    {os.path.basename(f)[:70]:70s} n={len(t)} {t[0].date()}~{t[-1].date()}")
    tot += len(t)
    ds.close()
cat = allt[0].append(allt[1])
print(f"  合计 n={tot}；拼接后 n={len(cat)}；重复={len(cat)-len(cat.unique())}")
print(f"  期望 noleap 22 年 = 8030 天；实际 {len(cat)} ⇒ 缺 {8030-len(cat)} 天")
missing = pd.date_range("2000-01-01", "2021-12-31", freq="D").difference(cat)
print(f"  公历缺失日期（前 5）: {[str(d.date()) for d in missing[:5]]}")
