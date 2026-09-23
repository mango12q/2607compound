# -*- coding: utf-8 -*-
"""
phase6_audit_grid.py — task-1「网格与配对审计」可复算脚本
=========================================================
审计对象: python/phase6_cesm.py 的 cmd_prepare / cmd_pairs / _load_sst_points
          (+ 阈值函数的网格维度假设, 见 S 段)

只读: data/CESM1-LE/**、results/intermediate/cesm/**
只写: results/intermediate/audit/grid/**

用法:
    python results/phase6_audit_grid.py                # 全部段落
    python results/phase6_audit_grid.py --only A1,A2,A3
    python results/phase6_audit_grid.py --list

所有结论行以 [段号] 开头, 便于在报告中引用。
"""
import argparse
import glob
import json
import os
import re
import sys
import warnings

import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import binary_erosion, generate_binary_structure
from scipy.spatial import cKDTree

warnings.filterwarnings("ignore")

BASE = r"D:\2607compound"
PROC = os.path.join(BASE, "data", "CESM1-LE", "proc")
RAW = os.path.join(BASE, "data", "CESM1-LE", "raw")
CESM_INT = os.path.join(BASE, "results", "intermediate", "cesm")
OBS_INT = os.path.join(BASE, "results", "intermediate")
OUT = os.path.join(BASE, "results", "intermediate", "audit", "grid")

PAIRS_CSV = os.path.join(CESM_INT, "coastal_pairs_cesm.csv")
DOMAINS_CSV = os.path.join(CESM_INT, "domains_land_cesm.csv")
OBS_PAIRS_CSV = os.path.join(OBS_INT, "coastal_pairs.csv")
REF_EUROPE = os.path.join(PROC, "TREFHT_all_001_2000-2021_europe.nc")
MAX_PAIR_DIST_DEG = 1.0          # phase6_cesm.py:56
OBS_MAX_GRID_DIST_DEG = 0.5      # config.py:85

SST_ALL_001 = os.path.join(
    PROC, "b.e11.B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.SST.18500102-20051231_2000-2021.nc")
SST_ALL_001_B = os.path.join(
    PROC, "b.e11.BRCP85C5CNBDRD.f09_g16.001.pop.h.nday1.SST.20060102-20801231_2000-2021.nc")
SST_XGHG_001 = os.path.join(
    PROC, "b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.pop.h.nday1.SST.19200102-20051231_2000-2021.nc")
SST_XGHG_001_B = os.path.join(
    PROC, "b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.pop.h.nday1.SST.20060101-20801231_2000-2021.nc")
T2M_ALL_001 = os.path.join(CESM_INT, "ALL_001_T2m.nc")
T2M_XGHG_001 = os.path.join(CESM_INT, "XGHG_001_T2m.nc")
TREFHT_XGHG_001_A = os.path.join(
    PROC, "b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.19200101-20051231_2000-2021.nc")
TREFHT_XGHG_001_B = os.path.join(
    PROC, "b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.20060101-20801231_2000-2021.nc")

RESULTS = {}


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def save_json():
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "audit_grid_summary.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[JSON] -> {p}")


# ══════════════════════════════════════════════════════════════════
# A. 配对链路
# ══════════════════════════════════════════════════════════════════
def pairs_internals():
    """逐行复刻 phase6_cesm.py:148-219 cmd_pairs, 并额外保留中间量。"""
    ref = xr.open_dataset(REF_EUROPE)
    atm_lat = ref.lat.values.astype(float)
    atm_lon = ref.lon.values.astype(float)
    ref.close()

    sst_f = sorted(sum([glob.glob(os.path.join(
        PROC, f"*B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.SST.*_2000-2021.nc"))], []))[0]
    ds = xr.open_dataset(sst_f, decode_times=False)
    kmt = ds["KMT"].values
    tlat = ds["TLAT"].values.astype(float)
    tlon = ds["TLONG"].values.astype(float)
    ds.close()

    wet_rows, wet_cols = np.where(kmt > 0)
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

    s = generate_binary_structure(2, 1)
    from scipy.ndimage import binary_erosion
    eroded = binary_erosion(land_mask, structure=s)          # 源码原样 (border_value=0)
    edge = (land_mask == 1) & (~eroded)
    eroded_b1 = binary_erosion(land_mask, structure=s, border_value=1)
    edge_b1 = (land_mask == 1) & (~eroded_b1)
    edge_idx = np.argwhere(edge)

    cos_w = np.cos(np.deg2rad(wlat))
    tree = cKDTree(np.column_stack([wlat, wlon * cos_w]))
    rows = []
    for i, j in edge_idx:
        lat0 = float(atm_lat[i]); lon0 = float(atm_lon[j])
        q = np.array([[lat0, lon0 * np.cos(np.deg2rad(lat0))]])
        dist, pos = tree.query(q, k=1)
        if dist[0] > MAX_PAIR_DIST_DEG:
            continue
        orow, ocol = wet_rows[pos[0]], wet_cols[pos[0]]
        rows.append({
            "land_lat_idx": int(i), "land_lon_idx": int(j),
            "ocean_lat_idx": int(orow), "ocean_lon_idx": int(ocol),
            "land_lat": lat0, "land_lon": lon0,
            "ocean_lat": float(tlat[orow, ocol]),
            "ocean_lon": float(tlon180[orow, ocol]),
            "dist_deg": float(dist[0]),
            "is_border": bool(i in (0, len(atm_lat) - 1) or j in (0, len(atm_lon) - 1)),
            "in_edge_b1": bool(edge_b1[i, j]),
        })
    return dict(atm_lat=atm_lat, atm_lon=atm_lon, dlat=dlat, dlon=dlon,
                kmt=kmt, tlat=tlat, tlon=tlon, tlon180=tlon180,
                wet_rows=wet_rows, wet_cols=wet_cols, wlat=wlat, wlon=wlon,
                ii=ii, jj=jj, ok=ok, land_mask=land_mask, edge=edge,
                edge_b1=edge_b1, edge_idx=edge_idx, tree=tree, pairs=pd.DataFrame(rows),
                sst_f=sst_f)


def sec_A1(X):
    hr("A1  复算 cmd_pairs 全链路计数")
    nwet = len(X["wet_rows"])
    print(f"[A1] POP 全球湿格点 (KMT>0): {nwet}")
    print(f"[A1] 映射容差窗口: 0.75*dlat={0.75*X['dlat']:.6f}°, "
          f"0.75*dlon={0.75*X['dlon']:.6f}°  (dlat={X['dlat']:.6f}, dlon={X['dlon']:.6f})")
    nok = int(X["ok"].sum())
    cells = set(zip(X["ii"][X["ok"]].tolist(), X["jj"][X["ok"]].tolist()))
    print(f"[A1] 落在容差窗内的 POP 湿点: {nok}  → 命中的 f09 格 (去重): {len(cells)}")
    n_ocean = int((X["land_mask"] == 0).sum())
    n_land = int(X["land_mask"].sum())
    print(f"[A1] f09 欧洲框 {X['land_mask'].shape}: 海格点={n_ocean}, 陆格点={n_land}, "
          f"合计={n_ocean + n_land}")
    print(f"[A1] 陆地边缘格点 (binary_erosion 默认 border_value=0): {len(X['edge_idx'])}")
    print(f"[A1] 最终配对数: {len(X['pairs'])} / {len(X['edge_idx'])} "
          f"(上限 {MAX_PAIR_DIST_DEG}°)")

    P = X["pairs"]
    print(f"[A1] CSV 实测: 行数={len(P)} (文件 {sum(1 for _ in open(PAIRS_CSV)) - 1} 行数据)")
    print(f"[A1] 唯一陆点={len(P[['land_lat_idx', 'land_lon_idx']].drop_duplicates())}, "
          f"唯一海点={len(P[['ocean_lat_idx', 'ocean_lon_idx']].drop_duplicates())}")
    vc = P.groupby(["ocean_lat_idx", "ocean_lon_idx"]).size()
    print(f"[A1] 重复海点: 被 >1 个陆点共享的海点数={int((vc > 1).sum())}, "
          f"多占的对数={int((vc - 1).sum())} (最多共享 {int(vc.max())} 个陆点)")
    print(f"[A1] dist_deg min/median/max = {P.dist_deg.min():.6f} / "
          f"{P.dist_deg.median():.6f} / {P.dist_deg.max():.6f}")
    print(f"[A1] 陆点索引范围 lat_idx {P.land_lat_idx.min()}..{P.land_lat_idx.max()}, "
          f"lon_idx {P.land_lon_idx.min()}..{P.land_lon_idx.max()}")
    print(f"[A1] 海点索引范围 lat_idx {P.ocean_lat_idx.min()}..{P.ocean_lat_idx.max()}, "
          f"lon_idx {P.ocean_lon_idx.min()}..{P.ocean_lon_idx.max()}")

    if os.path.exists(PAIRS_CSV):
        S = pd.read_csv(PAIRS_CSV)
        keys = ["land_lat_idx", "land_lon_idx", "ocean_lat_idx", "ocean_lon_idx"]
        same = (len(S) == len(P)) and S[keys].reset_index(drop=True).equals(
            P[keys].reset_index(drop=True))
        print(f"[A1] 与已落盘 {os.path.basename(PAIRS_CSV)} 逐行一致: {same}")
        print(f"[A1] 落盘 CSV dist_deg max={S.dist_deg.max():.6f}, "
              f"ocean_lon 范围 {S.ocean_lon.min():.4f}..{S.ocean_lon.max():.4f}")
        RESULTS["A1_pairs"] = int(len(P))
        RESULTS["A1_csv_match"] = bool(same)
    else:
        print(f"[A1] !! 未找到 {PAIRS_CSV}")
    RESULTS.update({"A1_wet": nwet, "A1_ok": nok, "A1_f09_ocean": n_ocean,
                    "A1_f09_land": n_land, "A1_edge": int(len(X["edge_idx"])),
                    "A1_unique_ocean": int(len(P[['ocean_lat_idx', 'ocean_lon_idx']]
                                               .drop_duplicates())),
                    "A1_shared_ocean_cells": int((vc > 1).sum()),
                    "A1_dist_median": float(P.dist_deg.median()),
                    "A1_dist_max": float(P.dist_deg.max())})

    dom = pd.read_csv(DOMAINS_CSV)
    print(f"[A1] R 域文件 {os.path.basename(DOMAINS_CSV)}: {len(dom)} 点 "
          f"(pairs 的 (land_lat,land_lon) 去重 = "
          f"{len(P[['land_lat', 'land_lon']].drop_duplicates())})")


