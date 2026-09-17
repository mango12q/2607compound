"""
detect_mhw.py — 海洋热浪检测
流式处理方案：逐时间步读取整幅 SST 场，同时为所有格点维护事件状态机。
避免逐格点随机 I/O（24 GB 文件），改为一次顺序扫描。
marineHeatWaves 包仅作单格点验证用（DEPRECATED）。
"""
import os
import numpy as np
import pandas as pd
import xarray as xr
from typing import Optional
from netCDF4 import Dataset

from config import (
    DURATION_THRESH, GAP_TOLERANCE, MHW_EVENTS_CSV,
    OISST_MERGED_FILE, SST_CLIM_FILE,
)


class _EventTracker:
    """逐格点事件状态机，逐时间步 feed 数据。"""
    __slots__ = ('lat_idx', 'lon_idx', 'lat_val', 'lon_val',
                 'time_dt', 'clim_per_doy', 'min_dur', 'max_gap',
                 'in_event', 'start_idx', 'gap_count', 'last_true_idx',
                 'events')

    def __init__(self, lat_idx, lon_idx, lat_val, lon_val,
                 time_dt, clim_per_doy, min_dur, max_gap):
        self.lat_idx = lat_idx
        self.lon_idx = lon_idx
        self.lat_val = lat_val
        self.lon_val = lon_val
        self.time_dt = time_dt
        self.clim_per_doy = clim_per_doy
        self.min_dur = min_dur
        self.max_gap = max_gap
        self.in_event = False
        self.start_idx = 0
        self.gap_count = 0
        self.last_true_idx = -1
        self.events = []

    def feed(self, t_idx, temp, thresh):
        if temp > thresh:
            if not self.in_event:
                self.in_event = True
                self.start_idx = t_idx
                self.gap_count = 0
            else:
                self.gap_count = 0
            self.last_true_idx = t_idx
        else:
            if self.in_event:
                self.gap_count += 1
                if self.gap_count > self.max_gap:
                    end_idx = t_idx - self.gap_count + 1
                    if end_idx - self.start_idx >= self.min_dur:
                        self._emit(self.start_idx, end_idx)
                    self.in_event = False

    def flush(self):
        if self.in_event:
            end_idx = self.last_true_idx + 1
            if end_idx - self.start_idx >= self.min_dur:
                self._emit(self.start_idx, end_idx)
            self.in_event = False

    def _emit(self, start_idx, end_idx):
        self.events.append({
            'event_start': pd.Timestamp(self.time_dt[start_idx]),
            'event_end': pd.Timestamp(self.time_dt[end_idx - 1]),
            'duration': end_idx - start_idx,
            'lat_idx': self.lat_idx,
            'lon_idx': self.lon_idx,
            'lat': self.lat_val,
            'lon': self.lon_val,
        })


