# -*- coding: utf-8 -*-
"""
phase6_cesm.py — CESM1-LE 归因管线（P0: 成员 001-003 验证版）
对应论文图 7: 复合热浪暴露时间的温室气体归因 (ALL vs FixGHG/XGHG)。

阶段:
  prepare   逐成员准备检测输入: XGHG 两段拼接 / K->°C / 改名 T2m / 裁到与
            AWS 成品一致欧洲框; SST 保持 proc 原样(检测时按配对点抽读)
  pairs     构建 CESM 沿海配对: POP gx1v6 湿格点(KMT>0)映射到 f09 大气格 →
            陆地掩码 → 形态学腐蚀取边缘 → KDTree 最近海点 (TLAT/TLONG, cos 加权)
  detect    逐成员: 陆地 THW 走 R detect_events.R (heatwaveR, 域限配对陆点);
            海洋 MHW 走逐 doy 90 分位气候态 + 游程状态机 (与观测管线同语义)
  compound  逐成员: 共超标复合日 (复用 compound_events.identify_compound_events)
            → 暴露时间表 (compound/standalone/THW 配对日数)
  attrib    ALL vs XGHG 暴露时间分布 + bootstrap 概率比 + 图7 验证版

用法:
  python phase6_cesm.py prepare --members 3
  python phase6_cesm.py pairs
  python phase6_cesm.py detect --members 3
  python phase6_cesm.py compound --members 3
  python phase6_cesm.py attrib --members 3

口径说明 (与观测管线 Phase 2-3 的一致性与差异):
  * 检测参数完全一致: pctile=90, 11 天窗(heatwaveR), min_dur=5, max_gap=2;
    MHW 气候态 = 逐 dayofyear 单日 90 分位 (与观测 load_data.calc_climatology 相同)。
  * 气候基准期: 模型侧用成员自身 2000-2021 全时段 (无更长的稳定基准期),
    观测侧为 1983-2012 —— 这是模型归因的常规做法, 图7 口径。
  * CESM 日历 noleap (365 天), 解码为标准日期后进入同一套管线。
  * 配对距离上限 1.0° (观测 0.5° 是 0.25° 网格调的; f09/gx1v6 都是 ~1° 网格)。
"""
import argparse
import glob
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import binary_erosion, generate_binary_structure
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
from config import RSCRIPT_PATH, R_WORKERS  # noqa: E402

CESM_PROC_DIR = C.CESM_PROC_DIR
CESM_INT = os.path.join(C.INTERMEDIATE_DIR, "cesm")
PAIRS_CSV = os.path.join(CESM_INT, "coastal_pairs_cesm.csv")
DOMAINS_CSV = os.path.join(CESM_INT, "domains_land_cesm.csv")
EXPOSURE_CSV = os.path.join(CESM_INT, "exposure_members.csv")
FIG7_PNG = os.path.join(C.FIGURES_DIR, "fig7_p0_validation.png")

MAX_PAIR_DIST_DEG = 1.0     # f09/gx1v6 均 ~1° 网格, 观测的 0.5° 不适用
N_BOOTSTRAP = C.N_BOOTSTRAP
CI = C.CI_ALPHA

MEMBERS_P0 = C.CESM_ALL_MEMBERS[:C.CESM_P0_MEMBERS]


# ──────────────────────────────────────────────
# 文件发现
# ──────────────────────────────────────────────
def find_t2m_segments(exp, m):
    """返回该成员 (exp) 的 TREFHT proc 段文件列表 (按起始年排序)。"""
    if exp == "ALL":
        f = os.path.join(CESM_PROC_DIR, f"TREFHT_all_{m}_2000-2021_europe.nc")
        return [f] if os.path.exists(f) else []
    pats = [
        os.path.join(CESM_PROC_DIR, f"*xghg.{m}.cam.h1.TREFHT.*_2000-2021.nc"),
    ]
    fs = sorted(sum([glob.glob(p) for p in pats], []))
    return fs


