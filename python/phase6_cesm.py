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

MAX_PAIR_DIST_DEG = C.MAX_PAIR_DIST_DEG   # f09/gx1v6 均 ~1° 网格, 观测的 0.5° 不适用

# ══════════════════════════════════════════════════════════════════════════
# Phase 6 口径决策（2026-09-23 用户拍板）
#   ★ 第三轮（2026-09-23）：这些常量已**下沉到 python/config.py**（SPEC §3.1 要求
#     "参数集中管理，避免硬编码"），此处改为引用；**取值一个未变**，CLI 默认值亦不变。
#     原委：results/phase6审计报告.md（问题清单）+ results/复现报告.md §5 D7（拍板记录）。
# ══════════════════════════════════════════════════════════════════════════
# 决策 1B：复合事件定义 = **MHW 包络**（论文模型 Methods paper_text.txt:546
#   "a marine heatwave fully encompasses a terrestrial heatwave"），
#   与已定稿的图1j-l（方案 B）同语义：
#     某 MHW 完全涵盖 >=1 个 THW 事件 -> 该 MHW 的**全部跨度天**计为复合天。
#   共超标口径（论文观测 Methods L502-503 / compound_events.identify_compound_events）
#   保留为 `--compound-def exceed`，供敏感性对照；图1a-i/1m/图2 仍用共超标。
COMPOUND_DEF = C.COMPOUND_DEF               # {"envelope", "exceed"}
# 决策 3A：主口径 = 区域暴露均值；p90 敏感性；格点最大降为参考
MAIN_AGG = C.MAIN_AGG
AGG_COLS = tuple(C.AGG_COLS)
AGG_LABEL = {"med_mean": "区域均值（主口径）",
             "med_p90": "区域 p90（敏感性）",
             "med_max": "格点最大（参考，原 P0 口径）"}
# 决策 2C：归因阈值扫描 + 论文 Fig.3c 的三条年份参考线（Med&BS 面板）
SWEEP_MIN, SWEEP_MAX, SWEEP_STEP = C.SWEEP_MIN, C.SWEEP_MAX, C.SWEEP_STEP
PAPER_THR_REFS = dict(C.PAPER_THR_REFS)     # 论文 Fig.3c 垂直线
# 决策 5A：主口径 = 独立重采样（论文 Methods :585-587 字面）；block 作附录
BOOT_MODE = C.BOOT_MODE                     # {"indep", "block"}（block = 成员内分层 + 块）
N_BOOTSTRAP = C.N_BOOTSTRAP
CI = C.CI_ALPHA

MEMBERS_P0 = C.CESM_ALL_MEMBERS[:C.CESM_P0_MEMBERS]


# ══════════════════════════════════════════════════════════════════════════
# ★ 2026-11-07：气候态基准期（论文 = 1983–2012 的 90 分位）可独立于分析期指定
#   背景：论文 Methods 明写阈值取 "the 90th percentile of the 1983–2012
#   climatological distribution"，而我们此前只有 CESM 的 2000–2021 切片，
#   只好拿 XGHG+LOO 在**同一 22 年**上取分位（D7.4）。用户 2026-11-07 拍板「补齐」：
#   另下 1983–2012 切片，阈值改用该期气候态，事件仍在 2000–2021 上检测。
#   用法：`detect --clim-period 1983-2012`（文件 tag 与 proc 文件名一致）。
# ══════════════════════════════════════════════════════════════════════════
CLIM_PERIOD_TAG = ""          # "" = 用分析期自身（旧行为）；"1983-2012" = 论文口径


def _period_tag_cli(spec):
    """`--clim-period 1983-2012` → '1983-2012'（也接受 1983-01-01:2012-12-31）。"""
    spec = (spec or "").strip()
    if not spec:
        return ""
    if spec.count("-") == 1:
        a, b = spec.split("-")
        return f"{int(a):04d}-{int(b):04d}"
    if ":" in spec:
        a, b = spec.split(":")
        return f"{a.strip()[:4]}-{b.strip()[:4]}"
    raise SystemExit(f"--clim-period 格式应为 Y0-Y1 或 START:END，收到 {spec!r}")


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
def _norm_latlon(obj):
    """统一坐标名为 lat/lon（gdex 切片件可能用 latitude/longitude）。★F11 配套"""
    ren = {}
    for a, b in (("latitude", "lat"), ("longitude", "lon")):
        if a in getattr(obj, "dims", ()) or a in getattr(obj, "coords", ()):
            ren[a] = b
    return obj.rename(ren) if ren else obj


def _prefer_gdex(fs, gdex_path):
    """同一成员若**同时**有 gdex 整段件与 raw/trim 分段件，只用 gdex 整段件。

    ★ 2026-10-30（P0）：`proc` 目录里成员 001–003 同时存在旧 raw+trim 分段件
      （`B20TRC5CNBDRD…18500102-20051231_2000-2021.nc` / `BRCP85C5CNBDRD…`）与新的
      gdex 整段件（`sst_all_001_2000-2021.nc`）。两者时间轴都覆盖 2000–2021，
      拼在一起会把同一时段算两遍（时间轴重复 ⇒ 阈值分位、事件天数、暴露量全部错）。
      实测未修前 ALL-001 的 SST 段返回 **3 个**文件、T2m 返回 **2 个**。
    """
    if os.path.exists(gdex_path):
        others = [s for s in fs if os.path.abspath(s) != os.path.abspath(gdex_path)]
        if others:
            print(f"  ⚠ 同一成员有 {len(others)} 个 raw/trim 分段件与 gdex 整段件并存 "
                  f"→ 只用 {os.path.basename(gdex_path)}")
        return [gdex_path]
    return sorted(set(fs))


def find_t2m_segments(exp, m, tag="2000-2021"):
    """返回该成员 (exp) 的 TREFHT proc 段文件列表 (按起始年排序)。

    ★F11：同时接受 **gdex 产出名** `trefht_{exp}_{m}_2000-2021.nc`
    （`download_cesm1le.py::cmd_gdex` 的命名规则 `{var}_{exp}_{mem}_{y0}-{y1}.nc`）
    与 aws/trim 派生名。两者的大气网格框一致（`config.CESM_EUROPE_LAT/LON`）。
    ★ 2026-11-07：`tag` 选时段（默认分析期 2000-2021；气候态期用 1983-2012）。
    """
    pats = []
    if exp == "ALL":
        pats.append(os.path.join(CESM_PROC_DIR, f"TREFHT_all_{m}_{tag}_europe.nc"))
        pats.append(os.path.join(CESM_PROC_DIR, f"trefht_all_{m}_{tag}.nc"))
    else:
        pats.append(os.path.join(CESM_PROC_DIR, f"*xghg.{m}.cam.h1.TREFHT.*_{tag}.nc"))
        pats.append(os.path.join(CESM_PROC_DIR, f"trefht_xghg_{m}_{tag}.nc"))
    fs = []
    for p in pats:
        fs += glob.glob(p)
    gdex = os.path.join(CESM_PROC_DIR, f"trefht_{'all' if exp == 'ALL' else 'xghg'}_{m}_{tag}.nc")
    return _prefer_gdex(fs, gdex)


