"""
gev_return_period.py — GEV 重现期分析（论文图 4 与图 6c 的数值内核）

论文口径（`results/paper_text.txt` 与 `TECHNICAL_SPEC.md` §3.9b）：

  图 4（三面板，地中海 & 黑海，ALL vs FixGHG）
      a 沿海海洋热浪天数 / b 沿海陆地热浪天数 / c 复合 MHW–THW 天数
      ① 对 FixGHG 年值做 1000 次有放回 bootstrap，每次 **MLE 拟合 GEV**，
         由逆 CDF 求 5/10/20/50/100 年重现水平 → 中位数 + 2.5–97.5% CI；
      ② 把 FixGHG 各重现水平映射为 ALL 的**等效重现期**，对 ALL 同样 bootstrap；
      ③ "Gap" = FixGHG 重现期 − ALL 等效重现期（论文原图 c 面板的红色标注）。

  图 6c（WBT 22–28 °C 的重现期，JJA 窗口）
      "Return periods (in years) of extreme wet-bulb temperatures in the range
       of 22 − 28 °C"，复合年（2003/2022/2023）vs 非复合年（如 2000）。

⚠️ 两处论文未明示、由本模块定口径并登记为决策（复现报告 D9）：
  1. **图 6c 的样本序列**：默认 = 该年 **JJA 逐日 WBT 的区域平均序列**（90 个值/年），
     与该年图 6a/b 的"区域平均"口径一致；另有 `spatial='per_cell'`（逐格点拟合后再平均）。
  2. **置信区间**：图 4 用 `GEV_CI = (2.5%, 97.5%)`；图 3 的 FAR/PR 用 5–95%，两者勿混。
     图 6c 原图未画 CI，本模块仍输出，供报告使用。

实现要点
--------
* `scipy.stats.genextreme` 的 `c` 参数是"标准 GEV 形状参数 ξ 的相反数"，本模块一律
  用 scipy 约定，不自行换号，避免两套符号混用。
* 重现期 = 1 / (1 − F(x))；F→1 时返回 `inf`（不是 NaN）。
* 分位数用**次序统计量**（`_emp_quantile`），避免 `np.percentile` 在两端含 inf 时
  算出 `inf − inf = nan`（与 `phase6_cesm.py::_emp_quantile` 同一处理）。
* `genextreme.fit` 偶有不收敛（尤其样本极小/全同值）：失败样本被**丢弃并计数**，
  若有效样本 < `MIN_FIT_SAMPLES` 则整条曲线返回 NaN，并打印警告——不静默伪造结果。
"""
from __future__ import annotations

import os
import sys
import warnings
from typing import Dict, Iterable, Optional, Sequence, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import N_BOOTSTRAP, GEV_RETURN_PERIODS, GEV_CI  # noqa: E402

MIN_FIT_SAMPLES = 8          # GEV MLE 至少需要这么多有效样本（3 参数）
DEFAULT_BLOCK_DAYS = 7       # 图 6c 的日序列用移动块 bootstrap 保自相关


# ──────────────────────────────────────────────
# 基础：拟合 / 逆 CDF / 重现期
# ──────────────────────────────────────────────
def fit_gev(values: np.ndarray):
    """
    MLE 拟合 GEV。

    Returns
    -------
    (c, loc, scale) 或 None（样本不足 / 不收敛 / 参数非法）
    """
    from scipy.stats import genextreme

    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < MIN_FIT_SAMPLES or np.allclose(v, v[0]):
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c, loc, scale = genextreme.fit(v)
    except Exception:
        return None
    if not (np.isfinite(c) and np.isfinite(loc) and np.isfinite(scale)) or scale <= 0:
        return None
    return float(c), float(loc), float(scale)


def return_level(params, rp: float) -> float:
    """给定重现期 rp（年）→ 重现水平（变量单位）。"""
    from scipy.stats import genextreme

    c, loc, scale = params
    p = 1.0 - 1.0 / float(rp)
    return float(genextreme.ppf(p, c, loc=loc, scale=scale))


