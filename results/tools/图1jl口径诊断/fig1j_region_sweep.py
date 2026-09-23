"""
fig1j_region_sweep.py — 用同一套 MHW 包络逻辑扫区域框，找能同时满足论文四条约束的口径

论文图1j 的四条约束：
  (1) 2022 ≈ 78 天   (2) 2023 = 72 天   (3) 峰值年在 2022
  (4) 1980s–90s 通常 < 20 天；全曲线 < 90
复用 python/fig_jkl_mhw_envelope.py 的 regional_envelope_series（不重算事件）。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "python")
from fig_jkl_mhw_envelope import regional_envelope_series, REGIONS  # noqa: E402
from config import INTERMEDIATE_DIR  # noqa: E402

pairs = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "coastal_pairs.csv"))
thw = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "thw_events_R.csv"))
mhw = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "mhw_events_R_global.csv"))
thw_g = {k: g[["event_start", "event_end"]].values.tolist()
         for k, g in thw.groupby(["lat", "lon"])}
mhw_g = {k: g[["event_start", "event_end"]].values.tolist()
         for k, g in mhw.groupby(["lat", "lon"])}

years = np.arange(1983, 2024)
PAPER = {2003: 62, 2022: 78, 2023: 72}

BOXES = [
    ("全盆地（现主图）", (30, 47), (5, 42)),
    ("西地中海",         (35, 45), (-2, 15)),
    ("西地中海弧 V1",    (36, 45), (0, 12)),
    ("西地中海弧 V2",    (36, 44), (-1, 10)),
    ("中西地中海",       (34, 45), (0, 18)),
    ("中地中海",         (33, 45), (10, 20)),
    ("东地中海",         (30, 42), (20, 36)),
    ("地中海（不含黑海）", (30, 46), (5, 30)),
]

print(f"{'区域框':<22} {'n':>4} {'2003':>7} {'2022':>7} {'2023':>7} "
      f"{'峰年':>6} {'80-90均值':>9} {'max':>7}  判定")
print("-" * 108)
rows = []
for name, (la0, la1), (lo0, lo1) in BOXES:
    ts, n = regional_envelope_series(thw_g, mhw_g, pairs, la0, la1, lo0, lo1)
    v03 = ts[years == 2003][0]
    v22 = ts[years == 2022][0]
    v23 = ts[years == 2023][0]
    pk = years[int(np.argmax(ts))]
    early = float(np.mean(ts[(years >= 1983) & (years <= 1999)]))
    mx = float(ts.max())
    ok = (abs(v22 - 78) / 78 < 0.10 and abs(v23 - 72) / 72 < 0.10
          and pk == 2022 and early < 20 and mx < 90)
    rows.append((name, n, v03, v22, v23, pk, early, mx, ok))
    print(f"{name:<22} {n:>4} {v03:>7.1f} {v22:>7.1f} {v23:>7.1f} "
          f"{pk:>6} {early:>9.1f} {mx:>7.1f}  {'✅ 全部满足' if ok else ''}")

print()
print("论文约束：2022≈78  2023=72  峰值年 2022  80s-90s<20  全曲线<90")
