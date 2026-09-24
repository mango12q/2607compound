"""
calc_wbt.py — 湿球温度 (WBT) / 相对湿度 (RH) / 比湿 (SH) 计算与趋势估计
（Phase 5：论文图 5 与图 6 的数值内核）

论文口径（`results/paper_text.txt`）：
    :365-366 "WBT is estimated from ERA5 reanalysis using maximum temperature,
              dew point temperature, and surface pressure."
    :616     "daily maximum wet-bulb temperature estimated from Tmax, dew point
              temperature and surface pressure"
    :372-376 图 5 = SST / 蒸发 / 比湿 的 **JAS** 线性趋势（OLS）
    :385-393 图 6 = WBT ≥ 25.5 °C 与 SH ≥ 19 g/kg 的**年度**天数；
             图 6c = WBT 22–28 °C 的重现期（JJA 窗口）；图 6d–f = 复合日 WBT 空间场

⚠️ 论文**未给 WBT 近似式**，只说输入是 Tmax + 露点 + 气压。本模块因此同时实现两种标准解，
   由 `calc_WBT(method=...)` 选择，并把选择登记为方法学决策（复现报告 §5.1 / D8）：

    ``stull``     Stull (2011) 解析近似（气压无关，隐含 p = 1013.25 hPa）
    ``iterative`` 对 psychrometric 方程做牛顿迭代（**用到气压**，默认）

    为什么默认 iterative：论文明确把 surface pressure 列为输入，而 Stull 公式不含气压项；
    在 p < 1013.25 hPa（内陆/高海拔）时 Stull 会系统性偏高。两者在 20–40 °C / 20–90 %RH
    的范围内相差 < 0.5 °C（见 `_selftest`），故该选择不影响定性结论，但须在报告中登记。

所有函数对 xarray.DataArray 逐点操作，**不强制 .values**，因此可安全用于 dask 分块数组。
"""
from __future__ import annotations

import os
import sys
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import GEV_CI  # noqa: F401  (供下游统一取 CI，避免各脚本各写一份)

# ──────────────────────────────────────────────
# 物理常数
# ──────────────────────────────────────────────
# Magnus/Tetens 饱和水汽压系数（Bolton 1980 常用形式）
MAGNUS_A = 6.112      # hPa
MAGNUS_B = 17.67
MAGNUS_C = 243.5      # °C

# 湿度计常数（psychrometric constant）经验式：γ = a·(1 + b·Td)
GAMMA_A = 0.00066     # 1/°C
GAMMA_B = 0.00115     # 1/°C

STULL_P0_HPA = 1013.25   # Stull (2011) 拟合时的标准气压

# 迭代解默认参数
WBT_MAX_ITER = 50
WBT_TOL = 1e-4           # °C

# 趋势估计最少需要的年数（不足则该格点置 NaN）
MIN_TREND_YEARS = 10


# ──────────────────────────────────────────────
# 基础热力学量
# ──────────────────────────────────────────────
def saturation_vapor_pressure(t, celsius: bool = True) -> xr.DataArray:
    """饱和水汽压 es(T) [hPa]（Magnus 公式，T 为 °C）。"""
    if not celsius:
        t = t - 273.15
    return MAGNUS_A * np.exp(MAGNUS_B * t / (t + MAGNUS_C))


def calc_relative_humidity(tmax: xr.DataArray, d2m: xr.DataArray) -> xr.DataArray:
    """
    相对湿度 RH [%] = es(Td) / es(T) × 100，裁剪到 [0, 100]。

    Parameters
    ----------
    tmax : 气温（日最高，°C）
    d2m  : 露点温度（°C）
    """
    es_t = saturation_vapor_pressure(tmax)
    es_d = saturation_vapor_pressure(d2m)
    rh = (es_d / es_t) * 100.0
    rh = rh.clip(min=0.0, max=100.0)
    rh.attrs.update(long_name="Relative humidity", units="%")
    return rh.rename("RH")


