# -*- coding: utf-8 -*-
"""
phase6_audit_stats.py — task-4 审计脚本
「复合与统计审计：identify_compound_events 复用、440 模型年池化单元、FAR/PR/百分位/bootstrap」

用法:
    python results/phase6_audit_stats.py i1      # 复合链路 / 键空间 / t0-nt 对齐
    python results/phase6_audit_stats.py i2      # 暴露口径 / 区域框 / 观测阈值
    python results/phase6_audit_stats.py i3      # FAR/PR/inf/bootstrap/CI
    python results/phase6_audit_stats.py i4      # 复算 P0 数字
    python results/phase6_audit_stats.py all

产物写 results/intermediate/audit/stats/；**只读** results/intermediate/cesm/ 与 python/。
"""
import argparse
import json
import os
import re
import sys

import numpy as np
import pandas as pd
import xarray as xr
import warnings

warnings.filterwarnings("ignore")

ROOT = r"D:\2607compound"
PYDIR = os.path.join(ROOT, "python")
AUDIT = os.path.join(ROOT, "results", "intermediate", "audit", "stats")
os.makedirs(AUDIT, exist_ok=True)
sys.path.insert(0, PYDIR)

import phase6_cesm as P6  # noqa: E402
import config as C  # noqa: E402
from compound_events import _pair_maps, _event_daily_mask  # noqa: E402

PAIRS = pd.read_csv(P6.PAIRS_CSV)
MEMBERS = list(P6.MEMBERS_P0)
SRC = open(os.path.join(PYDIR, "phase6_cesm.py"), encoding="utf-8").read().split("\n")
PAPER = open(os.path.join(ROOT, "results", "paper_text.txt"), encoding="utf-8").read().split("\n")


