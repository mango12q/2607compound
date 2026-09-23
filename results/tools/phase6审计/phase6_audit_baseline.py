# -*- coding: utf-8 -*-
"""
phase6_audit_baseline.py — task-3 审计脚本
「阈值基准期审计：XGHG 合并基准的 in-sample 偏差、exclude_member 支持、LOO 复算」

用法:
    python results/phase6_audit_baseline.py g1      # 静态证据 + 缓存指纹实测
    python results/phase6_audit_baseline.py g2      # T2m 轴崩溃根因 + 日历/池覆盖
    python results/phase6_audit_baseline.py g3      # 论文原文证据摘录
    python results/phase6_audit_baseline.py chain   # 复现现状 + LOO/in-sample 场景对比
    python results/phase6_audit_baseline.py all

产物一律写入 results/intermediate/audit/baseline/；
**不修改 results/intermediate/cesm/ 下任何文件**（阈值/事件表全部写 audit 目录）。
"""
import argparse
import contextlib
import io
import json
import os
import re
import sys
import time as _t
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = r"D:\2607compound"
PYDIR = os.path.join(ROOT, "python")
AUDIT = os.path.join(ROOT, "results", "intermediate", "audit", "baseline")
SRC = os.path.join(PYDIR, "phase6_cesm.py")
os.makedirs(AUDIT, exist_ok=True)
sys.path.insert(0, PYDIR)

import phase6_cesm as P6  # noqa: E402
import config as C  # noqa: E402
import xarray as xr  # noqa: E402
from compound_events import (  # noqa: E402
    identify_compound_events, _pair_maps, _event_daily_mask)

PAIRS = pd.read_csv(P6.PAIRS_CSV)
MEMBERS = list(P6.MEMBERS_P0)          # ['001','002','003']
OTHERS = {m: [x for x in MEMBERS if x != m] for m in MEMBERS}
MED = (PAIRS.land_lat.between(30, 47) & PAIRS.land_lon.between(5, 42)).values