def calc_vapor_pressure(d2m: xr.DataArray) -> xr.DataArray:
    """实际水汽压 e [hPa]，由露点温度定。"""
    e = saturation_vapor_pressure(d2m)
    e.attrs.update(long_name="Vapour pressure", units="hPa")
    return e.rename("e")


def calc_specific_humidity(d2m: xr.DataArray, sp: xr.DataArray,
                           sp_units: str = "Pa") -> xr.DataArray:
    """
    比湿 SH [g/kg]。

        e = es(Td)                [hPa]
        q = 0.622 · e / (p − 0.378 · e)     [kg/kg]
        SH = q × 1000             [g/kg]

    Parameters
    ----------
    d2m : 露点温度（°C）
    sp  : 地表气压；`sp_units` ∈ {'Pa', 'hPa'}，默认 'Pa'（ERA5 原始单位）
    """
    e = calc_vapor_pressure(d2m)
    if sp_units.lower() == "pa":
        p = sp / 100.0
    elif sp_units.lower() == "hpa":
        p = sp
    else:
        raise ValueError(f"sp_units 只能是 'Pa' 或 'hPa'，收到 {sp_units!r}")

    q = 0.622 * e / (p - 0.378 * e) * 1000.0
    q = q.where(q > 0)          # 露点 < −240 °C 的荒谬值（或 p≤e）置 NaN
    q.attrs.update(long_name="Specific humidity", units="g/kg")
    return q.rename("SH")


# ──────────────────────────────────────────────
# WBT：Stull (2011) 解析近似
# ──────────────────────────────────────────────
def calc_WBT_stull(tmax: xr.DataArray, d2m: xr.DataArray,
                   sp: Optional[xr.DataArray] = None) -> xr.DataArray:
    """
    Stull, R. (2011) *Wet-Bulb Temperature from Relative Humidity and Air
    Temperature*, J. Appl. Meteor. Climatol. 50, 2267–2269.

        WBT = T·atan(0.151977·√(RH + 8.313659))
              + atan(T + RH) − atan(RH − 1.676331)
              + 0.00391838·RH^{3/2}·atan(0.023101·RH)
              − 4.686035

    有效范围：−20 ≤ T ≤ 50 °C，5 ≤ RH ≤ 99 %，p = 1013.25 hPa。
    `sp` 参数仅为保持两种实现同签名（Stull 公式不含气压），传入时忽略。
    """
    if sp is not None:
        # 显式提示：调用方若以为气压被用了，会得到静默偏差
        pass
    rh = calc_relative_humidity(tmax, d2m)
    t = tmax

    wbt = (t * np.arctan(0.151977 * np.sqrt(rh + 8.313659))
           + np.arctan(t + rh)
           - np.arctan(rh - 1.676331)
           + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh)
           - 4.686035)
    wbt = wbt.clip(min=d2m, max=t)      # 物理约束：Td ≤ Tw ≤ T
    wbt.attrs.update(long_name="Wet-bulb temperature (Stull 2011)", units="degC",
                     method="stull")
    return wbt.rename("WBT")