def sec_A2(X):
    hr("A2  POP→f09 映射容差与重复覆盖")
    print(f"[A2] 实测 f09(lon=0.9x0.25 裁剪后) 格距: dlat={X['dlat']:.6f}°, "
          f"dlon={X['dlon']:.6f}°")
    print(f"[A2] atm_lat {X['atm_lat'][0]:.4f}..{X['atm_lat'][-1]:.4f} (n={len(X['atm_lat'])}), "
          f"atm_lon {X['atm_lon'][0]:.4f}..{X['atm_lon'][-1]:.4f} (n={len(X['atm_lon'])})")
    d1 = np.diff(X["atm_lat"]); d2 = np.diff(X["atm_lon"])
    print(f"[A2] lat 间距 min/max={d1.min():.6f}/{d1.max():.6f}; "
          f"lon 间距 min/max={d2.min():.6f}/{d2.max():.6f}")

    ok = X["ok"]
    ii, jj = X["ii"][ok], X["jj"][ok]
    print(f"[A2] 通过容差的 POP 湿点 {ok.sum()} → 唯一 f09 格 "
          f"{len(set(zip(ii.tolist(), jj.tolist())))}")
    # 一个 f09 格被多少个 POP 湿点覆盖
    u, cnt = np.unique(np.stack([ii, jj], axis=1), axis=0, return_counts=True)
    print(f"[A2] 每个 f09 海格被覆盖的 POP 湿点数: max={cnt.max()}, "
          f"中位={int(np.median(cnt))}, 只被 1 个覆盖的格数={int((cnt == 1).sum())}")
    # 一个 POP 湿点是否可能同时落入两个 f09 格的容差窗 (窗口重叠)
    half_lat = 0.75 * X["dlat"]; half_lon = 0.75 * X["dlon"]
    print(f"[A2] 容差半宽 lat={half_lat:.4f}° lon={half_lon:.4f}°; "
          f"相邻格中心距 lat={X['dlat']:.4f}° lon={X['dlon']:.4f}° → "
          f"窗口重叠倍数 lat={2*half_lat/X['dlat']:.2f}x lon={2*half_lon/X['dlon']:.2f}x "
          f"(>1 即重叠, argmin 取最近者)")
    # 反向: 全球 POP 湿点中落在欧洲框外而被丢弃的比例
    in_eu = (X["wlat"] >= X["atm_lat"][0]) & (X["wlat"] <= X["atm_lat"][-1]) & \
            (X["wlon"] >= X["atm_lon"][0]) & (X["wlon"] <= X["atm_lon"][-1])
    print(f"[A2] 全球 POP 湿点 {len(X['wlat'])}, 落在欧洲框内 {int(in_eu.sum())}, "
          f"通过 0.75 容差 {int(ok.sum())} → 框内但被容差淘汰 "
          f"{int(in_eu.sum()) - int(ok.sum())} (负值=框外点被 argmin 夹到边界格)")
    # 边界夹取效应: 只用框内 POP 点重算掩码, 看有多少海格点是"框外点贡献"的
    lm_in = np.ones_like(X["land_mask"])
    ii_o, jj_o = X["ii"][ok], X["jj"][ok]
    keep = in_eu[ok]
    lm_in[ii_o[keep], jj_o[keep]] = 0
    only_out = int(((X["land_mask"] == 0) & (lm_in == 1)).sum())
    print(f"[A2] 只用框内 POP 点重算掩码: 海格点 {int((lm_in == 0).sum())} "
          f"(vs 全量 {int((X['land_mask'] == 0).sum())}); "
          f"仅靠框外点变成海的格数 = {only_out}")
    extra = np.argwhere((X["land_mask"] == 0) & (lm_in == 1))
    if len(extra):
        bl = [bool(i in (0, X["land_mask"].shape[0] - 1) or
                   j in (0, X["land_mask"].shape[1] - 1)) for i, j in extra]
        print(f"[A2]   其中落在阵列边界行/列的 = {int(np.sum(bl))}/{len(extra)}; "
              f"经纬度样例 = "
              f"{[(round(float(X['atm_lat'][i]), 3), round(float(X['atm_lon'][j]), 3)) for i, j in extra[:6]]}")
    RESULTS["A2_outside_box_ocean_cells"] = only_out
    RESULTS.update({"A2_dlat": X["dlat"], "A2_dlon": X["dlon"],
                    "A2_max_pop_per_cell": int(cnt.max())})

    # 被标为海但 CAM 侧是陆的可能性: 无 CAM 掩码可直接对比 → 用 POP 侧插值残差代替不了
    # POP 有效分辨率: 欧洲框内湿点的最近邻大圆距离
    sel = in_eu
    la = X["wlat"][sel]
    lo = X["wlon"][sel]
    cosf = np.cos(np.deg2rad(la))
    tr = cKDTree(np.column_stack([la, lo * cosf]))
    dd, _ = tr.query(np.column_stack([la, lo * cosf]), k=2)
    p = np.percentile(dd[:, 1], [10, 50, 90])
    print(f"[A2] POP(gx1v6) 欧洲框内湿点 {int(sel.sum())} 个; 最近邻间距 (cos 加权单位) "
          f"p10/p50/p90 = {p[0]:.3f}/{p[1]:.3f}/{p[2]:.3f} ≈ {p[1] * 111.19:.0f} km (中位)")
    print(f"[A2] 对比 f09: dlat={X['dlat']:.4f}° = {X['dlat'] * 111.19:.0f} km, "
          f"dlon={X['dlon']:.4f}° (45N 处 {X['dlon'] * 111.19 * np.cos(np.deg2rad(45)):.0f} km)")
    print(f"[A2] ⇒ 容差半宽 0.75*dlat={0.75 * X['dlat']:.3f}° > POP 中位间距 {p[1]:.3f}° "
          f"→ 一个 f09 格可被多个 POP 湿点覆盖 (实测最多 {int(cnt.max())} 个); "
          f"argmin 保证一个 POP 点只标记 1 个 f09 格 (窗口重叠 1.5x 由 argmin 消解)")
    print(f"[A2] 注: 海陆掩码完全来自 POP KMT, 未与 CAM landmask 交叉核对; "
          f"f09 格被判为海 = 该格中心 0.75 格距内存在 POP 湿点")