def find_sst_segments(exp, m):
    if exp == "ALL":
        pats = [
            os.path.join(CESM_PROC_DIR,
                         f"*B20TRC5CNBDRD.f09_g16.{m}.pop.h.nday1.SST.*_2000-2021.nc"),
            os.path.join(CESM_PROC_DIR,
                         f"*BRCP85C5CNBDRD.f09_g16.{m}.pop.h.nday1.SST.*_2000-2021.nc"),
        ]
    else:
        pats = [
            os.path.join(CESM_PROC_DIR,
                         f"*xghg.{m}.pop.h.nday1.SST.*_2000-2021.nc"),
        ]
    return sorted(sum([glob.glob(p) for p in pats], []))


# ──────────────────────────────────────────────
# prepare
# ──────────────────────────────────────────────
def cmd_prepare(args):
    """逐成员生成 {exp}_{m}_T2m.nc (Europe 框, °C, 拼好两段)。"""
    os.makedirs(CESM_INT, exist_ok=True)
    # 参考欧洲框: 取 AWS 成品 001 的 lat/lon
    ref = xr.open_dataset(
        os.path.join(CESM_PROC_DIR, "TREFHT_all_001_2000-2021_europe.nc"))
    ref_lat, ref_lon = ref.lat, ref.lon
    ref.close()

    for exp in ("ALL", "XGHG"):
        for m in MEMBERS_P0[: args.members]:
            out = os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc")
            if os.path.exists(out):
                print(f"已存在, 跳过 {out}")
                continue
            segs = find_t2m_segments(exp, m)
            if not segs:
                print(f"!! {exp} {m}: 无 TREFHT 段文件, 跳过")
                continue
            print(f"{exp} {m}: {len(segs)} 段")
            ds_list = []
            for f in segs:
                ds = xr.open_dataset(f)
                var = "TREFHT" if "TREFHT" in ds.data_vars else "T2m"
                da = ds[var]
                # 统一到 AWS 成品的欧洲框坐标 (XGHG 原生 0-360 经度/纬度可能降序)
                lon180 = ((da.lon.astype(float) + 180) % 360) - 180
                da = da.assign_coords(lon=lon180).sortby("lon")
                da = da.sel(lat=ref_lat.values, lon=ref_lon.values,
                            method="nearest")
                da = da.assign_coords(lat=ref_lat.values, lon=ref_lon.values)
                if da.attrs.get("units", "").startswith("K") or float(
                        da.max()) > 150:
                    da = da - 273.15
                da = da.rename("T2m")
                da.attrs["units"] = "degC"
                ds_list.append(da)
                ds.close()
            merged = xr.concat(ds_list, dim="time") if len(ds_list) > 1 else ds_list[0]
            merged = merged.sortby("time")
            assert not merged.indexes["time"].has_duplicates, f"{exp} {m} 时间重复"
            merged.to_netcdf(out)
            print(f"  -> {out}  ({merged.sizes['time']} 天, "
                  f"{merged.sizes['lat']}x{merged.sizes['lon']}, "
                  f"{str(merged.time.values[0])[:10]}~"
                  f"{str(merged.time.values[-1])[:10]})")