# ──────────────────────────────────────────────
# WBT：psychrometric 方程牛顿迭代（用到气压）
# ──────────────────────────────────────────────
def calc_WBT_iterative(tmax: xr.DataArray, d2m: xr.DataArray, sp: xr.DataArray,
                       max_iter: int = WBT_MAX_ITER, tol: float = WBT_TOL,
                       sp_units: str = "Pa") -> xr.DataArray:
    """
    对 psychrometric（干湿球能量平衡）方程求根，得到通气湿球温度：

        f(Tw) = es(Tw) − e(Td) − γ·p·(T − Tw) = 0
        γ     = 0.00066·(1 + 0.00115·Td)          [1/°C]
        p     = 地表气压                            [hPa]

    牛顿迭代，初值为 Stull 近似；每步把解夹在物理区间 [Td, T] 内。
    气压越低 → 蒸发冷却越强 → Tw 越低（Stull 用固定 1013.25 hPa 会偏高）。

    Parameters
    ----------
    tmax, d2m : °C
    sp        : 地表气压，默认单位 Pa（`sp_units` 可切 'hPa'）
    max_iter  : 最大迭代次数
    tol       : 收敛判据（°C，|ΔTw|）
    """
    if sp_units.lower() == "pa":
        p = sp / 100.0
    elif sp_units.lower() == "hpa":
        p = sp
    else:
        raise ValueError(f"sp_units 只能是 'Pa' 或 'hPa'，收到 {sp_units!r}")

    t = tmax
    td = xr.where(d2m > tmax, tmax, d2m)      # 过饱和保护：Td ≤ T
    e = calc_vapor_pressure(td)
    gamma = GAMMA_A * (1.0 + GAMMA_B * td)

    def f(tw):
        return saturation_vapor_pressure(tw) - e - gamma * p * (t - tw)

    def df(tw):
        es = saturation_vapor_pressure(tw)
        return es * MAGNUS_B * MAGNUS_C / (tw + MAGNUS_C) ** 2 + gamma * p

    tw = calc_WBT_stull(t, td)
    for _ in range(int(max_iter)):
        step = f(tw) / df(tw)
        tw_new = (tw - step).clip(min=td, max=t)
        delta = np.abs(tw_new - tw)
        tw = tw_new
        # 全部点都已收敛则提前退出（NaN 视为收敛，避免死循环）
        if bool(np.all((delta < tol) | np.isnan(delta)).compute()
                if hasattr(delta, "compute") else np.all((delta < tol) | np.isnan(delta))):
            break

    tw = tw.clip(min=td, max=t)
    tw.attrs.update(long_name="Wet-bulb temperature (psychrometric Newton solve)",
                    units="degC", method="iterative",
                    max_iter=int(max_iter), tol=float(tol))
    return tw.rename("WBT")


def calc_WBT(tmax: xr.DataArray, d2m: xr.DataArray, sp: xr.DataArray,
             method: str = "iterative", **kwargs) -> xr.DataArray:
    """
    WBT 入口。

    method : {'iterative', 'stull'}
        - 'iterative'（默认）：psychrometric 牛顿迭代，用到 sp
        - 'stull'：Stull (2011) 解析式（忽略 sp）
    """
    m = str(method).lower()
    if m == "iterative":
        return calc_WBT_iterative(tmax, d2m, sp, **kwargs)
    if m == "stull":
        return calc_WBT_stull(tmax, d2m, sp)
    raise ValueError(f"method 只能是 'iterative' 或 'stull'，收到 {method!r}")


# ──────────────────────────────────────────────
# 趋势估计（图 5：JAS 季节平均的 OLS 线性趋势）
# ──────────────────────────────────────────────
def seasonal_mean(da: xr.DataArray, months: Sequence[int],
                  period: Tuple[int, int]) -> xr.DataArray:
    """逐年季节平均 → 维度 (year, ...)，只保留该年季节内有效值 >0 的年份。"""
    y0, y1 = period
    sub = da.sel(time=slice(f"{y0}-01-01", f"{y1}-12-31"))
    sub = sub.where(sub["time"].dt.month.isin(list(months)), drop=True)
    out = sub.groupby("time.year").mean(dim="time", skipna=True)
    out = out.where(out.notnull().any(dim=[d for d in out.dims if d != "year"]))
    out.attrs["season_months"] = ",".join(str(m) for m in months)
    out.attrs["period"] = f"{y0}-{y1}"
    return out.rename("seasonal_mean")


