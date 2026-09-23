# Lead 独立复核 第三部分：_run_events vs heatwaveR 的模糊等价性测试 + 真实数据影响量化
# 用法: python results\phase6_audit_lead_check3.py
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
import xarray as xr

BASE = r"D:\2607compound"
CESM_INT = os.path.join(BASE, "results", "intermediate", "cesm")
RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
TMP = os.path.join(BASE, "results", "intermediate", "audit", "lead")
os.makedirs(TMP, exist_ok=True)
sys.path.insert(0, os.path.join(BASE, "python"))
from phase6_cesm import _run_events  # noqa: E402


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# --------------------------------------------------------------------------
def runs_bridge_then_filter(x, min_dur=5, max_gap=2):
    """phase6_cesm._run_events：先桥接原始游程，再按总跨度过滤。"""
    return _run_events(np.asarray(x, np.int8), None)


def runs_filter_then_bridge(x, min_dur=5, max_gap=2):
    """heatwaveR 语义：先把 >=min_dur 的游程认定为事件，再桥接间隔<=max_gap 的事件。"""
    x = np.asarray(x, np.int8)
    d = np.diff(np.concatenate(([0], x, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1) - 1
    ev = [(a, b) for a, b in zip(st, en) if b - a + 1 >= min_dur]
    merged = []
    for a, b in ev:
        if merged and a - merged[-1][1] - 1 <= max_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


# --------------------------------------------------------------------------
hr("【L8】模糊等价性测试：150 条随机 0/1 序列 × 3 组 (min_dur,max_gap)")
rng = np.random.default_rng(20260923)
n_seq, L = 150, 400
seqs = []
for i in range(n_seq):
    p = rng.uniform(0.05, 0.5)
    seqs.append((rng.random(L) < p).astype(int))

cases = [(5, 2), (3, 1), (5, 3)]
rows = []
for (md, mg) in cases:
    for i, s in enumerate(seqs):
        rows.append({"case": f"{md}_{mg}", "seq": i, "o": "".join(map(str, s))})
df = pd.DataFrame(rows)
csv_in = os.path.join(TMP, "fuzz_sequences.csv")
df.to_csv(csv_in, index=False)

r_code = f'''
suppressPackageStartupMessages(library(heatwaveR))
d <- read.csv("{csv_in.replace(chr(92), '/')}", stringsAsFactors = FALSE, colClasses = c(o = "character"))
out <- data.frame()
for (i in seq_len(nrow(d))) {{
  o <- as.integer(strsplit(d$o[i], "")[[1]])
  n <- length(o)
  df <- data.frame(t = as.Date("2000-01-01") + seq_len(n) - 1L,
                   temp = ifelse(o == 1, 1, 0), seas = 0, thresh = 0.5)
  md <- as.integer(sub("_.*", "", d$case[i])); mg <- as.integer(sub(".*_", "", d$case[i]))
  ev <- detect_event(df, minDuration = md, maxGap = mg)$event
  if (!is.null(ev) && nrow(ev) > 0) ev <- ev[!is.na(ev$event_no), , drop = FALSE]
  ne <- if (is.null(ev)) 0L else nrow(ev)
  dur <- if (ne == 0) "" else paste(ev$duration, collapse = ",")
  out <- rbind(out, data.frame(case = d$case[i], seq = d$seq[i],
                               n_ev = ne, durs = dur, stringsAsFactors = FALSE))
}}
write.csv(out, "{os.path.join(TMP, 'fuzz_heatwaver.csv').replace(chr(92), '/')}", row.names = FALSE)
cat("R done\\n")
'''
r_file = os.path.join(TMP, "fuzz_hw.R")
with open(r_file, "w", encoding="utf-8") as f:
    f.write(r_code)
r = subprocess.run([RSCRIPT, r_file], capture_output=True, text=True)
print(r.stdout.strip()[-200:], r.stderr.strip()[-500:])
ref = pd.read_csv(os.path.join(TMP, "fuzz_heatwaver.csv"))
ref = ref.merge(df, on=["case", "seq"], how="left")

mismatch_a = mismatch_b = 0
for _, row in ref.iterrows():
    o = np.array(list(map(int, row.o)))
    md, mg = map(int, row.case.split("_"))
    ea = runs_bridge_then_filter(o, md, mg)
    eb = runs_filter_then_bridge(o, md, mg)
    da = ",".join(str(b - a + 1) for a, b in ea)
    db = ",".join(str(b - a + 1) for a, b in eb)
    dref = "" if pd.isna(row.durs) else str(row.durs)
    if da != dref or len(ea) != row.n_ev:
        mismatch_a += 1
    if db != dref or len(eb) != row.n_ev:
        mismatch_b += 1
print(f"共 {len(ref)} 例（3 组参数 × 150 随机序列）")
print(f"  先桥接后过滤 (_run_events 现状) 与 heatwaveR 不一致: {mismatch_a} / {len(ref)}")
print(f"  先过滤后桥接 (文档声称的语义)  与 heatwaveR 不一致: {mismatch_b} / {len(ref)}")

# --------------------------------------------------------------------------
hr("【L9】真实影响：CESM ALL 001 的 206 个陆点，两种游程口径对比")
pairs = pd.read_csv(os.path.join(CESM_INT, "coastal_pairs_cesm.csv"))
pj, pi_ = pairs.land_lat_idx.values, pairs.land_lon_idx.values
ds = xr.open_dataset(os.path.join(CESM_INT, "ALL_001_T2m.nc"))
da = ds["T2m"].isel(lat=xr.DataArray(pj, dims="p"), lon=xr.DataArray(pi_, dims="p"))
arr = da.transpose("time", "p").values.astype(np.float64)
t = pd.DatetimeIndex(da.time.values)
ds.close()

xghg = []
for m in ("001", "002", "003"):
    d2 = xr.open_dataset(os.path.join(CESM_INT, f"XGHG_{m}_T2m.nc"))
    a2 = d2["T2m"].isel(lat=xr.DataArray(pj, dims="p"), lon=xr.DataArray(pi_, dims="p"))
    xghg.append(a2.transpose("time", "p").values.astype(np.float64))
    d2.close()
mat = np.concatenate(xghg, axis=0)
doy_all = np.concatenate([t.dayofyear.values] * 3)
mat_by_doy = {d: mat[doy_all == d] for d in np.arange(1, 366)}
thr = np.full((366, mat.shape[1]), np.nan)
for d in np.arange(1, 366):
    win = [(d + k - 1) % 365 + 1 for k in range(-5, 6)]
    thr[d - 1] = np.nanpercentile(np.concatenate([mat_by_doy[w] for w in win], axis=0),
                                  90, axis=0)
doy = t.dayofyear.values

for label, fn in (("先桥接后过滤(现状)", runs_bridge_then_filter),
                  ("先过滤后桥接(heatwaveR)", runs_filter_then_bridge)):
    n_ev = n_day = 0
    for p in range(arr.shape[1]):
        x = arr[:, p] > thr[doy - 1, p]
        x[np.isnan(arr[:, p])] = False
        for a, b in fn(x):
            n_ev += 1
            n_day += b - a + 1
    print(f"  {label:24s} 事件={n_ev:7d}  超阈天数={n_day:8d}")

# --------------------------------------------------------------------------
hr("【L10】同口径对照：热浪阈值本身 vs 观测 OISST 的点均超阈天数（量级 sanity）")
z = np.load(os.path.join(CESM_INT, "thresh_sst_xghg.npz"))["thresh"]
print(f"SST 反事实阈值 (366,{z.shape[1]}) 范围 {np.nanmin(z):.2f}..{np.nanmax(z):.2f} °C")
