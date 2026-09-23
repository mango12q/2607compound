"""
compound_events.py — 复合事件识别（逐日共超标定义, 2025-09-18 修订）

2025-09-23 方案 B 定稿：本文件（共超标/L477）用于图1a-i/图1m/图2；
图1j-l 曲线已切换为 MHW 包络口径（L520），见 fig_jkl_mhw_envelope.py。

★ 定义修订记录 ★
  旧实现: compound = THW 事件**整段**被配对海 MHW **完全涵盖**（containment）。
  新实现: compound day = 陆地 THW 跨度日 ∩ 配对海洋 MHW 跨度日（**逐日共超标**）。
    依据: 论文 Methods L477 "Compound ... defined as periods during which both T2m
    and SST **simultaneously exceed** their respective thresholds in adjacent
    coastal grid cells"（逐日共超标）；L520 的 "fully encompasses" 与之冲突。
    实证检验（results/diagnose_compound_definition.py, R 严格检测 + 共超标）:
      - fig1m 共现概率 p50=0.59 / max=0.88  vs 论文 "地中海 0.6-0.8, 西地中海>0.8" ✓
      - fig2c CHR 2023 = 3.44               vs 论文 "2023 峰值 3.5"              ✓
      containment 定义两处均对不上（0.34 / 3.96），故采用共超标定义。

  standalone day = 陆地 THW 日 且 当天配对海格点无 MHW（fig2b: "in the absence
  of simultaneous marine heatwave"，按日扣除；保证 C + S = 全部 THW 日）。

  检测端保持不变: R heatwaveR 严格口径（先连续超标游程>=5 天再桥接 <=2 天间隙，
  与 heatwaveR / marineHeatWaves 两包的默认语义一致，见
  results/exp_smooth_compare.py 与 marineHeatWaves 源码核验）。
"""
import os
import numpy as np
import pandas as pd
import xarray as xr
from typing import Optional

from config import COMPOUND_NC, STANDALONE_NC


def _pair_maps(grid_pairs: pd.DataFrame):
    """land (lat_idx,lon_idx) -> ocean (lat_idx,lon_idx)；并给出带坐标的对表。"""
    land_pair_dict = {}
    for row in grid_pairs.itertuples(index=False):
        land_pair_dict[(int(row.land_lat_idx), int(row.land_lon_idx))] = (
            int(row.ocean_lat_idx), int(row.ocean_lon_idx))
    return land_pair_dict


def _event_daily_mask(events: pd.DataFrame, nt: int, t0: pd.Timestamp) -> np.ndarray:
    """事件跨度(start,end) -> 逐日 bool 掩码（越界自动裁剪）。"""
    m = np.zeros(nt, dtype=bool)
    if len(events) == 0:
        return m
    s = (pd.to_datetime(events.event_start) - t0).dt.days.values
    e = (pd.to_datetime(events.event_end) - t0).dt.days.values
    for i0, i1 in zip(s, e):
        a, b = max(int(i0), 0), min(int(i1), nt - 1)
        if b >= a:
            m[a:b + 1] = True
    return m


def _runs(mask: np.ndarray):
    """bool 掩码 -> (starts, ends) 连续段（含端点, 天索引）。"""
    x = np.concatenate(([0], mask.astype(np.int8), [0]))
    d = np.diff(x)
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
    return starts, ends


def identify_compound_events(
    mhw_events: pd.DataFrame,
    thw_events: pd.DataFrame,
    grid_pairs: pd.DataFrame,
    time: xr.DataArray,
) -> pd.DataFrame:
    """共超标定义的复合日段表（列名与旧 containment 表兼容）。

    返回列: thw_start, thw_end, land_lat_idx, land_lon_idx,
            ocean_lat_idx, ocean_lon_idx, land_lat, land_lon
    其中 [thw_start, thw_end] 是**连续共超标日段**（不再是 THW 事件跨度）。
    """
    t0 = pd.Timestamp(time.values[0])
    nt = len(time)
    land_pair_dict = _pair_maps(grid_pairs)

    # 配对海洋格点的 MHW 逐日掩码
    ocean_mask = {}
    for key, g in mhw_events.groupby(["lat_idx", "lon_idx"]):
        ocean_mask[key] = _event_daily_mask(g, nt, t0)

    # 只保留配对陆地格点上的 THW 事件（1.6M -> 沿海子集）
    kd = pd.DataFrame(list(land_pair_dict.keys()),
                      columns=["lat_idx", "lon_idx"])
    thw_co = thw_events.merge(kd, on=["lat_idx", "lon_idx"], how="inner")

    # 陆地 THW 逐日掩码（按陆点分组）
    thw_by_land = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}

    recs = []
    for land_key, ocean_key in land_pair_dict.items():
        g = thw_by_land.get(land_key)
        if g is None or len(g) == 0:
            continue
        land_m = _event_daily_mask(g, nt, t0)
        om = ocean_mask.get(ocean_key)
        if om is None or not om.any():
            continue
        coex = land_m & om
        if not coex.any():
            continue
        starts, ends = _runs(coex)
        li, lo = land_key
        oi, oj = ocean_key
        # 陆点坐标: 取该组第一行（同一点坐标恒定）
        land_lat = float(g.lat.iloc[0]); land_lon = float(g.lon.iloc[0])
        for a, b in zip(starts, ends):
            recs.append({
                "thw_start": t0 + pd.Timedelta(days=int(a)),
                "thw_end": t0 + pd.Timedelta(days=int(b)),
                "land_lat_idx": li, "land_lon_idx": lo,
                "ocean_lat_idx": oi, "ocean_lon_idx": oj,
                "land_lat": land_lat, "land_lon": land_lon,
            })
    return pd.DataFrame(recs)