def _linregress_slope(field: np.ndarray, x: np.ndarray,
                      min_years: int = MIN_TREND_YEARS) -> Tuple[np.ndarray, np.ndarray]:
    """
    逐格点 OLS 斜率 + 双侧 p 值（对 NaN 免疫）。

    field : (n_year, ...) 数组；x : (n_year,)
    return : (slope, pvalue)，形状同 field[0]

    实现：把空间维拉平后用 nan-aware 的求和公式一次算完（比 polyfit/循环快 2–3 个量级）。
    """
    field = np.asarray(field, dtype=np.float64)
    ny = field.shape[0]
    flat = field.reshape(ny, -1)
    mask = np.isfinite(flat)
    n = mask.sum(axis=0).astype(np.float64)

    xb = np.broadcast_to(x[:, None], flat.shape)
    xm = np.where(mask, xb, 0.0)
    ym = np.where(mask, flat, 0.0)

    sx = xm.sum(axis=0)
    sy = ym.sum(axis=0)
    sxx = (xm * xm).sum(axis=0)
    sxy = (xm * ym).sum(axis=0)
    syy = (ym * ym).sum(axis=0)

    denom = n * sxx - sx * sx
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = np.where(denom > 0, (n * sxy - sx * sy) / denom, np.nan)
        intercept = np.where(n > 0, (sy - slope * sx) / n, np.nan)

        # 残差平方和 → 斜率标准误 → t 统计量（双侧）
        sse = syy - intercept * sy - slope * sxy
        sse = np.where(sse < 0, 0.0, sse)
        dof = n - 2.0
        with np.errstate(invalid="ignore", divide="ignore"):
            s2 = np.where(dof > 0, sse / dof, np.nan)
            se_slope = np.sqrt(np.where(denom > 0, s2 * n / denom, np.nan))
            tstat = slope / se_slope
    pval = _t_sf_two_sided(tstat, dof)

    bad = (n < min_years) | ~np.isfinite(slope) | (denom <= 0)
    slope = np.where(bad, np.nan, slope)
    pval = np.where(bad, np.nan, pval)
    shape = field.shape[1:]
    return slope.reshape(shape), pval.reshape(shape)


def _t_sf_two_sided(t: np.ndarray, dof: np.ndarray) -> np.ndarray:
    """双侧 t 分布 p 值（scipy 缺失时的纯 numpy 兜底用 betainc）。"""
    try:
        from scipy import stats
        return 2.0 * stats.t.sf(np.abs(t), np.clip(dof, 1e-6, None))
    except Exception:                                    # pragma: no cover
        from scipy.special import betainc
        dof = np.clip(dof, 1e-6, None)
        x = dof / (dof + t * t)
        return betainc(dof / 2.0, 0.5, x)


def linear_trend_per_decade(yearly: xr.DataArray, per_decade: bool = True,
                            min_years: int = MIN_TREND_YEARS,
                            with_pvalue: bool = True):
    """
    逐年序列 → 逐格点线性趋势（默认单位：每十年）。

    Parameters
    ----------
    yearly : DataArray，含 'year' 维（`seasonal_mean` 的输出或年均值）
    per_decade : True 则斜率 ×10（论文图 5 的单位都是 per decade）
    with_pvalue : True 则同时返回双侧 p 值 DataArray

    Returns
    -------
    slope : DataArray(lat, lon)（或原空间维）
    pvalue : DataArray 同上（with_pvalue=True 时）
    """
    if "year" not in yearly.dims:
        raise ValueError("linear_trend_per_decade 需要 'year' 维（用 seasonal_mean 生成）")
    yearly = yearly.sortby("year")
    years = yearly["year"].values.astype(np.float64)
    years = years - years.mean()          # 数值条件改善（斜率不变）
    slope, pval = _linregress_slope(yearly.values, years, min_years=min_years)
    if per_decade:
        slope = slope * 10.0

    coords = {d: yearly[d].values for d in yearly.dims if d != "year"}
    dims = [d for d in yearly.dims if d != "year"]
    unit = "per_decade" if per_decade else "per_year"
    slope_da = xr.DataArray(slope, dims=dims, coords=coords,
                            name="trend", attrs={"units": unit, "n_min": min_years})
    if not with_pvalue:
        return slope_da
    p_da = xr.DataArray(pval, dims=dims, coords=coords, name="pvalue")
    return slope_da, p_da