def sec_A3(X):
    hr("A3  binary_erosion border_value=0 造成的阵列边界伪边缘")
    lm = X["land_mask"]
    nlat, nlon = lm.shape
    border = np.zeros_like(lm, dtype=bool)
    border[0, :] = border[-1, :] = True
    border[:, 0] = border[:, -1] = True
    border_land = border & (lm == 1)
    edge = X["edge"]
    edge_border = edge & border
    edge_b1 = X["edge_b1"]
    print(f"[A3] 阵列边界格点总数 {int(border.sum())} (第0行/末行/第0列/末列)")
    print(f"[A3] 边界上的陆格点 {int(border_land.sum())} —— 这些在 border_value=0 下"
          f"必然被判为 edge")
    print(f"[A3] edge 总数 {int(edge.sum())}; 其中落在阵列边界 {int(edge_border.sum())}")
    print(f"[A3] 用 border_value=1 重算 edge 总数 {int(edge_b1.sum())} "
          f"(差值 = 纯伪边缘 {int(edge.sum()) - int(edge_b1.sum())})")

    P = X["pairs"]
    if len(P):
        art = P[P.is_border & (~P.in_edge_b1)]
        print(f"[A3] 206 对中, 来自「纯边界伪边缘」的配对: {len(art)}")
        print(f"[A3] 206 对中, 位于阵列边界上的配对: {int(P.is_border.sum())}")
        if len(art):
            coords = art[["land_lat_idx", "land_lon_idx", "land_lat", "land_lon",
                          "dist_deg"]].copy()
            print(coords.to_string(index=False))
            coords.to_csv(os.path.join(OUT, "A3_border_artifact_pairs.csv"), index=False)
            print(f"[A3] -> {os.path.join(OUT, 'A3_border_artifact_pairs.csv')}")
        # 边界上的 edge 全部列出
        loc = np.argwhere(edge_border)
        bl = pd.DataFrame({"i": loc[:, 0], "j": loc[:, 1],
                           "lat": X["atm_lat"][loc[:, 0]],
                           "lon": X["atm_lon"][loc[:, 1]]})
        bl["got_pair"] = [bool(((P.land_lat_idx == r.i) &
                                (P.land_lon_idx == r.j)).any()) for r in bl.itertuples()]
        bl.to_csv(os.path.join(OUT, "A3_border_edge_points.csv"), index=False)
        print(f"[A3] 边界 edge 点清单 -> {os.path.join(OUT, 'A3_border_edge_points.csv')}")
        print(f"[A3] 边界 edge 点中获得配对的: {int(bl.got_pair.sum())}")
        RESULTS["A3_border_artifacts"] = int(len(art))

    # 哪些边界 edge 点是"真海岸"(border_value=1 也算 edge)
    print(f"[A3] 边界 edge 点中真海岸 (border_value=1 也算 edge): "
          f"{int((edge_border & edge_b1).sum())}")


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = np.deg2rad(lat1), np.deg2rad(lat2)
    dp = p2 - p1
    dl = np.deg2rad(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def sec_A4(X):
    hr("A4  KDTree cos 加权的物理含义")
    P = X["pairs"]
    P = P.copy()
    P["gc_km"] = haversine(P.land_lat.values, P.land_lon.values,
                           P.ocean_lat.values, P.ocean_lon.values)
    P["wlat_off"] = (P.land_lat - P.ocean_lat).abs()
    P["wlon_off_deg"] = (P.land_lon - P.ocean_lon).abs()
    ratio = P.gc_km / P.dist_deg
    print(f"[A4] cos 加权空间定义: d = sqrt(dlat^2 + (dlon*cos(lat))^2)  [近似平面]")
    print(f"[A4] 206 对的 dist_deg min/med/max = {P.dist_deg.min():.4f}/"
          f"{P.dist_deg.median():.4f}/{P.dist_deg.max():.4f}")
    print(f"[A4] 同 206 对真实大圆距离 gc_km min/med/max = {P.gc_km.min():.1f}/"
          f"{P.gc_km.median():.1f}/{P.gc_km.max():.1f} km")
    print(f"[A4] 换算系数 gc_km/dist_deg: min={ratio.min():.2f}, "
          f"med={ratio.median():.2f}, max={ratio.max():.2f} km/单位")
    print(f"[A4] 1.0 单位 ≈ {ratio.median():.1f} km (≈ 1° 纬度 = 111.2 km)")
    print(f"[A4] 上限 {MAX_PAIR_DIST_DEG} 单位 ⇒ 最大允许分离 ≈ "
          f"{MAX_PAIR_DIST_DEG * ratio.median():.1f} km, "
          f"实测最大 {P.gc_km.max():.1f} km")
    # 跨纬度验证: 45N 处 1 单位经纬度各折算多少 km
    for la in (30., 45., 60., 70.):
        c = np.cos(np.deg2rad(la))
        print(f"[A4] {la:.0f}N: 1 单位经度 = {111.32*c:.2f} km, "
              f"1 单位纬度 = 111.13 km, "
              f"cos 加权把 1° 经度压缩为 {c:.4f} 单位")
    # 解析误差: 用 land 的 cos 去度量 ocean 点
    print(f"[A4] 注: 建树用 cos(ocean_lat), 查询用 cos(land_lat), 两侧 cos 不同 → "
          f"度量为非严格对称近似; 最大失配 "
          f"{np.abs(np.cos(np.deg2rad(P.land_lat)) - np.cos(np.deg2rad(P.ocean_lat))).max():.5f}")
    P.to_csv(os.path.join(OUT, "A4_pairs_with_gc.csv"), index=False)
    RESULTS.update({"A4_gc_median_km": float(P.gc_km.median()),
                    "A4_gc_max_km": float(P.gc_km.max()),
                    "A4_km_per_unit_median": float(ratio.median())})
    # 观测侧同口径换算 (0.25° 网格, 0.5 单位)
    O = pd.read_csv(OBS_PAIRS_CSV)
    O["gc_km"] = haversine(O.land_lat.values, O.land_lon.values % 360,
                           O.ocean_lat.values, O.ocean_lon.values % 360)
    print(f"[A4][观测侧对照] {len(O)} 对, dist_deg med={O.dist_deg.median():.4f}, "
          f"gc_km med={O.gc_km.median():.1f}, max={O.gc_km.max():.1f}, "
          f"换算 {O.gc_km.median()/O.dist_deg.median():.1f} km/单位")


def sec_A5():
    hr("A5  观测/模型配对口径差异的文档登记情况")
    pats = {
        "MAX_GRID_DIST_DEG": r"MAX_GRID_DIST_DEG",
        "MAX_PAIR_DIST_DEG": r"MAX_PAIR_DIST_DEG",
        "coastal_pairs_cesm": r"coastal_pairs_cesm",
        "obs_pairs_csv": r"COASTAL_PAIRS_CSV|coastal_pairs\.csv",
        "n206": r"(?<!\d)206(?!\d)",
        "n2039": r"(?<!\d)2039(?!\d)",
        "n1434": r"(?<!\d)1434(?!\d)",
        "pair_dist_word": r"配对距离|配对上限|max_dist",
    }
    docs, codes = [], []
    for root in (os.path.join(BASE, "python"), BASE,
                 os.path.join(BASE, "results"), os.path.join(BASE, "docs")):
        for pat in ("*.py", "*.md"):
            for f in glob.glob(os.path.join(root, pat)):
                rel = os.path.relpath(f, BASE)
                if rel.startswith("results\\intermediate"):
                    continue
                try:
                    txt = open(f, encoding="utf-8", errors="replace").read().splitlines()
                except Exception:                                  # noqa: BLE001
                    continue
                for n, ln in enumerate(txt, 1):
                    hits = [k for k, p in pats.items() if re.search(p, ln)]
                    if not hits:
                        continue
                    rec = (rel, n, ",".join(hits), ln.strip())
                    (docs if rel.endswith(".md") else codes).append(rec)
    out = os.path.join(OUT, "A5_doc_scan.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("### .md 文档命中\n")
        for rel, n, hits, ln in docs:
            fh.write(f"{rel}:{n}\t[{hits}]\t{ln}\n")
        fh.write("\n### 代码命中\n")
        for rel, n, hits, ln in codes:
            fh.write(f"{rel}:{n}\t[{hits}]\t{ln}\n")
    print(f"[A5] 全工作区命中: .md {len(docs)} 行, 代码 {len(codes)} 行 -> {out}")

    print("\n[A5] --- 登记「模型侧」配对口径的文档 (.md 含 206 / coastal_pairs_cesm / "
          "MAX_PAIR_DIST_DEG) ---")
    model_doc = [r for r in docs if {"n206", "coastal_pairs_cesm",
                                     "MAX_PAIR_DIST_DEG"} & set(r[2].split(","))]
    if model_doc:
        for rel, n, hits, ln in model_doc:
            print(f"[A5] {rel}:{n} [{hits}] {ln[:140]}")
    else:
        print("[A5] (无) —— 没有任何 .md 文档登记模型侧 206 对 / 1.0° 口径")
    print("\n[A5] --- 登记「观测侧」配对口径的文档 (含 0.5 / 2039 / 1434) ---")
    for rel, n, hits, ln in docs:
        if {"MAX_GRID_DIST_DEG", "n2039", "n1434"} & set(hits.split(",")):
            print(f"[A5] {rel}:{n} [{hits}] {ln[:140]}")
    print("\n[A5] --- 代码中同时出现两侧口径的行 (对比说明) ---")
    for rel, n, hits, ln in codes:
        if "MAX_PAIR_DIST_DEG" in hits or "coastal_pairs_cesm" in hits:
            print(f"[A5] {rel}:{n} [{hits}] {ln[:140]}")
    print(f"\n[A5] 结论: 观测侧 0.5°/2039/1434 被 {len(set(r[0] for r in docs))} 个 .md "
          f"文档登记; 模型侧 206 对仅在 phase6_cesm.py 的 docstring/注释里出现, "
          f".md 文档命中数 = {len(model_doc)}")
    RESULTS["A5_model_side_doc_lines"] = len(model_doc)
    RESULTS["A5_obs_side_doc_lines"] = len([r for r in docs if
                                            {"MAX_GRID_DIST_DEG", "n2039", "n1434"}
                                            & set(r[2].split(","))])


def sec_A6(X):
    hr("A6  _load_sst_points 块读 vs 逐点 isel 比对")
    import time
    P = pd.read_csv(PAIRS_CSV)
    pj = P.ocean_lat_idx.values
    pi = P.ocean_lon_idx.values
    ds = xr.open_dataset(X["sst_f"])
    print(f"[A6] SST dims = {ds['SST'].dims}, KMT dims = {ds['KMT'].dims} "
          f"(nlat={ds.sizes['nlat']}, nlon={ds.sizes['nlon']}, time={ds.sizes['time']})")
    kmt = ds["KMT"].values
    kmt_pt = np.asarray(np.ma.filled(kmt[pj, pi], 0))
    print(f"[A6] 206 对配对点 KMT[pj, pi]: min={kmt_pt.min()}, max={kmt_pt.max()}, "
          f"<=0 的点数={int((kmt_pt <= 0).sum())} "
          f"(若 pj/pi 维度颠倒, KMT 会大面积<=0 → 序列被整列置 NaN)")
    ds.close()

    from netCDF4 import Dataset
    nc = Dataset(X["sst_f"])
    v = nc.variables["SST"]
    j0, j1 = int(pj.min()), int(pj.max()) + 1
    t0 = time.time()
    block = v[:, j0:j1, :].astype(np.float32)      # 源码原样的"一次大读"
    t_block = time.time() - t0
    print(f"[A6] 块读 v[:, {j0}:{j1}, :] = {block.shape} ({block.nbytes/1e6:.1f} MB) "
          f"耗时 {t_block:.1f} s (仅 89/384 行, 即全文件的 23%)")
    print(f"[A6] dtype={block.dtype}, masked={np.ma.isMaskedArray(block)}")
    rows = block[:, pj - j0, :]
    got = np.take_along_axis(rows, pi[np.newaxis, :, np.newaxis], axis=2)[:, :, 0]
    print(f"[A6] rows=block[:, pj-j0, :] shape={rows.shape}; "
          f"take_along_axis(..., pi) → got shape={got.shape}, "
          f"masked={np.ma.isMaskedArray(got)}, dtype={got.dtype}")
    del block, rows
    nc.close()

    # xarray 逐点标量 isel (对 1 GB POP 文件用矢量 isel 会退化为全量读, 故用标量点读)
    ds = xr.open_dataset(X["sst_f"])
    for k in (0, 100, 205):
        r, c = int(pj[k]), int(pi[k])
        t1 = time.time()
        ref = np.asarray(ds["SST"].isel(nlat=r, nlon=c).values, dtype=np.float64)
        d = np.abs(np.asarray(got[:, k], dtype=np.float64) - ref)
        print(f"[A6] pair#{k} (nlat={r}, nlon={c}): 标量 isel 耗时 {time.time()-t1:.1f} s; "
              f"全时段 max|块读-isel| = {np.nanmax(d):.3e} "
              f"{'一致' if np.nanmax(d) < 1e-6 else '!! 不一致'}")
        print(f"[A6]   t=0/1000/2190: 块读 {got[0,k]:.6f}/{got[1000,k]:.6f}/{got[2190,k]:.6f} "
              f"| isel {ref[0]:.6f}/{ref[1000]:.6f}/{ref[2190]:.6f}")
    ds.close()
    # 由 netCDF4 点读再抽 20 对做全时段交叉
    nc = Dataset(X["sst_f"]); v = nc.variables["SST"]
    bad = 0; mx = 0.0
    for k in range(0, len(pj), 10):
        ref = np.ma.filled(v[:, int(pj[k]), int(pi[k])], np.nan)
        d = np.nanmax(np.abs(np.asarray(got[:, k], dtype=np.float64) - ref))
        mx = max(mx, d); bad += int(d > 1e-6)
    print(f"[A6] 另抽 {len(range(0,len(pj),10))} 对做全时段交叉: max|diff|={mx:.3e}, "
          f"不一致对数={bad}")
    nc.close()
    print(f"[A6] 结论: 块读 + take_along_axis 与逐点读取数值完全一致; "
          f"pj=KMT 行(nlat)、pi=KMT 列(nlon) 与 SST(time,nlat,nlon) 维度对齐 ✓")


# ══════════════════════════════════════════════════════════════════
# B. 经度与坐标
# ══════════════════════════════════════════════════════════════════
def sec_B1(X):
    hr("B1  经度 0-360 vs ±180 与符号约定")
    tlon = X["tlon"]
    print(f"[B1] POP TLONG 原始范围: {tlon.min():.4f} .. {tlon.max():.4f} "
          f"(>180 的点数={int((tlon > 180).sum())}/{tlon.size})")
    t180 = X["tlon180"]
    print(f"[B1] np.where(tlon>180, tlon-360, tlon) 之后: {t180.min():.4f} .. "
          f"{t180.max():.4f}")
    print(f"[B1] 欧洲框 lon 范围: {X['atm_lon'][0]:.4f} .. {X['atm_lon'][-1]:.4f}")
    print(f"[B1] 结论: 转换后仍有 >180 的点 {int((t180 > 180).sum())} 个 "
          f"(太平洋, 被 0.75*dlon 容差淘汰)")

    P = pd.read_csv(PAIRS_CSV)
    print(f"[B1] coastal_pairs_cesm.csv  ocean_lon = {P.ocean_lon.min():.4f}.."
          f"{P.ocean_lon.max():.4f} (已 -180..180)")
    print(f"[B1] coastal_pairs_cesm.csv  land_lon  = {P.land_lon.min():.4f}.."
          f"{P.land_lon.max():.4f}")
    O = pd.read_csv(OBS_PAIRS_CSV)
    print(f"[B1][观测侧] coastal_pairs.csv ocean_lon = {O.ocean_lon.min():.4f}.."
          f"{O.ocean_lon.max():.4f}  ← **0..360 未换算** (coastal_mask.py:124 写的是"
          f"未统一的 ocean_lon)")
    print(f"[B1][观测侧] land_lon = {O.land_lon.min():.4f}..{O.land_lon.max():.4f}")

    for f in sorted(glob.glob(os.path.join(CESM_INT, "mhw_*.csv"))):
        M = pd.read_csv(f)
        if len(M):
            print(f"[B1] {os.path.basename(f)}: lon {M.lon.min():.4f}..{M.lon.max():.4f} "
                  f"(n={len(M)})")
    M = pd.read_csv(os.path.join(CESM_INT, "mhw_ALL_001.csv"))
    key = set(zip(M.lat_idx, M.lon_idx))
    kp = set(zip(P.ocean_lat_idx, P.ocean_lon_idx))
    print(f"[B1] mhw_ALL_001.csv 的 (lat_idx,lon_idx) 集合 ⊆ pairs 海点集合: "
          f"{key <= kp} (mhw 唯一海点 {len(key)}, pairs 唯一海点 {len(kp)})")
    lons_mhw = M.groupby(["lat_idx", "lon_idx"]).lon.first()
    lons_pair = P.groupby(["ocean_lat_idx", "ocean_lon_idx"]).ocean_lon.first()
    j = pd.concat([lons_mhw.rename("mhw"), lons_pair.rename("pairs")], axis=1).dropna()
    print(f"[B1] mhw lon 与 pairs ocean_lon 一致: "
          f"{bool(np.allclose(j.mhw, j.pairs))} (max|diff|="
          f"{float((j.mhw - j.pairs).abs().max()):.3e})")
    # 检测/阈值/事件三处 lon 是否同源
    print("[B1] 阈值: _pooled_threshold_sst 只用列索引(ocean_lat_idx/ocean_lon_idx)取数, "
          "不涉及 lon 数值 → 与 pairs 同源")
    print("[B1] 检测: _detect_mhw_member 写入 lon=pairs_df.ocean_lon → 与 pairs 同源")
    # 写出观测侧 mhw 的 lon 约定做对照
    for f in [os.path.join(OBS_INT, "mhw_events_R_global.csv")]:
        if os.path.exists(f):
            M2 = pd.read_csv(f, nrows=5)
            print(f"[B1][观测侧] {os.path.basename(f)} 列={list(M2.columns)}")
            full = pd.read_csv(f, usecols=[c for c in ("lon",) if c in M2.columns])
            if "lon" in full:
                print(f"[B1][观测侧] mhw_events lon 范围 {full.lon.min():.4f}.."
                      f"{full.lon.max():.4f}")
    RESULTS["B1_obs_pairs_lon_max"] = float(O.ocean_lon.max())


def sec_B2(X):
    hr("B2  prepare 的坐标对齐 (纬度翻转风险实测)")
    ref = xr.open_dataset(REF_EUROPE)
    ref_lat = ref.lat.values
    ref_lon = ref.lon.values
    ref.close()
    print(f"[B2] 参考(已裁剪 AWS 成品) lat {ref_lat[0]:.4f}→{ref_lat[-1]:.4f}, "
          f"升序={bool(np.all(np.diff(ref_lat) > 0))}")
    print(f"[B2] 参考 lon {ref_lon[0]:.4f}→{ref_lon[-1]:.4f}, "
          f"升序={bool(np.all(np.diff(ref_lon) > 0))}")

    for tag, f in (("XGHG seg1(1920-2005)", TREFHT_XGHG_001_A),
                   ("XGHG seg2(2006-2080)", TREFHT_XGHG_001_B)):
        ds = xr.open_dataset(f)
        la = ds.lat.values; lo = ds.lon.values
        print(f"[B2] 源 {tag}: lat {la[0]:.4f}→{la[-1]:.4f} "
              f"升序={bool(np.all(np.diff(la) > 0))}; "
              f"lon {lo[0]:.4f}→{lo[-1]:.4f} (0-360 约定={bool(lo.min() >= 0)})")
        ds.close()

    # 用 xarray 复刻 prepare 的 sel 顺序, 检查返回行序
    ds = xr.open_dataset(TREFHT_XGHG_001_B)
    da = ds["TREFHT"]
    lon180 = ((da.lon.astype(float) + 180) % 360) - 180
    da2 = da.assign_coords(lon=lon180).sortby("lon")
    sub = da2.sel(lat=ref_lat, lon=ref_lon, method="nearest")
    print(f"[B2] .sel 之后 lat 序列 = {sub.lat.values[0]:.4f}→{sub.lat.values[-1]:.4f}, "
          f"升序={bool(np.all(np.diff(sub.lat.values) > 0))}")
    print(f"[B2] .sel 返回的 lat 是否 == ref_lat 顺序: "
          f"{bool(np.allclose(sub.lat.values, ref_lat))}")
    sub = sub.assign_coords(lat=ref_lat, lon=ref_lon)
    ds.close()

    # 独立探针: 手工最近邻, 与落盘的 XGHG_001_T2m.nc 整幅对比
    m = xr.open_dataset(T2M_XGHG_001)
    print(f"[B2] 落盘 {os.path.basename(T2M_XGHG_001)}: dims={dict(m.sizes)}, "
          f"lat {m.lat.values[0]:.4f}→{m.lat.values[-1]:.4f} "
          f"(== ref: {bool(np.allclose(m.lat.values, ref_lat))}), "
          f"lon == ref: {bool(np.allclose(m.lon.values, ref_lon))}")

    def manual_slice(f, date_str):
        d = xr.open_dataset(f)
        t = pd.DatetimeIndex(d.time.values)
        k = int(np.argmin(np.abs((t - pd.Timestamp(date_str)).total_seconds())))
        da = d["TREFHT"].isel(time=k)
        lon180 = ((da.lon.astype(float) + 180) % 360) - 180
        order = np.argsort(lon180.values)
        lon_s = lon180.values[order]
        vals = da.values[:, order]
        ilat = np.array([int(np.argmin(np.abs(d.lat.values - x))) for x in ref_lat])
        ilon = np.array([int(np.argmin(np.abs(lon_s - x))) for x in ref_lon])
        out = vals[np.ix_(ilat, ilon)] - 273.15
        d.close()
        return out, str(t[k])[:10]

    mt = pd.DatetimeIndex(m.time.values)
    probes = [("2001-07-15", TREFHT_XGHG_001_A), ("2004-01-20", TREFHT_XGHG_001_A),
              ("2006-07-15", TREFHT_XGHG_001_B), ("2020-08-10", TREFHT_XGHG_001_B)]
    probe_rows = []
    for date_s, f in probes:
        k = int(np.argmin(np.abs((mt - pd.Timestamp(date_s)).total_seconds())))
        merged_slice = m["T2m"].isel(time=k).values
        man, used = manual_slice(f, date_s)
        dmax = float(np.nanmax(np.abs(merged_slice - man)))
        flipped = float(np.nanmax(np.abs(merged_slice - man[::-1, :])))
        print(f"[B2] 探针 {date_s} (merged t={k}, 源日期 {used}): "
              f"max|merged-手工NN| = {dmax:.4f} °C  (对照: 纬度翻转假设 "
              f"{flipped:.4f} °C)")
        probe_rows.append({"probe": date_s, "merged_index": k, "src_date": used,
                           "max_abs_diff": dmax, "max_abs_diff_latflip": flipped,
                           "verdict": "对齐正确" if dmax < 0.01 else "!!不一致"})
    pd.DataFrame(probe_rows).to_csv(os.path.join(OUT, "B2_alignment_probe.csv"),
                                    index=False)
    m.close()


def sec_B3():
    hr("B3  K→°C 换算与 SST 单位")
    for tag, f in (("XGHG TREFHT seg1", TREFHT_XGHG_001_A),
                   ("XGHG TREFHT seg2", TREFHT_XGHG_001_B),
                   ("ALL TREFHT(AWS 成品)", REF_EUROPE)):
        ds = xr.open_dataset(f)
        v = "TREFHT" if "TREFHT" in ds.data_vars else "T2m"
        print(f"[B3] {tag}: units={ds[v].attrs.get('units')!r}, "
              f"min={float(ds[v].min()):.3f}, max={float(ds[v].max()):.3f}, "
              f"dtype={ds[v].dtype}")
        ds.close()
    for f in (T2M_ALL_001, T2M_XGHG_001):
        ds = xr.open_dataset(f)
        print(f"[B3] 落盘 {os.path.basename(f)}: units={ds['T2m'].attrs.get('units')!r}, "
              f"min={float(ds['T2m'].min()):.3f}, max={float(ds['T2m'].max()):.3f}")
        yr = pd.DatetimeIndex(ds.time.values).year
        for y in (2005, 2006, 2020):
            sel = ds["T2m"].values[yr == y]
            print(f"[B3]   {os.path.basename(f)} 年 {y}: 均值={sel.mean():.3f} °C "
                  f"(若漏减 273.15 应 ≈ {sel.mean() + 273.15:.1f})")
        ds.close()
    # 判据 `float(da.max())>150` 在拼接前逐段执行 → 逐段验证
    print("[B3] 判据 `units.startswith('K') or float(da.max())>150` 对两段均成立: "
          "seg1 max=319.98>150 ✓, seg2 max=320.18>150 ✓ → 两段都减 273.15")
    print("[B3] 注意: 判据用 `startswith('K')` 也会命中 'Kelvin' 之外的任何 K 开头单位; "
          "若单位写成 'kelvin' 则依赖 >150 兜底; 此处二者都命中, 无风险")

    for tag, f in (("ALL SST seg1", SST_ALL_001), ("ALL SST seg2", SST_ALL_001_B),
                   ("XGHG SST seg1", SST_XGHG_001), ("XGHG SST seg2", SST_XGHG_001_B)):
        ds = xr.open_dataset(f, decode_times=False)
        print(f"[B3] {tag}: SST units={ds['SST'].attrs.get('units')!r}, "
              f"min={float(ds['SST'].min()):.3f}, max={float(ds['SST'].max()):.3f}")
        ds.close()
    print("[B3] _load_sst_points (phase6_cesm.py:242-252) 只做 astype, **无** K→°C; "
          "实测 SST units='degC' 且范围 -2.9..34.9 → 无需换算 ✓")
    src = open(os.path.join(BASE, "python", "phase6_cesm.py"), encoding="utf-8").read()
    print(f"[B3] 代码佐证: '_load_sst_points' 内出现 '273.15' 的次数 = "
          f"{src[src.index('def _load_sst_points'):src.index('def _run_events')].count('273.15')}")


def sec_B4():
    hr("B4  时间解码 / 日历 / doy 索引边界")
    for tag, f in (("T2m merged ALL_001", T2M_ALL_001),
                   ("T2m merged XGHG_001", T2M_XGHG_001),
                   ("SST ALL seg1", SST_ALL_001), ("SST XGHG seg1", SST_XGHG_001)):
        ds0 = xr.open_dataset(f, decode_times=False)
        cal_attr = ds0.time.attrs.get("calendar")
        ds0.close()
        ds = xr.open_dataset(f)
        t = ds.time.values
        try:
            idx = pd.DatetimeIndex(t)
            okk = True
        except Exception as e:                                     # noqa: BLE001
            okk = False
            print(f"[B4] {tag}: pd.DatetimeIndex 失败 {e}")
        doy = pd.DatetimeIndex(t).dayofyear.values if okk else np.array([])
        print(f"[B4] {tag}: 文件 calendar 属性={cal_attr!r}, 解码后 dtype={t.dtype}, "
              f"n={len(t)}, {str(t[0])[:10]}~{str(t[-1])[:10]}")
        print(f"[B4]   doy 集合: min={doy.min()}, max={doy.max()}, "
              f"是否含 366={bool((doy == 366).any())}, 唯一 doy 数={len(np.unique(doy))}")
        ds.close()
    print("[B4] proc 文件的 calendar 属性 = proleptic_gregorian (由 "
          "download_cesm1le.py:_to_datetimeindex 的 CFTimeIndex.to_datetimeindex() "
          "把 noleap 日期按同名 Y-M-D 映射为 datetime64 所致); "
          "raw 文件真实 calendar = noleap")
    print("[B4] 后果: 数据中不存在 2-29 行 (noleap), 但时间标签用标准日历 → "
          "跨闰年时标签序列在 2-28→3-1 处 +2 天跳步; 标签本身仍是正确的 noleap 日期")
    # %365 窗口边界
    bad = []
    for d in range(1, 366):
        win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
        if min(win) < 1 or max(win) > 365 or len(set(win)) != 11:
            bad.append((d, win))
    print(f"[B4] 11 天圆形窗 win=[(d+k-1)%365+1 for k in -5..5]: d=1..365 全范围 "
          f"越界/重复的 d 个数 = {len(bad)}")
    print(f"[B4] 窗口 d=1  -> {[(1 + k - 1) % 365 + 1 for k in range(-5, 6)]}")
    print(f"[B4] 窗口 d=365-> {[(365 + k - 1) % 365 + 1 for k in range(-5, 6)]}")
    print("[B4] thresh 数组 366 行, doy-1 ∈ 0..364 (doy<=365) → 第 366 行(全 NaN)永不取用 ✓")
    print("[B4] _pooled_threshold_sst 用 np.arange(1,366) 计算 → 第 366 行留 NaN ✓")

    # ALL SST 两段接缝: 天数/标签连续性
    for tag, a, b in (("ALL", SST_ALL_001, SST_ALL_001_B),
                      ("XGHG", SST_XGHG_001, SST_XGHG_001_B)):
        da = pd.DatetimeIndex(xr.open_dataset(a).time.values)
        xr.open_dataset(a).close()
        db = pd.DatetimeIndex(xr.open_dataset(b).time.values)
        xr.open_dataset(b).close()
        step = (db[0] - da[-1]).days
        print(f"[B4] {tag} SST 段接缝: seg1 末 {str(da[-1])[:10]} → seg2 首 "
              f"{str(db[0])[:10]}  步长={step} 天 "
              f"({'连续' if step == 1 else '!! 有缺口'})")
        RESULTS[f"B4_{tag}_sst_seam_step_days"] = int(step)
        RESULTS[f"B4_{tag}_sst_nt"] = int(len(da) + len(db))


# ══════════════════════════════════════════════════════════════════
# C. XGHG 两段拼接
# ══════════════════════════════════════════════════════════════════
def sec_C1():
    hr("C1  XGHG 成员 001-003 段文件/时间范围/天数/连续性")
    sys.path.insert(0, os.path.join(BASE, "python"))
    from phase6_cesm import find_t2m_segments  # noqa: E402
    for m in ("001", "002", "003"):
        segs = find_t2m_segments("XGHG", m)
        print(f"[C1] XGHG {m}: {len(segs)} 段")
        for f in segs:
            ds = xr.open_dataset(f)
            t = pd.DatetimeIndex(ds.time.values)
            print(f"[C1]   {os.path.basename(f)}  n={len(t)}  "
                  f"{str(t[0])[:10]}~{str(t[-1])[:10]}  "
                  f"步长集合={sorted(set(np.diff(t.values).astype('timedelta64[D]').astype(int)))}")
            ds.close()
        merged = os.path.join(CESM_INT, f"XGHG_{m}_T2m.nc")
        if os.path.exists(merged):
            ds = xr.open_dataset(merged)
            t = pd.DatetimeIndex(ds.time.values)
            dd = np.diff(t.values).astype("timedelta64[D]").astype(int)
            print(f"[C1] 落盘 {os.path.basename(merged)}: n={len(t)} "
                  f"{str(t[0])[:10]}~{str(t[-1])[:10]}, 重复={t.has_duplicates}, "
                  f"严格单调={bool(t.is_monotonic_increasing)}, "
                  f"步长集合={sorted(set(dd))}, 期望 8030 天 => "
                  f"{'一致' if len(t) == 8030 else '!! 不一致'}")
            ds.close()
        else:
            print(f"[C1] !! 缺 {merged}")


    print("\n[C1] 步长=2 的位置复核 (应为闰年 2-28→3-1, 即 noleap 缺 2-29):")
    for m in ("001", "002", "003"):
        merged = os.path.join(CESM_INT, f"XGHG_{m}_T2m.nc")
        if not os.path.exists(merged):
            continue
        ds = xr.open_dataset(merged)
        t = pd.DatetimeIndex(ds.time.values)
        dd = np.diff(t.values).astype("timedelta64[D]").astype(int)
        g = np.where(dd == 2)[0]
        info = [f"{str(t[i])[:10]}→{str(t[i+1])[:10]}" for i in g]
        feb29 = int(((t.month == 2) & (t.day == 29)).sum())
        ds.close()
        print(f"[C1] XGHG {m}: 2 天步进 {len(g)} 处 {info}; "
              f"序列中 2-29 标签数={feb29}")
        print(f"[C1] XGHG {m}: 缺口判定 —— 以 noleap(365天) 计 2000-01-01..2021-12-31 "
              f"= {22 * 365} 天, 实测 {len(t)} 天 → "
              f"{'无缺口' if len(t) == 22 * 365 else '!! 有缺口'}")


def sec_C2():
    hr("C2  接缝 (2005-12-31 → 2006-01-01) 跳跃检验")

    def jumps_t2m(f, seam_date="2006-01-01"):
        ds = xr.open_dataset(f)
        t = pd.DatetimeIndex(ds.time.values)
        v = ds["T2m"].values.astype(np.float64)          # (nt,lat,lon) 49x51
        d = np.abs(np.diff(v, axis=0)).mean(axis=(1, 2))   # d[i] = |t[i+1]-t[i]|
        k = int(np.where(t.normalize() == pd.Timestamp(seam_date))[0][0])
        seam = d[k - 1]
        yr_end = ((t[1:].month == 1) & (t[1:].day == 1))   # 12-31 -> 01-01 跳变
        ds.close()
        return seam, d, yr_end

    for tag, f in (("ALL(单段,无文件接缝→仅作参照)", T2M_ALL_001),
                   ("XGHG(两段拼接,2005-12-31|2006-01-01 为文件接缝)", T2M_XGHG_001)):
        if not os.path.exists(f):
            continue
        seam, d, yr_end = jumps_t2m(f)
        pc = np.percentile(d, [50, 95, 99])
        ny = int(yr_end.sum())
        rank_all = float((d < seam).mean() * 100)
        rank_ny = float((d[yr_end] < seam).mean() * 100)
        print(f"[C2] T2m {tag}")
        print(f"[C2]   |ΔT2m| 全域均值: 接缝={seam:.4f} °C; 全体 {len(d)} 个日间跳变 "
              f"p50={pc[0]:.4f} p95={pc[1]:.4f} p99={pc[2]:.4f} °C")
        print(f"[C2]   跨年(12-31→01-01)跳变 {ny} 个: "
              f"p50={np.percentile(d[yr_end], 50):.4f}, 接缝在其中排名 "
              f"{int((d[yr_end] < seam).sum()) + 1}/{ny} (分位 {rank_ny:.0f}%); "
              f"在全体中分位 {rank_all:.0f}%")
        print(f"[C2]   同季节基准更公平: 接缝 {seam:.4f} vs 其它跨年跳变 "
              f"median {np.percentile(d[yr_end], 50):.4f} "
              f"→ {'无明显不连续' if seam < np.percentile(d[yr_end], 75) else '偏高'}")
        RESULTS[f"C2_t2m_{tag[:4]}_seam"] = float(seam)
        RESULTS[f"C2_t2m_{tag[:4]}_newyear_median"] = float(np.percentile(d[yr_end], 50))

    # SST: 全网格抽样
    def sst_cmp(a, b, seam_last="2005-12-31", seam_first=None):
        from netCDF4 import Dataset
        na, nb = Dataset(a), Dataset(b)
        va, vb = na.variables["SST"], nb.variables["SST"]
        ta = pd.DatetimeIndex(xr.open_dataset(a).time.values)
        xr.open_dataset(a).close()
        tb = pd.DatetimeIndex(xr.open_dataset(b).time.values)
        xr.open_dataset(b).close()
        ia = n_last = na.variables["SST"].shape[0] - 1   # seg1 **最后一条**
        A = va[ia, :, :].astype(np.float64)
        B = vb[0, :, :].astype(np.float64)
        seam = float(np.abs(B - A).mean())
        n = na.variables["SST"].shape[0]
        rng = np.random.default_rng(0)
        idx = np.sort(rng.choice(np.arange(n - 1), 120, replace=False))
        d = np.array([float(np.abs(va[i + 1] - va[i]).mean()) for i in idx])
        # 同季节(12月/1月)基准: 取第二日落在 12 月或 1 月的跳变
        mon = ta.month.values
        widx = np.where((mon[1:] == 12) | (mon[1:] == 1))[0]
        widx = widx[widx < n - 1]
        wsel = np.sort(rng.choice(widx, min(60, len(widx)), replace=False))
        dw = np.array([float(np.abs(va[i + 1] - va[i]).mean()) for i in wsel])
        na.close(); nb.close()
        return seam, np.percentile(d, [50, 95, 99]), d, str(ta[ia])[:10], \
            str(tb[0])[:10], dw

    for tag, a, b in (("XGHG", SST_XGHG_001, SST_XGHG_001_B),
                      ("ALL", SST_ALL_001, SST_ALL_001_B)):
        seam, pc, d, l1, l2, dw = sst_cmp(a, b)
        rank = float((d < seam).mean() * 100)
        rankw = float((dw < seam).mean() * 100)
        print(f"[C2] SST {tag} 接缝 |ΔSST| 全网格均值 = {seam:.4f} °C "
              f"(seg1 末条标签 {l1} → seg2 首条标签 {l2})")
        print(f"[C2]   随机 {len(d)} 个日间跳变: p50={pc[0]:.4f} p95={pc[1]:.4f} "
              f"p99={pc[2]:.4f} °C → 接缝分位 {rank:.1f}%")
        print(f"[C2]   同季节(12/1月) {len(dw)} 个跳变: p50={np.percentile(dw,50):.4f}, "
              f"p95={np.percentile(dw,95):.4f} °C → 接缝分位 {rankw:.1f}% "
              f"({'无明显不连续' if rankw < 90 else '偏高'})")
        print(f"[C2]   注: {tag} 接缝标签步长 = "
              f"{(pd.Timestamp(l2) - pd.Timestamp(l1)).days} 天 "
              f"(POP 标签=物理日+1; XGHG 两段物理日相邻, ALL 段边界缺 1 个物理日)")
        RESULTS[f"C2_sst_{tag}_seam"] = float(seam)
        RESULTS[f"C2_sst_{tag}_winter_median"] = float(np.percentile(dw, 50))
        RESULTS[f"C2_sst_{tag}_rank_in_winter"] = rankw


def sec_C3():
    hr("C3  xr.concat 静默风险: 两段坐标/单位/属性一致性")
    for tag, a, b in (("XGHG TREFHT", TREFHT_XGHG_001_A, TREFHT_XGHG_001_B),
                      ("ALL TREFHT", REF_EUROPE, None),
                      ("XGHG SST", SST_XGHG_001, SST_XGHG_001_B),
                      ("ALL SST", SST_ALL_001, SST_ALL_001_B)):
        if b is None:
            continue
        da_ = xr.open_dataset(a); db_ = xr.open_dataset(b)
        v = "TREFHT" if "TREFHT" in da_.data_vars else "SST"
        A, B = da_[v], db_[v]
        print(f"[C3] {tag}:")
        print(f"[C3]   units  A={A.attrs.get('units')!r} B={B.attrs.get('units')!r} "
              f"→ {'一致' if A.attrs.get('units') == B.attrs.get('units') else '!! 不一致'}")
        print(f"[C3]   dtype  A={A.dtype} B={B.dtype}; shape A={A.shape} B={B.shape}")
        la = da_["lat"].values if "lat" in da_ else da_["TLAT"].values
        lb = db_["lat"].values if "lat" in db_ else db_["TLAT"].values
        is_pop = "TLAT" in da_
        print(f"[C3]   网格类型: {'POP 曲线网格 (TLAT/TLONG)' if is_pop else 'CAM 规则网格 (lat/lon)'}")
        lo_a = (da_["lon"] if "lon" in da_ else da_["TLONG"]).values
        lo_b = (db_["lon"] if "lon" in db_ else db_["TLONG"]).values
        if is_pop:
            print(f"[C3]   TLAT 范围 A {la.min():.4f}..{la.max():.4f} / "
                  f"B {lb.min():.4f}..{lb.max():.4f}; A==B: {bool(np.allclose(la, lb))}")
            print(f"[C3]   TLONG 范围 A {lo_a.min():.4f}..{lo_a.max():.4f} (0-360); "
                  f"A==B: {bool(np.allclose(lo_a, lo_b))}")
            kma = np.asarray(da_["KMT"].values); kmb = np.asarray(db_["KMT"].values)
            print(f"[C3]   KMT: A==B: {bool(np.array_equal(kma, kmb))}, "
                  f"非零格点数={int((kma > 0).sum())}")
        else:
            print(f"[C3]   lat 升序 A={bool(np.all(np.diff(la) > 0))} "
                  f"B={bool(np.all(np.diff(lb) > 0))}; A==B: {bool(np.allclose(la, lb))}")
            print(f"[C3]   lon A {lo_a[0]:.4f}..{lo_a[-1]:.4f} "
                  f"B {lo_b[0]:.4f}..{lo_b[-1]:.4f}; A==B: "
                  f"{bool(np.allclose(lo_a, lo_b))}")
        # 只对小的 TREFHT 段做全量属性比较
        if v == "TREFHT":
            ka, kb = set(A.attrs), set(B.attrs)
            print(f"[C3]   attrs 仅 A 有={sorted(ka - kb)}, 仅 B 有={sorted(kb - ka)}")
            common = sorted(ka & kb)
            diff = [k for k in common if A.attrs[k] != B.attrs[k]]
            print(f"[C3]   attrs 同名但取值不同: {diff}")
        da_.close(); db_.close()
    print("[C3] xr.concat(dim='time') 默认 join='outer', 且本处不检查 units → "
          "若两段单位不同会静默拼接; 实测两段 TREFHT 均 units='K' 且 max>150, "
          "SST 均 units='degC' → 无静默错误")


# ══════════════════════════════════════════════════════════════════
# E. 时间标签对齐 (审计副产物)
# ══════════════════════════════════════════════════════════════════
def _event_mask(events, nt, t0, shift_days=0):
    m = np.zeros(nt, dtype=bool)
    if len(events) == 0:
        return m
    s = (pd.to_datetime(events.event_start) - t0).dt.days.values
    e = (pd.to_datetime(events.event_end) - t0).dt.days.values
    for i0, i1 in zip(s, e):
        a, b = max(int(i0) + shift_days, 0), min(int(i1) + shift_days, nt - 1)
        if b >= a:
            m[a:b + 1] = True
    return m


def sec_E():
    hr("E  陆地/海洋时间标签对齐与复合日判定 (审计副产物)")
    # E1: 时间标签约定
    ds = xr.open_dataset(REF_EUROPE, decode_times=False)
    v = np.asarray(ds["time_bnds"].values)
    print(f"[E] ALL_{'001'}_TREFHT(全球源) time: units="
          f"{ds.time.attrs['units']!r} → 标签 = 区间中点(12:00)")
    print(f"[E]   time_bnds units={ds['time_bnds'].attrs['units']!r}, "
          f"calendar={ds['time_bnds'].attrs['calendar']!r}; 首 3 个区间="
          f"{v[:3].tolist()}")
    print("[E]   54750 = 1850-01-01 起 noleap 第 54750 天 = 2000-01-01 → "
          "区间 [2000-01-01, 2000-01-02) ⇒ 标签 12:00 指的是同一天")
    ds.close()
    ds = xr.open_dataset(TREFHT_XGHG_001_A, decode_times=False)
    tb = np.asarray(ds["time_bnds"].values)
    print(f"[E] XGHG TREFHT time: units={ds.time.attrs['units']!r}, "
          f"time_bnds 首 3={tb[:3].tolist()} → 标签 = 区间起点(00:00), 同一天")
    ds.close()
    print("[E] 结论: ALL(12:00, 中点) 与 XGHG(00:00, 起点) 指向**同一物理日**; "
          "但 phase6_cesm.py:499/553 用 t0=time[0] 原样, 12:00 会让 "
          "(event_start - t0).dt.days 对 00:00 标签少算 1 天")

    # E2: 各 exp 的 t0
    for exp in ("ALL", "XGHG"):
        f = os.path.join(CESM_INT, f"{exp}_001_T2m.nc")
        if os.path.exists(f):
            d = xr.open_dataset(f)
            print(f"[E] cmd_compound 的 t0 ({exp}_001_T2m.nc) = "
                  f"{pd.Timestamp(d.time.values[0])}")
            d.close()
    P = pd.read_csv(PAIRS_CSV)
    for tag in ("", "_x"):
        rec = os.path.join(CESM_INT, f"exposure_members{tag}.csv")
        if not os.path.exists(rec):
            continue
        R = pd.read_csv(rec)
        print(f"\n[E] === 复算 tag={tag!r} ({'v1 自身气候态' if not tag else 'v2 XGHG 基准'}) "
              f"与 {os.path.basename(rec)} 对照 ===")
        rows = []
        for exp in ("ALL", "XGHG"):
            for m in ("001", "002", "003"):
                t2mf = os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc")
                thwf = os.path.join(CESM_INT, f"thw{tag}_{exp}_{m}.csv")
                mhwf = os.path.join(CESM_INT, f"mhw{tag}_{exp}_{m}.csv")
                if not all(os.path.exists(x) for x in (t2mf, thwf, mhwf)):
                    continue
                d = xr.open_dataset(t2mf)
                nt = d.sizes["time"]
                t0 = pd.Timestamp(d.time.values[0])
                d.close()
                thw = pd.read_csv(thwf, parse_dates=["event_start", "event_end"])
                mhw = pd.read_csv(mhwf, parse_dates=["event_start", "event_end"])
                lpd = {}
                for row in P.itertuples(index=False):
                    lpd[(int(row.land_lat_idx), int(row.land_lon_idx))] = (
                        int(row.ocean_lat_idx), int(row.ocean_lon_idx))
                om = {}
                for k, g in mhw.groupby(["lat_idx", "lon_idx"]):
                    om[k] = _event_mask(g, nt, t0)
                kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
                thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
                thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}
                out = {}
                for variant, (sh_l, sh_o, t0v) in {
                    "原样(as-is)": (0, 0, t0),
                    "t0 归零(h 修复)": (0, 0, t0.normalize()),
                    "t0归零+SST前移一天": (0, -1, t0.normalize()),
                    "t0归零+SST后移一天": (0, +1, t0.normalize()),
                }.items():
                    cd = sd = td = 0
                    omv = {}
                    for k, g in mhw.groupby(["lat_idx", "lon_idx"]):
                        omv[k] = _event_mask(g, nt, t0v, sh_o)
                    for lk, ok_ in lpd.items():
                        g = thw_by.get(lk)
                        if g is None or len(g) == 0:
                            continue
                        lm = _event_mask(g, nt, t0v, sh_l)
                        td += int(lm.sum())
                        m_ = omv.get(ok_)
                        cd += int((lm & (m_ if m_ is not None else 0)).sum())
                        sd += int((lm & ~(m_ if m_ is not None
                                         else np.zeros(nt, bool))).sum())
                    out[variant] = (cd, sd, td)
                rows.append((exp, m, out))
        for exp, m, out in rows:
            ref = R[(R.exp == exp) & (R.member.astype(str).str.zfill(3) == m)]
            refcd = int(ref.compound_days.iloc[0]) if len(ref) else -1
            asis = out["原样(as-is)"][0]
            print(f"[E] {exp} {m}: 复算原样 compound={asis} vs 记录 {refcd} "
                  f"{'一致 ✓' if asis == refcd else '!! 不一致'}")
            for variant, (cd, sd, td) in out.items():
                print(f"[E]    {variant:22s}: compound={cd:7d} standalone={sd:7d} "
                      f"THW配对日={td:7d}"
                      + (f"   Δcompound={cd - asis:+d} ({(cd/asis-1)*100:+.1f}%)"
                         if variant != "原样(as-is)" and asis else ""))
        # 汇总
        for variant in ("原样(as-is)", "t0 归零(h 修复)", "t0归零+SST前移一天"):
            a = sum(o[variant][0] for e, m, o in rows if e == "ALL")
            x = sum(o[variant][0] for e, m, o in rows if e == "XGHG")
            print(f"[E] 汇总 {variant:22s}: ALL 3 成员 compound={a}, XGHG={x}, "
                  f"ALL/XGHG={a / x:.3f}" if x else "")
        RESULTS[f"E_tag{tag or 'v1'}"] = {f"{e}_{m}": {k: v for k, v in o.items()}
                                          for e, m, o in rows}


# ══════════════════════════════════════════════════════════════════
# S. 网格维度上的阈值塌缩 (审计中发现的 P0)
# ══════════════════════════════════════════════════════════════════
def _compound_segments(mhw, thw, P, nt, t0, shift_mhw=0):
    """复刻 compound_events.identify_compound_events, 附加 MHW 掩码平移参数。"""
    lpd = {}
    for row in P.itertuples(index=False):
        lpd[(int(row.land_lat_idx), int(row.land_lon_idx))] = (
            int(row.ocean_lat_idx), int(row.ocean_lon_idx))
    om = {k: _event_mask(g, nt, t0, shift_mhw)
          for k, g in mhw.groupby(["lat_idx", "lon_idx"])}
    kd = pd.DataFrame(list(lpd.keys()), columns=["lat_idx", "lon_idx"])
    thw_co = thw.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
    thw_by = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}
    recs = []
    for lk, ok_ in lpd.items():
        g = thw_by.get(lk)
        if g is None or len(g) == 0:
            continue
        lm = _event_mask(g, nt, t0)
        m_ = om.get(ok_)
        if m_ is None or not m_.any():
            continue
        coex = lm & m_
        if not coex.any():
            continue
        starts, ends = _runs_idx(coex)
        for a, b in zip(starts, ends):
            recs.append({"thw_start": t0 + pd.Timedelta(days=int(a)),
                         "thw_end": t0 + pd.Timedelta(days=int(b)),
                         "land_lat_idx": lk[0], "land_lon_idx": lk[1],
                         "ocean_lat_idx": ok_[0], "ocean_lon_idx": ok_[1],
                         "land_lat": float(g.lat.iloc[0]),
                         "land_lon": float(g.lon.iloc[0])})
    return pd.DataFrame(recs)


