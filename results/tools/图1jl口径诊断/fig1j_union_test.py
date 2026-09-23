"""
fig1j_union_test.py — 检验图1j "78 天" 的第三种口径：区域内"任一格点出现复合日"的天数并集

背景：复现报告 §6 已排除"空间均值/分位数"等 5 种口径，但未测"日并集"。
论文正文措辞是 "the region experienced ... fewer than 20 days ... exceeding 62 days
in recent peak years / reaching nearly 78 days in 2022"——"region experienced X days"
字面更接近"该区域有 X 天发生了复合"，即区域内任一格点当天为复合日即计 1 天（上限 365）。
"""
import os
import numpy as np
import xarray as xr

COMPOUND = r"results\intermediate\compound_events.nc"
REGIONS = {
    "Mediterranean & Black Sea": dict(lat=(30, 47), lon=(5, 42)),
    "All European coasts":       dict(lat=(30, 72), lon=(-15, 45)),
}

ds = xr.open_dataset(COMPOUND)
var = list(ds.data_vars)[0]
da = ds[var]
print("compound var:", var, "dims:", dict(da.sizes))

years = np.arange(1983, 2024)
out = {}
for name, r in REGIONS.items():
    sub = da.sel(lat=slice(*r["lat"]), lon=slice(*r["lon"]))
    arr = sub.values
    days = (arr > 0).any(axis=(1, 2))          # 当天是否有任一格点为复合日
    t = sub.time.values.astype("datetime64[Y]").astype(int) + 1970
    per_year = {y: int(days[t == y].sum()) for y in years}
    out[name] = per_year

paper = {"Mediterranean & Black Sea": {2022: 78, 2023: 72, 2003: 62}}
print()
for name, per_year in out.items():
    print(f"=== {name} ===")
    print("  年份: " + " ".join(f"{y}:{per_year[y]}" for y in range(2003, 2024)))
    peak = max(per_year, key=per_year.get)
    print(f"  峰值年: {peak} = {per_year[peak]} 天   80s-90s 均值: "
          f"{np.mean([per_year[y] for y in range(1983, 2000)]):.1f}")
    if name in paper:
        for y, v in paper[name].items():
            print(f"    论文 {y} = {v} 天  ->  本口径 {per_year[y]} 天")
print()
print("对照：现有主图口径（活跃点空间均值，来自 fig_stats_new.json）")
print("  2022=20.7  2023=37.9  2003=14.0")
