# -*- coding: utf-8 -*-
"""只读诊断（N=440 版）：图4 的重现期映射坏在"GEV 外推"还是"数据本身"。

A（现口径）= FixGHG 的 GEV 1000×bootstrap 重现水平 → 塞进 ALL 的 **GEV** 反算 RP
B（零假设检验）= FixGHG 的**经验分位**(80/90/95/98/99) → 塞进 ALL 的**经验 CDF**
B 完全不含尾部外推。B 明显更平、更接近论文 ⇒ 元凶是 GEV 形状参数（区间宽、外推病态）；
B 也差 ⇒ 暴露序列的年际分布本身与论文不同，换估计器无用。

用法: python logs\_diag_emp_rp.py _v7 [_v9o40 ...]
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "python"))

import numpy as np
import pandas as pd

import phase6_cesm as P

PAPER = {
    "marine": [2.30, 3.80, 6.30, 13.4, 24.0],
    "terrestrial": [1.26, 1.46, 1.75, 2.44, 3.26],
    "compound": [1.96, 2.56, 3.50, 5.14, 7.85],
}
QS = [80, 90, 95, 98, 99]
RPS = ["5", "10", "20", "50", "100"]
PANELS = ("marine", "terrestrial", "compound")
MEMBERS = [f"{i:03d}" for i in range(1, 21)]


def collect(tag, pairs_df, med):
    """每个 panel/exp 的 440 个模型年暴露值（20 成员 × 22 年）。"""
    out = {p: {"ALL": [], "XGHG": []} for p in PANELS}
    for exp in ("ALL", "XGHG"):
        for m in MEMBERS:
            try:
                r = P._member_exposure_series(exp, m, tag, pairs_df, med, verbose=False)
            except Exception as exc:                       # noqa: BLE001
                print(f"!! {tag} {exp} {m}: {type(exc).__name__}: {exc}")
                continue
            for p in PANELS:
                out[p][exp].extend(np.asarray(r[p], dtype=float).tolist())
    return {p: {e: np.asarray(v, dtype=float) for e, v in d.items()} for p, d in out.items()}


def fmt(x):
    if x is None or x != x:
        return "    -- "
    if x == float("inf"):
        return "   inf "
    return f"{x:6.2f}" if x < 1000 else f"{x:6.0f}"


def main(tags):
    pairs_df = pd.read_csv(P.PAIRS_CSV)
    med = (pairs_df.land_lat.between(30, 47) & pairs_df.land_lon.between(5, 42)).values
    for tag in tags:
        ser = collect(tag, pairs_df, med)
        gev_p = os.path.join(HERE, "results", "tables", f"phase6_gev{tag}.json")
        gev = json.load(open(gev_p, encoding="utf-8")) if os.path.exists(gev_p) else None
        print("=" * 84)
        print(f"[{tag}]  A=GEV 外推法  B=经验法（FixGHG 经验分位 → ALL 经验 CDF）")
        hdr = f"{'panel':<13}{'meth':<6}" + " ".join(f"{r+'-yr':>7}" for r in RPS)
        print(hdr)
        print("-" * len(hdr))
        for p in PANELS:
            a, f = ser[p]["ALL"], ser[p]["XGHG"]
            if gev and p in gev and gev[p]:
                g = [((gev[p]["all"].get(r) or {}).get("median")) for r in RPS]
                print(f"{p:<13}{'A':<6}" + " ".join(fmt(v) for v in g))
            lv = np.percentile(f, QS)
            b = []
            for x in lv:
                frac = float(np.mean(a > x))
                b.append(float("inf") if frac <= 0 else 1.0 / frac)
            print(f"{'':<13}{'B':<6}" + " ".join(fmt(v) for v in b))
            print(f"{'':<13}{'论文':<6}" + " ".join(fmt(v) for v in PAPER[p])
                  + f"   N={a.size}/{f.size} fix_max={f.max():.1f} all_max={a.max():.1f}"
                  + f" fix_p99={lv[-1]:.1f}")
        print()


if __name__ == "__main__":
    main(sys.argv[1:] or ["_v7"])