def jdump(obj, name):
    p = os.path.join(AUDIT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    print(f"  -> {p}")
    return p


def noleap_doy(idx):
    """noleap 年内序号 1..365。

    数据是 noleap 日历（无 2 月 29 日），但被解码成 datetime64 后 pandas 按
    **公历**算 dayofyear：闰年 3 月 1 日 -> 61（非闰年 -> 60），故 12 月 31 日
    在闰年是 366。本函数扣掉闰年 2 月 29 日的占位，得到全程一致的 1..365。
    """
    d = (idx - pd.to_datetime(idx.year.astype(str) + "-01-01")).days.values + 1
    leap = pd.DatetimeIndex(pd.to_datetime(idx.year.astype(str) + "-01-01")).is_leap_year
    return d - (leap & (idx.month > 2)).astype(int)


# ══════════════════════════════════════════════════════════════
# G1: exclude_member 支持 / 缓存指纹
# ══════════════════════════════════════════════════════════════
def stage_g1():
    print("== G1 静态证据 ==")
    src = open(SRC, encoding="utf-8").read().splitlines()
    out = {}

    pat = re.compile(r"exclude_member|leave[-_ ]?one[-_ ]?out|\bloo\b|LOO", re.I)
    hits = [(i + 1, ln.strip()) for i, ln in enumerate(src) if pat.search(ln)]
    out["keyword_hits_phase6"] = hits
    print(f"[G1-1] phase6_cesm.py 中 exclude_member/LOO 命中: {len(hits)} 处")
    for i, ln in hits:
        print(f"    L{i}: {ln}")

    out["cache_read_sst"] = {"lines": "276-279", "code": src[275:279]}
    out["cache_read_t2m"] = {"lines": "300-303", "code": src[299:303]}
    for f in ("thresh_sst_xghg.npz", "thresh_t2m_xghg.npz"):
        z = np.load(os.path.join(P6.CESM_INT, f))
        out[f"npz_keys_{f}"] = list(z.keys())
        print(f"[G1-2] {f}: keys={list(z.keys())}  (无 members / n_members 指纹)")

    orig_load = P6._load_sst_points

    def boom(*a, **k):
        raise AssertionError("_load_sst_points 被调用 => 缓存未命中")

    P6._load_sst_points = boom
    try:
        buf = io.StringIO()
        t0 = _t.time()
        with contextlib.redirect_stdout(buf):
            thr_fake, _ = P6._pooled_threshold_sst(PAIRS, ["999"])
        dt = _t.time() - t0
        sst_msg = (f"members=['999'] 仍成功返回 (耗时 {dt*1000:.0f} ms, "
                   f"stdout={buf.getvalue()!r} -> 无任何提示)")
        sst_ok = True
    except Exception as e:  # noqa: BLE001
        sst_ok, sst_msg = False, f"异常: {e!r}"
    finally:
        P6._load_sst_points = orig_load
    z = np.load(os.path.join(P6.CESM_INT, "thresh_sst_xghg.npz"))
    out["sst_cache_reuse"] = {
        "ok": sst_ok, "msg": sst_msg,
        "identical_to_disk": bool(np.array_equal(np.nan_to_num(thr_fake, nan=-999),
                                                 np.nan_to_num(z["thresh"], nan=-999)))}
    print(f"[G1-3] SST 缓存复用实测: {sst_msg}")
    print(f"        与磁盘 npz 逐位一致: {out['sst_cache_reuse']['identical_to_disk']}")

    buf = io.StringIO()
    t0 = _t.time()
    with contextlib.redirect_stdout(buf):
        thr_t2m_fake = P6._pooled_threshold_t2m(PAIRS, ["999"])
    dt = _t.time() - t0
    z2 = np.load(os.path.join(P6.CESM_INT, "thresh_t2m_xghg.npz"))
    out["t2m_cache_reuse"] = {
        "ok": True,
        "msg": (f"members=['999'] 仍成功返回 (耗时 {dt*1000:.0f} ms, "
                f"stdout={buf.getvalue()!r} -> 无任何提示)"),
        "identical_to_disk": bool(np.array_equal(np.nan_to_num(thr_t2m_fake, nan=-999),
                                                np.nan_to_num(z2["thresh"], nan=-999)))}
    print(f"[G1-4] T2m 缓存复用实测: {out['t2m_cache_reuse']['msg']}")
    print(f"        与磁盘 npz 逐位一致: {out['t2m_cache_reuse']['identical_to_disk']}")

    out["members"] = {
        "CESM_ALL_MEMBERS": C.CESM_ALL_MEMBERS,
        "CESM_P0_MEMBERS": C.CESM_P0_MEMBERS,
        "MEMBERS_P0": MEMBERS,
        "MEMBERS_P0[:20]": list(P6.MEMBERS_P0[:20]),
        "n20": len(P6.MEMBERS_P0[:20]),
        "source_line60": src[59].strip()}
    print(f"[G1-5] MEMBERS_P0 = C.CESM_ALL_MEMBERS[:{C.CESM_P0_MEMBERS}] -> {MEMBERS}")
    print(f"       MEMBERS_P0[:20] -> {len(P6.MEMBERS_P0[:20])} 个 ({P6.MEMBERS_P0[:20][0]}.."
          f"{P6.MEMBERS_P0[:20][-1]})  (取前 N 个, 非显式名单)")
    jdump(out, "g1_cache_and_members.json")
    return out


# ══════════════════════════════════════════════════════════════
# 阈值构造（与 phase6_cesm.py 同逻辑；buggy / fixed 两版）
# ══════════════════════════════════════════════════════════════
def build_sst_thresh(mats, doys):
    """= _pooled_threshold_sst 主体（逐 doy 单日 90 分位；无窗）。"""
    doy_all = np.concatenate(doys)
    mat = np.concatenate(mats, axis=0)
    thresh = np.full((366, mat.shape[1]), np.nan)
    for d in np.arange(1, 366):
        rows = mat[doy_all == d]
        if len(rows):
            thresh[d - 1] = np.nanpercentile(rows, 90, axis=0)
    return thresh


def build_t2m_thresh(mats, doys, buggy=True):
    """= _pooled_threshold_t2m 主体。

    buggy=True  : 原文 L329 `np.concatenate([...], axis=0)` 把 11 个 (npair,) 拼成
                  1-D，再 `nanpercentile(..., axis=0)` 得**标量** -> 广播到整行
                  => 全部陆点共用一条曲线（空间均匀阈值）。
    buggy=False : 堆成 (11, npair) 后逐列取分位（每点各自阈值，= heatwaveR 语义）。
    """
    doy_all = np.concatenate(doys)
    mat = np.concatenate(mats, axis=0)
    nland = mat.shape[1]
    single = np.full((366, nland), np.nan)
    for d in np.arange(1, 366):
        rows = mat[doy_all == d]
        if len(rows):
            single[d - 1] = np.nanpercentile(rows, 90, axis=0)
    thresh = np.full_like(single, np.nan)
    for d in np.arange(1, 366):
        win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
        if buggy:
            stacked = np.concatenate([single[w - 1] for w in win], axis=0)
        else:
            stacked = np.concatenate([single[w - 1][np.newaxis, :] for w in win], axis=0)
        thresh[d - 1] = np.nanpercentile(stacked, 90, axis=0)
    return thresh, single


# ══════════════════════════════════════════════════════════════
# 数据加载（缓存到 audit 目录）
# ══════════════════════════════════════════════════════════════
def load_sst(exp, m):
    p = os.path.join(AUDIT, f"sst_{exp}_{m}.npz")
    if os.path.exists(p):
        z = np.load(p)
        return z["vals"].astype(np.float64), pd.DatetimeIndex(z["time"])
    vals, time, _ = P6._load_sst_points(exp, m, PAIRS)
    np.savez_compressed(p, vals=vals.astype(np.float32), time=time.values)
    return vals, time


def load_t2m(exp, m):
    p = os.path.join(AUDIT, f"t2m_{exp}_{m}.npz")
    if os.path.exists(p):
        z = np.load(p)
        return z["arr"].astype(np.float64), pd.DatetimeIndex(z["time"])
    f = os.path.join(P6.CESM_INT, f"{exp}_{m}_T2m.nc")
    ds = xr.open_dataset(f)
    da = ds["T2m"].isel(lat=xr.DataArray(PAIRS.land_lat_idx.values, dims="p"),
                        lon=xr.DataArray(PAIRS.land_lon_idx.values, dims="p"))
    arr = da.transpose("time", "p").values.astype(np.float64)
    time = pd.DatetimeIndex(da.time.values)
    ds.close()
    np.savez_compressed(p, arr=arr.astype(np.float32), time=time.values)
    return arr, time


# ══════════════════════════════════════════════════════════════
# 检测 / 复合（与 phase6_cesm.py 同逻辑，输出到 audit 目录）
# ══════════════════════════════════════════════════════════════
def detect_mhw(vals, time, thresh, tag=None):
    """= _detect_mhw_member 主体（外置阈值分支）。"""
    thr_t = thresh[time.dayofyear.values - 1]
    events = []
    for p in range(vals.shape[1]):
        x = vals[:, p] > thr_t[:, p]
        x[np.isnan(vals[:, p])] = False
        for a, b in P6._run_events(x, time):
            events.append({"event_start": time[a], "event_end": time[b],
                           "duration": int(b - a + 1),
                           "lat_idx": int(PAIRS.ocean_lat_idx.iloc[p]),
                           "lon_idx": int(PAIRS.ocean_lon_idx.iloc[p]),
                           "lat": float(PAIRS.ocean_lat.iloc[p]),
                           "lon": float(PAIRS.ocean_lon.iloc[p])})
    df = pd.DataFrame(events)
    if tag:
        df.to_csv(os.path.join(AUDIT, f"mhw_{tag}.csv"), index=False)
    return df


def detect_thw(arr, time, thresh, tag=None):
    """= _detect_thw_member_ext 主体（外置阈值分支）。"""
    thr_t = thresh[time.dayofyear.values - 1]
    events = []
    for p in range(arr.shape[1]):
        x = arr[:, p] > thr_t[:, p]
        x[np.isnan(arr[:, p])] = False
        for a, b in P6._run_events(x, time):
            events.append({"event_start": time[a], "event_end": time[b],
                           "duration": int(b - a + 1),
                           "lat_idx": int(PAIRS.land_lat_idx.iloc[p]),
                           "lon_idx": int(PAIRS.land_lon_idx.iloc[p]),
                           "lat": float(PAIRS.land_lat.iloc[p]),
                           "lon": float(PAIRS.land_lon.iloc[p])})
    df = pd.DataFrame(events)
    if tag:
        df.to_csv(os.path.join(AUDIT, f"thw_{tag}.csv"), index=False)
    return df


def exceed_days(vals, time, thresh):
    x = vals > thresh[time.dayofyear.values - 1]
    x[np.isnan(vals)] = False
    return int(x.sum())


def compound_chain(mhw, thw, time_t2m, tag=None):
    """= cmd_compound 的逐日口径 + _annual_per_pair。"""
    time_da = xr.DataArray(np.zeros(len(time_t2m), dtype=np.int8), dims="time",
                           coords={"time": time_t2m})
    # 注意: identify_compound_events 内部用 time.values[0] 取 t0, 必须传**坐标**(xr 的 .time),
    # 与 cmd_compound 的 `identify_compound_events(..., time_da.time)` 一致。
    comp = identify_compound_events(mhw, thw, PAIRS, time_da.time)
    if tag:
        comp.to_csv(os.path.join(AUDIT, f"compound_{tag}.csv"), index=False)
    t0 = pd.Timestamp(time_t2m[0])
    nt = len(time_t2m)
    lpd = _pair_maps(PAIRS)
    om = {k: _event_daily_mask(g, nt, t0)
          for k, g in mhw.groupby(["lat_idx", "lon_idx"])}
    kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
    thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner") if len(thw) else thw
    thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])} if len(thw_co) else {}
    comp_days = std_days = thw_days = 0
    for lk, ok_ in lpd.items():
        g = thw_by.get(lk)
        if g is None or len(g) == 0:
            continue
        lm = _event_daily_mask(g, nt, t0)
        thw_days += int(lm.sum())
        m_ = om.get(ok_)
        comp_days += int((lm & (m_ if m_ is not None else 0)).sum())
        std_days += int((lm & ~(m_ if m_ is not None else np.zeros(nt, bool))).sum())
    ann = P6._annual_per_pair(comp, time_da, PAIRS)
    if tag:
        ann.to_csv(os.path.join(AUDIT, f"annual_{tag}.csv"), index=False)
    expo = {"compound_days": comp_days, "standalone_days": std_days,
            "thw_pair_days": thw_days, "n_compound_segments": len(comp)}
    return expo, ann, comp


