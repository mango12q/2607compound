"""run_detection_R.py — 统一的海陆热浪检测编排（R heatwaveR + Python 下游）。

用法:
  python run_detection_R.py ocean          # OISST 海洋热浪（1,434 个配对格点）
  python run_detection_R.py land           # E-OBS 陆地热浪（全网格）
  python run_detection_R.py both
  python run_detection_R.py validate       # 只校验已有输出

海陆使用 detect_events.R **同一份代码**，保证 minDuration/maxGap/阈值窗口
完全一致 —— 这是 CHR = compound/standalone 有意义的前提。
"""
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import xarray as xr

RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
R_SCRIPT = r"D:\2607compound\python\detect_events.R"

OISST_CLIP = r"E:\2607compound\data\OISST\oisst_v2.1_eur_1983_2023.nc"
EOBS = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"
DOMAINS = r"D:\2607compound\results\intermediate\domains_ocean_pairs.csv"
WORK = r"D:\2607compound\results\intermediate\_detect_R"

OUT_OCEAN = r"D:\2607compound\results\intermediate\mhw_events_R.csv"
# ★ 回归测试专用：detect_thw.R 的已验证输出 thw_events_R.csv（1,635,196 事件）
#   是回归基准，绝不能被覆盖。陆地重跑写到 v2，对比一致后才启用。
OUT_LAND = r"D:\2607compound\results\intermediate\thw_events_R_v2.csv"

CLIM0, CLIM1 = 1983, 2012
MIN_DUR, MAX_GAP = 5, 2
WORKERS = 12


def run(cmd, log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    print("  RUN:", " ".join(cmd))
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8") as fh:
        p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)
    el = time.time() - t0
    print(f"  exit={p.returncode}  elapsed={el/60:.1f} min  log={log_path}")
    with open(log_path, encoding="utf-8") as fh:
        tail = fh.read().splitlines()[-25:]
    print("  --- log tail ---")
    for l in tail:
        print("   ", l)
    return p.returncode


def detect(kind):
    if kind == "ocean":
        nc, var, out, dom = OISST_CLIP, "sst", OUT_OCEAN, DOMAINS
    else:
        nc, var, out, dom = EOBS, "T2m", OUT_LAND, "-"
    for p in (nc,):
        if not os.path.exists(p):
            raise FileNotFoundError(f"{kind}: missing {p}")
    if dom != "-" and not os.path.exists(dom):
        raise FileNotFoundError(f"{kind}: missing domains file {dom}")

    cmd = [RSCRIPT, R_SCRIPT, nc, var, out, str(CLIM0), str(CLIM1), dom,
           str(MIN_DUR), str(MAX_GAP), str(WORKERS),
           os.path.join(WORK, kind)]
    return run(cmd, os.path.join(r"D:\2607compound\logs", f"detect_R_{kind}.log"))


def validate(kind):
    out = OUT_OCEAN if kind == "ocean" else OUT_LAND
    if not os.path.exists(out):
        print(f"  [{kind}] MISSING {out}")
        return False
    df = pd.read_csv(out)
    ok = True
    print(f"  [{kind}] {out}")
    print(f"    rows={len(df):,}  columns={list(df.columns)}")
    if len(df) == 0:
        print("    EMPTY!")
        return False
    na = int(df[["event_no", "event_start", "duration"]].isna().any(axis=1).sum())
    print(f"    rows with NA event_no/start/duration: {na}")
    ok &= na == 0
    dt = pd.to_datetime(df.event_start, errors="coerce")
    print(f"    dates parseable: {bool(dt.notna().all())}")
    ok &= bool(dt.notna().all())
    pts = df.groupby(["lat_idx", "lon_idx"]).ngroups
    print(f"    points={pts:,}  events/point={len(df)/pts:.1f}  "
          f"mean duration={df.duration.mean():.2f}")
    print(f"    years {dt.dt.year.min()} .. {dt.dt.year.max()}")
    ok &= dt.dt.year.min() >= CLIM0 and dt.dt.year.max() <= 2023

    # 索引 <-> 坐标 自检
    g = xr.open_dataset(OISST_CLIP if kind == "ocean" else EOBS)
    idx = df[["lat_idx", "lon_idx", "lat", "lon"]].drop_duplicates()
    lat_g, lon_g = g.lat.values, g.lon.values
    dlat = np.abs(lat_g[idx.lat_idx.values] - idx.lat.values).max()
    # OISST 经度可能已卷绕；统一按角度差取模比较
    dlon = np.abs(lon_g[idx.lon_idx.values] - idx.lon.values)
    dlon = np.minimum(dlon, np.abs(dlon - 360)).max()
    print(f"    index->coord max err: lat {dlat:.2e}, lon {dlon:.2e}")
    ok &= dlat < 1e-4 and dlon < 1e-4
    # 范围自检
    print(f"    lat_idx {df.lat_idx.min()}..{df.lat_idx.max()} "
          f"(grid {g.sizes['lat']})  lon_idx {df.lon_idx.min()}..{df.lon_idx.max()} "
          f"(grid {g.sizes['lon']})")
    ok &= df.lat_idx.max() < g.sizes["lat"] and df.lon_idx.max() < g.sizes["lon"]
    g.close()
    print(f"    => {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    print("=" * 74)
    print(f"Unified R heatwave detection — target: {what}")
    print("=" * 74)
    rc = 0
    if what in ("ocean", "both"):
        print("\n--- OCEAN (OISST -> MHW) ---")
        rc |= detect("ocean")
        validate("ocean")
    if what in ("land", "both"):
        print("\n--- LAND (E-OBS -> THW) ---")
        rc |= detect("land")
        validate("land")
    if what == "validate":
        validate("ocean")
        validate("land")
    print("\ndone, rc =", rc)


if __name__ == "__main__":
    main()