def detect_mhw_at_points(
    sst: xr.DataArray,
    ocean_points: list,
    clim_period: tuple = None,
    save_path: Optional[str] = None,
    checkpoint_interval: int = 5000,
) -> pd.DataFrame:
    if save_path is None:
        save_path = MHW_EVENTS_CSV

    print(f"Detecting MHW at {len(ocean_points)} ocean points (streaming)...")

    print(f"Loading SST climatology: {SST_CLIM_FILE}")
    sst_clim = xr.open_dataarray(SST_CLIM_FILE)
    clim_values = sst_clim.values
    lat_vals = sst.lat.values
    lon_vals = sst.lon.values
    time_index = pd.DatetimeIndex(sst.time.values)
    time_doy = time_index.dayofyear.values
    time_dt = time_index.to_numpy().astype('datetime64[D]')
    ntime = len(time_index)

    partial_path = save_path + '.partial.csv'
    if os.path.exists(save_path):
        print(f"Loading existing results: {save_path}")
        combined = pd.read_csv(save_path)
        print(f"  Loaded {len(combined)} events")
        sst_clim.close()
        return combined

    if os.path.exists(partial_path):
        try:
            existing = pd.read_csv(partial_path)
            if not existing.empty and 'lat_idx' in existing.columns:
                done_points = set(zip(
                    existing['lat_idx'].astype(int).tolist(),
                    existing['lon_idx'].astype(int).tolist(),
                ))
                remaining = [(li, lo) for li, lo in ocean_points if (li, lo) not in done_points]
                all_events = existing.to_dict('records')
                print(f"Resuming from checkpoint: {len(done_points)} points done, {len(remaining)} remaining")
                if not remaining:
                    combined = existing
                    if save_path and os.path.exists(partial_path):
                        os.remove(partial_path)
                    sst_clim.close()
                    return combined
                return detect_mhw_at_points(sst, remaining, None, save_path, checkpoint_interval)
        except Exception:
            pass

    print(f"Initializing {len(ocean_points)} trackers...")
    trackers = {}
    for lat_idx, lon_idx in ocean_points:
        clim_per_doy = clim_values[:, lat_idx, lon_idx]
        trackers[(lat_idx, lon_idx)] = _EventTracker(
            lat_idx, lon_idx,
            float(lat_vals[lat_idx]), float(lon_vals[lon_idx]),
            time_dt, clim_per_doy,
            DURATION_THRESH, GAP_TOLERANCE,
        )

    print(f"Streaming {ntime} time steps from {OISST_MERGED_FILE}...")
    tracker_list = list(trackers.values())
    nc = Dataset(OISST_MERGED_FILE, 'r')
    sst_var = nc.variables['sst']

    last_report = 0
    for t_idx in range(ntime):
        sst_slice = sst_var[t_idx, :, :].astype(np.float64)
        doy = time_doy[t_idx]
        safe_doy = min(doy, clim_values.shape[0])
        clim_slice = clim_values[safe_doy - 1]

        for trk in tracker_list:
            trk.feed(t_idx, sst_slice[trk.lat_idx, trk.lon_idx],
                     clim_slice[trk.lat_idx, trk.lon_idx])

        if t_idx - last_report >= 1000:
            print(f"  Time step {t_idx}/{ntime} ({100*t_idx//ntime}%)")
            last_report = t_idx

    nc.close()

    print("  Flushing remaining events...")
    for trk in trackers.values():
        trk.flush()

    all_events = []
    for trk in trackers.values():
        all_events.extend(trk.events)

    if all_events:
        combined = pd.DataFrame(all_events)
    else:
        combined = pd.DataFrame()

    print(f"Total MHW events detected: {len(combined)}")
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        combined.to_csv(save_path, index=False)
        print(f"Saved to: {save_path}")
        if os.path.exists(partial_path):
            os.remove(partial_path)

    sst_clim.close()
    return combined


def detect_mhw_all_grids(
    sst: xr.DataArray,
    clim_period: tuple = None,
    save_path: Optional[str] = None,
    checkpoint_interval: int = 5000,
) -> pd.DataFrame:
    if save_path is None:
        save_path = MHW_EVENTS_CSV

    total_lat = len(sst.lat)
    total_lon = len(sst.lon)
    print(f"Detecting MHW on {total_lat}x{total_lon} grid (threshold method)...")

    print("Computing valid ocean mask (single time slice)...")
    valid_mask = sst.isel(time=0).notnull().values

    valid_points = [(li, lo) for li in range(total_lat) for lo in range(total_lon) if valid_mask[li, lo]]
    print(f"Valid ocean points: {len(valid_points)} / {total_lat * total_lon}")

    return detect_mhw_at_points(
        sst, valid_points, clim_period, save_path, checkpoint_interval,
    )


# ──────────────────────────────────────────────
# marineHeatWaves 包（单格点验证用，DEPRECATED）
# ──────────────────────────────────────────────

def _make_time_array(time_values):
    return np.array([pd.Timestamp(ts).toordinal() for ts in time_values.astype('datetime64[D]')])


def detect_mhw_grid(
    sst: xr.DataArray,
    clim_period: tuple = None,
    duration: int = DURATION_THRESH,
    gap: int = GAP_TOLERANCE,
) -> pd.DataFrame:
    """DEPRECATED: 使用 marineHeatWaves 包检测单个格点的 MHW（内部计算 climatology）。
    仅用于单格点验证，run_all.py 不再调用。
    """
    from marineHeatWaves import detect as mhw_detect

    temp = sst.values.astype(np.float64)
    t = _make_time_array(sst.time.values)

    start_year, end_year = clim_period or (1983, 2012)
    result = mhw_detect(
        t, temp,
        climatologyPeriod=[start_year, end_year],
        pctile=90,
        minDuration=duration,
        maxGap=gap,
        smoothPercentile=False,
    )

    events_dict = result[0]
    n_events = events_dict.get('n_events', 0)
    if n_events == 0:
        return pd.DataFrame()

    events = pd.DataFrame(events_dict)
    events = events.rename(columns={'date_start': 'event_start', 'date_end': 'event_end'})
    events['lat'] = float(sst.lat.values) if 'lat' in sst.coords else np.nan
    events['lon'] = float(sst.lon.values) if 'lon' in sst.coords else np.nan
    return events
