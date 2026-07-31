"""
compound_events.py — 复合事件识别
使用 dict 做 O(1) 查找，避免 DataFrame 逐行过滤。
"""
import os
import numpy as np
import pandas as pd
import xarray as xr
from typing import Optional

from config import COMPOUND_NC, STANDALONE_NC


def is_event_contained(
    thw_start: pd.Timestamp,
    thw_end: pd.Timestamp,
    mhw_start: pd.Timestamp,
    mhw_end: pd.Timestamp,
) -> bool:
    return (mhw_start <= thw_start) and (mhw_end >= thw_end)


def _build_lookup_tables(grid_pairs: pd.DataFrame, mhw_events: pd.DataFrame):
    land_pair_dict = {}
    for row in grid_pairs.itertuples(index=False):
        key = (int(row.land_lat_idx), int(row.land_lon_idx))
        land_pair_dict[key] = (int(row.ocean_lat_idx), int(row.ocean_lon_idx))

    mhw_by_ocean = {}
    for mhw in mhw_events.itertuples(index=False):
        key = (int(mhw.lat_idx), int(mhw.lon_idx))
        if key not in mhw_by_ocean:
            mhw_by_ocean[key] = []
        mhw_by_ocean[key].append({
            'event_start': pd.Timestamp(mhw.event_start),
            'event_end': pd.Timestamp(mhw.event_end),
            'duration': mhw.duration if hasattr(mhw, 'duration') and not np.isnan(mhw.duration) else np.nan,
        })

    return land_pair_dict, mhw_by_ocean


def identify_compound_events(
    mhw_events: pd.DataFrame,
    thw_events: pd.DataFrame,
    grid_pairs: pd.DataFrame,
) -> pd.DataFrame:
    land_pair_dict, mhw_by_ocean = _build_lookup_tables(grid_pairs, mhw_events)

    compound = []

    for thw in thw_events.itertuples(index=False):
        land_key = (int(thw.lat_idx), int(thw.lon_idx))

        if land_key not in land_pair_dict:
            continue

        ocean_lat_idx, ocean_lon_idx = land_pair_dict[land_key]
        ocean_key = (ocean_lat_idx, ocean_lon_idx)

        mhw_list = mhw_by_ocean.get(ocean_key, [])
        if not mhw_list:
            continue

        thw_start = pd.Timestamp(thw.event_start)
        thw_end = pd.Timestamp(thw.event_end)

        for mhw in mhw_list:
            if is_event_contained(thw_start, thw_end, mhw['event_start'], mhw['event_end']):
                compound.append({
                    'thw_start': thw_start,
                    'thw_end': thw_end,
                    'thw_duration': thw.duration,
                    'mhw_start': mhw['event_start'],
                    'mhw_end': mhw['event_end'],
                    'mhw_duration': mhw.get('duration', np.nan),
                    'land_lat_idx': thw.lat_idx,
                    'land_lon_idx': thw.lon_idx,
                    'ocean_lat_idx': ocean_lat_idx,
                    'ocean_lon_idx': ocean_lon_idx,
                    'land_lat': thw.lat,
                    'land_lon': thw.lon,
                })
                break

    return pd.DataFrame(compound)


def compound_events_to_daily(
    compound_events: pd.DataFrame,
    time: xr.DataArray,
    lat: xr.DataArray,
    lon: xr.DataArray,
    output_path: Optional[str] = None,
) -> xr.DataArray:
    nt = len(time)
    nlat = len(lat)
    nlon = len(lon)

    compound_daily = np.zeros((nt, nlat, nlon), dtype=np.int8)

    for event in compound_events.itertuples(index=False):
        time_start = pd.Timestamp(event.thw_start)
        time_end = pd.Timestamp(event.thw_end)

        time_mask = (time >= time_start) & (time <= time_end)
        li = int(event.land_lat_idx)
        lo = int(event.land_lon_idx)

        compound_daily[time_mask, li, lo] = 1

    da = xr.DataArray(
        compound_daily,
        dims=['time', 'lat', 'lon'],
        coords={'time': time, 'lat': lat, 'lon': lon},
        name='compound_mhw_thw',
        attrs={'long_name': 'Compound MHW-THW Day', 'units': '0/1'},
    )

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        da.to_netcdf(output_path)
        print(f"Saved compound events to: {output_path}")

    return da


def calc_standalone_days(
    thw_events: pd.DataFrame,
    mhw_events: pd.DataFrame,
    grid_pairs: pd.DataFrame,
    time: xr.DataArray,
    lat: xr.DataArray,
    lon: xr.DataArray,
    output_path: Optional[str] = None,
) -> xr.DataArray:
    land_pair_dict, mhw_by_ocean = _build_lookup_tables(grid_pairs, mhw_events)

    nt = len(time)
    nlat = len(lat)
    nlon = len(lon)

    standalone_daily = np.zeros((nt, nlat, nlon), dtype=np.int8)
    count_standalone = 0

    for thw in thw_events.itertuples(index=False):
        land_key = (int(thw.lat_idx), int(thw.lon_idx))

        if land_key not in land_pair_dict:
            continue

        ocean_lat_idx, ocean_lon_idx = land_pair_dict[land_key]
        ocean_key = (ocean_lat_idx, ocean_lon_idx)

        mhw_list = mhw_by_ocean.get(ocean_key, [])
        if not mhw_list:
            count_standalone += 1
            time_mask = (time >= pd.Timestamp(thw.event_start)) & (time <= pd.Timestamp(thw.event_end))
            li = int(thw.lat_idx)
            lo = int(thw.lon_idx)
            standalone_daily[time_mask, li, lo] = 1
            continue

        thw_start = pd.Timestamp(thw.event_start)
        thw_end = pd.Timestamp(thw.event_end)

        has_concurrent_mhw = False
        for mhw in mhw_list:
            if not (mhw['event_end'] < thw_start or mhw['event_start'] > thw_end):
                has_concurrent_mhw = True
                break

        if not has_concurrent_mhw:
            time_mask = (time >= thw_start) & (time <= thw_end)
            li = int(thw.lat_idx)
            lo = int(thw.lon_idx)
            standalone_daily[time_mask, li, lo] = 1
            count_standalone += 1

    print(f"Standalone THW events: {count_standalone}")

    da = xr.DataArray(
        standalone_daily,
        dims=['time', 'lat', 'lon'],
        coords={'time': time, 'lat': lat, 'lon': lon},
        name='standalone_thw',
        attrs={'long_name': 'Stand-alone THW Day', 'units': '0/1'},
    )

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        da.to_netcdf(output_path)
        print(f"Saved standalone days to: {output_path}")

    return da
