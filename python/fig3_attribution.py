"""
fig3_attribution.py — 论文图 3：复合海岸热浪暴露的 FAR / PR 阈值扫描曲线

面板（按 `pdf_extract/fig3_p05.png` 逐像素校准，2026-09-23 第四轮审查）
--------------------------------------------------------------------
a  FAR —— European coastlines      x: 0–105 线性；y: −0.05–1.05 线性
b  PR  —— European Coastlines      x: 0–105 线性；y: **1–1000 对数**
c  FAR —— Mediterranean & Black Sea x: **1–100** 线性；含 2003/2022/2023 三条竖线
d  PR  —— Mediterranean & Black Sea x: 1–100 线性；y: **1–100 对数**

样式：
  · 曲线纯蓝 `#0000FF`、实线、lw≈2.5，无 marker；
  · 不确定带同色、`alpha=0.40`、无描边；
  · 竖线仅在 c/d：2003 红 `#FF0000` @62 天、2022 绿 `#008000` @78 天、2023 黑 @72 天；
  · 图例置于坐标区**右侧外侧**；c/d 的图例为 5 项（FAR/PR、Uncertainty、2003、2022、2023）；
  · 4 边框线 + 主刻度浅灰网格（matplotlib 默认 #B0B0B0）；
  · PR 曲线超出上轴时**断开**（论文 b 在 x≈90.5、d 在 x≈81 处离开画面）。

输入契约（由 `python phase6_cesm.py attrib` 产出）
-------------------------------------------------
    results/tables/phase6_attrib_sweep{tag}_{agg}.csv
    列：threshold, p_all, p_fix, PR, PR_lo, PR_hi, FAR, FAR_lo, FAR_hi, n_inf, n_boot

区域 → 聚合列的默认映射（可用 CLI 覆盖）：
    European coastlines         : `eur_p90`（欧洲全岸 p90；旧 P0 产物里叫 `eur_mean/eur_max`）
    Mediterranean & Black Sea   : `med_mean`（D7.3 主口径）

用法
----
    python python/fig3_attribution.py --tag _v4
    python python/fig3_attribution.py --tag _x3 --agg-eur eur_max      # 旧 P0 产物兜底

⚠️ 论文 Table 1 的三个锚点（FAR 0.72 / 0.95 / 0.78）会在运行时打印对照，
   但**只有 20 成员 + `--loo` 的全量结果才有判读意义**（见 results/复现报告.md D7）。
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

COLOR_CURVE = "#0000FF"
REF_LINES = ((2003, 62.0, "#FF0000"), (2022, 78.0, "#008000"), (2023, 72.0, "#000000"))


def _load_sweep(tag: str, agg: str) -> pd.DataFrame:
    for cand in (agg,):
        path = os.path.join(C.TABLES_DIR, f"phase6_attrib_sweep{tag}_{cand}.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            print(f"  读取 {path}（{len(df)} 个阈值）")
            return df
    avail = sorted(f for f in os.listdir(C.TABLES_DIR)
                   if f.startswith(f"phase6_attrib_sweep{tag}_")) if os.path.isdir(C.TABLES_DIR) else []
    raise SystemExit(
        f"找不到聚合列 {agg!r} 的扫描结果（tag={tag!r}）。\n"
        f"  期望文件：{os.path.join(C.TABLES_DIR, f'phase6_attrib_sweep{tag}_{agg}.csv')}\n"
        f"  该 tag 下现有：{avail or '（无）'}\n"
        f"  先跑：python python\\phase6_cesm.py attrib --members 20 --tag {tag} "
        f"--compound-def envelope")


def _plot_one(ax, df: pd.DataFrame, metric: str, *, logy: bool, xlim, show_refs: bool,
              ylim=None):
    x = df["threshold"].values.astype(float)
    y = df[metric].values.astype(float)
    lo = df.get(f"{metric}_lo")
    hi = df.get(f"{metric}_hi")
    lo = None if lo is None else lo.values.astype(float)
    hi = None if hi is None else hi.values.astype(float)

    top = None if ylim is None else ylim[1]
    if logy:
        y = np.where(np.isfinite(y) & (y > 0), y, np.nan)
        if top is not None:
            y = np.where(y >= top, np.nan, y)          # 超出上轴 → 断开（论文原图行为）
    if lo is not None:
        lo = np.where(np.isfinite(lo) & (lo > 0 if logy else True), lo, np.nan)
        hi = np.where(np.isfinite(hi) & (hi > 0 if logy else True), hi, np.nan)
        if top is not None:
            hi = np.minimum(hi, top)

    if lo is not None and hi is not None:
        ax.fill_between(x, lo, hi, color=COLOR_CURVE, alpha=0.40, lw=0,
                        label="Uncertainty")
    ax.plot(x, y, color=COLOR_CURVE, lw=2.5, label=metric)

    if show_refs:
        for year, thr, col in REF_LINES:
            ax.axvline(thr, color=col, ls="--", lw=2.0, dashes=(6, 4), label=str(year))

    ax.set_xlim(*xlim)
    ax.set_yscale("log") if logy else None
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.grid(True, which="major", color="#B0B0B0", lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(True)
        s.set_linewidth(0.9)


def make_figure(tag: str = "", agg_eur: str = "eur_p90", agg_med: str = "med_mean",
                outdir: str = None, dpi: int = 300) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir = outdir or C.FIGURES_DIR
    os.makedirs(outdir, exist_ok=True)

    print("[图3] 读取扫描结果 …")
    df_eur = _load_sweep(tag, agg_eur)
    df_med = _load_sweep(tag, agg_med)

    fig, axes = plt.subplots(2, 2, figsize=(9.6, 8.2))
    (a, b), (c, d) = axes

    # ── a / b：European coastlines ──────────────────────────────────────
    _plot_one(a, df_eur, "FAR", logy=False, xlim=(0, 105), show_refs=False,
              ylim=(-0.05, 1.05))
    a.set_title("European coastlines", fontsize=11)
    a.set_xlabel("Thresholds")
    a.set_ylabel("Fraction of Attributable Risk (FAR)")
    a.set_xticks([10, 20, 40, 60, 80, 100])
    a.set_yticks(np.arange(0, 1.01, 0.2))
    a.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9, framealpha=1.0)

    _plot_one(b, df_eur, "PR", logy=True, xlim=(0, 105), show_refs=False,
              ylim=(1, 1000))
    b.set_title("European Coastlines", fontsize=11)     # 论文原图就是大写 C（保留不一致）
    b.set_xlabel("Thresholds")
    b.set_ylabel("Probability Ratio (PR)")
    b.set_xticks([10, 20, 40, 60, 80, 100])
    b.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9, framealpha=1.0)

    # ── c / d：Mediterranean & Black Sea ────────────────────────────────
    _plot_one(c, df_med, "FAR", logy=False, xlim=(1, 100), show_refs=True,
              ylim=(-0.05, 1.05))
    c.set_title("Mediterranean & Black Sea", fontsize=11)
    c.set_xlabel("Thresholds\n(Compound heatwave days)")
    c.set_ylabel("Fraction of Attributable Risk (FAR)")
    c.set_xticks([10, 20, 40, 60, 80, 100])
    c.set_yticks(np.arange(0, 1.01, 0.2))
    c.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9, framealpha=1.0)

    _plot_one(d, df_med, "PR", logy=True, xlim=(1, 100), show_refs=True,
              ylim=(1, 100))
    d.set_title("Mediterranean & Black Sea", fontsize=11)
    d.set_xlabel("Thresholds\n(Compound heatwave days)")
    d.set_ylabel("Probability Ratio (PR)")
    d.set_xticks([10, 20, 40, 60, 80, 100])
    d.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9, framealpha=1.0)

    for ax, lab in zip((a, b, c, d), "abcd"):
        ax.text(0.02, 0.97, lab, transform=ax.transAxes, fontsize=12,
                fontweight="bold", va="top")

    # 论文原图无总标题；这里只放一条 ASCII 元信息，避免中文字形缺失告警
    fig.suptitle(f"CESM1-LE attribution (tag={tag or 'default'}) — "
                 f"europe: {agg_eur} / med: {agg_med}", fontsize=9, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    outs = []
    for ext in ("pdf", "png"):
        p = os.path.join(outdir, f"fig3_attribution{tag}.{ext}")
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        outs.append(p)
    plt.close(fig)
    for p in outs:
        print(f"  -> {p}")

    # ── 锚点对照（论文 Table 1 / 正文）──────────────────────────────────
    print("\n[图3] 论文锚点对照（Med & BS，5–95% CI）")
    paper = {62.0: ("2003", 0.72, (0.64, 0.80)), 78.0: ("2022", 0.95, (0.93, 1.00)),
             72.0: ("2023", 0.78, (0.70, 0.88))}
    for thr, (year, far_ref, far_ci) in paper.items():
        r = df_med[np.isclose(df_med.threshold, thr)]
        if len(r):
            r = r.iloc[0]
            print(f"  {year} @ {thr:.0f} 天：FAR = {r.FAR:.3f} "
                  f"[{r.FAR_lo:.3f}–{r.FAR_hi:.3f}]（论文 {far_ref:.2f} "
                  f"[{far_ci[0]:.2f}–{far_ci[1]:.2f}]）  PR = {r.PR:.2f} "
                  f"[{r.PR_lo:.2f}–{r.PR_hi:.2f}]")
        else:
            print(f"  {year} @ {thr:.0f} 天：该阈值不在扫描范围内")
    return outs[1]


def main(argv=None):
    p = argparse.ArgumentParser(description="论文图 3：FAR/PR 阈值扫描曲线")
    p.add_argument("--tag", default="", help="phase6 产物后缀（如 _v4）")
    p.add_argument("--agg-eur", default="eur_p90",
                   help="European coastlines 用的聚合列（旧 P0 产物可用 eur_mean/eur_max）")
    p.add_argument("--agg-med", default="med_mean",
                   help="Mediterranean & Black Sea 用的聚合列（D7.3 主口径 med_mean）")
    p.add_argument("--outdir", default=None)
    args = p.parse_args(argv)
    make_figure(tag=args.tag, agg_eur=args.agg_eur, agg_med=args.agg_med,
                outdir=args.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
