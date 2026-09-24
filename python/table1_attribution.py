"""
table1_attribution.py — 论文 Table 1：三次事件阈值的 FAR / PR 汇总（5–95 % CI）

论文 Table 1 的三行（地中海 & 黑海，观测暴露天数 → CESM1-LE 归因）：

| 事件 | 阈值（复合热浪日） | FAR（5–95 % CI） | PR（5–95 % CI） |
|---|---|---|---|
| 2003 | 62 天 | 0.72 [0.64–0.80] | 4.1 [2.8–7.2] |
| 2022 | 78 天 | 0.95 [0.93–1.00] | [6–∞) |
| 2023 | 72 天 | 0.78 [0.70–0.88] | 8 [4–10] |

数据来源（二选一，优先 summary）
--------------------------------
1. `results/tables/phase6_attrib_summary{tag}.csv`（`phase6_cesm.py attrib` 直接产出）
2. 退而读 `results/tables/phase6_attrib_sweep{tag}_{agg}.csv` 并在 62/78/72 三点取样

⚠️ 只有 **20 成员 + `--loo`** 的全量结果才有判读意义；P0（3 成员）产物仅用于验证流程。
⚠️ `PR` 上界为 ∞ 时按论文写法输出 `inf`（反事实概率为 0，不是缺失）。

用法
----
    python python\\table1_attribution.py --tag _v4
    python python\\table1_attribution.py --tag _v4 --agg med_mean --out results/tables/table1.csv
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

PAPER = {  # 年 → (阈值, FAR, FAR_lo, FAR_hi, PR 文本)
    2003: (62.0, 0.72, 0.64, 0.80, "4.1 [2.8–7.2]"),
    2022: (78.0, 0.95, 0.93, 1.00, "[6–∞)"),
    2023: (72.0, 0.78, 0.70, 0.88, "8 [4–10]"),
}


def _fmt(v, nd=3):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "inf" if (isinstance(v, float) and np.isinf(v)) else ""
    return f"{v:.{nd}f}"


def main(argv=None):
    p = argparse.ArgumentParser(description="论文 Table 1：FAR/PR 汇总")
    p.add_argument("--tag", default="", help="phase6 产物后缀（如 _v4）")
    p.add_argument("--agg", default=C.MAIN_AGG, help=f"聚合列（默认 {C.MAIN_AGG}）")
    p.add_argument("--out", default=os.path.join(C.TABLES_DIR, "table1.csv"))
    args = p.parse_args(argv)

    rows = []
    summary = os.path.join(C.TABLES_DIR, f"phase6_attrib_summary{args.tag}.csv")
    if os.path.exists(summary):
        df = pd.read_csv(summary)
        print(f"读取 {summary}（{len(df)} 行）")
        if "agg" in df.columns:
            df = df[df["agg"].astype(str) == str(args.agg)]
        for year, (thr, *_rest) in PAPER.items():
            r = df[np.isclose(df["threshold"], thr)]
            if not len(r):
                print(f"  [warn] summary 里没有阈值 {thr:.0f} 天（{year}）")
                continue
            r = r.iloc[0]
            rows.append({"year": year, "threshold": thr, "agg": r.get("agg", args.agg),
                         "p_all": r.get("p_all"), "p_fix": r.get("p_fix"),
                         "FAR": r.get("FAR"), "FAR_lo": r.get("FAR_lo"),
                         "FAR_hi": r.get("FAR_hi"),
                         "PR": r.get("PR"), "PR_lo": r.get("PR_lo"),
                         "PR_hi": r.get("PR_hi"),
                         "n_inf": r.get("n_inf"), "boot": r.get("boot", C.BOOT_MODE)})
    else:
        sweep = os.path.join(C.TABLES_DIR, f"phase6_attrib_sweep{args.tag}_{args.agg}.csv")
        if not os.path.exists(sweep):
            raise SystemExit(
                f"找不到 {summary}\n  也找不到 {sweep}\n"
                f"  先跑：python python\\phase6_cesm.py attrib --members 20 --tag {args.tag} "
                f"--compound-def {C.COMPOUND_DEF}")
        tab = pd.read_csv(sweep)
        print(f"读取 {sweep}（{len(tab)} 个阈值）")
        for year, (thr, *_rest) in PAPER.items():
            r = tab[np.isclose(tab["threshold"], thr)]
            if not len(r):
                print(f"  [warn] 扫描里没有阈值 {thr:.0f} 天（{year}）")
                continue
            r = r.iloc[0]
            rows.append({"year": year, "threshold": thr, "agg": args.agg,
                         "p_all": r.get("p_all"), "p_fix": r.get("p_fix"),
                         "FAR": r.get("FAR"), "FAR_lo": r.get("FAR_lo"),
                         "FAR_hi": r.get("FAR_hi"), "PR": r.get("PR"),
                         "PR_lo": r.get("PR_lo"), "PR_hi": r.get("PR_hi"),
                         "n_inf": r.get("n_inf"), "boot": C.BOOT_MODE})

    out = pd.DataFrame(rows)
    if out.empty:
        raise SystemExit("没有取到任何一行；检查 tag / agg 是否匹配现有产物")

    # 与论文对照列
    out["paper_FAR"] = [PAPER[y][1] for y in out["year"]]
    out["paper_FAR_ci"] = [f"[{PAPER[y][2]:.2f}–{PAPER[y][3]:.2f}]" for y in out["year"]]
    out["paper_PR"] = [PAPER[y][4] for y in out["year"]]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"\n-> {args.out}\n")

    # 终端对照表
    print(f"{'年':<6}{'阈值':<7}{'FAR (5–95%)':<26}{'PR (5–95%)':<26}{'论文 FAR':<16}{'论文 PR'}")
    for _, r in out.iterrows():
        far = f"{_fmt(r.FAR)} [{_fmt(r.FAR_lo)}–{_fmt(r.FAR_hi)}]"
        pr = f"{_fmt(r.PR, 2)} [{_fmt(r.PR_lo, 2)}–{_fmt(r.PR_hi, 2)}]"
        pf = f"{r.paper_FAR:.2f} {r.paper_FAR_ci}"
        print(f"{int(r.year):<6}{r.threshold:<7.0f}{far:<26}{pr:<26}{pf:<16}{r.paper_PR}")
    print("\n⚠️ P0（3 成员）产物只用于验证流程；结论须用 20 成员 + --loo 的全量结果。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