# ──────────────────────────────────────────────
# pairs
# ──────────────────────────────────────────────
def cmd_pairs(args):
    """CESM 沿海配对: POP 湿点 → f09 陆地掩码 → 边缘 → KDTree。"""
    os.makedirs(CESM_INT, exist_ok=True)
    ref = xr.open_dataset(
        os.path.join(CESM_PROC_DIR, "TREFHT_all_001_2000-2021_europe.nc"))
    atm_lat = ref.lat.values.astype(float)   # 升序?
    atm_lon = ref.lon.values.astype(float)   # -17..47
    ref.close()

    sst_f = find_sst_segments("ALL", "001")[0]
    ds = xr.open_dataset(sst_f, decode_times=False)
    kmt = ds["KMT"].values            # (nlat, nlon) >0 = 湿格点
    tlat = ds["TLAT"].values.astype(float)
    tlon = ds["TLONG"].values.astype(float)
    ds.close()

    wet_rows, wet_cols = np.where(kmt > 0)
    print(f"POP 湿格点: {len(wet_rows)}")

    # 1) POP 湿点 → 最近 f09 格 (距离容差 = 0.75 倍格距)
    dlat = float(np.abs(np.diff(atm_lat).mean()))
    dlon = float(np.abs(np.diff(atm_lon).mean()))
    tlon180 = np.where(tlon > 180, tlon - 360, tlon)
    wlat = tlat[wet_rows, wet_cols]
    wlon = tlon180[wet_rows, wet_cols]

    ii = np.abs(wlat[:, None] - atm_lat[None, :]).argmin(axis=1)
    jj = np.abs(wlon[:, None] - atm_lon[None, :]).argmin(axis=1)
    ok = (np.abs(wlat - atm_lat[ii]) <= 0.75 * dlat) & \
         (np.abs(wlon - atm_lon[jj]) <= 0.75 * dlon)
    land_mask = np.ones((len(atm_lat), len(atm_lon)), dtype=np.int8)
    land_mask[ii[ok], jj[ok]] = 0
    n_ocean_atm = int((land_mask == 0).sum())
    print(f"f09 欧洲框 {land_mask.shape}: 海格点 {n_ocean_atm}, "
          f"陆格点 {int(land_mask.sum())}")

    # 2) 陆地边缘 (形态学腐蚀)
    s = generate_binary_structure(2, 1)
    eroded = binary_erosion(land_mask, structure=s)
    edge = (land_mask == 1) & (~eroded)
    edge_idx = np.argwhere(edge)
    print(f"陆地边缘格点: {len(edge_idx)}")

    # 3) KDTree: POP 湿点 (cos 纬度加权), 陆点查最近海点
    cos_w = np.cos(np.deg2rad(wlat))
    tree = cKDTree(np.column_stack([wlat, wlon * cos_w]))
    pairs = []
    for i, j in edge_idx:
        lat0 = float(atm_lat[i]); lon0 = float(atm_lon[j])
        q = np.array([[lat0, lon0 * np.cos(np.deg2rad(lat0))]])
        dist, pos = tree.query(q, k=1)
        if dist[0] > MAX_PAIR_DIST_DEG:
            continue
        orow, ocol = wet_rows[pos[0]], wet_cols[pos[0]]
        pairs.append({
            "land_lat_idx": int(i), "land_lon_idx": int(j),
            "ocean_lat_idx": int(orow), "ocean_lon_idx": int(ocol),
            "land_lat": lat0, "land_lon": lon0,
            "ocean_lat": float(tlat[orow, ocol]),
            "ocean_lon": float(tlon180[orow, ocol]),
            "dist_deg": float(dist[0]),
        })
    pairs_df = pd.DataFrame(pairs)
    pairs_df.to_csv(PAIRS_CSV, index=False)
    print(f"配对成功 {len(pairs_df)}/{len(edge_idx)} (上限 {MAX_PAIR_DIST_DEG}°)"
          f" -> {PAIRS_CSV}")

    # 4) R 域文件 (只检测配对陆点)
    dom = pairs_df[["land_lat", "land_lon"]].drop_duplicates()
    dom.columns = ["lat", "lon"]
    dom.to_csv(DOMAINS_CSV, index=False)
    print(f"R 域文件: {DOMAINS_CSV} ({len(dom)} 点)")


