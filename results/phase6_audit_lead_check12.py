# Lead 独立复核 第十二部分：ALL 组 t0=2000-01-01 12:00 的日期→索引映射是否自洽
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

BASE = r"D:\2607compound"
CESM_INT = os.path.join(BASE, "results", "intermediate", "cesm")
sys.path.insert(0, os.path.join(BASE, "python"))
from compound_events import identify_compound_events, _pair_maps, _event_daily_mask  # noqa: E402

pairs = pd.read_csv(os.path.join(CESM_INT, "coastal_pairs_cesm.csv"))

print("=" * 78)
print("【L20】各组 T2m 时间原点 t0")
print("=" * 78)
t0s = {}
for exp in ("ALL", "XGHG"):
    for m in ("001",):
        ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
        t = pd.DatetimeIndex(ds["T2m"].time.values)
        t0s[exp] = pd.Timestamp(t[0])
        print(f"  {exp} {m}: n={len(t)}  t0={t[0]}  t_last={t[-1]}  "
              f"（分钟={t[0].minute}, 小时={t[0].hour}）")
        ds.close()

print()
print("=" * 78)
print("【L21】同一日期在两种 t0 下映射到的数组索引")
print("=" * 78)
print(f"  {'日期':12s} {'ALL t0 索引':>12s} {'正确索引':>10s} {'XGHG t0 索引':>13s} {'正确索引':>10s}")
for d in ("2000-01-01", "2000-01-02", "2000-06-15", "2006-01-02", "2021-12-31"):
    ts = pd.Timestamp(d)
    ia = (ts - t0s["ALL"]).days
    ix = (ts - t0s["XGHG"]).days
    corr = (ts - pd.Timestamp("2000-01-01")).days
    print(f"  {d:12s} {ia:12d} {corr:10d} {ix:13d} {corr:10d}")
print("  ⇒ ALL 组整体偏移 −1（因 t0 在 12:00）；XGHG 组无偏移。")

print()
print("=" * 78)
print("【L22】决定性检验：THW 与 MHW 掩码是否用了同一个 t0（同偏移则互抵）")
print("=" * 78)
for exp, m in (("ALL", "001"), ("XGHG", "001")):
    ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
    time_da = ds["T2m"]
    nt = time_da.sizes["time"]
    t0 = pd.Timestamp(time_da.time.values[0])
    thw = pd.read_csv(os.path.join(CESM_INT, f"thw_x_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    mhw = pd.read_csv(os.path.join(CESM_INT, f"mhw_x_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    for nm, ev in (("THW", thw), ("MHW", mhw)):
        s = (ev.event_start - t0).dt.days.values
        e = (ev.event_end - t0).dt.days.values
        print(f"  {exp} {m} {nm}: 事件 {len(ev)} 个，索引范围 "
              f"s∈[{s.min()},{s.max()}] e∈[{e.min()},{e.max()}]  "
              f"min_s<0 的个数={int((s<0).sum())}  max_e>nt-1 的个数={int((e>nt-1).sum())}")
    ds.close()

print()
print("=" * 78)
print("【L23】用『显式正确的日期→索引映射』重算 ALL/XGHG 的 v2 复合暴露，与落盘值对比")
print("=" * 78)


def exposure_with_correct_origin(exp, m):
    """索引 = (date - 2000-01-01).days，完全绕开 t0 的小时部分。"""
    ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
    time_da = ds["T2m"]
    nt = time_da.sizes["time"]
    ds.close()
    origin = pd.Timestamp("2000-01-01")
    thw = pd.read_csv(os.path.join(CESM_INT, f"thw_x_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    mhw = pd.read_csv(os.path.join(CESM_INT, f"mhw_x_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    lpd = _pair_maps(pairs)

    def mask(ev):
        mm = np.zeros(nt, dtype=bool)
        s = (ev.event_start - origin).dt.days.values
        e = (ev.event_end - origin).dt.days.values
        for i0, i1 in zip(s, e):
            a, b = max(int(i0), 0), min(int(i1), nt - 1)
            if b >= a:
                mm[a:b + 1] = True
        return mm

    om = {k: mask(g) for k, g in mhw.groupby(["lat_idx", "lon_idx"])}
    kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
    thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
    thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}
    cd = sd = td = 0
    for lk, ok_ in lpd.items():
        g = thw_by.get(lk)
        if g is None or len(g) == 0:
            continue
        lm = mask(g)
        td += int(lm.sum())
        mm = om.get(ok_)
        cd += int((lm & (mm if mm is not None else 0)).sum())
        sd += int((lm & ~(mm if mm is not None else np.zeros(nt, bool))).sum())
    return cd, sd, td


ref = pd.read_csv(os.path.join(CESM_INT, "exposure_members_x.csv"))
for exp in ("ALL", "XGHG"):
    for m in ("001", "002", "003"):
        cd, sd, td = exposure_with_correct_origin(exp, m)
        r = ref[(ref.exp == exp) & (ref.member == int(m))].iloc[0]
        same = (int(r.compound_days) == cd and int(r.standalone_days) == sd
                and int(r.thw_pair_days) == td)
        print(f"  {exp} {m}: 正确原点 compound={cd:,} standalone={sd:,} thw={td:,} | "
              f"落盘 compound={int(r.compound_days):,} standalone={int(r.standalone_days):,} "
              f"thw={int(r.thw_pair_days):,} | 完全一致? {same}")
        if not same:
            print(f"      差值: compound {cd-int(r.compound_days):+d} "
                  f"standalone {sd-int(r.standalone_days):+d} "
                  f"thw {td-int(r.thw_pair_days):+d}")
