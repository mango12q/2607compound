"""
只读诊断（不产生任何 _v8 产物）：暴露量纲 days vs events 对 Fig4 a/b 的影响。

问题：图4 的重现期映射是
    L = GEV_100y(FixGHG 年暴露)      # 参数外推
    RP_ALL = 1 / (1 - F_ALL_gev(L))  # ALL 的 GEV CDF 在该水平处的尾部概率
线性换尺度（days → days/365）对两步都是等变的 ⇒ RP 完全不变（诊断里逐位验证）。
非线性/离散换尺度（days → 事件数/年）会改变 GEV 形状 ⇒ 才可能移动 RP。

用法: python logs/_diag_v8_metric.py [--tag _v7] [--n-boot 1000]
产物: logs\_diag_v8_metric.log（stdout 重定向）+ logs\_diag_v8_series.npz（缓存）
"""
import io
import os
import sys
import json
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import numpy as np
import pandas as pd
import xarray as xr

import config as C
import phase6_cesm as P
from gev_return_period import analyse_return_periods, fit_gev

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(HERE, "logs", "_diag_v8_series.npz")


def event_counts_per_year(events, keys, years_axis, nt, t0):
    """{key: 事件起始日在各年的事件数} -> (n_year, n_key) 矩阵（按 event_start 归年）。"""
    uyears = np.unique(years_axis)
    ycount = {int(y): np.zeros(len(keys), dtype=np.int16) for y in uyears}
    kpos = {k: i for i, k in enumerate(keys)}
    if len(events) == 0:
        return np.stack([ycount[int(y)] for y in uyears])
    sub = events.copy()
    sub["_y"] = pd.to_datetime(sub["event_start"]).dt.year.values
    for (k0, k1), g in sub.groupby(["lat_idx", "lon_idx"]):
        j = kpos.get((int(k0), int(k1)))
        if j is None:
            continue
        for y, n in g["_y"].value_counts().items():
            if int(y) in ycount:
                ycount[int(y)][j] += int(n)
    return np.stack([ycount[int(y)] for y in uyears])


def daily_counts_per_year(events, keys, years_axis, nt, t0):
    """用与主链完全一致的掩码实现算日数（交叉校验 _member_exposure_series）。"""
    masks = P._event_masks_by_key(events, set(keys), nt, t0)
    return P._annual_exposure_from_masks(masks, keys, years_axis)[0]


def boot_map(a, f, n_boot, ci):
    """与 cmd_gev 完全相同的调用，只取 5 个 RP 的中位数。"""
    res = analyse_return_periods(np.asarray(a, float), np.asarray(f, float),
                                 n_bootstrap=n_boot, rps=C.GEV_RETURN_PERIODS, ci=ci)
    out = {}
    for rp in C.GEV_RETURN_PERIODS:
        rpv = float(rp)
        out[rpv] = (res["fixghg"]["rp"][rpv]["median"], res["all"][rpv]["median"])
    return out, res


