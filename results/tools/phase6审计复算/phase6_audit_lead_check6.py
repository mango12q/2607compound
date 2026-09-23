# Lead 独立复核 第六部分：检验"短游程可被并入含种子的簇"假说 (H)
import os

import numpy as np
import pandas as pd

TMP = r"D:\2607compound\results\intermediate\audit\lead"
ref = pd.read_csv(os.path.join(TMP, "fuzz_heatwaver.csv"))
df = pd.read_csv(os.path.join(TMP, "fuzz_sequences.csv"), dtype={"o": str})
ref = ref.merge(df, on=["case", "seq"], how="left")


def ftb(x, min_dur=5, max_gap=2):
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
    return merged


def hypothesis_cluster(x, min_dur=5, max_gap=2):
    """H: 先按 gap<=maxGap 把所有游程聚成簇；簇内存在 >=min_dur 的游程才发事件(取簇跨度)。"""
    x = np.asarray(x, np.int8)
    d = np.diff(np.concatenate(([0], x, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1) - 1
    runs = list(zip(st, en))
    clusters = []
    for a, b in runs:
        if clusters and a - clusters[-1][-1][1] - 1 <= max_gap:
            clusters[-1].append((a, b))
        else:
            clusters.append([(a, b)])
    out = []
    for cl in clusters:
        if max(b - a + 1 for a, b in cl) >= min_dur:
            out.append((cl[0][0], cl[-1][1]))
    return out


def hypothesis_seed_join(x, min_dur=5, max_gap=2):
    """H2: 把短游程(<min_dur)视为"可跨过的间隙"，只对 >=min_dur 的种子事件做桥接，
    但桥接判据用 种子事件之间的原始距离。"""
    x = np.asarray(x, np.int8)
    d = np.diff(np.concatenate(([0], x, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1) - 1
    seeds = [(a, b) for a, b in zip(st, en) if b - a + 1 >= min_dur]
    merged = []
    for a, b in seeds:
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
    print(f"  {name:44s} 不一致 {len(bad):3d}/{len(ref)}")
    for c, s, w, g in bad[:4]:
        print(f"      case={c} seq={s}: heatwaveR=[{w}]  我们=[{g}]")
    return bad


print("对照（已知结果）：")
check("filter-then-bridge, gap<=maxGap", ftb)
print("\n假说检验：")
check("H  簇内存在种子则取簇跨度", hypothesis_cluster)
check("H2 只桥接种子事件(=ftb)", hypothesis_seed_join)

# 直接把 heatwaveR 的真实函数体打出来，找权威定义
print("\n---- heatwaveR::detect_event 函数体（前 120 行）----")
import subprocess  # noqa: E402
r = subprocess.run(
    [r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe", "-e",
     'cat(deparse(heatwaveR::detect_event), sep="\\n")'],
    capture_output=True, text=True)
body = r.stdout
print(body[:6000] if body else r.stderr[-1500:])