def find_sst_segments(exp, m, tag="2000-2021"):
    """返回该成员 (exp) 的 POP SST proc 段文件列表。

    ★F11：额外接受 gdex 产出名 `sst_{exp}_{m}_2000-2021.nc`。
    注意 gdex 件必须保留 POP 全局网格（见 `download_cesm1le._mask_sst_box` 的说明），
    否则 `coastal_pairs_cesm.csv` 里缓存的网格索引会与文件错位。
    ★ 2026-11-07：`tag` 选时段（默认分析期 2000-2021；气候态期用 1983-2012）。
    """
    if exp == "ALL":
        pats = [
            os.path.join(CESM_PROC_DIR,
                         f"*B20TRC5CNBDRD.f09_g16.{m}.pop.h.nday1.SST.*_{tag}.nc"),
            os.path.join(CESM_PROC_DIR,
                         f"*BRCP85C5CNBDRD.f09_g16.{m}.pop.h.nday1.SST.*_{tag}.nc"),
            os.path.join(CESM_PROC_DIR, f"sst_all_{m}_{tag}.nc"),
        ]
    else:
        pats = [
            os.path.join(CESM_PROC_DIR,
                         f"*xghg.{m}.pop.h.nday1.SST.*_{tag}.nc"),
            os.path.join(CESM_PROC_DIR, f"sst_xghg_{m}_{tag}.nc"),
        ]
    gdex = os.path.join(CESM_PROC_DIR, f"sst_{'all' if exp == 'ALL' else 'xghg'}_{m}_{tag}.nc")
    return _prefer_gdex(sum([glob.glob(p) for p in pats], []), gdex)


# ──────────────────────────────────────────────
# prepare
# ──────────────────────────────────────────────
def _atm_reference():
    """参考大气网格（lat/lon）：取 ALL 001 的 TREFHT proc 件。

    ★F11：不再硬编码 `TREFHT_all_001_2000-2021_europe.nc`——只有 raw+trim 路径才产出
    该名，gdex 路径产出的是 `trefht_all_001_2000-2021.nc`。
    """
    refs = find_t2m_segments("ALL", "001")
    if not refs:
        raise FileNotFoundError(
            "找不到 ALL 001 的 TREFHT proc 文件（aws/trim 或 gdex 命名均可）；"
            f"目录 = {CESM_PROC_DIR}")
    return refs[0]


def cmd_prepare(args):
    """逐成员生成 {exp}_{m}_T2m.nc (Europe 框, °C, 拼好两段)。"""
    os.makedirs(CESM_INT, exist_ok=True)
    # 参考欧洲框: 取 ALL 001 成品件的 lat/lon
    ref = _norm_latlon(xr.open_dataset(_atm_reference()))
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
                da = _norm_latlon(ds[var])          # ★F11：gdex 件可能用 latitude/longitude
                # 统一到参考成品的欧洲框坐标 (XGHG 原生 0-360 经度/纬度可能降序)
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
    ref = _norm_latlon(xr.open_dataset(_atm_reference()))   # ★F11：不硬编码 aws 名
    atm_lat = ref.lat.values.astype(float)   # 升序?
    atm_lon = ref.lon.values.astype(float)   # -17..47
    ref.close()

    sst_segs = find_sst_segments("ALL", "001")             # ★F11
    if not sst_segs:
        raise FileNotFoundError(
            f"找不到 ALL 001 的 POP SST proc 文件；目录 = {CESM_PROC_DIR}")
    sst_f = sst_segs[0]
    ds = xr.open_dataset(sst_f, decode_times=False)
    for need in ("KMT", "TLAT", "TLONG"):
        if need not in ds:
            ds.close()
            raise KeyError(
                f"{os.path.basename(sst_f)} 缺少 POP 静态场 {need}——"
                "gdex 切片件必须用**第三轮修正后**的 download_cesm1le.py 生成"
                "（该版本保留 KMT/TLAT/TLONG）；否则请改用 raw+trim 路径。")
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
    print(f"  ⚠ 网格来源 = {os.path.basename(sst_f)}（POP 索引 {kmt.shape}）；"
          f"若日后改用另一来源（raw/trim ↔ gdex）必须**重跑 pairs**，否则索引会静默错位。")

    # 4) R 域文件 (只检测配对陆点)
    dom = pairs_df[["land_lat", "land_lon"]].drop_duplicates()
    dom.columns = ["lat", "lon"]
    dom.to_csv(DOMAINS_CSV, index=False)
    print(f"R 域文件: {DOMAINS_CSV} ({len(dom)} 点)")


# ──────────────────────────────────────────────
# detect
# ──────────────────────────────────────────────
def _load_sst_points(exp, m, pairs_df, tag="2000-2021"):
    """配对海点 SST 序列 (块读+对角抽取)。返回 (vals(nt,npair), time, kmt_pt)。

    ★ 2026-11-07：`tag` 选时段文件（"2000-2021" = 分析期；"1983-2012" = 气候态期）。
    """
    segs = find_sst_segments(exp, m, tag=tag)
    if not segs:
        raise FileNotFoundError(f"{exp} {m}: 无 SST 段（时段 {tag}）")
    pj = pairs_df.ocean_lat_idx.values
    pi = pairs_df.ocean_lon_idx.values

    series, times = [], []
    kmt = None
    from netCDF4 import Dataset
    for f in segs:
        ds = xr.open_dataset(f)
        tv = pd.DatetimeIndex(ds.time.values)
        if kmt is None:
            if "KMT" not in ds:
                ds.close()
                raise KeyError(
                    f"{os.path.basename(f)} 缺 POP 静态场 KMT——gdex 切片件需用"
                    "**第三轮修正后**的 download_cesm1le.py 生成（保留 KMT/TLAT/TLONG）。")
            kmt = ds["KMT"].values
        ds.close()
        nc = Dataset(f)
        v = nc.variables["SST"]                     # (time, nlat, nlon)
        j0, j1 = int(pj.min()), int(pj.max()) + 1
        i1 = int(pi.max()) + 1
        if j1 > v.shape[1] or i1 > v.shape[2]:
            nc.close()
            raise ValueError(
                f"{os.path.basename(f)} 的 POP 网格 {tuple(v.shape[1:])} 小于配对索引所需 "
                f"({j1}, {i1})——coastal_pairs_cesm.csv 与该 SST 文件**不同源**"
                "（例如 pairs 由 raw/trim 全网格生成、detect 却用了被空间裁剪的 gdex 件）。"
                "请统一来源后重跑 pairs。")
        block = v[:, j0:j1, :].astype(np.float32)   # (nt, rows, 320) 一次大读
        nc.close()
        rows = block[:, pj - j0, :]                 # (nt, npair, 320)
        series.append(np.take_along_axis(
            rows, pi[np.newaxis, :, np.newaxis], axis=2)[:, :, 0])
        times.append(tv)
        del block, rows
    vals = np.concatenate(series, axis=0).astype(np.float64)   # (nt, npair)
    time = pd.DatetimeIndex([t for tv in times for t in tv])
    # ★F10：POP `time` = 平均区间**右端** ⇒ 标签 = 物理日 + 1（raw `time_bound` 实测）。
    #   统一回退 1 天，使 MHW 与 THW 的掩码落在同一物理日；不校正则 MHW 掩码整体晚 1 天。
    #   阈值池化（_pooled_threshold）与事件日期（cmd_detect）都吃这条时间轴，故一处即全覆盖。
    if SST_TIME_LABEL_SHIFT_DAYS:
        time = time + pd.Timedelta(days=SST_TIME_LABEL_SHIFT_DAYS)
    kmt_pt = np.asarray(np.ma.filled(kmt[pj, pi], 0))           # 配对点 KMT
    vals[:, kmt_pt <= 0] = np.nan               # 陆点/死海无值
    return vals, time, kmt_pt


