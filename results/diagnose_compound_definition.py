"""diagnose_compound_definition.py — 检验论文复合日数的两种操作性定义。

论文 Methods 里有两个表述:
  L477: "compound = periods during which both T2m and SST simultaneously exceed
         their respective thresholds"  -> 逐日共超标 (co-exceedance)
  L520: "compound heatwave day = a day when a MHW fully encompasses a THW"
                                        -> 整事件包含 (containment, 我们当前实现)

对同一套事件分别按两种定义计算, 与论文锚点对照:
  fig1j Med&BS: 80s/90s 通常<20, 2022~78, 2023~72
  fig1l Europe: 2022~77
  fig1m cooc:   西地中海>0.8, 地中海 0.6-0.8, 大西洋 0.2-0.4
  fig2c CHR:    80s/90s ~1, 2023 峰值 3.5

对 R(严格) 与 Python旧(跨度) 两套事件各算一遍。
"""
import os

import numpy as np
import pandas as pd

INTER = r"D:\2607compound\results\intermediate"
PIPE = {
    "R严格": (os.path.join(INTER, "thw_events_R.csv"),
              os.path.join(INTER, "mhw_events_R_global.csv")),
    "Py跨度": (os.path.join(INTER, "thw_events.csv.bak"),
               os.path.join(INTER, "mhw_events_py.csv.bak")),
}
PAIRS = os.path.join(INTER, "coastal_pairs.csv")

NT = 14975                      # 1983-01-01 .. 2023-12-31
EPOCH = pd.Timestamp("1983-01-01")
# 每天所属年份:
_day_years = np.array([(EPOCH + pd.Timedelta(days=i)).year for i in range(NT)])

REGIONS = {"Med&BS": ((30, 47), (5, 42)), "Europe": ((30, 72), (-15, 45))}


def d2i(d):
    return (pd.Timestamp(d) - EPOCH).days


def daily_masks(events):
    """event spans -> boolean daily mask (length NT)。"""
    m = np.zeros(NT, dtype=bool)
    for s, e in events:
        i0, i1 = d2i(s), d2i(e)
        m[max(i0, 0):min(i1, NT - 1) + 1] = True
    return m


def year_sum(mask):
    out = {}
    for y in range(1983, 2024):
        idx = _day_years == y
        out[y] = int(mask[idx].sum())
    return out


def main():
    pairs = pd.read_csv(PAIRS)
    for tag, (thw_path, mhw_path) in PIPE.items():
        thw = pd.read_csv(thw_path)
        mhw = pd.read_csv(mhw_path)
        # 按 (lat,lon) 建事件字典
        tg = thw.groupby(["lat", "lon"])
        og = mhw.groupby(["lat", "lon"])
        print(f"\n{'=' * 74}\n{tag}: thw={len(thw):,} mhw={len(mhw):,}")
        rows = []
        for _, p in pairs.iterrows():
            try:
                t_ev = tg.get_group((p.land_lat, p.land_lon))[
                    ["event_start", "event_end"]].values.tolist()
                o_ev = og.get_group((p.ocean_lat, p.ocean_lon))[
                    ["event_start", "event_end"]].values.tolist()
            except KeyError:
                continue
            lm = daily_masks(t_ev)
            om = daily_masks(o_ev)
            coex = lm & om
            t_days = year_sum(lm)
            c_days = year_sum(coex)
            s_days = {y: t_days[y] - c_days[y] for y in t_days}
            rows.append({
                "lat": p.land_lat, "lon": p.land_lon,
                "ocean_lat": p.ocean_lat, "ocean_lon": p.ocean_lon,
                **{f"coex_{y}": c_days[y] for y in (1990, 1995, 2022, 2023)},
                "coex_80s90s": float(np.mean([c_days[y] for y in range(1983, 2000)])),
                "cooc_0323": (sum(c_days[y] for y in range(2003, 2024))
                              / max(sum(t_days[y] for y in range(2003, 2024)), 1)),
            })
        df = pd.DataFrame(rows)
        for rname, ((la0, la1), (lo0, lo1)) in REGIONS.items():
            r = df[(df.lat.between(la0, la1)) & (df.lon.between(lo0, lo1))]
            if len(r) == 0:
                continue
            print(f"  {rname}: n={len(r)} pairs")
            print(f"    coex/pair: 1990={r.coex_1990.mean():5.1f} 1995={r.coex_1995.mean():5.1f}"
                  f"  80s-90s均值={r.coex_80s90s.mean():5.1f}"
                  f"  2022={r.coex_2022.mean():5.1f}  2023={r.coex_2023.mean():5.1f}")
            a22 = r[r.coex_2022 > 0].coex_2022
            a23 = r[r.coex_2023 > 0].coex_2023
            print(f"    当年活跃点均值: 2022={a22.mean():5.1f} (活跃 {len(a22)}/{len(r)})"
                  f"  2023={a23.mean():5.1f} (活跃 {len(a23)}/{len(r)})"
                  f"   <- 论文 fig1j: 2022~78, 2023~72")
            print(f"    格点分位数 2022: p75={r.coex_2022.quantile(.75):5.1f}"
                  f" p90={r.coex_2022.quantile(.9):5.1f} max={r.coex_2022.max():5.1f}"
                  f" | 2023: p75={r.coex_2023.quantile(.75):5.1f}"
                  f" p90={r.coex_2023.quantile(.9):5.1f} max={r.coex_2023.max():5.1f}")
            print(f"    cooc 03-23: p50={r.cooc_0323.median():.3f} "
                  f"p90={r.cooc_0323.quantile(.9):.3f} max={r.cooc_0323.max():.3f}"
                  f"   <- 论文 fig1m: 地中海 0.6-0.8, 西地中海>0.8, 大西洋 0.2-0.4")
        # Europe 加权 CHR 序列 (C=coex days; S=THW days - coex days)
        r = df[(df.lat >= 30) & (df.lat <= 72) & (df.lon >= -15) & (df.lon <= 45)]
        w = np.cos(np.deg2rad(r.lat.values))
        C = {}; S = {}
        for wi, (_, p) in zip(w, r.iterrows()):
            try:
                t_ev = tg.get_group((p.lat, p.lon))[["event_start", "event_end"]].values.tolist()
                o_ev = og.get_group((p.ocean_lat, p.ocean_lon))[
                    ["event_start", "event_end"]].values.tolist()
            except KeyError:
                continue
            lm = daily_masks(t_ev); om = daily_masks(o_ev)
            ty = year_sum(lm); cy = year_sum(lm & om)
            for y in range(1983, 2024):
                C[y] = C.get(y, 0) + wi * cy[y]
                S[y] = S.get(y, 0) + wi * (ty[y] - cy[y])
        chr_ts = {y: C[y] / S[y] if S.get(y, 0) > 0 else np.nan for y in C}
        sel = {y: round(chr_ts.get(y, float('nan')), 2)
               for y in (1990, 1995, 2003, 2018, 2022, 2023)}
        print(f"    CHR(coex定义) 1990={sel[1990]} 1995={sel[1995]} 2003={sel[2003]}"
              f" 2018={sel[2018]} 2022={sel[2022]} 2023={sel[2023]}  (论文: 80s/90s~1, 2023~3.5)")


if __name__ == "__main__":
    main()
