"""
coastal_mask.py — 沿海格点掩码与配对
基于形态学腐蚀提取陆地边缘，使用 KDTree 在 OISST 网格上查找最近海洋格点。
支持 E-OBS（陆地）与 OISST（海洋）不同分辨率网格之间的跨网格配对。
"""
import os
import numpy as np
import pandas as pd
import xarray as xr
from scipy.ndimage import binary_erosion, generate_binary_structure
from scipy.spatial import cKDTree
from typing import Optional

from config import MAX_GRID_DIST_DEG, COASTAL_PAIRS_CSV


def build_land_mask(eobs: xr.Dataset) -> xr.DataArray:
    t2m_var = 'T2m' if 'T2m' in eobs.data_vars else 'tg'
    land_mask = eobs[t2m_var].isel(time=0).notnull().values.astype(np.int8)

    return xr.DataArray(
        land_mask,
        dims=['lat', 'lon'],
        coords={'lat': eobs.lat, 'lon': eobs.lon},
        name='land_mask'
    )


def build_ocean_mask(sst: xr.DataArray) -> xr.DataArray:
    ocean_mask = sst.isel(time=0).notnull().values.astype(np.int8)

    return xr.DataArray(
        ocean_mask,
        dims=['lat', 'lon'],
        coords={'lat': sst.lat, 'lon': sst.lon},
        name='ocean_mask'
    )


def find_coastal_grid_pairs(
    land_mask: xr.DataArray,
    ocean_mask: xr.DataArray,
    max_dist_deg: float = MAX_GRID_DIST_DEG,
    save_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    跨网格沿海配对：E-OBS（陆地）与 OISST（海洋）可能分辨率/范围不同。
    1. 对陆地掩码做形态学腐蚀，提取陆地边缘格点
    2. 为 OISST 海洋格点构建 KDTree（经度用 cos(lat) 加权处理纬度收敛）
    3. 对每个 E-OBS 陆地边缘格点，查询最近 OISST 海洋格点
    """
    land_arr = land_mask.values.astype(np.int8)
    ocean_arr = ocean_mask.values.astype(np.int8)
    land_lat = land_mask.lat.values
    land_lon = land_mask.lon.values
    ocean_lat = ocean_mask.lat.values
    ocean_lon = ocean_mask.lon.values

    s = generate_binary_structure(2, 1)
    land_eroded = binary_erosion(land_arr, structure=s)
    land_edge = land_arr & ~land_eroded

    edge_indices = np.argwhere(land_edge == 1)
    print(f"Finding coastal pairs across grids...")
    print(f"  Land grid (E-OBS): {len(land_lat)} lat x {len(land_lon)} lon")
    print(f"  Ocean grid (OISST): {len(ocean_lat)} lat x {len(ocean_lon)} lon")
    print(f"  Land edge points: {len(edge_indices)}")

    ocean_rows, ocean_cols = np.where(ocean_arr == 1)
    print(f"  Ocean valid points: {len(ocean_rows)}")

    ocean_lats = ocean_lat[ocean_rows]
    ocean_lons = ocean_lon[ocean_cols]
    # OISST 用 0-360°，E-OBS 用 -180-180°，统一到 [-180, 180)
    ocean_lons_unified = np.where(ocean_lons > 180, ocean_lons - 360, ocean_lons)
    cos_factors = np.cos(np.deg2rad(ocean_lats))
    ocean_coords = np.column_stack([ocean_lats, ocean_lons_unified * cos_factors])
    tree = cKDTree(ocean_coords)

    pairs = []
    matched = 0

    for idx, (i, j) in enumerate(edge_indices):
        land_lat_val = float(land_lat[i])
        land_lon_val = float(land_lon[j])

        cos_w = np.cos(np.deg2rad(land_lat_val))
        query_pt = np.array([[land_lat_val, land_lon_val * cos_w]])
        dist, pos = tree.query(query_pt, k=1)

        if dist[0] <= max_dist_deg:
            oi = ocean_rows[pos[0]]
            oj = ocean_cols[pos[0]]
            pairs.append({
                'land_lat_idx': i,
                'land_lon_idx': j,
                'ocean_lat_idx': int(oi),
                'ocean_lon_idx': int(oj),
                'land_lat': land_lat_val,
                'land_lon': land_lon_val,
                'ocean_lat': float(ocean_lat[oi]),
                'ocean_lon': float(ocean_lon[oj]),
                'dist_deg': float(dist[0]),
            })
            matched += 1

        if (idx + 1) % 5000 == 0:
            print(f"  Progress: {idx + 1}/{len(edge_indices)}, matched: {matched}")

    pairs_df = pd.DataFrame(pairs)
    print(f"Found {len(pairs_df)} coastal pairs (matched {matched}/{len(edge_indices)} edge points)")

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        pairs_df.to_csv(save_path, index=False)
        print(f"Saved to: {save_path}")

    return pairs_df
