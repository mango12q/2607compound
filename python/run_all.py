#!/usr/bin/env python
"""
run_all.py — 一键运行入口
Phase 0: 数据预处理（合并 OISST / E-OBS）
Phase 1: 热浪检测（MHW + THW）
Phase 2: 沿海配对 + 复合事件识别
Phase 3: CHR / 共现概率计算
"""
import os
import sys
import time
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
    CLIM_PERIOD,
    INTERMEDIATE_DIR, FIGURES_DIR, TABLES_DIR, LOGS_DIR,
)

import preprocess
import load_data
import detect_mhw
import detect_thw_wrapper
import coastal_mask
import compound_events
import calc_chr


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

    if os.path.exists(MHW_EVENTS_CSV):
        print(f"MHW events already exist: {MHW_EVENTS_CSV}")
        mhw_df = pd.read_csv(MHW_EVENTS_CSV)
        print(f"  Loaded {len(mhw_df)} events from CSV")
    else:
        t0 = time.time()
        mhw_df = detect_mhw.detect_mhw_at_points(sst, ocean_points, clim_period=CLIM_PERIOD)
        elapsed = time.time() - t0
        print(f"MHW detection completed in {elapsed/60:.1f} minutes")

    print("\n[1c] Detecting Terrestrial Heatwaves (pure Python)...")
    if os.path.exists(THW_EVENTS_CSV):
        print(f"THW events already exist: {THW_EVENTS_CSV}")
        thw_df = pd.read_csv(THW_EVENTS_CSV)
        print(f"  Loaded {len(thw_df)} events from CSV")
    else:
        t0 = time.time()
        thw_df = detect_thw_wrapper.detect_thw(clim_period=CLIM_PERIOD)
        elapsed = time.time() - t0
        print(f"THW detection completed in {elapsed/60:.1f} minutes")

    return data, mhw_df, thw_df, pairs_df


def phase2_compound(data, mhw_df, thw_df, pairs_df):
    print("\n" + "=" * 60)
    print("PHASE 2: Compound Events")
    print("=" * 60)

    eobs = data['eobs']
    sst = data['oisst']['SST']

    print(f"Using {len(pairs_df)} pre-computed coastal pairs")

    print("\n[2a] Identifying compound events...")
    t0 = time.time()
    compound_df = compound_events.identify_compound_events(mhw_df, thw_df, pairs_df)
    elapsed = time.time() - t0
    print(f"Found {len(compound_df)} compound events in {elapsed:.1f} seconds")

    print("\n[2b] Converting to daily fields...")
    time_coord = eobs['T2m'].time
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
    print("  2. Use export_for_matlab.py to prepare .mat files (to be written)")
    print("  3. Generate figures with MATLAB scripts (to be written)")


if __name__ == "__main__":
    main()
