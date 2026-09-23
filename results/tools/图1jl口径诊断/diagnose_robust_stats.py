"""diagnose_robust_stats.py — 检验论文 fig1j/l 是否用中位数/分位数聚合。

对每个区域逐年, 在配对格点上取 mean/p50/p75/p90:
  (a) 共超标天数 V4 (来自 annual_compound_days.nc, 瞬时可得)
  (b) MHW 包络天数 V1 (逐格点重算, 存 npz)

论文目标特征: 80s/90s<20, 2018/2020/2022 高峰, 2022=78(峰值) > 2023=72,
Europe 2022=77(峰值), 曲线 <90。
"""
import os

import numpy as np
import pandas as pd
import xarray as xr

INTER = r"D:\2607compound\results\intermediate"
NT = 14975
EPOCH = pd.Timestamp("1983-01-01")
_day_years = np.array([(EPOCH + pd.Timedelta(days=i)).year for i in range(NT)])
YEARS = np.arange(1983, 2024)
REG = {"Med&BS": (30, 47, 5, 42), "Europe": (30, 72, -15, 45)}
SHOW = [1990, 2003, 2018, 2020, 2022, 2023]


def d2i(d):
    return (pd.Timestamp(d) - EPOCH).days


def main():
    comp = xr.open_dataset(os.path.join(INTER, "annual_compound_days.nc"))["compound_mhw_thw"]
    thwtot = xr.open_dataset(os.path.join(INTER, "annual_thw_days.nc"))["compound_mhw_thw"]
    lat, lon = comp.lat.values, comp.lon.values
    C = comp.values.astype(float)                      # (41, nlat, nlon)
    T = thwtot.values.astype(float)
    paired = T.sum(axis=0) > 0                         # 配对格点掩码

    # ---- (a) V4 分位数 ----
    print("== V4 逐日共超标 (annual nc) ==")
    for rn, (la0, la1, lo0, lo1) in REG.items():
        m = paired & (lat[:, None] >= la0) & (lat[:, None] <= la1) \
            & (lon[None, :] >= lo0) & (lon[None, :] <= lo1)
        cs = C[:, m].T                                 # (n_cells, 41)
        p50 = np.median(cs, axis=0)
        p75 = np.percentile(cs, 75, axis=0)
        p90 = np.percentile(cs, 90, axis=0)
        sel = lambda v: "  ".join(f"{y}={v[list(YEARS).index(y)]:5.1f}" for y in SHOW)
        print(f"  {rn}: p50 {sel(p50)}")
        print(f"  {'':8s}p75 {sel(p75)}")
        print(f"  {'':8s}p90 {sel(p90)}")

    # ---- (b) V1 逐格点包络 ----
    npz = os.path.join(INTER, "_v1_envelope_cells.npz")
    if not os.path.exists(npz):
        print("\ncomputing per-cell V1 envelope series...")
        pairs = pd.read_csv(os.path.join(INTER, "coastal_pairs.csv"))
        thw = pd.read_csv(os.path.join(INTER, "thw_events_R.csv"))
        mhw = pd.read_csv(os.path.join(INTER, "mhw_events_R_global.csv"))
        tg = {k: g[["event_start", "event_end"]].values.tolist()
              for k, g in thw.groupby(["lat", "lon"])}
        og = {k: g[["event_start", "event_end"]].values.tolist()
              for k, g in mhw.groupby(["lat", "lon"])}
        keys, series = [], []
        for _, p in pairs.iterrows():
            t_ev = tg.get((p.land_lat, p.land_lon), [])
            o_ev = og.get((p.ocean_lat, p.ocean_lon), [])
            v = np.zeros(41)
            t_iv = [(d2i(s), d2i(e)) for s, e in t_ev]
            for ms, me in o_ev:
                mi0, mi1 = d2i(ms), d2i(me)
                if t_iv and any(a >= mi0 and b <= mi1 for a, b in t_iv):
                    v += (_day_years[max(mi0, 0):min(mi1, NT - 1) + 1]
                          == YEARS[:, None]).sum(axis=1)
            keys.append((p.land_lat, p.land_lon))
            series.append(v)
        np.savez_compressed(npz, keys=np.array(keys), series=np.array(series))
    z = np.load(npz, allow_pickle=True)
    keys, S = z["keys"], z["series"].astype(float)     # (n_pairs, 41)
    klat = np.array([k[0] for k in keys])
    klon = np.array([k[1] for k in keys])

    print("\n== V1 MHW 包络 (per-cell) ==")
    for rn, (la0, la1, lo0, lo1) in REG.items():
        m = (klat >= la0) & (klat <= la1) & (klon >= lo0) & (klon <= lo1)
        cs = S[m]
        w = np.cos(np.deg2rad(klat[m]))
        wm = (cs * w[:, None]).sum(axis=0) / w.sum()
        p50 = np.median(cs, axis=0)
        p75 = np.percentile(cs, 75, axis=0)
        p90 = np.percentile(cs, 90, axis=0)
        sel = lambda v: "  ".join(f"{y}={v[list(YEARS).index(y)]:5.1f}" for y in SHOW)
        print(f"  {rn} (n={m.sum()}): wmean {sel(wm)}")
        print(f"  {'':8s}p50 {sel(p50)}")
        print(f"  {'':8s}p75 {sel(p75)}")
        print(f"  {'':8s}p90 {sel(p90)}")
    print("\n论文: Med 80s/90s<20, 2022=78(峰)>2023=72, 峰值年>62, <90 | Europe 2022=77(峰)")


if __name__ == "__main__":
    main()
