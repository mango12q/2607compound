"""fig_jkl_mhw_envelope.py — 图1 j/k/l 的第三候选: MHW 包络天数 (V1)。

定义: 陆地配对格点上, 某个 MHW **完全涵盖** >=1 个 THW 事件 ->
      该 MHW 的全部跨度天计为"复合天"(复合事件以海洋热浪为包络)。
依据: 论文 L520 "a day when a marine heatwave fully encompasses a terrestrial
      heatwave" 的主语是 MHW; 且 78 天的区域均值只有 MHW 侧计数才可能达到
      (THW 子集天数的区域均值受 90 分位上限 ~65 天约束)。

输出: results/figures/figS2_jkl_mhw_envelope.pdf|png + tables/fig_jkl_envelope.json
"""
import json
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import INTERMEDIATE_DIR, FIGURES_DIR, TABLES_DIR

NT = 14975
EPOCH = pd.Timestamp("1983-01-01")
_day_years = np.array([(EPOCH + pd.Timedelta(days=i)).year for i in range(NT)])

REGIONS = [
    ("j", "Mediterranean & Black Sea", (30, 47), (5, 42)),
    ("k", "Baltic Sea", (53, 66), (10, 30)),
    ("l", "European Coasts", (30, 72), (-15, 45)),
]


def d2i(d):
    return (pd.Timestamp(d) - EPOCH).days


def regional_envelope_series(thw_g, mhw_g, pairs, la0, la1, lo0, lo1):
    acc = np.zeros(41)
    wtot = 0.0
    n = 0
    for _, p in pairs.iterrows():
        if not (la0 <= p.land_lat <= la1 and lo0 <= p.land_lon <= lo1):
            continue
        g = thw_g.get((p.land_lat, p.land_lon))
        o = mhw_g.get((p.ocean_lat, p.ocean_lon))
        if not o:
            continue
        n += 1
        wi = float(np.cos(np.deg2rad(p.land_lat)))
        wtot += wi
        t_iv = [(d2i(s), d2i(e)) for s, e in (g if g is not None else [])]
        for ms, me in o:
            mi0, mi1 = d2i(ms), d2i(me)
            if not t_iv:
                continue
            if any(a >= mi0 and b <= mi1 for a, b in t_iv):
                acc += wi * (_day_years[max(mi0, 0):min(mi1, NT - 1) + 1]
                             == np.arange(1983, 2024)[:, None]).sum(axis=1)
    return acc / max(wtot, 1e-9), n


def main():
    pairs = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "coastal_pairs.csv"))
    thw = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "thw_events_R.csv"))
    mhw = pd.read_csv(os.path.join(INTERMEDIATE_DIR, "mhw_events_R_global.csv"))
    thw_g = {k: g[["event_start", "event_end"]].values.tolist()
             for k, g in thw.groupby(["lat", "lon"])}
    mhw_g = {k: g[["event_start", "event_end"]].values.tolist()
             for k, g in mhw.groupby(["lat", "lon"])}

    years = np.arange(1983, 2024)
    out = {}
    fig, axes = plt.subplots(3, 1, figsize=(6, 9), sharex=True)
    for ax, (lbl, name, (la0, la1), (lo0, lo1)) in zip(axes, REGIONS):
        ts, n = regional_envelope_series(thw_g, mhw_g, pairs, la0, la1, lo0, lo1)
        out[f"fig1{lbl}_{name.split()[0].lower()}"] = {
            "years": [int(y) for y in years],
            "values": [round(float(v), 2) for v in ts],
            "n_pairs": n,
        }
        ax.fill_between(years, 0, ts, color="#d73027", alpha=0.6, step="mid")
        ax.plot(years, ts, color="#d73027", linewidth=0.8, marker=".", markersize=2)
        pk = years[int(np.argmax(ts))]
        ax.set_title(f"({lbl}) {name} — MHW-envelope days "
                     f"(peak {float(ts.max()):.1f} in {pk}, n={n})",
                     fontsize=9, fontweight="bold")
        ax.set_ylabel("Days/year", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3, linestyle=":", linewidth=0.3)
        print(f"({lbl}) {name}: 1990={ts[years == 1990][0]:.1f} "
              f"2003={ts[years == 2003][0]:.1f} 2018={ts[years == 2018][0]:.1f} "
              f"2022={ts[years == 2022][0]:.1f} 2023={ts[years == 2023][0]:.1f} "
              f"peak={float(ts.max()):.1f} ({pk})")
    axes[-1].set_xlim(1983, 2023)
    axes[-1].set_xticks(range(1983, 2024, 5))
    fig.suptitle("Fig.1 j-l candidate 3: MHW-envelope compound days\n"
                 "(paper text: Med 2022~78 / 2023~72 / <20 in 80s-90s / <90)",
                 fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.94])

    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(TABLES_DIR, exist_ok=True)
    path = os.path.join(FIGURES_DIR, "figS2_jkl_mhw_envelope.pdf")
    tmp = os.path.join(tempfile.gettempdir(), "figS2_temp.pdf")
    fig.savefig(tmp, dpi=300, bbox_inches="tight")
    tmp_png = os.path.join(tempfile.gettempdir(), "figS2_temp.png")
    fig.savefig(tmp_png, dpi=200, bbox_inches="tight")
    plt.close(fig)
    shutil.copy2(tmp, path)
    os.remove(tmp)
    shutil.copy2(tmp_png, os.path.join(FIGURES_DIR, "figS2_jkl_mhw_envelope.png"))
    os.remove(tmp_png)
    with open(os.path.join(TABLES_DIR, "fig_jkl_envelope.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"Saved: {path}")


if __name__ == "__main__":
    main()