# ──────────────────────────────────────────────
# detect
# ──────────────────────────────────────────────
def _detect_mhw_member(exp, m, pairs_df):
    """MHW: 配对海点 + 逐 doy 90 分位气候态 + 游程状态机 (与观测同语义)。"""
    out_csv = os.path.join(CESM_INT, f"mhw_{exp}_{m}.csv")
    if os.path.exists(out_csv):
        print(f"已存在, 跳过 {out_csv}")
        return out_csv

    segs = find_sst_segments(exp, m)
    if not segs:
        raise FileNotFoundError(f"{exp} {m}: 无 SST 段")
    pj = pairs_df.ocean_lat_idx.values
    pi = pairs_df.ocean_lon_idx.values
    npair = len(pj)

    series, times = [], []
    kmt = None
    from netCDF4 import Dataset
    for f in segs:
        ds = xr.open_dataset(f)
        tv = pd.DatetimeIndex(ds.time.values)
        if kmt is None:
            kmt = ds["KMT"].values
        ds.close()
        nc = Dataset(f)
        v = nc.variables["SST"]                     # (time, nlat, nlon)
        j0, j1 = int(pj.min()), int(pj.max()) + 1
        block = v[:, j0:j1, :].astype(np.float32)   # (nt, rows, 320) 一次大读
        nc.close()
        rows = block[:, pj - j0, :]                 # (nt, npair, 320)
        series.append(np.take_along_axis(
            rows, pi[np.newaxis, :, np.newaxis], axis=2)[:, :, 0])
        times.append(tv)
        del block, rows
    vals = np.concatenate(series, axis=0).astype(np.float64)   # (nt, npair)
    time = pd.DatetimeIndex([t for tv in times for t in tv])
    kmt_pt = np.asarray(np.ma.filled(kmt[pj, pi], 0))           # 配对点 KMT
    vals[:, kmt_pt <= 0] = np.nan               # 陆点/死海无值

    print(f"{exp} {m}: SST {vals.shape[0]} 天 x {vals.shape[1]} 配对点")

    # 逐 doy 90 分位气候态 (成员自身 2000-2021, 与观测 load_data 同语义)
    doy = time.dayofyear.values
    nt, npair = vals.shape
    thresh = np.full((366, npair), np.nan)
    for d in np.unique(doy):
        thresh[d - 1] = np.nanpercentile(vals[doy == d], 90, axis=0)
    thr_t = thresh[doy - 1]                       # (nt, npairs)

    # 游程状态机 (min_dur=5, max_gap=2) — 与 detect_mhw._EventTracker 同语义
    events = []
    for p in range(npair):
        x = vals[:, p] > thr_t[:, p]
        x[np.isnan(vals[:, p])] = False
        x = x.astype(np.int8)
        dz = np.diff(np.concatenate(([0], x, [0])))
        starts = np.flatnonzero(dz == 1)
        ends = np.flatnonzero(dz == -1) - 1
        # 桥接 <=2 天间隙: 合并间隔 <=2 的相邻游程
        merged = []
        for a, b in zip(starts, ends):
            if merged and a - merged[-1][1] - 1 <= 2:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        for a, b in merged:
            if b - a + 1 >= 5:
                events.append({
                    "event_start": time[a], "event_end": time[b],
                    "duration": int(b - a + 1),
                    "lat_idx": int(pairs_df.ocean_lat_idx.iloc[p]),
                    "lon_idx": int(pairs_df.ocean_lon_idx.iloc[p]),
                    "lat": float(pairs_df.ocean_lat.iloc[p]),
                    "lon": float(pairs_df.ocean_lon.iloc[p]),
                })
    df = pd.DataFrame(events)
    df.to_csv(out_csv, index=False)
    print(f"  MHW 事件 {len(df)} -> {out_csv}")
    return out_csv


def _detect_thw_member(exp, m):
    """THW: R detect_events.R (heatwaveR), 域限配对陆点, 气候期 2000-2021。"""
    out_csv = os.path.join(CESM_INT, f"thw_{exp}_{m}.csv")
    if os.path.exists(out_csv):
        print(f"已存在, 跳过 {out_csv}")
        return out_csv
    t2m = os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc")
    if not os.path.exists(t2m):
        raise FileNotFoundError(t2m)
    work = out_csv + ".work"
    cmd = [
        RSCRIPT_PATH,
        os.path.join(C.BASE_DIR, "python", "detect_events.R"),
        t2m, "T2m", out_csv, "2000", "2021",
        DOMAINS_CSV, "5", "2", str(R_WORKERS), work,
    ]
    print(f"R THW 检测: {exp} {m} ...")
    r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    tail = "\n".join((r.stdout or "").strip().splitlines()[-3:])
    print("  " + tail.replace("\n", "\n  "))
    if not os.path.exists(out_csv):
        raise RuntimeError(f"R 未产出 {out_csv}; stderr: {r.stderr[-500:]}")
    return out_csv