# ══════════════════════════════════════════════════════════════
# G2: T2m 轴崩溃根因 + 日历/池覆盖
# ══════════════════════════════════════════════════════════════
def stage_g2():
    print("== G2 T2m 轴崩溃根因 + 日历/池覆盖 ==")
    res = {}

    a = np.arange(3.0)
    res["minimal_repro"] = {
        "concat_axis0_shape_of_11x206": list(np.concatenate([a] * 11, axis=0).shape),
        "nanpercentile_axis0_is_scalar": bool(np.isscalar(
            np.nanpercentile(np.concatenate([a] * 11, axis=0), 90, axis=0))),
        "stack_shape": list(np.concatenate([a[np.newaxis, :]] * 11, axis=0).shape)}
    print(f"[G2-1] 极简复现: 11 个 (206,) 经 concatenate(axis=0) -> "
          f"{res['minimal_repro']['concat_axis0_shape_of_11x206']} (1-D)，"
          f"nanpercentile(axis=0) 返回标量 -> 赋值 thresh[d-1] 时广播到整行 206 列")

    mats, doys, smats, sdoys = [], [], [], []
    for m in MEMBERS:
        v, t = load_sst("XGHG", m)
        smats.append(v)
        sdoys.append(t.dayofyear.values)
        a_, t_ = load_t2m("XGHG", m)
        mats.append(a_)
        doys.append(t_.dayofyear.values)
    thr_sst = build_sst_thresh(smats, sdoys)
    thr_bug, single = build_t2m_thresh(mats, doys, buggy=True)
    thr_fix, _ = build_t2m_thresh(mats, doys, buggy=False)
    z = np.load(os.path.join(P6.CESM_INT, "thresh_sst_xghg.npz"))
    z2 = np.load(os.path.join(P6.CESM_INT, "thresh_t2m_xghg.npz"))
    res["sst_repro_bitexact"] = bool(np.array_equal(
        np.nan_to_num(thr_sst, nan=-999), np.nan_to_num(z["thresh"], nan=-999)))
    res["t2m_repro_bitexact"] = bool(np.array_equal(
        np.nan_to_num(thr_bug, nan=-999), np.nan_to_num(z2["thresh"], nan=-999)))
    print(f"[G2-2] 复算=磁盘: SST {res['sst_repro_bitexact']}  T2m(buggy) "
          f"{res['t2m_repro_bitexact']}  => 磁盘 npz 即现码产物, 根因定位完整")
    np.savez_compressed(os.path.join(AUDIT, "thresh_sst_3mem_repro.npz"), thresh=thr_sst)
    np.savez_compressed(os.path.join(AUDIT, "thresh_t2m_3mem_buggy.npz"), thresh=thr_bug)
    np.savez_compressed(os.path.join(AUDIT, "thresh_t2m_3mem_fixed.npz"), thresh=thr_fix)

    def rowspan(t):
        return np.nanmax(t, axis=1) - np.nanmin(t, axis=1)

    res["structure"] = {
        "t2m_buggy_row_ptp_max": float(np.nanmax(rowspan(thr_bug))),
        "t2m_buggy_n_unique": int(len(np.unique(thr_bug[~np.isnan(thr_bug)]))),
        "t2m_fixed_row_ptp_median": float(np.nanmedian(rowspan(thr_fix))),
        "t2m_fixed_row_ptp_p95": float(np.nanpercentile(rowspan(thr_fix), 95)),
        "sst_row_ptp_median": float(np.nanmedian(rowspan(thr_sst))),
        "sst_row_ptp_p95": float(np.nanpercentile(rowspan(thr_sst), 95)),
        "t2m_npz_bytes": os.path.getsize(os.path.join(P6.CESM_INT, "thresh_t2m_xghg.npz")),
        "sst_npz_bytes": os.path.getsize(os.path.join(P6.CESM_INT, "thresh_sst_xghg.npz"))}
    d = thr_fix - thr_bug
    res["t2m_fixed_minus_buggy"] = {
        "mean": float(np.nanmean(d)), "median": float(np.nanmedian(d)),
        "p05": float(np.nanpercentile(d, 5)), "p95": float(np.nanpercentile(d, 95)),
        "max_abs": float(np.nanmax(np.abs(d))),
        "frac_gt_1C": float(np.mean(np.abs(d) > 1.0)),
        "frac_gt_2C": float(np.mean(np.abs(d) > 2.0))}
    print(f"[G2-3] buggy 阈值: 每行跨列极差 max = {res['structure']['t2m_buggy_row_ptp_max']} "
          f"(=0 => 206 个陆点共用 1 条曲线), 唯一值 {res['structure']['t2m_buggy_n_unique']}, "
          f"文件 {res['structure']['t2m_npz_bytes']} B")
    print(f"       fixed 阈值: 行内极差中位 {res['structure']['t2m_fixed_row_ptp_median']:.2f} °C; "
          f"Δ(fixed-buggy) 中位 {res['t2m_fixed_minus_buggy']['median']:+.2f} °C, "
          f"|Δ|>1 °C 占比 {res['t2m_fixed_minus_buggy']['frac_gt_1C']*100:.1f}%")

    doy_all = np.concatenate(doys)
    cnt = pd.Series(doy_all).value_counts().sort_index()
    res["pool_coverage"] = {
        "t2m_pool_rows": int(len(doy_all)),
        "sst_pool_rows": int(sum(len(x) for x in sdoys)),
        "doy_bins_present": int(cnt.size),
        "doy_bins_missing": sorted(set(range(1, 367)) - set(cnt.index.tolist())),
        "min_samples_per_doy": int(cnt.min()), "max_samples_per_doy": int(cnt.max()),
        "doy_with_fewest": int(cnt.idxmin()),
        "samples_at_doy60": int(cnt.get(60, 0)),
        "samples_at_doy366": int(cnt.get(366, 0))}
    print(f"[G2-4] T2m 池 {res['pool_coverage']['t2m_pool_rows']} 行 / "
          f"SST 池 {res['pool_coverage']['sst_pool_rows']} 行; doy 有样本 "
          f"{res['pool_coverage']['doy_bins_present']}/366, 缺 "
          f"{res['pool_coverage']['doy_bins_missing']}; 每 doy 样本 "
          f"{res['pool_coverage']['min_samples_per_doy']}~"
          f"{res['pool_coverage']['max_samples_per_doy']}")

    tt = pd.DatetimeIndex(np.load(os.path.join(AUDIT, "t2m_XGHG_001.npz"))["time"])
    g_doy = tt.dayofyear.values
    n_doy = noleap_doy(tt)
    diff = g_doy - n_doy
    res["calendar_doy"] = {
        "n_days_greg_doy_ne_noleap": int((diff != 0).sum()),
        "n_days_total": int(len(tt)),
        "first_date_where_differs": str(tt[np.argmax(diff != 0)].date()),
        "n_doy366_greg": int((g_doy == 366).sum()),
        "leap_years_in_period": sorted(set(tt.year[diff != 0].tolist())),
        "greg_doy_max": int(g_doy.max()), "noleap_doy_max": int(n_doy.max())}
    print(f"[G2-5] 公历 doy ≠ noleap 年内序号的天数: "
          f"{res['calendar_doy']['n_days_greg_doy_ne_noleap']}/"
          f"{res['calendar_doy']['n_days_total']} (首处 "
          f"{res['calendar_doy']['first_date_where_differs']}; 闰年 "
          f"{res['calendar_doy']['leap_years_in_period']}; 公历 doy 上界 "
          f"{res['calendar_doy']['greg_doy_max']} vs noleap {res['calendar_doy']['noleap_doy_max']})")

    # doy 定义敏感性: 公历 doy vs noleap 一致序号 (3 成员池, SST/T2m 逐点阈值)
    sdoys_nl = [noleap_doy(pd.DatetimeIndex(np.load(
        os.path.join(AUDIT, f"sst_XGHG_{m}.npz"))["time"])) for m in MEMBERS]
    thr_sst_nl = build_sst_thresh(smats, sdoys_nl)
    tdoys_nl = [noleap_doy(pd.DatetimeIndex(np.load(
        os.path.join(AUDIT, f"t2m_XGHG_{m}.npz"))["time"])) for m in MEMBERS]
    thr_t2m_nl, _ = build_t2m_thresh(mats, tdoys_nl, buggy=False)

    sens = {}
    for m in MEMBERS:
        v, t = load_sst("XGHG", m)
        nd = noleap_doy(t)
        e_g = exceed_days(v, t, thr_sst)
        e_n = int((((v > thr_sst_nl[nd - 1]) & ~np.isnan(v))).sum())
        a_, t_ = load_t2m("XGHG", m)
        nd2 = noleap_doy(t_)
        y_g = int((((a_ > thr_fix[t_.dayofyear.values - 1]) & ~np.isnan(a_))).sum())
        y_n = int((((a_ > thr_t2m_nl[nd2 - 1]) & ~np.isnan(a_))).sum())
        sens[m] = {"sst_exceed_greg": e_g, "sst_exceed_noleap": e_n,
                   "sst_rel": (e_n - e_g) / e_g,
                   "thw_exceed_greg": y_g, "thw_exceed_noleap": y_n,
                   "thw_rel": (y_n - y_g) / y_g}
        print(f"[G2-6] {m}: SST 超标日 {e_g} -> {e_n} ({(e_n-e_g)/e_g*100:+.3f}%); "
              f"THW 超标日 {y_g} -> {y_n} ({(y_n-y_g)/y_g*100:+.3f}%)")
    res["noleap_doy_sensitivity"] = sens
    for var, a_, b_ in (("sst", thr_sst, thr_sst_nl), ("t2m", thr_fix, thr_t2m_nl)):
        n = min(a_.shape[0], b_.shape[0])
        d_ = a_[:n] - b_[:n]
        res[f"noleap_doy_thresh_delta_{var}"] = {
            "median": float(np.nanmedian(d_)), "absmean": float(np.nanmean(np.abs(d_))),
            "p95abs": float(np.nanpercentile(np.abs(d_), 95))}
        print(f"        {var.upper()} 阈值 Δ(公历doy - noleap序号): 中位 "
              f"{res[f'noleap_doy_thresh_delta_{var}']['median']:+.3f} °C, |Δ|均 "
              f"{res[f'noleap_doy_thresh_delta_{var}']['absmean']:.3f} °C")

    jdump(res, "g2_t2m_axis_and_calendar.json")
    return res


