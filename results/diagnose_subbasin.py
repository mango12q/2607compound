"""diagnose_subbasin.py — 检验"论文 78 天 = 西地中海子盆地均值"假设。

对 R 严格事件, 分别按 逐日共超标(V4) 与 MHW包络(V1) 计,
分盆地统计 2022/2023 的 cos 加权均值 (over pairs)。
"""
import os

import numpy as np
import pandas as pd

INTER = r"D:\2607compound\results\intermediate"
PAIRS = os.path.join(INTER, "coastal_pairs.csv")
NT = 14975
EPOCH = pd.Timestamp("1983-01-01")
_day_years = np.array([(EPOCH + pd.Timedelta(days=i)).year for i in range(NT)])

BOXES = {
    "西地中海(30-45N,-5-15E)": ((30, 45), (-5, 15)),
    "中地中海(30-45N,15-25E)": ((30, 45), (15, 25)),
    "东地中海(30-45N,25-42E)": ((30, 45), (25, 42)),
    "黑海(40-47N,27-42E)": ((40, 47), (27, 42)),
    "全Med&BS": ((30, 47), (5, 42)),
}


def d2i(d):
    return (pd.Timestamp(d) - EPOCH).days


def main():
    pairs = pd.read_csv(PAIRS)
    thw = pd.read_csv(os.path.join(INTER, "thw_events_R.csv"))
    mhw = pd.read_csv(os.path.join(INTER, "mhw_events_R_global.csv"))
    tg = {k: g[["event_start", "event_end"]].values.tolist()
          for k, g in thw.groupby(["lat", "lon"])}
    og = {k: g[["event_start", "event_end"]].values.tolist()
          for k, g in mhw.groupby(["lat", "lon"])}

    for bname, ((la0, la1), (lo0, lo1)) in BOXES.items():
        acc = {"V4": {}, "V1": {}}
        n = 0
        for _, p in pairs.iterrows():
            if not (la0 <= p.land_lat <= la1 and lo0 <= p.land_lon <= lo1):
                continue
            t_ev = tg.get((p.land_lat, p.land_lon), [])
            o_ev = og.get((p.ocean_lat, p.ocean_lon), [])
            n += 1
            wi = np.cos(np.deg2rad(p.land_lat))
            # V4: 逐日共超标
            lm = np.zeros(NT, dtype=bool)
            om = np.zeros(NT, dtype=bool)
            for s, e in t_ev:
                lm[max(d2i(s), 0):min(d2i(e), NT - 1) + 1] = True
            for s, e in o_ev:
                om[max(d2i(s), 0):min(d2i(e), NT - 1) + 1] = True
            coex = lm & om
            for y in (2022, 2023):
                cnt = int(coex[_day_years == y].sum())
                acc["V4"][y] = acc["V4"].get(y, 0) + wi * cnt
            # V1: MHW 包络 (含 >=1 THW)
            t_iv = [(d2i(s), d2i(e)) for s, e in t_ev]
            for ms, me in o_ev:
                mi0, mi1 = d2i(ms), d2i(me)
                if any(a >= mi0 and b <= mi1 for a, b in t_iv):
                    for y in (2022, 2023):
                        days = int((_day_years[max(mi0, 0):min(mi1, NT - 1) + 1] == y).sum())
                        acc["V1"][y] = acc["V1"].get(y, 0) + wi * days
        line = f"{bname} (n={n}): "
        for v in ("V4", "V1"):
            d = acc[v]
            line += f"  {v} 2022={d.get(2022, 0) / max(n, 1):5.1f} 2023={d.get(2023, 0) / max(n, 1):5.1f}"
        print(line)
    print("论文(正文引述): 2022~78, 2023~72, 近年峰值>62, 曲线<90")


if __name__ == "__main__":
    main()
