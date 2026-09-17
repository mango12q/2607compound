"""
detect_thw_wrapper.py — 陆地热浪检测入口
加载 E-OBS 数据、构建掩码，调用 detect_thw 核心逻辑。
"""
import os
import numpy as np
import pandas as pd
import xarray as xr
from typing import Optional

from config import (
    EOBS_MERGED_FILE, THW_EVENTS_CSV,
    CLIM_PERIOD,
)
import detect_thw as _thw_mod


def detect_thw(
    eobs_filepath: Optional[str] = None,
    output_csv: Optional[str] = None,
    clim_period: tuple = CLIM_PERIOD,
) -> pd.DataFrame:
    if eobs_filepath is None:
        eobs_filepath = EOBS_MERGED_FILE
    if output_csv is None:
        output_csv = THW_EVENTS_CSV

    if not os.path.exists(eobs_filepath):
        raise FileNotFoundError(
            f"E-OBS file not found: {eobs_filepath}\n"
            f"Run preprocess.merge_eobs() first."
        )

    print(f"Loading E-OBS for THW detection: {eobs_filepath}")
    ds = xr.open_dataset(eobs_filepath)
    t2m = ds['T2m']

    time_index = pd.DatetimeIndex(t2m.time.values)

    land_mask = t2m.notnull().any(dim='time').values

    print(f"Data shape: {len(time_index)} time x {len(t2m.lat)} lat x {len(t2m.lon)} lon")
    print(f"Land points: {int(land_mask.sum())}")

    thw_df = _thw_mod.detect_thw_all_points(
        t2m, time_index, land_mask,
        clim_start=clim_period[0],
        clim_end=clim_period[1],
        save_path=output_csv,
    )

    ds.close()
    return thw_df


def load_thw_events(csv_path: Optional[str] = None) -> pd.DataFrame:
    if csv_path is None:
        csv_path = THW_EVENTS_CSV

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"THW events CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    if 'event_start' in df.columns:
        df['event_start'] = pd.to_datetime(df['event_start'])
    if 'event_end' in df.columns:
        df['event_end'] = pd.to_datetime(df['event_end'])

    print(f"Loaded {len(df)} THW events from {csv_path}")
    return df