# ══════════════════════════════════════════════════════════════
# G3: 论文原文证据
# ══════════════════════════════════════════════════════════════
def stage_g3():
    print("== G3 论文原文（模型侧基准期）证据 ==")
    txt = open(os.path.join(ROOT, "results", "paper_text.txt"),
               encoding="utf-8").read().split("\n")   # 与 read 工具/项目文档同一编号（\n 计数）
    pats = {
        "threshold_definition": r"90th percentile|seasonally varying threshold|climatological distribution",
        "consistency_claim": r"same compound heatwave detection approach|consistently to both",
        "period_2000_2021": r"period 2000|440 model years|2000–2021",
        "model_span": r"CESM1-LE simulations span|FixGHG; a counterfactual"}
    out = {}
    for k, p in pats.items():
        rx = re.compile(p)
        hits = [(i + 1, txt[i].strip()) for i in range(len(txt)) if rx.search(txt[i])]
        out[k] = hits
        print(f"[G3] {k}: {len(hits)} 行")
        for i, ln in hits[:8]:
            print(f"    L{i}: {ln[:120]}")
    i0 = next(i for i, ln in enumerate(txt) if ln.strip() == "Model data")
    out["model_data_block"] = [(i + 1, txt[i].strip()) for i in range(i0, min(i0 + 12, len(txt)))]
    out["methods_definition_block"] = [(i + 1, txt[i].strip()) for i in range(487, 508)]
    out["gev_bootstrap_block"] = [(i + 1, txt[i].strip()) for i in range(582, 596)]
    jdump(out, "g3_paper_evidence.json")
    return out


