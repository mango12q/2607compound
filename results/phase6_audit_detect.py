# -*- coding: utf-8 -*-
"""
phase6_audit_detect.py — D-2 检测语义审计（Python 侧，E1-E5 + 附加 A1/A2）

审计对象: python/phase6_cesm.py 的
    _run_events / _detect_mhw_member / _detect_thw_member / _detect_thw_member_ext
    / _pooled_threshold_sst / _pooled_threshold_t2m
对照物:   python/detect_events.R（heatwaveR 0.5.5，观测侧正式链路）

原则: 不采信任何项目文档自述。所有结论 = 实测数字 + heatwaveR 真实函数体。
      本脚本只读 python/ 与 results/intermediate/cesm/，绝不写入。

产物 -> results/intermediate/audit/detect/
    audit_summary.json          全部量化结论（机器可读）
    E1_*.csv / E2_*.csv / E3_*.csv / E4*.csv / E5_*.csv / A1_*.csv / A2_*.csv

用法:
    python results/phase6_audit_detect.py                          # 全流程（含调用 R）
    python results/phase6_audit_detect.py --skip-r                 # 仅用已有 R 产物
    python results/phase6_audit_detect.py --only export,fuzz,r,e1,e2,e3,e4,e4c,e5,a1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
import xarray as xr

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)

AUDIT = r"D:\2607compound\results\intermediate\audit\detect"
PYDIR = r"D:\2607compound\python"
CESM_INT = r"D:\2607compound\results\intermediate\cesm"
RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
R_AUDIT = r"D:\2607compound\results\phase6_audit_detect.R"

sys.path.insert(0, PYDIR)
import phase6_cesm as P6            # noqa: E402  (被审计代码)
import config as C                  # noqa: E402
import detect_mhw                   # noqa: E402  (观测侧 Python 状态机，作对照)

os.makedirs(AUDIT, exist_ok=True)
PAIRS = pd.read_csv(P6.PAIRS_CSV)
RES: dict = {}


def sec(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78, flush=True)


def rec(key, val):
    RES[key] = val
    return val


# =============================================================================
# 工具: heatwaveR 语义的忠实参考实现
# =============================================================================
def hw_doy(dates: pd.DatetimeIndex) -> np.ndarray:
    """heatwaveR make_whole_fast 的 doy 映射:
    非闰年 doy>59 者 +1（把每个日历年规格化到 366 槽，Feb-29 槽保留）。
    注意 CESM 序列本身缺 Feb 29，故闰年 doy 即 pandas dayofyear。"""
    k = dates.dayofyear.values
    yr = dates.year.values
    leap = np.array([(y % 4 == 0 and y % 100 != 0) or (y % 400 == 0) for y in yr])
    return np.where((~leap) & (k > 59), k + 1, k)


def build_A(members, npts: int):
    """members: [(vals(nt,npts), dates)] -> A(366, n_year_slots, npts)

    复刻 heatwaveR clim_spread: 每个日历年一列、doy 一行；
    缺 Feb-29 者按 clim_spread 的 .NA2mean 规则用 round(mean(doy59,doy61),2) 填充。"""
    out = []
    for vals, dates in members:
        yrs = sorted(set(dates.year))
        yi = {y: i for i, y in enumerate(yrs)}
        A = np.full((366, len(yrs), npts), np.nan)
        A[hw_doy(dates) - 1, np.array([yi[y] for y in dates.year]), :] = vals
        A[59] = np.round((A[58] + A[60]) / 2.0, 2)     # doy 60 = Feb 29 槽
        out.append(A)
    return np.concatenate(out, axis=1)


def thresh_from_A(A, half: int = 5, pct: float = 90.0) -> np.ndarray:
    """heatwaveR clim_calc: 窗口内合并原始样本后取分位（366 天圆形环绕）。"""
    npts = A.shape[2]
    th = np.full((366, npts), np.nan)
    for d in range(366):
        idx = [(d + k) % 366 for k in range(-half, half + 1)]
        th[d] = np.nanpercentile(A[idx].reshape(-1, npts), pct, axis=0)
    return th


def single_thresh(doy: np.ndarray, vals: np.ndarray, npts: int, hw_map: bool):
    """逐 doy 单日 90 分位。hw_map=True 用 heatwaveR doy(含 366)，False 用 pandas doy。
    后者复刻 _pooled_threshold_* 的 1..365 循环。返回 (366,npts)。"""
    th = np.full((366, npts), np.nan)
    rng = np.arange(1, 367) if hw_map else np.arange(1, 366)
    for d in rng:
        rows = vals[doy == d]
        if len(rows):
            th[d - 1] = np.nanpercentile(rows, 90, axis=0)
    return th


def count_events(vals, thr, time, min_dur=5, max_gap=2):
    """用被审计的 _run_events 跑全点，返回 (n_events, exceed_days, durations)。
    thr 必须是 (366, npts) 的 doy 索引表（与 _detect_* 内部一致）。"""
    thr_t = thr[pd.DatetimeIndex(time).dayofyear.values - 1]
    n_ev, n_exc, durs = 0, 0, []
    for p in range(vals.shape[1]):
        x = vals[:, p] > thr_t[:, p]
        x[np.isnan(vals[:, p])] = False
        n_exc += int(x.sum())
        ev = P6._run_events(x, time, min_dur, max_gap)
        n_ev += len(ev)
        durs += [b - a + 1 for a, b in ev]
    return n_ev, n_exc, np.array(durs)


def load_t2m(exp, m):
    ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
    da = ds["T2m"].isel(lat=xr.DataArray(PAIRS.land_lat_idx.values, dims="p"),
                        lon=xr.DataArray(PAIRS.land_lon_idx.values, dims="p"))
    arr = da.transpose("time", "p").values.astype(np.float64)
    t = pd.DatetimeIndex(da.time.values)
    ds.close()
    return arr, t


# =============================================================================
# 阶段 0 / 0b: 导出真实序列 + 生成模糊用例
# =============================================================================
def export_series():
    sec("阶段 0  导出真实序列 CSV 供 R 侧权威计算")
    for exp in ("ALL", "XGHG"):
        arr, t = load_t2m(exp, "001")
        d = pd.DataFrame(arr, columns=[f"p{i:03d}" for i in range(arr.shape[1])])
        d.insert(0, "date", t.strftime("%Y-%m-%d"))
        p = os.path.join(AUDIT, f"series_t2m_{exp}_001.csv")
        d.to_csv(p, index=False, float_format="%.10g")
        print(f"  {p}  {d.shape}")
        v, tsst, _ = P6._load_sst_points(exp, "001", PAIRS)
        d2 = pd.DataFrame(v, columns=[f"p{i:03d}" for i in range(v.shape[1])])
        d2.insert(0, "date", tsst.strftime("%Y-%m-%d"))
        p2 = os.path.join(AUDIT, f"series_sst_{exp}_001.csv")
        d2.to_csv(p2, index=False, float_format="%.10g")
        print(f"  {p2}  {d2.shape}")


def gen_fuzz(m=150, seed=20260923):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(m):
        n = int(rng.integers(20, 61))
        p = float(rng.uniform(0.15, 0.6))
        pat = "".join("1" if z else "0" for z in (rng.random(n) < p))
        rows.append(dict(case=f"f{i:03d}", n=n, pattern=pat))
    pd.DataFrame(rows).to_csv(os.path.join(AUDIT, "fuzz_cases.csv"), index=False)
    print(f"  生成 {len(rows)} 条模糊用例 -> fuzz_cases.csv")
    return rows


def run_r(mode="all"):
    sec(f"阶段 1  调用 R 侧审计脚本（heatwaveR 权威语义, MODE={mode}）")
    r = subprocess.run([RSCRIPT, R_AUDIT, AUDIT, AUDIT, mode],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "")[-6000:])
    if r.returncode != 0:
        print("!! R 失败 stderr:\n", (r.stderr or "")[-4000:])
    return r.returncode


# =============================================================================
# E1 — _pooled_threshold_t2m 的 axis 崩溃
# =============================================================================
def e1():
    sec("E1  _pooled_threshold_t2m / _pooled_threshold_sst 的 axis 崩溃")
    z_t = np.load(os.path.join(CESM_INT, "thresh_t2m_xghg.npz"))
    z_s = np.load(os.path.join(CESM_INT, "thresh_sst_xghg.npz"))
    thr_t, thr_s = z_t["thresh"], z_s["thresh"]
    sz_t = os.path.getsize(os.path.join(CESM_INT, "thresh_t2m_xghg.npz"))
    sz_s = os.path.getsize(os.path.join(CESM_INT, "thresh_sst_xghg.npz"))

    rows = []
    for tag, th, sz in (("t2m", thr_t, sz_t), ("sst", thr_s, sz_s)):
        fin = np.isfinite(th)
        safe = np.where(fin, th, np.nan)
        ptp = np.nanmax(safe, axis=1) - np.nanmin(safe, axis=1)
        ptp_f = ptp[np.isfinite(ptp)]
        rows.append(dict(var=tag, shape=str(th.shape), file_bytes=int(sz),
                         all_nan_rows=str(np.flatnonzero(~fin.any(axis=1)).tolist()),
                         rows_with_data=int(fin.any(axis=1).sum()),
                         max_row_ptp_degC=float(ptp_f.max()),
                         all_finite_rows_constant=bool(np.all(ptp_f == 0)),
                         value_min=float(np.nanmin(th)), value_max=float(np.nanmax(th))))
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    df.to_csv(os.path.join(AUDIT, "E1_cache_shape.csv"), index=False)
    rec("E1_cache_shape", rows)

    # 复算 broken 阈值，证明与缓存一致（不写 cesm 目录）
    members = P6.MEMBERS_P0[:3]
    chunks = []
    for m in members:
        arr, t = load_t2m("XGHG", m)
        chunks.append((arr, t))
    nland = chunks[0][0].shape[1]
    mat = np.concatenate([v for v, _ in chunks], axis=0)
    doy_all = np.concatenate([t.dayofyear.values for _, t in chunks])
    single = single_thresh(doy_all, mat, nland, hw_map=False)
    broken = np.full_like(single, np.nan)
    stack_broken = np.full_like(single, np.nan)
    for d in np.arange(1, 366):
        win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
        stacked = np.concatenate([single[w - 1] for w in win], axis=0)   # 1 维! (11*nland,)
        broken[d - 1] = np.nanpercentile(stacked, 90, axis=0)            # 标量 -> 广播
        stack_broken[d - 1] = np.nanpercentile(
            np.stack([single[w - 1] for w in win], axis=0), 90, axis=0)  # 仅修 axis
    diff_cache = float(np.nanmax(np.abs(broken - thr_t)))
    print(f"\n[复算校验] 复算的 broken 阈值 vs 缓存 npz 最大差 = {diff_cache:.3e}")
    rec("E1_recompute_matches_cache_maxabs_degC", diff_cache)
    print(f"[复算校验] 仅修 axis（逐日分位再分位）后行内 ptp 最大 = "
          f"{float(np.nanmax(np.nanmax(stack_broken, 1) - np.nanmin(stack_broken, 1))):.3f} degC")

    # 正确参考: 3 成员池化 + heatwaveR 语义（11 天窗合并原始样本）
    A_pool = build_A(chunks, nland)
    thr_ref = thresh_from_A(A_pool, half=5, pct=90)

    # 用 R 的权威输出校验参考实现（必须同一条序列: XGHG_001 与 ALL_001 各校一次）
    val = {}
    for exp in ("XGHG", "ALL"):
        rfile = os.path.join(AUDIT, f"R_thr_w11_t2m_{exp}_001.csv")
        if not os.path.exists(rfile):
            continue
        rd = pd.read_csv(rfile, parse_dates=["date"])
        rthr = rd.iloc[:, 1:].values
        arr_e, t_e = load_t2m(exp, "001")
        thr_e = thresh_from_A(build_A([(arr_e, t_e)], nland), half=5, pct=90)
        idxn = t_e.normalize()
        raw_pos = t_e.get_indexer(pd.DatetimeIndex(rd["date"]))
        pos = idxn.get_indexer(pd.DatetimeIndex(rd["date"]).normalize())
        ok = pos >= 0
        mine = thr_e[hw_doy(idxn)[pos[ok]] - 1, :]
        val[exp] = dict(
            n=int(ok.sum()),
            exact_timestamp_match_frac=float((raw_pos >= 0).mean()),
            date_normalized_match_frac=float((pos >= 0).mean()),
            max_abs_diff_degC=float(np.nanmax(np.abs(mine - rthr[ok]))),
            mean_abs_diff_degC=float(np.nanmean(np.abs(mine - rthr[ok]))))
        print(f"\n[参考实现校验] Python 参考 vs R ts2clm({exp}_001, 11天窗): "
              f"n={val[exp]['n']} max|d|={val[exp]['max_abs_diff_degC']:.2e} degC "
              f"mean|d|={val[exp]['mean_abs_diff_degC']:.2e} degC "
              f"(精确时间戳匹配率={val[exp]['exact_timestamp_match_frac']:.3f})")
    rec("E1_ref_impl_validation_vs_R", val)

    def diffstat(a, b, name):
        s = (a[:365] - b[:365])
        s = s[np.isfinite(s)]
        d = np.abs(s)
        return dict(case=name, n=int(d.size), mean_abs_degC=float(d.mean()),
                    signed_mean_degC=float(s.mean()),
                    frac_thresh_too_cold=float((s < 0).mean()),
                    p50=float(np.percentile(d, 50)), p90=float(np.percentile(d, 90)),
                    p99=float(np.percentile(d, 99)), max_degC=float(d.max()),
                    frac_gt_1C=float((d > 1).mean()), frac_gt_2C=float((d > 2).mean()))

    single_hw = single_thresh(np.concatenate([hw_doy(t) for _, t in chunks]),
                              mat, nland, hw_map=True)
    diffs = [diffstat(thr_t, thr_ref, "broken(缓存, 全域同一曲线) vs 正确池化11天窗"),
             diffstat(stack_broken, thr_ref, "仅修axis(逐日分位再分位) vs 正确池化11天窗"),
             diffstat(single, thr_ref, "单日分位(pandas doy, 无窗) vs 正确池化11天窗"),
             diffstat(single_hw, thr_ref, "单日分位(heatwaveR doy, 无窗) vs 正确池化11天窗")]
    dd = pd.DataFrame(diffs)
    print("\n[E1 阈值差分布, degC]")
    print(dd.to_string(index=False))
    dd.to_csv(os.path.join(AUDIT, "E1_threshold_diffs.csv"), index=False)
    rec("E1_threshold_diffs", diffs)

    # 阈值均值 + 逐点偏差范围（与 Lead 的独立实现交叉核对）
    per_point = np.nanmean(thr_t[:365] - thr_ref[:365], axis=0)
    means = dict(broken_degC=float(np.nanmean(thr_t[:365])),
                 axis_fixed_degC=float(np.nanmean(stack_broken[:365])),
                 single_day_pandas_degC=float(np.nanmean(single[:365])),
                 correct_pooled11_degC=float(np.nanmean(thr_ref[:365])),
                 per_point_delta_min_degC=float(per_point.min()),
                 per_point_delta_max_degC=float(per_point.max()),
                 per_point_delta_argmax=int(np.argmax(per_point)),
                 per_point_delta_argmin=int(np.argmin(per_point)))
    print(f"[E1 阈值均值] broken={means['broken_degC']:.3f}  "
          f"仅修axis={means['axis_fixed_degC']:.3f}  "
          f"单日(pandas doy)={means['single_day_pandas_degC']:.3f}  "
          f"正确池化11天窗={means['correct_pooled11_degC']:.3f} degC")
    print(f"[E1 逐点偏差] broken-correct 被抬高最多 {means['per_point_delta_max_degC']:+.2f} degC "
          f"(p{means['per_point_delta_argmax']}), 被压低最多 "
          f"{means['per_point_delta_min_degC']:+.2f} degC (p{means['per_point_delta_argmin']})")
    rec("E1_threshold_means", means)

    # 检测影响（成员 001, ALL 与 XGHG；阈值按 pandas doy 索引, 与被审计代码一致）
    imp = []
    for exp in ("ALL", "XGHG"):
        arr, t = load_t2m(exp, "001")
        for name, th in (("broken(实际v2)", thr_t),
                         ("仅修axis", stack_broken),
                         ("正确池化11天窗", thr_ref)):
            ne, nx, du = count_events(arr, th, t)
            imp.append(dict(exp=exp, member="001", thresh=name, n_events=ne,
                            exceed_days=nx,
                            mean_duration=float(du.mean()) if du.size else np.nan))
        p = os.path.join(CESM_INT, f"thw_x_{exp}_001.csv")
        if os.path.exists(p):
            n = len(pd.read_csv(p))
            k = [i for i, r in enumerate(imp) if r["thresh"].startswith("broken")][-1]
            imp[k]["n_events_in_product"] = n
            print(f"[复算校验] {exp} 001 复算 broken 事件 vs 产物 thw_x_{exp}_001.csv: "
                  f"{imp[k]['n_events']} vs {n}")
            rec(f"E1_recompute_eventcount_{exp}_001",
                dict(recomputed=imp[k]["n_events"], product=n))
    di = pd.DataFrame(imp)
    print("\n[E1 检测影响: 成员 001, 逐点 _run_events]")
    print(di.to_string(index=False))
    di.to_csv(os.path.join(AUDIT, "E1_detection_impact.csv"), index=False)
    rec("E1_detection_impact", imp)
    for exp in ("ALL", "XGHG"):
        g = di[di.exp == exp]
        b = g[g.thresh.str.startswith("broken")].iloc[0]
        c = g[g.thresh.str.startswith("正确")].iloc[0]
        print(f"[E1 倍数] {exp} 001: 事件 broken/correct = {b.n_events}/{c.n_events} "
              f"= {b.n_events / c.n_events:.2f}x;  超标日 {b.exceed_days}/{c.exceed_days} "
              f"= {b.exceed_days / c.exceed_days:.2f}x")
        rec(f"E1_ratio_{exp}_001",
            dict(events_ratio=float(b.n_events / c.n_events),
                 exceed_ratio=float(b.exceed_days / c.exceed_days)))

    # doy=366 缺行的影响: 闰年 12-31 共 6 天 x 206 点 永远不可能超标
    impact366 = {}
    for exp in ("ALL", "XGHG"):
        arr, t = load_t2m(exp, "001")
        doy = t.dayofyear.values
        nanmask = ~np.isfinite(thr_t[doy - 1])
        impact366[f"t2m_{exp}_001"] = dict(
            n_days_doy366=int((doy == 366).sum()), n_point_days_masked=int(nanmask.sum()),
            masked_dates=[str(t[i].date()) for i in np.flatnonzero(nanmask.all(axis=1))])
    v, tsst, _ = P6._load_sst_points("XGHG", "001", PAIRS)
    doys = tsst.dayofyear.values
    nanmask = ~np.isfinite(thr_s[doys - 1])
    impact366["sst_XGHG_001_v2"] = dict(
        n_days_doy366=int((doys == 366).sum()),
        n_point_days_masked=int(nanmask.sum()),
        masked_dates=[str(tsst[i].date()) for i in np.flatnonzero(nanmask.all(axis=1))])
    impact366["sst_ALL_001_v1"] = dict(
        note="v1 自身气候态用 np.unique(doy) 循环, 含 doy=366, 无此缺口", n_points=206)
    print("\n[E1 doy=366 缺行] " + json.dumps(impact366, ensure_ascii=False))
    rec("E1_doy366_impact", impact366)


# =============================================================================
# E2 — MHW 阈值缺 11 天窗
# =============================================================================
def e2():
    sec("E2  MHW 阈值缺 11 天窗（模型侧 Python vs 观测侧 heatwaveR）")
    ev = dict(
        config_MHW_EVENTS_CSV=C.MHW_EVENTS_CSV,
        exists=os.path.exists(C.MHW_EVENTS_CSV),
        n_events=int(len(pd.read_csv(C.MHW_EVENTS_CSV))) if os.path.exists(C.MHW_EVENTS_CSV) else None,
        built_from="python/run_all.py L176-177: detect_events.R(OISST clip) -> mhw_events_R.csv -> globalize -> MHW_EVENTS_CSV",
        detect_events_R_params="ts2clm(pctile=90, windowHalfWidth=5L, smoothPercentile=FALSE) + detect_event(minDuration=5, maxGap=2)",
    )
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    rec("E2_obs_chain", ev)

    members = P6.MEMBERS_P0[:3]
    chunks = []
    for m in members:
        v, t, _ = P6._load_sst_points("XGHG", m, PAIRS)
        chunks.append((v, t))
    npair = chunks[0][0].shape[1]
    mat = np.concatenate([v for v, _ in chunks], axis=0)
    doy_pd = np.concatenate([t.dayofyear.values for _, t in chunks])
    doy_hw = np.concatenate([hw_doy(t) for _, t in chunks])

    thr_sst_ref = thresh_from_A(build_A(chunks, npair))
    single_pd_sst = single_thresh(doy_pd, mat, npair, hw_map=False)   # 实际 v2 口径
    single_hw_sst = single_thresh(doy_hw, mat, npair, hw_map=True)
    thr_sst_broken = np.load(os.path.join(CESM_INT, "thresh_sst_xghg.npz"))["thresh"]

    def dstat(a, b, name):
        s = (a[:365] - b[:365])
        s = s[np.isfinite(s)]
        d = np.abs(s)
        return dict(case=name, n=int(d.size), mean_abs_degC=float(d.mean()),
                    signed_mean_degC=float(s.mean()),
                    frac_thresh_too_cold=float((s < 0).mean()),
                    p50=float(np.percentile(d, 50)), p90=float(np.percentile(d, 90)),
                    p99=float(np.percentile(d, 99)), max_degC=float(d.max()),
                    frac_gt_0p5C=float((d > .5).mean()))

    rows = [dstat(thr_sst_broken, thr_sst_ref,
                  "SST v2实际(单日pandas doy,池化) vs 正确池化11天窗"),
            dstat(single_hw_sst, thr_sst_ref, "SST 单日(heatwaveR doy) vs 正确池化11天窗"),
            dstat(thr_sst_broken, single_hw_sst,
                  "SST v2实际 vs 单日(heatwaveR doy) -- 纯 doy 映射差")]

    for tag in ("t2m_ALL_001_sub24", "sst_ALL_001_sub24"):
        f11 = os.path.join(AUDIT, f"R_thr_w11_{tag}.csv")
        f01 = os.path.join(AUDIT, f"R_thr_w01_{tag}.csv")
        if os.path.exists(f11) and os.path.exists(f01):
            a = pd.read_csv(f11).iloc[:, 1:].values
            b = pd.read_csv(f01).iloc[:, 1:].values
            s = (a - b)
            s = s[np.isfinite(s)]
            d = np.abs(s)
            rows.append(dict(case=f"R ts2clm 官方: {tag} 单日 vs 11天窗 (n={a.shape[1]}点)",
                             n=int(d.size), mean_abs_degC=float(d.mean()),
                             signed_mean_degC=float(s.mean()),
                             frac_thresh_too_cold=float((s < 0).mean()),
                             p50=float(np.percentile(d, 50)), p90=float(np.percentile(d, 90)),
                             p99=float(np.percentile(d, 99)), max_degC=float(d.max()),
                             frac_gt_0p5C=float((d > .5).mean())))
    dfa = pd.DataFrame(rows)
    print("\n[E2(a) SST 阈值差, degC]")
    print(dfa.to_string(index=False))
    dfa.to_csv(os.path.join(AUDIT, "E2_mhw_window_diffs.csv"), index=False)
    rec("E2a_sst_threshold_diffs", rows)

    imp = []
    for exp in ("ALL", "XGHG"):
        v, t, _ = P6._load_sst_points(exp, "001", PAIRS)
        own_single = np.full((366, v.shape[1]), np.nan)
        for d in np.unique(t.dayofyear.values):            # v1 自身气候态口径
            own_single[d - 1] = np.nanpercentile(v[t.dayofyear.values == d], 90, axis=0)
        own_ref = thresh_from_A(build_A([(v, t)], v.shape[1]))   # 同成员 11 天窗
        for name, th in ((f"{exp}-001 自身单日分位(实际v1)", own_single),
                         (f"{exp}-001 自身11天窗(正确)", own_ref),
                         ("XGHG池化单日分位(实际v2)", thr_sst_broken),
                         ("XGHG池化11天窗(正确)", thr_sst_ref)):
            ne, nx, du = count_events(v, th, t)
            imp.append(dict(exp=exp, member="001", thresh=name, n_events=ne,
                            exceed_days=nx,
                            mean_duration=float(du.mean()) if du.size else np.nan))
        p = os.path.join(CESM_INT, f"mhw_{exp}_001.csv")
        if os.path.exists(p):
            fex = pd.read_csv(p)
            k = [i for i, r in enumerate(imp) if r["thresh"].startswith(f"{exp}-001")][0]
            imp[k]["n_events_in_product"] = len(fex)
            imp[k]["exceed_days_in_product"] = int(fex["duration"].sum())
            print(f"[复算校验] {exp} 001 v1 MHW: 复算 {imp[k]['n_events']} vs "
                  f"产物 {len(fex)};  超标日 复算 {imp[k]['exceed_days']} vs "
                  f"产物(时长和) {int(fex['duration'].sum())}")
    di = pd.DataFrame(imp)
    print("\n[E2(a) MHW 检测影响: 成员 001, 逐点 _run_events]")
    print(di.to_string(index=False))
    di.to_csv(os.path.join(AUDIT, "E2_mhw_detection_impact.csv"), index=False)
    rec("E2a_sst_detection_impact", imp)


# =============================================================================
# E3 — _run_events 桥接/过滤顺序 vs heatwaveR proto_event
# =============================================================================
SYNTH_CASES = [
    ("3+2gap+3 (both runs <5)", 30, [10, 11, 12, 15, 16, 17]),
    ("1+2gap+4 (both runs <5)", 30, [10, 13, 14, 15, 16]),
    ("4+2gap+4 (both runs <5)", 30, [10, 11, 12, 13, 16, 17, 18, 19]),
    ("2+2gap+5 (short run at head)", 30, [1, 2, 5, 6, 7, 8, 9]),
    ("5+2gap+4 (2nd run <5)", 30, [10, 11, 12, 13, 14, 17, 18, 19, 20]),
    ("4+2gap+5 (1st run <5)", 30, [10, 11, 12, 13, 16, 17, 18, 19, 20]),
    ("5+2gap+3+2gap+5 (middle <5)", 40, [10, 11, 12, 13, 14, 17, 18, 19, 22, 23, 24, 25, 26]),
    ("5+1gap+5 (gap=1)", 30, [10, 11, 12, 13, 14, 16, 17, 18, 19, 20]),
    ("5+2gap+5 (gap=2, boundary)", 30, [10, 11, 12, 13, 14, 17, 18, 19, 20, 21]),
    ("5+3gap+5 (gap=3 > maxGap)", 30, [10, 11, 12, 13, 14, 18, 19, 20, 21, 22]),
    ("5+2gap+5+2gap+5 (chain)", 40, [10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28]),
    ("6+2gap+6", 40, [10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23]),
    ("10 contiguous (no gap)", 30, list(range(10, 20))),
    ("4 contiguous (<5, single run)", 30, [10, 11, 12, 13]),
    ("5+2gap+2+2gap+5", 40, [10, 11, 12, 13, 14, 17, 18, 21, 22, 23, 24, 25]),
    # 尾部空档吸收 / 头部空档不吸收（proto_event 判据 index_end > 首个种子起点）
    ("TAIL: 5 exc 20-24, n=26 (tail gap=2<=maxGap)", 26, [20, 21, 22, 23, 24]),
    ("TAIL: 5 exc 25-29, n=30 (tail gap=1)", 30, [25, 26, 27, 28, 29]),
    ("TAIL: 5 exc 22-26, n=30 (tail gap=4>maxGap)", 30, [22, 23, 24, 25, 26]),
    ("HEAD: 5 exc 3-7, n=30 (head gap=2, NOT absorbed)", 30, [3, 4, 5, 6, 7]),
    ("HEAD: 5 exc 1-5, n=30 (no head gap)", 30, [1, 2, 3, 4, 5]),
    ("TAIL+HEAD: 5 exc 3-7, n=9 (tail gap=2)", 9, [3, 4, 5, 6, 7]),
]


def sr(_unused, n, exc):
    x = np.zeros(n, bool)
    x[[i - 1 for i in exc]] = True
    return x


def proto_event_replica(crit, min_dur=5, max_gap=2, join=True):
    """按 heatwaveR:::proto_event 函数体逐行复刻（用于独立验证语义）。"""
    def rle(x):
        x = np.asarray(x, bool)
        if x.size == 0:
            return np.array([], int), np.array([], int), np.array([], bool)
        d = np.concatenate(([True], x[:-1] != x[1:], [True]))
        idx = np.flatnonzero(d)
        st, ln = idx[:-1], np.diff(idx)
        return st, ln, x[st]

    n = len(crit)
    crit = np.asarray(crit, bool)
    s, l, v = rle(crit)
    raw = [(int(a), int(a + ln - 1)) for a, ln, vv in zip(s, l, v) if vv]
    if not raw or max(b - a + 1 for a, b in raw) < min_dur:
        return []
    seeds = [(a, b) for a, b in raw if b - a + 1 >= min_dur]
    dc = np.zeros(n, bool)
    for a, b in seeds:
        dc[a:b + 1] = True
    event = dc.copy()
    if join:
        s2, l2, v2 = rle(dc)
        gaps = [(int(a), int(a + ln - 1), int(ln))
                for a, ln, vv in zip(s2, l2, v2) if not vv]
        gaps = [g for g in gaps if g[1] > seeds[0][0]]     # 丢弃头部空档, 保留尾部
        if any(1 <= g[2] <= max_gap for g in gaps):
            for a, b, ln in [g for g in gaps if 1 <= g[2] <= max_gap]:
                event[a:b + 1] = True
    s3, l3, v3 = rle(event)
    return [(int(a), int(a + ln - 1)) for a, ln, vv in zip(s3, l3, v3) if vv]


def _ftb(x, min_dur, max_gap, absorb_head=False, absorb_tail=True):
    """变体: 先按原始游程>=min_dur 过滤出种子, 再桥接 <=max_gap 的空档。
    absorb_head/tail 控制是否也吸收首/尾空档（heatwaveR: 尾吸收、头不吸收）。
    absorb_tail=True 且 absorb_head=False 时应与 proto_event 完全一致。"""
    n = len(x)
    x = np.asarray(x, bool)
    d = np.concatenate(([True], x[:-1] != x[1:], [True]))
    idx = np.flatnonzero(d)
    raw = [(int(a), int(a + ln - 1)) for a, ln in zip(idx[:-1], np.diff(idx)) if x[a]]
    seeds = [(a, b) for a, b in raw if (b - a + 1) >= min_dur]
    if not seeds:
        return []
    m = np.zeros(n, bool)
    for a, b in seeds:
        m[a:b + 1] = True
    nm = ~m
    d3 = np.concatenate(([True], nm[:-1] != nm[1:], [True]))
    idx3 = np.flatnonzero(d3)
    gaps = [(int(a), int(a + ln - 1), int(ln))
            for a, ln in zip(idx3[:-1], np.diff(idx3)) if nm[a]]
    if not absorb_head:
        gaps = [g for g in gaps if g[1] > seeds[0][0]]
    if not absorb_tail:
        gaps = [g for g in gaps if g[1] < n - 1]
    if any(1 <= g[2] <= max_gap for g in gaps):
        for a, b, ln in [g for g in gaps if 1 <= g[2] <= max_gap]:
            m[a:b + 1] = True
    d4 = np.concatenate(([True], m[:-1] != m[1:], [True]))
    idx4 = np.flatnonzero(d4)
    out = []
    for a, ln in zip(idx4[:-1], np.diff(idx4)):
        if m[a]:
            out.append((int(a) + 1, int(a + ln), int(ln)))
    return out


def e3():
    sec("E3  _run_events 的桥接/过滤顺序 vs heatwaveR proto_event")
    rows = []
    for label, n, exc in SYNTH_CASES:
        t = pd.date_range("2001-01-01", periods=n, freq="D")
        ev = P6._run_events(sr(None, n, exc), t, min_dur=5, max_gap=2)
        rows.append(dict(case=label, py_n_events=len(ev),
                         py_durations=";".join(str(b - a + 1) for a, b in ev),
                         py_starts=";".join(str(t[a].date()) for a, b in ev)))
    py = pd.DataFrame(rows)
    rfile = os.path.join(AUDIT, "synth_discriminative.csv")
    if os.path.exists(rfile):
        rr = pd.read_csv(rfile)
        py = py.merge(rr[["case", "n_events", "durations", "starts"]]
                      .rename(columns={"n_events": "R_n_events",
                                       "durations": "R_durations",
                                       "starts": "R_starts"}), on="case", how="left")
        py["verdict"] = np.where(
            (py.py_n_events == py.R_n_events) &
            (py.py_durations == py.R_durations.fillna("")), "等价", "不等价")
    else:
        print("!! 缺 synth_discriminative.csv（先跑 R 脚本）")
    print(py.to_string(index=False))
    py.to_csv(os.path.join(AUDIT, "E3_synth_python.csv"), index=False)
    rec("E3_synth", py.to_dict("records"))

    rows2 = []
    for label, n, exc in SYNTH_CASES:
        t64 = pd.date_range("2001-01-01", periods=n, freq="D").values.astype("datetime64[D]")
        trk = detect_mhw._EventTracker(0, 0, 0.0, 0.0, t64, np.full(366, 0.5), 5, 2)
        for i in range(n):
            trk.feed(i, 1.0 if (i + 1) in exc else 0.0, 0.5)
        trk.flush()
        rows2.append(dict(case=label, tracker_n_events=len(trk.events),
                          tracker_durations=";".join(str(e["duration"]) for e in trk.events)))
    py2 = pd.DataFrame(rows2).merge(py[["case", "py_n_events", "py_durations"]], on="case")
    py2["same_as_run_events"] = (py2.tracker_n_events == py2.py_n_events) & \
        (py2.tracker_durations == py2.py_durations)
    print("\n[观测侧 Python 状态机 detect_mhw._EventTracker 对照]")
    print(py2.to_string(index=False))
    rec("E3_eventtracker_same", bool(py2.same_as_run_events.all()))

    real = []
    for tag in ("t2m_ALL_001", "t2m_XGHG_001"):
        fs = os.path.join(AUDIT, f"series_{tag}.csv")
        ft = os.path.join(AUDIT, f"R_thr_w11_{tag}.csv")
        fe = os.path.join(AUDIT, f"R_ev_{tag}_w11.csv")
        if not all(os.path.exists(p) for p in (fs, ft, fe)):
            continue
        d = pd.read_csv(fs, parse_dates=["date"])
        thr = pd.read_csv(ft, parse_dates=["date"])
        t = pd.DatetimeIndex(d["date"])
        cols = [c for c in d.columns if c != "date"]
        # R 导出的阈值按日期逐行对齐（不是 366 行 doy 索引表），必须逐行取。
        # 若误用 thr[doy-1]，对闰年 3-1 及以后会整体取到次日阈值。
        assert (pd.DatetimeIndex(thr["date"]).values == t.values).all()
        thr_t = thr[cols].values
        vmat = d[cols].values
        py_ev, py_exc = [], 0
        for k in range(len(cols)):
            x = vmat[:, k] > thr_t[:, k]
            x[np.isnan(vmat[:, k])] = False
            py_exc += int(x.sum())
            for a, b in P6._run_events(x, t, 5, 2):
                py_ev.append((cols[k], str(t[a].date()), str(t[b].date()), b - a + 1))
        pe = pd.DataFrame(py_ev, columns=["point", "event_start", "event_end", "duration"])
        re_ = pd.read_csv(fe)
        r_set = set(zip(re_.point, re_.event_start, re_.event_end, re_.duration))
        p_set = set(pe.itertuples(index=False, name=None))
        rd = pd.read_csv(os.path.join(AUDIT, f"R_counts_{tag}.csv"))
        real.append(dict(tag=tag, n_points=len(cols),
                         R_events=len(re_), py_events=len(pe),
                         identical_events=len(r_set & p_set),
                         events_only_R=len(r_set - p_set),
                         events_only_py=len(p_set - r_set),
                         R_exceed_days=int(rd.n_exceed_w11.sum()), py_exceed_days=py_exc,
                         py_extra_pct=100.0 * (len(pe) - len(re_)) / max(len(re_), 1)))
        print(f"\n[E3 真实数据 {tag}] R={len(re_)} 事件, Python={len(pe)} 事件, "
              f"完全一致={len(r_set & p_set)}, 仅R={len(r_set - p_set)}, "
              f"仅Py={len(p_set - r_set)}; 超标日 R={int(rd.n_exceed_w11.sum())} Py={py_exc}")
    if real:
        pd.DataFrame(real).to_csv(os.path.join(AUDIT, "E3_real_comparison.csv"), index=False)
    rec("E3_real", real)


# =============================================================================
# E2c — 缺失 11 天窗对「复合暴露(复合日数)」的传播影响（成员 001）
# =============================================================================
def e2c_compound():
    sec("E2(c)  MHW 缺 11 天窗 -> 复合日数的影响（成员 001，THW 固定为实际产物）")
    from compound_events import _event_daily_mask as _edm, _pair_maps
    lpd = _pair_maps(PAIRS)
    out = []
    for exp in ("ALL", "XGHG"):
        v, t, _ = P6._load_sst_points(exp, "001", PAIRS)
        ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_001_T2m.nc"))
        t0 = pd.Timestamp(ds["T2m"].time.values[0])
        nt = ds.sizes["time"]
        ds.close()
        thw = pd.read_csv(os.path.join(CESM_INT, f"thw_{exp}_001.csv"),
                          parse_dates=["event_start", "event_end"])
        own_single = np.full((366, v.shape[1]), np.nan)
        for d in np.unique(t.dayofyear.values):
            own_single[d - 1] = np.nanpercentile(v[t.dayofyear.values == d], 90, axis=0)
        own_ref = thresh_from_A(build_A([(v, t)], v.shape[1]))
        row = dict(exp=exp, member="001")
        for name, th in (("actual_single_day", own_single), ("correct_11day", own_ref)):
            thr_t = th[t.dayofyear.values - 1]
            rows_ev = []
            for p in range(v.shape[1]):
                x = v[:, p] > thr_t[:, p]
                x[np.isnan(v[:, p])] = False
                for a, b in P6._run_events(x, t, 5, 2):
                    rows_ev.append(dict(lat_idx=int(PAIRS.ocean_lat_idx.iloc[p]),
                                        lon_idx=int(PAIRS.ocean_lon_idx.iloc[p]),
                                        event_start=t[a], event_end=t[b]))
            mev = pd.DataFrame(rows_ev)
            om = {k: _edm(g, nt, t0) for k, g in mev.groupby(["lat_idx", "lon_idx"])} \
                if len(mev) else {}
            kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
            thwc = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
            by = {k: g for k, g in thwc.groupby(["lat_idx", "lon_idx"])}
            comp_days = thw_days = 0
            for lk, ok_ in lpd.items():
                g = by.get(lk)
                if g is None or len(g) == 0:
                    continue
                lm = _edm(g, nt, t0)
                thw_days += int(lm.sum())
                m_ = om.get(ok_)
                comp_days += int((lm & (m_ if m_ is not None else 0)).sum())
            row[f"compound_days_{name}"] = comp_days
            row[f"thw_pair_days_{name}"] = thw_days
            row[f"n_ocean_events_{name}"] = int(len(mev))
        row["compound_ratio"] = row["compound_days_actual_single_day"] / \
            max(row["compound_days_correct_11day"], 1)
        out.append(row)
        print(f"{exp} 001: 复合日 actual(单日)={row['compound_days_actual_single_day']:,} "
              f"vs correct(11天窗)={row['compound_days_correct_11day']:,} "
              f"-> {row['compound_ratio']:.3f}x")
    pd.DataFrame(out).to_csv(os.path.join(AUDIT, "E2c_compound_impact.csv"), index=False)
    rec("E2c_compound_impact", out)


# =============================================================================
# E4 — 游程状态机其它细节 + 头尾空档 + 模糊测试
# =============================================================================
def e4():
    sec("E4  游程状态机细节: 严格大于 / 时长含空档 / 跨年 / NaN")
    det = []
    t = pd.date_range("2001-01-01", periods=20, freq="D")
    for tag, v, thr in (("temp>thresh (1.0 vs 0.5)", 1.0, 0.5),
                        ("temp==thresh 恰好相等 (0.5 vs 0.5)", 0.5, 0.5),
                        ("temp稍小于 (0.4999 vs 0.5)", 0.4999, 0.5)):
        x = np.concatenate([np.full(6, v) > thr, np.zeros(14, bool)])
        ev = P6._run_events(x, t, 5, 2)
        det.append(dict(item="严格大于", case=tag, py_n_events=len(ev),
                        note="heatwaveR detect_event 源码: !is.na(ts_y) & ts_y > ts_thresh"))

    x = np.zeros(30, bool)
    x[[9, 10, 11, 12, 13, 16, 17, 18, 19, 20]] = True
    ev = P6._run_events(x, t[:30], 5, 2)
    det.append(dict(item="时长含空档", case="5+2gap+5", py_n_events=len(ev),
                    py_duration=str([b - a + 1 for a, b in ev]),
                    note="R 合成实验实测 duration=12"))

    t2 = pd.date_range("2001-12-28", periods=8, freq="D")
    ev2 = P6._run_events(np.ones(8, bool), t2, 5, 2)
    det.append(dict(item="跨年不切分", case="2001-12-28..2002-01-04 连续 8 天",
                    py_n_events=len(ev2),
                    py_duration=str([b - a + 1 for a, b in ev2]),
                    note="_run_events 在整条序列上跑; heatwaveR proto_event 亦无年份切分"))

    x = np.zeros(30, bool)
    x[10:20] = True
    x[14] = np.nan
    xa = x.astype(bool)
    xa[np.isnan(x)] = False
    ev = P6._run_events(xa, t[:30], 5, 2)
    det.append(dict(item="NaN temp", case="NaN 夹在事件中间", py_n_events=len(ev),
                    py_duration=str([b - a + 1 for a, b in ev]),
                    note="Python: x[isnan(vals)]=False -> 算作空档; "
                         "R: NA temp 先被 seas 覆盖后判 seas>thresh"))

    thr = np.full(30, 0.5)
    thr[15:18] = np.nan
    ev = P6._run_events(np.full(30, 1.0) > thr, t[:30], 5, 2)
    det.append(dict(item="阈值 NaN", case="阈值 NaN 3 天", py_n_events=len(ev),
                    py_duration=str([b - a + 1 for a, b in ev]),
                    note="Python: NaN 比较为 False -> 空档; R 会产生 NA 判据"))
    d = pd.DataFrame(det)
    print(d.to_string(index=False))
    d.to_csv(os.path.join(AUDIT, "E4_details.csv"), index=False)
    rec("E4_details", det)

    # 尾部空档吸收的独立显式验证（heatwaveR 权威 vs _run_events vs 复刻）
    sec("E4b  proto_event 的头部/尾部空档不对称（Lead 提示的关键点，独立复核）")
    tail = []
    for label, n, exc in SYNTH_CASES[15:]:
        x = sr(None, n, exc)
        t = pd.date_range("2001-01-01", periods=n, freq="D")
        py = [(str(t[a].date()), str(t[b].date()), b - a + 1)
              for a, b in P6._run_events(x, t, 5, 2)]
        rep = [(str(t[a].date()), str(t[b].date()), b - a + 1)
               for a, b in proto_event_replica(x, 5, 2)]
        tail.append(dict(case=label, n=len(x), n_exceed=len(exc), py_run_events=py,
                         proto_replica=rep))
    dt = pd.DataFrame(tail)
    rfile = os.path.join(AUDIT, "synth_discriminative.csv")
    if os.path.exists(rfile):
        rr = pd.read_csv(rfile).set_index("case")

        def r_tuples(case):
            if case not in rr.index:
                return None
            row = rr.loc[case]
            if int(row.n_events) == 0:
                return []
            return [(s, e, int(du)) for s, e, du in
                    zip(str(row.starts).split(";"), str(row.ends).split(";"),
                        str(row.durations).split(";"))]
        dt["R_events"] = dt.case.map(r_tuples)
        dt["replica_matches_R"] = dt.apply(lambda r: r.R_events == r.proto_replica, axis=1)
        dt["run_events_matches_R"] = dt.apply(lambda r: r.R_events == r.py_run_events, axis=1)
    print(dt.to_string(index=False))
    dt.to_csv(os.path.join(AUDIT, "E4b_tail_head_gap.csv"), index=False)
    rec("E4b_tail_head", dt.to_dict("records"))

    e4c_fuzz()


def e4c_fuzz():
    sec("E4c  模糊测试: 各实现变体 vs 真实 heatwaveR（含头/尾空档非对称性）")
    ff = os.path.join(AUDIT, "fuzz_R.csv")
    if not os.path.exists(ff):
        print("!! 缺 fuzz_R.csv（需先跑 R 脚本 MODE=fuzz）")
        return
    fc = pd.read_csv(os.path.join(AUDIT, "fuzz_cases.csv"))
    fr = pd.read_csv(ff)
    summ = []
    for (md, mg), g in fr.groupby(["min_dur", "max_gap"]):
        c = dict.fromkeys(["A_run_events", "B_proto_replica", "C_ftb_plain",
                           "D_ftb_tail", "E_ftb_head_tail"], 0)
        for _, r in fc.iterrows():
            x = np.array([ch == "1" for ch in r.pattern], bool)
            t = pd.date_range("2001-01-01", periods=r.n, freq="D")
            sub = g[g.case == r.case]
            if len(sub) == 0:
                continue
            row = sub.iloc[0]
            R = [] if (pd.isna(row.n_events) or int(row.n_events) == 0) else [
                (int(s), int(e), int(du)) for s, e, du in
                zip(str(row.starts).split(";"), str(row.ends).split(";"),
                    str(row.durations).split(";"))]
            A = [(a + 1, b + 1, b - a + 1) for a, b in P6._run_events(x, t, int(md), int(mg))]
            B = [(a + 1, b + 1, b - a + 1) for a, b in proto_event_replica(x, int(md), int(mg))]
            C = _ftb(x, int(md), int(mg), absorb_tail=False)
            D = _ftb(x, int(md), int(mg), absorb_tail=True)
            E = _ftb(x, int(md), int(mg), absorb_head=True, absorb_tail=True)
            for k, v in (("A_run_events", A), ("B_proto_replica", B), ("C_ftb_plain", C),
                         ("D_ftb_tail", D), ("E_ftb_head_tail", E)):
                c[k] += int(v != R)
        summ.append(dict(min_dur=int(md), max_gap=int(mg), n_cases=len(fc), **c))
    ds = pd.DataFrame(summ)
    print(ds.to_string(index=False))
    print("\n  A=_run_events(先桥接后过滤)  B=proto_event 逐行复刻  "
          "C=先过滤后桥接(头尾都不吸收)\n  D=先过滤后桥接+尾吸收(头不吸收, 应=heatwaveR)  "
          "E=C+头尾都吸收")
    ds.to_csv(os.path.join(AUDIT, "E3_fuzz_summary.csv"), index=False)
    rec("E3_fuzz", summ)


# =============================================================================
# E5 — 与观测侧 detect_events.R 的其它参数差异
# =============================================================================
def e5():
    sec("E5  v1/v2 参数差异表 + min_valid=730 影响")
    obs_clim = (1983, 2012)
    rows = [
        dict(chain="观测-海洋 MHW", detector="R detect_events.R (heatwaveR)",
             pctile=90, window="11天窗", smoothPercentile=False,
             clim=f"{obs_clim[0]}-{obs_clim[1]}", min_dur=5, max_gap=2,
             min_valid=730, run_order="先过滤后桥接(heatwaveR proto_event)",
             source="config.MHW_EVENTS_CSV=intermediate/mhw_events_R_global.csv"),
        dict(chain="观测-陆地 THW", detector="R detect_events.R (heatwaveR)",
             pctile=90, window="11天窗", smoothPercentile=False,
             clim=f"{obs_clim[0]}-{obs_clim[1]}", min_dur=5, max_gap=2,
             min_valid=730, run_order="先过滤后桥接",
             source="config.THW_EVENTS_CSV=intermediate/thw_events_R.csv"),
        dict(chain="模型 v1-海洋 MHW", detector="Python _detect_mhw_member",
             pctile=90, window="单日(无窗)", smoothPercentile="n/a",
             clim="成员自身 2000-2021", min_dur=5, max_gap=2,
             min_valid="无", run_order="先桥接后过滤(_run_events)",
             source="phase6_cesm.py L336-378"),
        dict(chain="模型 v1-陆地 THW", detector="R detect_events.R (heatwaveR)",
             pctile=90, window="11天窗", smoothPercentile=False,
             clim="2000-2021", min_dur=5, max_gap=2,
             min_valid=730, run_order="先过滤后桥接",
             source="phase6_cesm.py L381-403（与观测侧同代码, 仅气候期不同）"),
        dict(chain="模型 v2-海洋 MHW", detector="Python _detect_mhw_member(thresh_ext)",
             pctile=90, window="单日(无窗)", smoothPercentile="n/a",
             clim="XGHG 3成员池化 2000-2021", min_dur=5, max_gap=2,
             min_valid="无", run_order="先桥接后过滤(_run_events)",
             source="phase6_cesm.py L274-295 + L336-378"),
        dict(chain="模型 v2-陆地 THW", detector="Python _detect_thw_member_ext",
             pctile=90, window="11天窗(写法有误)", smoothPercentile="n/a",
             clim="XGHG 3成员池化 2000-2021", min_dur=5, max_gap=2,
             min_valid="无", run_order="先桥接后过滤(_run_events)",
             source="phase6_cesm.py L298-333 + L406-444"),
    ]
    d = pd.DataFrame(rows)
    print(d.to_string(index=False))
    d.to_csv(os.path.join(AUDIT, "E5_param_diff.csv"), index=False)
    rec("E5_param_diff", rows)

    stats = {}
    for exp in ("ALL", "XGHG"):
        for m in ("001", "002", "003"):
            arr, t = load_t2m(exp, m)
            valid = np.isfinite(arr).sum(axis=0)
            stats[f"T2m_{exp}_{m}"] = dict(
                min_valid_days=int(valid.min()), max_valid_days=int(valid.max()),
                n_points_below_730=int((valid < 730).sum()))
            v, ts, _ = P6._load_sst_points(exp, m, PAIRS)
            vs = np.isfinite(v).sum(axis=0)
            stats[f"SST_{exp}_{m}"] = dict(
                min_valid_days=int(vs.min()), max_valid_days=int(vs.max()),
                n_points_below_730=int((vs < 730).sum()))
    print("\n[min_valid=730 影响: 模型域内有效日数]")
    for k, v in stats.items():
        print(f"  {k}: 最少有效日={v['min_valid_days']}  <730 的点数={v['n_points_below_730']}")
    rec("E5_min_valid", stats)


# =============================================================================
# A1/A2 — 附加: 时间轴 12:00 / 缺日 导致的掩码偏移
# =============================================================================
def a1_extra():
    sec("A1（附加发现）时间轴不一致导致的日期-索引偏移")
    out = {}
    from compound_events import _event_daily_mask
    for exp in ("ALL", "XGHG"):
        ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_001_T2m.nc"))
        t0 = pd.Timestamp(ds["T2m"].time.values[0])
        nt = ds.sizes["time"]
        ds.close()
        v, tsst, _ = P6._load_sst_points(exp, "001", PAIRS)
        starts = {}
        for k, f in (("mhw", f"mhw_{exp}_001.csv"), ("mhw_x", f"mhw_x_{exp}_001.csv"),
                     ("thw", f"thw_{exp}_001.csv"), ("thw_x", f"thw_x_{exp}_001.csv")):
            starts[k] = str(pd.read_csv(os.path.join(CESM_INT, f))["event_start"].iloc[0])
        res = dict(t0=str(t0), n_days_t2m=nt, n_days_sst=len(tsst),
                   sst_missing_days=[str(x.date()) for x in
                                     pd.date_range("2000-01-01", "2021-12-31").difference(tsst)
                                     if not (x.month == 2 and x.day == 29)],
                   raw_event_start=starts)
        for k, s in starts.items():
            one = pd.DataFrame([dict(lat_idx=0, lon_idx=0,
                                     event_start=pd.Timestamp(s), event_end=pd.Timestamp(s))])
            m = _event_daily_mask(one, nt, t0)
            idx = int(np.flatnonzero(m)[0]) if m.any() else -1
            true_idx = int((pd.Timestamp(s).normalize() - t0.normalize()).days)
            res[f"mask_index_{k}"] = idx
            res[f"true_calendar_index_{k}"] = true_idx
            res[f"mask_shift_days_{k}"] = idx - true_idx
        out[exp] = res
        print(f"\n{exp}: t0={t0}  T2m天数={nt}  SST天数={len(tsst)}")
        print(f"   SST 非 Feb-29 缺日: {res['sst_missing_days']}")
        print(f"   各事件表首行 event_start: {starts}")
        print(f"   _event_daily_mask 落点 vs 真实日历索引 (负=掩码偏早): "
              f"{ {k: res[f'mask_shift_days_{k}'] for k in starts} }")
    pd.DataFrame([dict(exp=k, **{kk: str(vv) for kk, vv in v.items()})
                  for k, v in out.items()]).to_csv(
        os.path.join(AUDIT, "A1_mask_shift.csv"), index=False)
    rec("A1_time_axis", out)

    sec("A2（附加发现）掩码偏移对复合日数的影响")
    from compound_events import _event_daily_mask as _edm, _pair_maps
    lpd = _pair_maps(PAIRS)
    comp = []
    for exp in ("ALL", "XGHG"):
        for tag in ("", "_x"):
            fthw = os.path.join(CESM_INT, f"thw{tag}_{exp}_001.csv")
            fmhw = os.path.join(CESM_INT, f"mhw{tag}_{exp}_001.csv")
            if not (os.path.exists(fthw) and os.path.exists(fmhw)):
                continue
            ds = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_001_T2m.nc"))
            t0 = pd.Timestamp(ds["T2m"].time.values[0])
            nt = ds.sizes["time"]
            ds.close()
            thw = pd.read_csv(fthw, parse_dates=["event_start", "event_end"])
            mhw = pd.read_csv(fmhw, parse_dates=["event_start", "event_end"])
            out_row = dict(exp=exp, variant="v1" if tag == "" else "v2", t0=str(t0), nt=nt)
            for name, t0x in (("actual", t0), ("aligned", t0.normalize())):
                om = {k: _edm(g, nt, t0x) for k, g in mhw.groupby(["lat_idx", "lon_idx"])}
                kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
                thwc = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
                by = {k: g for k, g in thwc.groupby(["lat_idx", "lon_idx"])}
                cd = 0
                for lk, ok_ in lpd.items():
                    g = by.get(lk)
                    if g is None or len(g) == 0:
                        continue
                    lm = _edm(g, nt, t0x)
                    m_ = om.get(ok_)
                    cd += int((lm & (m_ if m_ is not None else 0)).sum())
                out_row[f"compound_days_{name}"] = cd
            out_row["delta_pct"] = 100.0 * (out_row["compound_days_aligned"] -
                                            out_row["compound_days_actual"]) / \
                max(out_row["compound_days_actual"], 1)
            comp.append(out_row)
    if comp:
        dc = pd.DataFrame(comp)
        print(dc.to_string(index=False))
        dc.to_csv(os.path.join(AUDIT, "A2_compound_mask_shift.csv"), index=False)
        rec("A2_compound_mask_shift", comp)


# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-r", action="store_true")
    ap.add_argument("--rmode", default="all", help="all | fuzz | force")
    ap.add_argument("--only", default="",
                    help="逗号分隔: export,fuzz,r,e1,e2,e3,e4,e4c,e5,a1")
    a = ap.parse_args()
    only = set(x.strip() for x in a.only.split(",") if x.strip())

    def want(k):
        return (not only) or (k in only)

    if want("export"):
        export_series()
    if want("fuzz"):
        sec("阶段 0b  生成模糊测试用例")
        gen_fuzz()
    if want("r") and not a.skip_r:
        run_r(a.rmode)
    if want("e1"):
        e1()
    if want("e2"):
        e2()
    if want("e2c"):
        e2c_compound()
    if want("e3"):
        e3()
    if want("e4"):
        e4()
    if want("e4c"):
        e4c_fuzz()
    if want("e5"):
        e5()
    if want("a1"):
        a1_extra()

    with open(os.path.join(AUDIT, "audit_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(RES, fh, ensure_ascii=False, indent=2, default=str)
    print(f"\n== 汇总已写出 -> {os.path.join(AUDIT, 'audit_summary.json')} ==")


if __name__ == "__main__":
    main()