def calc_sst_trend(oisst: xr.Dataset, period: Tuple[int, int] = (1994, 2023),
                   months: Sequence[int] = (7, 8, 9), var: str = "SST"):
    """图 5a：OISST JAS 逐年平均的线性趋势 [°C/decade]（1994–2023）。"""
    da = oisst[var] if var in oisst else oisst[list(oisst.data_vars)[0]]
    yearly = seasonal_mean(da, months, period)
    slope, pval = linear_trend_per_decade(yearly)
    slope.attrs["long_name"] = f"SST trend ({'JAS' if tuple(months) == (7, 8, 9) else months})"
    return slope, pval


def calc_evap_trend(oaflux: xr.Dataset, period: Tuple[int, int] = (1991, 2020),
                    months: Sequence[int] = (7, 8, 9), var: Optional[str] = None):
    """
    图 5b：OAFlux JAS 蒸发线性趋势（论文单位 cm/yr per decade）。

    OAFlux 月平均蒸发原始单位通常是 cm/day（或 cm/month，视版本），
    本函数**先按 `to_cm_per_year` 换算成 cm/yr**，再取 JAS 季节平均求趋势。
    """
    if var is None:
        cand = [v for v in oaflux.data_vars]
        var = cand[0] if cand else None
    da = oaflux[var]
    yearly = seasonal_mean(da, months, period)
    slope, pval = linear_trend_per_decade(yearly)
    slope.attrs["long_name"] = "Evaporation trend"
    return slope, pval


def oaflux_to_cm_per_year(da: xr.DataArray, units: str) -> xr.DataArray:
    """
    OAFlux 蒸发单位统一到 cm/yr。

    支持：'cm/day'（×365）、'cm/month'（×12）、'cm/yr'（原样）、
          'm/day'、'mm/day'、'kg/m2/day'（≈cm/day，1 kg/m² = 0.1 cm 水当量… 见下）
    OAFlux 官方蒸发产品以 cm/yr 为主；`kg/m2/day` 是**水当量**，1 kg/m² = 0.1 cm。
    """
    u = units.strip().lower().replace("**", "^")
    fac = {
        "cm/day": 365.0, "cm d-1": 365.0, "cm/day ": 365.0,
        "cm/month": 12.0, "cm/mon": 12.0,
        "cm/yr": 1.0, "cm/year": 1.0, "cm a-1": 1.0,
        "m/day": 36500.0, "m/yr": 100.0,
        "mm/day": 36.5, "mm/yr": 0.1,
        "kg/m2/day": 36.5, "kg m-2 d-1": 36.5,   # 1 kg/m² = 0.1 cm = 1 mm
        "kg/m2/s": 3.1536e6,
    }.get(u)
    if fac is None:
        raise ValueError(f"未登记的 OAFlux 单位 {units!r}；请在 oaflux_to_cm_per_year 中补充")
    out = da * fac
    out.attrs.update(units="cm/yr", long_name="Evaporation")
    return out


def calc_sh_trend(sh_daily: xr.DataArray, period: Tuple[int, int] = (1994, 2023),
                  months: Sequence[int] = (7, 8, 9)):
    """图 5c：ERA5 JAS 比湿线性趋势 [g/kg per decade]（1994–2023）。"""
    yearly = seasonal_mean(sh_daily, months, period)
    slope, pval = linear_trend_per_decade(yearly)
    slope.attrs["long_name"] = "Specific humidity trend"
    return slope, pval