# ══════════════════════════════════════════════════════════════
# chain: 复现现状 + LOO 场景
# ══════════════════════════════════════════════════════════════
SCEN_DOC = {
    "in3_bug": "现状 v2：池=3 XGHG(in-sample)，T2m 轴崩溃版（=磁盘 npz）",
    "in3_fix": "仅修 T2m 轴：池仍=3 XGHG(in-sample)，T2m 逐点阈值",
    "in3_fix_sstm1": "在 in3_fix 基础上把 MHW 日期 -1 天（SST 标签->物理日对齐）",
    "in2in_a": "池大小配对(2)且仍 in-sample：池={m, 次一成员}",
    "in2in_b": "池大小配对(2)且仍 in-sample：池={m, 另一成员}",
    "loo": "LOO 主口径：XGHG 成员剔除自身(池=其余2)；ALL 成员用全 3 池",
    "loo2": "池大小配对的 LOO：两组都剔除同号 XGHG 成员(池=2)",
    "own": "v1 参照：XGHG 用成员自身气候态；ALL 用 3 成员 XGHG 池",
}


def pool_of(kind, exp, m):
    if kind == "in3_bug" or kind == "in3_fix":
        return MEMBERS
    if kind == "in2in_a":
        return [m, OTHERS[m][0]] if exp == "XGHG" else OTHERS[m]
    if kind == "in2in_b":
        return [m, OTHERS[m][1]] if exp == "XGHG" else OTHERS[m]
    if kind == "loo":
        return OTHERS[m] if exp == "XGHG" else MEMBERS
    if kind == "loo2":
        return OTHERS[m]
    if kind == "own":
        return [m] if exp == "XGHG" else MEMBERS
    raise KeyError(kind)


