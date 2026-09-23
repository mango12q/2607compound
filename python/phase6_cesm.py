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

用法（20 成员全量，推荐序列；口径见文件顶部 COMPOUND_DEF 等常量与
results/phase6审计报告.md §4 的口径决策记录）:
  python phase6_cesm.py pairs
  python phase6_cesm.py prepare  --members 20
  python phase6_cesm.py detect   --members 20 --baseline xghg --loo --tag _v4
  python phase6_cesm.py compound --members 20 --tag _v4 --compound-def envelope
  python phase6_cesm.py attrib   --members 20 --tag _v4 --compound-def envelope --boot indep
  可选敏感性：
  python phase6_cesm.py compound --members 20 --tag _v4e --compound-def exceed   # 共超标对照
  python phase6_cesm.py attrib   --members 20 --tag _v4  --boot block            # 分层块 bootstrap
  python phase6_cesm.py attrib   --members 20 --tag _v4  --agg med_p90 med_max   # 单口径

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

# ══════════════════════════════════════════════════════════════════════════
# Phase 6 口径决策（2026-09-23 用户拍板；原委见 results/phase6审计报告.md §4）
# ══════════════════════════════════════════════════════════════════════════
# 决策 1B：复合事件定义 = **MHW 包络**（论文模型 Methods paper_text.txt:546
#   "a marine heatwave fully encompasses a terrestrial heatwave"），
#   与已定稿的图1j-l（方案 B）同语义：
#     某 MHW 完全涵盖 >=1 个 THW 事件 -> 该 MHW 的**全部跨度天**计为复合天。
#   共超标口径（论文观测 Methods L503 / compound_events.identify_compound_events）
#   保留为 `--compound-def exceed`，供敏感性对照；图1a-i/1m/图2 仍用共超标。
COMPOUND_DEF = "envelope"       # {"envelope", "exceed"}
# 决策 3A：主口径 = 区域暴露均值；p90 敏感性；格点最大降为参考
MAIN_AGG = "med_mean"
AGG_COLS = ("med_mean", "med_p90", "med_max")
AGG_LABEL = {"med_mean": "区域均值（主口径）",
             "med_p90": "区域 p90（敏感性）",
             "med_max": "格点最大（参考，原 P0 口径）"}
# 决策 2C：归因阈值扫描 + 论文 Fig.3c 的三条年份参考线（Med&BS 面板）
SWEEP_MIN, SWEEP_MAX, SWEEP_STEP = 0.0, 100.0, 1.0
PAPER_THR_REFS = {2003: 62.0, 2022: 78.0, 2023: 72.0}   # 论文 Fig.3c 垂直线
# 决策 5A：主口径 = 独立重采样（论文 Methods :585-587 字面）；block 作附录
BOOT_MODE = "indep"             # {"indep", "block"}（block = 成员内分层 + 块）
N_BOOTSTRAP = C.N_BOOTSTRAP
CI = C.CI_ALPHA

MEMBERS_P0 = C.CESM_ALL_MEMBERS[:C.CESM_P0_MEMBERS]


def select_members(n):
    """★ F6 修复：--members N 必须作用于**全量名单** CESM_ALL_MEMBERS。

    原实现 `MEMBERS_P0[:N]` 中 MEMBERS_P0 已被 `CESM_P0_MEMBERS=3` 截成前 3 个，
    因此 `--members 20` 与 `--members 3` 完全等价（静默只跑 3 个成员），
    全量跑时会以为是 20+20，实际仍是 3+3。此处改为显式取全量名单前 N 个，
    并对 N 越界显式报错。
    """
    n = int(n)
    if n < 1:
        raise SystemExit(f"--members 必须 >=1，收到 {n}")
    if n > len(C.CESM_ALL_MEMBERS):
        raise SystemExit(
            f"--members {n} 超出可用名单（{len(C.CESM_ALL_MEMBERS)} 个："
            f"{','.join(C.CESM_ALL_MEMBERS)}）")
    return C.CESM_ALL_MEMBERS[:n]


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
        for m in select_members(getattr(args, 'members', C.CESM_P0_MEMBERS)):
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
def _load_sst_points(exp, m, pairs_df):
    """配对海点 SST 序列 (块读+对角抽取)。返回 (vals(nt,npair), time, kmt_pt)。"""
    segs = find_sst_segments(exp, m)
    if not segs:
        raise FileNotFoundError(f"{exp} {m}: 无 SST 段")
    pj = pairs_df.ocean_lat_idx.values
    pi = pairs_df.ocean_lon_idx.values

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
    return vals, time, kmt_pt


# ★ 审计修复 2026-09-23（结果见 results/phase6审计报告.md）★
# 修复项：
#   F1 `_run_events` 的桥接/过滤顺序（原「先桥接后过滤」→ 改为逐行复刻
#      heatwaveR 0.5.5 的 `proto_event()`：先取 >=min_dur 的游程作种子，再桥接）
#   F2 `_pooled_threshold_t2m` 的 axis 崩溃（原 1-D `stacked` 求分位退化为标量，
#      206 个陆点共用一条曲线）
#   F3 阈值分位改为 heatwaveR `ts2clm` 语义：**窗内合并原始样本**再取分位
#      （原 SST 完全无窗；T2m 是「逐日分位的再分位」）
#   F4 阈值缓存加入成员名单指纹（原先换 --members 会静默复用旧缓存）
#   F5 支持 leave-one-out（`exclude` 参数，剔除被检测成员自身）
THRESH_VERSION = "v3_w11_loo"


