# -*- coding: utf-8 -*-
"""年度 d2m 文件总审计：格式 / 天数 / 时间轴连续性 / 网格 / 缺测 / 数值范围

    python logs\audit_yearly_d2m.py [目录]

判据（任一条不满足即 FAIL）：
  1. 格式必须是 NETCDF3_CLASSIC 或 NETCDF3_64BIT_OFFSET（GrADS sdfopen 原生）；
  2. 维度名必须是 time/latitude/longitude，大小 (365|366, 721, 1440)；
  3. 时间轴必须是 1 天步长、从 YYYY-01-01 起连续，无重复无跳跃；
  4. 纬度升序且为 -90..90，经度 -180..179.75；
  5. 缺测比例 < 0.5%（用 _FillValue 判定，不是 NaN）。
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import numpy as np
from netCDF4 import Dataset

EPOCH = dt.datetime(1900, 1, 1)
GOOD_FMT = {"NETCDF3_CLASSIC", "NETCDF3_64BIT_OFFSET"}


def audit(path: str) -> tuple[str, str]:
    """返回 (状态, 说明)，状态 ∈ OK / PART（年份还没走完，但已有时段连续）/ FAIL"""
    name = os.path.basename(path)
    year = int(name.split(".")[-2])
    try:
        with Dataset(path, "r") as d:
            fmt = d.data_model
            if fmt not in GOOD_FMT:
                return "FAIL", f"格式 {fmt} 不是 netCDF-3 classic"
            v = d.variables["d2m"]
            dims = {k: len(d.dimensions[k]) for k in d.dimensions}
            if set(dims) != {"time", "latitude", "longitude"}:
                return "FAIL", f"维度异常 {dims}"
            n = dims["time"]
            ndays = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
            partial = n < ndays
            if n > ndays:
                return "FAIL", f"天数 {n} > {ndays}"
            if dims["latitude"] != 721 or dims["longitude"] != 1440:
                return "FAIL", f"网格 {dims['latitude']}x{dims['longitude']} != 721x1440"

            tv = d.variables["time"]
            t = np.asarray(tv[:], dtype="float64")
            base = tv.units.split("since")[-1].strip()
            b = dt.datetime.fromisoformat(base)
            off = (b - EPOCH).days
            dates = [EPOCH + dt.timedelta(days=float(x) + off) for x in t]
            expect0 = dt.date(year, 1, 1)
            if dates[0].date() != expect0:
                return "FAIL", f"起始日 {dates[0].date()} != {expect0}"
            gaps = [i for i in range(1, n) if (dates[i] - dates[i - 1]) != dt.timedelta(days=1)]
            if gaps:
                return "FAIL", f"时间轴有 {len(gaps)} 处断点，首个在 index {gaps[0]}"
            if not partial and dates[-1].date() != dt.date(year, 12, 31):
                return "FAIL", f"结束日 {dates[-1].date()} != {year}-12-31"

            lat = np.asarray(d.variables["latitude"][:], dtype="float64")
            lon = np.asarray(d.variables["longitude"][:], dtype="float64")
            if abs(lat[0] + 90) > 1e-6 or abs(lat[-1] - 90) > 1e-6 or np.any(np.diff(lat) <= 0):
                return "FAIL", f"纬度不是升序 -90..90（{lat[0]}..{lat[-1]}）"
            if abs(lon[0] + 180) > 1e-6 or abs(lon[-1] - 179.75) > 1e-6:
                return "FAIL", f"经度 {lon[0]}..{lon[-1]}"

            fill = v.getncattr("_FillValue") if "_FillValue" in v.ncattrs() else None
            n_fill = 0
            tot = 0
            vmin, vmax = 1e9, -1e9
            for i in range(n):
                a = np.asarray(v[i], dtype="float32")
                tot += a.size
                if fill is not None:
                    bad = ~np.isfinite(a) | (np.abs(a - np.float32(fill)) < 1)
                else:
                    bad = ~np.isfinite(a)
                n_fill += int(bad.sum())
                g = a[~bad]
                if g.size:
                    vmin = min(vmin, float(g.min()))
                    vmax = max(vmax, float(g.max()))
            frac = n_fill / tot
            if frac > 0.005:
                return "FAIL", f"缺测 {frac * 100:.2f}% 偏高"
            if not (150 <= vmin and vmax <= 340):
                return "FAIL", f"数值范围 {vmin:.2f}..{vmax:.2f} K 不合理"
            span = f"{n} 天连续" if not partial else f"{n}/{ndays} 天（止于 {dates[-1].date()}）"
            return ("OK" if not partial else "PART"), (
                f"{span} | {vmin:.2f}..{vmax:.2f} K | "
                f"缺测 {frac * 100:.3f}% | {os.path.getsize(path) / 2**20:.0f} MB | {fmt}")
    except Exception as exc:  # noqa: BLE001
        return "FAIL", f"{type(exc).__name__}: {exc}"


def main() -> int:
    d = sys.argv[1] if len(sys.argv) > 1 else r"E:\2607compound\data\ERA5\d2m_yearly"
    files = sorted(f for f in os.listdir(d) if f.endswith(".nc"))
    if not files:
        print(f"目录里没有 .nc：{d}")
        return 1
    print(f"审计目录: {d}  （{len(files)} 个文件）")
    print("-" * 100)
    bad = 0
    part = 0
    tot = 0
    for f in files:
        p = os.path.join(d, f)
        st, msg = audit(p)
        tot += os.path.getsize(p)
        tag = {"OK": "  OK   ", "PART": "  PART ", "FAIL": "  FAIL "}[st]
        print(tag + f"{f:<28} {msg}")
        bad += 1 if st == "FAIL" else 0
        part += 1 if st == "PART" else 0
    print("-" * 100)
    print(f"结论: {len(files) - bad - part} 好 / {part} 未走完（正常） / {bad} 坏 | 合计 {tot / 2**30:.1f} GB")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
