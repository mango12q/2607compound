"""
fig1j_thw_test.py — 图1j 的算术约束卡在哪一环（限定沿海配对点）

方法：用 results/intermediate/coastal_pairs.csv 取出沿海陆格点索引，
在这些点上对年度 THW / 复合 / standalone 天数做区域平均（地中海 & 黑海框），
再与论文锚点（2003:62 / 2022:78 / 2023:72 天）比较。
"""
import numpy as np
import pandas as pd
import xarray as xr

MED = dict(lat=(30, 47), lon=(5, 42))
PAIRS = r"results\intermediate\coastal_pairs.csv"
FILES = {
    "THW总 ": r"results\intermediate\annual_thw_days.nc",
    "复合  ": r"results\intermediate\annual_compound_days.nc",
    "独立  ": r"results\intermediate\annual_standalone_days.nc",
}

pairs = pd.read_csv(PAIRS)
print("coastal pairs:", len(pairs), "唯一陆点:",
      len(set(zip(pairs.land_lat_idx, pairs.land_lon_idx))))

out = {}
for label, path in FILES.items():
    ds = xr.open_dataset(path)
    v = ds[list(ds.data_vars)[0]]
    lat = v.lat.values
    lon = v.lon.values
    # 经纬度 → 索引
    lat_i = {round(float(x), 4): i for i, x in enumerate(lat)}
    lon_i = {round(float(x), 4): i for i, x in enumerate(lon)}
    li = pairs.land_lat.values if "land_lat" in pairs else None
    # 用 land_lat / land_lon 匹配
    sel = []
    for la, lo in zip(pairs.land_lat.values, pairs.land_lon.values):
        i = lat_i.get(round(float(la), 4))
        j = lon_i.get(round(float(lo), 4))
        if i is None or j is None:
            continue
        if MED["lat"][0] <= la <= MED["lat"][1] and MED["lon"][0] <= lo <= MED["lon"][1]:
            sel.append((i, j))
    sel = sorted(set(sel))
    print(f"{label}: 地中海框内配对陆点 {len(sel)}")
    arr = v.values[:, [i for i, _ in sel], [j for _, j in sel]]   # (year, npts)
    ann = np.nanmean(arr, axis=1)
    years = v.time.values.astype(int)
    out[label] = {int(y): float(a) for y, a in zip(years, ann)}
    ds.close()

print()
print("=== 地中海 & 黑海区域，沿海配对点均值（天/年）===")
years_show = [1983, 1990, 2000, 2003, 2018, 2022, 2023]
print("  year   " + "  ".join(f"{k.strip():>8}" for k in FILES))
for y in years_show:
    print(f"  {y}   " + "  ".join(f"{out[k][y]:>8.1f}" for k in FILES))

print()
print("=== 论文锚点（复合暴露天数）===")
print("  2003 = 62   2022 = 78   2023 = 72")
for y, anchor in [(2003, 62), (2022, 78), (2023, 72)]:
    thw = out["THW总 "][y]
    comp = out["复合  "][y]
    print(f"  {y}: 论文 {anchor:>2} 天 | 我们 THW总 {thw:5.1f}  复合 {comp:5.1f}"
          f"  ⇒ 复合口径缺口 {anchor/max(comp,1e-9):5.1f}×，"
          f"THW 口径缺口 {anchor/max(thw,1e-9):5.1f}×")

print()
print("=== 关键判据 ===")
for y in (2003, 2022, 2023):
    thw = out["THW总 "][y]
    print(f"  {y}: 复合天数不可能超过 THW 总天数 {thw:.1f}；"
          f"{'⇒ 卡在 THW 检测' if thw < 62 else '⇒ THW 足够，卡在复合定义'}")