def cmd_detect(args):
    pairs_df = pd.read_csv(PAIRS_CSV)
    for exp in ("ALL", "XGHG"):
        for m in MEMBERS_P0[: args.members]:
            try:
                _detect_thw_member(exp, m)
            except Exception as e:
                print(f"!! THW 失败 {exp} {m}: {e}")
                continue
            try:
                _detect_mhw_member(exp, m, pairs_df)
            except Exception as e:
                print(f"!! MHW 失败 {exp} {m}: {e}")


# ──────────────────────────────────────────────
# compound
# ──────────────────────────────────────────────
def cmd_compound(args):
    from compound_events import (
        identify_compound_events, _pair_maps, _event_daily_mask,
    )
    pairs_df = pd.read_csv(PAIRS_CSV)
    rows = []
    for exp in ("ALL", "XGHG"):
        for m in MEMBERS_P0[: args.members]:
            thw_f = os.path.join(CESM_INT, f"thw_{exp}_{m}.csv")
            mhw_f = os.path.join(CESM_INT, f"mhw_{exp}_{m}.csv")
            if not (os.path.exists(thw_f) and os.path.exists(mhw_f)):
                print(f"!! 缺事件表, 跳过 {exp} {m}")
                continue
            t2m = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
            time_da = t2m["T2m"]
            t0 = pd.Timestamp(time_da.time.values[0])
            nt = time_da.sizes["time"]

            thw = pd.read_csv(thw_f, parse_dates=["event_start", "event_end"])
            mhw = pd.read_csv(mhw_f, parse_dates=["event_start", "event_end"])
            comp = identify_compound_events(mhw, thw, pairs_df, time_da.time)

            # 暴露时间 (与 identify_compound_events 同一套逐日口径)
            lpd = _pair_maps(pairs_df)
            om = {}
            for k, g in mhw.groupby(["lat_idx", "lon_idx"]):
                om[k] = _event_daily_mask(g, nt, t0)
            kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
            thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
            thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}
            comp_days = std_days = thw_days = 0
            for lk, ok_ in lpd.items():
                g = thw_by.get(lk)
                if g is None or len(g) == 0:
                    continue
                lm = _event_daily_mask(g, nt, t0)
                thw_days += int(lm.sum())
                m_ = om.get(ok_)
                comp_days += int((lm & (m_ if m_ is not None else 0)).sum())
                std_days += int((lm & ~(m_ if m_ is not None
                                        else np.zeros(nt, bool))).sum())
            rows.append({"exp": exp, "member": m,
                         "compound_days": comp_days,
                         "standalone_days": std_days,
                         "thw_pair_days": thw_days})
            print(f"{exp} {m}: 段数={len(comp)} compound={comp_days:,} "
                  f"standalone={std_days:,} THW(配对)={thw_days:,}")

            # 逐年暴露时间 (PR 口径: 模型年 = 22 年 × 成员; 聚合用 Med 框)
            ann = _annual_per_pair(comp, time_da.time, pairs_df)
            ann.to_csv(os.path.join(CESM_INT, f"annual_{exp}_{m}.csv"),
                       index=False)
            t2m.close()
    df = pd.DataFrame(rows)
    df.to_csv(EXPOSURE_CSV, index=False)
    print(f"暴露时间表 -> {EXPOSURE_CSV}")


