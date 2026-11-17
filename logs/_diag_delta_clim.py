# -*- coding: utf-8 -*-
"""只读诊断：1983–2012 与 2000–2021 两个窗口的 ALL−XGHG 气候态差（δ），
在 206 个配对点上、分 land(T2m) / ocean(SST)。用来把"共享基准偏移"折算成 Δ°C 的标尺。

用法: python logs\_diag_delta_clim.py [--members 5]
不写任何产物，只打印。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "python"))

import numpy as np
import pandas as pd

import phase6_cesm as P

MEMBERS = ["001", "005", "010", "015", "020"]


def window_mean(kind, exp, tag):
    vals = []
    for m in MEMBERS:
        try:
            arr, _t = P._load_stitched(kind, exp, m, PAIRS, tag)   # (nt, npair), time
        except Exception as exc:                                # noqa: BLE001
            print(f"!! {kind} {exp} {m} {tag}: {type(exc).__name__}: {exc}")
            continue
        finite = np.isfinite(arr)
        vals.append(np.nanmean(arr[finite]))
    return float(np.mean(vals)) if vals else float("nan")


PAIRS = pd.read_csv(P.PAIRS_CSV)
med = (PAIRS.land_lat.between(30, 47) & PAIRS.land_lon.between(5, 42)).values
ocean_pts = PAIRS[med].drop_duplicates(["ocean_lat_idx", "ocean_lon_idx"])

print(f"配对点 {len(PAIRS)}（其中地中海&黑海框 {int(med.sum())} 对，唯一海点 {len(ocean_pts)}）")
print(f"成员子集: {', '.join(MEMBERS)}")
print()
print(f"{'kind':<6}{'window':<12}{'ALL':>9}{'XGHG':>9}{'δ=ALL−XGHG':>13}")
print("-" * 52)
for kind in ("t2m", "sst"):
    for tag in ("1983-2012", "2000-2021"):
        a = window_mean(kind, "ALL", tag)
        b = window_mean(kind, "XGHG", tag)
        print(f"{kind:<6}{tag:<12}{a:9.3f}{b:9.3f}{a - b:13.3f}")
print()
print("判读：'1983-2012' 的 δ 就是 _v8（共用 ALL 基准）相对 _v7（各用各的）"
      "把 XGHG 世界的阈值抬高了多少 °C。")