def compound_events_to_daily(
    compound_events: pd.DataFrame,
    time: xr.DataArray,
    lat: xr.DataArray,
    lon: xr.DataArray,
    output_path: Optional[str] = None,
) -> xr.DataArray:
    """复合日段表 -> (time, lat, lon) 0/1 日场。段即最大连续段, 直接标跨度。"""
    nt, nlat, nlon = len(time), len(lat), len(lon)
    compound_daily = np.zeros((nt, nlat, nlon), dtype=np.int8)
    t0 = pd.Timestamp(time.values[0])

    starts = (pd.to_datetime(compound_events.thw_start) - t0).dt.days.values
    ends = (pd.to_datetime(compound_events.thw_end) - t0).dt.days.values
    for i, ev in enumerate(compound_events.itertuples(index=False)):
        a, b = max(int(starts[i]), 0), min(int(ends[i]), nt - 1)
        if b >= a:
            compound_daily[a:b + 1, int(ev.land_lat_idx), int(ev.land_lon_idx)] = 1

    da = xr.DataArray(
        compound_daily,
        dims=['time', 'lat', 'lon'],
        coords={'time': time, 'lat': lat, 'lon': lon},
        name='compound_mhw_thw',
        attrs={'long_name': 'Compound MHW-THW Day (daily co-exceedance)',
               'units': '0/1',
               'definition': 'land THW span day AND paired ocean MHW span day'},
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
    """standalone THW 日 = 陆 THW 日 且 当天配对海无 MHW（逐日扣除）。"""
    t0 = pd.Timestamp(time.values[0])
    nt, nlat, nlon = len(time), len(lat), len(lon)
    land_pair_dict = _pair_maps(grid_pairs)

    ocean_mask = {}
    for key, g in mhw_events.groupby(["lat_idx", "lon_idx"]):
        ocean_mask[key] = _event_daily_mask(g, nt, t0)

    kd = pd.DataFrame(list(land_pair_dict.keys()),
                      columns=["lat_idx", "lon_idx"])
    thw_co = thw_events.merge(kd, on=["lat_idx", "lon_idx"], how="inner")
    thw_by_land = {k: g for k, g in thw_co.groupby(["lat_idx", "lon_idx"])}

    standalone_daily = np.zeros((nt, nlat, nlon), dtype=np.int8)
    n_days_total = 0
    for land_key, ocean_key in land_pair_dict.items():
        g = thw_by_land.get(land_key)
        if g is None or len(g) == 0:
            continue
        land_m = _event_daily_mask(g, nt, t0)
        om = ocean_mask.get(ocean_key)
        std = land_m & ~(om if om is not None else np.zeros(nt, dtype=bool))
        if not std.any():
            continue
        li, lo = land_key
        standalone_daily[:, li, lo] = std.astype(np.int8)
        n_days_total += int(std.sum())

    print(f"Standalone THW days: {n_days_total:,} "
          f"(pair-level, {len(thw_by_land)} paired land cells)")

    da = xr.DataArray(
        standalone_daily,
        dims=['time', 'lat', 'lon'],
        coords={'time': time, 'lat': lat, 'lon': lon},
        name='standalone_thw',
        attrs={'long_name': 'Stand-alone THW Day (no simultaneous paired MHW)',
               'units': '0/1'},
    )

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        da.to_netcdf(output_path)
        print(f"Saved standalone days to: {output_path}")

    return da
