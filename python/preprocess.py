"""
preprocess.py — 原始数据合并为规范文件
- merge_oisst(): 15340 个日文件 → 单文件 oisst_v2.1_1982_2023.nc
- merge_eobs(): 三个版本文件 → 合并 + 裁剪 → EOBS_tg_1983_2023.nc
"""
import os
import glob
import xarray as xr
import numpy as np
from config import (
    OISST_RAW_PATTERN, OISST_MERGED_FILE,
    EOBS_RAW_FILES, EOBS_MERGED_FILE,
    EOBS_VERSION_NOTE,
)


def merge_oisst(output_path=None):
    if output_path is None:
        output_path = OISST_MERGED_FILE

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Scanning OISST raw files: {OISST_RAW_PATTERN}")
    files = sorted(glob.glob(OISST_RAW_PATTERN))
    print(f"Found {len(files)} files")

    if not files:
        raise FileNotFoundError(f"No OISST files found at {OISST_RAW_PATTERN}")

    print("Opening with xarray (parallel=False, nested combine)...")
    ds = xr.open_mfdataset(
        files,
        parallel=True,
        chunks={'time': 365},
        combine='nested',
        concat_dim='time',
        engine='netcdf4',
    )

    print(f"Combined dataset shape: {dict(ds.sizes)}")
    print(f"Variables: {list(ds.data_vars)}")

    if 'zlev' in ds.dims:
        ds = ds.squeeze('zlev', drop=True)
        print("Squeezed zlev dimension")

    ds['sst'].attrs['units'] = 'degC'
    ds['sst'].attrs['long_name'] = 'Sea Surface Temperature'

    print(f"Writing to: {output_path}")
    print("  (no compression for speed; individual files already compressed)")
    ds.to_netcdf(output_path, engine='netcdf4')
    ds.close()

    size_gb = os.path.getsize(output_path) / 1e9
    print(f"Done. Output size: {size_gb:.2f} GB")


def merge_eobs(output_path=None):
    if output_path is None:
        output_path = EOBS_MERGED_FILE

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print("Merging E-OBS files:")
    for f in EOBS_RAW_FILES:
        exists = os.path.exists(f)
        size = os.path.getsize(f) / 1e6 if exists else 0
        print(f"  {os.path.basename(f)}: {'OK' if exists else 'MISSING'} ({size:.1f} MB)")

    missing = [f for f in EOBS_RAW_FILES if not os.path.exists(f)]
    if missing:
        raise FileNotFoundError(f"Missing E-OBS files: {missing}")

    print("Opening with xarray...")
    ds = xr.open_mfdataset(
        EOBS_RAW_FILES,
        parallel=True,
        chunks={'time': 365},
        combine='by_coords',
        engine='netcdf4',
    )

    print(f"Combined time range: {ds.time.values[0]} to {ds.time.values[-1]}")
    print(f"Original shape: {dict(ds.sizes)}")

    ds_subset = ds.sel(time=slice('1983-01-01', '2023-12-31'))
    print(f"Subset time range: {ds_subset.time.values[0]} to {ds_subset.time.values[-1]}")
    print(f"Subset shape: {dict(ds_subset.sizes)}")

    rename_dict = {}
    if 'tg' in ds_subset.data_vars:
        rename_dict['tg'] = 'T2m'
    if 'latitude' in ds_subset.dims or 'latitude' in ds_subset.coords:
        rename_dict['latitude'] = 'lat'
    if 'longitude' in ds_subset.dims or 'longitude' in ds_subset.coords:
        rename_dict['longitude'] = 'lon'

    if rename_dict:
        ds_subset = ds_subset.rename(rename_dict)
        print(f"Renamed: {rename_dict}")

    ds_subset['T2m'].attrs['units'] = 'degC'
    ds_subset['T2m'].attrs['long_name'] = '2m Temperature'
    ds_subset.attrs['eobs_version_note'] = EOBS_VERSION_NOTE

    print(f"Writing to: {output_path}")
    ds_subset.to_netcdf(output_path, engine='netcdf4')
    ds_subset.close()
    ds.close()

    size_gb = os.path.getsize(output_path) / 1e9
    print(f"Done. Output size: {size_gb:.2f} GB")