def return_period(params, level: float) -> float:
    """给定变量水平 → 重现期（年）；F(level) ≥ 1 时返回 inf。"""
    from scipy.stats import genextreme

    c, loc, scale = params
    p = float(genextreme.cdf(level, c, loc=loc, scale=scale))
    if not np.isfinite(p):
        return np.nan
    if p >= 1.0:
        return np.inf
    if p <= 0.0:
        return np.nan
    return 1.0 / (1.0 - p)


def _emp_quantile(a: np.ndarray, q: float) -> float:
    """
    次序统计量分位数（对 inf 安全；`np.percentile` 在两端含 inf 时会给出 nan）。
    """
    x = np.asarray(a, dtype=np.float64)
    x = x[~np.isnan(x)]
    if x.size == 0:
        return np.nan
    x = np.sort(x)
    if x.size == 1:
        return float(x[0])
    pos = q * (x.size - 1)
    lo = int(np.floor(pos))
    hi = int(np.ceil(pos))
    if lo == hi:
        return float(x[lo])
    w = pos - lo
    return float((1 - w) * x[lo] + w * x[hi])


def _bootstrap_indices(n: int, n_boot: int, seed: int,
                       block: Optional[int] = None) -> np.ndarray:
    """
    (n_boot, n) 索引矩阵。

    block=None  → 经典有放回重采样（独立样本；图 4 的"模型年"口径）
    block=k     → 移动块 bootstrap（长度 k，环状），用于图 6c 的日序列
    """
    rng = np.random.default_rng(seed)
    if block is None or int(block) <= 1:
        return rng.integers(0, n, size=(int(n_boot), int(n)))
    k = int(block)
    n_blocks = int(np.ceil(n / k))
    starts = rng.integers(0, n, size=(int(n_boot), n_blocks))
    idx = (starts[:, :, None] + np.arange(k)[None, None, :]) % n
    return idx.reshape(int(n_boot), n_blocks * k)[:, :n]