def stage_chain():
    print("== chain: 复现 v2 现状 + LOO / in-sample 场景 ==")
    t_start = _t.time()
    SST, T2M, TS, TT = {}, {}, {}, {}
    for m in MEMBERS:
        for exp in ("XGHG", "ALL"):
            SST[(exp, m)], TS[(exp, m)] = load_sst(exp, m)
            T2M[(exp, m)], TT[(exp, m)] = load_t2m(exp, m)
    print(f"  数据加载完成 {_t.time()-t_start:.0f}s")

    cache_s, cache_t = {}, {}

    def sst_thr(pool):
        k = tuple(pool)
        if k not in cache_s:
            cache_s[k] = build_sst_thresh([SST[("XGHG", x)] for x in pool],
                                          [TS[("XGHG", x)].dayofyear.values for x in pool])
        return cache_s[k]

    def t2m_thr(pool, buggy):
        k = (tuple(pool), buggy)
        if k not in cache_t:
            cache_t[k] = build_t2m_thresh([T2M[("XGHG", x)] for x in pool],
                                          [TT[("XGHG", x)].dayofyear.values for x in pool],
                                          buggy=buggy)[0]
        return cache_t[k]

    rows, annual_store = [], {}
    keep_csv = {"in3_bug", "loo"}
    for scen, kind in [(s, s) for s in ("in3_bug", "in3_fix", "in2in_a", "in2in_b",
                                        "loo", "loo2", "own")]:
        buggy = (scen == "in3_bug")
        for exp in ("ALL", "XGHG"):
            for m in MEMBERS:
                pool = pool_of(kind, exp, m)
                thr_s, thr_t = sst_thr(pool), t2m_thr(pool, buggy)
                v, ts = SST[(exp, m)], TS[(exp, m)]
                a_, tt = T2M[(exp, m)], TT[(exp, m)]
                tag = f"{scen}_{exp}_{m}" if scen in keep_csv else None
                mhw = detect_mhw(v, ts, thr_s, tag)
                thw = detect_thw(a_, tt, thr_t, tag)
                expo, ann, _ = compound_chain(mhw, thw, tt, tag)
                annual_store[(scen, exp, m)] = ann
                rows.append({"scenario": scen, "exp": exp, "member": m,
                             "sst_pool": "+".join(pool), "t2m_pool": "+".join(pool),
                             "t2m_buggy": buggy,
                             "n_days_sst": int(v.shape[0]), "n_days_t2m": int(a_.shape[0]),
                             "mhw_events": len(mhw), "thw_events": len(thw),
                             "mhw_exceed_days": exceed_days(v, ts, thr_s),
                             "thw_exceed_days": exceed_days(a_, tt, thr_t),
                             **expo})
                # SST 日历 +1 天错位的敏感性: 标签转物理日 => MHW 日期 -1 天
                if scen == "in3_fix":
                    scen2 = "in3_fix_sstm1"
                    mhw_s = mhw.copy()
                    mhw_s["event_start"] = pd.to_datetime(mhw_s.event_start) - pd.Timedelta(days=1)
                    mhw_s["event_end"] = pd.to_datetime(mhw_s.event_end) - pd.Timedelta(days=1)
                    expo_s, ann_s, _ = compound_chain(mhw_s, thw, tt)
                    annual_store[(scen2, exp, m)] = ann_s
                    rows.append({"scenario": scen2, "exp": exp, "member": m,
                                 "sst_pool": "+".join(pool), "t2m_pool": "+".join(pool),
                                 "t2m_buggy": buggy, "n_days_sst": int(v.shape[0]),
                                 "n_days_t2m": int(a_.shape[0]),
                                 "mhw_events": len(mhw), "thw_events": len(thw),
                                 "mhw_exceed_days": exceed_days(v, ts, thr_s),
                                 "thw_exceed_days": exceed_days(a_, tt, thr_t),
                                 **expo_s})
        print(f"  [{scen}] " + " | ".join(
            f"{r['exp']}{r['member']} comp={r['compound_days']}"
            for r in rows if r["scenario"] == scen))

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(AUDIT, "chain_members.csv"), index=False)
    print(f"  -> {os.path.join(AUDIT, 'chain_members.csv')}")

    # 全部场景的逐年样本（供 PR 阈值扫描）
    long = []
    for (scen, exp, m), ann in annual_store.items():
        x = ann.copy()
        x.insert(0, "member", m)
        x.insert(0, "exp", exp)
        x.insert(0, "scenario", scen)
        long.append(x)
    pd.concat(long).to_csv(os.path.join(AUDIT, "annual_all_scenarios.csv"), index=False)
    print(f"  -> {os.path.join(AUDIT, 'annual_all_scenarios.csv')}")

    # ── 阈值差表 ─────────────────────────────────────────────
    tinfo = []
    for m in MEMBERS:
        base_s, base_t = sst_thr(MEMBERS), t2m_thr(MEMBERS, False)
        bug_t = t2m_thr(MEMBERS, True)
        own_s, own_t = sst_thr([m]), t2m_thr([m], False)
        loo_s, loo_t = sst_thr(OTHERS[m]), t2m_thr(OTHERS[m], False)
        in2_s, in2_t = sst_thr([m, OTHERS[m][0]]), t2m_thr([m, OTHERS[m][0]], False)
        rec = {"member": m}
        for nm, A, B in (("sst_loo_minus_in3", loo_s, base_s),
                         ("sst_own_minus_in3", own_s, base_s),
                         ("sst_in2_minus_in3", in2_s, base_s),
                         ("t2m_loo_minus_in3fix", loo_t, base_t),
                         ("t2m_own_minus_in3fix", own_t, base_t),
                         ("t2m_fix_minus_buggy", base_t, bug_t)):
            d = A - B
            rec[nm + "_mean"] = float(np.nanmean(d))
            rec[nm + "_median"] = float(np.nanmedian(d))
            rec[nm + "_absmean"] = float(np.nanmean(np.abs(d)))
            rec[nm + "_p95abs"] = float(np.nanpercentile(np.abs(d), 95))
            rec[nm + "_frac_gt1C"] = float(np.nanmean(np.abs(d) > 1.0))
        tinfo.append(rec)
        print(f"  [阈值] {m} SST loo-in3: Δ均 {rec['sst_loo_minus_in3_mean']:+.3f} "
              f"|Δ|均 {rec['sst_loo_minus_in3_absmean']:.3f} °C; "
              f"T2m loo-in3fix: Δ均 {rec['t2m_loo_minus_in3fix_mean']:+.3f} "
              f"|Δ|均 {rec['t2m_loo_minus_in3fix_absmean']:.3f} °C; "
              f"T2m fix-buggy: Δ均 {rec['t2m_fix_minus_buggy_mean']:+.3f} "
              f"|Δ|均 {rec['t2m_fix_minus_buggy_absmean']:.3f} °C")
    pd.DataFrame(tinfo).to_csv(os.path.join(AUDIT, "threshold_deltas.csv"), index=False)

    # ── 现状复现校验 ─────────────────────────────────────────
    val = {}
    st = pd.read_csv(os.path.join(P6.CESM_INT, "exposure_members_x.csv"))
    st["member"] = st["member"].astype(str).str.zfill(3)
    mine = df[(df.scenario == "in3_bug")][["exp", "member", "compound_days",
                                           "standalone_days", "thw_pair_days"]].copy()
    mine["member"] = mine["member"].astype(str).str.zfill(3)
    mg = st.merge(mine, on=["exp", "member"], suffixes=("_stored", "_mine"))
    val["exposure_match_all6"] = bool(
        (mg.compound_days_stored == mg.compound_days_mine).all() and
        (mg.standalone_days_stored == mg.standalone_days_mine).all() and
        (mg.thw_pair_days_stored == mg.thw_pair_days_mine).all())
    ev_ok = ev_tot = 0
    for f in sorted(os.listdir(P6.CESM_INT)):
        mm = re.match(r"(mhw|thw)_x_(ALL|XGHG)_(\d+)\.csv$", f)
        if not mm:
            continue
        ev_tot += 1
        mf = os.path.join(AUDIT, f"{mm.group(1)}_in3_bug_{mm.group(2)}_{mm.group(3)}.csv")
        x = pd.read_csv(os.path.join(P6.CESM_INT, f))
        y = pd.read_csv(mf) if os.path.exists(mf) else pd.DataFrame()
        if len(x) == len(y) and len(x) and \
                (pd.to_datetime(x.event_start).values == pd.to_datetime(y.event_start).values).all() \
                and (x.lat_idx.values == y.lat_idx.values).all() and \
                (x.duration.values == y.duration.values).all():
            ev_ok += 1
    val["event_tables_identical"] = f"{ev_ok}/{ev_tot}"
    print(f"  [校验] exposure_members_x.csv 6 行逐格一致: {val['exposure_match_all6']}; "
          f"事件表逐行一致: {val['event_tables_identical']}")

    # ── PR / FAR ─────────────────────────────────────────────
    obs = P6._obs_annual_threshold()
    v22_mean = float(obs.loc[obs.year == 2022, "med_mean"].iloc[0])
    v22_max = float(obs.loc[obs.year == 2022, "med_max"].iloc[0])
    print(f"  观测 Med 2022 阈值: med_mean={v22_mean:.1f} 天  med_max={v22_max:.1f} 天")
    res_rows = []
    for scen in [s for s in SCEN_DOC if s in set(df.scenario)]:
        for col in ("med_mean", "med_max"):
            x22 = v22_mean if col == "med_mean" else v22_max
            sa = np.concatenate([annual_store[(scen, "ALL", m)][col].values for m in MEMBERS])
            sf = np.concatenate([annual_store[(scen, "XGHG", m)][col].values for m in MEMBERS])
            pr, far, lo, hi, boots = P6._pr_boot(x22, sa, sf)
            res_rows.append({"scenario": scen, "col": col, "threshold_days": x22,
                             "p_all": float((sa >= x22).mean()),
                             "p_fix": float((sf >= x22).mean()),
                             "PR": pr, "FAR": far, "ci_lo": lo, "ci_hi": hi,
                             "n_inf_boot": int((~np.isfinite(boots)).sum()),
                             "all_mean_days": float(sa.mean()),
                             "fix_mean_days": float(sf.mean()),
                             "ratio_means": float(sa.mean() / sf.mean()) if sf.mean() else np.nan})
    rdf = pd.DataFrame(res_rows)
    rdf.to_csv(os.path.join(AUDIT, "chain_pr_far.csv"), index=False)
    print(rdf[["scenario", "col", "threshold_days", "p_all", "p_fix", "PR", "FAR",
               "ci_lo", "ci_hi", "n_inf_boot", "all_mean_days", "fix_mean_days",
               "ratio_means"]].to_string(index=False))
    jdump({"obs_threshold": {"med_mean_2022": v22_mean, "med_max_2022": v22_max},
           "validation": val, "scenarios": SCEN_DOC}, "chain_validation.json")
    print(f"  chain 总耗时 {_t.time()-t_start:.0f}s")
    return rdf