def _load_t2m_points(exp, m, pairs_df, tag="2000-2021"):
    """配对陆点 T2m 序列 (nt, npair)，°C。返回 (vals, time)。
    （内存缓存见 `_clim_series`，勿重复读盘）

    ★ 2026-11-07：`tag` 选时段。
      · 分析期（2000-2021）优先读 prepare 产出的中间件 `CESM_INT/{exp}_{m}_T2m.nc`
        （已被 prepare 对齐到参考欧洲框，且单位已转 °C），省一次对齐；
      · 其他时段（如气候态 1983-2012）直接读 proc 件，按与 prepare **完全相同**的
        对齐规则（经度回 -180..180、就近取参考框、K→°C）落到同一网格，
        再按 pairs 的 land_lat_idx/land_lon_idx 抽点。
    对齐规则必须与 prepare 一致，否则 206 个陆点的索引会错位（网格同为 49×51）。
    """
    if tag == "2000-2021":
        f = os.path.join(CESM_INT, f"{exp}_{m}_T2m.nc")
        if os.path.exists(f):
            ds = xr.open_dataset(f)
            da = ds["T2m"].isel(
                lat=xr.DataArray(pairs_df.land_lat_idx.values, dims="p"),
                lon=xr.DataArray(pairs_df.land_lon_idx.values, dims="p"))
            vals = da.transpose("time", "p").values.astype(np.float64)
            time = pd.DatetimeIndex(da.time.values)
            ds.close()
            return vals, time
        print(f"  !! 缺中间件 {os.path.basename(f)}，回落到直接读 proc 件（先跑 prepare 更快）")
    ref = _norm_latlon(xr.open_dataset(_atm_reference()))
    ref_lat, ref_lon = ref.lat.values, ref.lon.values
    ref.close()
    segs = find_t2m_segments(exp, m, tag=tag)
    if not segs:
        raise FileNotFoundError(f"{exp} {m}: 无 TREFHT 段（时段 {tag}）")
    vals_l, time_l = [], []
    for f in segs:
        ds = xr.open_dataset(f)
        var = "TREFHT" if "TREFHT" in ds.data_vars else "T2m"
        da = _norm_latlon(ds[var])
        lon180 = ((da.lon.astype(float) + 180) % 360) - 180
        da = da.assign_coords(lon=lon180).sortby("lon")
        da = da.sel(lat=ref_lat, lon=ref_lon, method="nearest")
        if da.attrs.get("units", "").startswith("K") or float(np.nanmax(da.values)) > 150:
            da = da - 273.15
        da = da.isel(lat=xr.DataArray(pairs_df.land_lat_idx.values, dims="p"),
                     lon=xr.DataArray(pairs_df.land_lon_idx.values, dims="p"))
        vals_l.append(da.transpose("time", "p").values.astype(np.float64))
        time_l.append(pd.DatetimeIndex(ds.time.values))
        ds.close()
    vals = np.concatenate(vals_l, axis=0)
    time = pd.DatetimeIndex([t for idx in time_l for t in idx])
    order = np.argsort(time.values)
    return vals[order], time[order]


_CLIM_CACHE = {}     # (kind, exp, m, tag) -> (vals, time)；detect 的 20 个 LOO 池反复用同批成员


def _clim_series(kind, exp, m, pairs_df, tag):
    """阈值池化用的成员序列，**进程内缓存**。

    动机（2026-11-07）：`--clim-period` 让阈值改从 30 年气候态算，而 LOO 会为 20 个
    成员各建一次池（每池 19 个成员）。不做缓存时同一成员的 30 年序列被读 19 次
    ⇒ 单次 detect 读盘 ≈ 380 × 155 MB。缓存后每成员只读一次（内存 ≈ 18 MB/条）。
    """
    key = (kind, exp, m, tag)
    if key not in _CLIM_CACHE:
        vals, time = _load_stitched(kind, exp, m, pairs_df, tag)
        _CLIM_CACHE[key] = (vals, time)
    return _CLIM_CACHE[key]


# 气候态时段 → [(文件 tag, 日期切片)] 的拼接表。
# ★ 2026-11-07：论文气候态 1983–2012 里，**2000–2012 这 13 年已经在分析期文件里**，
#   只补下 1983–1999 即可（省 40% 流量）。两个时段在时间轴上首尾相接、无重叠。
CLIM_STITCH = {
    "1983-2012": [("1983-1999", None), ("2000-2021", ("2000-01-01", "2012-12-31"))],
}


def _slice_series(vals, time, start, end):
    m = (time >= pd.Timestamp(start)) & (time <= pd.Timestamp(end))
    return vals[m], time[m]


def _load_stitched(kind, exp, m, pairs_df, tag):
    """按 CLIM_STITCH 把多段文件拼成一条气候态序列（未登记则按单段 tag 读）。"""
    parts = CLIM_STITCH.get(tag)
    if parts is None:
        return _load_one(kind, exp, m, pairs_df, tag)
    vs, ts = [], []
    for ftag, sl in parts:
        v, t = _load_one(kind, exp, m, pairs_df, ftag)
        if sl:
            v, t = _slice_series(v, t, *sl)
        vs.append(v)
        ts.append(t)
    vals = np.concatenate(vs, axis=0)
    time = ts[0].append(ts[1:]) if len(ts) > 1 else ts[0]
    order = np.argsort(time.values)
    print(f"  气候态拼接 {exp} {m} [{kind}]: " +
          " + ".join(f"{f}({len(t)} 天)" for f, t in zip([p[0] for p in parts], ts)) +
          f" = {len(time)} 天 {str(time[0])[:10]}~{str(time[-1])[:10]}")
    return vals[order], time[order]