def jdump(obj, name):
    p = os.path.join(AUDIT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    print(f"  -> {p}")


BASE_CACHE = os.path.join(ROOT, "results", "intermediate", "audit", "baseline")


def t2m_axis(exp, m):
    """T2m 时间轴：优先用 task-3 已缓存的 npz（与 nc 逐位一致），否则读 nc。"""
    cache = os.path.join(BASE_CACHE, f"t2m_{exp}_{m}.npz")
    if os.path.exists(cache):
        return pd.DatetimeIndex(np.load(cache)["time"])
    f = os.path.join(P6.CESM_INT, f"{exp}_{m}_T2m.nc")
    last = None
    for _ in range(5):          # 工作区内其他进程并发时偶发 ENOENT，重试
        try:
            ds = xr.open_dataset(f)
            t = pd.DatetimeIndex(ds["T2m"].time.values)
            ds.close()
            return t
        except FileNotFoundError as e:
            last = e
            import time as _time
            _time.sleep(1.0)
    raise last


def load_annual(tag, exp):
    """读 annual{tag}_{exp}_{m}.csv -> (长表, 每列 66 样本)。"""
    parts = []
    for m in MEMBERS:
        p = os.path.join(P6.CESM_INT, f"annual{tag}_{exp}_{m}.csv")
        parts.append(pd.read_csv(p).assign(member=m))
    df = pd.concat(parts).sort_values(["member", "year"])
    return df


# ══════════════════════════════════════════════════════════════
# I1 复合链路 / 键空间 / t0-nt 对齐
# ══════════════════════════════════════════════════════════════
def stage_i1():
    print("== I1 复合链路 ==")
    out = {}

    # 1) 证据行
    hits = [(i + 1, SRC[i].strip()) for i in range(len(SRC))
            if "identify_compound_events" in SRC[i] or "_pair_maps" in SRC[i]
            or "_event_daily_mask" in SRC[i]]
    out["reuse_lines"] = hits
    print("[I1-1] cmd_compound 的复用证据:")
    for i, ln in hits:
        print(f"    L{i}: {ln[:110]}")

    # 2) 键空间
    def rng(df, cols):
        return {c: [int(df[c].min()), int(df[c].max())] for c in cols}
    out["pair_index_ranges"] = rng(PAIRS, ["land_lat_idx", "land_lon_idx",
                                           "ocean_lat_idx", "ocean_lon_idx"])
    ks = {}
    for f in sorted(os.listdir(P6.CESM_INT)):
        if re.match(r"(mhw|thw)_x?_(ALL|XGHG)_\d+\.csv$", f):
            d = pd.read_csv(os.path.join(P6.CESM_INT, f))
            ks[f] = {"n": len(d), "lat_idx": [int(d.lat_idx.min()), int(d.lat_idx.max())],
                     "lon_idx": [int(d.lon_idx.min()), int(d.lon_idx.max())],
                     "ts_time_of_day": sorted({str(pd.Timestamp(x).time())
                                               for x in pd.to_datetime(d.event_start)})}
    out["event_tables"] = ks
    print("[I1-2] 键空间: pairs 海索引", out["pair_index_ranges"]["ocean_lat_idx"],
          out["pair_index_ranges"]["ocean_lon_idx"],
          "| 陆索引", out["pair_index_ranges"]["land_lat_idx"],
          out["pair_index_ranges"]["land_lon_idx"])
    bad = [f for f, v in ks.items() if f.startswith("mhw") and (
        v["lat_idx"][0] < out["pair_index_ranges"]["ocean_lat_idx"][0] or
        v["lat_idx"][1] > out["pair_index_ranges"]["ocean_lat_idx"][1])]
    bad += [f for f, v in ks.items() if f.startswith("thw") and (
        v["lat_idx"][1] > out["pair_index_ranges"]["land_lat_idx"][1])]
    out["key_space_consistent"] = (len(bad) == 0)
    print(f"[I1-2] 越界事件表: {bad if bad else '无'} ⇒ 键空间一致={out['key_space_consistent']}")

    # 3) t0/nt 与事件日期
    rows = []
    for exp in ("ALL", "XGHG"):
        for m in MEMBERS:
            tt = t2m_axis(exp, m)
            t0 = pd.Timestamp(tt[0])
            nt = len(tt)
            for kind in ("mhw_x", "thw_x", "mhw", "thw"):
                p = os.path.join(P6.CESM_INT, f"{kind}_{exp}_{m}.csv")
                if not os.path.exists(p):
                    continue
                d = pd.read_csv(p, parse_dates=["event_start", "event_end"])
                s = (d.event_start - t0).dt.days.values
                e = (d.event_end - t0).dt.days.values
                rows.append({
                    "file": os.path.basename(p), "exp": exp, "member": m,
                    "t0": str(t0), "t0_hour": t0.hour, "nt": nt,
                    "event_hour": sorted({pd.Timestamp(x).hour for x in d.event_start}),
                    "n": len(d),
                    "inside": int(((s >= 0) & (e <= nt - 1)).sum()),
                    "clip_left": int(((s < 0) & (e >= 0)).sum()),
                    "clip_right": int(((s <= nt - 1) & (e > nt - 1)).sum()),
                    "dropped": int(((e < 0) | (s > nt - 1)).sum()),
                    "min_s": int(s.min()), "max_e": int(e.max())})
    bdf = pd.DataFrame(rows)
    bdf.to_csv(os.path.join(AUDIT, "i1_event_bounds.csv"), index=False)
    print("[I1-3] 事件越界审计（t0/nt 取自同成员 T2m 文件）:")
    print(bdf[["file", "t0_hour", "event_hour", "n", "inside", "clip_left",
               "clip_right", "dropped", "min_s", "max_e"]].to_string(index=False))

    # 4) _pair_maps 1:1 与多对一
    lpd = _pair_maps(PAIRS)
    oc = pd.Series(list(lpd.values()))
    vc = oc.value_counts()
    out["pair_maps"] = {
        "n_land_keys": len(lpd), "n_pairs": len(PAIRS),
        "n_unique_ocean_keys": int(oc.nunique()),
        "max_land_per_ocean": int(vc.max()),
        "n_ocean_with_multiple_land": int((vc > 1).sum()),
        "n_duplicate_land_keys": int(len(PAIRS) - PAIRS[["land_lat_idx", "land_lon_idx"]]
                                     .drop_duplicates().shape[0])}
    print(f"[I1-4] _pair_maps: {len(lpd)} 个陆键（=配对数 {len(PAIRS)}，无覆盖丢失）；"
          f"{oc.nunique()} 个唯一海键；一对多最大 {vc.max()} 个陆点共用同一海点，"
          f"共 {int((vc>1).sum())} 个海点")

    # 5) identify_compound_events 输出 = cmd_compound 的 compound_days
    from compound_events import identify_compound_events
    cmp_rows = []
    for exp in ("ALL", "XGHG"):
        for m in MEMBERS:
            tt = t2m_axis(exp, m)
            time_da = xr.DataArray(np.zeros(len(tt), dtype=np.int8), dims="time",
                                   coords={"time": tt})
            mhw = pd.read_csv(os.path.join(P6.CESM_INT, f"mhw_x_{exp}_{m}.csv"),
                              parse_dates=["event_start", "event_end"])
            thw = pd.read_csv(os.path.join(P6.CESM_INT, f"thw_x_{exp}_{m}.csv"),
                              parse_dates=["event_start", "event_end"])
            comp = identify_compound_events(mhw, thw, PAIRS, time_da.time)
            seg_days = int(((comp.thw_end - comp.thw_start).dt.days + 1).sum())
            stored = pd.read_csv(os.path.join(P6.CESM_INT, "exposure_members_x.csv"))
            ref = int(stored[(stored.exp == exp) & (stored.member.astype(str)
                                                    .str.zfill(3) == m)].compound_days.iloc[0])
            cmp_rows.append({"exp": exp, "member": m, "identify_segments": len(comp),
                             "identify_seg_days": seg_days, "exposure_csv_compound_days": ref,
                             "match": seg_days == ref})
    cdf = pd.DataFrame(cmp_rows)
    cdf.to_csv(os.path.join(AUDIT, "i1_identify_vs_exposure.csv"), index=False)
    print("[I1-5] identify_compound_events 段天数 vs exposure_members_x.compound_days:")
    print(cdf.to_string(index=False))

    jdump(out, "i1_structure.json")
    return out


# ══════════════════════════════════════════════════════════════
# I2 暴露口径 / 区域框 / 观测阈值
# ══════════════════════════════════════════════════════════════
def stage_i2():
    print("== I2 暴露口径与统计单元 ==")
    out = {}
    med = (PAIRS.land_lat.between(30, 47) & PAIRS.land_lon.between(5, 42)).values
    op = pd.read_csv(C.COASTAL_PAIRS_CSV)
    omed = (op.land_lat.between(30, 47) & op.land_lon.between(5, 42)).values
    out["region_box"] = {
        "cesm_pairs_in_box": int(med.sum()), "cesm_pairs_total": len(PAIRS),
        "cesm_frac": float(med.mean()),
        "cesm_unique_ocean_in_box": int(PAIRS[med][["ocean_lat_idx", "ocean_lon_idx"]]
                                        .drop_duplicates().shape[0]),
        "obs_pairs_in_box": int(omed.sum()), "obs_pairs_total": len(op),
        "obs_frac": float(omed.mean()),
        "box": "lat 30-47, lon 5-42"}
    print(f"[I2-1] 区域框 lat30-47/lon5-42: CESM {med.sum()}/{len(PAIRS)} = "
          f"{med.mean()*100:.1f}%（唯一海点 {out['region_box']['cesm_unique_ocean_in_box']}）; "
          f"观测 {omed.sum()}/{len(op)} = {omed.mean()*100:.1f}%")

    # 逐年归属 + 22 年
    anns = {}
    for exp in ("ALL", "XGHG"):
        df = load_annual("_x", exp)
        anns[exp] = df
    yrs = sorted(anns["ALL"].year.unique())
    out["year_attribution"] = {
        "n_unique_years": len(yrs), "first": int(yrs[0]), "last": int(yrs[-1]),
        "years": [int(y) for y in yrs],
        "n_rows_per_col": int(len(anns["ALL"])),
        "sample_size": int(len(anns["ALL"])),
        "members": MEMBERS}
    print(f"[I2-2] 年度归属: {len(yrs)} 个唯一年份 {yrs[0]}-{yrs[-1]}；"
          f"每列样本 = 3 成员 × 22 年 = {len(anns['ALL'])}（20 成员时 440）")

    # 观测阈值
    obs = P6._obs_annual_threshold()
    ann = xr.open_dataset(C.ANNUAL_COMPOUND_NC)
    var = list(ann.data_vars)[0]
    da = ann[var]
    p = op[omed]
    sub = da.isel(lat=xr.DataArray(p.land_lat_idx.values, dims="p"),
                  lon=xr.DataArray(p.land_lon_idx.values, dims="p"))
    arr = sub.transpose("time", "p").values
    yv = sub.time.values.astype(int)
    tab = pd.DataFrame({"year": yv, "med_mean": arr.mean(axis=1), "med_max": arr.max(axis=1),
                        "p90": np.percentile(arr, 90, axis=1),
                        "p95": np.percentile(arr, 95, axis=1)})
    ann.close()
    out["obs_aggregations"] = {str(y): {k: float(tab.loc[tab.year == y, k].iloc[0])
                                        for k in ("med_mean", "med_max", "p90", "p95")}
                               for y in (2003, 2022, 2023)}
    paper_ref = {"2003": 62, "2022": 78, "2023": 72}
    print("[I2-3] 观测 Med 框（615 对）2022 阈值: med_mean=%.2f 天  med_max=%.1f 天 "
          "（=年度复现报告 §11.6 的 128）" % (
              float(tab.loc[tab.year == 2022, 'med_mean'].iloc[0]),
              float(tab.loc[tab.year == 2022, 'med_max'].iloc[0])))
    print(f"      论文 Fig.3c 参考线 {paper_ref} vs 本复现各聚合口径:")
    for y in (2003, 2022, 2023):
        r = out["obs_aggregations"][str(y)]
        print(f"      {y}: 论文 {paper_ref[str(y)]:>3} | med_mean {r['med_mean']:6.2f} | "
              f"p90 {r['p90']:6.1f} | p95 {r['p95']:6.1f} | med_max {r['med_max']:6.1f}")
    jdump(out, "i2_unit_and_threshold.json")
    return out


# ══════════════════════════════════════════════════════════════
# I3 FAR/PR / bootstrap
# ══════════════════════════════════════════════════════════════
def clopper_pearson(k, n, alpha=(0.05, 0.95)):
    from scipy.stats import beta
    lo = 0.0 if k == 0 else float(beta.ppf(alpha[0], k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(alpha[1], k + 1, n - k))
    return lo, hi


def boot_variants(sa, sf, x, n_boot=1000, seed=42):
    """四种 bootstrap 变体 -> (点估计, CI, inf 比例)。"""
    rng = np.random.default_rng(seed)

    def pr(a, f):
        pa = float((a >= x).mean())
        pf = float((f >= x).mean())
        return np.inf if pf == 0 else pa / pf

    def ci(boots):
        fin = boots[np.isfinite(boots)]
        return ((float(np.percentile(fin, 5)), float(np.percentile(fin, 95)))
                if len(fin) else (np.nan, np.nan), float(np.mean(~np.isfinite(boots))))

    res = {"point": pr(sa, sf)}
    # (1) 现状: 组内 i.i.d. 年重采样（两组独立, 各 n=66）
    b = np.array([pr(sa[rng.integers(0, len(sa), len(sa))],
                     sf[rng.integers(0, len(sf), len(sf))]) for _ in range(n_boot)])
    res["iid"] = ci(b)
    # (2) 成员 block: 成员有放回重采样（保留成员内 22 年结构）
    res["member_block"] = ci(np.array([pr(
        np.concatenate([sa.reshape(3, 22)[i] for i in rng.integers(0, 3, 3)]),
        np.concatenate([sf.reshape(3, 22)[i] for i in rng.integers(0, 3, 3)]))
        for _ in range(n_boot)]))
    # (3) 成员内分层: 每个成员的 22 年各自重采样（保留成员结构, 打散年自相关）
    res["stratified"] = ci(np.array([pr(
        np.concatenate([sa.reshape(3, 22)[i][rng.integers(0, 22, 22)] for i in range(3)]),
        np.concatenate([sf.reshape(3, 22)[i][rng.integers(0, 22, 22)] for i in range(3)]))
        for _ in range(n_boot)]))
    # (4) 成员内移动块 (L=5)
    def mbb(a):
        out = []
        for i in range(3):
            v = a.reshape(3, 22)[i]
            idx = []
            while len(idx) < 22:
                s0 = rng.integers(0, 22)
                idx += [(s0 + k) % 22 for k in range(5)]
            out.append(v[np.array(idx[:22])])
        return np.concatenate(out)
    res["moving_block5"] = ci(np.array([pr(mbb(sa), mbb(sf)) for _ in range(n_boot)]))
    # (5) Clopper-Pearson（二项精确, 不做 bootstrap）
    ka, kf = int((sa >= x).sum()), int((sf >= x).sum())
    alo, ahi = clopper_pearson(ka, len(sa))
    flo, fhi = clopper_pearson(kf, len(sf))
    res["clopper_pearson"] = {
        "k_all": ka, "k_fix": kf, "n": len(sa),
        "p_all_ci": [alo, ahi], "p_fix_ci": [flo, fhi],
        "PR_ci": [float("inf") if fhi == 0 else alo / fhi,
                  float("inf") if flo == 0 else ahi / flo],
        "inf_frac": float(flo == 0)}
    return res


def stage_i3():
    print("== I3 FAR/PR 与 bootstrap ==")
    out = {}
    out["paper_eq"] = {
        "eq2_far": [(i + 1, PAPER[i].strip()) for i in range(558, 564)],
        "eq3_pr": [(i + 1, PAPER[i].strip()) for i in range(564, 569)],
        "bootstrap": [(i + 1, PAPER[i].strip()) for i in range(583, 590)],
        "ci_note": [(i + 1, PAPER[i].strip()) for i in range(589, 596)]}
    for k, v in out["paper_eq"].items():
        print(f"[I3-1] {k}:")
        for i, ln in v:
            print(f"    L{i}: {ln[:110]}")

    # 公式方向: 数值验证 1-1/point == 1-p_fix/p_all
    sa = np.array([10.0, 20.0, 30.0, 40.0])
    sf = np.array([5.0, 10.0, 15.0, 20.0])
    x = 25.0
    p_all = (sa >= x).mean()
    p_fix = (sf >= x).mean()
    point = p_all / p_fix
    out["formula_check"] = {"p_all": float(p_all), "p_fix": float(p_fix),
                            "PR": float(point), "FAR_via_1-1/PR": float(1 - 1 / point),
                            "FAR_via_1-p_fix/p_all": float(1 - p_fix / p_all),
                            "identical": bool(abs((1 - 1 / point) - (1 - p_fix / p_all)) < 1e-12)}
    print(f"[I3-2] 公式一致性: 1-1/PR={1-1/point:.6f} vs 1-p_fix/p_all="
          f"{1-p_fix/p_all:.6f} ⇒ {out['formula_check']['identical']}")

    # 最小用例: p_fix=0
    s0 = np.array([1.0, 2.0, 3.0])
    pr0, far0, lo0, hi0, b0 = P6._pr_boot(x, sa, s0)
    try:
        s_fmt = f"{far0:.2f}"
        fmt_ok = True
    except Exception as e:  # noqa: BLE001
        s_fmt, fmt_ok = repr(e), False
    out["pfix_zero_case"] = {"PR": pr0, "FAR": far0, "lo": lo0, "hi": hi0,
                             "n_boot": len(b0), "n_finite": int(np.isfinite(b0).sum()),
                             "f_far_2f_ok": fmt_ok, "f_far_2f_value": s_fmt}
    print(f"[I3-3] p_fix=0 最小用例: PR={pr0} FAR={far0} lo={lo0} hi={hi0} "
          f"有限重采样 {int(np.isfinite(b0).sum())}/{len(b0)}；f'{{far:.2f}}' -> {s_fmt!r} "
          f"(不抛错={fmt_ok})")

    # docstring vs 返回个数
    doc = SRC[591].strip()
    ret = SRC[612].strip()
    out["docstring"] = {"line592": doc, "line613": ret,
                        "returns_n": 5, "doc_n": 4}
    print(f"[I3-4] docstring(L592)='{doc}' vs 实际 return(L613)='{ret}' ⇒ 文档 4 值/实际 5 值")

    # 现状 bootstrap 细节（用 annual_x 样本）
    obs = P6._obs_annual_threshold()
    v22_mean = float(obs.loc[obs.year == 2022, "med_mean"].iloc[0])
    v22_max = float(obs.loc[obs.year == 2022, "med_max"].iloc[0])
    rows = []
    for col, x in (("med_mean", v22_mean), ("med_max", v22_max)):
        sa_ = load_annual("_x", "ALL")[col].values.astype(float)
        sf_ = load_annual("_x", "XGHG")[col].values.astype(float)
        point, far, lo, hi, boots = P6._pr_boot(x, sa_, sf_)
        fin = boots[np.isfinite(boots)]
        v = boot_variants(sa_, sf_, x)
        rows.append({
            "col": col, "threshold": x,
            "p_all": float((sa_ >= x).mean()), "p_fix": float((sf_ >= x).mean()),
            "k_all": int((sa_ >= x).sum()), "k_fix": int((sf_ >= x).sum()),
            "PR_point": point, "FAR_point": far,
            "ci_drop_inf": [lo, hi],
            "n_inf": int((~np.isfinite(boots)).sum()),
            "inf_frac": float((~np.isfinite(boots)).mean()),
            "median_finite": float(np.median(fin)) if len(fin) else np.nan,
            "ci_iid": v["iid"][0], "ci_member_block": v["member_block"][0],
            "ci_stratified": v["stratified"][0], "ci_mblock5": v["moving_block5"][0],
            "cp_PR_ci": v["clopper_pearson"]["PR_ci"],
            "cp_inf_frac": v["clopper_pearson"]["inf_frac"],
            "ci_iid_inffrac": v["iid"][1]})
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(AUDIT, "i3_bootstrap.csv"), index=False)
    print("[I3-5] bootstrap 变体对照:")
    print(t[["col", "threshold", "p_all", "p_fix", "PR_point", "FAR_point",
             "ci_drop_inf", "n_inf", "median_finite", "ci_member_block",
             "ci_stratified", "ci_mblock5", "cp_PR_ci"]].to_string(index=False))
    jdump(out, "i3_formulas.json")
    return out


# ══════════════════════════════════════════════════════════════
# I4 复算 P0 数字
# ══════════════════════════════════════════════════════════════
def stage_i4():
    print("== I4 复算 P0 数字 ==")
    out = {}
    res = []
    for tag, name in (("", "v1 (own-clim)"), ("_x", "v2 (XGHG-pooled)")):
        st = pd.read_csv(os.path.join(P6.CESM_INT, f"exposure_members{tag}.csv"))
        g = st.groupby("exp").compound_days.mean()
        out[f"ratio_{tag or 'v1'}"] = {
            "all_mean": float(g["ALL"]), "fix_mean": float(g["XGHG"]),
            "ratio": float(g["ALL"] / g["XGHG"])}
        obs = P6._obs_annual_threshold()
        for col in ("med_mean", "med_max"):
            x = float(obs.loc[obs.year == 2022, col].iloc[0])
            sa = load_annual(tag, "ALL")[col].values.astype(float)
            sf = load_annual(tag, "XGHG")[col].values.astype(float)
            pr, far, lo, hi, boots = P6._pr_boot(x, sa, sf)
            res.append({"tag": name, "col": col, "threshold": x,
                        "p_all": float((sa >= x).mean()), "p_fix": float((sf >= x).mean()),
                        "PR": pr, "FAR": far, "ci_lo": lo, "ci_hi": hi,
                        "n_inf": int((~np.isfinite(boots)).sum()),
                        "all_mean": float(sa.mean()), "fix_mean": float(sf.mean())})
    r = pd.DataFrame(res)
    r.to_csv(os.path.join(AUDIT, "i4_recompute.csv"), index=False)
    print(f"[I4-1] 22 年总暴露均值比: v2 = {out['ratio__x']['ratio']:.3f} "
          f"(报告称 8.88)；v1 = {out['ratio_v1']['ratio']:.3f}（报告称 1.00）")
    print("[I4-2] PR/FAR 复算:")
    print(r.to_string(index=False))
    print("[I4-3] fig7 标题（人工读图）: v2 med_mean 'PR=∞ FAR=nan' / med_max "
          "'PR=48.0 FAR=0.98'; v1 med_mean 'PR=1.0 FAR=0.00' / med_max 'PR=∞ FAR=nan'")
    jdump(out, "i4_ratios.json")
    return out


# ══════════════════════════════════════════════════════════════
# I1b 日历/时刻对齐敏感性（noleap 解码 + 事件表时刻差异）
# ══════════════════════════════════════════════════════════════
def _compound_from_tables(tag, exp, m, shift_mhw=0, shift_thw=0):
    """用既有事件表重算复合日 + Med 框年暴露（不改 cesm 目录）。"""
    from compound_events import identify_compound_events
    tt = t2m_axis(exp, m)
    time_da = xr.DataArray(np.zeros(len(tt), dtype=np.int8), dims="time",
                           coords={"time": tt})
    mhw = pd.read_csv(os.path.join(P6.CESM_INT, f"mhw{tag}_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    thw = pd.read_csv(os.path.join(P6.CESM_INT, f"thw{tag}_{exp}_{m}.csv"),
                      parse_dates=["event_start", "event_end"])
    if shift_mhw:
        for c in ("event_start", "event_end"):
            mhw[c] = mhw[c] + pd.Timedelta(days=shift_mhw)
    if shift_thw:
        for c in ("event_start", "event_end"):
            thw[c] = thw[c] + pd.Timedelta(days=shift_thw)
    t0 = pd.Timestamp(tt[0])
    nt = len(tt)
    lpd = _pair_maps(PAIRS)
    om = {k: _event_daily_mask(g, nt, t0)
          for k, g in mhw.groupby(["lat_idx", "lon_idx"])}
    kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
    thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
    thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}
    comp_days = 0
    daily = np.zeros((nt, len(PAIRS)), dtype=np.int8)
    pos = {(int(r.land_lat_idx), int(r.land_lon_idx)): p
           for p, r in enumerate(PAIRS.itertuples(index=False))}
    for lk, ok_ in lpd.items():
        g = thw_by.get(lk)
        if g is None or len(g) == 0:
            continue
        lm = _event_daily_mask(g, nt, t0)
        m_ = om.get(ok_)
        if m_ is None:
            continue
        coex = lm & m_
        comp_days += int(coex.sum())
        daily[coex, pos[lk]] = 1
    comp = identify_compound_events(mhw, thw, PAIRS, time_da.time)
    years = tt.year.values
    uy = np.unique(years)
    ann = np.stack([daily[years == y].sum(axis=0) for y in uy])
    med = (PAIRS.land_lat.between(30, 47) & PAIRS.land_lon.between(5, 42)).values
    return pd.DataFrame({"year": uy, "med_mean": ann[:, med].mean(axis=1),
                         "med_max": ann[:, med].max(axis=1)}), comp_days, len(comp)


def stage_i1b():
    """I1b: 事件表时刻约定差异导致的 ±1 天掩码位移（组间不一致）敏感性。

    背景（lead 已否证"标签物理日相差 1 天"）：CAM 的 `date` = time_bnds 右端，
    POP 的 time = time_bound 右端 ⇒ 同一标签 = 同一 24 小时区间。
    但 `_event_daily_mask` 用 floor((事件时刻 − t0)/1 天) 取索引：
      * ALL 组的 T2m 来自 AWS 成品，时刻 12:00；POP SST 时刻 00:00
        ⇒ MHW 掩码比 THW 掩码**早 1 天**（floor(-0.5) = -1）；
      * XGHG 组的 T2m 由 cmd_prepare 写自 raw CAM（00:00），SST 也是 00:00
        ⇒ 无位移。
    两者不可能同时正确 ⇒ 组间不一致（缺陷），本阶段量化其影响。
    """
    print("== I1b 事件表时刻/掩码位移敏感性（组间不一致） ==")
    obs = P6._obs_annual_threshold()
    th = {c: float(obs.loc[obs.year == 2022, c].iloc[0]) for c in ("med_mean", "med_max")}
    VARIANTS = [
        ("V0-current", {"ALL": (0, 0), "XGHG": (0, 0)}),
        ("V1-ALL_MHW+1", {"ALL": (1, 0), "XGHG": (0, 0)}),
        ("V2-XGHG_MHW-1", {"ALL": (0, 0), "XGHG": (-1, 0)}),
        ("V3-both_MHW-1", {"ALL": (-1, 0), "XGHG": (-1, 0)}),
        ("V4-both_MHW+1", {"ALL": (1, 0), "XGHG": (1, 0)}),
        ("V5-ALL_THW+1", {"ALL": (0, 1), "XGHG": (0, 0)}),
    ]
    rows = []
    for tag, tname in (("_x", "v2"), ("", "v1")):
        for label, spec in VARIANTS:
            store = {}
            for exp in ("ALL", "XGHG"):
                dm, dt_ = spec[exp]
                anns = []
                for m in MEMBERS:
                    ann, cd, nseg = _compound_from_tables(tag, exp, m, dm, dt_)
                    anns.append(ann)
                    rows.append({"tag": tname, "variant": label, "exp": exp, "member": m,
                                 "compound_days": cd, "segments": nseg})
                store[exp] = pd.concat(anns)
            for col in ("med_mean", "med_max"):
                sa = store["ALL"][col].values
                sf = store["XGHG"][col].values
                pr, far, lo, hi, _ = P6._pr_boot(th[col], sa, sf)
                rows.append({"tag": tname, "variant": label, "exp": "P",
                             "member": col, "compound_days": np.nan, "segments": np.nan,
                             "p_all": float((sa >= th[col]).mean()),
                             "p_fix": float((sf >= th[col]).mean()),
                             "PR": pr, "FAR": far, "ci_lo": lo, "ci_hi": hi,
                             "all_med_mean_mean": float(store["ALL"]["med_mean"].mean()),
                             "fix_med_mean_mean": float(store["XGHG"]["med_mean"].mean())})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(AUDIT, "i1b_alignment.csv"), index=False)
    piv = df[df.exp == "P"].pivot_table(index=["tag", "variant"], columns="member",
                                        values="PR", aggfunc="first")
    print("[I1b-1] PR (threshold = obs 2022 same-metric):")
    print(piv.to_string())
    cd = df[df.exp != "P"].pivot_table(index=["tag", "variant"], columns="exp",
                                      values="compound_days", aggfunc="sum")
    print("[I1b-2] compound days (3 members summed):")
    print(cd.to_string())
    print("  -> " + os.path.join(AUDIT, "i1b_alignment.csv"))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["i1", "i1b", "i2", "i3", "i4", "all"])
    a = ap.parse_args()
    for s in (["i1", "i1b", "i2", "i3", "i4"] if a.stage == "all" else [a.stage]):
        globals()[f"stage_{s}"]()


if __name__ == "__main__":
    main()
