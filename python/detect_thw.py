"""
detect_thw.py — 陆地热浪检测（纯 Python 实现）
替代 R heatwaveR 包，避免 R 依赖和并行序列化问题。

算法：基于日阈值（90th percentile）检测，参考期 1983-2012。
  1. 加载预计算气候学阈值（由 load_data.calc_climatology 生成）
  2. 逐格点比较温度与阈值，检测超阈值持续 >= minDuration 天的事件
  3. maxGap 天内允许中断不拆分为两个事件
"""
import os
import numpy as np
import pandas as pd
import xarray as xr
from typing import Optional

from config import (
    EOBS_MERGED_FILE, THW_EVENTS_CSV,
    T2M_CLIM_FILE,
    CLIM_PERIOD, PERCENTILE, DURATION_THRESH, GAP_TOLERANCE,
)
from detect_events import detect_events_from_exceed


def detect_thw_grid(
    t2m_ts, doy_thresh, time_index, lat_val, lon_val,
    lat_idx, lon_idx, min_duration, max_gap,
):
    valid = ~np.isnan(t2m_ts)
    if valid.sum() < 730:
        return []

    safe_doy = np.clip(time_index.dayofyear, 1, len(doy_thresh))
    exceed = t2m_ts > doy_thresh[safe_doy - 1]
    events = detect_events_from_exceed(exceed, min_duration, max_gap)

    result = []
    for start_idx, end_idx in events:
        result.append({
            'event_start': time_index[start_idx],
            'event_end': time_index[end_idx - 1],
            'duration': end_idx - start_idx,
            'lat_idx': int(lat_idx),
            'lon_idx': int(lon_idx),
            'lat': lat_val,
            'lon': lon_val,
        })
    return result


def _process_land_point(li, lo, t2m_values, t2m_clim_values,
                        lat_vals, lon_vals, time_index,
                        min_duration, max_gap):
    try:
        ts = t2m_values[:, li, lo]
        doy_thresh = t2m_clim_values[:, li, lo]
        lat_val = float(lat_vals[li])
        lon_val = float(lon_vals[lo])
        return detect_thw_grid(
            ts, doy_thresh, time_index, lat_val, lon_val,
            li, lo, min_duration, max_gap,
        )
    except Exception as e:
        print(f"  Warning: THW failed at lat={li}, lon={lo}: {e}")
        return []


def detect_thw_all_points(
    t2m: xr.DataArray,
    time_index: pd.DatetimeIndex,
    land_mask: np.ndarray,
    clim_start: int = CLIM_PERIOD[0],
    clim_end: int = CLIM_PERIOD[1],
    pctile: int = PERCENTILE,
    min_duration: int = DURATION_THRESH,
    max_gap: int = GAP_TOLERANCE,
    save_path: Optional[str] = None,
    checkpoint_interval: int = 5000,
) -> pd.DataFrame:
    if save_path is None:
        save_path = THW_EVENTS_CSV

    nlat = len(t2m.lat)
    nlon = len(t2m.lon)

    land_points = [(i, j) for i in range(nlat) for j in range(nlon) if land_mask[i, j]]
    print(f"Detecting THW on {nlat}x{nlon} grid, {len(land_points)} land points...")

    print(f"Loading T2m climatology: {T2M_CLIM_FILE}")
    t2m_clim = xr.open_dataarray(T2M_CLIM_FILE)

    t2m_values = t2m.values
    t2m_clim_values = t2m_clim.values
    lat_vals = t2m.lat.values
    lon_vals = t2m.lon.values

    partial_path = save_path + '.partial.csv'
    processed = set()
    all_events = []

    if os.path.exists(partial_path):
        try:
            existing = pd.read_csv(partial_path)
            if not existing.empty and 'lat_idx' in existing.columns:
                all_events = existing.to_dict('records')
                processed = set(zip(
                    existing['lat_idx'].astype(int).tolist(),
                    existing['lon_idx'].astype(int).tolist(),
                ))
                print(f"Resuming from checkpoint: {len(processed)} points already processed")
        except Exception as e:
            print(f"Warning: could not load checkpoint, starting fresh: {e}")

    remaining = [(li, lo) for li, lo in land_points if (li, lo) not in processed]
    total = len(remaining)
    print(f"Processing {total} points serially...")

    for count, (li, lo) in enumerate(remaining):
        evts = _process_land_point(
            li, lo, t2m_values, t2m_clim_values, lat_vals, lon_vals,
            time_index, min_duration, max_gap,
        )
        all_events.extend(evts)
        if (count + 1) % checkpoint_interval == 0:
            print(f"  Progress: {count + 1}/{total} ({100*(count+1)/total:.1f}%)")
            if partial_path:
                pd.DataFrame(all_events).to_csv(partial_path, index=False)

    if all_events:
        combined = pd.DataFrame(all_events)
    else:
        combined = pd.DataFrame()

    print(f"Total THW events detected: {len(combined)}")
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        combined.to_csv(save_path, index=False)
        print(f"Saved to: {save_path}")
        if os.path.exists(partial_path):
            os.remove(partial_path)

    t2m_clim.close()
    return combined
