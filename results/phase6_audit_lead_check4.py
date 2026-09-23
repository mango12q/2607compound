# Lead 独立复核 第四部分：定位"先过滤后桥接"与 heatwaveR 的 5/450 残余不一致
import os
import subprocess
import sys

import numpy as np
import pandas as pd

BASE = r"D:\2607compound"
TMP = os.path.join(BASE, "results", "intermediate", "audit", "lead")
RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
sys.path.insert(0, os.path.join(BASE, "python"))
from phase6_cesm import _run_events  # noqa: E402

ref = pd.read_csv(os.path.join(TMP, "fuzz_heatwaver.csv"))
df = pd.read_csv(os.path.join(TMP, "fuzz_sequences.csv"), dtype={"o": str})
ref = ref.merge(df, on=["case", "seq"], how="left")


def ftb(x, min_dur=5, max_gap=2, inclusive=True):
    x = np.asarray(x, np.int8)
    d = np.diff(np.concatenate(([0], x, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1) - 1
    ev = [(a, b) for a, b in zip(st, en) if b - a + 1 >= min_dur]
    merged = []
    for a, b in ev:
        gap = a - merged[-1][1] - 1 if merged else 10**9
        if merged and (gap <= max_gap if inclusive else gap < max_gap):
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def btf(x, min_dur=5, max_gap=2, inclusive=True):
    x = np.asarray(x, np.int8)
    d = np.diff(np.concatenate(([0], x, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1) - 1
    merged = []
    for a, b in zip(st, en):
        gap = a - merged[-1][1] - 1 if merged else 10**9
        if merged and (gap <= max_gap if inclusive else gap < max_gap):
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a + 1 >= min_dur]


def show(name, fn, inclusive=True):
    bad = []
    for _, r in ref.iterrows():
        o = np.array(list(map(int, r.o)))
        md, mg = map(int, r.case.split("_"))
        ev = fn(o, md, mg, inclusive)
        got = ",".join(str(b - a + 1) for a, b in ev)
        want = "" if pd.isna(r.durs) else str(r.durs)
        if got != want or len(ev) != r.n_ev:
            bad.append((r.case, r.seq, r.o[:60], want, got))
    print(f"\n{name}: 不一致 {len(bad)}/{len(ref)}")
    for c, s, o, want, got in bad[:8]:
        print(f"  case={c} seq={s} 前60位={o}")
        print(f"    heatwaveR durations = [{want!r}]  我们的 = [{got!r}]")
    return bad


bad = show("先过滤后桥接 (gap<=maxGap)", ftb, True)
show("先过滤后桥接 (gap<maxGap)", ftb, False)
show("先桥接后过滤 (gap<=maxGap)", btf, True)
show("先桥接后过滤 (gap<maxGap)", btf, False)

# 把残余不一致的完整序列交给 R 复算，看 heatwaveR 到底怎么处理
if bad:
    c, s, _, want, _ = bad[0]
    seq = df[(df.case == c) & (df.seq == s)].o.iloc[0]
    md, mg = c.split("_")
    p = os.path.join(TMP, "one_seq.txt")
    with open(p, "w") as f:
        f.write(seq)
    pp = p.replace(chr(92), "/")
    code = f'''
o <- as.integer(strsplit(readLines("{pp}")[1], "")[[1]])
n <- length(o)
df <- data.frame(t = as.Date("2000-01-01") + seq_len(n) - 1L,
                 temp = ifelse(o == 1, 1, 0), seas = 0, thresh = 0.5)
ev <- detect_event(df, minDuration = {md}, maxGap = {mg})$event
ev <- ev[!is.na(ev$event_no), , drop = FALSE]
cat("runs(>thresh):\\n"); print(rle(o))
cat("heatwaveR duration:", ev$duration, "\\n")
cat("heatwaveR 事件表: date_start / date_end\\n"); print(ev[, c("duration","date_start","date_end")])
'''
    with open(os.path.join(TMP, "one_seq.R"), "w") as f:
        f.write(code)
    r = subprocess.run([RSCRIPT, os.path.join(TMP, "one_seq.R")],
                       capture_output=True, text=True)
    print("\n---- R 复算该序列 ----")
    print(r.stdout)
    print(r.stderr[-400:])
