"""globalize_mhw_idx.py — 把 R 海洋检测输出的局部索引换算回全球 OISST 索引。

背景：
  detect_events.R 用裁剪文件 (lat 204 x lon 340) 跑海洋检测，输出的
  lat_idx/lon_idx 是**相对裁剪文件**的 0-based 索引。
  下游 compound_events.identify_compound_events 用 mhw 的 (lat_idx, lon_idx)
  与 coastal_pairs.csv 的 (ocean_lat_idx, ocean_lon_idx) **整型直接匹配**，
  而后者是**全球 OISST 网格 (720 x 1440)** 的索引
  （例如 ocean_lat_idx=461 -> lat=-89.875+0.25*461=25.375）。
  不换算的话 compound 匹配数 = 0，Phase 2 全部归零 —— 这是必须做的一步。

做法（self-checking，零硬编码）：
  1. 从裁剪文件读坐标，校验 CSV 内 idx<->coord 一致（陷阱 3）。
  2. 打开原始全球文件**只读 lon/lat 坐标变量**（不碰 23 GB 数据体）。
  3. 每个 (lat_idx, lon_idx) -> 坐标 -> 在全球坐标网格上精确匹配
     （容差 1e-6 度；裁剪网格是全球格点的一个子集，必须精确命中），
     得到全球 0-based 索引。
  4. 与 coastal_pairs.csv 的海洋点做集合交叉校验：
     R 输出点集必须是 1,434 个配对海洋点的子集。
  5. 写 mhw_events_R_global.csv（列结构不变，仅 idx 换成全球索引）。

用法:
    python globalize_mhw_idx.py                          # 用 config 默认路径
    python globalize_mhw_idx.py <src_csv> <dst_csv>      # 显式指定（供 run_all.py 调用）

路径来源：默认全部取自 python/config.py（2026-09-23 去除硬编码盘符）。
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
from config import (  # noqa: E402
    OISST_MERGED_FILE, COASTAL_PAIRS_CSV, INTERMEDIATE_DIR,
)

# 裁剪件：配置里没有独立常量，按约定名推导；不存在时回退到全球件
_CLIP_CANDIDATE = os.path.join(os.path.dirname(OISST_MERGED_FILE),
                               "oisst_v2.1_eur_1983_2023.nc")

SRC_CSV = os.path.join(INTERMEDIATE_DIR, "mhw_events_R.csv")          # R 原始输出（局部索引）
DST_CSV = os.path.join(INTERMEDIATE_DIR, "mhw_events_R_global.csv")   # 换算后（全球索引）
CLIP = _CLIP_CANDIDATE
GLOB = OISST_MERGED_FILE
PAIRS = COASTAL_PAIRS_CSV
TOL = 1e-6


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main(src_csv=None, dst_csv=None):
    src_csv = src_csv or SRC_CSV
    dst_csv = dst_csv or DST_CSV
    for p in (src_csv, CLIP, GLOB, PAIRS):
        if not os.path.exists(p):
            raise FileNotFoundError(p)

    df = pd.read_csv(src_csv)
    log(f"loaded {src_csv}: {len(df):,} events")
    if len(df) == 0:
        raise SystemExit("empty event table — nothing to globalize")

    clip = xr.open_dataset(CLIP)
    clat, clon = clip.lat.values, clip.lon.values
    glob = xr.open_dataset(GLOB)
    glat, glon = glob.lat.values, glob.lon.values
    log(f"clip grid lat {clat[0]}..{clat[-1]} ({clat.size}), "
        f"lon {clon[0]}..{clon[-1]} ({clon.size})")
    log(f"global grid lat {glat[0]}..{glat[-1]} ({glat.size}), "
        f"lon {glon[0]}..{glon[-1]} ({glon.size})")

    pts = df[["lat_idx", "lon_idx", "lat", "lon"]].drop_duplicates()
    log(f"unique grid points in events: {len(pts):,}")

    # ---- 1. idx <-> coord 校验（相对裁剪文件）----
    dlat = np.abs(clat[pts.lat_idx.values] - pts.lat.values).max()
    dlon = np.abs(clon[pts.lon_idx.values] - pts.lon.values).max()
    log(f"idx->coord check vs CLIP: max |dlat|={dlat:.2e}, |dlon|={dlon:.2e}")
    if dlat > TOL or dlon > TOL:
        raise SystemExit("FAIL: event idx/coord mismatch against clip grid")

    # ---- 2. 坐标 -> 全球索引（精确匹配，1e-6 容差）----
    def gidx(vals, coord):
        hits = np.where(np.abs(vals - coord) < TOL)[0]
        if hits.size != 1:
            raise SystemExit(
                f"FAIL: coord {coord} hits {hits.size} global grid points "
                f"(expected exactly 1)")
        return int(hits[0])

    key2g = {}
    for r in pts.itertuples(index=False):
        lat360 = float(r.lon) % 360.0   # 裁剪文件 lon 是 -180..180
        gi = gidx(glat, float(r.lat))
        gj = gidx(glon, lat360)
        # 回读校验：全球坐标必须与裁剪坐标完全一致
        if abs(glat[gi] - r.lat) > TOL or abs(glon[gj] - lat360) > TOL:
            raise SystemExit(f"FAIL: roundtrip mismatch at {r}")
        key2g[(int(r.lat_idx), int(r.lon_idx))] = (gi, gj)
    log(f"mapped {len(key2g):,} points to global indices "
        f"(lat_idx {min(v[0] for v in key2g.values())}..{max(v[0] for v in key2g.values())}, "
        f"lon_idx {min(v[1] for v in key2g.values())}..{max(v[1] for v in key2g.values())})")

    # ---- 3. 与 coastal_pairs 交叉校验 ----
    pairs = pd.read_csv(PAIRS)
    pair_pts = set(zip(pairs.ocean_lat_idx.astype(int),
                       pairs.ocean_lon_idx.astype(int)))
    log(f"coastal_pairs unique ocean points: {len(pair_pts):,}")
    ev_pts = set(key2g.values())
    outside = ev_pts - pair_pts
    log(f"event points inside pair set: {len(ev_pts & pair_pts):,} / {len(ev_pts):,}")
    if outside:
        bad = sorted(outside)[:10]
        raise SystemExit(f"FAIL: {len(outside)} event points NOT in coastal_pairs "
                         f"(first few: {bad})")
    log(f"coverage: {len(ev_pts):,} of {len(pair_pts):,} paired ocean points "
        f"produced events")

    # ---- 4. 换算写出 ----
    g = df.copy()
    g["lat_idx"] = [key2g[(int(a), int(b))][0]
                    for a, b in zip(df.lat_idx, df.lon_idx)]
    g["lon_idx"] = [key2g[(int(a), int(b))][1]
                    for a, b in zip(df.lat_idx, df.lon_idx)]
    g.to_csv(dst_csv, index=False)
    log(f"wrote {dst_csv}: {len(g):,} events, "
        f"{g.groupby(['lat_idx', 'lon_idx']).ngroups:,} points")
    glob.close()
    clip.close()
    log("DONE — PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(*(sys.argv[1:3] if len(sys.argv) > 1 else (None, None))))
