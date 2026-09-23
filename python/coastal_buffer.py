"""
coastal_buffer.py — 海岸向内缓冲区掩码（Phase 5 图6 分析域）

论文原文（Methods / Fig.6 caption，三处）：
    "... average over land grid cells located up to 100 km inland from the
     Mediterranean coast."

论文未给算法。本实现采用与 `coastal_mask.py` 同一套口径：
**到最近海洋格点中心的球面距离 ≤ COASTAL_BUFFER_KM 的 E-OBS 陆地格点**。

为什么不用"到海岸线几何的距离"：
    - 项目已用 OISST 海洋掩码做全部海陆配对（`coastal_pairs.csv`），
      再用海岸线矢量会引入第二套几何基准，两套口径不一致；
    - 0.25° 格网（≈28 km）下，"到最近海洋格点中心"与"到海岸线"的差异
      在半个格距量级，小于论文给的有效数字。

实现要点：
    - 海洋格点取自 OISST（NaN = 陆地/冰，与 coastal_mask.build_ocean_mask 同）；
    - 用 KDTree 在 **3D 单位球笛卡尔坐标** 上做最近邻（避免经度 ±180 环绕问题）；
    - 弦长换算回大圆距离：d = 2R·asin(chord / 2R)，R = 6371.0088 km；
    - 默认区域 = 地中海（config.COASTAL_BUFFER_REGION），不含黑海
      （论文图6 只写 "Mediterranean coast"，与图1/图3 的 "Mediterranean & Black Sea" 不同）。

用法：
    python python/coastal_buffer.py            # 打印掩码统计并落盘
"""
import os
import sys

import numpy as np
import xarray as xr
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    EOBS_MERGED_FILE, OISST_MERGED_FILE,
    COASTAL_BUFFER_KM, COASTAL_BUFFER_REGION,
    INTERMEDIATE_DIR,
)

EARTH_RADIUS_KM = 6371.0088


def _to_unit_vectors(lat2d: np.ndarray, lon2d: np.ndarray) -> np.ndarray:
    """(lat, lon) 度 → 3D 单位球笛卡尔坐标 (N, 3)。"""
    la = np.deg2rad(np.asarray(lat2d, dtype=np.float64).ravel())
    lo = np.deg2rad(np.asarray(lon2d, dtype=np.float64).ravel())
    return np.column_stack([np.cos(la) * np.cos(lo),
                            np.cos(la) * np.sin(lo),
                            np.sin(la)])


def _chord_to_km(chord_unit: np.ndarray) -> np.ndarray:
    """
    单位球弦长 → 大圆距离（km）。

    单位球上两点弦长 c = 2·sin(θ/2)（无量纲，取值 0–2），
    大圆距离 d = R·θ = 2R·asin(c/2)。
    """
    c = np.clip(np.asarray(chord_unit, dtype=np.float64) / 2.0, 0.0, 1.0)
    return 2.0 * EARTH_RADIUS_KM * np.arcsin(c)