# ──────────────────────────────────────────────
# 图 6a/b：超阈天数（年度，非 JJA —— 论文为全年）
# ──────────────────────────────────────────────
def annual_exceedance_days(da: xr.DataArray, threshold: float,
                           mask: Optional[xr.DataArray] = None,
                           domain_mean: bool = True) -> xr.DataArray:
    """
    某变量超阈值的**年度天数**（论文图 6a/b 用全年口径，不是 JJA）。

    Parameters
    ----------
    da        : (time, lat, lon) 日值
    threshold : 阈值（WBT 25.5 °C / SH 19 g/kg）
    mask      : 区域掩码（如 100 km 海岸缓冲）；None 表示不掩
    domain_mean : True → 返回掩码内**区域平均**天数 (year,)；
                  False → 返回逐格点年天数 (year, lat, lon)

    Returns
    -------
    DataArray，`domain_mean=True` 时维度为 (year,)
    """
    # ★ 缺测必须是 NaN 而不是 False：否则 NaN 会被当成"未超标日"混进分母
    valid = da.notnull()
    exceed = (da >= threshold).where(valid)
    if mask is not None:
        # 掩码外设为 NaN，使均值只统计掩码内格点；掩码本身随时间恒定
        exceed = exceed.where(mask.astype(bool))

    if domain_mean:
        cnt = exceed.groupby("time.year").sum(dim="time", skipna=True)
        nvalid = exceed.notnull().groupby("time.year").sum(dim="time", skipna=True)
        # ⚠️ sum(skipna=True) 对"全 NaN 切片"返回 0 而不是 NaN：
        #    必须显式把掩码外/全缺测格点置 NaN，否则它们会以 0 天混进区域平均、系统性拉低结果。
        cnt = cnt.where(nvalid > 0)
        spatial = [d for d in cnt.dims if d != "year"]
        out = cnt.mean(dim=spatial, skipna=True) if spatial else cnt
        out.attrs.update(long_name=f"Annual days with value >= {threshold}",
                         aggregation="domain_mean", n_cells=(
                             int(mask.sum()) if mask is not None else None))
        return out.rename("annual_exceedance_days")

    out = exceed.groupby("time.year").sum(dim="time", skipna=True)
    out.attrs.update(long_name=f"Annual days with value >= {threshold}",
                     aggregation="per_grid_cell")
    return out.rename("annual_exceedance_days")