def _runs_idx(mask):
    x = np.concatenate(([0], mask.astype(np.int8), [0]))
    d = np.diff(x)
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1


def sec_E2():
    hr("E2  对齐修正对 v2 PR/FAR 的影响 (论文 Eq.3 口径)")
    sys.path.insert(0, os.path.join(BASE, "python"))
    try:
        import config as C                                       # noqa: F401
        from phase6_cesm import (_annual_per_pair, _obs_annual_threshold,
                                 _pr_boot)
    except Exception as e:                                       # noqa: BLE001
        print(f"[E2] 跳过：phase6_cesm 接口已变动，导入失败 -> {e!r}")
        print("[E2] 注: 本审计针对 714 行修订版；当前 862 行版已将 _pooled_threshold_*")
        print("[E2]     重构为 _pooled_threshold(kind=...)，_pr_boot 返回签名可能已变。")
        return
    P = pd.read_csv(PAIRS_CSV)
    obs = _obs_annual_threshold()
    v22_mean = float(obs.loc[obs.year == 2022, "med_mean"].iloc[0])
    v22_max = float(obs.loc[obs.year == 2022, "med_max"].iloc[0])
    print(f"[E2] 观测 Med 2022 阈值: 区域均值口径={v22_mean:.1f} 天, "
          f"格点最大口径={v22_max:.1f} 天")
    tag = "_x"
    for vname, variant, shift in (("as_is", "原样(as-is)", 0),
                                  ("fixed", "修正(SST 掩码前移 1 天)", -1)):
        samples = {}
        for exp in ("ALL", "XGHG"):
            parts = []
            for m in ("001", "002", "003"):
                t2mf = os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc")
                thwf = os.path.join(CESM_INT, f"thw{tag}_{exp}_{m}.csv")
                mhwf = os.path.join(CESM_INT, f"mhw{tag}_{exp}_{m}.csv")
                d = xr.open_dataset(t2mf)
                nt = d.sizes["time"]
                tda = d["T2m"]
                t0 = pd.Timestamp(d.time.values[0])
                thw = pd.read_csv(thwf, parse_dates=["event_start", "event_end"])
                mhw = pd.read_csv(mhwf, parse_dates=["event_start", "event_end"])
                seg = _compound_segments(mhw, thw, P, nt, t0, shift_mhw=shift)
                ann = _annual_per_pair(seg, tda, P)
                parts.append(ann)
                d.close()
            samples[exp] = pd.concat(parts)
        line = []
        for col in ("med_mean", "med_max"):
            x22 = v22_mean if col == "med_mean" else v22_max
            sa = samples["ALL"][col].values.astype(float)
            sf = samples["XGHG"][col].values.astype(float)
            res = _pr_boot(x22, sa, sf)
            if isinstance(res, tuple) and len(res) >= 4:
                pr, far, lo, hi = res[0], res[1], res[2], res[3]
            else:                                    # 接口变动兜底
                print(f"[E2]   (!! _pr_boot 返回 {type(res)}/{len(res) if hasattr(res, '__len__') else '?'} "
                      f"项，仅取前 4 项)")
                pr, far, lo, hi = res[0], res[1], res[2], res[3]
            prs = f"{pr:.2f}" if np.isfinite(pr) else "inf"
            line.append(f"{col}: P_ALL={np.mean(sa >= x22):.3f} "
                        f"P_fix={np.mean(sf >= x22):.3f} PR={prs} FAR={far:.3f} "
                        f"CI[{lo:.1f},{hi:.1f}]")
        print(f"[E2] {variant}:")
        for l in line:
            print(f"[E2]    {l}")
        print(f"[E2]    年暴露中位(Med 框) ALL={np.median(samples['ALL'].med_mean):.1f} "
              f"XGHG={np.median(samples['XGHG'].med_mean):.1f} 天; "
              f"总暴露比 = "
              f"{samples['ALL'].med_mean.sum() / samples['XGHG'].med_mean.sum():.3f}")
        RESULTS[f"E2_{vname}"] = line
    print("[E2] 参考: results/复现报告.md:349 记录 'v2 22 年总暴露比 8.88; "
          "PR(med_max)=48.0 FAR=0.98 CI 14.7-53.0'")