def _rle_all(mask):
    """连续同值段 -> [(value, start, end)]（含端点，0-based）。"""
    x = np.asarray(mask).astype(np.int8)
    if x.size == 0:
        return []
    idx = np.flatnonzero(np.diff(x) != 0) + 1
    b = np.concatenate(([0], idx, [x.size]))
    return [(bool(x[b[i]]), int(b[i]), int(b[i + 1] - 1))
            for i in range(len(b) - 1)]


def _run_events(x, time=None, min_dur=5, max_gap=2):
    """超标 bool 序列 -> 事件 [(start, end)]（含端点，0-based）。

    ★ 逐行复刻 heatwaveR 0.5.5 的 `proto_event()`（detect_event 的内部实现）：
      1) 原始超标游程中 `duration >= min_dur` 的为「种子」；
      2) durationCriterion 只在种子段为 True；
      3) 若 joinAcrossGaps：把 durationCriterion 中**所有**长度 ∈ [1, max_gap]
         且「右端 > 首个种子起点」的 False 连续段整段置 True
         —— 含最后一个种子之后的**尾部空档**（使末事件延长 ≤max_gap 天），
         不含第一个种子之前的**首部空档**（头尾不对称）；
      4) 最终事件 = 置 True 后的极大连续段。
    等价性校验：450 例（150 条随机 0/1 序列 × 3 组参数）与真实 heatwaveR
    `detect_event` **0 例不一致**；另有 6 个手工边界用例逐一相符。
    详见 results/phase6审计报告.md 与 results/phase6_audit_lead_check7.py。
    """
    x = np.asarray(x).astype(np.int8)
    n = x.size
    runs = _rle_all(x)
    seeds = [(a, b) for v, a, b in runs if v and (b - a + 1) >= min_dur]
    if not seeds:
        return []
    dc = np.zeros(n, dtype=bool)
    for a, b in seeds:
        dc[a:b + 1] = True
    first_start = seeds[0][0]
    for v, a, b in _rle_all(dc):
        if not v and b > first_start and 1 <= (b - a + 1) <= max_gap:
            dc[a:b + 1] = True
    return [(a, b) for v, a, b in _rle_all(dc) if v]


def _thresh_cache_path(kind, members, exclude):
    """阈值缓存路径带**成员名单指纹**，避免换 --members / 换 LOO 时静默复用旧缓存。"""
    tag = "-".join(sorted(members)) + ("_loo" + exclude if exclude else "")
    return os.path.join(CESM_INT, f"thresh_{kind}_xghg_{THRESH_VERSION}_{tag}.npz")


def _pooled_threshold(pairs_df, members, exclude=None, kind="sst"):
    """XGHG 合并反事实基准阈值 (366, npt)，heatwaveR ts2clm 语义。

    kind='sst' : 配对海点 SST；kind='t2m': 配对陆点 T2m。
    两者统一为「11 天窗内**合并原始样本**再取 90 分位」（windowHalfWidth=5），
    与 python/detect_events.R 的 ts2clm(pctile=90, windowHalfWidth=5L,
    smoothPercentile=FALSE) 同语义（smoothPercentile 只控制是否对阈值序列再做
    31 天滑动平均，不影响 11 天窗合并）。
    exclude：leave-one-out，从池中剔除该成员（主口径）。
    """
    pool = [m for m in members if m != exclude]
    if not pool:
        raise ValueError("池为空：exclude 后没有剩余成员")
    cache = _thresh_cache_path(kind, pool, None)
    if os.path.exists(cache):
        z = np.load(cache)
        if int(z["n_members"]) == len(pool):
            print(f"  阈值缓存命中 {os.path.basename(cache)} (池={len(pool)} 成员)")
            return z["thresh"]
        print(f"  !! 缓存成员数不符({int(z['n_members'])}!={len(pool)})，重建")
    chunks = []
    for m in pool:
        if kind == "sst":
            vals, time, _ = _load_sst_points("XGHG", m, pairs_df)
        else:
            f = os.path.join(CESM_INT, f"XGHG_{m}_T2m.nc")
            ds = xr.open_dataset(f)
            da = ds["T2m"].isel(
                lat=xr.DataArray(pairs_df.land_lat_idx.values, dims="p"),
                lon=xr.DataArray(pairs_df.land_lon_idx.values, dims="p"))
            vals = da.transpose("time", "p").values.astype(np.float64)
            time = pd.DatetimeIndex(da.time.values)
            ds.close()
        chunks.append((vals, time.dayofyear.values))
        print(f"  基准池({kind}): XGHG {m} ({vals.shape[0]} 天)")
    doy_all = np.concatenate([d for _, d in chunks])
    mat = np.concatenate([v for v, _ in chunks], axis=0)
    npt = mat.shape[1]
    thresh = np.full((366, npt), np.nan)
    cal = 365 if (doy_all.max() <= 365 and 366 not in set(doy_all.tolist())) else 366
    # ★ F9：循环上界必须是 cal（而非硬编码 365）。proc 文件日历标为
    #   proleptic_gregorian 但数据实为 noleap，闰年 12-31 的 dayofyear = 366，
    #   原写法只填 1..365 ⇒ 第 366 行全 NaN ⇒ 闰年 12-31 恒不超阈
    #   （6 天/序列 × 206 点）。heatwaveR ts2clm 会为 366 行都算阈值。
    for d in np.arange(1, cal + 1):
        win = [(d + k - 1) % cal + 1 for k in range(-5, 6)]
        pool_rows = [mat[doy_all == w] for w in win]
        pool_rows = [r for r in pool_rows if len(r)]
        if pool_rows:
            thresh[d - 1] = np.nanpercentile(
                np.concatenate(pool_rows, axis=0), 90, axis=0)
    np.savez_compressed(cache, thresh=thresh, doy_map=np.arange(366),
                        n_members=len(pool), members=np.array(pool),
                        version=THRESH_VERSION, calendar=cal)
    print(f"  {kind.upper()} 反事实基准 (11 天窗, 池 {len(pool)} 成员) -> {cache}")
    return thresh