def _load_one(kind, exp, m, pairs_df, ftag):
    if kind == "sst":
        v, t, _ = _load_sst_points(exp, m, pairs_df, tag=ftag)
        return v, t
    return _load_t2m_points(exp, m, pairs_df, tag=ftag)


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
#   （F6 `--members` 全量名单见 select_members；F7 次序统计量 CI 见 _emp_quantile；
#     F8 日期原点 .normalize() 见 cmd_compound；F9 doy=366 见 _pooled_threshold）
THRESH_VERSION = C.THRESH_VERSION           # "v3_w11_loo"（下沉 config，值不变）

# ★ 第三轮修复（2026-09-23；见 results/规划一致性审查.md「第三轮」）★
#   F10 POP SST 时间标签校正 —— POP `time` 是平均区间的**右端**标签
#       （raw 实测 `time_bound[0] = (1920-01-01 01:00, 1920-01-02)`，标签 1920-01-02），
#       而 CAM TREFHT 的 `date` 是区间**左端**（标签 = 该物理日）⇒ **POP 标签 = 物理日 + 1**。
#       不校正时 MHW 掩码相对 THW 掩码整体晚 1 天（复合暴露量级 ±1~2%，并改变
#       包络判据"MHW 完全涵盖 THW"的边缘日）。此处把 SST 时间轴整体回退 1 天。
#       ⚠️ 该结论**推翻**了 phase6审计报告 §四 C11 的"已否证"裁决（§0.5 的方向是对的）。
#   F11 文件发现兼容 gdex 产出命名 `{var}_{exp}_{mem}_2000-2021.nc`
#       （download_cesm1le.py::cmd_gdex）。原先只认 aws/trim 派生名 ⇒
#       `--members 20` 时 prepare 对成员 004–020 静默跳过、detect 在成员 004
#       FileNotFoundError，即"全量只跑 3 个成员"在数据层复现（F6 只修了名单层）。
SST_TIME_LABEL_SHIFT_DAYS = C.SST_TIME_LABEL_SHIFT_DAYS     # -1


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
    详见 results/phase6审计报告.md 与 results/tools/phase6审计复算/phase6_audit_lead_check7.py。
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


def _thresh_cache_path(kind, members, exclude, clim_tag="2000-2021", pool_exp="XGHG"):
    """阈值缓存路径带**成员名单指纹**，避免换 --members / 换 LOO 时静默复用旧缓存。

    ★ 2026-11-07：再带**气候态时段**（`clim_tag`）——1983-2012 与 2000-2021 的阈值
      数值完全不同，混用会静默给出错基准。
    ★ 2026-11-08：再带**池的实验**（`pool_exp`）——`--baseline self` 时 ALL 用 ALL 的
      气候态、XGHG 用 XGHG 的，两者数值不同，不能共用缓存。XGHG 池沿用旧文件名
      （`_v5` 预计算的 20 个 LOO 缓存继续命中）。
    """
    tag = "-".join(sorted(members)) + ("_loo" + exclude if exclude else "")
    pe = "" if pool_exp == "XGHG" else f"_{pool_exp.lower()}"
    return os.path.join(
        CESM_INT, f"thresh_{kind}_xghg{pe}_{THRESH_VERSION}_{clim_tag}_{tag}.npz")


# ★ 第二十四批（_v9 标定扫描）：阈值整体加常数 °C。
#   动机：_v5(共用 XGHG 冷基准) / _v7(各用各的) / _v8(共用 ALL 暖基准) 把论文图4 夹在中间，
#   需要一个"参考气候态的暖度"标量 θ 来定位论文到底站在哪。实现只做**加法**，
#   缓存里存的仍是未偏移的基准分位（⇒ 所有 θ 复用同一批 `thresh_*.npz`）。
THRESH_OFFSET = 0.0
# ★ 第二十五批（_v11）：**按变量**的附加偏移。θ_sst 走 `--thresh-offset`，θ_t2m 走
#   `--thresh-offset-t2m`（额外叠加在 SST 偏移之上，所以两者互不覆盖）。
#   动机：实测 CESM ALL 相对观测的暖偏差 β 在两个变量上差一个量级
#   （T2m 地中海框 +1.17 °C，SST +0.07 °C），"观测阈值"读法要求陆地阈值单独抬高；
#   共享单一标量（_v9o40/_v9o70）已证明会把海洋/复合面板一起打死。
THRESH_OFFSET_T2M = 0.0
# ★ 第二十五批（_v12）：**只加在反事实世界（pool_exp='XGHG'）陆地阈值**上的偏移。
#   机理（_v11 双世界同偏移结果证明）：图4 的等效重现期几乎只由「两世界阈值之差」决定，
#   共同抬高只通过零膨胀把尾部弄歪（θ_t2m=1.10 反而把陆地 100 年从 14.7 抬到 25.9）。
#   所以真正能连续调节的旋钮是"参考气候态在两个实验之间的混合权重 w"：
#     XGHG 阈值 += w·δ_t2m  ⇔  w=0 即 _v7/_v10（各用各的），w=1 即 _v8 的陆地侧（完全共用）。
#   ⚠️ 只有 `--baseline self` 时 pool_exp == 被检测实验，才等价于"只动 XGHG 世界"；
#   `--baseline xghg` 下两个世界都用 XGHG 池，这个偏移会同时加到两边。
THRESH_OFFSET_XGHG_T2M = 0.0


def _offset_of(kind, pool_exp=None):
    """该 (变量, 池实验) 组合的总偏移（°C）。"""
    off = float(THRESH_OFFSET)
    if kind == "t2m":
        off += float(THRESH_OFFSET_T2M)
        if pool_exp == "XGHG":
            off += float(THRESH_OFFSET_XGHG_T2M)
    return off


def _with_offset(thr, kind="sst", pool_exp=None):
    """阈值 + 该 (变量, 池实验) 的偏移；总偏移 0 时原样返回。"""
    off = _offset_of(kind, pool_exp)
    if not off:
        return thr
    return np.asarray(thr, dtype=float) + off


