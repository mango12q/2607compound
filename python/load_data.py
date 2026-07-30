"""
load_data.py — 数据加载与预处理
加载合并后的 OISST / E-OBS，计算气候学阈值。
支持两种模式：
1. 合并文件存在时直接加载
2. 合并文件不存在时使用原始文件（OISST 用 open_mfdataset 懒加载）
"""
import os
import glob
import numpy as np
import xarray as xr
from typing import Optional

from config import (
    OISST_MERGED_FILE, OISST_RAW_PATTERN,
    EOBS_MERGED_FILE,
    SST_CLIM_FILE, T2M_CLIM_FILE,
    CLIM_PERIOD, PERCENTILE,
)


def load_oisst(filepath: Optional[str] = None) -> xr.Dataset:
    if filepath is None:
        filepath = OISST_MERGED_FILE

    if os.path.exists(filepath):
        print(f"Loading OISST (merged): {filepath}")
        ds = xr.open_dataset(filepath)
    else:
        print(f"Loading OISST (raw files): {OISST_RAW_PATTERN}")
        files = sorted(glob.glob(OISST_RAW_PATTERN))
        if not files:
            raise FileNotFoundError(
                f"No OISST files found at {OISST_RAW_PATTERN}\n"
                f"Run preprocess.merge_oisst() first, or ensure raw files exist."
            )
        ds = xr.open_mfdataset(
            files,
            parallel=True,
            chunks={'time': 365},
            combine='by_coords',
            engine='netcdf4',
        )
        if 'zlev' in ds.dims:
            ds = ds.squeeze('zlev', drop=True)

    if 'sst' in ds.data_vars:
        ds = ds.rename({'sst': 'SST'})

    ds['SST'].attrs['units'] = 'degC'
    ds['SST'].attrs['long_name'] = 'Sea Surface Temperature'

    print(f"  Shape: {dict(ds.sizes)}")
    print(f"  Time: {ds.time.values[0]} to {ds.time.values[-1]}")
    return ds


def load_eobs(filepath: Optional[str] = None) -> xr.Dataset:
    if filepath is None:
        filepath = EOBS_MERGED_FILE

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"E-OBS merged file not found: {filepath}\n"
            f"Run preprocess.merge_eobs() first."
        )

    print(f"Loading E-OBS: {filepath}")
    ds = xr.open_dataset(filepath)

    if 'T2m' in ds.data_vars:
        ds['T2m'].attrs['units'] = 'degC'
        ds['T2m'].attrs['long_name'] = '2m Temperature'

    print(f"  Shape: {dict(ds.sizes)}")
    print(f"  Time: {ds.time.values[0]} to {ds.time.values[-1]}")
    return ds


def calc_climatology(
    da: xr.DataArray,
    clim_period: tuple = CLIM_PERIOD,
    output_path: Optional[str] = None,
) -> xr.DataArray:
    start_year, end_year = clim_period

    clim_data = da.sel(time=slice(f"{start_year}-01-01", f"{end_year}-12-31"))
    print(f"Calculating {PERCENTILE}th percentile climatology ({start_year}-{end_year})...")
    print(f"  Climatology data shape: {dict(clim_data.sizes)}")

    print("  Computing groupby quantile (this may take a few minutes)...")
    clim = clim_data.groupby('time.dayofyear').quantile(q=PERCENTILE / 100.0)
    clim = clim.rename({'dayofyear': 'time'})

    clim.attrs['clim_period'] = f"{start_year}-{end_year}"
    clim.attrs['percentile'] = PERCENTILE

    if output_path is not None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        print(f"  Writing to: {output_path}")
        clim.to_netcdf(output_path)
        print(f"  Saved climatology to: {output_path}")

    return clim


def load_all():
    print("=" * 60)
    print("Loading all observational data...")
    print("=" * 60)

    oisst = load_oisst()
    eobs = load_eobs()

    print("\nCalculating climatologies...")
    if os.path.exists(SST_CLIM_FILE):
        print(f"Loading existing SST climatology: {SST_CLIM_FILE}")
        sst_clim = xr.open_dataarray(SST_CLIM_FILE)
    else:
        sst_clim = calc_climatology(oisst['SST'], output_path=SST_CLIM_FILE)

    if os.path.exists(T2M_CLIM_FILE):
        print(f"Loading existing T2m climatology: {T2M_CLIM_FILE}")
        t2m_clim = xr.open_dataarray(T2M_CLIM_FILE)
    else:
        t2m_clim = calc_climatology(eobs['T2m'], output_path=T2M_CLIM_FILE)

    print("\nDone.")
    return {
        'oisst': oisst,
        'eobs': eobs,
        'sst_clim': sst_clim,
        't2m_clim': t2m_clim,
    }