def _pooled_threshold_sst(pairs_df, members, exclude=None):
    return _pooled_threshold(pairs_df, members, exclude, kind="sst"), np.arange(366)


def _pooled_threshold_t2m(pairs_df, members, exclude=None):
    return _pooled_threshold(pairs_df, members, exclude, kind="t2m")


def _detect_mhw_member(exp, m, pairs_df, thresh_ext=None, suffix=""):
    """MHW: 配对海点 + 逐 doy 90 分位气候态 + 游程状态机 (与观测同语义)。

    thresh_ext=None -> 成员自身气候态 (v1); 传入 (366,npair) 外置阈值 -> 反事实基准 (v2)。
    """
    out_csv = os.path.join(CESM_INT, f"mhw{suffix}_{exp}_{m}.csv")
    if os.path.exists(out_csv):
        print(f"已存在, 跳过 {out_csv}")
        return out_csv

    vals, time, _ = _load_sst_points(exp, m, pairs_df)

    print(f"{exp} {m}: SST {vals.shape[0]} 天 x {vals.shape[1]} 配对点")

    doy = time.dayofyear.values
    nt, npair = vals.shape
    if thresh_ext is not None:
        thresh = thresh_ext
    else:
        # 逐 doy 90 分位气候态 (成员自身 2000-2021)。
        # ★ F3 修复：必须与 heatwaveR ts2clm 一样做 **11 天窗内合并原始样本**，
        #   原实现只用单日 doy 分位（实测使超标日放大 1.49–1.53 倍）。
        cal = 365 if (doy.max() <= 365 and 366 not in set(doy.tolist())) else 366
        thresh = np.full((366, npair), np.nan)
        for d in np.arange(1, cal + 1):   # ★ F9：上界 cal，见 _pooled_threshold 注释
            win = [(d + k - 1) % cal + 1 for k in range(-5, 6)]
            rs = [vals[doy == w] for w in win]
            rs = [r for r in rs if len(r)]
            if rs:
                thresh[d - 1] = np.nanpercentile(np.concatenate(rs, axis=0),
                                                 90, axis=0)
    thr_t = thresh[doy - 1]                       # (nt, npairs)

    # 游程事件 (min_dur=5, max_gap=2) — 与 detect_mhw._EventTracker 同语义
    events = []
    for p in range(npair):
        x = vals[:, p] > thr_t[:, p]
        x[np.isnan(vals[:, p])] = False
        for a, b in _run_events(x, time):
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


def _pair_table(pairs_df):
    """{(land_lat_idx, land_lon_idx): (land_lat, land_lon,
                                     ocean_lat_idx, ocean_lon_idx)}"""
    return {(int(r.land_lat_idx), int(r.land_lon_idx)):
            (float(r.land_lat), float(r.land_lon),
             int(r.ocean_lat_idx), int(r.ocean_lon_idx))
            for r in pairs_df.itertuples(index=False)}


def _envelope_mask(thw_g, mhw_g, nt, t0):
    """★ 决策 1B：MHW 包络复合掩码。

    与 python/fig_jkl_mhw_envelope.py 的观测侧定义**逐条对齐**：
      1) 取该陆点的所有 THW 事件 [a, b]（日索引）；
      2) 取配对海点的所有 MHW 事件 [ms, me]；
      3) 若某个 MHW 满足 `a >= ms and b <= me`（THW 被该 MHW **完全涵盖**），
         则该 MHW 的**全部跨度天** [ms, me] 计入复合天；
      4) 同一陆点多个 MHW 的跨度取并集。
    注：复合天可超出该陆点的 THW 天集合（这正是包络口径与共超标口径的区别，
    也是图1j/l 量级可达 78/72 的原因）。
    """
    m = np.zeros(nt, dtype=bool)
    if thw_g is None or len(thw_g) == 0 or mhw_g is None or len(mhw_g) == 0:
        return m
    ts = (pd.to_datetime(thw_g.event_start) - t0).dt.days.values
    te = (pd.to_datetime(thw_g.event_end) - t0).dt.days.values
    tin = list(zip(ts, te))
    ms = (pd.to_datetime(mhw_g.event_start) - t0).dt.days.values
    me = (pd.to_datetime(mhw_g.event_end) - t0).dt.days.values
    for mi0, mi1 in zip(ms, me):
        if any(a >= mi0 and b <= mi1 for a, b in tin):
            a, b = max(int(mi0), 0), min(int(mi1), nt - 1)
            if b >= a:
                m[a:b + 1] = True
    return m


