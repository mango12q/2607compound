"""
calc_chr.py — 复合热浪比 (CHR) 和共现概率计算
"""
import os
import numpy as np
import xarray as xr
from typing import Optional

from config import (
    ANNUAL_COMPOUND_NC, ANNUAL_STANDALONE_NC, ANNUAL_THW_NC,
    CHR_ANNUAL_NC, COOCCURRENCE_PROB_NC,
)


def calc_annual_days(daily: xr.DataArray, output_path: Optional[str] = None) -> xr.DataArray:
    annual = daily.groupby('time.year').sum(dim='time')
    annual = annual.rename({'year': 'time'})
    annual.attrs['units'] = 'days/year'

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        annual.to_netcdf(output_path)
        print(f"Saved annual days to: {output_path}")

    return annual


def calc_CHR(
    compound_annual: xr.DataArray,
    standalone_annual: xr.DataArray,
    output_path: Optional[str] = None,
) -> xr.DataArray:
    CHR = compound_annual / standalone_annual
    CHR = CHR.where(standalone_annual > 0, np.nan)
    CHR.attrs['long_name'] = 'Compound Heatwave Ratio'
    CHR.attrs['units'] = 'dimensionless'
    CHR.attrs['description'] = 'Compound days / Standalone days'

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        CHR.to_netcdf(output_path)
        print(f"Saved CHR to: {output_path}")

    return CHR


def calc_cooccurrence_prob(
    compound_annual: xr.DataArray,
    thw_annual: xr.DataArray,
    output_path: Optional[str] = None,
) -> xr.DataArray:
    prob = compound_annual / thw_annual
    prob = prob.where(thw_annual > 0, np.nan)
    prob.attrs['long_name'] = 'Co-occurrence Probability'
    prob.attrs['units'] = 'fraction'
    prob.attrs['description'] = 'Compound days / Total THW days'

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        prob.to_netcdf(output_path)
        print(f"Saved co-occurrence probability to: {output_path}")

    return prob


def calc_spatial_mean(
    da: xr.DataArray,
    lat_range: Optional[tuple] = None,
    lon_range: Optional[tuple] = None,
) -> xr.DataArray:
    if lat_range is not None:
        da = da.sel(lat=slice(lat_range[0], lat_range[1]))
    if lon_range is not None:
        da = da.sel(lon=slice(lon_range[0], lon_range[1]))

    weights = np.cos(np.deg2rad(da.lat))
    return da.weighted(weights).mean(dim=['lat', 'lon'])
