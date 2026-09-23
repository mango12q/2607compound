#!/usr/bin/env python
"""
run_all.py — 一键运行入口
Phase 0: 数据预处理（合并 OISST / E-OBS）
Phase 1: 热浪检测（MHW + THW）
Phase 2: 沿海配对 + 复合事件识别
Phase 3: CHR / 共现概率计算

⚠️ 检测链路（2026-09-23 修正）：
    本脚本原经 `detect_thw_wrapper` → `python/detect_thw.R`，而该脚本已被标注为
    "有 return-in-tryCatch 静默吞错、仅存档勿用"。现改为统一调用
    `python/detect_events.R`（海陆同一份代码的正式链路）。

    缓存行为：若 config.MHW_EVENTS_CSV / THW_EVENTS_CSV 已存在则直接读，不重跑。
    如需强制重检：删除对应 CSV，或直接跑 `results/run_detection_R.py ocean|land`。
"""
import os
import sys
import time
import subprocess
import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    OISST_MERGED_FILE, EOBS_MERGED_FILE,
    SST_CLIM_FILE, T2M_CLIM_FILE,
    MHW_EVENTS_CSV, THW_EVENTS_CSV,
    COASTAL_PAIRS_CSV,
    COMPOUND_NC, STANDALONE_NC,
    ANNUAL_COMPOUND_NC, ANNUAL_STANDALONE_NC, ANNUAL_THW_NC,
    CHR_ANNUAL_NC, COOCCURRENCE_PROB_NC,
    CLIM_PERIOD, RSCRIPT_PATH, R_WORKERS,
    INTERMEDIATE_DIR, FIGURES_DIR, TABLES_DIR, LOGS_DIR,
)

import preprocess
import load_data
import detect_mhw
import coastal_mask
import compound_events
import calc_chr

# 正式检测链路（海陆同一份 R 代码）
DETECT_EVENTS_R = os.path.join(os.path.dirname(__file__), "detect_events.R")
OISST_CLIP = os.path.join(os.path.dirname(EOBS_MERGED_FILE), "..", "OISST",
                          "oisst_v2.1_eur_1983_2023.nc")
DOMAINS_CSV = os.path.join(INTERMEDIATE_DIR, "domains_ocean_pairs.csv")
OISST_CLIP = os.path.normpath(OISST_CLIP)


def globalize_mhw_idx(src_csv, dst_csv):
    """调用 results/globalize_mhw_idx.py，把裁剪网格索引换算回全球 OISST 索引。"""
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "results", "globalize_mhw_idx.py")
    if not os.path.exists(script):
        raise FileNotFoundError(f"缺索引换算脚本: {script}")
    cmd = [sys.executable, script, src_csv, dst_csv]
    print("  RUN:", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    print("\n".join(p.stdout.splitlines()[-8:]))
    if p.returncode != 0:
        print(p.stderr[-2000:])
        raise RuntimeError("globalize_mhw_idx.py failed")
    if not os.path.exists(dst_csv):
        raise RuntimeError(f"换算未产出 {dst_csv}")
    return dst_csv


def detect_with_R(kind, nc_file, varname, out_csv, domains="-"):  # noqa: D401
    """用正式链路 detect_events.R 跑一次检测。

    kind: 'ocean' | 'land'（仅用于日志与工作目录命名）
    """
    if not os.path.exists(nc_file):
        raise FileNotFoundError(f"{kind}: 输入不存在 {nc_file}")
    if domains != "-" and not os.path.exists(domains):
        raise FileNotFoundError(f"{kind}: 缺 domains 文件 {domains}")
    work = os.path.join(INTERMEDIATE_DIR, "_detect_R", kind)
    cmd = [RSCRIPT_PATH, DETECT_EVENTS_R, nc_file, varname, out_csv,
           str(CLIM_PERIOD[0]), str(CLIM_PERIOD[1]), domains,
           "5", "2", str(R_WORKERS), work]
    print("  RUN:", " ".join(cmd))
    os.makedirs(os.path.dirname(os.path.join(LOGS_DIR, "x")), exist_ok=True)
    log = os.path.join(LOGS_DIR, f"detect_R_{kind}.log")
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)
    print(f"  exit={p.returncode}  elapsed={(time.time() - t0) / 60:.1f} min  log={log}")
    if p.returncode != 0:
        with open(log, encoding="utf-8") as fh:
            print("\n".join(fh.read().splitlines()[-20:]))
        raise RuntimeError(f"detect_events.R failed for {kind}")
    return out_csv