def stage_trend():
    """G3 补充: 池时段 (2000-2021) 内 XGHG 反事实世界与 ALL 世界的增暖趋势。

    用于判断"用与检测期完全重叠的 2000-2021 XGHG 池当基准"是否合适：
    反事实世界在固定 GHG 下应近似平稳，则单条 22 年合并气候态即可代表该世界。
    """
    print("== trend: 2000-2021 池时段内的增暖趋势 ==")
    rows = []
    for exp in ("XGHG", "ALL"):
        for m in MEMBERS:
            v, t = load_sst(exp, m)
            a_, t2 = load_t2m(exp, m)
            yr, yr2 = t.year.values, t2.year.values
            ys = np.unique(yr).astype(float)
            sst_ann = np.array([np.nanmean(v[yr == y]) for y in np.unique(yr)])
            t2m_ann = np.array([np.nanmean(a_[yr2 == y]) for y in np.unique(yr2)])
            sst_slope = np.polyfit(ys, sst_ann, 1)[0] * 10     # °C/decade
            t2m_slope = np.polyfit(ys, t2m_ann, 1)[0] * 10
            rows.append({"exp": exp, "member": m, "n_days_sst": int(v.shape[0]),
                         "sst_2000_2021_mean": float(sst_ann.mean()),
                         "sst_trend_C_per_decade": float(sst_slope),
                         "t2m_2000_2021_mean": float(t2m_ann.mean()),
                         "t2m_trend_C_per_decade": float(t2m_slope)})
            print(f"  {exp} {m}: SST 均值 {sst_ann.mean():.2f} °C, 趋势 "
                  f"{sst_slope:+.3f} °C/10a | T2m {t2m_ann.mean():.2f} °C, "
                  f"{t2m_slope:+.3f} °C/10a")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(AUDIT, "pool_period_trends.csv"), index=False)
    print(df.groupby("exp")[["sst_trend_C_per_decade", "t2m_trend_C_per_decade"]].mean()
          .to_string())
    print(f"  -> {os.path.join(AUDIT, 'pool_period_trends.csv')}")
    return df