def _pooled_threshold(pairs_df, members, exclude=None, kind="sst", clim_tag="2000-2021",
                      pool_exp="XGHG"):
    """合并反事实基准阈值 (366, npt)，heatwaveR ts2clm 语义。

    kind='sst' : 配对海点 SST；kind='t2m': 配对陆点 T2m。
    两者统一为「11 天窗内**合并原始样本**再取 90 分位」（windowHalfWidth=5），
    与 python/detect_events.R 的 ts2clm(pctile=90, windowHalfWidth=5L,
    smoothPercentile=FALSE) 同语义（smoothPercentile 只控制是否对阈值序列再做
    31 天滑动平均，不影响 11 天窗合并）。
    exclude：leave-one-out，从池中剔除该成员（主口径）。
    pool_exp：**池来自哪个实验**。默认 XGHG（`--baseline xghg`，两个世界共用反事实
      冷基准）；`--baseline self` 时传 exp 本身，各实验用自己的气候态。
    """
    pool = [m for m in members if m != exclude]
    if not pool:
        raise ValueError("池为空：exclude 后没有剩余成员")
    cache = _thresh_cache_path(kind, pool, None, clim_tag, pool_exp=pool_exp)
    if os.path.exists(cache):
        z = np.load(cache)
        if int(z["n_members"]) == len(pool):
            print(f"  阈值缓存命中 {os.path.basename(cache)} (池={len(pool)} 成员)")
            return _with_offset(z["thresh"], kind, pool_exp)
        print(f"  !! 缓存成员数不符({int(z['n_members'])}!={len(pool)})，重建")
    print(f"  阈值气候态时段: {clim_tag}  池实验: {pool_exp}")
    chunks = []
    for m in pool:
        vals, time = _clim_series(kind, pool_exp, m, pairs_df, clim_tag)
        chunks.append((vals, time.dayofyear.values))
        print(f"  基准池({kind}): {pool_exp} {m} ({vals.shape[0]} 天, 时段 {clim_tag})")
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
    return _with_offset(thresh, kind, pool_exp)


def _pooled_threshold_sst(pairs_df, members, exclude=None, clim_tag="2000-2021",
                          pool_exp="XGHG"):
    return _pooled_threshold(pairs_df, members, exclude, kind="sst",
                             clim_tag=clim_tag, pool_exp=pool_exp), np.arange(366)


def _pooled_threshold_t2m(pairs_df, members, exclude=None, clim_tag="2000-2021",
                          pool_exp="XGHG"):
    return _pooled_threshold(pairs_df, members, exclude, kind="t2m",
                             clim_tag=clim_tag, pool_exp=pool_exp)


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
    # ★ 2026-11-07：气候态基准期（论文 = 1983–2012）与事件分析期解耦。
    global CLIM_PERIOD_TAG
    CLIM_PERIOD_TAG = _period_tag_cli(getattr(args, "clim_period", "")) or "2000-2021"
    clim_tag = CLIM_PERIOD_TAG
    print(f"检测成员: {members}（共 {len(members)} 个）"
          f"{'  [leave-one-out 基准]' if (baseline == 'xghg' and loo) else ''}"
          f"  输出后缀={dtag!r}"
          f"{'  阈值气候态=' + clim_tag if clim_tag != '2000-2021' else ''}")
    # ★ _v9 标定扫描（第二十四批）/ _v11 按变量偏移 / _v12 只动 XGHG 世界陆地（第二十五批）
    global THRESH_OFFSET, THRESH_OFFSET_T2M, THRESH_OFFSET_XGHG_T2M
    THRESH_OFFSET = float(getattr(args, "thresh_offset", 0.0) or 0.0)
    THRESH_OFFSET_T2M = float(getattr(args, "thresh_offset_t2m", 0.0) or 0.0)
    THRESH_OFFSET_XGHG_T2M = float(getattr(args, "thresh_offset_xghg_t2m", 0.0) or 0.0)
    if THRESH_OFFSET or THRESH_OFFSET_T2M:
        print(f"== 阈值偏移 θ_sst={THRESH_OFFSET:+.2f} °C  θ_t2m="
              f"{THRESH_OFFSET + THRESH_OFFSET_T2M:+.2f} °C（两个世界共用同一偏移）==")
    if THRESH_OFFSET_XGHG_T2M:
        print(f"== 仅反事实世界陆地阈值偏移 w·δ = {THRESH_OFFSET_XGHG_T2M:+.2f} °C"
              f"（混合权重 w≈{THRESH_OFFSET_XGHG_T2M / 1.129:+.2f}，δ_t2m=1.129）==")

    if baseline == "self":
        # ★ 2026-11-08：`--baseline self` = 每个实验用自己的气候态算阈值。
        #   动机：`--baseline xghg` 让 ALL 也套 XGHG 的冷基准 90 分位，ALL 世界
        #   （暖 ~1.5 °C）常年超阈 ⇒ marine 暴露 254 天/年、序列饱和，图4 的
        #   "百年一遇"水平退化成 1–2 年一遇（见 `_v5` 结果）。自算基准下两个世界
        #   的超阈比例都 ~10%，重现期位移才可解释。
        print(f"== v6: 各实验自算基准（阈值池 = 本实验成员"
              f"{'，LOO 剔除自身' if loo else '，含自身'}；气候态 {clim_tag}）==")
        for exp in ("ALL", "XGHG"):
            for m in members:
                pool = [x for x in members if x != m] if loo else list(members)
                if not pool:
                    print(f"!! {exp} {m}: 池为空，跳过")
                    continue
                try:
                    thr_sst, _ = _pooled_threshold_sst(pairs_df, pool, clim_tag=clim_tag,
                                                       pool_exp=exp)
                    thr_t2m = _pooled_threshold_t2m(pairs_df, pool, clim_tag=clim_tag,
                                                    pool_exp=exp)
                except Exception as e:
                    print(f"!! 自算阈值失败 {exp} {m}: {e}")
                    continue
                try:
                    _detect_thw_member_ext(exp, m, pairs_df, thr_t2m, suffix=dtag)
                except Exception as e:
                    print(f"!! THW(x) 失败 {exp} {m}: {e}")
                try:
                    _detect_mhw_member(exp, m, pairs_df, thresh_ext=thr_sst, suffix=dtag)
                except Exception as e:
                    print(f"!! MHW(x) 失败 {exp} {m}: {e}")
        return

    if baseline == "all":
        # ★ 2026-11-08 第二十四批：`--baseline all` = 阈值池取 **ALL 实验** 的 1983–2012
        #   气候态，两个实验共用（`--loo` 时剔除当前成员）。
        #   动机：论文 Methods 写的是 "the 90th percentile of the 1983–2012 climatological
        #   distribution"——单数、唯一的分布。对 FixGHG 控制跑来说"1983–2012"只是任意
        #   30 年窗口，对 ALL 跑来说它就是观测期气候态 ⇒ 最字面的读法是**一份历史气候态、
        #   两个世界共用**。已试的两个极端都不是它：`_v5` 共用 XGHG 冷基准（ALL 侧过冲、
        #   marine 饱和），`_v7` 各用各的（自适应阈值把 1.2 °C 强迫整体抵消，XGHG 侧
        #   相对阈值只剩 +0.08 °C ⇒ FixGHG 百年暴露水平虚高，见 `_cmp_gev_tags.log`）。
        #   定量：ALL 的 1983–2012 比 XGHG 暖 ≈1.05 °C ⇒ XGHG 世界相对阈值 −0.82 °C。
        #   ★ 免费对照：ALL 侧阈值与 `--baseline self` 逐位相同（ALL 用自己 1983–2012 的
        #   合并 q90、LOO 池也一样）⇒ `_v8` 的 ALL 侧年暴露序列必须与 `_v7` 完全相同。
        print(f"== v8: 两实验共用 ALL 实验基准（阈值池 = ALL 成员"
              f"{'，LOO 剔除自身' if loo else '，含自身'}；气候态 {clim_tag}）==")
        for exp in ("ALL", "XGHG"):
            for m in members:
                pool = [x for x in members if x != m] if loo else list(members)
                if not pool:
                    print(f"!! {exp} {m}: 池为空，跳过")
                    continue
                try:
                    thr_sst, _ = _pooled_threshold_sst(pairs_df, pool, clim_tag=clim_tag,
                                                       pool_exp="ALL")
                    thr_t2m = _pooled_threshold_t2m(pairs_df, pool, clim_tag=clim_tag,
                                                    pool_exp="ALL")
                except Exception as e:
                    print(f"!! 共用 ALL 阈值失败 {exp} {m}: {e}")
                    continue
                try:
                    _detect_thw_member_ext(exp, m, pairs_df, thr_t2m, suffix=dtag)
                except Exception as e:
                    print(f"!! THW(x) 失败 {exp} {m}: {e}")
                try:
                    _detect_mhw_member(exp, m, pairs_df, thresh_ext=thr_sst, suffix=dtag)
                except Exception as e:
                    print(f"!! MHW(x) 失败 {exp} {m}: {e}")
        return

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
                        thr_sst, _ = _pooled_threshold_sst(pairs_df, pool, clim_tag=clim_tag)
                        thr_t2m = _pooled_threshold_t2m(pairs_df, pool, clim_tag=clim_tag)
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
        thr_sst, _ = _pooled_threshold_sst(pairs_df, members, clim_tag=clim_tag)
        thr_t2m = _pooled_threshold_t2m(pairs_df, members, clim_tag=clim_tag)
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
def _event_masks_by_key(events: pd.DataFrame, keys: set, nt: int, t0) -> dict:
    """
    事件表 → {key: 逐日布尔掩码}，只保留 keys 里出现过的键。

    key = (lat_idx, lon_idx)；MHW 表用海洋索引、THW 表用陆地索引
    （与 `cmd_compound` 里 `_pair_maps` 的用法一致）。
    """
    from compound_events import _event_daily_mask
    out = {}
    if events is None or len(events) == 0:
        return out
    for k, g in events.groupby(["lat_idx", "lon_idx"]):
        kk = (int(k[0]), int(k[1]))
        if kk in keys:
            out[kk] = _event_daily_mask(g, nt, t0)
    return out