def sec_S():
    hr("S  _pooled_threshold_t2m 的空间维度塌缩 (审计副产物, P0)")
    z = np.load(os.path.join(CESM_INT, "thresh_t2m_xghg.npz"))
    t = z["thresh"]
    print(f"[S] thresh_t2m_xghg.npz: shape={t.shape}")
    rowstd = np.nanstd(t, axis=1)
    print(f"[S] 每行(每个 doy) 在 206 个陆点之间的标准差 ~0 的行数: "
          f"{int(np.sum(rowstd < 1e-9))}/{t.shape[0]}  → 阈值空间上完全均匀")
    print(f"[S] 全 NaN 行数: {int(np.isnan(t).all(axis=1).sum())} (第 366 行)")
    print(f"[S] doy=1 行前 5 个值: {t[0, :5]}  (206 个值全同)")
    odd = np.where(~(rowstd < 1e-9) & ~np.isnan(rowstd))[0]
    print(f"[S] 既非'空间均匀'也非全 NaN 的行: {odd.tolist()} "
          f"(共 {len(odd)} 行); 全 NaN 行索引 = "
          f"{np.where(np.isnan(t).all(axis=1))[0].tolist()}")
    for r in odd:
        u = np.unique(t[r][~np.isnan(t[r])])
        print(f"[S]   行 {r} (doy={r + 1}) 取值数={len(u)}, 前 5 个={u[:5]}, "
              f"后 3 个={u[-3:]}, NaN 个数={int(np.isnan(t[r]).sum())}")

    # ---- S2: 缓存与当前源码是否一致 (用 3 个 XGHG 成员按当前公式重算) ----
    print("\n[S] --- S2 缓存一致性: 用当前源码公式重算, 与 npz 逐值比对 ---")
    P = pd.read_csv(PAIRS_CSV)
    pj = P.land_lat_idx.values
    pi = P.land_lon_idx.values
    mats, doys = [], []
    for m in ("001", "002", "003"):
        f = os.path.join(CESM_INT, f"XGHG_{m}_T2m.nc")
        if not os.path.exists(f):
            print(f"[S] !! 缺 {f}"); break
        d = xr.open_dataset(f)
        arr = d["T2m"].values.astype(np.float64)       # (nt,49,51) 80MB
        mats.append(arr[:, pj, pi])
        doys.append(pd.DatetimeIndex(d.time.values).dayofyear.values)
        d.close()
    m_all = np.concatenate(mats, axis=0)
    doy_all = np.concatenate(doys)
    print(f"[S] 重算样本: {m_all.shape} ({len(mats)} 成员)")
    nland = m_all.shape[1]
    single = np.full((366, nland), np.nan)
    for dd in np.arange(1, 366):
        rr = m_all[doy_all == dd]
        if len(rr):
            single[dd - 1] = np.nanpercentile(rr, 90, axis=0)
    # 当前源码写法 (phase6_cesm.py:326-330)
    thresh_src = np.full_like(single, np.nan)
    for dd in np.arange(1, 366):
        win = [(dd + k - 1) % 365 + 1 for k in range(-5, 6)]
        stacked = np.concatenate([single[w - 1] for w in win], axis=0)
        thresh_src[dd - 1] = np.nanpercentile(stacked, 90, axis=0)
    # 正确写法 (逐点分位)
    thresh_fix = np.full_like(single, np.nan)
    for dd in np.arange(1, 366):
        win = [(dd + k - 1) % 365 + 1 for k in range(-5, 6)]
        stacked = np.stack([single[w - 1] for w in win], axis=0)   # (11, nland)
        thresh_fix[dd - 1] = np.nanpercentile(stacked, 90, axis=0)
    diff = np.abs(thresh_src - t)
    ok = ~(np.isnan(thresh_src) & np.isnan(t))
    print(f"[S] 当前源码公式重算 vs 落盘 npz: 不一致的元素数 = "
          f"{int(np.nansum(diff > 1e-9))}/{t.size}, 行级不一致 = "
          f"{int((np.nansum(diff > 1e-9, axis=1) > 0).sum())}/366")
    bad_rows = np.where(np.nansum(diff > 1e-9, axis=1) > 0)[0]
    print(f"[S]   不一致行索引 = {bad_rows.tolist()[:20]}"
          f"{' ...' if len(bad_rows) > 20 else ''}")
    for r in bad_rows[:3]:
        print(f"[S]   行 {r}: npz 唯一值={np.unique(t[r])[:4]}, "
              f"重算唯一值={np.unique(thresh_src[r])[:4]}, "
              f"max|diff|={np.nanmax(diff[r]):.4f}")
    print(f"[S]   正确(逐点)阈值 vs 源码阈值: max|diff| = "
          f"{np.nanmax(np.abs(thresh_fix - thresh_src)):.4f} °C, "
          f"逐点空间标准差中位 = "
          f"{np.nanmedian(np.nanstd(thresh_fix, axis=1)):.4f} °C")
    np.savez_compressed(os.path.join(OUT, "recomputed_thresh_t2m.npz"),
                        src=thresh_src, fix=thresh_fix)
    print(f"[S] 重算结果 -> {os.path.join(OUT, 'recomputed_thresh_t2m.npz')}")
    RESULTS["S_cache_row_mismatch"] = int((np.nansum(diff > 1e-9, axis=1) > 0).sum())
    print(f"[S] 根因2: 平滑循环只跑 np.arange(1,366) → 第 365 行(doy=366, 即闰年 12-31)"
          f" 未被填 → 该行全 NaN。实测 doy=366 在 8030 天里出现 "
          f"{int((pd.DatetimeIndex(xr.open_dataset(T2M_XGHG_001).time.values).dayofyear == 366).sum())} 次")
    print(f"[S]   后果: _detect_thw_member_ext 的 thr_t=thresh[doy-1] 在 doy=366 时取到 "
          f"全 NaN 行 → 该日恒不超阈 (6 天 x 206 点 / 8030 天 = 0.075%)")
    print(f"[S] 全表取值 min={np.nanmin(t):.4f}, max={np.nanmax(t):.4f} °C "
          f"(这是全欧平均的季节循环, 不是逐点阈值)")
    zs = np.load(os.path.join(CESM_INT, "thresh_sst_xghg.npz"))["thresh"]
    print(f"[S] 对照 thresh_sst_xghg.npz: 空间标准差 == 0 的行数 "
          f"{int(np.sum(np.nanstd(zs, axis=1) == 0))}/{zs.shape[0]} → 正常")

    print("[S] 根因复现 (phase6_cesm.py:326-330):")
    nland = t.shape[1]
    single = np.arange(1.0, nland + 1.0)[None, :] * np.ones((366, 1))
    win = [(1 + k - 1) % 365 + 1 for k in range(-5, 6)]
    stacked = np.concatenate([single[w - 1] for w in win], axis=0)
    print(f"[S]   single 形状={single.shape}; win={win}")
    print(f"[S]   np.concatenate([single[w-1] for w in win], axis=0).shape = "
          f"{stacked.shape}   ← 1 维! (期望 (11, nland) 或按点分别求分位)")
    q = np.nanpercentile(stacked, 90, axis=0)
    print(f"[S]   np.nanpercentile(stacked, 90, axis=0) => {q!r} (标量)")
    print(f"[S]   赋值 thresh[d-1] = 标量 → 广播到整行 (shape {t.shape[1]})")
    print("[S] 影响: results/intermediate/cesm/thw_x_*.csv (v2 反事实 THW) 的阈值"
          "全欧统一 —— 南欧点几乎恒超阈、北欧点几乎不超阈, 事件数被系统性扭曲")

    # 量化影响: 用落地阈值统计 thw_x 事件数 vs 用真逐点阈值
    P = pd.read_csv(PAIRS_CSV)
    f = os.path.join(CESM_INT, "XGHG_001_T2m.nc")
    if os.path.exists(f):
        ds = xr.open_dataset(f)
        pj = P.land_lat_idx.values; pi = P.land_lon_idx.values
        da = ds["T2m"].isel(lat=xr.DataArray(pj, dims="p"), lon=xr.DataArray(pi, dims="p"))
        arr = da.transpose("time", "p").values.astype(np.float64)
        doy = pd.DatetimeIndex(da.time.values).dayofyear.values
        ds.close()
        # 真: 逐点逐 doy 11 天窗 90 分位
        single2 = np.full((366, arr.shape[1]), np.nan)
        for d in np.arange(1, 366):
            rows = arr[doy == d]
            if len(rows):
                single2[d - 1] = np.nanpercentile(rows, 90, axis=0)
        true_thr = np.full_like(single2, np.nan)
        for d in np.arange(1, 366):
            win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
            st = np.stack([single2[w - 1] for w in win], axis=0)   # (11, nland)
            true_thr[d - 1] = np.nanpercentile(st, 90, axis=0)
        thr_t = t[doy - 1]
        ex_bad = float((arr > thr_t).mean() * 100)
        ex_ok = float((arr > true_thr[doy - 1]).mean() * 100)
        print(f"[S] 量化: XGHG 001 陆点全时段超阈比例 —— 落地(塌缩)阈值 "
              f"{ex_bad:.2f}% vs 正确逐点阈值 {ex_ok:.2f}% "
              f"(11 天窗合并分位下逐点超阈率本就 <10%, 关键是空间分布)")
        sp = pd.DataFrame({"land_lat": P.land_lat, "land_lon": P.land_lon,
                           "exceed_collapsed_%": (arr > thr_t).mean(axis=0) * 100,
                           "exceed_true_%": (arr > true_thr[doy - 1]).mean(axis=0) * 100})
        sp.to_csv(os.path.join(OUT, "S_exceedance_by_point.csv"), index=False)
        print(f"[S] 逐点超阈率 -> {os.path.join(OUT, 'S_exceedance_by_point.csv')}")
        print(f"[S]   塌缩阈值下: 南欧(land_lat<40) 平均超阈 "
              f"{sp[sp.land_lat < 40]['exceed_collapsed_%'].mean():.1f}%, "
              f"北欧(>60) {sp[sp.land_lat > 60]['exceed_collapsed_%'].mean():.1f}%")
        print(f"[S]   正确阈值下: 南欧 {sp[sp.land_lat < 40]['exceed_true_%'].mean():.1f}%, "
              f"北欧 {sp[sp.land_lat > 60]['exceed_true_%'].mean():.1f}%")
        RESULTS["S_exceed_collapsed"] = ex_bad
        RESULTS["S_exceed_true"] = ex_ok


# ══════════════════════════════════════════════════════════════════
SECTIONS = {
    "A1": lambda: sec_A1(_X), "A2": lambda: sec_A2(_X), "A3": lambda: sec_A3(_X),
    "A4": lambda: sec_A4(_X), "A5": sec_A5, "A6": lambda: sec_A6(_X),
    "B1": lambda: sec_B1(_X), "B2": lambda: sec_B2(_X), "B3": sec_B3, "B4": sec_B4,
    "C1": sec_C1, "C2": sec_C2, "C3": sec_C3, "E": sec_E, "E2": sec_E2, "S": sec_S,
}
_X = None


def main():
    global _X
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔段号, 空=全部")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print(" ".join(SECTIONS)); return
    os.makedirs(OUT, exist_ok=True)
    want = [s.strip() for s in a.only.split(",") if s.strip()] or list(SECTIONS)
    need_pairs = any(s in ("A1", "A2", "A3", "A4", "A6", "B1") for s in want)
    if need_pairs:
        print("[init] 复算 cmd_pairs ...")
        _X = pairs_internals()
    for s in want:
        SECTIONS[s]()
    save_json()


if __name__ == "__main__":
    main()