# ──────────────────────────────────────────────
# attrib
# ──────────────────────────────────────────────
def _annual_per_pair(comp, time_da, pairs_df):
    """复合日段表 -> 逐年逐配对点复合日数 + 区域聚合列 (Med 框同 fig1)。"""
    nt = time_da.sizes["time"]
    years = time_da.time.dt.year.values
    uyears = np.unique(years)
    pos = {(int(r.land_lat_idx), int(r.land_lon_idx)): p
           for p, r in enumerate(pairs_df.itertuples(index=False))}
    t0 = pd.Timestamp(time_da.time.values[0])
    daily = np.zeros((nt, len(pairs_df)), dtype=np.int8)
    for seg in comp.itertuples(index=False):
        p = pos.get((int(seg.land_lat_idx), int(seg.land_lon_idx)))
        if p is None:
            continue
        a = (pd.Timestamp(seg.thw_start) - t0).days
        b = (pd.Timestamp(seg.thw_end) - t0).days
        daily[max(a, 0):min(b, nt - 1) + 1, p] = 1
    ann = np.stack([daily[years == y].sum(axis=0) for y in uyears])  # (yr, pair)
    med = (pairs_df.land_lat.between(30, 47) & pairs_df.land_lon.between(5, 42)).values
    out = pd.DataFrame({"year": uyears,
                        "med_mean": ann[:, med].mean(axis=1),
                        "med_max": ann[:, med].max(axis=1),
                        "eur_mean": ann.mean(axis=1),
                        "eur_max": ann.max(axis=1)})
    return out


def _obs_annual_threshold():
    """观测侧同口径阈值: annual_compound_days.nc 限制 Med 框, 2022 年值。"""
    ann = xr.open_dataset(C.ANNUAL_COMPOUND_NC)
    var = list(ann.data_vars)[0]
    da = ann[var]
    pairs = pd.read_csv(C.COASTAL_PAIRS_CSV)
    med = (pairs.land_lat.between(30, 47) & pairs.land_lon.between(5, 42)).values
    p = pairs[med]
    sub = da.isel(lat=xr.DataArray(p.land_lat_idx.values, dims="p"),
                  lon=xr.DataArray(p.land_lon_idx.values, dims="p"))  # (time, p)
    arr = sub.transpose("time", "p").values
    years = sub.time.values.astype(int)
    med_mean = arr.mean(axis=1)
    med_max = arr.max(axis=1)
    tab = pd.DataFrame({"year": years, "med_mean": med_mean, "med_max": med_max})
    ann.close()
    return tab


def _pr_boot(x_thresh, sample_all, sample_fix, n_boot=N_BOOTSTRAP, seed=42):
    """PR/FAR + bootstrap (按年重采样, 与论文 1000 次一致)。返回 (PR, FAR, lo, hi)。"""
    rng = np.random.default_rng(seed)

    def pr(sa, sf):
        p_all = float((sa >= x_thresh).mean())
        p_fix = float((sf >= x_thresh).mean())
        if p_fix == 0:
            return np.inf
        return p_all / p_fix

    point = pr(sample_all, sample_fix)
    boots = []
    for _ in range(n_boot):
        a = sample_all[rng.integers(0, len(sample_all), len(sample_all))]
        f = sample_fix[rng.integers(0, len(sample_fix), len(sample_fix))]
        boots.append(pr(a, f))
    boots = np.array(boots)
    fin = boots[np.isfinite(boots)]
    lo, hi = (np.percentile(fin, [CI[0] * 100, CI[1] * 100])
              if len(fin) else (np.nan, np.nan))
    far = 1 - 1 / point if np.isfinite(point) and point > 0 else np.nan
    return point, far, lo, hi, boots