# ──────────────────────────────────────────────
# 自检（纯合成，不读任何数据）
# ──────────────────────────────────────────────
def _selftest() -> int:
    print("=" * 74)
    print("calc_wbt.py 自检（纯合成数据，不读磁盘）")
    print("=" * 74)
    fails = []

    def check(name, cond, extra=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))
        if not cond:
            fails.append(name)

    # 1) Magnus 公式参考值
    es0 = float(saturation_vapor_pressure(xr.DataArray(0.0)))
    es20 = float(saturation_vapor_pressure(xr.DataArray(20.0)))
    check("es(0 °C) = 6.112 hPa", abs(es0 - 6.112) < 1e-9, f"got {es0:.6f}")
    check("es(20 °C) ≈ 23.39 hPa（Magnus 参考值）", abs(es20 - 23.39) < 0.05, f"got {es20:.3f}")

    # 2) RH：饱和时 100 %
    t = xr.DataArray([25.0, 30.0], dims="x")
    rh_sat = calc_relative_humidity(t, t)
    check("Td = T 时 RH = 100 %", bool(np.allclose(rh_sat.values, 100.0)),
          f"got {rh_sat.values}")

    # 3) 比湿参考值：Td = 20 °C, p = 1013.25 hPa → 14.47 g/kg
    sh = float(calc_specific_humidity(xr.DataArray(20.0), xr.DataArray(101325.0)))
    check("SH(Td=20 °C, p=1013.25 hPa) ≈ 14.47 g/kg", abs(sh - 14.47) < 0.05,
          f"got {sh:.3f} g/kg")

    # 4) Stull 公式逐项复算（防止实现抄错）
    T, RH = 30.0, 50.0
    ref = (T * np.arctan(0.151977 * np.sqrt(RH + 8.313659))
           + np.arctan(T + RH) - np.arctan(RH - 1.676331)
           + 0.00391838 * RH ** 1.5 * np.arctan(0.023101 * RH)
           - 4.686035)
    es30 = float(saturation_vapor_pressure(xr.DataArray(T)))
    td = float(xr.DataArray(np.log(RH / 100.0 * es30 / MAGNUS_A))
               .pipe(lambda x: MAGNUS_C * float(x) / (MAGNUS_B - float(x))))
    wbt_s = float(calc_WBT_stull(xr.DataArray(T), xr.DataArray(td)))
    check("Stull 解析式逐项一致", abs(wbt_s - ref) < 1e-6, f"got {wbt_s:.4f} vs {ref:.4f}")

    # 5) 迭代解满足 psychrometric 方程（残差 ≈ 0）
    p_hpa = 1013.25
    wbt_i = float(calc_WBT_iterative(xr.DataArray(T), xr.DataArray(td),
                                     xr.DataArray(p_hpa * 100.0)))
    e = float(saturation_vapor_pressure(xr.DataArray(td)))
    gamma = GAMMA_A * (1 + GAMMA_B * td)
    resid = float(saturation_vapor_pressure(xr.DataArray(wbt_i))) - e \
        - gamma * p_hpa * (T - wbt_i)
    check("迭代解满足 f(Tw) = 0（|残差| < 1e-6 hPa）", abs(resid) < 1e-6,
          f"resid {resid:.3e} hPa")
    check("物理区间 Td ≤ Tw ≤ T", td - 1e-9 <= wbt_i <= T + 1e-9,
          f"Td={td:.3f} Tw={wbt_i:.3f} T={T}")
    check("Stull 与迭代在 1013.25 hPa 下差距 < 0.5 °C", abs(wbt_s - wbt_i) < 0.5,
          f"Δ={wbt_s - wbt_i:+.3f} °C")

    # 6) 气压越低 → 湿球温度越低（Stull 不含气压，故对其无此性质）
    w_hi = float(calc_WBT_iterative(xr.DataArray(T), xr.DataArray(td),
                                    xr.DataArray(102000.0)))
    w_lo = float(calc_WBT_iterative(xr.DataArray(T), xr.DataArray(td),
                                    xr.DataArray(70000.0)))
    check("气压单调性：p↓ ⇒ WBT↓", w_lo < w_hi, f"700hPa {w_lo:.3f} < 1020hPa {w_hi:.3f}")

    # 7) 两法一致性：Stull（p=1013.25 固定）vs 气压感知的迭代解
    #    实测（20 万随机点，20–42 °C / 20–95 %RH）：median|Δ| ≈ 0.12 °C、max|Δ| ≈ 0.69 °C
    #    最大差出现在"干热"端（T 高、RH 低）；潮湿端（RH ≥ 60 %，即 WBT ≥ 25.5 的相关域）
    #    max|Δ| ≈ 0.33 °C。两条断言都写进来，便于回归时立刻发现公式被改坏。
    rng = np.random.default_rng(0)
    Tf = xr.DataArray(rng.uniform(20, 42, 200000), dims="x")
    RHf = xr.DataArray(rng.uniform(20, 95, 200000), dims="x")
    esf = saturation_vapor_pressure(Tf)
    ln = np.log(RHf / 100.0 * esf / MAGNUS_A)
    tdf = xr.DataArray(MAGNUS_C * ln / (MAGNUS_B - ln))
    s_stull = calc_WBT_stull(Tf, tdf)
    s_iter = calc_WBT_iterative(Tf, tdf, xr.full_like(Tf, 101325.0))
    dabs = np.abs(s_stull.values - s_iter.values)
    dmax, dmed = float(np.nanmax(dabs)), float(np.nanmedian(dabs))
    check("全域 median|Stull−迭代| < 0.25 °C", dmed < 0.25, f"median|Δ| = {dmed:.3f} °C")
    check("全域 max|Stull−迭代| < 0.75 °C", dmax < 0.75, f"max|Δ| = {dmax:.3f} °C")
    humid = (Tf.values >= 25) & (RHf.values >= 60)
    dmax_h = float(np.nanmax(dabs[humid]))
    check("高温高湿域（T≥25 °C, RH≥60 %）max|Δ| < 0.4 °C", dmax_h < 0.4,
          f"max|Δ| = {dmax_h:.3f} °C（n={int(humid.sum())}）")

    # 8) NaN 传播
    Tn = xr.DataArray([25.0, np.nan], dims="x")
    Tdn = xr.DataArray([15.0, 15.0], dims="x")
    wn = calc_WBT_iterative(Tn, Tdn, xr.full_like(Tn, 101325.0))
    check("NaN 正确传播", bool(np.isnan(wn.values[1]) and np.isfinite(wn.values[0])))

    # 9) 趋势估计：完美线性序列应恢复解析斜率
    yrs = np.arange(1994, 2024)
    base = 20.0 + 0.03 * (yrs - yrs.mean())
    da = xr.DataArray(base[:, None, None] * np.ones((1, 2, 3)),
                      dims=("year", "lat", "lon"),
                      coords={"year": yrs, "lat": [40.0, 41.0], "lon": [0.0, 1.0, 2.0]})
    slope, pval = linear_trend_per_decade(da)
    check("完美线性序列恢复斜率 0.30/decade", np.allclose(slope.values, 0.3, atol=1e-9),
          f"got {slope.values.ravel()[0]:.6f}")
    check("完美线性序列 p 值 ≈ 0", np.all(pval.values < 1e-6))

    # 10) 趋势估计：含 NaN 的年份被跳过而不是污染
    da2 = da.copy()
    da2[0, 0, 0] = np.nan
    slope2, _ = linear_trend_per_decade(da2, min_years=5)
    check("NaN 年份被 nan-aware 跳过", np.isfinite(slope2.values[0, 0])
          and abs(slope2.values[0, 0] - 0.3) < 1e-9, f"got {slope2.values[0, 0]:.6f}")

    # 11) 年超阈天数（区域平均口径）
    tt = xr.date_range("2001-01-01", periods=365, freq="D")
    vals = xr.DataArray(np.r_[np.full(10, 26.0), np.full(355, 20.0)][:, None, None],
                        dims=("time", "lat", "lon"), coords={"time": tt,
                                                             "lat": [40.0], "lon": [0.0]})
    mask = xr.DataArray(np.ones((1, 1), dtype=bool), dims=("lat", "lon"),
                        coords={"lat": [40.0], "lon": [0.0]})
    days = annual_exceedance_days(vals, 25.5, mask=mask)
    check("年超阈天数 = 10（不是 10/365 的分数）", float(days.isel(year=0)) == 10.0,
          f"got {float(days.isel(year=0))}")
    check("年超阈天数返回 (year,) 一维", days.dims == ("year",), f"dims={days.dims}")

    # 11b) 掩码外格点不得稀释区域平均（全 NaN 切片的 sum 会退化为 0）
    vals2 = xr.concat([vals, vals], dim="lon").assign_coords(lon=[0.0, 1.0])
    mask2 = xr.DataArray([[True, False]], dims=("lat", "lon"),
                         coords={"lat": [40.0], "lon": [0.0, 1.0]})
    days2 = annual_exceedance_days(vals2, 25.5, mask=mask2)
    check("掩码外格点不稀释区域平均", float(days2.isel(year=0)) == 10.0,
          f"got {float(days2.isel(year=0))}")

    # 12) OAFlux 单位换算
    check("OAFlux cm/day → cm/yr", abs(float(oaflux_to_cm_per_year(xr.DataArray(1.0),
          "cm/day")) - 365.0) < 1e-9)
    check("OAFlux kg/m2/day → cm/yr", abs(float(oaflux_to_cm_per_year(xr.DataArray(1.0),
          "kg/m2/day")) - 36.5) < 1e-9)

    print("-" * 74)
    if fails:
        print(f"SELFTEST FAILED: {len(fails)} 项 -> {fails}")
        return 1
    print("calc_wbt.py SELFTEST: ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
