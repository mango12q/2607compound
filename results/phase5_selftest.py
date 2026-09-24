"""
phase5_selftest.py — Phase 5（图5/图6）**纯合成**自检：不读任何真实观测数据

覆盖三件事：
  1. 统计口径正确性：`phase5_humid.stats_fig6` 在**构造好的** WBT/SH 场上是否给出
     可解析预期的超阈频率曲线、重现期曲线与复合日 WBT 场；
  2. 年集合口径：图6 的 3 个复合年 + 论文 Fig.6c 图例的 11 个非复合年是否被正确使用；
  3. 出图链路：`fig6_wbt.make_figure` 能否在合成统计产物上产出 PNG（a–c 面板）。

运行：`python results\\phase5_selftest.py` → 期望 `ALL PHASE5 SELFTESTS PASSED`
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

import numpy as np
import xarray as xr

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "python"))

import config as C              # noqa: E402
import phase5_humid as P        # noqa: E402

FAIL = []


def check(name, cond, extra=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))
    if not cond:
        FAIL.append(name)


def _synth_field(years, base=20.0, amp=3.0, seed=0, name="WBT"):
    """
    构造 (time, lat, lon) 合成场：与掩码网格一致，逐年升温便于验证超阈/重现期。

    ⚠️ 必须**向量化**构造：40 年 × 68×148 的逐日循环会产生 1.4×10⁸ 个随机数，
    第一版按天循环直接跑到超时。
    """
    mask = P._buffer_mask()
    lat, lon = mask["lat"].values, mask["lon"].values
    rng = np.random.default_rng(seed)
    times = xr.date_range(f"{min(years)}-01-01", f"{max(years)}-12-31", freq="D")
    doy = times.dayofyear.values.astype(float)
    yr = times.year.values.astype(float)
    season = amp * np.sin(2 * np.pi * (doy - 172) / 365.25)
    year_off = (yr - min(years)) * 0.08
    spatial = np.linspace(-1.0, 1.0, lat.size)[:, None] * np.ones(lon.size)
    vals = (base + year_off[:, None, None] + season[:, None, None]
            + spatial[None, :, :]
            + rng.normal(0, 0.3, (times.size, lat.size, lon.size)))
    return xr.DataArray(vals.astype("float32"), dims=("time", "lat", "lon"),
                        coords={"time": times, "lat": lat, "lon": lon}, name=name)


def main():
    print("=" * 74)
    print("Phase 5 自检（纯合成数据，不读磁盘观测）")
    print("=" * 74)

    mask = P._buffer_mask()
    # 只需覆盖"复合年 + 若干非复合年"即可验证口径；全量 40 年会显著拖慢自检
    years = sorted({*C.WBT_RP_YEARS, C.WBT_NONCOMPOUND_YEAR_PAPER,
                    1984, 1988, 2004, 2008})

    # 1) 年集合口径
    print("\n1) 图6 年份集合口径（以论文 Fig.6c 图例为准）")
    check("复合年 = 2003/2022/2023", tuple(C.WBT_RP_YEARS) == (2003, 2022, 2023))
    check("非复合年 = 论文图例 11 年（含 2000）",
          len(C.WBT_NONCOMPOUND_YEARS) == 11 and 2000 in C.WBT_NONCOMPOUND_YEARS,
          f"{len(C.WBT_NONCOMPOUND_YEARS)} 年：{C.WBT_NONCOMPOUND_YEARS}")
    check("S1 判读口径保留为敏感性对照",
          set(C.WBT_NONCOMPOUND_YEARS_S1) <= set(C.WBT_NONCOMPOUND_YEARS) | {1985, 1989, 1998})

    # 2) 统计链路
    print("\n2) stats_fig6 在合成场上跑通并给出可解析结果")
    wbt = _synth_field(years, base=22.0, amp=4.0, seed=1, name="WBT")
    sh = wbt - 7.0
    sh.name = "SH"
    stats = P.stats_fig6(wbt, sh, verbose=False)
    check("exceedance_curves 两种变量都在",
          set(stats["exceedance_curves"]) == {"wbt", "sh"})
    ec = stats["exceedance_curves"]["wbt"]
    want = set(C.WBT_RP_YEARS) | set(C.WBT_NONCOMPOUND_YEARS)
    check("超阈曲线覆盖全部 14 个设计年份（3 复合 + 11 非复合）",
          set(map(int, ec)) == want,
          f"got {len(ec)} 年 / need {len(want)} 年")
    d23 = ec[2023]["days"]
    d84 = ec[1984]["days"]
    check("超阈天数随阈值单调不增",
          all(np.diff([v for v in d23 if v is not None]) <= 1e-6))
    check("升温年（2023）同阈值天数 ≥ 早期年（1984）",
          float(d23[0]) >= float(d84[0]), f"2023={d23[0]:.1f} vs 1984={d84[0]:.1f}")
    check("阈值轴长度 = config 定义",
          len(ec[2023]["thresholds"]) == len(C.WBT_EXCEED_THRESHOLDS))
    check("rp_curves 非空且含 2023", 2023 in set(map(int, stats["rp_curves"])),
          f"got {sorted(map(int, stats['rp_curves']))}")
    rp = stats["rp_curves"][2023]
    fin = [v for v in rp["rp"] if v is not None]
    check("重现期随阈值单调不减",
          all(np.diff(fin) >= -1e-9), f"rp={np.round(fin[:5], 2)}…")
    check("spatial_fields 三个复合年都在",
          set(map(int, stats["spatial_fields"])) == set(C.WBT_RP_YEARS))
    check("annual_days 含 25.5 与 19 两档",
          set(stats["annual_days"]) == {"wbt25.5", "sh19"})

    # 3) 出图链路（合成统计产物 → PNG）
    print("\n3) fig6_wbt 出图链路（a–c 面板）")
    tmp = tempfile.mkdtemp(prefix="phase5_selftest_")
    try:
        jpath = os.path.join(tmp, "fig6_stats.json")
        with open(jpath, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, default=lambda o: (None if isinstance(o, float)
                                                    and not np.isfinite(o) else str(o)))
        import fig6_wbt
        out = fig6_wbt.make_figure(outdir=tmp, dpi=90, only_curves=True,
                                   stats_path=jpath)
        check("fig6_wbt 产出 PNG", os.path.exists(out) and os.path.getsize(out) > 10_000,
              f"{os.path.getsize(out) if os.path.exists(out) else 0} bytes")
    except Exception as exc:                                   # pragma: no cover
        import traceback
        traceback.print_exc()
        check("fig6_wbt 产出 PNG", False, f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 74)
    print("4) OAFlux 蒸发链路（图5b）—— 合成件，端到端口径核对")
    print("=" * 74)
    tmp2 = tempfile.mkdtemp(prefix="phase5_oaflux_")
    try:
        import xarray as xr
        from calc_wbt import seasonal_mean, linear_trend_per_decade
        import load_data as L

        # 合成：1° 网格、1991–2020 逐月、单位 cm/yr，JAS 值 = 基线 + 已知线性趋势
        lat = np.arange(25.0, 70.01, 1.0)
        lon = np.arange(-20.0, 45.01, 1.0)
        times = xr.date_range("1991-01-01", "2020-12-01", freq="MS")
        yrs = times.year.values
        doy_season = np.where(np.isin(times.month.values, [7, 8, 9]), 1.0, 0.0)
        slope_per_year = 0.6                       # 6.0 cm/yr per decade
        base = 40.0 + (yrs - 1991) * slope_per_year
        field = (base[:, None, None] * doy_season[:, None, None]
                 + 5.0 * (1 - doy_season)[:, None, None]
                 + np.zeros((times.size, lat.size, lon.size), dtype="float32"))
        ds = xr.Dataset({"evap": (("time", "lat", "lon"), field.astype("float32"),
                                  {"units": "cm/yr"})},
                        coords={"time": times, "lat": lat, "lon": lon})
        p = os.path.join(tmp2, "OAFlux_evap_synth.nc")
        ds.to_netcdf(p)

        oa = L.load_oaflux(filepath=p)
        check("load_oaflux 读出合成件并归一维度",
              {"lat", "lon"} <= set(oa.dims) or {"lat", "lon"} <= set(oa["evap"].dims),
              f"dims={dict(oa.sizes)}")
        ev = L.oaflux_evap_cm_per_year(oa, var="evap")
        check("单位保留原始值（cm/yr）", ev.attrs.get("units_original") == "cm/yr")
        slope, _ = linear_trend_per_decade(seasonal_mean(ev, (7, 8, 9), (1991, 2020)))
        got = float(np.nanmedian(slope.values))
        check("合成趋势 +6.0 cm/yr/decade 被准确恢复", abs(got - 6.0) < 1e-3,
              f"got {got:+.4f}")
        # 未登记单位必须明确报错，不能静默当成 cm/yr
        ds2 = ds.copy()
        ds2["evap"].attrs["units"] = "furlongs/fortnight"
        p2 = os.path.join(tmp2, "bad_units.nc")
        ds2.to_netcdf(p2)
        try:
            L.oaflux_evap_cm_per_year(L.load_oaflux(filepath=p2), var="evap")
            check("未登记单位明确报错", False, "居然没报错")
        except ValueError as exc:
            check("未登记单位明确报错（不静默当 cm/yr）", "未登记" in str(exc))
    except Exception as exc:                                   # pragma: no cover
        import traceback
        traceback.print_exc()
        check("OAFlux 链路端到端", False, f"{type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)

    print("\n" + "=" * 74)
    print("5) 图6d–f 地图面板（cartopy + 离散色标）—— 合成场")
    print("=" * 74)
    tmp3 = tempfile.mkdtemp(prefix="phase5_maps_")
    _old_int = C.INTERMEDIATE_DIR
    try:
        import xarray as xr
        lat = np.arange(30.0, 60.01, 0.25)
        lon = np.arange(-10.0, 40.01, 0.25)
        for yr, bias in zip(C.WBT_RP_YEARS, (1.0, 3.0, 5.0)):
            f = 20.0 + bias + 2.0 * np.cos(np.deg2rad(lat))[:, None] * 0 + \
                0.02 * lon[None, :]
            da = xr.DataArray(f.astype("float32"), dims=("lat", "lon"),
                              coords={"lat": lat, "lon": lon})
            xr.Dataset({"wbt_mean": da, "wbt_max": da + 1.5}).to_netcdf(
                os.path.join(tmp3, f"wbt_compound_{yr}.nc"))
        jpath = os.path.join(tmp3, "fig6_stats.json")
        with open(jpath, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, default=str)
        C.INTERMEDIATE_DIR = tmp3          # fig6_wbt 在调用时读该常量
        import fig6_wbt
        out = fig6_wbt.make_figure(outdir=tmp3, dpi=80, only_curves=False,
                                   stats_path=jpath, outname="fig6_maps_probe")
        check("含 d–f 地图面板的完整图6 渲染成功",
              os.path.exists(out) and os.path.getsize(out) > 20_000,
              f"{os.path.getsize(out) if os.path.exists(out) else 0} bytes")
    except Exception as exc:                                   # pragma: no cover
        import traceback
        traceback.print_exc()
        check("图6d–f 地图面板渲染", False, f"{type(exc).__name__}: {exc}")
    finally:
        C.INTERMEDIATE_DIR = _old_int
        shutil.rmtree(tmp3, ignore_errors=True)

    print("\n" + "=" * 74)
    if FAIL:
        print(f"SELFTEST FAILED: {len(FAIL)} 项 -> {FAIL}")
        return 1
    print("ALL PHASE5 SELFTESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