def _mask_to_segments(mask, t0, pairs_df, ptab, land_key, ocean_key):
    """逐日 bool 掩码 -> 复合日段记录（列名与 identify_compound_events 兼容）。"""
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    recs = []
    lat, lon, _, _ = ptab[land_key]
    for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1):
        recs.append({"thw_start": t0 + pd.Timedelta(days=int(a)),
                     "thw_end": t0 + pd.Timedelta(days=int(b)),
                     "land_lat_idx": int(land_key[0]),
                     "land_lon_idx": int(land_key[1]),
                     "ocean_lat_idx": int(ocean_key[0]),
                     "ocean_lon_idx": int(ocean_key[1]),
                     "land_lat": lat, "land_lon": lon})
    return recs


def _detect_thw_member_ext(exp, m, pairs_df, thresh, suffix="_x"):
    """THW v2: 外置反事实阈值 (XGHG 合并 11 天窗 90 分位) + 游程事件。

    阈值来源与 heatwaveR ts2clm 同语义 (11 天窗内合并原始样本求分位), 事件逻辑
    (游程>=5 作种子, 桥接<=2) 由 `_run_events` 逐行复刻 heatwaveR `proto_event`,
    并经 450 例模糊测试 0 不一致校验 —— 阈值与事件逻辑两端均与 R 等价。
    """
    out_csv = os.path.join(CESM_INT, f"thw{suffix}_{exp}_{m}.csv")
    if os.path.exists(out_csv):
        print(f"已存在, 跳过 {out_csv}")
        return out_csv
    f = os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc")
    ds = xr.open_dataset(f)
    pj = pairs_df.land_lat_idx.values
    pi = pairs_df.land_lon_idx.values
    da = ds["T2m"].isel(lat=xr.DataArray(pj, dims="p"),
                        lon=xr.DataArray(pi, dims="p"))
    arr = da.transpose("time", "p").values.astype(np.float64)
    time = pd.DatetimeIndex(da.time.values)
    ds.close()

    doy = time.dayofyear.values
    thr_t = thresh[doy - 1]                       # (nt, nland)
    events = []
    for p in range(len(pj)):
        x = arr[:, p] > thr_t[:, p]
        x[np.isnan(arr[:, p])] = False
        for a, b in _run_events(x, time):
            events.append({
                "event_start": time[a], "event_end": time[b],
                "duration": int(b - a + 1),
                "lat_idx": int(pj[p]), "lon_idx": int(pi[p]),
                "lat": float(pairs_df.land_lat.iloc[p]),
                "lon": float(pairs_df.land_lon.iloc[p]),
            })
    df = pd.DataFrame(events)
    df.to_csv(out_csv, index=False)
    print(f"  THW(x) 事件 {len(df)} -> {out_csv}")
    return out_csv