# ──────────────────────────────────────────────
# 图 4 第一步：FixGHG 重现水平
# ──────────────────────────────────────────────
def fit_return_levels(annual_values: np.ndarray,
                      n_bootstrap: int = N_BOOTSTRAP,
                      seed: int = 42,
                      rps: Sequence[float] = GEV_RETURN_PERIODS,
                      ci: Tuple[float, float] = GEV_CI) -> Dict:
    """
    FixGHG（或任意一组）年值 → GEV 重现水平分布（1000 次 bootstrap + MLE）。

    Returns
    -------
    dict:
        rp            : {rp: {'median','ci_lower','ci_upper'}}  点估计 + CI
        rp_samples    : {rp: ndarray(n_valid_boot,)}            原始 bootstrap 样本
        n_valid       : 成功拟合的 bootstrap 次数
        n_failed      : 失败的 bootstrap 次数
        point_params  : 全样本拟合的 (c, loc, scale) 或 None
        n_years       : 去缺测后的年数
    """
    vals = np.asarray(annual_values, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    out = {"n_years": int(vals.size), "n_valid": 0, "n_failed": 0,
           "rp": {float(rp): {"median": np.nan, "ci_lower": np.nan, "ci_upper": np.nan}
                  for rp in rps},
           "rp_samples": {float(rp): np.array([]) for rp in rps},
           "point_params": fit_gev(vals)}

    if vals.size < MIN_FIT_SAMPLES:
        print(f"  [GEV] 样本仅 {vals.size} 个（< {MIN_FIT_SAMPLES}），无法拟合，返回 NaN")
        return out

    idx = _bootstrap_indices(vals.size, n_bootstrap, seed)
    samples = {float(rp): [] for rp in rps}
    n_failed = 0
    for b in range(idx.shape[0]):
        params = fit_gev(vals[idx[b]])
        if params is None:
            n_failed += 1
            continue
        for rp in rps:
            samples[float(rp)].append(return_level(params, rp))

    n_valid = int(n_bootstrap) - n_failed
    out["n_valid"], out["n_failed"] = n_valid, n_failed
    if n_valid == 0:
        print("  [GEV] 全部分 bootstrap 拟合失败，返回 NaN")
        return out
    for rp in rps:
        arr = np.asarray(samples[float(rp)], dtype=np.float64)
        out["rp_samples"][float(rp)] = arr
        out["rp"][float(rp)] = {
            "median": _emp_quantile(arr, 0.5),
            "ci_lower": _emp_quantile(arr, ci[0]),
            "ci_upper": _emp_quantile(arr, ci[1]),
        }
    return out


# ──────────────────────────────────────────────
# 图 4 第二步：FixGHG 重现水平 → ALL 等效重现期
# ──────────────────────────────────────────────
def map_return_period(all_annual: np.ndarray,
                      return_levels: Dict,
                      n_bootstrap: int = N_BOOTSTRAP,
                      seed: int = 43,
                      ci: Tuple[float, float] = GEV_CI) -> Dict:
    """
    FixGHG 各重现水平 → ALL 的等效重现期（对 ALL 重复 bootstrap 估计不确定性）。

    ★ 不确定性的双向传播（比 TECHNICAL_SPEC §3.9b 的草稿更严格）：
      第 b 次抽样同时取
        · ALL 的第 b 个 bootstrap 拟合（本函数），
        · FixGHG 的第 b 个 bootstrap 重现水平（`return_levels['rp_samples']`，若可用；
          否则退化为用其中位数）。
      这样 CI 同时含"ALL 拟合不确定性"与"FixGHG 重现水平不确定性"。

    Returns
    -------
    dict: {rp: {'median','ci_lower','ci_upper'}}（单位：年）
    """
    vals = np.asarray(all_annual, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    rps = list(return_levels["rp"].keys())
    res = {float(rp): {"median": np.nan, "ci_lower": np.nan, "ci_upper": np.nan}
           for rp in rps}
    if vals.size < MIN_FIT_SAMPLES:
        print(f"  [GEV] ALL 样本仅 {vals.size} 个（< {MIN_FIT_SAMPLES}），返回 NaN")
        return res

    idx = _bootstrap_indices(vals.size, n_bootstrap, seed)
    acc = {float(rp): [] for rp in rps}
    n_failed = 0
    for b in range(idx.shape[0]):
        params = fit_gev(vals[idx[b]])
        if params is None:
            n_failed += 1
            continue
        for rp in rps:
            st = return_levels["rp"][float(rp)]
            lvl = st["median"]
            arr = return_levels.get("rp_samples", {}).get(float(rp))
            if arr is not None and len(arr) > 0:
                lvl = float(arr[b % len(arr)])       # 同步索引，传播 FixGHG 不确定性
            if not np.isfinite(lvl):
                continue
            acc[float(rp)].append(return_period(params, lvl))

    if n_failed:
        print(f"  [GEV] ALL bootstrap 拟合失败 {n_failed}/{n_bootstrap} 次（已丢弃）")
    for rp in rps:
        arr = np.asarray(acc[float(rp)], dtype=np.float64)
        if arr.size == 0:
            continue
        res[float(rp)] = {"median": _emp_quantile(arr, 0.5),
                          "ci_lower": _emp_quantile(arr, ci[0]),
                          "ci_upper": _emp_quantile(arr, ci[1])}
    return res


def compute_gap(return_levels: Dict, mapped: Dict) -> Dict:
    """
    图 4c 的 "Gap" 标注 = FixGHG 重现期 − ALL 等效重现期（单位：年）。

    只统计**有限**的 ALL 等效重现期：若 ALL 下该水平的重现期为 inf（永不发生），
    Gap 无有限值，返回 inf 并单独计数。
    """
    out = {}
    for rp, st in mapped.items():
        a = st["median"]
        out[float(rp)] = float(rp) - a if np.isfinite(a) else np.inf
    return out


# ──────────────────────────────────────────────
# 图 4 一站式：三类事件 → 三面板
# ──────────────────────────────────────────────
def analyse_return_periods(all_annual: np.ndarray, fixghg_annual: np.ndarray,
                           n_bootstrap: int = N_BOOTSTRAP,
                           seed_fix: int = 42, seed_all: int = 43,
                           rps: Sequence[float] = GEV_RETURN_PERIODS,
                           ci: Tuple[float, float] = GEV_CI) -> Dict:
    """一次算完一个面板所需的全部量（FixGHG 水平 + ALL 等效重现期 + Gap）。"""
    lv = fit_return_levels(fixghg_annual, n_bootstrap=n_bootstrap, seed=seed_fix,
                           rps=rps, ci=ci)
    mapped = map_return_period(all_annual, lv, n_bootstrap=n_bootstrap,
                               seed=seed_all, ci=ci)
    return {"fixghg": lv, "all": mapped, "gap": compute_gap(lv["rp"], mapped),
            "n_years_all": int(np.isfinite(np.asarray(all_annual, dtype=float)).sum()),
            "n_years_fixghg": lv["n_years"]}


# ──────────────────────────────────────────────
# 图 6c：WBT 阈值 → 重现期曲线（逐年 / 逐组）
# ──────────────────────────────────────────────
def gev_return_period_curve(values: np.ndarray,
                            thresholds: Iterable[float],
                            n_bootstrap: int = N_BOOTSTRAP,
                            seed: int = 44,
                            ci: Tuple[float, float] = GEV_CI,
                            block: Optional[int] = DEFAULT_BLOCK_DAYS) -> Dict:
    """
    单条曲线：给定一串日值（如某年 JJA 的区域平均 WBT）→ 各阈值的重现期。

    RP(x) = 1 / (1 − F(x))，F 为该序列拟合的 GEV CDF；
    CI 由 bootstrap（日序列默认**移动块**，块长 7 天，保留自相关）给出。

    Returns
    -------
    dict: thresholds / rp / rp_lo / rp_hi / n_valid_boot / n_failed / params
    """
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    thr = np.asarray(list(thresholds), dtype=np.float64)
    res = {"thresholds": thr, "rp": np.full(thr.size, np.nan),
           "rp_lo": np.full(thr.size, np.nan), "rp_hi": np.full(thr.size, np.nan),
           "n_valid_boot": 0, "n_failed": 0, "params": fit_gev(v),
           "n_samples": int(v.size)}
    if v.size < MIN_FIT_SAMPLES or res["params"] is None:
        return res

    res["rp"] = np.array([return_period(res["params"], x) for x in thr])

    idx = _bootstrap_indices(v.size, n_bootstrap, seed, block=block)
    acc = np.full((idx.shape[0], thr.size), np.nan)
    n_failed = 0
    for b in range(idx.shape[0]):
        params = fit_gev(v[idx[b]])
        if params is None:
            n_failed += 1
            continue
        for j, x in enumerate(thr):
            acc[b, j] = return_period(params, x)
    res["n_valid_boot"] = int(idx.shape[0]) - n_failed
    res["n_failed"] = n_failed
    if res["n_valid_boot"] > 0:
        good = acc[~np.isnan(acc).all(axis=1)]
        for j in range(thr.size):
            col = good[:, j]
            res["rp_lo"][j] = _emp_quantile(col, ci[0])
            res["rp_hi"][j] = _emp_quantile(col, ci[1])
    return res


def domain_mean_series(field, spatial_dims: Sequence[str] = ("lat", "lon")):
    """(time, lat, lon) → (time,) 区域平均（跳过 NaN 格点）。"""
    return field.mean(dim=[d for d in spatial_dims if d in field.dims], skipna=True)


# ──────────────────────────────────────────────
# 自检（纯合成，不读数据）
# ──────────────────────────────────────────────
def _selftest() -> int:
    print("=" * 74)
    print("gev_return_period.py 自检（纯合成数据，不读磁盘）")
    print("=" * 74)
    fails = []

    def check(name, cond, extra=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))
        if not cond:
            fails.append(name)

    from scipy.stats import genextreme

    # 1) 已知 GEV 的参数恢复（大样本）
    rng = np.random.default_rng(7)
    c_true, loc_true, sc_true = -0.1, 20.0, 2.0
    sample = genextreme.rvs(c_true, loc=loc_true, scale=sc_true, size=20000, random_state=rng)
    params = fit_gev(sample)
    check("大样本 GEV 参数可恢复（|Δc|<0.05, |Δloc|<0.3, |Δscale|<0.2）",
          params is not None and abs(params[0] - c_true) < 0.05
          and abs(params[1] - loc_true) < 0.3 and abs(params[2] - sc_true) < 0.2,
          f"got c={params[0]:.3f} loc={params[1]:.2f} scale={params[2]:.2f}" if params else "fit=None")

    # 2) return_level / return_period 互逆
    lv20 = return_level(params, 20)
    rp_back = return_period(params, lv20)
    check("return_level ↔ return_period 互逆", abs(rp_back - 20) < 1e-6,
          f"RP(level(20)) = {rp_back:.6f}")

    # 3) 重现期随阈值单调上升（阈值越高 → 越稀有 → 重现期越长）
    thr = np.arange(22.0, 28.01, 0.5)
    curve = gev_return_period_curve(sample, thr, n_bootstrap=200, seed=1)
    rp = curve["rp"]
    check("重现期随阈值单调不减", bool(np.all(np.diff(rp) >= -1e-9)), f"rp={np.round(rp, 2)}")
    check("bootstrap 有效次数 = 200", curve["n_valid_boot"] == 200,
          f"got {curve['n_valid_boot']}（failed {curve['n_failed']}）")
    check("CI 下界 ≤ 中位点估计 ≤ 上界",
          bool(np.all(curve["rp_lo"] <= curve["rp"] + 1e-9)
               and np.all(curve["rp"] <= curve["rp_hi"] + 1e-9)))

    # 4) 次序统计量分位数对 inf 安全（np.percentile 会给出 nan）
    arr = np.array([1.0, 2.0, np.inf, np.inf, np.inf])
    q = _emp_quantile(arr, 0.975)
    check("含 inf 样本的分位数不产生 nan", not np.isnan(q) and q == np.inf, f"got {q}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")           # 对照组：np.percentile 会 RuntimeWarning + nan
        q_np = np.percentile(arr, 97.5)
    check("np.percentile 在同一输入下退化为 nan（对照）", np.isnan(q_np), f"got {q_np}")

    # 5) 位移分布的等效重现期应显著短于原分布
    warm = genextreme.rvs(c_true, loc=loc_true + 3.0, scale=sc_true, size=400,
                          random_state=rng)
    lv = fit_return_levels(genextreme.rvs(c_true, loc=loc_true, scale=sc_true,
                                          size=400, random_state=rng),
                           n_bootstrap=200, seed=2)
    mapped = map_return_period(warm, lv, n_bootstrap=200, seed=3)
    gaps = compute_gap(lv["rp"], mapped)
    check("增暖后等效重现期缩短（100 年事件 → 更短）",
          mapped[100.0]["median"] < 100.0, f"ALL RP(100y level) = {mapped[100.0]['median']:.1f} y")
    check("Gap(100) > 0", gaps[100.0] > 0, f"Gap = {gaps[100.0]:.1f} y")

    # 6) 样本不足时返回 NaN 而不是抛异常
    small = fit_return_levels(np.array([1.0, 2.0, 3.0]), n_bootstrap=10, seed=4)
    check("样本不足 → NaN（不抛异常）", np.isnan(small["rp"][100.0]["median"]))

    # 7) 常数列不产生伪拟合
    check("常数列拟合返回 None", fit_gev(np.full(50, 3.0)) is None)

    # 8) 移动块 bootstrap 保长度、保自相关结构
    idxb = _bootstrap_indices(90, 5, seed=9, block=7)
    check("块 bootstrap 形状正确", idxb.shape == (5, 90))
    check("块 bootstrap 索引在 [0,90) 内", bool(idxb.min() >= 0 and idxb.max() < 90))

    # 9) analyse_return_periods 端到端
    res = analyse_return_periods(warm, genextreme.rvs(c_true, loc=loc_true,
                                                      scale=sc_true, size=400,
                                                      random_state=rng),
                                 n_bootstrap=100, seed_fix=5, seed_all=6)
    check("analyse_return_periods 三件套齐全",
          set(res.keys()) == {"fixghg", "all", "gap", "n_years_all", "n_years_fixghg"})
    check("FixGHG 100 年重现水平 ≈ loc+scale·(−ln(−ln(0.99))) 量级",
          np.isfinite(res["fixghg"]["rp"][100.0]["median"]))

    print("-" * 74)
    if fails:
        print(f"SELFTEST FAILED: {len(fails)} 项 -> {fails}")
        return 1
    print("gev_return_period.py SELFTEST: ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
