# -*- coding: utf-8 -*-
r"""phase6_selftest.py — Phase 6 新口径的**纯合成**自检（不读任何项目数据、不跑管线）。

覆盖 2026-09-23 拍板后新增/改动的三块逻辑：
  1) `_envelope_mask`（决策 1B：MHW 包络）——与观测侧
     `python/fig_jkl_mhw_envelope.py` 的判据 `any(a >= mi0 and b <= mi1)` 逐条对齐；
  2) `_mask_to_segments` —— 掩码 → 日段表 的往返一致；
  3) `_sweep_one` / `_boot_indices`（决策 2C/5A）——PR/FAR 与 inf 处理。

用法: python results\phase6_selftest.py      （期望末行 "ALL SELFTESTS PASSED"）
"""
import os
import sys

import numpy as np
import pandas as pd

BASE = r"D:\2607compound"
sys.path.insert(0, os.path.join(BASE, "python"))
import phase6_cesm as P  # noqa: E402

T0 = pd.Timestamp("2000-01-01")
NT = 60
FAIL = []


def check(name, cond, extra=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        FAIL.append(name)


def ev(pairs):
    """[(start_day, end_day)] -> 事件表（含端点，0-based 日索引）。"""
    return pd.DataFrame({
        "event_start": [T0 + pd.Timedelta(days=int(a)) for a, b in pairs],
        "event_end": [T0 + pd.Timedelta(days=int(b)) for a, b in pairs],
    })


def days(mask):
    return sorted(np.flatnonzero(mask).tolist())


print("=" * 74)
print("1) _envelope_mask（决策 1B：MHW 完全涵盖 >=1 个 THW -> 计 MHW 全部跨度天）")
print("=" * 74)

cases = [
    # (名称, THW 事件, MHW 事件, 期望复合日索引)
    ("MHW 完全涵盖单个 THW", [(10, 14)], [(8, 20)], list(range(8, 21))),
    ("MHW 恰好等于 THW", [(10, 14)], [(10, 14)], list(range(10, 15))),
    ("MHW 覆盖 THW 但不完全涵盖（尾部短）", [(10, 14)], [(10, 12)], []),
    ("MHW 覆盖 THW 但不完全涵盖（头部晚）", [(10, 14)], [(12, 20)], []),
    ("MHW 与 THW 有交集但无涵盖", [(10, 14)], [(14, 25)], []),
    ("MHW 完全不碰 THW", [(10, 14)], [(30, 35)], []),
    ("两个 THW，只涵盖其一", [(10, 12), (40, 45)], [(8, 20)], list(range(8, 21))),
    ("两个 MHW，只有一个涵盖", [(10, 14)], [(8, 20), (25, 30)], list(range(8, 21))),
    ("两个 MHW 各自涵盖一个 THW -> 并集",
     [(10, 14), (26, 28)], [(8, 20), (25, 35)],
     sorted(set(range(8, 21)) | set(range(25, 36)))),
    ("MHW 涵盖跨越 THW 之外的多天（包络口径的核心特征）",
     [(12, 13)], [(0, 59)], list(range(0, 60))),
    ("无 THW", [], [(8, 20)], []),
    ("无 MHW", [(10, 14)], [], []),
    ("跨越序列末端的 MHW 被裁剪", [(55, 58)], [(50, 200)], list(range(50, 60))),
]

for name, thw_iv, mhw_iv, want in cases:
    got = days(P._envelope_mask(ev(thw_iv) if thw_iv else None,
                                ev(mhw_iv) if mhw_iv else None, NT, T0))
    check(name, got == want, f"got={got[:6]}{'...' if len(got) > 6 else ''} want_len={len(want)}")

print()
print("=" * 74)
print("2) 与观测侧 fig_jkl_mhw_envelope.py 判据的等价性（随机 2000 例）")
print("=" * 74)


def ref_envelope(thw_iv, mhw_iv, nt):
    """逐字复刻 fig_jkl_mhw_envelope.py:53-60 的判据。"""
    acc = np.zeros(nt, dtype=bool)
    t_iv = [(a, b) for a, b in thw_iv]
    for ms, me in mhw_iv:
        if not t_iv:
            continue
        if any(a >= ms and b <= me for a, b in t_iv):
            acc[max(ms, 0):min(me, nt - 1) + 1] = True
    return sorted(np.flatnonzero(acc).tolist())


rng = np.random.default_rng(7)
mism = 0
for _ in range(2000):
    thw_iv = []
    for _ in range(rng.integers(0, 4)):
        a = int(rng.integers(0, NT))
        thw_iv.append((a, min(a + int(rng.integers(0, 8)), NT - 1)))
    mhw_iv = []
    for _ in range(rng.integers(0, 4)):
        a = int(rng.integers(0, NT))
        mhw_iv.append((a, min(a + int(rng.integers(0, 15)), NT - 1)))
    g1 = days(P._envelope_mask(ev(thw_iv) if thw_iv else None,
                               ev(mhw_iv) if mhw_iv else None, NT, T0))
    g2 = ref_envelope(thw_iv, mhw_iv, NT)
    if g1 != g2:
        mism += 1
check("2000 例随机用例与观测侧判据完全一致", mism == 0, f"mismatch={mism}")

print()
print("=" * 74)
print("3) _mask_to_segments 往返一致")
print("=" * 74)
ptab = {(3, 4): (41.0, 12.0, 300, 50)}
mask = np.zeros(NT, dtype=bool)
mask[5:12] = True
mask[20:21] = True
segs = P._mask_to_segments(mask, T0, None, ptab, (3, 4), (300, 50))
ok = (len(segs) == 2
      and segs[0]["thw_start"] == T0 + pd.Timedelta(days=5)
      and segs[0]["thw_end"] == T0 + pd.Timedelta(days=11)
      and segs[1]["thw_start"] == T0 + pd.Timedelta(days=20)
      and segs[0]["land_lat"] == 41.0 and segs[0]["land_lon"] == 12.0
      and segs[0]["ocean_lat_idx"] == 300 and segs[0]["ocean_lon_idx"] == 50)
check("掩码 -> 段表（含坐标与海点索引透传）", ok, f"segments={len(segs)}")

print()
print("=" * 74)
print("4) _sweep_one / _boot_indices（决策 2C / 5A）")
print("=" * 74)
ra = np.random.default_rng(1)
sa = ra.normal(30, 10, 66).clip(0, 120)
sf = ra.normal(8, 5, 66).clip(0, 120)
idx_a = P._boot_indices(np.array(["001"] * 22 + ["002"] * 22 + ["003"] * 22),
                        200, np.random.default_rng(2), "indep")
idx_f = P._boot_indices(np.array(["001"] * 22 + ["002"] * 22 + ["003"] * 22),
                        200, np.random.default_rng(3), "indep")
tab = P._sweep_one(sa, sf, idx_a, idx_f, np.arange(0, 101, 5), 200)
check("输出行长 = 阈值个数", len(tab) == 21, f"n={len(tab)}")
check("阈值 0 时 P_ALL=P_fix=1 且 FAR=0",
      np.isclose(tab.p_all.iloc[0], 1) and np.isclose(tab.p_fix.iloc[0], 1)
      and np.isclose(tab.FAR.iloc[0], 0))
check("p_all 与阈值单调不增",
      bool(np.all(np.diff(tab.p_all.values) <= 1e-12)))
check("PR 随阈值单调不减（在有限处）",
      bool(np.all(np.diff(tab.PR.replace([np.inf], np.nan).dropna().values) >= -1e-9)))
deep_x = float(max(sa.max(), sf.max()) + 1.0)
tab_d = P._sweep_one(sa, sf, idx_a, idx_f, np.array([deep_x]), 200).iloc[0]
check("两组都无样本 -> PR=nan（0/0 不是 inf）", np.isnan(tab_d.PR), f"P_all={tab_d.p_all:.3f} P_fix={tab_d.p_fix:.3f}")
sa2 = np.concatenate([sa, [1e6]])          # 让 ALL 组有样本、XGHG 组没有
tab_i = P._sweep_one(sa2, sf, P._boot_indices(np.zeros(len(sa2), int), 200,
                                              np.random.default_rng(5), "indep"),
                     idx_f, np.array([deep_x]), 200).iloc[0]
check("仅 FixGHG 组无样本 -> PR=inf 且 FAR=1",
      np.isinf(tab_i.PR) and np.isclose(tab_i.FAR, 1.0),
      f"P_all={tab_i.p_all:.4f} P_fix={tab_i.p_fix:.3f}")
check("0/0 记为 nan 而非 inf",
      np.isnan(P._sweep_one(np.array([0.0]), np.array([0.0]), np.zeros((1, 1), int),
                            np.zeros((1, 1), int), np.array([5.0]), 1).PR.iloc[0]))

# ★ 第三轮（F12）：FAR 的置信区间（Table 1 的先决条件）
check("输出含 FAR 置信区间列（FAR_lo/FAR_hi/FAR_*_fin）",
      {"FAR_lo", "FAR_hi", "FAR_lo_fin", "FAR_hi_fin"} <= set(tab.columns))
_fin_rows = tab[np.isfinite(tab.FAR.values)]
check("FAR 的 CI 包住点估计（有限行）",
      bool(np.all(_fin_rows.FAR_lo.values <= _fin_rows.FAR.values + 1e-12)
           and np.all(_fin_rows.FAR.values <= _fin_rows.FAR_hi.values + 1e-12)),
      f"n={len(_fin_rows)}/{len(tab)}")
check("阈值 0（FAR 恒 0）时 CI 退化为 [0, 0]",
      np.isclose(float(tab.FAR_lo.iloc[0]), 0.0)
      and np.isclose(float(tab.FAR_hi.iloc[0]), 0.0))
check("两组都无样本时 FAR 与区间同为 nan",
      np.isnan(tab_d.FAR) and np.isnan(tab_d.FAR_lo) and np.isnan(tab_d.FAR_hi))
check("仅 FixGHG 无样本时 FAR=1，区间上界亦为 1",
      np.isclose(float(tab_i.FAR), 1.0) and np.isclose(float(tab_i.FAR_hi), 1.0),
      f"FAR_lo={tab_i.FAR_lo:.3f} FAR_hi={tab_i.FAR_hi:.3f}")

mem = np.array(["001"] * 22 + ["002"] * 22 + ["003"] * 22)
ib = P._boot_indices(mem, 50, np.random.default_rng(4), "block")
check("block 索引矩阵形状正确", ib.shape == (50, 66))
check("block 每次抽样的成员数恒为 3 的整数倍（成员整体进出）",
      all(len(set(mem[ib[b]])) <= 3 for b in range(50)))
check("indep 索引在 [0,N) 内", idx_a.min() >= 0 and idx_a.max() < 66)

print()
print("=" * 74)
print("5) 文件发现兼容 gdex 命名 + 坐标名归一（第三轮 F10/F11）")
print("=" * 74)

import shutil          # noqa: E402
import tempfile        # noqa: E402

import xarray as xr    # noqa: E402

_tmp = tempfile.mkdtemp(prefix="p6selftest_")
_old_proc = P.CESM_PROC_DIR
try:
    P.CESM_PROC_DIR = _tmp
    # 001 用 gdex 命名、002 用 aws/trim 命名（两者必须都被认出，且不互相串号）
    for _n in ("trefht_all_001_2000-2021.nc", "TREFHT_all_002_2000-2021_europe.nc",
               "trefht_xghg_001_2000-2021.nc", "sst_all_001_2000-2021.nc",
               "sst_xghg_001_2000-2021.nc"):
        open(os.path.join(_tmp, _n), "w", encoding="utf-8").close()

    check("认出 gdex 名（T2m ALL 001）",
          len(P.find_t2m_segments("ALL", "001")) == 1,
          f"got={[os.path.basename(x) for x in P.find_t2m_segments('ALL', '001')]}")
    check("依旧认 aws 名（T2m ALL 002）且不串号",
          len(P.find_t2m_segments("ALL", "002")) == 1,
          f"got={[os.path.basename(x) for x in P.find_t2m_segments('ALL', '002')]}")
    check("认出 gdex 名（T2m XGHG 001）",
          len(P.find_t2m_segments("XGHG", "001")) == 1)
    check("认出 gdex 名（SST ALL 001 / XGHG 001）",
          len(P.find_sst_segments("ALL", "001")) == 1
          and len(P.find_sst_segments("XGHG", "001")) == 1)
    check("不存在的成员返回空列表（不误报）",
          len(P.find_t2m_segments("ALL", "019")) == 0
          and len(P.find_sst_segments("XGHG", "019")) == 0)

    _da = xr.DataArray(np.zeros((2, 3)), dims=("latitude", "longitude"))
    check("_norm_latlon 把 latitude/longitude 统一为 lat/lon",
          set(P._norm_latlon(_da).dims) == {"lat", "lon"})
    check("F10 校正常量已定义（POP SST 标签整体回退 1 天）",
          P.SST_TIME_LABEL_SHIFT_DAYS == -1)
finally:
    P.CESM_PROC_DIR = _old_proc
    shutil.rmtree(_tmp, ignore_errors=True)

print()
print("=" * 74)
print("6) gev 子命令的辅助函数（第八批：图4 的三类年暴露序列）")
print("=" * 74)
_pairs = pd.DataFrame({
    "land_lat_idx": [0, 0, 1, 2], "land_lon_idx": [0, 1, 0, 0],
    "ocean_lat_idx": [9, 9, 8, 9], "ocean_lon_idx": [9, 9, 8, 9],
    "land_lat": [40.0, 40.0, 35.0, 50.0], "land_lon": [10.0, 10.0, 6.0, 30.0],
    "ocean_lat": [40.1, 40.1, 35.1, 50.1], "ocean_lon": [10.1, 10.1, 6.1, 30.1],
    "dist_deg": [0.1, 0.1, 0.1, 0.1]})
_med = (_pairs.land_lat.between(30, 47) & _pairs.land_lon.between(5, 42)).values
check("区域掩码只选中框内陆点（4 对里 3 对）", int(_med.sum()) == 3, f"got {int(_med.sum())}")

_ev = pd.DataFrame({
    "event_start": pd.to_datetime(["2000-01-01", "2000-01-10", "2000-01-05"]),
    "event_end": pd.to_datetime(["2000-01-03", "2000-01-12", "2000-01-06"]),
    "lat_idx": [9, 9, 8], "lon_idx": [9, 9, 8]})
_masks = P._event_masks_by_key(_ev, {(9, 9), (8, 8)}, NT, T0)
check("事件表 → 掩码只保留 keys 里的键（2 个）", set(_masks) == {(9, 9), (8, 8)},
      f"got {sorted(_masks)}")
check("掩码长度 = 时间轴长度", all(len(m) == NT for m in _masks.values()))
check("掩码天数与事件跨度一致（(9,9) 共 3+3=6 天）", int(_masks[(9, 9)].sum()) == 6,
      f"got {int(_masks[(9, 9)].sum())}")

# 合成的"年份"轴：3 个 20 天桶（2000/2001/2002），事件全落在第一个桶内
_years = np.array([2000] * 20 + [2001] * 20 + [2002] * 20)
_ann, _uy = P._annual_exposure_from_masks(_masks, [(9, 9), (8, 8)], _years)
check("年暴露矩阵形状 = (n_year, n_key)", _ann.shape == (3, 2), f"got {_ann.shape}")
check("年份轴 = 唯一值升序", list(_uy) == [2000, 2001, 2002], f"got {list(_uy)}")
check("事件所在年份合计正确（(9,9)=6、(8,8)=2）",
      _ann[0].tolist() == [6, 2], f"got {_ann[0].tolist()}")
check("无事件的年份为 0（而非 NaN）", _ann[1].sum() == 0 and _ann[2].sum() == 0,
      f"got {_ann[1].tolist()} / {_ann[2].tolist()}")
check("含事件但未被选中的键不参与统计（键集合外无列）", _ann.shape[1] == 2)
check("空事件表返回空字典", P._event_masks_by_key(pd.DataFrame(
    columns=["event_start", "event_end", "lat_idx", "lon_idx"]), {(9, 9)}, NT, T0) == {})

print()
print("=" * 74)
if FAIL:
    print(f"SELFTEST FAILED: {len(FAIL)} 项 -> {FAIL}")
    sys.exit(1)
print("ALL SELFTESTS PASSED")
