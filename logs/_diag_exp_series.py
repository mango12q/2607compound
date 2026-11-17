# -*- coding: utf-8 -*-
"""只读诊断：不同 tag 的图4 三类**区域年暴露序列**（440 模型年）统计对照。

不写任何产物，只打印。用法:
    python logs\_diag_exp_series.py _v7 _v8

目的：A′（`--baseline all`）跑完后，需要看清 XGHG 侧被打到什么程度
（均值/中位/分位/max/零年占比），以及 ALL 侧是否与 _v7 逐位相同。
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

PANELS = ("marine", "terrestrial", "compound")
MEMBERS = [f"{i:03d}" for i in range(1, 21)]


def collect(tag):
    pairs_df = pd.read_csv(P.PAIRS_CSV)
    med = (pairs_df.land_lat.between(30, 47) & pairs_df.land_lon.between(5, 42)).values
    out = {p: {"ALL": [], "XGHG": []} for p in PANELS}
    for exp in ("ALL", "XGHG"):
        for m in MEMBERS:
            try:
                r = P._member_exposure_series(exp, m, tag, pairs_df, med, verbose=False)
            except Exception as exc:                      # noqa: BLE001
                print(f"!! {tag} {exp} {m}: {type(exc).__name__}: {exc}")
                continue
            for p in PANELS:
                out[p][exp].append(np.asarray(r[p], dtype=float))
    return {p: {e: (np.mean(np.vstack(v), axis=0) if v else np.array([]))
                for e, v in d.items()} for p, d in out.items()}


def stats(a):
    if a.size == 0:
        return None
    return dict(mean=a.mean(), p50=np.percentile(a, 50), p90=np.percentile(a, 90),
                mx=a.max(), zero=100.0 * np.mean(a == 0.0))


def main(tags):
    for tag in tags:
        print("=" * 96)
        print(f"[{tag}] 图4 区域年暴露（64 对的地中海&黑海框；440 模型年）")
        ser = collect(tag)
        print(f"{'panel':<12}{'exp':<6}{'mean':>9}{'p50':>9}{'p90':>9}{'max':>9}{'零年%':>8}")
        for p in PANELS:
            for e in ("ALL", "XGHG"):
                s = stats(ser[p][e])
                if s is None:
                    print(f"{p:<12}{e:<6}{'--':>9}")
                    continue
                print(f"{p:<12}{e:<6}{s['mean']:9.2f}{s['p50']:9.2f}"
                      f"{s['p90']:9.2f}{s['mx']:9.1f}{s['zero']:8.1f}")
        for p in PANELS:
            a, b = stats(ser[p]["ALL"]), stats(ser[p]["XGHG"])
            if a and b and b["mean"] > 0:
                print(f"  → {p:<12} ALL/XGHG 均值比 = {a['mean'] / b['mean']:6.2f}×")
        # 供"ALL 侧是否与 _v7 逐位相同"的对照
        ser_all = {p: ser[p]["ALL"] for p in PANELS}
        np.savez(os.path.join(HERE, "logs", f"_exp_series{tag}.npz"),
                 **{f"{p}_ALL": v for p, v in ser_all.items()},
                 **{f"{p}_XGHG": ser[p]["XGHG"] for p in PANELS})
        print(f"  （序列已存 logs\\_exp_series{tag}.npz 便于跨 tag 逐位对比）")


if __name__ == "__main__":
    main(sys.argv[1:] or ["_v7", "_v8"])