def phase0_preprocess():
    print("\n" + "=" * 60)
    print("PHASE 0: Data Preprocessing")
    print("=" * 60)

    if os.path.exists(OISST_MERGED_FILE):
        print(f"OISST merged file already exists: {OISST_MERGED_FILE}")
        size_gb = os.path.getsize(OISST_MERGED_FILE) / 1e9
        print(f"  Size: {size_gb:.2f} GB")
    else:
        t0 = time.time()
        preprocess.merge_oisst()
        elapsed = time.time() - t0
        print(f"OISST merge completed in {elapsed/60:.1f} minutes")

    if os.path.exists(EOBS_MERGED_FILE):
        print(f"E-OBS merged file already exists: {EOBS_MERGED_FILE}")
        size_gb = os.path.getsize(EOBS_MERGED_FILE) / 1e9
        print(f"  Size: {size_gb:.2f} GB")
    else:
        t0 = time.time()
        preprocess.merge_eobs()
        elapsed = time.time() - t0
        print(f"E-OBS merge completed in {elapsed/60:.1f} minutes")


def phase1_detection():
    print("\n" + "=" * 60)
    print("PHASE 1: Heatwave Detection")
    print("=" * 60)

    data = load_data.load_all()

    oisst_ds = data['oisst']
    eobs = data['eobs']
    sst = oisst_ds['SST']
    t2m = eobs['T2m']

    print("\n[1a] Building land/ocean masks and finding coastal pairs...")
    land_mask = coastal_mask.build_land_mask(eobs)
    ocean_mask = coastal_mask.build_ocean_mask(sst)
    print(f"  Land mask: {int(np.sum(land_mask.values))} land points")
    print(f"  Ocean mask: {int(np.sum(ocean_mask.values))} ocean points")

    if os.path.exists(COASTAL_PAIRS_CSV):
        print(f"Coastal pairs already exist: {COASTAL_PAIRS_CSV}")
        pairs_df = pd.read_csv(COASTAL_PAIRS_CSV)
        print(f"  Loaded {len(pairs_df)} pairs from CSV")
    else:
        t0 = time.time()
        pairs_df = coastal_mask.find_coastal_grid_pairs(
            land_mask, ocean_mask, save_path=COASTAL_PAIRS_CSV
        )
        elapsed = time.time() - t0
        print(f"Coastal pair search completed in {elapsed/60:.1f} minutes")

    ocean_points = list(set(zip(
        pairs_df['ocean_lat_idx'].astype(int).tolist(),
        pairs_df['ocean_lon_idx'].astype(int).tolist(),
    )))
    print(f"  Unique ocean points to detect: {len(ocean_points)}")

    print("\n[1b] Marine Heatwaves (R detect_events.R + 全球索引换算)...")
    if os.path.exists(MHW_EVENTS_CSV):
        print(f"MHW events already exist: {MHW_EVENTS_CSV}")
        mhw_df = pd.read_csv(MHW_EVENTS_CSV)
        print(f"  Loaded {len(mhw_df)} events from CSV")
    else:
        t0 = time.time()
        # ⚠️ 海洋检测必须走两步：
        #   ① detect_events.R 在**欧洲裁剪件**上跑，输出的是裁剪网格的局部 0-based 索引
        #      → results/intermediate/mhw_events_R.csv
        #   ② globalize_mhw_idx.py 把局部索引换算回**全球 OISST 720x1440** 索引
        #      → MHW_EVENTS_CSV (mhw_events_R_global.csv)
        #   跳过 ② 会让下游 compound 的整型索引匹配全部落空（Phase 2 归零），
        #   且不会报错——属静默错位，务必保持两步。
        clip_csv = os.path.join(INTERMEDIATE_DIR, "mhw_events_R.csv")
        detect_with_R("ocean", OISST_CLIP, "sst", clip_csv, DOMAINS_CSV)
        globalize_mhw_idx(clip_csv, MHW_EVENTS_CSV)
        mhw_df = pd.read_csv(MHW_EVENTS_CSV)
        print(f"MHW detection completed in {(time.time() - t0) / 60:.1f} minutes")

    print("\n[1c] Terrestrial Heatwaves (R detect_events.R)...")
    if os.path.exists(THW_EVENTS_CSV):
        print(f"THW events already exist: {THW_EVENTS_CSV}")
        thw_df = pd.read_csv(THW_EVENTS_CSV)
        print(f"  Loaded {len(thw_df)} events from CSV")
    else:
        t0 = time.time()
        # 陆地直接写 THW_EVENTS_CSV：E-OBS 网格即下游使用的网格，无需索引换算
        detect_with_R("land", EOBS_MERGED_FILE, "T2m", THW_EVENTS_CSV, "-")
        thw_df = pd.read_csv(THW_EVENTS_CSV)
        print(f"THW detection completed in {(time.time() - t0) / 60:.1f} minutes")

    return data, mhw_df, thw_df, pairs_df


