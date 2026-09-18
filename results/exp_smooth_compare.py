"""exp_smooth_compare.py — smoothPercentile ON vs OFF 复合天数抽样对比。

步骤:
  1. 从 coastal_pairs.csv 分区抽样 (Med/Baltic/Atlantic)
  2. 调 R exp_smooth_test.R 用包默认 (smoothPercentile=TRUE, 31天) 重检两侧事件
  3. 对同样的点, 用现有 (smooth=FALSE) 全量结果做 containment, 计算逐年复合天数
  4. 对比 ON/OFF 的区域复合天数 (2022/2023) 与论文锚点
     (fig1j: Med 2022~78, 2023~72; fig2b: standalone 多数<10)
"""
import os
import subprocess
import sys

import numpy as np
import pandas as pd

INTER = r"D:\2607compound\results\intermediate"
RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
R_EXP = r"D:\2607compound\results\exp_smooth_test.R"
SAMPLE = os.path.join(INTER, "_exp_smooth_sample.csv")
EXP_EV = os.path.join(INTER, "_exp_smooth_events.csv")

PAIRS = os.path.join(INTER, "coastal_pairs.csv")
THW = os.path.join(INTER, "thw_events_R.csv")          # smooth=OFF 陆地基准
MHW = os.path.join(INTER, "mhw_events_R_global.csv")   # smooth=OFF 海洋
THW_V2 = os.path.join(INTER, "thw_events_R_v2.csv")    # 与基准逐值一致, 用哪个都行


def build_sample():
    pairs = pd.read_csv(PAIRS)
    rng = np.random.default_rng(42)
    boxes = {
        "Med": ((30, 47), (5, 42), 50),
        "Baltic": ((53, 66), (10, 30), 20),
        "Atlantic": ((35, 60), (-10, 5), 20),
    }
    frames = []
    for name, ((la0, la1), (lo0, lo1), n) in boxes.items():
        m = (pairs.land_lat.between(la0, la1) & pairs.land_lon.between(lo0, lo1))
        sub = pairs[m]
        take = sub.iloc[rng.choice(len(sub), size=min(n, len(sub)), replace=False)]
        take = take.copy()
        take["region"] = name
        frames.append(take)
    samp = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame({
        "region": samp.region,
        "land_lat": samp.land_lat, "land_lon": samp.land_lon,
        "ocean_lat": samp.ocean_lat,
        "ocean_lon": np.where(samp.ocean_lon > 180, samp.ocean_lon - 360, samp.ocean_lon),
    })
    out.to_csv(SAMPLE, index=False)
    print(f"sample: {len(out)} pairs "
          f"({out.region.value_counts().to_dict()}) -> {SAMPLE}")
    return out


def run_r():
    cmd = [RSCRIPT, R_EXP, SAMPLE, EXP_EV]
    print("RUN:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout[-2000:])
    if r.returncode != 0:
        print(r.stderr[-3000:])
        sys.exit(1)


def compound_days_per_year(thw_ev, mhw_ev):
    """containment 复合天数: THW 完全被某 MHW 涵盖 -> 事件跨度逐日记天。"""
    out = {}
    mhw_list = mhw_ev[["event_start", "event_end"]].values.tolist()
    for _, thw in thw_ev.iterrows():
        ts, te = pd.Timestamp(thw.event_start), pd.Timestamp(thw.event_end)
        if not any((pd.Timestamp(ms) <= ts) and (pd.Timestamp(me) >= te)
                   for ms, me in mhw_list):
            continue
        d = ts
        while d <= te:
            out[d.year] = out.get(d.year, 0) + 1
            d += pd.Timedelta(days=1)
    return out


def standalone_flags(thw_ev, mhw_ev):
    """standalone = 与任何 MHW 无重叠的 THW 事件 (返回其跨度天数逐年)。"""
    out = {}
    mhw_list = mhw_ev[["event_start", "event_end"]].values.tolist()
    for _, thw in thw_ev.iterrows():
        ts, te = pd.Timestamp(thw.event_start), pd.Timestamp(thw.event_end)
        if any(not (pd.Timestamp(me) < ts or pd.Timestamp(ms) > te)
               for ms, me in mhw_list):
            continue
        d = ts
        while d <= te:
            out[d.year] = out.get(d.year, 0) + 1
            d += pd.Timedelta(days=1)
    return out


def load_events(path, lat, lon, tol=1e-6):
    df = pd.read_csv(path)
    key = pd.merge(df, pd.DataFrame({"lat": lat, "lon": lon}),
                   on=["lat", "lon"])
    return key


def main():
    samp = build_sample()
    run_r()

    # ---- 控制组 (smooth=OFF): 现有全量结果按抽样点过滤 ----
    thw = pd.read_csv(THW)
    mhw = pd.read_csv(MHW)
    pairs = pd.read_csv(PAIRS)
    # 把抽样对映回 land/ocean 全局索引
    merged = samp.merge(pairs, left_on=["land_lat", "land_lon"],
                        right_on=["land_lat", "land_lon"], how="left")
    mhw["lon360"] = np.where(mhw.lon > 180, mhw.lon - 360, mhw.lon)
    # 控制组事件表: (pair_row, side) -> events
    ctrl_events = {}
    for i, row in merged.iterrows():
        t = thw[(thw.lat_idx == row.land_lat_idx) & (thw.lon_idx == row.land_lon_idx)]
        o = mhw[(mhw.lat_idx == row.ocean_lat_idx) & (mhw.lon_idx == row.ocean_lon_idx)]
        ctrl_events[i] = (t, o)
    # 实验组 (smooth=ON)
    exp = pd.read_csv(EXP_EV)
    exp_land = exp[exp.side == "land"]
    exp_ocean = exp[exp.side == "ocean"]

    rows = []
    for i, row in merged.iterrows():
        # 实验组: 同一对的 land/ocean 事件
        t_on = exp_land[exp_land.pair_row == i]
        o_on = exp_ocean[exp_ocean.pair_row == i]
        t_off, o_off = ctrl_events[i]
        for tag, (t_ev, o_ev) in (("ON", (t_on, o_on)), ("OFF", (t_off, o_off))):
            comp = compound_days_per_year(t_ev, o_ev)
            std = standalone_flags(t_ev, o_ev)
            rows.append({"region": row.region, "pair": i, "mode": tag,
                         "comp_2022": comp.get(2022, 0), "comp_2023": comp.get(2023, 0),
                         "comp_mean_0323": np.mean([comp.get(y, 0) for y in range(2003, 2024)]),
                         "std_mean_0323": np.mean([std.get(y, 0) for y in range(2003, 2024)]),
                         "n_thw": len(t_ev), "n_mhw": len(o_ev)})
    df = pd.DataFrame(rows)
    agg = df.groupby(["region", "mode"]).agg(
        comp22_mean=("comp_2022", "mean"), comp23_mean=("comp_2023", "mean"),
        comp_0323_mean=("comp_mean_0323", "mean"),
        std_0323_mean=("std_mean_0323", "mean"),
        n_thw_mean=("n_thw", "mean"), n_mhw_mean=("n_mhw", "mean")).round(2)
    print("\n===== 区域均值 (每个抽样点的平均) =====")
    print(agg.to_string())
    print("\n论文锚点: fig1j Med 2022~78/2023~72 (区域聚合), fig2b standalone 多数<10, "
          "fig2c CHR 2023~3.5")
    print("注: 抽样点均值 < 区域聚合值; 重点看 ON/OFF 的相对倍率与方向")


if __name__ == "__main__":
    main()