def build_coastal_buffer_mask(
    eobs_file: str = EOBS_MERGED_FILE,
    oisst_file: str = OISST_MERGED_FILE,
    buffer_km: float = COASTAL_BUFFER_KM,
    region: dict = None,
    max_search_km: float = 400.0,
):
    """
    构建"地中海海岸向内 buffer_km"的陆地格点掩码。

    Parameters:
        eobs_file  : E-OBS 合并件（变量 T2m，坐标 lat/lon）
        oisst_file : OISST 合并件（变量 sst/SST，坐标 lat/lon）
        buffer_km  : 缓冲距离（论文 = 100 km）
        region     : {'lon': (w, e), 'lat': (s, n)}；默认地中海
        max_search_km : 允许的最远搜索距离（只在距海此范围内找最近海点，
                        用于把掩码限定在真正的"海岸带"）

    Returns:
        mask : xr.DataArray(bool, dims=('lat','lon'))，True = 落在缓冲区内
        info : dict，含 dist_km 场与统计量
    """
    if region is None:
        region = COASTAL_BUFFER_REGION
    (w, e), (s, n) = region["lon"], region["lat"]

    # ── 陆地掩码（E-OBS：非 NaN 即陆地）──────────────────────────
    eobs = xr.open_dataset(eobs_file)
    t2m = eobs["T2m"] if "T2m" in eobs else eobs[list(eobs.data_vars)[0]]
    land = t2m.isel(time=0).notnull()
    land = land.sel(lat=slice(s, n), lon=slice(w, e))
    eobs.close()

    # ── 海洋掩码（OISST：非 NaN 即有效海洋）─────────────────────
    oisst = xr.open_dataset(oisst_file)
    sst = oisst["SST"] if "SST" in oisst else oisst[list(oisst.data_vars)[0]]
    ocean = sst.isel(time=0).notnull()
    # 海洋侧多留 max_search_km 余量，保证岸边陆点能搜到最近海点
    margin = max_search_km / 111.0
    ocean = ocean.sel(lat=slice(s - margin, n + margin), lon=slice(w - margin, e + margin))
    oisst.close()

    lat_l = land["lat"].values
    lon_l = land["lon"].values
    lat_o = ocean["lat"].values
    lon_o = ocean["lon"].values

    ocean_mask = ocean.values
    if not ocean_mask.any():
        raise ValueError("区域内没有有效海洋格点，检查 OISST 掩码与区域定义")

    # ── KDTree：陆地格点 → 最近海洋格点 ─────────────────────────
    lon2d_o, lat2d_o = np.meshgrid(lon_o, lat_o)
    ocean_vec = _to_unit_vectors(lat2d_o[ocean_mask], lon2d_o[ocean_mask])

    lon2d_l, lat2d_l = np.meshgrid(lon_l, lat_l)
    land_vec = _to_unit_vectors(lat2d_l, lon2d_l)

    tree = cKDTree(ocean_vec)
    chord, _ = tree.query(land_vec, k=1)
    dist_km = _chord_to_km(chord).reshape(lat2d_l.shape)

    dist_da = xr.DataArray(dist_km, dims=("lat", "lon"),
                           coords={"lat": lat_l, "lon": lon_l}, name="dist_to_ocean_km")

    mask = ((dist_km <= buffer_km) & land.values)
    mask_da = xr.DataArray(mask, dims=("lat", "lon"),
                           coords={"lat": lat_l, "lon": lon_l}, name="coastal_buffer_mask")

    info = {
        "buffer_km": buffer_km,
        "region": region,
        "land_cells_in_region": int(land.values.sum()),
        "ocean_cells_used": int(ocean_mask.sum()),
        "cells_within_buffer": int(mask.sum()),
        "cells_within_search": int((dist_km <= max_search_km).sum()),
        "dist_km_min": float(np.nanmin(dist_km)),
        "dist_km_max_within": float(np.nanmax(dist_km[mask])) if mask.any() else None,
    }
    return mask_da, dist_da, info


def main():
    mask, dist, info = build_coastal_buffer_mask()
    out_mask = os.path.join(INTERMEDIATE_DIR, "coastal_buffer100km_mask.nc")
    out_dist = os.path.join(INTERMEDIATE_DIR, "dist_to_ocean_km.nc")
    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
    mask.to_dataset().to_netcdf(out_mask)
    dist.to_dataset().to_netcdf(out_dist)

    print("=" * 62)
    print("地中海 100 km 海岸缓冲掩码")
    print("=" * 62)
    print(f"  区域            : lon {info['region']['lon']}  lat {info['region']['lat']}")
    print(f"  缓冲距离        : {info['buffer_km']} km")
    print(f"  区域内陆地格点  : {info['land_cells_in_region']}")
    print(f"  区域内海洋格点  : {info['ocean_cells_used']}")
    print(f"  落入缓冲区格点  : {info['cells_within_buffer']}")
    print(f"  最近海点距离    : min {info['dist_km_min']:.1f} km"
          f" / 缓冲内 max {info['dist_km_max_within']:.1f} km")
    print(f"  -> {out_mask}")
    print(f"  -> {out_dist}")


if __name__ == "__main__":
    main()
