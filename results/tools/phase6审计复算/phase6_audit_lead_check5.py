# Lead 独立复核 第五部分：确定 heatwaveR 精确的合并（桥接）判据
import os
import sys

import numpy as np
import pandas as pd

BASE = r"D:\2607compound"
TMP = os.path.join(BASE, "results", "intermediate", "audit", "lead")
sys.path.insert(0, os.path.join(BASE, "python"))

ref = pd.read_csv(os.path.join(TMP, "fuzz_heatwaver.csv"))
df = pd.read_csv(os.path.join(TMP, "fuzz_sequences.csv"), dtype={"o": str})
ref = ref.merge(df, on=["case", "seq"], how="left")


def ftb(x, min_dur=5, max_gap=2, slack=0, gap_mode="between"):
    """先过滤游程>=min_dur，再桥接。slack 加在 maxGap 上；gap_mode 控制 gap 的定义。"""
    x = np.asarray(x, np.int8)
    d = np.diff(np.concatenate(([0], x, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1) - 1
    ev = [(a, b) for a, b in zip(st, en) if b - a + 1 >= min_dur]
    merged = []
    for a, b in ev:
        if merged:
            prev_end = merged[-1][1]
            gap = (a - prev_end - 1) if gap_mode == "between" else (a - prev_end)
            if gap <= max_gap + slack:
                merged[-1][1] = b
                continue
        merged.append([a, b])
    return [(a, b) for a, b in merged]


variants = {
    "gap_between <= maxGap        (现状基线)": dict(slack=0, gap_mode="between"),
    "gap_between <= maxGap+1": dict(slack=1, gap_mode="between"),
    "gap_index   <= maxGap  (=between+1)": dict(slack=0, gap_mode="index"),
    "gap_index   <= maxGap+1": dict(slack=1, gap_mode="index"),
    "gap_between <= maxGap-1": dict(slack=-1, gap_mode="between"),
}
for name, kw in variants.items():
    bad = 0
    for _, r in ref.iterrows():
        o = np.array(list(map(int, r.o)))
        md, mg = map(int, r.case.split("_"))
        ev = ftb(o, md, mg, **kw)
        got = ",".join(str(b - a + 1) for a, b in ev)
        want = "" if pd.isna(r.durs) else str(r.durs)
        if got != want or len(ev) != r.n_ev:
            bad += 1
    print(f"  {name:38s} 不一致 {bad:3d}/{len(ref)}")

# 对最优变体，列出仍不一致的用例
best = dict(slack=1, gap_mode="between")
bad = []
for _, r in ref.iterrows():
    o = np.array(list(map(int, r.o)))
    md, mg = map(int, r.case.split("_"))
    ev = ftb(o, md, mg, **best)
    got = ",".join(str(b - a + 1) for a, b in ev)
    want = "" if pd.isna(r.durs) else str(r.durs)
    if got != want or len(ev) != r.n_ev:
        bad.append((r.case, r.seq, want, got))
print(f"\n最优变体 (gap_between <= maxGap+1) 残余不一致 {len(bad)} 例:")
for c, s, w, g in bad[:10]:
    print(f"  case={c} seq={s}: heatwaveR=[{w}]  我们=[{g}]")
