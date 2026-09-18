"""snapshot_fig_stats.py — 对图1/图2 用到的中间产物做数值快照。

用法:
  python snapshot_fig_stats.py old   # 在重跑 run_all.py 之前调用（读当前 .nc）
  python snapshot_fig_stats.py new   # 重跑之后调用

输出: results/tables/fig_stats_<tag>.json
比较基准（论文 / 交接记录）:
  - 图2(c) CHR 时序量级应回到 0.4-0.9（论文），旧管线约 0.22
  - 图2(d) CHR 空间图 0-5
  - 图1 各年复合日数空间型（2003/2006/2010/2012/2018/2019/2020/2022/2023）
"""
import json
import os
import sys

import numpy as np
import xarray as xr

INTER = r"D:\2607compound\results\intermediate"
TABLES = r"D:\2607compound\results\tables"


def series_stats(v, years):
    v = np.asarray(v, dtype=float)
    sl, ic = np.polyfit(years, v, 1)
    return {
        "years": [int(y) for y in years],
        "values": [round(float(x), 4) for x in v],
        "mean": round(float(np.nanmean(v)), 4),
        "min": round(float(np.nanmin(v)), 4),
        "max": round(float(np.nanmax(v)), 4),
        "trend_per_decade": round(float(sl * 10), 4),
        "val_2003": round(float(v[list(years).index(2003)]), 4) if 2003 in years else None,
        "val_2010": round(float(v[list(years).index(2010)]), 4) if 2010 in years else None,
        "val_2018": round(float(v[list(years).index(2018)]), 4) if 2018 in years else None,
        "val_2023": round(float(v[list(years).index(2023)]), 4) if 2023 in years else None,
    }


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "old"
    out = {}

    comp = xr.open_dataset(os.path.join(INTER, "annual_compound_days.nc"))["compound_mhw_thw"]
    std = xr.open_dataset(os.path.join(INTER, "annual_standalone_days.nc"))["standalone_thw"]
    chr_ds = xr.open_dataset(os.path.join(INTER, "CHR_annual.nc"))
    chr_da = chr_ds[list(chr_ds.data_vars)[0]]

    # 图2(c): 欧洲加权 CHR 时序 = sum(compound)/sum(standalone)
    c = comp.sel(lat=slice(30, 72), lon=slice(-15, 45))
    s = std.sel(lat=slice(30, 72), lon=slice(-15, 45))
    w = np.cos(np.deg2rad(c.lat))
    chr_ts = ((c * w).sum(dim=["lat", "lon"]) / (s * w).sum(dim=["lat", "lon"])).values
    years = comp.time.values.astype(int)
    out["fig2c_chr_timeseries"] = series_stats(chr_ts, years)

    # 图2(a)(b)(d): 2003-2023 平均空间场
    for name, da in (("fig2a_compound_days", comp),
                     ("fig2b_standalone_days", std),
                     ("fig2d_chr_map", chr_da)):
        m = da.sel(time=slice(2003, 2023)).mean(dim="time").values.astype(float)
        pos = m[m > 0]
        out[name] = {
            "nonzero_points": int(pos.size),
            "mean_of_nonzero": round(float(pos.mean()), 4) if pos.size else None,
            "p50_of_nonzero": round(float(np.percentile(pos, 50)), 4) if pos.size else None,
            "p95_of_nonzero": round(float(np.percentile(pos, 95)), 4) if pos.size else None,
            "max": round(float(m.max()), 4),
        }

    # 图1 区域时序（地中海&黑海 / 波罗的海 / 全欧洲沿海）
    regions = [
        ("fig1j_med_black_sea", (30, 47), (5, 42)),
        ("fig1k_baltic", (53, 66), (10, 30)),
        ("fig1l_european_coasts", (30, 72), (-15, 45)),
    ]
    for nm, (la0, la1), (lo0, lo1) in regions:
        r = comp.sel(lat=slice(la0, la1), lon=slice(lo0, lo1))
        mask = r.mean(dim="time") > 0
        r_m = r.where(mask) if int(mask.sum()) >= 5 else r
        w2 = np.cos(np.deg2rad(r_m.lat))
        ts = r_m.weighted(w2).mean(dim=["lat", "lon"]).values
        out[nm] = series_stats(np.asarray(ts, dtype=float), years)

    os.makedirs(TABLES, exist_ok=True)
    path = os.path.join(TABLES, f"fig_stats_{tag}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(json.dumps({k: (v if not isinstance(v, dict) or "values" not in v
                          else {kk: vv for kk, vv in v.items() if kk != "values"})
                      for k, v in out.items()}, ensure_ascii=False, indent=2))
    print(f"\nsaved: {path}")


if __name__ == "__main__":
    main()
