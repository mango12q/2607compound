# -*- coding: utf-8 -*-
"""只读对照：已有四套口径的图4 (ALL 等效重现期) vs 论文像素锚点。

不改任何产物；只打印表。用法: python logs\_cmp_gev_tags.py
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TAB = r"D:\2607compound\results\tables"
RPS = ["5", "10", "20", "50", "100"]

# 论文 Fig4 像素读数中位数（python/fig4_return_period.py:61-71 DEMO）
PAPER = {
    "marine": [2.3, 3.8, 6.3, 13.4, 24.0],
    "terrestrial": [1.26, 1.46, 1.75, 2.44, 3.26],
    "compound": [1.96, 2.56, 3.50, 5.14, 7.85],
}
TAGS = ["_v5", "_v6", "_v7", "_v7e", "_v8", "_v8e", "_v9o40", "_v9o70", "_v10"]


def load(tag):
    p = os.path.join(TAB, f"phase6_gev{tag}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def table1_rows():
    """顺带打印各 tag 的 Table 1（若 results\\tables\\table1{tag}.csv 存在）。"""
    import csv
    rows = []
    for t in TAGS:
        p = os.path.join(TAB, f"table1{t}.csv")
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rows.append((t, r))
    if not rows:
        return
    print("=" * 78)
    print("Table 1（med_mean，62/78/72 天）—— 论文 FAR 0.72 / 0.95 / 0.78")
    print("-" * 78)
    print(f"{'tag':<10}{'year':<6}{'P_ALL':>8}{'P_fix':>8}{'FAR':>8}{'PR':>10}")
    for t, r in rows:
        try:
            pr = float(r["PR"]) if r["PR"] not in ("inf", "") else float("inf")
        except ValueError:
            pr = float("nan")
        print(f"{t:<10}{r['year']:<6}{float(r['p_all']):8.4f}{float(r['p_fix']):8.4f}"
              f"{float(r['FAR']):8.3f}{(f'{pr:10.2f}' if pr == pr and pr != float('inf') else '       inf')}")
    print()


def fmt(x):
    if x is None:
        return "   --  "
    if x != x or x == float("inf"):
        return "   inf "
    if x >= 1000:
        return f"{x:6.0f}"
    if x >= 100:
        return f"{x:6.1f}"
    return f"{x:6.2f}"


def main():
    data = {t: load(t) for t in TAGS}
    have = [t for t in TAGS if data[t]]
    print("已有 GEV 产物:", ", ".join(have))
    print()
    hdr = "panel        source      " + " ".join(f"{r+'-yr':>7}" for r in RPS)
    for panel in ("marine", "terrestrial", "compound"):
        print("=" * len(hdr))
        print(f"【{panel}】  (值 = FixGHG 该重现水平映射到 ALL 后的等效重现期, 年)")
        print(hdr)
        print("-" * len(hdr))
        print(f"{'':12} {'论文':<11}" + " ".join(fmt(v) for v in PAPER[panel]))
        for t in have:
            rec = data[t].get(panel) or {}
            allv = rec.get("all") or {}
            vals = [((allv.get(r) or {}).get("median")) for r in RPS]
            rat = ""
            m100 = vals[-1]
            if m100 is not None and m100 == m100 and m100 != float("inf") and m100 > 0:
                rat = f"   x{m100 / PAPER[panel][-1]:5.2f} (100y)"
            elif m100 == float("inf"):
                rat = "   x  inf (100y)"
            print(f"{'':12} {t:<11}" + " ".join(fmt(v) for v in vals) + rat)
        print()

    # FixGHG 侧的百年水平（诊断用：说明差距在 ALL 侧还是 FixGHG 侧）
    print("=" * 78)
    print("FixGHG 100 年重现水平（天/年，区域均值）—— 看两版基准期改造有没有动 XGHG 侧")
    print("-" * 78)
    for panel in ("marine", "terrestrial", "compound"):
        row = []
        for t in have:
            rec = data[t].get(panel) or {}
            lv = ((rec.get("fixghg") or {}).get("100") or {}).get("median")
            row.append(f"{t}={fmt(lv).strip()}")
        print(f"{panel:<12} " + "  ".join(row))
    print()
    table1_rows()


if __name__ == "__main__":
    main()
