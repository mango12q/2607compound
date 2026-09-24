"""
load_data.py — 数据加载与预处理
加载合并后的 OISST / E-OBS，计算气候学阈值。
支持两种模式：
1. 合并文件存在时直接加载
2. 合并文件不存在时使用原始文件（OISST 用 open_mfdataset 懒加载）

────────────────────────────────────────────────────────────────────────────
Phase 5（图5/图6）输入加载：ERA5 tmax / d2m / sp 与 OAFlux 蒸发
────────────────────────────────────────────────────────────────────────────
实测结构（2026-09-23 数据探针，详见 results/规划一致性审查.md 第四轮）：

| 变量 | 文件 | 变量名 | 单位 | 维度名 | lat | lon | 时间戳 |
|---|---|---|---|---|---|---|---|
| tmax | `tmax_eur_daily/tmax_eur_YYYY_MM.nc` | `mx2t` | **K** | `valid_time` | 66→30 降序 | −10→40 升序 | 00:00 |
| d2m  | `d2m_global_daily/d2m_global_YYYY_MM.nc`（+`yearly/`） | `d2m` | **K** | `valid_time` | 90→−90 降序 | −180..180 升序 | 00:00 |
| sp025| `sp_eur_daily/sp_eur_YYYY_MM.nc`（⬜ 待下载） | `sp` | **Pa** | `valid_time` | 66→30 降序 | −10→40 升序 | 00:00 |
| sp(1°)| `sp/pres.sfc.daily.era5.YYYY.nc`（旧件，兜底） | `sp` | **Pa** | `time` | 90→−90 降序 | **0..360** | **11:30** |

因此本模块统一做四件事（否则下游会静默出 NaN 或错位）：
  1. 维度名归一：`valid_time`/`time` → `time`；`latitude`/`longitude` → `lat`/`lon`；
  2. 经度统一到 **−180..180**（0..360 的件先 roll 再排序）；
  3. 纬度统一为 **升序**（原始全部是降序，`sel(lat=slice(30,66))` 会返回空）；
  4. 时间戳 **floor 到日**（sp 1.0° 的 11:30 与其余 00:00 精确对齐会全 NaN）。
温度默认转 °C（`to_celsius=True`），气压保持 Pa —— WBT/SH 公式内部再按需换算。
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
    ERA5_TMAX_PATTERN, ERA5_TMAX_MERGED_FILE,
    ERA5_D2M_PATTERN, ERA5_D2M_YEARLY_PATTERN,
    ERA5_SP025_PATTERN, ERA5_SP025_MERGED_FILE,
    ERA5_SP1_PATTERN,
    ERA5_EUROPE_BOX,
    OAFLUX_MERGED_FILE, OAFLUX_RAW_DIR,
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


# ══════════════════════════════════════════════════════════════════════════
# Phase 5 输入：ERA5（tmax / d2m / sp）与 OAFlux
# ══════════════════════════════════════════════════════════════════════════

#: 逻辑变量名 → 候选物理变量名（CDS 各版本命名差异的兜底）
ERA5_VAR_CANDIDATES = {
    "tmax": ("mx2t", "tmax", "maximum_temperature_at_2_metres_since_previous_post_processing",
             "t2m_max", "var167_max"),
    "d2m": ("d2m", "d2m_dewpoint_temperature", "2_metre_dewpoint_temperature"),
    "sp025": ("sp", "surface_pressure"),
    "sp": ("sp", "surface_pressure"),
}

ERA5_PATTERNS = {
    "tmax": (ERA5_TMAX_PATTERN, ERA5_TMAX_MERGED_FILE),
    "d2m": (ERA5_D2M_PATTERN, None),
    "d2m_yearly": (ERA5_D2M_YEARLY_PATTERN, None),
    "sp025": (ERA5_SP025_PATTERN, ERA5_SP025_MERGED_FILE),
    "sp": (ERA5_SP1_PATTERN, None),
}


def _pick_data_var(ds: xr.Dataset, logical: str) -> str:
    """在数据集中找出对应逻辑变量的物理变量名（含 fallback，找不到时明确报错）。"""
    for cand in ERA5_VAR_CANDIDATES.get(logical, ()):
        if cand in ds.data_vars:
            return cand
    if len(ds.data_vars) == 1:
        return list(ds.data_vars)[0]
    raise KeyError(
        f"文件里找不到 {logical} 对应的变量；候选 {ERA5_VAR_CANDIDATES.get(logical)}，"
        f"实际变量 = {list(ds.data_vars)}"
    )


def _normalise_dims(ds) -> "xr.Dataset | xr.DataArray":
    """
    维度/坐标归一（见模块头表格）：
      valid_time → time、latitude/longitude → lat/lon、去掉标量 number、
      经度 roll 到 −180..180、纬度转升序、时间戳 floor 到日。
    """
    ren = {}
    for src, dst in (("valid_time", "time"), ("latitude", "lat"),
                     ("longitude", "lon"), ("Longitude", "lon"), ("Latitude", "lat")):
        if src in ds.dims or src in ds.coords:
            ren[src] = dst
    if ren:
        ds = ds.rename(ren)
    if "number" in ds.coords and "number" not in ds.dims:
        ds = ds.drop_vars("number")

    if "lon" in ds.coords:
        lon = ds["lon"]
        if float(lon.max()) > 180.0:                     # 0..360 → −180..180
            new_lon = (((lon + 180.0) % 360.0) - 180.0)
            ds = ds.assign_coords(lon=new_lon).sortby("lon")
        ds = ds.sortby("lon")
    if "lat" in ds.coords:
        if float(ds["lat"][0]) > float(ds["lat"][-1]):   # 降序 → 升序
            ds = ds.sortby("lat")
    if "time" in ds.coords:
        ds = ds.assign_coords(time=ds["time"].dt.floor("D"))
    return ds


def _open_many(files, chunks=None, engine: str = "netcdf4"):
    """open_mfdataset 优先，dask 不可用时退回逐个 open + concat。"""
    if not files:
        raise FileNotFoundError("没有匹配到任何文件")
    if len(files) == 1:
        return xr.open_dataset(files[0], engine=engine)
    try:
        return xr.open_mfdataset(files, combine="by_coords", chunks=chunks or {},
                                 engine=engine, parallel=False)
    except Exception as exc:                              # pragma: no cover
        print(f"  [warn] open_mfdataset 失败（{exc}）；退回逐个打开 + concat")
        parts = [xr.open_dataset(f, engine=engine) for f in files]
        return xr.concat(parts, dim="time" if "time" in parts[0].dims else "valid_time")


def _files_for_period(pattern: str, period=None):
    """按文件名里的年份筛文件，避免把 573 个月度件全部打开（实测仅元数据就 ~71 s）。"""
    files = sorted(glob.glob(pattern))
    if period is None:
        return files
    y0, y1 = int(period[0]), int(period[1])
    keep = []
    for f in files:
        base = os.path.basename(f)
        years = [int(t) for t in "".join(c if c.isdigit() else " " for c in base).split()
                 if len(t) == 4]
        if not years or any(y0 <= y <= y1 for y in years):
            keep.append(f)
    return keep


def open_era5(varname: str, period=None, filepath: Optional[str] = None,
              use_yearly: bool = False, chunks=None) -> xr.Dataset:
    """
    懒加载 ERA5 单变量（**未 subset 到区域，谨慎 .load()**）。

    varname : {'tmax','d2m','sp025','sp'}；`d2m` 可用 `use_yearly=True` 走年度件。
    period  : (y0, y1)，按文件名预筛（不读数据，快）。
    """
    key = "d2m_yearly" if (varname == "d2m" and use_yearly) else varname
    if filepath is None:
        if key not in ERA5_PATTERNS:
            raise ValueError(f"未知 ERA5 变量 {varname!r}；可选 {sorted(ERA5_PATTERNS)}")
        pattern, merged = ERA5_PATTERNS[key]
        if merged and os.path.exists(merged) and period is None:
            filepath = merged
        else:
            if merged and os.path.exists(merged):
                filepath = merged
            else:
                files = _files_for_period(pattern, period)
                if not files:
                    raise FileNotFoundError(
                        f"{varname} 无可用文件：{pattern}\n"
                        f"（Phase 5 下载：run_phase5_downloads.bat / "
                        f"python python\\download_era5_{{tmax,sp025}}.py）")
                ds = _open_many(files, chunks=chunks)
                return _normalise_dims(ds)
    ds = xr.open_dataset(filepath, engine="netcdf4")
    return _normalise_dims(ds)


def load_era5_var(varname: str, filepath: Optional[str] = None, period=None,
                  region: Optional[dict] = None, to_celsius: bool = True,
                  use_yearly: bool = False, load: bool = True) -> xr.DataArray:
    """
    加载 ERA5 单变量 → DataArray(time, lat, lon)。

    Parameters
    ----------
    varname    : {'tmax','d2m','sp025','sp'}
    period     : (y0, y1) 时间子集
    region     : {'lat': (s, n), 'lon': (w, e)}；默认 `config.ERA5_EUROPE_BOX`
                 （传 `{}`/False 表示不裁区域——d2m 是全球场，裁了才省内存）
    to_celsius : True 时把 K → °C（tmax / d2m）；sp 永远保持 Pa
    load       : True 时立刻 .load()（小区域下更快，避免反复解压）

    Returns
    -------
    DataArray，dims=('time','lat','lon')，坐标升序、经度 −180..180、时间戳=日
    """
    ds = open_era5(varname, period=period, filepath=filepath, use_yearly=use_yearly)
    phys = _pick_data_var(ds, "d2m" if (varname == "d2m") else varname)
    da = ds[phys]

    if region is None:
        region = ERA5_EUROPE_BOX
    if region:
        (s, n) = region.get("lat", ERA5_EUROPE_BOX["lat"])
        (w, e) = region.get("lon", ERA5_EUROPE_BOX["lon"])
        da = da.sel(lat=slice(s, n), lon=slice(w, e))

    if period is not None:
        y0, y1 = int(period[0]), int(period[1])
        da = da.sel(time=slice(f"{y0}-01-01", f"{y1}-12-31"))

    if to_celsius and varname in ("tmax", "d2m"):
        units = str(da.attrs.get("units", "")).lower()
        if units in ("k", "kelvin"):
            da = da - 273.15
            da.attrs["units"] = "degC"
            da.attrs["units_original"] = "K"
        elif units not in ("degc", "c", "celsius", "°c"):
            print(f"  [warn] {varname} 单位是 {da.attrs.get('units')!r}，"
                  f"既不是 K 也不是 °C —— 未做换算，请人工核对")

    da.attrs.setdefault("source_file", filepath or ERA5_PATTERNS.get(
        "d2m_yearly" if (varname == "d2m" and use_yearly) else varname, ("", ""))[0])
    if load:
        da = da.load()
    return da.rename(phys if phys != varname else varname)


def era5_available_period(varname: str, use_yearly: bool = False):
    """返回磁盘上实际存在的 (最早年, 最晚年, 文件数)，用于开工前检查。"""
    key = "d2m_yearly" if (varname == "d2m" and use_yearly) else varname
    pattern = ERA5_PATTERNS[key][0]
    files = sorted(glob.glob(pattern))
    years = []
    for f in files:
        toks = [t for t in "".join(c if c.isdigit() else " " for c in os.path.basename(f)).split()
                if len(t) == 4]
        years.extend(int(t) for t in toks)
    if not years:
        return None
    return (min(years), max(years), len(files))


# ──────────────────────────────────────────────
# OAFlux 蒸发
# ──────────────────────────────────────────────
def load_oaflux(filepath: Optional[str] = None, load: bool = False) -> xr.Dataset:
    """
    加载 OAFlux 月平均蒸发。

    ⚠️ 变量名/单位/经度约定**随镜像而变**（下载脚本只校验"变量名含 evap"），
    因此这里把所有坐标归一，并把单位原样保留在 `attrs['units_original']`，
    换算交给 `oaflux_evap_cm_per_year()`（它会明确报出用了哪个单位）。
    """
    if filepath is None:
        if os.path.exists(OAFLUX_MERGED_FILE):
            filepath = OAFLUX_MERGED_FILE
        else:
            raw = sorted(glob.glob(os.path.join(OAFLUX_RAW_DIR, "*.nc")))
            if not raw:
                raise FileNotFoundError(
                    f"OAFlux 无数据：{OAFLUX_MERGED_FILE} 与 {OAFLUX_RAW_DIR}\\*.nc 都不存在\n"
                    f"  下载：python python\\download_oaflux_evap.py --merge")
            ds = _open_many(raw)
            ds = _normalise_dims(ds)
            return ds.load() if load else ds

    ds = xr.open_dataset(filepath, engine="netcdf4")
    ds = _normalise_dims(ds)
    return ds.load() if load else ds


def oaflux_evap_cm_per_year(oaflux, var: Optional[str] = None,
                            units: Optional[str] = None) -> xr.DataArray:
    """
    OAFlux 蒸发 → cm/yr。

    单位从 `attrs['units']` 读（缺省时按 `units` 参数），换算表见
    `calc_wbt.oaflux_to_cm_per_year`；未登记的单位会**明确报错**而不是静默当成 cm/yr。
    """
    from calc_wbt import oaflux_to_cm_per_year

    if isinstance(oaflux, xr.Dataset):
        if var is None:
            cand = [v for v in oaflux.data_vars if "evap" in v.lower()]
            var = cand[0] if cand else list(oaflux.data_vars)[0]
        da = oaflux[var]
    else:
        da = oaflux
    u = units or da.attrs.get("units") or da.attrs.get("unit")
    if u is None:
        raise ValueError(
            "OAFlux 变量没有 units 属性：请显式传 units=（如 'cm/yr'）——"
            "不同镜像的单位不同，不能默认")
    out = oaflux_to_cm_per_year(da, str(u))
    out.attrs["units_original"] = str(u)
    return out


# ──────────────────────────────────────────────
# 开工前检查（Phase 5 / Phase 6）
# ──────────────────────────────────────────────
def check_phase5_inputs(verbose: bool = True) -> dict:
    """
    检查 Phase 5（图 5–6）四类输入是否就位。

    Returns
    -------
    dict: {name: {'ok': bool, 'detail': str}}
    """
    rep = {}

    def _era5(name, key, need_period, note=""):
        avail = era5_available_period(key)
        if avail is None:
            rep[name] = {"ok": False, "detail": f"未找到文件（{ERA5_PATTERNS[key][0]}）{note}"}
            return
        y0, y1, n = avail
        ok = (y0 <= need_period[0]) and (y1 >= need_period[1])
        rep[name] = {"ok": ok, "detail": f"{n} 个文件，覆盖 {y0}–{y1}；"
                                        f"需要 {need_period[0]}–{need_period[1]}{note}"}

    _era5("ERA5 tmax（图6 WBT 分子）", "tmax", (1984, 2023))
    _era5("ERA5 d2m（WBT/SH）", "d2m", (1984, 2023))
    _era5("ERA5 sp 0.25°（WBT 气压）", "sp025", (1984, 2023),
          note="　⚠️ 缺失时只能退回 1.0° sp（分辨率降级，须登记）")
    if not rep["ERA5 sp 0.25°（WBT 气压）"]["ok"]:
        av1 = era5_available_period("sp")
        if av1:
            rep["ERA5 sp 1.0°（兜底）"] = {
                "ok": True, "detail": f"{av1[2]} 个文件，覆盖 {av1[0]}–{av1[1]}（lon 0..360）"}

    if os.path.exists(OAFLUX_MERGED_FILE):
        rep["OAFlux 蒸发（图5b）"] = {"ok": True, "detail": OAFLUX_MERGED_FILE}
    else:
        raw = sorted(glob.glob(os.path.join(OAFLUX_RAW_DIR, "*.nc")))
        rep["OAFlux 蒸发（图5b）"] = {
            "ok": bool(raw),
            "detail": (f"raw/ 下 {len(raw)} 个年度件（未合并）" if raw
                       else "未下载（python python\\download_oaflux_evap.py --merge）")}

    for f, label in ((OISST_MERGED_FILE, "OISST（图5a）"),
                     (EOBS_MERGED_FILE, "E-OBS（图6 陆地）")):
        rep[label] = {"ok": os.path.exists(f), "detail": f}

    if verbose:
        print("=" * 74)
        print("Phase 5 输入检查")
        print("=" * 74)
        for k, v in rep.items():
            print(f"  [{'OK ' if v['ok'] else '缺 '}] {k}: {v['detail']}")
    return rep

