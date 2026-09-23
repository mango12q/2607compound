# -*- coding: utf-8 -*-
"""Lead 独立复核脚本（D 任务）— 只读，不写任何既有产物。

用法: python results\phase6_audit_lead_check.py
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

BASE = r"D:\2607compound"
CESM_INT = os.path.join(BASE, "results", "intermediate", "cesm")
sys.path.insert(0, os.path.join(BASE, "python"))
import config as C  # noqa: E402

pd.set_option("display.width", 160)


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# --------------------------------------------------------------------------
hr("【L1】thresh_t2m_xghg.npz vs thresh_sst_xghg.npz —— shape 与行内离散度")
z_t = np.load(os.path.join(CESM_INT, "thresh_t2m_xghg.npz"))
z_s = np.load(os.path.join(CESM_INT, "thresh_sst_xghg.npz"))
print("t2m npz keys:", z_t.files, {k: z_t[k].shape for k in z_t.files})
print("sst npz keys:", z_s.files, {k: z_s[k].shape for k in z_s.files})

thr_t = z_t["thresh"]
print(f"\nT2m thresh shape={thr_t.shape} dtype={thr_t.dtype}")
ptp = np.nanmax(thr_t, axis=1) - np.nanmin(thr_t, axis=1)
print(f"  每行(doy)内 max-min: min={np.nanmin(ptp):.6g} max={np.nanmax(ptp):.6g} "
      f"全零? {bool(np.all(ptp[~np.isnan(ptp)] == 0))}")
print(f"  第 0 行前 8 个值: {thr_t[0, :8]}")
print(f"  第 100 行前 8 个值: {thr_t[100, :8]}")
print(f"  跨 doy 取值范围: {np.nanmin(thr_t):.2f} .. {np.nanmax(thr_t):.2f} degC")

thr_s = z_s["thresh"]
ptp_s = np.nanmax(thr_s, axis=1) - np.nanmin(thr_s, axis=1)
print(f"\nSST thresh shape={thr_s.shape}, 每行内 max-min: "
      f"min={np.nanmin(ptp_s):.3f} max={np.nanmax(ptp_s):.3f} "
      f"(全零? {bool(np.all(ptp_s[~np.isnan(ptp_s)] == 0))})")
print(f"  跨 doy 取值范围: {np.nanmin(thr_s):.2f} .. {np.nanmax(thr_s):.2f}")

# --------------------------------------------------------------------------
hr("【L2】用代码原逻辑重算 T2m 阈值，证明 axis 崩溃：stacked 是 (11*nland,)")
pairs = pd.read_csv(os.path.join(CESM_INT, "coastal_pairs_cesm.csv"))
print(f"配对表: {pairs.shape[0]} 行 / 唯一陆点 "
      f"{pairs[['land_lat_idx','land_lon_idx']].drop_duplicates().shape[0]} / "
      f"唯一海点 {pairs[['ocean_lat_idx','ocean_lon_idx']].drop_duplicates().shape[0]}")
print("dist_deg: min=%.4f median=%.4f max=%.4f" % (
    pairs.dist_deg.min(), pairs.dist_deg.median(), pairs.dist_deg.max()))
dup = pairs.groupby(["ocean_lat_idx", "ocean_lon_idx"]).size()
print(f"海点复用: {int((dup > 1).sum())} 个海点被 >1 个陆点共用, 最多 {int(dup.max())} 个陆点")

pj = pairs.land_lat_idx.values
pi = pairs.land_lon_idx.values
chunks = []
for m in ("001", "002", "003"):
    ds = xr.open_dataset(os.path.join(CESM_INT, f"XGHG_{m}_T2m.nc"))
    da = ds["T2m"].isel(lat=xr.DataArray(pj, dims="p"), lon=xr.DataArray(pi, dims="p"))
    arr = da.transpose("time", "p").values.astype(np.float64)
    chunks.append((arr, pd.DatetimeIndex(da.time.values).dayofyear.values))
    ds.close()
doy_all = np.concatenate([d for _, d in chunks])
mat = np.concatenate([v for v, _ in chunks], axis=0)
nland = mat.shape[1]
print(f"池矩阵 mat: {mat.shape}  (3 成员 × 22 年 noleap = {3*22*365} 天?) 实际 {mat.shape[0]}")

single = np.full((366, nland), np.nan)
for d in np.arange(1, 366):
    rows = mat[doy_all == d]
    if len(rows):
        single[d - 1] = np.nanpercentile(rows, 90, axis=0)

# --- 现状（原代码）---
thresh_bug = np.full_like(single, np.nan)
for d in np.arange(1, 366):
    win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
    stacked = np.concatenate([single[w - 1] for w in win], axis=0)
    thresh_bug[d - 1] = np.nanpercentile(stacked, 90, axis=0)
print(f"原代码 stacked 形状 = {(11 * nland,)}, percentile(axis=0) 标量 -> "
      f"thresh 每行全等: {bool(np.allclose(thresh_bug, thresh_bug[:, :1]))}")

# --- 修法 A：只在 axis 上改对（对 11 个 '逐日分位' 再取分位）---
thrA = np.full_like(single, np.nan)
for d in np.arange(1, 366):
    win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
    stack2 = np.stack([single[w - 1] for w in win], axis=0)      # (11, nland)
    thrA[d - 1] = np.nanpercentile(stack2, 90, axis=0)

# --- 修法 B：heatwaveR ts2clm 语义（窗内合并原始样本再取分位）---
# 用轮转后的池矩阵一次性算：对每个 doy，取 11 天窗的全部原始样本 (11*nmemb*nyr, nland)
mat_by_doy = {d: mat[doy_all == d] for d in np.arange(1, 366)}
thrB = np.full_like(single, np.nan)
for d in np.arange(1, 366):
    win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
    pool = np.concatenate([mat_by_doy.get(w, mat[:0]) for w in win], axis=0)
    thrB[d - 1] = np.nanpercentile(pool, 90, axis=0)

print("\n阈值对比 (°C, 全 366 doy × 206 点):")
for name, thr in (("现状(bug)", thresh_bug), ("修法A(分位再分位)", thrA),
                  ("修法B(=heatwaveR 窗内合并)", thrB)):
    print(f"  {name:26s} mean={np.nanmean(thr):7.3f} "
          f"min={np.nanmin(thr):7.3f} max={np.nanmax(thr):7.3f}")
d_bug_B = thresh_bug - thrB
d_A_B = thrA - thrB
print(f"  现状 - 修法B : mean={np.nanmean(d_bug_B):+.3f} "
      f"p5={np.nanpercentile(d_bug_B,5):+.3f} p50={np.nanpercentile(d_bug_B,50):+.3f} "
      f"p95={np.nanpercentile(d_bug_B,95):+.3f} °C")
print(f"  修法A - 修法B: mean={np.nanmean(d_A_B):+.3f} "
      f"p5={np.nanpercentile(d_A_B,5):+.3f} p50={np.nanpercentile(d_A_B,50):+.3f} "
      f"p95={np.nanpercentile(d_A_B,95):+.3f} °C")

# 单点视角：现状把"最冷点"和"最暖点"的阈值差抹平到什么程度
site_mean = np.nanmean(thrB, axis=0)
i_cold, i_warm = int(np.argmin(site_mean)), int(np.argmax(site_mean))
print(f"\n  单点年均阈值(修法B): 最冷点 #{i_cold} = {site_mean[i_cold]:.2f} °C, "
      f"最暖点 #{i_warm} = {site_mean[i_warm]:.2f} °C, 差 {site_mean[i_warm]-site_mean[i_cold]:.2f} °C")
print(f"  现状(bug)给的(全部点同一条): 年均 "
      f"{np.nanmean(thresh_bug, axis=0)[i_cold]:.2f} °C")
print(f"  => 最冷点被抬高了 {np.nanmean(thresh_bug,axis=0)[i_cold] - site_mean[i_cold]:+.2f} °C, "
      f"最暖点被压低了 {np.nanmean(thresh_bug,axis=0)[i_warm] - site_mean[i_warm]:+.2f} °C")

# --------------------------------------------------------------------------
hr("【L3】缓存无指纹：members 参数变化会不会被 npz 缓存静默吞掉")
print("代码位置 phase6_cesm.py:274-280 / 298-303 —— 只判断 os.path.exists(cache)，"
      "不校验成员数/名单/池大小。")
print(f"现有 thresh_t2m_xghg.npz mtime/size: "
      f"{os.path.getsize(os.path.join(CESM_INT,'thresh_t2m_xghg.npz'))} B")


def _pooled(pairs_df, members):
    """复刻原函数的缓存判定（不写盘）。"""
    cache = os.path.join(CESM_INT, "thresh_sst_xghg.npz")
    if os.path.exists(cache):
        return "HIT-CACHE(成员列表被忽略)"
    return "MISS"


print("模拟: _pooled_threshold_sst(pairs, ['001']) ->", _pooled(pairs, ["001"]))
print("模拟: _pooled_threshold_sst(pairs, 20 个成员)  ->", _pooled(pairs, [f"{i:03d}" for i in range(1, 21)]))

# --------------------------------------------------------------------------
hr("【L4】观测侧口径 vs 模型侧口径（配对距离上限）")
obs = pd.read_csv(C.COASTAL_PAIRS_CSV)
print(f"观测 coastal_pairs.csv: {len(obs)} 对 / 唯一海点 "
      f"{obs[['ocean_lat_idx','ocean_lon_idx']].drop_duplicates().shape[0]} / "
      f"dist_deg max={obs.dist_deg.max():.4f} (config MAX_GRID_DIST_DEG={C.MAX_GRID_DIST_DEG})")
print(f"模型 coastal_pairs_cesm.csv: {len(pairs)} 对 / 唯一海点 "
      f"{pairs[['ocean_lat_idx','ocean_lon_idx']].drop_duplicates().shape[0]} / "
      f"dist_deg max={pairs.dist_deg.max():.4f} (MAX_PAIR_DIST_DEG=1.0)")
print("\n观测对表列:", list(obs.columns))
print("模型对表列:", list(pairs.columns))

# --------------------------------------------------------------------------
hr("【L5】_run_events 桥接/过滤顺序（合成判别用例，纯逻辑，不依赖 R）")
sys.path.insert(0, os.path.join(BASE, "python"))
from phase6_cesm import _run_events  # noqa: E402

cases = {
    "3超+2空+3超 (总跨度8)": [1, 1, 1, 0, 0, 1, 1, 1],
    "1超+2空+4超 (跨度7)": [1, 0, 0, 1, 1, 1, 1],
    "2超+2空+2超 (跨度6)": [1, 1, 0, 0, 1, 1],
    "1超+1空+3超 (跨度5)": [1, 0, 1, 1, 1],
    "4超+3空+4超 (间隙>2)": [1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1],
    "5超 单段": [1, 1, 1, 1, 1],
    "4超 单段(<5)": [1, 1, 1, 1],
    "1超+2空+1超 (跨度4)": [1, 0, 0, 1],
}
print(f"{'用例':28s} {'_run_events 结果':40s} 事件数")
for k, v in cases.items():
    ev = _run_events(np.array(v, dtype=np.int8))
    print(f"{k:28s} {str(ev):40s} {len(ev)}")

print("""
判读要点：原代码 = 先对原始游程桥接(<=2) 再按 '总跨度>=5' 过滤。
因此 '3超+2空+3超'(跨度8) 与 '1超+2空+4超'(跨度7) 都会被判为**一个 5 天以上事件**；
而 '先过滤游程>=5 再桥接' 的口径下这两例都不会产生事件。
""")