def stage_sweep():
    """PR 阈值扫描: 把"in-sample 偏差"从"阈值选择"里分离出来。

    读 annual_all_scenarios.csv, 对每个场景在每个阈值上算 P_ALL/P_fix/PR,
    并与现状(in3_bug) 对比 —— 论文 Fig.3c/3d 也是阈值曲线, 单点阈值不足以下结论。
    """
    print("== sweep: PR(阈值) 曲线 ==")
    df = pd.read_csv(os.path.join(AUDIT, "annual_all_scenarios.csv"))
    scens = [s for s in SCEN_DOC if s in set(df.scenario)]
    grids = [0, 5, 10, 15, 20, 25, 30, 40, 50, 62, 78, 100, 128, 150]
    recs = []
    for scen in scens:
        for col in ("med_mean", "med_max"):
            sa = df[(df.scenario == scen) & (df.exp == "ALL")][col].values
            sf = df[(df.scenario == scen) & (df.exp == "XGHG")][col].values
            for x in grids:
                p_all = float((sa >= x).mean())
                p_fix = float((sf >= x).mean())
                pr = p_all / p_fix if p_fix > 0 else (np.inf if p_all > 0 else np.nan)
                recs.append({"scenario": scen, "col": col, "threshold": x,
                             "p_all": p_all, "p_fix": p_fix, "PR": pr,
                             "PR_capped": min(pr, 999) if np.isfinite(pr) else 999,
                             "n_all_above": int((sa >= x).sum()),
                             "n_fix_above": int((sf >= x).sum())})
    sdf = pd.DataFrame(recs)
    sdf.to_csv(os.path.join(AUDIT, "pr_threshold_sweep.csv"), index=False)
    piv = sdf.pivot_table(index=["col", "threshold"], columns="scenario",
                          values="PR_capped")
    print(piv.to_string(float_format=lambda v: f"{v:8.1f}"))
    print("  (999 = P_fix=0 即 PR 发散)")
    print(f"  -> {os.path.join(AUDIT, 'pr_threshold_sweep.csv')}")
    return sdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["g1", "g2", "g3", "trend", "chain",
                                      "sweep", "all"])
    a = ap.parse_args()
    if a.stage in ("g1", "all"):
        stage_g1()
    if a.stage in ("g2", "all"):
        stage_g2()
    if a.stage in ("g3", "all"):
        stage_g3()
    if a.stage in ("trend", "all"):
        stage_trend()
    if a.stage in ("chain", "all"):
        stage_chain()
    if a.stage in ("sweep", "all"):
        stage_sweep()


if __name__ == "__main__":
    main()
