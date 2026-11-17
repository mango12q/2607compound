# -*- coding: utf-8 -*-
"""只读诊断：CESM1-LE ALL 世界 1983–2012 气候态 vs 观测（OISST SST / E-OBS tg）
在 206 个配对点上的偏差 β。

做法（快版）：只算 1983–2012 的**时间平均场**，所以按"经纬度子框"整块读一次
（OISST 里欧洲框仅 ~72×152 格点），再按最近邻把格点值与配对点对上。
不用 xarray 的散点 fancy-index（那个在 1 GB 文件上会反复读整片，慢到不可用）。

假设检验：若论文阈值 = **观测** 1983–2012 的 90 分位（Methods 说观测与模式用同一套检测），
折算到模式空间，XGHG 世界的阈值相对它自己的 1983–2012 抬高了 θ_obs = δ − β。
θ_obs 落在 0.4–0.6 °C ⇒ "观测阈值"正是图4 需要的中间基准，口径可辩护。

用法: python logs\_diag_obs_bias.py
不写任何产物，只打印。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "python"))

import numpy as np
import pandas as pd
import xarray as xr

import phase6_cesm as P

OISST = os.path.join(HERE, "data", "OISST", "oisst_v2.1_eur_1983_2023.nc")
EOBS = os.path.join(HERE, "data", "E-OBS", "EOBS_tg_1983_2023.nc")
MEMBERS = ["001", "005", "010", "015", "020"]
TAG = "1983-2012"
T0, T1 = "1983-01-01", "2012-12-31"


def obs_clim_map(path, var):
    """观测 1983–2012 时间平均场（经纬度子框，dask 分块）。"""
    with xr.open_dataset(path, chunks={"time": 1000}) as ds:
        sub = ds[var].sel(time=slice(T0, T1))
        clim = sub.mean("time", skipna=True).compute()
        return clim.load()


def map_at(clim, lats, lons):
    """按最近邻从 2-D 气候态场取每个点的值。"""
    la = clim["lat"].values
    lo = clim["lon"].values
    il = np.abs(la[None, :] - np.asarray(lats)[:, None]).argmin(axis=1)
    io_ = np.abs(lo[None, :] - np.asarray(lons)[:, None]).argmin(axis=1)
    vals = clim.values[il, io_]
    return np.asarray(vals, dtype=float)


def cesm_clim_pairs(kind):
    acc = []
    for m in MEMBERS:
        arr, _t = P._load_stitched(kind, "ALL", m, PAIRS, TAG)
        acc.append(np.nanmean(arr, axis=0))
    return np.nanmean(np.vstack(acc), axis=0)


PAIRS = pd.read_csv(P.PAIRS_CSV)
med = (PAIRS.land_lat.between(30, 47) & PAIRS.land_lon.between(5, 42)).values

print(f"配对 {len(PAIRS)} 对（地中海&黑海框 {int(med.sum())}）；模式成员子集 {', '.join(MEMBERS)}")
print(f"CESM 窗口 {TAG}；观测窗口 {T0}~{T1}；逐配对对齐（每对用自己的海点/陆点）")
print()
print(f"{'':<30}{'CESM ALL':>10}{'OBS':>10}{'β=模式−观测':>14}{'N':>6}")
print("-" * 72)

rows = []
jobs = (
    ("sst", OISST, "sst", "ocean_lat", "ocean_lon", "SST 1983-2012（对均值）"),
    ("t2m", EOBS, "T2m", "land_lat", "land_lon", "T2m 1983-2012（对均值）"),
)
for kind, path, var, latcol, loncol, label in jobs:
    clim = obs_clim_map(path, var)
    obs = map_at(clim, PAIRS[latcol].values.astype(float), PAIRS[loncol].values.astype(float))
    mod = cesm_clim_pairs(kind)
    ok = np.isfinite(obs) & np.isfinite(mod)
    b = float(np.nanmean(mod[ok]) - np.nanmean(obs[ok]))
    rows.append((kind, float(np.nanmean(mod[ok])), float(np.nanmean(obs[ok])), b, int(ok.sum())))
    print(f"{label:<30}{rows[-1][1]:10.3f}{rows[-1][2]:10.3f}{b:14.3f}{int(ok.sum()):6d}")
    # 地中海框子集（图4 用的 64 对）
    okm = ok & med
    if okm.sum():
        print(f"{'   └ 地中海框子集':<30}{float(np.nanmean(mod[okm])):10.3f}"
              f"{float(np.nanmean(obs[okm])):10.3f}"
              f"{float(np.nanmean(mod[okm]) - np.nanmean(obs[okm])):14.3f}{int(okm.sum()):6d}")

print()
delta = {"t2m": 1.129, "sst": 0.796}
print("θ_obs = δ − β（δ 见 logs\\_diag_delta_clim.py）:")
for kind, m_, o_, b, n in rows:
    print(f"  {kind}: δ={delta[kind]:.3f}  β={b:+.3f}  →  θ_obs={delta[kind] - b:.3f} °C")
print()
print("判读：θ_obs 0.4–0.6 ⇒ '观测阈值'就是图4 需要的中间基准，口径可辩护；")
print("      θ_obs ≈ 0 ⇒ 模式无偏，观测阈值 ≈ _v8（marine/comp 会死）；")
print("      θ_obs ≈ δ ⇒ 观测 ≈ XGHG 世界，观测阈值 ≈ _v7（terr 偏高 5.5×）。")