def phase2_compound(data, mhw_df, thw_df, pairs_df):
    print("\n" + "=" * 60)
    print("PHASE 2: Compound Events")
    print("=" * 60)

    eobs = data['eobs']
    sst = data['oisst']['SST']

    print(f"Using {len(pairs_df)} pre-computed coastal pairs")

    print("\n[2a] Identifying compound events...")
    time_coord = eobs['T2m'].time
    t0 = time.time()
    compound_df = compound_events.identify_compound_events(
        mhw_df, thw_df, pairs_df, time_coord)
    elapsed = time.time() - t0
    print(f"Found {len(compound_df)} compound day-segments in {elapsed:.1f} seconds")

    print("\n[2b] Converting to daily fields...")
    lat_coord = eobs['T2m'].lat
    lon_coord = eobs['T2m'].lon

    compound_daily = compound_events.compound_events_to_daily(
        compound_df, time_coord, lat_coord, lon_coord, output_path=COMPOUND_NC
    )

    standalone_daily = compound_events.calc_standalone_days(
        thw_df, mhw_df, pairs_df, time_coord, lat_coord, lon_coord,
        output_path=STANDALONE_NC,
    )

    return compound_daily, standalone_daily, pairs_df


def phase3_metrics(compound_daily, standalone_daily):
    print("\n" + "=" * 60)
    print("PHASE 3: Annual Metrics (CHR / Co-occurrence)")
    print("=" * 60)

    all_thw_daily = xr.where(compound_daily > 0, 1, standalone_daily).astype(np.int8)

    print("\n[3a] Computing annual day counts...")
    annual_compound = calc_chr.calc_annual_days(compound_daily, output_path=ANNUAL_COMPOUND_NC)
    annual_standalone = calc_chr.calc_annual_days(standalone_daily, output_path=ANNUAL_STANDALONE_NC)
    annual_thw = calc_chr.calc_annual_days(all_thw_daily, output_path=ANNUAL_THW_NC)

    print("\n[3b] Computing CHR...")
    CHR = calc_chr.calc_CHR(annual_compound, annual_standalone, output_path=CHR_ANNUAL_NC)

    print("\n[3c] Computing co-occurrence probability...")
    coocc = calc_chr.calc_cooccurrence_prob(annual_compound, annual_thw, output_path=COOCCURRENCE_PROB_NC)

    print("\n[3d] Spatial mean time series (Europe coastal):")
    chr_ts = calc_chr.calc_spatial_mean(CHR, lat_range=(30, 66), lon_range=(-10, 42))
    print(f"  CHR mean over Europe: {float(np.nanmean(CHR.values)):.3f}")
    print(f"  CHR max over Europe: {float(np.nanmax(CHR.values)):.3f}")
    # Note: spatial mean uses np.nanmean, so inland NaN values (no coastal pairs) are excluded

    return {
        'annual_compound': annual_compound,
        'annual_standalone': annual_standalone,
        'annual_thw': annual_thw,
        'CHR': CHR,
        'cooccurrence_prob': coocc,
    }


def main():
    print("=" * 60)
    print("Compound Coastal Marine-Terrestrial Heatwaves")
    print("Paper Reproduction Pipeline")
    print("=" * 60)
    t_start = time.time()

    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(TABLES_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    phase0_preprocess()

    data, mhw_df, thw_df, pairs_df = phase1_detection()

    compound_daily, standalone_daily, pairs_df = phase2_compound(data, mhw_df, thw_df, pairs_df)

    results = phase3_metrics(compound_daily, standalone_daily)

    t_total = time.time() - t_start
    print("\n" + "=" * 60)
    print(f"ALL PHASES COMPLETED in {t_total/60:.1f} minutes ({t_total/3600:.2f} hours)")
    print("=" * 60)
    print(f"Results saved to: {INTERMEDIATE_DIR}")
    print(f"Figures output:   {FIGURES_DIR}")
    print(f"Tables output:    {TABLES_DIR}")
    print("\nNext steps:")
    print("  1. Run verify_data.py to check all output files")
    print("  2. Generate figures: python figures.py  (+ fig_jkl_mhw_envelope.py for S2)")
    print("  3. Phase 5 (Fig.5-6): needs ERA5 tmax + sp 0.25 + OAFlux "
          "-> run_phase5_downloads.bat")
    print("  4. Phase 6 (Fig.3-4): python phase6_cesm.py prepare|pairs|detect|compound|attrib")


if __name__ == "__main__":
    main()