def _annual_exposure_from_masks(masks: dict, keys: list, years: np.ndarray):
    """
    {key: 日掩码} → (n_year, n_key) 的年暴露天数矩阵 + 年份数组。

    ★ 第九批修复：原实现里混进了一个草稿表达式
    （`daily[years == uyears[0]] * 0 + …`），会把结果撑成 (n_days, n_key) 的三维形状。
    该错误由 `results/phase6_selftest.py` 第 6 节捕获。
    """
    keys = list(keys)
    nt = int(len(next(iter(masks.values())))) if masks else 0
    daily = np.zeros((max(nt, 1), len(keys)), dtype=np.int16)
    for j, k in enumerate(keys):
        m = masks.get(k)
        if m is not None:
            daily[:len(m), j] = np.asarray(m, dtype=np.int16)
    uyears = np.unique(years)
    ann = np.stack([daily[years == y].sum(axis=0) for y in uyears])   # (n_year, n_key)
    return ann, uyears


def _member_exposure_series(exp: str, member: str, tag: str, pairs_df: pd.DataFrame,
                            med: np.ndarray, verbose: bool = True) -> dict:
    """
    单个成员的三类**区域年暴露序列**（地中海 & 黑海，图4 的 a/b/c）：
      marine      —— 区域内**唯一海洋点**的 MHW 年天数（点均值）
      terrestrial —— 区域内**配对陆点**的 THW 年天数（点均值）
      compound    —— 复用 `annual{tag}_{exp}_{member}.csv` 的 `med_mean` 列
                     （图4 三类统一用区域均值；图3/Table 1 另用格点 p90，见 config.MAIN_AGG）
    """
    t2m_path = os.path.join(CESM_INT, f"{exp}_{member}_T2m.nc")
    if not os.path.exists(t2m_path):
        raise FileNotFoundError(f"缺 {t2m_path}（先跑 prepare）")
    with xr.open_dataset(t2m_path) as ds:
        time_da = ds["T2m"]
        nt = time_da.sizes["time"]
        years = time_da.time.dt.year.values
        t0 = pd.Timestamp(time_da.time.values[0]).normalize()

    mhw_f = os.path.join(CESM_INT, f"mhw{tag}_{exp}_{member}.csv")
    thw_f = os.path.join(CESM_INT, f"thw{tag}_{exp}_{member}.csv")
    for f in (mhw_f, thw_f):
        if not os.path.exists(f):
            raise FileNotFoundError(f"缺 {f}（先跑 detect）")
    mhw = pd.read_csv(mhw_f, parse_dates=["event_start", "event_end"])
    thw = pd.read_csv(thw_f, parse_dates=["event_start", "event_end"])

    sub = pairs_df[med]
    ocean_keys = list({(int(a), int(b)) for a, b in
                       sub[["ocean_lat_idx", "ocean_lon_idx"]].itertuples(index=False)})
    land_keys = list({(int(a), int(b)) for a, b in
                      sub[["land_lat_idx", "land_lon_idx"]].itertuples(index=False)})

    mo = _event_masks_by_key(mhw, set(ocean_keys), nt, t0)
    tl = _event_masks_by_key(thw, set(land_keys), nt, t0)
    ann_o, uyears = _annual_exposure_from_masks(mo, ocean_keys, years)
    ann_l, _ = _annual_exposure_from_masks(tl, land_keys, years)

    comp_path = os.path.join(CESM_INT, f"annual{tag}_{exp}_{member}.csv")
    if os.path.exists(comp_path):
        ca = pd.read_csv(comp_path)
        # 图4 三类序列统一用**区域均值**（区域年暴露；p90 会让 marine 常年顶到 365 天上限）
        comp = ca.set_index("year")["med_mean"].reindex(uyears).values
    else:
        raise FileNotFoundError(
            f"缺 {comp_path}（先跑：phase6_cesm.py compound --tag {tag}）")

    res = {"year": uyears,
           "marine": ann_o.mean(axis=1),
           "terrestrial": ann_l.mean(axis=1),
           "compound": comp}
    if verbose:
        print(f"  {exp} {member}: marine={res['marine'].mean():7.2f} "
              f"terrestrial={res['terrestrial'].mean():7.2f} "
              f"compound={np.nanmean(res['compound']):7.2f} 天/年（区域均值）")
    return res


