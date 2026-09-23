# Lead 独立复核 第七部分：按 heatwaveR:::proto_event 源码逐行复刻，验证 450/450 等价
import os

import numpy as np
import pandas as pd

TMP = r"D:\2607compound\results\intermediate\audit\lead"
ref = pd.read_csv(os.path.join(TMP, "fuzz_heatwaver.csv"))
df = pd.read_csv(os.path.join(TMP, "fuzz_sequences.csv"), dtype={"o": str})
ref = ref.merge(df, on=["case", "seq"], how="left")


def _rle(mask):
    """返回 [(value, start, end)]（含端点，0-based）。"""
    x = np.asarray(mask).astype(np.int8)
    if x.size == 0:
        return []
    d = np.diff(np.concatenate(([0], x, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1) - 1
    return [(True, int(a), int(b)) for a, b in zip(st, en)]


def _rle_all(mask):
    """完整 rle：连续同值段，含 False 段。"""
    x = np.asarray(mask).astype(np.int8)
    if x.size == 0:
        return []
    idx = np.flatnonzero(np.diff(x) != 0) + 1
    bounds = np.concatenate(([0], idx, [x.size]))
    return [(bool(x[bounds[i]]), int(bounds[i]), int(bounds[i + 1] - 1))
            for i in range(len(bounds) - 1)]


def hw_proto_event(criterion, min_dur=5, max_gap=2, join_across_gaps=True):
    """逐行复刻 heatwaveR:::proto_event (heatwaveR 0.5.5)。"""
    n = len(criterion)
    runs = _rle(criterion)                                  # ex1
    seeds = [(a, b) for _, a, b in runs if (b - a + 1) >= min_dur]
    if not seeds:                                           # max(duration) < minDuration
        return []
    dc = np.zeros(n, dtype=bool)                            # durationCriterion
    for a, b in seeds:
        dc[a:b + 1] = True
    if join_across_gaps:
        gaps = [(a, b) for v, a, b in _rle_all(dc) if not v]
        first_seed_start = seeds[0][0]
        gaps = [(a, b) for a, b in gaps
                if b > first_seed_start and 1 <= (b - a + 1) <= max_gap]
        for a, b in gaps:
            dc[a:b + 1] = True
    return [(a, b) for _, a, b in _rle(dc)]


def ftb(x, min_dur=5, max_gap=2):
    x = np.asarray(x, np.int8)
    d = np.diff(np.concatenate(([0], x, [0])))
    st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1
    ev = [(a, b) for a, b in zip(st, en) if b - a + 1 >= min_dur]
    merged = []
    for a, b in ev:
        if merged and a - merged[-1][1] - 1 <= max_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return merged


def check(name, fn):
    bad = []
    for _, r in ref.iterrows():
        o = np.array(list(map(int, r.o)))
        md, mg = map(int, r.case.split("_"))
        ev = fn(o, md, mg)
        got = ",".join(str(b - a + 1) for a, b in ev)
        want = "" if pd.isna(r.durs) else str(r.durs)
        if got != want or len(ev) != r.n_ev:
            bad.append((r.case, r.seq, want, got))
    print(f"  {name:42s} 不一致 {len(bad):3d}/{len(ref)}")
    for c, s, w, g in bad[:5]:
        print(f"      case={c} seq={s}: heatwaveR=[{w}]  我们=[{g}]")
    return bad


print("最终对照（450 例：3 组参数 × 150 条随机序列）：")
check("先过滤后桥接 (ftb，近似)", ftb)
check("proto_event 逐行复刻 (精确)", hw_proto_event)

# 再补 4 个刻意构造的边界用例
print("\n边界用例（manual）：")
manual = {
    "5超 + 2天空档(到序列末)": [1, 1, 1, 1, 1, 0, 0],
    "2天空档 + 5超(序列首)": [0, 0, 1, 1, 1, 1, 1],
    "5超 + 1空 + 5超": [1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1],
    "5超 + 2空 + 1超 + 2空 + 5超": [1]*5 + [0, 0] + [1] + [0, 0] + [1]*5,
    "5超 + 2空 + 2超 + 2空 + 5超": [1]*5 + [0, 0] + [1, 1] + [0, 0] + [1]*5,
    "3超 + 2空 + 3超": [1, 1, 1, 0, 0, 1, 1, 1],
}
for k, v in manual.items():
    a = [b - x + 1 for x, b in ftb(v)]
    bb = [b - x + 1 for x, b in hw_proto_event(v)]
    print(f"  {k:32s} ftb={a}  proto_event={bb}")

# 把 manual 用例送 R 核对
p = os.path.join(TMP, "manual_seqs.csv")
pd.DataFrame({"k": list(manual), "o": ["".join(map(str, v)) for v in manual.values()]}).to_csv(p, index=False)
pp = p.replace(chr(92), "/")
code = f'''
suppressPackageStartupMessages(library(heatwaveR))
d <- read.csv("{pp}", colClasses = c(o = "character"))
for (i in seq_len(nrow(d))) {{
  o <- as.integer(strsplit(d$o[i], "")[[1]]); n <- length(o)
  df <- data.frame(t = as.Date("2000-01-01") + seq_len(n) - 1L,
                   temp = ifelse(o == 1, 1, 0), seas = 0, thresh = 0.5)
  ev <- detect_event(df, minDuration = 5, maxGap = 2)$event
  ev <- ev[!is.na(ev$event_no), , drop = FALSE]
  cat(sprintf("%-32s heatwaveR=%s\\n", d$k[i],
              if (nrow(ev) == 0) "[]" else paste0("[", paste(ev$duration, collapse = ", "), "]")))
}}
'''
with open(os.path.join(TMP, "manual_seqs.R"), "w", encoding="utf-8") as f:
    f.write(code)
import subprocess  # noqa: E402
r = subprocess.run([r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe",
                    os.path.join(TMP, "manual_seqs.R")], capture_output=True, text=True)
print("\n---- R 权威结果 ----")
print(r.stdout)
print(r.stderr[-300:])