def cmd_attrib(args):
    """论文口径: PR/FAR = P(年暴露时间 >= 观测阈值) 之比, bootstrap 1000 次。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = pd.read_csv(EXPOSURE_CSV)
    if len(df):
        a = df[df.exp == "ALL"].compound_days.values.astype(float)
        f = df[df.exp == "XGHG"].compound_days.values.astype(float)
        if len(a) and len(f) and f.mean() > 0:
            print(f"[参考] 22 年总暴露时间均值比 ALL/XGHG = "
                  f"{a.mean() / f.mean():.2f} (非论文口径, 仅 sanity)")

    # 观测阈值 (同口径: Med 框, 2022 年值; 均值/最大值两种聚合)
    obs = _obs_annual_threshold()
    v22_mean = float(obs.loc[obs.year == 2022, "med_mean"].iloc[0])
    v22_max = float(obs.loc[obs.year == 2022, "med_max"].iloc[0])
    print(f"观测 Med 2022: 区域均值口径 {v22_mean:.1f} 天, "
          f"格点最大口径 {v22_max:.1f} 天")

    # 模型年样本 (合并成员: 3 成员 × 22 年 = 66 模型年/组)
    def load_sample(exp, col):
        fs = sorted(glob.glob(os.path.join(CESM_INT, f"annual_{exp}_*.csv")))
        if not fs:
            raise SystemExit(f"缺 {exp} 年序列, 先跑 compound")
        parts = []
        for f in fs:
            m = re.search(r"annual_(\w+)_(\d+)\.csv$", os.path.basename(f))
            parts.append(pd.read_csv(f).assign(member=m.group(2)))
        s = pd.concat(parts).sort_values(["member", "year"])
        return s[col].values.astype(float), s

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    results = {}
    for k, col in enumerate(["med_mean", "med_max"]):
        x22 = v22_mean if col == "med_mean" else v22_max
        sa, _ = load_sample("ALL", col)
        sf, _ = load_sample("XGHG", col)
        pr, far, lo, hi, boots = _pr_boot(x22, sa, sf)
        results[col] = (pr, far, lo, hi)
        prs = f"{pr:.1f}" if np.isfinite(pr) else "∞"
        print(f"[{col}] 阈值={x22:.1f} 天: P_ALL={np.mean(sa >= x22):.3f} "
              f"P_fix={np.mean(sf >= x22):.3f}  PR={prs} FAR={far:.2f} "
              f"(bootstrap CI {lo:.1f}-{hi:.1f})")

        ax = axes[0, k]
        bins = np.histogram_bin_edges(np.concatenate([sa, sf, [x22]]), bins=14)
        ax.hist(sf, bins=bins, alpha=0.65, label="FixGHG (model-years)",
                color="#4878cf")
        ax.hist(sa, bins=bins, alpha=0.65, label="ALL (model-years)",
                color="#d65f5f")
        ax.axvline(x22, color="k", ls="--", lw=1.2,
                   label=f"obs 2022 = {x22:.0f} d")
        ax.set_xlabel(f"Annual compound days ({col}, Med box)")
        ax.set_ylabel("Model years")
        ax.set_title(f"P0: {col}  PR={prs} FAR={far:.2f}")
        ax.legend(fontsize=8)

        ax = axes[1, k]
        fin = boots[np.isfinite(boots)]
        if len(fin):
            ax.hist(np.minimum(fin, 50), bins=30, color="#d65f5f", alpha=0.75)
        ax.axvline(min(pr, 50) if np.isfinite(pr) else 50, color="k", lw=1.5)
        ax.set_xlabel("Bootstrapped PR (clipped at 50)")
        ax.set_ylabel("Bootstrap replicates")
    fig.suptitle("CESM1-LE P0 (3 members): Probability Ratio validation "
                 "(paper Fig.7 metric)", fontsize=11)
    fig.tight_layout()
    os.makedirs(C.FIGURES_DIR, exist_ok=True)
    fig.savefig(FIG7_PNG, dpi=200)
    print(f"图 -> {FIG7_PNG}")


# ──────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="CESM1-LE Phase 6 归因管线 (P0)")
    sp = p.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "pairs", "detect", "compound", "attrib"):
        q = sp.add_parser(name)
        if name != "pairs":
            q.add_argument("--members", type=int, default=C.CESM_P0_MEMBERS)
        q.set_defaults(func=globals()[f"cmd_{name}"])
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
