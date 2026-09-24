"""
fig4_return_period.py — 论文图 4：海洋 / 陆地 / 复合热浪日的重现期位移

面板（按 `pdf_extract/fig4_p06.png` 逐像素校准，2026-09-23 第四轮审查）
--------------------------------------------------------------------
a  Coastal Marine Heatwave Days
b  Coastal Terrestrial Heatwave Days
c  Coastal Marine-Terrestrial Heatwave Days
   三面板均为 **1×3**；x 轴 = FixGHG 重现期，取 5/10/20/50/100 **等距分类刻度**
   （⚠️ 论文原图 **不是对数 x 轴**；TECHNICAL_SPEC_PHASE_B §B.4 写的 "双对数" 有误）；
   y 轴 = ALL 等效重现期，**对数**，上界 ≈1.2e2，下界 ≈ 0.8×最小印刷值
   （a ≈1.7、b ≈0.96、c ≈1.3 —— 即 1e0 在 a/c 里落到轴外）。

样式要点（全部来自原图像素测量）
  · 浅蓝柱 `#A8DDEF`，宽度 = 0.80 × 分类间距，无描边；
  · 绿色虚线 = **1:1 参考线**（不是第二条数据曲线），图例仅出现在 a 面板；
  · 误差棒：黑色细线 + 小帽，跨 2.5–97.5% CI；
  · **每根柱印两个数字 = CI 的上/下界**（柱高 = 中位数，本身不印）；
  · c 面板两条红竖线：50 年处文字在左、100 年处文字在右，标注形如 `Gap: -44.8`
    （负号是原图就有的；数值 = median(ALL) − FixGHG 重现期）；
  · 仅保留左/下轴脊 + 浅灰网格。

输入契约
--------
    results/tables/phase6_gev{tag}.json      （由 `python phase6_cesm.py gev` 产出）
    {
      "marine":     {"fixghg": {"5": {"median":..,"ci_lower":..,"ci_upper":..}, ...},
                     "all":    {...}, "gap": {...}},
      "terrestrial":{...},
      "compound":   {...},
      "_meta": {"tag": "...", "n_members": 20, "n_years": 440, "agg": "med_mean"}
    }

用法
----
    python python/fig4_return_period.py --tag _v4
    python python/fig4_return_period.py --demo      # 用论文锚点数渲染版式自检图
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C

BAR_COLOR = "#A8DDEF"
LINE_1TO1_COLOR = "green"
PANELS = (("marine", "Coastal\nMarine Heatwave Days"),
          ("terrestrial", "Coastal\nTerrestrial Heatwave Days"),
          ("compound", "Coastal Marine-Terrestrial\nHeatwave Days"))
RPS = tuple(float(x) for x in C.GEV_RETURN_PERIODS)

#: `--demo` 用的论文锚点（柱高 = 中位数；CI = 图中印刷的两个数字）
#: 来源：`pdf_extract/fig4_p06.png` 像素读数（±5%），见第四轮审查 §图4
DEMO = {
    "marine": {"median": [2.3, 3.8, 6.3, 13.4, 24.0],
               "lo": [2.1, 3.3, 5.5, 11.5, 20.7],
               "hi": [2.7, 4.5, 7.8, 17.3, 34.8]},
    "terrestrial": {"median": [1.26, 1.46, 1.75, 2.44, 3.26],
                    "lo": [1.2, 1.3, 1.6, 2.1, 2.8],
                    "hi": [1.3, 1.5, 1.9, 2.8, 3.8]},
    "compound": {"median": [1.96, 2.56, 3.50, 5.14, 7.85],
                 "lo": [1.6, 2.0, 2.6, 3.5, 5.0],
                 "hi": [2.4, 3.3, 4.8, 7.4, 12.1]},
}


def _load(tag: str) -> dict:
    path = os.path.join(C.TABLES_DIR, f"phase6_gev{tag}.json")
    if not os.path.exists(path):
        raise SystemExit(
            f"找不到 {path}\n"
            f"  先跑：python python\\phase6_cesm.py gev --members 20 --tag {tag}\n"
            f"  （或先用 `--demo` 渲染论文锚点版式自检图）")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _as_arrays(blk: dict):
    med = np.array([blk["fixghg"][f"{rp:g}"]["median"] for rp in RPS], dtype=float)
    allm = np.array([blk["all"][f"{rp:g}"]["median"] for rp in RPS], dtype=float)
    lo = np.array([blk["all"][f"{rp:g}"]["ci_lower"] for rp in RPS], dtype=float)
    hi = np.array([blk["all"][f"{rp:g}"]["ci_upper"] for rp in RPS], dtype=float)
    # 论文把轴下限设在 0.8 × 最小印刷（CI 下界）值处
    finite_lo = lo[np.isfinite(lo)]
    ymin = 0.8 * finite_lo.min() if finite_lo.size else 0.8
    ymax = 1.2e2
    med = np.clip(med, ymin, ymax)
    lo = np.clip(lo, ymin, ymax)
    hi = np.clip(hi, ymin, ymax)
    return med, allm, lo, hi, ymin, ymax


def make_figure(tag: str = "", demo: bool = False, outdir: str = None,
                dpi: int = 300) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = DEMO if demo else _load(tag)
    outdir = outdir or C.FIGURES_DIR
    os.makedirs(outdir, exist_ok=True)

    x = np.arange(len(RPS))
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))
    for ax, (key, title) in zip(axes, PANELS):
        if demo:
            med = np.array(data[key]["median"])
            lo = np.array(data[key]["lo"])
            hi = np.array(data[key]["hi"])
            finite_lo = lo[np.isfinite(lo)]
            ymin = 0.8 * finite_lo.min()
            ymax = 1.2e2
            med, lo, hi = (np.clip(v, ymin, ymax) for v in (med, lo, hi))
        else:
            med, allm, lo, hi, ymin, ymax = _as_arrays(data[key])

        ax.bar(x, med, width=0.80, color=BAR_COLOR, edgecolor="none",
               label="Return Period\nin ALL", zorder=2)
        ax.errorbar(x, med, yerr=[med - lo, hi - med], fmt="none",
                    ecolor="black", elinewidth=0.9, capsize=3, capthick=0.9,
                    zorder=3)
        ax.plot(x, RPS, ls="--", color=LINE_1TO1_COLOR, lw=1.8,
                label="Return Period\nin FixGHG", zorder=4)   # 1:1 参考线

        # 每根柱印 CI 上/下界（柱高本身不印 —— 论文原图如此）
        for xi, (l, h) in enumerate(zip(lo, hi)):
            ax.text(xi, h * 1.05, f"{h:.1f}", ha="center", va="bottom", fontsize=8)
            ax.text(xi, l * 0.95, f"{l:.1f}", ha="center", va="top", fontsize=8,
                    color="white" if l < med[xi] else "black")

        # c 面板的 Gap 标注
        if key == "compound":
            for rp, side in ((50.0, "left"), (100.0, "right")):
                i = list(RPS).index(rp)
                gap = med[i] - rp                     # 负号（ALL 比 FixGHG 短）
                ax.plot([i, i], [med[i], rp], color="red", lw=1.6, zorder=5)
                ax.annotate(f"Gap: {gap:.1f}", xy=(i, np.sqrt(med[i] * rp)),
                            xytext=(-8 if side == "left" else 8, 0),
                            textcoords="offset points", color="red", fontsize=9,
                            ha="right" if side == "left" else "left", va="center",
                            zorder=6)

        ax.set_yscale("log")
        ax.set_ylim(ymin, ymax)
        ax.set_xlim(-0.6, len(RPS) - 0.4)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{rp:g}" for rp in RPS])
        ax.set_xlabel("Return Period in FixGHG forcing")
        ax.set_title(title, fontsize=10)
        ax.grid(True, which="major", color="#B0B0B0", lw=0.6, alpha=0.7)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.text(-0.02, 1.06, f"({ 'abc'[PANELS.index((key, title))] })",
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                va="bottom", ha="left")

    axes[0].set_ylabel("Return Period in ALL forcing")
    axes[0].legend(loc="upper left", fontsize=8, framealpha=1.0)

    meta = ({} if demo else data.get("_meta", {}))
    subtitle = ("DEMO — paper anchors (pdf_extract/fig4_p06.png pixel read-out)"
                if demo else
                f"CESM1-LE — {meta.get('n_members', '?')} members, "
                f"{meta.get('n_years', '?')} model-years, agg={meta.get('agg', '?')}, "
                f"tag={tag or 'default'}")
    fig.suptitle(f"Return periods — {subtitle}", fontsize=9, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    outs = []
    suffix = "_demo" if demo else tag
    for ext in ("pdf", "png"):
        p = os.path.join(outdir, f"fig4_return_period{suffix}.{ext}")
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        outs.append(p)
    plt.close(fig)
    for p in outs:
        print(f"  -> {p}")
    return outs[1]


def main(argv=None):
    p = argparse.ArgumentParser(description="论文图 4：重现期位移（海洋/陆地/复合）")
    p.add_argument("--tag", default="", help="phase6 产物后缀（如 _v4）")
    p.add_argument("--demo", action="store_true",
                   help="用论文锚点数字渲染版式自检图（不读 phase6 产物）")
    p.add_argument("--outdir", default=None)
    args = p.parse_args(argv)
    make_figure(tag=args.tag, demo=args.demo, outdir=args.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