def describe(name, v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    return (f"{name}: mean={v.mean():7.2f} p50={np.median(v):7.2f} "
            f"p90={np.percentile(v, 90):7.2f} p95={np.percentile(v, 95):7.2f} "
            f"max={v.max():7.2f} N={v.size}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="_v7")
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--rebuild", action="store_true", help="忽略 npz 缓存重建序列")
    args = ap.parse_args()
    tag = args.tag

    pairs_df = pd.read_csv(P.PAIRS_CSV)
    med = (pairs_df.land_lat.between(30, 47) & pairs_df.land_lon.between(5, 42)).values
    sub = pairs_df[med]
    ocean_keys = list({(int(a), int(b)) for a, b in
                       sub[["ocean_lat_idx", "ocean_lon_idx"]].itertuples(index=False)})
    land_keys = list({(int(a), int(b)) for a, b in
                      sub[["land_lat_idx", "land_lon_idx"]].itertuples(index=False)})
    print(f"tag={tag}  Med 框配对数={int(med.sum())}  唯一海点={len(ocean_keys)}  唯一陆点={len(land_keys)}")

    store = {}
    if os.path.exists(CACHE) and not args.rebuild:
        z = np.load(CACHE)
        store = {k: z[k] for k in z.files}
        print(f"[cache] 复用 {CACHE}（{len(store)} 个数组；--rebuild 可重建）")

    for exp in ("ALL", "XGHG"):
        for m in P.select_members(20):
            key = f"{exp}_{m}"
            if key in store and not args.rebuild:
                continue
            t2m_path = os.path.join(P.CESM_INT, f"{exp}_{m}_T2m.nc")
            with xr.open_dataset(t2m_path) as ds:
                nt = ds["T2m"].sizes["time"]
                years = ds["T2m"].time.dt.year.values
                t0 = pd.Timestamp(ds["T2m"].time.values[0]).normalize()
            mhw = pd.read_csv(os.path.join(P.CESM_INT, f"mhw{tag}_{exp}_{m}.csv"),
                              parse_dates=["event_start", "event_end"])
            thw = pd.read_csv(os.path.join(P.CESM_INT, f"thw{tag}_{exp}_{m}.csv"),
                              parse_dates=["event_start", "event_end"])
            for nm, ev, keys, uy in (("marine", mhw, ocean_keys, years),
                                     ("terr", thw, land_keys, years)):
                d = daily_counts_per_year(ev, keys, years, nt, t0)
                e = event_counts_per_year(ev, keys, uy, nt, t0)
                store[f"{key}_{nm}_days"] = d.mean(axis=1)
                store[f"{key}_{nm}_events"] = e.mean(axis=1)
                store[f"{key}_{nm}_evmax"] = e.max(axis=1)
                store[f"{key}_{nm}_daysmax"] = d.max(axis=1)
            store[f"{key}_year"] = uy
            print(f"  {key} ok")

    if args.rebuild or not os.path.exists(CACHE):
        np.savez_compressed(CACHE, **store)
        print(f"[cache] 写入 {CACHE}")

    # ---- compound：直接读 annual csv 的 med_mean（days），事件数缺失，按列说明 ----
    comp = {}
    for exp in ("ALL", "XGHG"):
        vals = []
        for m in P.select_members(20):
            ca = pd.read_csv(os.path.join(P.CESM_INT, f"annual{tag}_{exp}_{m}.csv"))
            vals.append(ca.set_index("year")["med_mean"].values)
        comp[exp] = np.concatenate(vals)

    series = {}
    for exp in ("ALL", "XGHG"):
        for nm in ("marine", "terr"):
            for metric in ("days", "events"):
                series[(nm, metric, exp)] = np.concatenate(
                    [store[f"{exp}_{m}_{nm}_{metric}"] for m in P.select_members(20)])

    print("\n=== 序列描述（440 个模型年）===")
    for nm in ("marine", "terr"):
        for metric in ("days", "events"):
            for exp in ("ALL", "XGHG"):
                print(describe(f"{nm:6s} {metric:6s} {exp:4s}", series[(nm, metric, exp)]))
        print()
    for exp in ("ALL", "XGHG"):
        print(describe(f"comp   days   {exp:4s}", comp[exp]))

    print("\n=== GEV 点估计（负形状=有上界，正形状=重尾）===")
    for nm in ("marine", "terr"):
        for metric in ("days", "events"):
            for exp in ("ALL", "XGHG"):
                p = fit_gev(series[(nm, metric, exp)])
                print(f"  {nm:6s} {metric:6s} {exp:4s}  shape={p[0]:+.3f} loc={p[1]:8.2f} scale={p[2]:7.2f}")
    for exp in ("ALL", "XGHG"):
        p = fit_gev(comp[exp])
        print(f"  comp   days   {exp:4s}  shape={p[0]:+.3f} loc={p[1]:8.2f} scale={p[2]:7.2f}")

    print("\n=== 线性换尺度是否完全等变（days vs days/365）===")
    m_a = boot_map(series[("marine", "days", "ALL")], series[("marine", "days", "XGHG")],
                   args.n_boot, C.GEV_CI)[0]
    m_b = boot_map(series[("marine", "days", "ALL")] / 365.0,
                   series[("marine", "days", "XGHG")] / 365.0, args.n_boot, C.GEV_CI)[0]
    for rp in sorted(m_a):
        print(f"   {rp:5.0f}y  days->ALL {m_a[rp][1]:8.3f}  |  frac->ALL {m_b[rp][1]:8.3f}")

    print("\n=== 图4 映射：days vs events（vs 论文）===")
    PAPER = {("marine", "days"): {5: None, 10: None, 20: None, 50: 11.5, 100: 20.7},
             ("terr", "days"): {5: 1.2, 10: 1.4, 20: 1.7, 50: 2.4, 100: 3.2}}
    for nm in ("marine", "terr"):
        for metric in ("days", "events", "evmax", "daysmax"):
            if metric in ("evmax", "daysmax"):
                a = np.concatenate([store[f"ALL_{m}_{nm}_{metric}"] for m in P.select_members(20)])
                f = np.concatenate([store[f"XGHG_{m}_{nm}_{metric}"] for m in P.select_members(20)])
            else:
                a, f = series[(nm, metric, "ALL")], series[(nm, metric, "XGHG")]
            mp, _ = boot_map(a, f, args.n_boot, C.GEV_CI)
            ref = PAPER.get((nm, "days"), {})
            cells = []
            for rp in sorted(mp):
                lvl, al = mp[rp]
                r = ref.get(rp)
                cells.append(f"{rp:3.0f}y: L={lvl:7.2f} -> ALL {al:7.2f}" +
                             (f" (paper {r})" if r is not None else ""))
            print(f"\n[{nm} / {metric}]")
            for c in cells:
                print("   " + c)


if __name__ == "__main__":
    main()

