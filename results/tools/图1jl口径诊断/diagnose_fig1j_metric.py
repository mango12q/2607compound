"""diagnose_fig1j_metric.py — 检验图1 j/l 的"复合天数"到底按哪侧计。

候选口径（同一套 R 严格事件）:
  V1 包络=containment: MHW **完全涵盖** >=1 个 THW -> 计该 MHW 全部跨度天
  V2 包络=overlap:     MHW 与 >=1 个 THW **有重叠**   -> 计该 MHW 全部跨度天
  V3 THW侧 containment: THW 被完全涵盖 -> 计 THW 跨度天 (旧实现, 已知 14/28)
  V4 逐日共超标:        陆THW日 ∩ 海MHW日 (当前实现, 已知 20.7/37.7)

论文锚点: Med 80s/90s <20, 62+ 近年峰值, 2022~78, 2023~72; Europe 2022~77;
用户目视: 论文曲线不超过 ~90 天。
"""
import os

import numpy as np
import pandas as pd

INTER = r"D:\2607compound\results\intermediate"
PAIRS = os.path.join(INTER, "coastal_pairs.csv")
PIPES = {
    "R严格": (os.path.join(INTER, "thw_events_R.csv"),
              os.path.join(INTER, "mhw_events_R_global.csv")),
}
NT = 14975
EPOCH = pd.Timestamp("1983-01-01")
_day_years = np.array([(EPOCH + pd.Timedelta(days=i)).year for i in range(NT)])
REGIONS = {"Med&BS": ((30, 47), (5, 42)), "Europe": ((30, 72), (-15, 45))}


def d2i(d):
    return (pd.Timestamp(d) - EPOCH).days


def spans_to_day_years(s, e):
    """事件跨度 -> 该事件每一天的年份列表。"""
    i0, i1 = max(d2i(s), 0), min(d2i(e), NT - 1)
    return _day_years[i0:i1 + 1]


def main():
    pairs = pd.read_csv(PAIRS)
    for tag, (thw_path, mhw_path) in PIPES.items():
        thw = pd.read_csv(thw_path)
        mhw = pd.read_csv(mhw_path)
        tg = {k: g[["event_start", "event_end"]].values.tolist()
              for k, g in thw.groupby(["lat", "lon"])}
        og = {k: g[["event_start", "event_end"]].values.tolist()
              for k, g in mhw.groupby(["lat", "lon"])}
        print(f"\n===== {tag} =====")
        for rname, ((la0, la1), (lo0, lo1)) in REGIONS.items():
            acc = {v: {} for v in ("V1", "V2")}
            wsum = {}
            n = 0
            for _, p in pairs.iterrows():
                if not (la0 <= p.land_lat <= la1 and lo0 <= p.land_lon <= lo1):
                    continue
                t_ev = tg.get((p.land_lat, p.land_lon), [])
                o_ev = og.get((p.ocean_lat, p.ocean_lon), [])
                if not o_ev:
                    continue
                n += 1
                wi = np.cos(np.deg2rad(p.land_lat))
                t_iv = [(d2i(s), d2i(e)) for s, e in t_ev]
                for ms, me in o_ev:
                    mi0, mi1 = d2i(ms), d2i(me)
                    if not t_iv:
                        continue
                    contained = any(a >= mi0 and b <= mi1 for a, b in t_iv)
                    overlap = any(not (b < mi0 or a > mi1) for a, b in t_iv)
                    if not (contained or overlap):
                        continue
                    dys = spans_to_day_years(ms, me)
                    for v, flag in (("V1", contained), ("V2", overlap)):
                        if not flag:
                            continue
                        d = acc[v]
                        for y in dys:
                            d[y] = d.get(y, 0) + wi
            print(f"  {rname} (n={n} pairs, cos加权均值):")
            sel = [1990, 1995, 2003, 2018, 2022, 2023]
            for v in ("V1", "V2"):
                d = acc[v]
                w8090 = np.mean([d.get(y, 0) for y in range(1983, 2000)]) / max(n, 1)
                row = "  ".join(f"{y}={d.get(y, 0) / max(n, 1):5.1f}" for y in sel)
                print(f"    {v}: {row}  80s90s={w8090:5.2f}")
        print("  论文: Med 80s/90s<20 | 2022~78 | 2023~72 | Europe 2022~77 | 曲线<90")


if __name__ == "__main__":
    main()