def cmd_gev(args):
    """
    图 4：海洋 / 陆地 / 复合热浪日的**重现期位移**（ALL vs FixGHG）。

    论文口径（Methods "Return level and period estimation using GEV"）：
      ① FixGHG 区域年暴露序列 1000 次 bootstrap + MLE 拟合 GEV → 5/10/20/50/100 年重现水平
         （中位数 + 2.5–97.5 % CI）；
      ② 把各重现水平映射到 ALL 的等效重现期（同样 bootstrap）；
      ③ Gap = FixGHG 重现期 − ALL 等效重现期（论文图 4c 的红色标注）。

    输出契约（`python/fig4_return_period.py` 直接消费）：
        results/tables/phase6_gev{tag}.json
    """
    import json
    from gev_return_period import analyse_return_periods, analyse_return_periods_emp
    mapping = getattr(args, "mapping", "gev")

    tag = getattr(args, "tag", "")
    members = select_members(getattr(args, "members", C.CESM_P0_MEMBERS))
    n_boot = int(getattr(args, "n_boot", C.N_BOOTSTRAP))
    pairs_df = pd.read_csv(PAIRS_CSV)
    med = (pairs_df.land_lat.between(30, 47) & pairs_df.land_lon.between(5, 42)).values
    print(f"== 图4 重现期分析：{len(members)} 个成员/组，"
          f"bootstrap={n_boot}，区域 = 地中海&黑海（{int(med.sum())} 对）==")

    series = {"marine": {"ALL": [], "XGHG": []},
              "terrestrial": {"ALL": [], "XGHG": []},
              "compound": {"ALL": [], "XGHG": []}}
    for exp in ("ALL", "XGHG"):
        for m in members:
            try:
                r = _member_exposure_series(exp, m, tag, pairs_df, med,
                                            verbose=not getattr(args, "quiet", False))
            except FileNotFoundError as exc:
                print(f"!! 跳过 {exp} {m}: {exc}")
                continue
            for k in series:
                series[k][exp].extend(np.asarray(r[k], dtype=float).tolist())

    out = {"_meta": {"tag": tag, "n_members": len(members),
                     "agg": "med_mean (regional mean over coastal pairs)",
                     "region": "lat 30-47 / lon 5-42 (Mediterranean & Black Sea)",
                     "n_boot": n_boot, "ci": list(C.GEV_CI),
                     "mapping": mapping,
                     "compound_def": getattr(args, "compound_def", COMPOUND_DEF),
                     "source": "CESM1-LE ALL vs FixGHG"}}
    for k, d in series.items():
        a = np.asarray(d["ALL"], dtype=float)
        f = np.asarray(d["XGHG"], dtype=float)
        print(f"\n[{k}] 样本 N_ALL={a.size} N_XGHG={f.size}；"
              f"年暴露均值 ALL={np.nanmean(a):.2f} XGHG={np.nanmean(f):.2f} 天")
        if a.size < 8 or f.size < 8:
            print("  [skip] 样本不足 8，跳过 GEV 拟合（P0 3 成员时属正常）")
            out[k] = None
            continue
        res = analyse_return_periods_emp(a, f, n_bootstrap=n_boot,
                                        rps=C.GEV_RETURN_PERIODS,
                                        ci=C.GEV_CI) if mapping == "emp" else \
            analyse_return_periods(a, f, n_bootstrap=n_boot,
                                   rps=C.GEV_RETURN_PERIODS, ci=C.GEV_CI)
        block = {"fixghg": {f"{rp:g}": res["fixghg"]["rp"][float(rp)]
                            for rp in C.GEV_RETURN_PERIODS},
                 "all": {f"{rp:g}": res["all"][float(rp)]
                         for rp in C.GEV_RETURN_PERIODS},
                 "gap": {f"{rp:g}": res["gap"][float(rp)]
                         for rp in C.GEV_RETURN_PERIODS},
                 "n_years_all": res["n_years_all"],
                 "n_years_fixghg": res["n_years_fixghg"],
                 "n_valid_boot_fixghg": res["fixghg"]["n_valid"],
                 "n_failed_boot_fixghg": res["fixghg"]["n_failed"]}
        out[k] = block
        print("  FixGHG 重现水平 → ALL 等效重现期（中位数）与 Gap：")
        for rp in C.GEV_RETURN_PERIODS:
            rpv = float(rp)
            lv = block["fixghg"][f"{rp:g}"]["median"]
            av = block["all"][f"{rp:g}"]["median"]
            g = block["gap"][f"{rp:g}"]
            print(f"    {rpv:5.0f} 年：水平={lv:6.1f} 天 → ALL {av:6.2f} 年"
                  f"（Gap {g:6.2f}）")

    os.makedirs(C.TABLES_DIR, exist_ok=True)
    path = os.path.join(C.TABLES_DIR, f"phase6_gev{tag}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2,
                  default=lambda o: (None if isinstance(o, float) and not np.isfinite(o)
                                     else str(o)))
    print(f"\n-> {path}")
    print("   出图：python python\\fig4_return_period.py --tag " + (tag or "<空>"))


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
            # ★F12（第三轮 P0-3）：补 **FAR 的 bootstrap 分布**——Table 1 要求
            #   `FAR 0.72 [0.64–0.80]` 这类区间，而旧实现只输出 PR 的 CI。
            #   FAR = 1 − p_fix/p_all：p_all=0 → nan（无定义）；p_fix=0 且 p_all>0 → 1。
            #   FAR 有界（≤1），无 PR 的 inf 问题；仍用次序统计量取分位，并给
            #   `*_fin`（仅有限样本）对照，口径与 PR_lo_fin/PR_hi_fin 一致。
            farb = np.where(ba == 0, np.nan,
                            np.where(bf == 0, 1.0,
                                     1.0 - bf / np.where(ba == 0, 1.0, ba)))
        sv = np.sort(prb[~np.isnan(prb)])
        fin = prb[np.isfinite(prb)]
        lo_f, hi_f = (np.percentile(fin, [CI[0] * 100, CI[1] * 100])
                      if len(fin) else (np.nan, np.nan))
        svf = np.sort(farb[~np.isnan(farb)])
        finf = farb[np.isfinite(farb)]
        lo_ff, hi_ff = (np.percentile(finf, [CI[0] * 100, CI[1] * 100])
                        if len(finf) else (np.nan, np.nan))
        rows.append({"threshold": float(x), "p_all": p_all, "p_fix": p_fix,
                     "PR": pr, "FAR": far,
                     "PR_lo": _emp_quantile(sv, CI[0] * 100),
                     "PR_hi": _emp_quantile(sv, CI[1] * 100),
                     "PR_lo_fin": float(lo_f), "PR_hi_fin": float(hi_f),
                     "FAR_lo": _emp_quantile(svf, CI[0] * 100),
                     "FAR_hi": _emp_quantile(svf, CI[1] * 100),
                     "FAR_lo_fin": float(lo_ff), "FAR_hi_fin": float(hi_ff),
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
    results/phase6审计报告.md §4 与 results/Phase6审计报告.md §2。
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
                      f"P_fix={r.p_fix:.3f} PR={r.PR:.2f} "
                      f"[{r.PR_lo:.2f}–{r.PR_hi:.2f}] FAR={r.FAR:.3f} "
                      f"[{r.FAR_lo:.3f}–{r.FAR_hi:.3f}] "
                      f"(inf {int(r.n_inf)}/{int(r.n_boot)})")
                summary.append({"agg": col, "year": y, "threshold": x,
                                "p_all": r.p_all, "p_fix": r.p_fix,
                                "PR": r.PR, "FAR": r.FAR,
                                "PR_lo": r.PR_lo, "PR_hi": r.PR_hi,
                                "FAR_lo": r.FAR_lo, "FAR_hi": r.FAR_hi,
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
    for name in ("prepare", "pairs", "detect", "compound", "attrib", "gev"):
        q = sp.add_parser(name)
        if name == "detect":
            q.add_argument("--baseline", choices=["own", "xghg", "self", "all"],
                           default="own",
                           help="own=成员自身气候态(v1); xghg=XGHG 合并反事实基准(v2，ALL 也套 XGHG);"
                                " self=各实验用自身气候态(v6 诊断，ALL 用 ALL);"
                                " all=两实验共用 **ALL 实验** 的 1983–2012 气候态(v8，"
                                "论文 Methods 的字面读法)")
            q.add_argument("--thresh-offset", type=float, default=0.0,
                           help="阈值整体加常数 °C（_v9 标定扫描）。θ=0 与 _v5/_v7 的 XGHG 侧"
                                "等价；θ=δ(≈1.13 T2m / 0.80 SST)=_v8 的共用 ALL 基准。")
            q.add_argument("--thresh-offset-t2m", type=float, default=0.0,
                           dest="thresh_offset_t2m",
                           help="**只加在陆地 T2m 阈值上**的附加偏移 °C（_v11；叠加在 "
                                "--thresh-offset 之上）。动机：实测模式暖偏差 β_t2m(地中海框)"
                                "=+1.17 °C 而 β_sst=+0.07 °C ⇒ 『观测阈值』读法要求陆地单独抬高。")
            q.add_argument("--thresh-offset-xghg-t2m", type=float, default=0.0,
                           dest="thresh_offset_xghg_t2m",
                           help="**只加在反事实世界（XGHG 池）陆地阈值**上的偏移 °C（_v12）。"
                                "等价于把参考气候态按权重 w 混合：w=0 各用各的(= _v7/_v10)，"
                                "w=1 完全共用(= _v8 的陆地侧)。需配 --baseline self。")
            q.add_argument("--tag", default="_x2",
                           help="输出事件表后缀（默认 _x2，不覆盖旧 P0 的 _x 产物）")
            q.add_argument("--loo", action="store_true",
                           help="leave-one-out：检测成员 m 时从 XGHG 池中剔除 m 自身"
                                "（仅 --baseline xghg 有效；TECHNICAL_SPEC_PHASE_B 步骤 2b 主口径）")
            q.add_argument("--clim-period", default="", dest="clim_period",
                           help="阈值气候态时段（如 1983-2012 = 论文口径）；留空 = 与事件分析期"
                                "同一 22 年（旧口径 D7.4）。事件仍在 2000-2021 上检测。"
                                "需先用 download_cesm1le.py gdex --years 1983-2012 下好切片。")
        if name != "pairs":
            q.add_argument("--members", type=int, default=C.CESM_P0_MEMBERS,
                           help="成员数（作用于全量 20 人名单，不再被 CESM_P0_MEMBERS 截断）")
        if name in ("compound", "attrib", "gev"):
            q.add_argument("--tag", default="",
                           help="事件文件后缀: ''=v1(own), '_x'=v2(XGHG 基准)")
            q.add_argument("--compound-def", choices=["envelope", "exceed"],
                           default=COMPOUND_DEF, dest="compound_def",
                           help="复合定义: envelope=MHW 包络(论文模型 Methods, 决策 1B, 默认); "
                                "exceed=逐日共超标(观测 Methods L503)")
        if name in ("attrib", "gev"):
            q.add_argument("--boot", choices=["indep", "block"], default=BOOT_MODE,
                           help="bootstrap: indep=模型年独立重采样(论文口径, 默认); "
                                "block=成员内分层+块(附录稳健性)")
            q.add_argument("--n-boot", type=int, default=N_BOOTSTRAP)
            q.add_argument("--quiet", action="store_true")
        if name == "gev":
            q.add_argument("--mapping", choices=["gev", "emp"], default="gev",
                           help="重现期映射内核: gev=GEV MLE + bootstrap（论文 Methods 口径，"
                                "默认）; emp=固定分位经验映射（非参数，_v10 诊断 —— 440 个年值上"
                                "GEV 形状参数会对零膨胀序列跑飞，见 results/复现报告.md §5.2）")
        if name == "attrib":
            q.add_argument("--agg", nargs="+", default=list(AGG_COLS),
                           help=f"聚合口径列，默认 {list(AGG_COLS)}")
            q.add_argument("--thr-step", type=float, default=SWEEP_STEP,
                           help="阈值扫描步长（天）")
        q.set_defaults(func=globals()[f"cmd_{name}"])
    args = p.parse_args()
    args.func(args)


def _force_utf8_stdout():
    """GBK 控制台下打印 `⚠`/`✓` 会抛 UnicodeEncodeError；直接跑时先切成 UTF-8。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


if __name__ == "__main__":
    _force_utf8_stdout()
    main()
