# -*- coding: utf-8 -*-
"""phase6_selftest.py — Phase 6 新口径的**纯合成**自检（不读任何项目数据、不跑管线）。

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

mem = np.array(["001"] * 22 + ["002"] * 22 + ["003"] * 22)
ib = P._boot_indices(mem, 50, np.random.default_rng(4), "block")
check("block 索引矩阵形状正确", ib.shape == (50, 66))
check("block 每次抽样的成员数恒为 3 的整数倍（成员整体进出）",
      all(len(set(mem[ib[b]])) <= 3 for b in range(50)))
check("indep 索引在 [0,N) 内", idx_a.min() >= 0 and idx_a.max() < 66)

print()
print("=" * 74)
if FAIL:
    print(f"SELFTEST FAILED: {len(FAIL)} 项 -> {FAIL}")
    sys.exit(1)
print("ALL SELFTESTS PASSED")
