"""
phase5_humid.py — Phase 5 处理链路：湿热应力（论文图 5 与图 6 的数值部分）

论文对应关系（`results/paper_text.txt`）
--------------------------------------
图 5  a  OISST SST，JAS 1994–2023，线性趋势（OLS）[°C/decade]
      b  OAFlux 蒸发，JAS 1991–2020，线性趋势 [cm/yr per decade]
      c  ERA5 比湿 SH，JAS 1994–2023，线性趋势 [g/kg per decade]
图 6  a  WBT ≥ 25.5 °C 的**年度天数**（100 km 海岸缓冲内陆地格点区域平均）
      b  SH ≥ 19 g/kg 的**年度天数**（同上）
      c  WBT 22–28 °C 的重现期（JJA 窗口），复合年 vs 非复合年
      d–f 2003 / 2022 / 2023 复合日 WBT 空间场（正文=平均，caption=最大，两者都存）

子命令
------
    python python/phase5_humid.py check              # 只做输入就位检查
    python python/phase5_humid.py fields             # 逐日 WBT/SH 场 → intermediate/*.nc
    python python/phase5_humid.py stats              # 图5 趋势场 + 图6 统计 → intermediate/ + tables/
    python python/phase5_humid.py all                # fields + stats（推荐）

口径与偏差（全部登记进 results/复现报告.md §5.1）
------------------------------------------------
D8  WBT 公式：论文只说"由 Tmax + 露点 + 地表气压估算"，未给公式。
    本实现默认 `iterative`（psychrometric 牛顿迭代，**用到气压**；
    Stull 2011 解析式不含气压，作为 `--wbt-method stull` 敏感性）。
D9  网格与掩码：WBT/SH 在 ERA5 0.25° 网格上计算，**最近邻**映射到 E-OBS 0.25°
    陆地网格（两套 0.25° 网格原点相差 ~0.13°，即半格 ≈ 14 km），
    再套用既有的 `coastal_buffer100km_mask.nc`（E-OBS 网格）与 `compound_events.nc`。
    这样全项目陆地分析共用同一套陆地网格与掩码。
D10 日窗口拼接：ERA5 `mx2t`（daily_maximum，time_shift = −1 d +23 h）与
    `d2m`/`sp`（daily_mean，time_shift = 0）的 24 h 窗口相差 1 小时。
    论文未涉及；本项目**不做移位**，偏差为亚日尺度（对日最高 WBT 影响 ≪ 0.1 °C）。
D11 sp 兜底：0.25° 欧洲框 sp 未下载时，`--sp-source auto` 会退回 **1.0° 全球 sp**
    并最近邻插值到 0.25°（属需登记的降级），屏幕与 JSON 都会明示。

输出
----
    results/intermediate/wbt_daily.nc            逐日 WBT（Europe 框，float32，可选）
    results/intermediate/sh_daily.nc             逐日 SH（同上）
    results/intermediate/sst_trend_jas_1994_2023.nc
    results/intermediate/evap_trend_jas_1991_2020.nc
    results/intermediate/sh_trend_jas_1994_2023.nc
    results/tables/fig5_stats.json               趋势分位数/锚点
    results/tables/fig6_stats.json               图6a/b 年天数序列 + 6c 重现期 + 6d–f 场
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as C
from calc_wbt import (calc_WBT, calc_specific_humidity, annual_exceedance_days,
                      seasonal_mean, linear_trend_per_decade, calc_sst_trend,
                      oaflux_to_cm_per_year)
from gev_return_period import (fit_gev, gev_return_period_curve,
                               domain_mean_series)
from load_data import (load_era5_var, load_oisst, load_eobs, load_oaflux,
                       oaflux_evap_cm_per_year, check_phase5_inputs,
                       era5_available_period)

WBT_NC = os.path.join(C.INTERMEDIATE_DIR, "wbt_daily.nc")
SH_NC = os.path.join(C.INTERMEDIATE_DIR, "sh_daily.nc")
BUFFER_NC = os.path.join(C.INTERMEDIATE_DIR, "coastal_buffer100km_mask.nc")
TREND_SST_NC = os.path.join(C.INTERMEDIATE_DIR, "sst_trend_jas_1994_2023.nc")
TREND_EVAP_NC = os.path.join(C.INTERMEDIATE_DIR, "evap_trend_jas_1991_2020.nc")
TREND_SH_NC = os.path.join(C.INTERMEDIATE_DIR, "sh_trend_jas_1994_2023.nc")
FIG5_JSON = os.path.join(C.TABLES_DIR, "fig5_stats.json")
FIG6_JSON = os.path.join(C.TABLES_DIR, "fig6_stats.json")

# 分析时段：E-OBS 有 1983 起；WBT/SH 需要 1984–2023（图6 的 S1 判读窗口）
FIELDS_PERIOD = (1984, 2023)


# ══════════════════════════════════════════════════════════════════════════
# 通用小工具
# ══════════════════════════════════════════════════════════════════════════
def _ensure_dirs():
    for d in (C.INTERMEDIATE_DIR, C.TABLES_DIR, C.FIGURES_DIR):
        os.makedirs(d, exist_ok=True)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return v if np.isfinite(v) else None
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def _write_json(path: str, obj: dict):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=_json_default)
    print(f"  -> {path}")


def lon_to_180(da: xr.DataArray, lon_name: str = "lon") -> xr.DataArray:
    """经度 0..360 → −180..180 并排序（OISST 用 0..360，ERA5 用 −180..180）。"""
    lon = da[lon_name]
    if float(lon.max()) <= 180.0:
        return da
    new = (((lon + 180.0) % 360.0) - 180.0)
    return da.assign_coords({lon_name: new}).sortby(lon_name)


def _sel_box(da: xr.DataArray, lat: Tuple[float, float], lon: Tuple[float, float]):
    return da.sel(lat=slice(*lat), lon=slice(*lon))


# ══════════════════════════════════════════════════════════════════════════
# 步骤 1：逐日 WBT / SH 场
# ══════════════════════════════════════════════════════════════════════════
def _sp_for_year(year: int, sp_source: str, region: Optional[dict] = None):
    """返回该年的 sp（Pa）——0.25° 优先，缺失时按 sp_source 退回 1.0°。"""
    if sp_source in ("auto", "sp025"):
        try:
            return load_era5_var("sp025", period=(year, year), to_celsius=False,
                                 region=region)
        except FileNotFoundError as exc:
            if sp_source == "sp025":
                raise
            print(f"  [warn] 0.25° sp 不可用（{exc.__class__.__name__}）；"
                  f"退回 1.0° sp（分辨率降级，D11）")
    return load_era5_var("sp", period=(year, year), to_celsius=False, region=region)


def compute_fields(years: Sequence[int] = None, wbt_method: str = None,
                   sp_source: str = "auto", save_daily: bool = True,
                   verbose: bool = True) -> Dict:
    """
    逐年计算 WBT（日最高）与 SH（日均），可选落盘。

    Returns
    -------
    dict: {'wbt': DataArray(time,lat,lon), 'sh': DataArray(...), 'meta': {...}}
          —— 只在 `save_daily=False` 且调用方需要时才持有整段序列；
          默认路径下为了避免 40 年 × 2 变量驻留内存，返回的是**按年拼接的 dask 惰性数组**
          （`save_daily=True` 时由写入过程逐块消费）。
    """
    years = list(years) if years is not None else list(range(FIELDS_PERIOD[0],
                                                            FIELDS_PERIOD[1] + 1))
    method = wbt_method or C.WBT_METHOD
    wbt_parts, sh_parts, meta = [], [], {"wbt_method": method, "sp_source": sp_source,
                                         "years": years, "per_year": []}
    t_start = time.time()
    for yr in years:
        t0 = time.time()
        tmax = load_era5_var("tmax", period=(yr, yr), to_celsius=True)
        d2m = load_era5_var("d2m", period=(yr, yr), to_celsius=True)
        sp = _sp_for_year(yr, sp_source)

        # sp 与 tmax/d2m 网格不一致（1.0° 兜底）时最近邻对齐到 0.25°
        # ⚠️ 必须用 reindex(method='nearest')：sel(method='nearest') 会保留**源**标签，
        #    在 1.0° → 0.25° 时产生重复索引，后续 xr.align 直接报错。
        if not (sp.sizes.get("lat") == tmax.sizes.get("lat")
                and sp.sizes.get("lon") == tmax.sizes.get("lon")):
            sp = sp.reindex(lat=tmax.lat, lon=tmax.lon, method="nearest")
            meta.setdefault("sp_regridded_years", []).append(int(yr))

        # 三者时间轴取交集：数据不完整（如某月的 tmax 尚未下载）时不至于整体崩掉
        tmax, d2m, sp = xr.align(tmax, d2m, sp, join="inner")

        wbt = calc_WBT(tmax, d2m, sp, method=method).astype("float32")
        sh = calc_specific_humidity(d2m, sp).astype("float32")
        wbt = wbt.rename("WBT"); sh = sh.rename("SH")
        wbt_parts.append(wbt)
        sh_parts.append(sh)
        meta["per_year"].append({"year": int(yr), "n_days": int(wbt.sizes["time"]),
                                 "wbt_max": float(wbt.max()), "sh_max": float(sh.max()),
                                 "secs": round(time.time() - t0, 1)})
        if verbose:
            print(f"  [{yr}] {wbt.sizes['time']:3d} 天  "
                  f"WBT max {float(wbt.max()):5.2f} °C  SH max {float(sh.max()):5.2f} g/kg"
                  f"  ({time.time() - t0:.1f} s)")

    wbt_all = xr.concat(wbt_parts, dim="time").sortby("time")
    sh_all = xr.concat(sh_parts, dim="time").sortby("time")
    meta["secs_total"] = round(time.time() - t_start, 1)

    if save_daily:
        _ensure_dirs()
        for da, path, name in ((wbt_all, WBT_NC, "WBT"), (sh_all, SH_NC, "SH")):
            enc = {name: {"zlib": True, "complevel": 4, "dtype": "float32"}}
            da.to_dataset().to_netcdf(path, encoding=enc)
            print(f"  -> {path}  ({da.sizes['time']} 天 × {da.sizes['lat']} × {da.sizes['lon']})")
        meta["saved_daily"] = True
    return {"wbt": wbt_all, "sh": sh_all, "meta": meta}


def load_fields(period: Optional[Tuple[int, int]] = None):
    """读取已落盘的逐日 WBT/SH（缺失时明确报错并给出命令）。"""
    missing = [p for p in (WBT_NC, SH_NC) if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            "缺少 " + "、".join(missing) + "\n"
            "  先运行：python python\\phase5_humid.py fields")
    wbt = xr.open_dataarray(WBT_NC)
    sh = xr.open_dataarray(SH_NC)
    if period is not None:
        y0, y1 = period
        sl = slice(f"{y0}-01-01", f"{y1}-12-31")
        wbt, sh = wbt.sel(time=sl), sh.sel(time=sl)
    return wbt, sh


# ══════════════════════════════════════════════════════════════════════════
# 步骤 2：图 5 —— 三条趋势场
# ══════════════════════════════════════════════════════════════════════════
def trends_fig5(save: bool = True, verbose: bool = True) -> Dict:
    _ensure_dirs()
    out = {}
    box = C.ERA5_MAP_BOX          # 论文 Fig.5 的地图范围（比下载框大，第五轮实测）

    # 5a OISST SST，JAS 1994–2023 —— 只算论文 Fig.5 的地图范围，省内存
    oisst = load_oisst()
    sst = lon_to_180(oisst["SST"])
    sst = _sel_box(sst, box["lat"], box["lon"])
    slope, pval = calc_sst_trend(sst.to_dataset(name="SST"),
                                 period=C.SST_TREND_PERIOD, months=C.TREND_MONTHS)
    out["sst"] = (slope, pval)
    if save:
        xr.Dataset({"sst_trend": slope, "pvalue": pval}).to_netcdf(TREND_SST_NC)
        print(f"  -> {TREND_SST_NC}")

    # 5b OAFlux 蒸发，JAS 1991–2020（cm/yr per decade）
    try:
        oa = load_oaflux()
        ev = oaflux_evap_cm_per_year(oa)
        ev = _sel_box(lon_to_180(ev), box["lat"], box["lon"])
        slope, pval = linear_trend_per_decade(
            seasonal_mean(ev, C.TREND_MONTHS, C.EVAP_TREND_PERIOD))
        slope.attrs["units"] = "cm/yr per decade"
        out["evap"] = (slope, pval)
        if save:
            xr.Dataset({"evap_trend": slope, "pvalue": pval}).to_netcdf(TREND_EVAP_NC)
            print(f"  -> {TREND_EVAP_NC}")
    except FileNotFoundError as exc:
        print(f"  [skip] 图5b 蒸发趋势：{exc}")
        out["evap"] = None

    # 5c ERA5 SH，JAS 1994–2023（g/kg per decade）
    # ★ 只用 d2m（+sp）算 SH —— **不需要 tmax**，因此 tmax 未下载也能先跑图5c
    #   区域按论文 Fig.5 的地图范围取（d2m 是全球场；sp 0.25° 的下载框已相应扩大）
    sh_parts = []
    for yr in range(C.SH_TREND_PERIOD[0], C.SH_TREND_PERIOD[1] + 1):
        d2m = load_era5_var("d2m", period=(yr, yr), to_celsius=True, region=box)
        sp = _sp_for_year(yr, "auto", region=box)
        if not (sp.sizes.get("lat") == d2m.sizes.get("lat")
                and sp.sizes.get("lon") == d2m.sizes.get("lon")):
            sp = sp.reindex(lat=d2m.lat, lon=d2m.lon, method="nearest")
        d2m, sp = xr.align(d2m, sp, join="inner")
        sh_parts.append(calc_specific_humidity(d2m, sp).astype("float32"))
        if verbose:
            print(f"  [5c {yr}] SH 计算完成（{d2m.sizes['time']} 天）")
    sh_daily = xr.concat(sh_parts, dim="time").sortby("time")
    slope, pval = linear_trend_per_decade(
        seasonal_mean(sh_daily, C.TREND_MONTHS, C.SH_TREND_PERIOD))
    slope.attrs["units"] = "g/kg per decade"
    out["sh"] = (slope, pval)
    if save:
        xr.Dataset({"sh_trend": slope, "pvalue": pval}).to_netcdf(TREND_SH_NC)
        print(f"  -> {TREND_SH_NC}")
    return out


def _field_summary(slope: xr.DataArray, pval: xr.DataArray) -> Dict:
    v = np.asarray(slope.values, dtype=float)
    p = np.asarray(pval.values, dtype=float)
    fin = np.isfinite(v)
    return {
        "n_cells": int(fin.sum()),
        "median": float(np.nanmedian(v)),
        "p05": float(np.nanpercentile(v, 5)),
        "p95": float(np.nanpercentile(v, 95)),
        "min": float(np.nanmin(v)), "max": float(np.nanmax(v)),
        "frac_p_lt_005": float(np.nanmean(p[fin] < 0.05)),
    }


# ══════════════════════════════════════════════════════════════════════════
# 步骤 3：图 6 —— 缓冲区内 WBT/SH 统计
# ══════════════════════════════════════════════════════════════════════════
def _buffer_mask() -> xr.DataArray:
    if not os.path.exists(BUFFER_NC):
        raise FileNotFoundError(
            f"缺少海岸缓冲掩码 {BUFFER_NC}\n  先运行：python python\\coastal_buffer.py")
    m = xr.open_dataarray(BUFFER_NC)
    return m.astype(bool)


def _compound_mask(period: Tuple[int, int]) -> xr.DataArray:
    path = C.COMPOUND_NC
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺少 {path}\n  先运行：python python\\run_all.py")
    ds = xr.open_dataset(path)
    key = "compound_mhw_thw" if "compound_mhw_thw" in ds else list(ds.data_vars)[0]
    da = ds[key]
    y0, y1 = period
    return da.sel(time=slice(f"{y0}-01-01", f"{y1}-12-31"))


def _to_buffer_grid(da: xr.DataArray, mask: xr.DataArray) -> xr.DataArray:
    """
    ERA5 0.25° → E-OBS 0.25°（掩码网格）**最近邻**映射（D9）。
    只在掩码外接矩形范围内取样，避免把 201×464 的整张陆地网格都做映射。
    """
    lat0, lat1 = float(mask.lat.min()), float(mask.lat.max())
    lon0, lon1 = float(mask.lon.min()), float(mask.lon.max())
    # 外扩半格，保证 reindex 的每个目标点在源网格覆盖范围内
    sub = da.sel(lat=slice(lat0 - 0.5, lat1 + 0.5), lon=slice(lon0 - 0.5, lon1 + 0.5))
    same = (sub.sizes.get("lat") == mask.sizes.get("lat")
            and sub.sizes.get("lon") == mask.sizes.get("lon")
            and np.allclose(sub.lat.values, mask.lat.values, atol=1e-6)
            and np.allclose(sub.lon.values, mask.lon.values, atol=1e-6))
    if not same:
        # reindex（不是 sel）→ 结果坐标就是 mask 的坐标，不会出现重复索引
        sub = sub.reindex(lat=mask.lat, lon=mask.lon, method="nearest")
    return sub


def stats_fig6(wbt: xr.DataArray, sh: xr.DataArray, verbose: bool = True) -> Dict:
    mask = _buffer_mask()
    out: Dict = {"buffer": {
        "region": C.COASTAL_BUFFER_REGION, "buffer_km": C.COASTAL_BUFFER_KM,
        "n_cells": int(mask.sum()),
    }}
    # 图6 关心的年份 = 3 个复合年 + 论文 Fig.6c 图例列出的 11 个非复合年
    # （★ 第五轮：**不含** S1 判读的敏感性年份——论文原图正好 14 条曲线，
    #   多画年份会让图与论文不一致；S1 口径另在 groups 里登记备用）
    years_of_interest = sorted(set(C.WBT_RP_YEARS) | set(C.WBT_NONCOMPOUND_YEARS))

    # ── 6a / 6b：超阈频率曲线（论文原图是"曲线家族"，不是单值柱状图）─────
    # ★ 2026-09-24 第五轮更正：论文 Fig.6a/b 的 x 轴是**阈值**（a: WBT 25.5–27.0 °C、
    #   b: SH 19.0–20.7 g/kg），y 轴是"Exceedance frequency (Days)"，**每年一条曲线**
    #   （3 个复合年粗实线 + 11 个非复合年细虚线）。TECHNICAL_SPEC_PHASE_C §C.4 把它
    #   写成"每个年份一根柱"是错的，出图与统计都按原图改。
    #   统计口径：对每个阈值 t，先逐格点统计"全年 ≥t 的天数"，再在缓冲区内做区域平均
    #   ——即 mean_cells(Σ_days 1[v≥t])，不能先区域平均再判阈值（两者不等价）。
    curves = {"wbt": {}, "sh": {}}
    for tag, da, thresholds in (("wbt", wbt, C.WBT_EXCEED_THRESHOLDS),
                                ("sh", sh, C.SH_EXCEED_THRESHOLDS)):
        buf = _to_buffer_grid(da, mask)
        thr_arr = np.asarray(thresholds, dtype="float32")
        for yr in years_of_interest:
            sub = buf.sel(time=(buf["time"].dt.year == yr))
            if sub.sizes.get("time", 0) == 0:
                continue
            v = sub.values                                  # (time, lat, lon)
            cnt = (v[:, None, :, :] >= thr_arr[None, :, None, None]).sum(axis=0)
            cnt = np.where(mask.values[None, :, :], cnt, np.nan)
            days = np.nanmean(cnt, axis=(1, 2))
            curves[tag][int(yr)] = {
                "thresholds": [float(t) for t in thresholds],
                "days": [None if not np.isfinite(d) else float(d) for d in days],
            }
    out["exceedance_curves"] = curves
    out["exceedance_thresholds"] = {"wbt": list(C.WBT_EXCEED_THRESHOLDS),
                                    "sh": list(C.SH_EXCEED_THRESHOLDS)}

    # 单阈值年度天数（保留：报告与锚点核对用；论文正文的"2023 ≈40 天"即出自 6a 的 25.5 点）
    series = {}
    for tag, da, thr in (("wbt25.5", wbt, C.WBT_THRESHOLD), ("sh19", sh, C.SH_THRESHOLD)):
        buf = _to_buffer_grid(da, mask)
        days = annual_exceedance_days(buf, thr, mask=mask, domain_mean=True)
        series[tag] = {int(y): float(v) for y, v in
                       zip(days["year"].values, days.values)}
        if verbose:
            y23 = series[tag].get(2023)
            nc_vals = [series[tag][y] for y in C.WBT_NONCOMPOUND_YEARS
                       if y in series[tag]]
            nc_mean = float(np.mean(nc_vals)) if nc_vals else float("nan")
            print(f"  [{tag}] 2023 = "
                  f"{'（该年不在数据里）' if y23 is None else f'{y23:.1f} 天'}；"
                  f"非复合年（论文 Fig.6c 图例 11 年）均值 = "
                  f"{'（无可用年）' if not nc_vals else f'{nc_mean:.1f} 天'}")
    out["annual_days"] = series
    out["groups"] = {
        "compound_years": list(C.WBT_RP_YEARS),
        "noncompound_paper11": list(C.WBT_NONCOMPOUND_YEARS),
        "noncompound_s1_judgement": list(C.WBT_NONCOMPOUND_YEARS_S1),
        "paper_named_2000": C.WBT_NONCOMPOUND_YEAR_PAPER,
    }

    # ── 6c：WBT 22–28 °C 的重现期（JJA 窗口）───────────────────────────
    buf_wbt = _to_buffer_grid(wbt, mask)
    jja = buf_wbt.where(buf_wbt["time"].dt.month.isin(list(C.WBT_RP_MONTHS)), drop=True)
    curves_rp, daily_jja = {}, {}
    for yr in sorted(years_of_interest):
        if yr not in set(jja["time"].dt.year.values):
            continue
        ser = domain_mean_series(jja.sel(time=jja.time.dt.year == yr))
        vals = np.asarray(ser.values, dtype=float)
        daily_jja[int(yr)] = {"n": int(np.isfinite(vals).sum()),
                              "max": float(np.nanmax(vals)),
                              "mean": float(np.nanmean(vals))}
        curve = gev_return_period_curve(vals, C.WBT_RP_THRESHOLDS)
        curves_rp[int(yr)] = {
            "thresholds": [float(t) for t in curve["thresholds"]],
            "rp": [None if not np.isfinite(v) else float(v) for v in curve["rp"]],
            "rp_lo": [None if not np.isfinite(v) else float(v) for v in curve["rp_lo"]],
            "rp_hi": [None if not np.isfinite(v) else float(v) for v in curve["rp_hi"]],
            "n_valid_boot": curve["n_valid_boot"], "n_failed": curve["n_failed"],
            "params": (None if curve["params"] is None else
                       {"c": curve["params"][0], "loc": curve["params"][1],
                        "scale": curve["params"][2]}),
        }
        if verbose:
            rp26 = curves_rp[int(yr)]["rp"][C.WBT_RP_THRESHOLDS.index(26.0)]
            print(f"  [6c {yr}] JJA 区域平均 WBT max={daily_jja[int(yr)]['max']:.2f} °C，"
                  f"RP(26 °C) = {rp26 if rp26 is None else round(rp26, 2)} 年")
    out["rp_curves"] = curves_rp
    out["jja_summary"] = daily_jja

    # ── 6d–f：复合日 WBT 空间场（平均 + 最大）──────────────────────────
    # ★ 第五轮更正：论文 d–f 是**整个地中海—欧洲陆地区域**的地图（不限 100 km 缓冲），
    #   故这里用复合掩码的完整网格（裁到 ERA5 欧洲框内）做映射。
    comp = _compound_mask((min(C.WBT_RP_YEARS), max(C.WBT_RP_YEARS)))
    lat0, lat1 = C.ERA5_EUROPE_BOX["lat"]
    lon0, lon1 = C.ERA5_EUROPE_BOX["lon"]
    template = comp.sel(lat=slice(lat0, lat1), lon=slice(lon0, lon1))
    wbt_reg = wbt.reindex(lat=template.lat, lon=template.lon, method="nearest")
    comp_reg = (template.fillna(0) > 0.5)
    fields = {}
    for yr in C.WBT_RP_YEARS:
        # ⚠️ 两边的年份布尔掩码必须各自基于**自己的** time 轴构造
        c = comp_reg.sel(time=(comp_reg["time"].dt.year == yr))
        w = wbt_reg.sel(time=(wbt_reg["time"].dt.year == yr))
        w, c = xr.align(w, c, join="inner")
        n_days = int(c.sum())
        sel = w.where(c)
        if n_days == 0 or sel.sizes.get("time", 0) == 0:
            empty = wbt_reg.isel(time=0, drop=True) * np.nan
            fields[int(yr)] = {"n_compound_days": 0, "mean": empty, "max": empty.copy()}
            if verbose:
                print(f"  [6d-f {yr}] 该年无复合日 / 不在 WBT 数据范围内 → 场置 NaN")
            continue
        fields[int(yr)] = {
            "n_compound_days": n_days,
            "mean": sel.mean(dim="time", skipna=True),
            "max": sel.max(dim="time", skipna=True),
        }
        if verbose:
            print(f"  [6d-f {yr}] 陆地区域内复合日 {n_days} 天，"
                  f"复合日平均 WBT 区域均值 "
                  f"{float(sel.mean(dim='time').mean()):.2f} °C，"
                  f"最大 {float(sel.max()):.2f} °C")
    out["spatial_fields"] = fields
    return out


# ══════════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════════
def cmd_check(args):
    rep = check_phase5_inputs(verbose=True)
    ok = all(v["ok"] for k, v in rep.items() if "兜底" not in k)
    print("\n结论：" + ("输入齐备，可以跑 `phase5_humid.py all`"
                      if ok else "仍有缺项——见上面的 [缺] 行；" 
                      "缺 tmax/sp0.25°/OAFlux 时先跑 run_phase5_downloads.bat"))
    return 0 if ok else 2


def cmd_fields(args):
    compute_fields(wbt_method=args.wbt_method, sp_source=args.sp_source,
                   save_daily=not args.no_save_daily)
    return 0


def cmd_stats(args):
    _ensure_dirs()

    print("\n[1/3] 图 5 趋势场 ...")
    tr = trends_fig5(save=True, verbose=not args.quiet)
    fig5 = {k: (_field_summary(*v) if v is not None else None) for k, v in tr.items()}
    fig5["_config"] = {
        "sst_period": C.SST_TREND_PERIOD, "evap_period": C.EVAP_TREND_PERIOD,
        "sh_period": C.SH_TREND_PERIOD, "months": list(C.TREND_MONTHS),
    }
    fig5["_anchor"] = {
        "sst_trend_expect": "≈ +0.5 °C/decade（论文正文 up to 0.5；容差 ±0.15）",
        "evap_trend_expect": "局部 > +10 cm/yr/decade（论文正文）",
        "sh_trend_expect": "≈ +0.3 g/kg/decade（论文正文；容差 ±0.1）",
    }
    _write_json(FIG5_JSON, fig5)

    print("\n[2/3] 读取逐日 WBT/SH ...")
    wbt, sh = load_fields()
    print(f"  WBT {dict(wbt.sizes)}；SH {dict(sh.sizes)}")

    print("\n[3/3] 图 6 统计 ...")
    fig6 = stats_fig6(wbt.load(), sh.load(), verbose=not args.quiet)
    fig6["_anchor"] = {
        "2023_wbt_days_expect": "≈ 40 天（论文正文；容差 ±5）",
        "noncompound_wbt_days_expect": "< 5 天（论文正文；容差 ±3）",
        "rp_2023_at_26C_expect": "≈ 3–4 年（论文正文）",
        "rp_2000_at_26C_expect": "≈ 60 年（论文正文）",
    }
    _write_json(FIG6_JSON, fig6)

    # 6d–f 的空间场单独落盘（JSON 装不下 2D 场）
    fields = fig6.get("spatial_fields", {})
    if fields:
        for yr, d in fields.items():
            p = os.path.join(C.INTERMEDIATE_DIR, f"wbt_compound_{yr}.nc")
            xr.Dataset({"wbt_mean": d["mean"], "wbt_max": d["max"]}).to_netcdf(p)
            print(f"  -> {p}")
    return 0


def cmd_all(args):
    cmd_fields(args)
    cmd_stats(args)
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        description="Phase 5 湿热应力处理链路（论文图 5/图 6 的数值部分）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--wbt-method", default=C.WBT_METHOD,
                        choices=["iterative", "stull"],
                        help="WBT 公式（默认 iterative = psychrometric 牛顿迭代，用到气压）")
        sp.add_argument("--sp-source", default="auto",
                        choices=["auto", "sp025", "sp"],
                        help="地表气压来源；auto = 0.25° 优先、缺失退回 1.0°")
        sp.add_argument("--no-save-daily", action="store_true",
                        help="不落盘逐日 WBT/SH（省 ~3.5 GB 磁盘，但 stats 需重算）")
        sp.add_argument("--quiet", action="store_true")

    common(sub.add_parser("check", help="只检查输入是否就位"))
    common(sub.add_parser("fields", help="逐日 WBT/SH 场"))
    common(sub.add_parser("stats", help="图5 趋势 + 图6 统计"))
    common(sub.add_parser("all", help="fields + stats"))
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return {"check": cmd_check, "fields": cmd_fields,
            "stats": cmd_stats, "all": cmd_all}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