def cmd_detect(args):
    pairs_df = pd.read_csv(PAIRS_CSV)
    baseline = getattr(args, "baseline", "own")
    # ★ F6 修复：成员列表必须来自全量名单，不能被 CESM_P0_MEMBERS 硬截断。
    #   原实现 MEMBERS_P0[:args.members] 中 MEMBERS_P0 已被截成前 3 个，
    #   因此 --members 20 与 --members 3 完全等价（静默）。
    n_mem = int(getattr(args, "members", C.CESM_P0_MEMBERS))
    members = select_members(n_mem)
    loo = bool(getattr(args, "loo", False))
    dtag = getattr(args, "tag", "_x2") or "_x2"
    print(f"检测成员: {members}（共 {len(members)} 个）"
          f"{'  [leave-one-out 基准]' if (baseline == 'xghg' and loo) else ''}"
          f"  输出后缀={dtag!r}")

    if baseline == "xghg":
        print("== v2: XGHG 合并反事实基准 ==")
        if loo:
            # 每个成员用「其余成员」的池建阈，剔除自身（主口径）
            for exp in ("ALL", "XGHG"):
                for m in members:
                    pool = [x for x in members if x not in (m,) or exp == "ALL"]
                    pool = [x for x in members if x != m]
                    if not pool:
                        print(f"!! {exp} {m}: LOO 池为空，跳过")
                        continue
                    try:
                        thr_sst, _ = _pooled_threshold_sst(pairs_df, pool)
                        thr_t2m = _pooled_threshold_t2m(pairs_df, pool)
                    except Exception as e:
                        print(f"!! LOO 阈值失败 {exp} {m}: {e}")
                        continue
                    try:
                        _detect_thw_member_ext(exp, m, pairs_df, thr_t2m,
                                               suffix=dtag)
                    except Exception as e:
                        print(f"!! THW(x) 失败 {exp} {m}: {e}")
                    try:
                        _detect_mhw_member(exp, m, pairs_df, thresh_ext=thr_sst,
                                           suffix=dtag)
                    except Exception as e:
                        print(f"!! MHW(x) 失败 {exp} {m}: {e}")
            return
        thr_sst, _ = _pooled_threshold_sst(pairs_df, members)
        thr_t2m = _pooled_threshold_t2m(pairs_df, members)
        print(f"  in-sample 说明：XGHG 组成员在池中含自身；ALL 组成员不含自身")
        for exp in ("ALL", "XGHG"):
            for m in members:
                try:
                    _detect_thw_member_ext(exp, m, pairs_df, thr_t2m,
                                           suffix=dtag)
                except Exception as e:
                    print(f"!! THW(x) 失败 {exp} {m}: {e}")
                    continue
                try:
                    _detect_mhw_member(exp, m, pairs_df,
                                       thresh_ext=thr_sst, suffix=dtag)
                except Exception as e:
                    print(f"!! MHW(x) 失败 {exp} {m}: {e}")
        return
    for exp in ("ALL", "XGHG"):
        for m in members:
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
    tag = getattr(args, "tag", "")
    cdef = getattr(args, "compound_def", COMPOUND_DEF)
    print(f"== 复合定义 = {cdef} "
          f"({'MHW 包络 fully-encompasses，决策 1B' if cdef == 'envelope' else '逐日共超标 L503'}) ==")
    pairs_df = pd.read_csv(PAIRS_CSV)
    ptab = _pair_table(pairs_df)
    rows = []
    for exp in ("ALL", "XGHG"):
        for m in select_members(getattr(args, 'members', C.CESM_P0_MEMBERS)):
            thw_f = os.path.join(CESM_INT, f"thw{tag}_{exp}_{m}.csv")
            mhw_f = os.path.join(CESM_INT, f"mhw{tag}_{exp}_{m}.csv")
            if not (os.path.exists(thw_f) and os.path.exists(mhw_f)):
                print(f"!! 缺事件表, 跳过 {exp} {m}")
                continue
            t2m = xr.open_dataset(os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc"))
            time_da = t2m["T2m"]
            # ★ F8：原点归一（见 _annual_per_pair 注释）
            t0 = pd.Timestamp(time_da.time.values[0]).normalize()
            nt = time_da.sizes["time"]

            thw = pd.read_csv(thw_f, parse_dates=["event_start", "event_end"])
            mhw = pd.read_csv(mhw_f, parse_dates=["event_start", "event_end"])
            # ★ F8：传入已归一到 00:00 的时间轴，使 THW（T2m 轴，ALL 组为 12:00）
            #   与 MHW（SST 轴，00:00）的日期→索引映射一致。
            time_norm = xr.DataArray(
                pd.DatetimeIndex(time_da.time.values).normalize(),
                dims="time", coords={"time": time_da.time})
            lpd = _pair_maps(pairs_df)
            om = {}
            om_raw = {}
            for k, g in mhw.groupby(["lat_idx", "lon_idx"]):
                om[k] = _event_daily_mask(g, nt, t0)
                om_raw[k] = g
            kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
            thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
            thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}

            comp_days = std_days = thw_days = thw_in_comp = 0
            seg_recs = []
            for lk, ok_ in lpd.items():
                g = thw_by.get(lk)
                if g is None or len(g) == 0:
                    continue
                lm = _event_daily_mask(g, nt, t0)
                thw_days += int(lm.sum())
                if cdef == "envelope":
                    cm = _envelope_mask(g, om_raw.get(ok_), nt, t0)
                else:
                    m_ = om.get(ok_)
                    cm = lm & (m_ if m_ is not None else np.zeros(nt, bool))
                comp_days += int(cm.sum())
                thw_in_comp += int((lm & cm).sum())
                # standalone = 该陆点 THW 日中**不在复合日**的天数
                # （共超标口径下等价于原 `lm & ~MHW`，行为不变）
                std_days += int((lm & ~cm).sum())
                if cm.any():
                    seg_recs += _mask_to_segments(cm, t0, pairs_df, ptab, lk, ok_)

            if cdef == "envelope":
                comp = pd.DataFrame(seg_recs) if seg_recs else pd.DataFrame(
                    columns=["thw_start", "thw_end", "land_lat_idx",
                             "land_lon_idx", "ocean_lat_idx", "ocean_lon_idx",
                             "land_lat", "land_lon"])
            else:
                # 共超标：仍复用观测链路的 identify_compound_events（口径单一来源），
                # 并断言其段长与上面逐日计数同源，防两套实现漂移。
                comp = identify_compound_events(mhw, thw, pairs_df, time_norm)
                if len(comp):
                    seg_len = int(((pd.to_datetime(comp.thw_end)
                                    - pd.to_datetime(comp.thw_start)).dt.days + 1).sum())
                    assert seg_len == comp_days, (seg_len, comp_days)

            rows.append({"exp": exp, "member": m, "compound_def": cdef,
                         "compound_days": comp_days,
                         "thw_in_compound_days": thw_in_comp,
                         "standalone_days": std_days,
                         "thw_pair_days": thw_days})
            print(f"{exp} {m} [{cdef}]: 段数={len(comp)} compound={comp_days:,} "
                  f"(其中 THW 日 {thw_in_comp:,}) standalone={std_days:,} "
                  f"THW(配对)={thw_days:,}")

            # 逐年暴露时间 (PR 口径: 模型年 = 22 年 × 成员; 聚合用 Med 框)
            ann = _annual_per_pair(comp, time_da.time, pairs_df)
            ann.to_csv(os.path.join(CESM_INT, f"annual{tag}_{exp}_{m}.csv"),
                       index=False)
            t2m.close()
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(CESM_INT, f"exposure_members{tag}.csv"),
              index=False)
    print(f"暴露时间表 -> {os.path.join(CESM_INT, f'exposure_members{tag}.csv')}")


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
    # ★ F8 修复：把原点归一到 00:00。ALL 组成品的 T2m 时间是 12:00，
    #   而事件表时刻继承各自的序列轴（MHW 来自 SST=00:00），
    #   `(date - t0).days` 的向下取整会让 ALL 组的 MHW 掩码整体早 1 天。
    t0 = pd.Timestamp(time_da.time.values[0]).normalize()
    daily = np.zeros((nt, len(pairs_df)), dtype=np.int8)
    for seg in comp.itertuples(index=False):
        p = pos.get((int(seg.land_lat_idx), int(seg.land_lon_idx)))
        if p is None:
            continue
        a = (pd.Timestamp(seg.thw_start).normalize() - t0).days
        b = (pd.Timestamp(seg.thw_end).normalize() - t0).days
        daily[max(a, 0):min(b, nt - 1) + 1, p] = 1
    ann = np.stack([daily[years == y].sum(axis=0) for y in uyears])  # (yr, pair)
    med = (pairs_df.land_lat.between(30, 47) & pairs_df.land_lon.between(5, 42)).values
    out = pd.DataFrame({"year": uyears,
                        "med_mean": ann[:, med].mean(axis=1),
                        "med_p90": np.percentile(ann[:, med], 90, axis=1),
                        "med_max": ann[:, med].max(axis=1),
                        "eur_mean": ann.mean(axis=1),
                        "eur_p90": np.percentile(ann, 90, axis=1),
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
    """PR/FAR + bootstrap。返回 dict（含 CI 与 inf 计数）。

    ★ F7 修复：不再静默丢弃 inf 重复。
      P_fix=0 的重复意味着"反事实世界中一次都没发生"——这是最强证据，
      原实现 `boots[np.isfinite(boots)]` 把它丢掉会把 CI 系统性压低
      （P0 实测 med_max 口径 372/1000 为 inf；med_mean 口径 1000/1000 全 inf）。
      现在：`lo/hi` 为**保留 inf** 的经验分位数（上界可为 inf）；
      `lo_fin/hi_fin` 为仅有限样本的对照区间；并报告 inf/nan 比例。
    """
    rng = np.random.default_rng(seed)

    def pr(sa, sf):
        p_all = float((sa >= x_thresh).mean())
        p_fix = float((sf >= x_thresh).mean())
        if p_all == 0 and p_fix == 0:
            return np.nan          # ★ 0/0 不是 ∞
        if p_fix == 0:
            return np.inf
        return p_all / p_fix

    point = pr(sample_all, sample_fix)
    boots = []
    for _ in range(n_boot):
        a = sample_all[rng.integers(0, len(sample_all), len(sample_all))]
        f = sample_fix[rng.integers(0, len(sample_fix), len(sample_fix))]
        boots.append(pr(a, f))
    boots = np.array(boots, dtype=float)
    n_inf = int(np.isinf(boots).sum())
    n_nan = int(np.isnan(boots).sum())
    with np.errstate(invalid="ignore", all="ignore"):
        # 经验分位数用**次序统计量**实现：np.percentile 在两端都是 inf 时会算出
        # inf-inf=nan，把"上界为 ∞"这个正确结论错误地变成 nan。
        _sv = np.sort(boots[~np.isnan(boots)])

        def _q(p):
            if len(_sv) == 0:
                return np.nan
            k = int(np.ceil(p / 100.0 * len(_sv))) - 1
            return float(_sv[min(max(k, 0), len(_sv) - 1)])

        lo, hi = _q(CI[0] * 100), _q(CI[1] * 100)
    fin = boots[np.isfinite(boots)]
    lo_f, hi_f = (np.percentile(fin, [CI[0] * 100, CI[1] * 100])
                  if len(fin) else (np.nan, np.nan))
    far = 1 - 1 / point if np.isfinite(point) and point > 0 else np.nan
    return dict(pr=point, far=far, lo=lo, hi=hi, lo_fin=lo_f, hi_fin=hi_f,
                n_inf=n_inf, n_nan=n_nan, n_boot=len(boots), boots=boots)


def _boot_indices(member, n_boot, rng, mode="indep"):
    """返回 (n_boot, N) 整型重采样索引矩阵。

    mode='indep'：对 N 个模型年独立有放回重采样（论文 Methods :585-587 字面，主口径）。
    mode='block'：成员内分层 —— 先对成员有放回抽，再在抽中成员内对其年份有放回抽，
                  保留同成员年际自相关（附录稳健性检验）。
    """
    member = np.asarray(member)
    N = len(member)
    if mode == "block":
        umem = np.unique(member)
        pos = {m: np.flatnonzero(member == m) for m in umem}
        out = np.empty((n_boot, N), dtype=int)
        for b in range(n_boot):
            chosen = rng.choice(umem, size=len(umem), replace=True)
            out[b] = np.concatenate(
                [rng.choice(pos[m], size=len(pos[m]), replace=True) for m in chosen])
        return out
    return rng.integers(0, N, size=(n_boot, N))


def _emp_quantile(sorted_vals, pct):
    """次序统计量分位数（对 inf 安全；避免 np.percentile 在 inf-inf 处返回 nan）。"""
    n = len(sorted_vals)
    if n == 0:
        return np.nan
    k = int(np.ceil(pct / 100.0 * n)) - 1
    return float(sorted_vals[min(max(k, 0), n - 1)])


def _sweep_one(sa, sf, idx_a, idx_f, thrs, n_boot):
    """单聚合列的阈值扫描：返回逐阈值 PR/FAR 与 bootstrap CI 的 DataFrame。"""
    rows = []
    for x in thrs:
        ia = (sa >= x)
        ifx = (sf >= x)
        p_all = float(ia.mean())
        p_fix = float(ifx.mean())
        if p_all == 0 and p_fix == 0:
            pr = far = np.nan
        elif p_fix == 0:
            pr = np.inf
            far = 1.0 if p_all > 0 else np.nan
        else:
            pr = p_all / p_fix
            far = 1.0 - p_fix / p_all
        ba = ia[idx_a].mean(axis=1)          # (n_boot,)
        bf = ifx[idx_f].mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            prb = np.where((ba == 0) & (bf == 0), np.nan,
                           np.where(bf == 0, np.inf,
                                    ba / np.where(bf == 0, 1.0, bf)))
        sv = np.sort(prb[~np.isnan(prb)])
        fin = prb[np.isfinite(prb)]
        lo_f, hi_f = (np.percentile(fin, [CI[0] * 100, CI[1] * 100])
                      if len(fin) else (np.nan, np.nan))
        rows.append({"threshold": float(x), "p_all": p_all, "p_fix": p_fix,
                     "PR": pr, "FAR": far,
                     "PR_lo": _emp_quantile(sv, CI[0] * 100),
                     "PR_hi": _emp_quantile(sv, CI[1] * 100),
                     "PR_lo_fin": float(lo_f), "PR_hi_fin": float(hi_f),
                     "n_inf": int(np.isinf(prb).sum()),
                     "n_nan": int(np.isnan(prb).sum()), "n_boot": int(n_boot)})
    return pd.DataFrame(rows)


def _our_year_refs(cdef):
    """本复现自己的年份参考值（用于与论文 62/78/72 对照）。"""
    refs = {}
    if cdef == "envelope":
        fp = os.path.join(C.TABLES_DIR, "fig_jkl_envelope.json")
        try:
            import json
            with open(fp, encoding="utf-8") as fh:
                j = json.load(fh)
            for k, v in j.items():
                if "mediterr" in k:
                    yy = dict(zip(v["years"], v["values"]))
                    refs["envelope·图1j 区域均值"] = {
                        y: float(yy[y]) for y in PAPER_THR_REFS if y in yy}
        except Exception as e:
            print(f"  (本复现包络参考值不可用: {e})")
    try:
        obs = _obs_annual_threshold()
        for col in ("med_mean", "med_max"):
            refs[f"共超标·观测 {col}"] = {
                y: float(obs.loc[obs.year == y, col].iloc[0])
                for y in PAPER_THR_REFS if (obs.year == y).any()}
    except Exception as e:
        print(f"  (观测参考值不可用: {e})")
    return refs


def cmd_attrib(args):
    """★ 决策 2C/3A/5A：阈值扫描 + 三聚合口径 + 两种 bootstrap。

    与旧实现（只报单点阈值 + 丢弃 inf 的 CI）的区别见
    results/phase6审计报告.md §4 与 results/phase6审计_修复前后对比.md。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tag = getattr(args, "tag", "")
    cdef = getattr(args, "compound_def", COMPOUND_DEF)
    boot_mode = getattr(args, "boot", BOOT_MODE)
    cols = tuple(getattr(args, "agg", None) or AGG_COLS)
    thrs = np.arange(SWEEP_MIN, SWEEP_MAX + 1e-9,
                     float(getattr(args, "thr_step", SWEEP_STEP)))
    n_boot = int(getattr(args, "n_boot", N_BOOTSTRAP))

    df_path = os.path.join(CESM_INT, f"exposure_members{tag}.csv")
    if os.path.exists(df_path):
        d = pd.read_csv(df_path)
        if "compound_def" in d.columns:
            print(f"[口径] 暴露表记录的复合定义 = {d.compound_def.iloc[0]}")
        a = d[d.exp == "ALL"].compound_days.values.astype(float)
        f = d[d.exp == "XGHG"].compound_days.values.astype(float)
        if len(a) and len(f) and f.mean() > 0:
            print(f"[参考] 22 年总暴露时间均值比 ALL/XGHG = {a.mean()/f.mean():.2f}")

    def load_sample(exp, col):
        fs = sorted(glob.glob(os.path.join(CESM_INT, f"annual{tag}_{exp}_*.csv")))
        if not fs:
            raise SystemExit(f"缺 {exp} 年序列 (tag={tag!r}), 先跑 compound")
        parts = []
        for fp in fs:
            mm = re.search(r"annual_\w+_(\d+)\.csv$", os.path.basename(fp))
            parts.append(pd.read_csv(fp).assign(member=mm.group(1)))
        ss = pd.concat(parts).sort_values(["member", "year"])
        if col not in ss.columns:
            raise SystemExit(f"年序列表缺列 {col!r}（已有 {list(ss.columns)}）"
                             f"；请用新版 compound 重跑以生成 med_p90")
        return ss[col].values.astype(float), ss.member.values

    rng = np.random.default_rng(42)
    refs = _our_year_refs(cdef)
    print(f"\n扫描阈值 {thrs[0]:.0f}..{thrs[-1]:.0f} 天（步长 {thrs[1]-thrs[0]:.0f}）"
          f"，bootstrap={boot_mode}×{n_boot}")
    print(f"论文 Fig.3c 参考线（Med&BS）：{PAPER_THR_REFS}")
    for k, v in refs.items():
        print(f"本复现参考值 [{k}]：{ {y: round(x,1) for y, x in v.items()} }")

    fig, axes = plt.subplots(len(cols), 2, figsize=(13, 3.6 * len(cols)),
                             squeeze=False)
    os.makedirs(C.TABLES_DIR, exist_ok=True)
    summary = []
    for row, col in enumerate(cols):
        sa, ma = load_sample("ALL", col)
        sf, mf = load_sample("XGHG", col)
        idx_a = _boot_indices(ma, n_boot, rng, boot_mode)
        idx_f = _boot_indices(mf, n_boot, rng, boot_mode)
        tab = _sweep_one(sa, sf, idx_a, idx_f, thrs, n_boot)
        csv = os.path.join(C.TABLES_DIR, f"phase6_attrib_sweep{tag}_{col}.csv")
        tab.to_csv(csv, index=False)
        print(f"\n[{col}] {AGG_LABEL.get(col, '')}  样本 N_ALL={len(sa)} N_XGHG={len(sf)}"
              f"  -> {csv}")
        # 论文参考线处读数
        for y, x in PAPER_THR_REFS.items():
            r = tab[np.isclose(tab.threshold, x)]
            if len(r):
                r = r.iloc[0]
                print(f"    @论文 {y} 参考线 {x:.0f} 天: P_ALL={r.p_all:.3f} "
                      f"P_fix={r.p_fix:.3f} PR={r.PR:.2f} FAR={r.FAR:.3f} "
                      f"(inf {int(r.n_inf)}/{int(r.n_boot)})")
                summary.append({"agg": col, "year": y, "threshold": x,
                                "p_all": r.p_all, "p_fix": r.p_fix,
                                "PR": r.PR, "FAR": r.FAR,
                                "PR_lo": r.PR_lo, "PR_hi": r.PR_hi,
                                "n_inf": int(r.n_inf), "boot": boot_mode})

        prp = tab.PR.replace([np.inf], np.nan)
        ax = axes[row, 0]
        ax.plot(tab.threshold, tab.FAR, color="#4878cf", lw=1.6, label="FAR")
        ax.set_ylim(0, 1.05)
        ax.set_ylabel(f"FAR\n({col})")
        ax = axes[row, 1]
        ax.plot(tab.threshold, prp, color="#4878cf", lw=1.6, label="PR")
        ax.set_yscale("log")
        ax.set_ylabel(f"PR\n({col})")
        for ax in (axes[row, 0], axes[row, 1]):
            for y, x in PAPER_THR_REFS.items():
                ax.axvline(x, color="k", ls="--", lw=0.9, alpha=0.6)
                ax.text(x, ax.get_ylim()[1], f" {y}", fontsize=7,
                        va="top", rotation=90)
            for nm, vv in refs.items():
                if 2022 in vv:
                    ax.axvline(vv[2022], color="#d65f5f", ls=":", lw=1.0,
                               label=f"本复现 2022 ({nm})")
            ax.set_xlim(thrs[0], thrs[-1])
            ax.set_xlabel("Threshold (compound heatwave days)")
            ax.grid(True, alpha=0.25, ls=":")
        axes[row, 1].legend(fontsize=7, loc="upper right")
    fig.suptitle(f"Phase 6 attribution sweep — compound def={cdef}, "
                 f"boot={boot_mode}, tag={tag!r}", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    os.makedirs(C.FIGURES_DIR, exist_ok=True)
    out_png = os.path.join(C.FIGURES_DIR, f"fig3_attribution_sweep{tag}.png")
    fig.savefig(out_png, dpi=200)
    plt.close(fig)
    print(f"图 -> {out_png}")
    if summary:
        sp = os.path.join(C.TABLES_DIR, f"phase6_attrib_summary{tag}.csv")
        pd.DataFrame(summary).to_csv(sp, index=False)
        print(f"汇总 -> {sp}")


# ──────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="CESM1-LE Phase 6 归因管线 (P0)")
    sp = p.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "pairs", "detect", "compound", "attrib"):
        q = sp.add_parser(name)
        if name == "detect":
            q.add_argument("--baseline", choices=["own", "xghg"], default="own",
                           help="own=成员自身气候态(v1); xghg=XGHG 合并反事实基准(v2)")
            q.add_argument("--tag", default="_x2",
                           help="输出事件表后缀（默认 _x2，不覆盖旧 P0 的 _x 产物）")
            q.add_argument("--loo", action="store_true",
                           help="leave-one-out：检测成员 m 时从 XGHG 池中剔除 m 自身"
                                "（仅 --baseline xghg 有效；TECHNICAL_SPEC_PHASE_B 步骤 2b 主口径）")
        if name != "pairs":
            q.add_argument("--members", type=int, default=C.CESM_P0_MEMBERS,
                           help="成员数（作用于全量 20 人名单，不再被 CESM_P0_MEMBERS 截断）")
        if name in ("compound", "attrib"):
            q.add_argument("--tag", default="",
                           help="事件文件后缀: ''=v1(own), '_x'=v2(XGHG 基准)")
            q.add_argument("--compound-def", choices=["envelope", "exceed"],
                           default=COMPOUND_DEF, dest="compound_def",
                           help="复合定义: envelope=MHW 包络(论文模型 Methods, 决策 1B, 默认); "
                                "exceed=逐日共超标(观测 Methods L503)")
        if name == "attrib":
            q.add_argument("--boot", choices=["indep", "block"], default=BOOT_MODE,
                           help="bootstrap: indep=模型年独立重采样(论文口径, 默认); "
                                "block=成员内分层+块(附录稳健性)")
            q.add_argument("--agg", nargs="+", default=list(AGG_COLS),
                           help=f"聚合口径列，默认 {list(AGG_COLS)}")
            q.add_argument("--thr-step", type=float, default=SWEEP_STEP,
                           help="阈值扫描步长（天）")
            q.add_argument("--n-boot", type=int, default=N_BOOTSTRAP)
        q.set_defaults(func=globals()[f"cmd_{name}"])
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
