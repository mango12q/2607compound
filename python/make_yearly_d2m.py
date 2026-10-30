# -*- coding: utf-8 -*-
"""
把 ERA5 逐月 d2m 文件合并成"GrADS 一定能打开"的年度文件
=========================================================

背景（2026-10 实测）
--------------------
本机 ``E:\\2607compound\\data\\ERA5\\d2m_global_daily\\`` 里的 573 个月文件
**全部是 netCDF-4 / HDF5**，而且带 ``chunking + zlib(deflate=1) + shuffle``：

    d2m encoding: {'zlib': True, 'shuffle': True, 'complevel': 1,
                   'chunksizes': (11, 361, 720), 'contiguous': False}

这类文件在 GrADS 里的两种典型报错正好对应：
  * ``NetCDF: Unknown file format``  → 文件连 HDF5 魔数都不完整（被截断 / 0 字节 /
    存成了 zip、GRIB、HTML）——**不是**数据坏了；
  * ``NetCDF: HDF error``            → 魔数在、元数据能读，但数据块（chunked+deflate）
    读不出来，多半是 netCDF/HDF5 库版本或压缩过滤器不匹配 / 文件尾部被截断。

所以最稳的出路是**转成 classic netCDF-3（CDF-2 64-bit offset）、不压缩、不分块**：
这是 GrADS ``sdfopen`` 的原生格式，任何版本都不会踩这些坑。

用法
----
    # 生成 2000–2004 五年的年度文件到 E: 盘
    python python/make_yearly_d2m.py --years 2000-2004 ^
        --out E:\\2607compound\\data\\ERA5\\d2m_yearly

    # 只体检（不写文件）：看某个目录里哪些年度文件是坏的
    python python/make_yearly_d2m.py --check-only --out G:\\ERA5\\surface

    # 目录里已有文件时强制覆盖
    python python/make_yearly_d2m.py --years 2000-2004 --out <dir> --overwrite

产物
----
``<out>\\d2m.era5.daily.<YYYY>.nc``：维度 ``time, latitude, longitude``，
变量 ``d2m``（float32，K，2 米露点温度），1412×721… 精确地说是
365/366 × 721 × 1440，≈1.4–1.5 GB/年（netCDF-3 不压缩）。
纬度默认翻成**升序**（−90 → 90），避免 GrADS 出图上下颠倒。
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time
import warnings

import numpy as np

DEFAULT_SRC = r"E:\2607compound\data\ERA5\d2m_global_daily"
DEFAULT_OUT = r"E:\2607compound\data\ERA5\d2m_yearly"
NAME_PATTERN = "d2m.era5.daily.{year}.nc"
FILL = np.float32(1e30)  # classic netCDF 用缺测标记，不用 NaN


# --------------------------------------------------------------------------- #
# 年份解析
# --------------------------------------------------------------------------- #
def parse_years(spec: str) -> list[int]:
    """'2000-2004' / '2000,2002' / '2000-2004,2010' → [2000,2001,...]"""
    years: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part[1:]:  # 注意 '2000-2004'，不把前导负号当分隔
            a, b = part.split("-", 1)
            years.extend(range(int(a), int(b) + 1))
        else:
            years.append(int(part))
    return sorted(set(years))


# --------------------------------------------------------------------------- #
# 体检
# --------------------------------------------------------------------------- #
def sniff(path: str, n: int = 8) -> str:
    if os.path.getsize(path) == 0:
        return "空文件(0B)"
    with open(path, "rb") as fh:
        head = fh.read(n)
    for magic, name in (
        (b"CDF\x01", "netCDF classic CDF-1"),
        (b"CDF\x02", "netCDF CDF-2(64-bit offset)"),
        (b"CDF\x05", "netCDF CDF-5"),
        (b"\x89HDF\r\n\x1a\n", "netCDF-4/HDF5"),
        (b"PK\x03\x04", "ZIP 压缩包(不是 NetCDF)"),
        (b"GRIB", "GRIB(不是 NetCDF)"),
        (b"<!DO", "HTML 错误页"),
        (b"<?xm", "XML 错误页"),
    ):
        if head.startswith(magic):
            return name
    return "未知格式 head=" + repr(head[:8])


def check_file(path: str) -> dict:
    """返回体检结果 dict：format / ok / dims / days / nan_frac / min / max / err"""
    from netCDF4 import Dataset

    res = {"file": path, "bytes": os.path.getsize(path) if os.path.exists(path) else -1,
           "format": sniff(path) if os.path.exists(path) else "不存在",
           "ok": False, "err": ""}
    try:
        with Dataset(path, "r") as ds:
            res["format"] = ds.file_format
            res["dims"] = {k: len(v) for k, v in ds.dimensions.items()}
            var = "d2m" if "d2m" in ds.variables else list(ds.variables)[-1]
            v = ds.variables[var]
            res["var"] = var
            res["shape"] = v.shape
            data = v[:]
            data = np.ma.masked_invalid(np.ma.filled(data.astype("float64"), np.nan))
            res["nan_frac"] = float(np.ma.getmaskarray(data).mean())
            res["min"] = float(data.min())
            res["max"] = float(data.max())
            tname = "time" if "time" in ds.variables else (
                "valid_time" if "valid_time" in ds.variables else None)
            if tname:
                import datetime as _dt
                tv = ds.variables[tname]
                res["time_units"] = getattr(tv, "units", "")
                vals = np.asarray(tv[:], dtype="float64")
                res["days"] = int(vals.size)
                res["time_step_ok"] = bool(np.allclose(np.diff(vals), 1.0))
            res["ok"] = True
    except Exception as exc:  # noqa: BLE001
        res["err"] = f"{type(exc).__name__}: {exc}"
    return res


def report(r: dict) -> None:
    tag = "OK  " if r["ok"] else "FAIL"
    line = f"  {tag} {os.path.basename(r['file']):28s} {r['bytes']/1048576:9.1f} MB  {r['format']}"
    print(line)
    if r["ok"]:
        extra = (f"        dims={r.get('dims')} days={r.get('days')} "
                 f"纳值={r.get('nan_frac', 0)*100:.3f}% "
                 f"范围={r.get('min'):.2f}..{r.get('max'):.2f} K")
        if r.get("time_step_ok") is False:
            extra += "  <-- 时间步长不是 1 天！"
        print(extra)
    else:
        print(f"        错误: {r['err']}")


# --------------------------------------------------------------------------- #
# 合并（逐月流式写 classic netCDF-3）
# --------------------------------------------------------------------------- #
def merge_year(src: str, year: int, out_path: str, lat_ascending: bool = True,
               fmt: str = "NETCDF3_64BIT") -> dict:
    from netCDF4 import Dataset

    months = sorted(glob.glob(os.path.join(src, f"d2m_global_{year}_*.nc")))
    if not months:
        raise FileNotFoundError(f"{src} 里没有 d2m_global_{year}_*.nc")
    if len(months) != 12 and not (year == time.gmtime().tm_year and len(months) >= 1):
        print(f"  [警告] {year} 只有 {len(months)} 个月文件：{[os.path.basename(m) for m in months]}")

    # 先摸清网格 + 时间
    lat = lon = None
    times = []
    for m in months:
        with Dataset(m, "r") as ds:
            if lat is None:
                lat = np.asarray(ds.variables["latitude"][:], dtype="float64")
                lon = np.asarray(ds.variables["longitude"][:], dtype="float64")
            tv = ds.variables["valid_time"]
            tu = tv.units
            vals = np.asarray(tv[:], dtype="float64")
            base = tu.split("since")[-1].strip()
            times.append((tu, base, vals))

    n_time = sum(len(v) for _, _, v in times)
    flip = lat_ascending and lat is not None and lat[0] > lat[-1]
    out_lat = lat[::-1] if flip else lat

    if os.path.exists(out_path):
        os.remove(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    nc_fmt = fmt
    with Dataset(out_path, "w", format=nc_fmt) as out:
        out.createDimension("time", n_time)
        out.createDimension("latitude", len(out_lat))
        out.createDimension("longitude", len(lon))
        vlat = out.createVariable("latitude", "f8", ("latitude",))
        vlon = out.createVariable("longitude", "f8", ("longitude",))
        vt = out.createVariable("time", "f8", ("time",))
        vv = out.createVariable("d2m", "f4", ("time", "latitude", "longitude"),
                                fill_value=FILL)

        vlat.units = "degrees_north"
        vlat.longitude = "longitude"
        vlat.standard_name = "latitude"
        vlon.units = "degrees_east"
        vlon.standard_name = "longitude"
        vt.units = "days since 1900-01-01 00:00:00"
        vt.calendar = "proleptic_gregorian"
        vt.standard_name = "time"
        vv.units = "K"
        vv.long_name = "2 metre dewpoint temperature"
        vv.short_name = "d2m"

        vlat[:] = out_lat
        vlon[:] = lon

        # 时间：统一折算成 days since 1900-01-01
        import datetime as dt
        epoch = dt.datetime(1900, 1, 1)
        tdays = np.empty(n_time, dtype="float64")
        k = 0
        for (tu, base, vals) in times:
            try:
                b = dt.datetime.fromisoformat(base.replace("Z", "").strip())
            except ValueError:
                b = dt.datetime(1900, 1, 1)
            tdays[k:k + len(vals)] = [(b - epoch).days + v for v in vals]
            k += len(vals)
        vt[:] = tdays

        # 数据：一个月一读一写，避免整年驻留内存
        pos = 0
        for m in months:
            with Dataset(m, "r") as ds:
                arr = np.asarray(ds.variables["d2m"][:], dtype="float32")
            if flip:
                arr = arr[:, ::-1, :]
            arr = np.where(np.isfinite(arr), arr, FILL)
            with warnings.catch_warnings():
                # netCDF4 1.7.4 + NumPy 2.5 内部会触发 shape 赋值弃用告警，与结果无关
                warnings.simplefilter("ignore", DeprecationWarning)
                vv[pos:pos + arr.shape[0], :, :] = arr
            pos += arr.shape[0]

        out.title = f"ERA5 daily 2m dewpoint temperature, {year}"
        out.source = "merged from ERA5 monthly d2m (netCDF-4) by make_yearly_d2m.py"
        out.history = f"{time.strftime('%Y-%m-%dT%H:%M')} merged {len(months)} monthly files -> classic netCDF-3"

    return check_file(out_path)


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="月度 d2m → GrADS 友好的年度 netCDF-3")
    ap.add_argument("--src", default=DEFAULT_SRC, help="月度文件目录")
    ap.add_argument("--out", default=DEFAULT_OUT, help="年度文件输出目录")
    ap.add_argument("--years", default=None, help="如 2000-2004 或 2000,2002")
    ap.add_argument("--pattern", default=NAME_PATTERN, help="输出文件名模板")
    ap.add_argument("--format", default="NETCDF3_64BIT",
                    choices=["NETCDF3_CLASSIC", "NETCDF3_64BIT", "NETCDF4"],
                    help="输出格式，默认 NETCDF3_64BIT（GrADS 原生）")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--no-lat-flip", action="store_true", help="保持纬度降序（ERA5 原生）")
    ap.add_argument("--check-only", action="store_true", help="只体检 --out 目录，不生成")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # ---- 只体检 ----
    if args.check_only:
        years = parse_years(args.years) if args.years else None
        files = ([os.path.join(args.out, args.pattern.format(year=y)) for y in years]
                 if years else sorted(glob.glob(os.path.join(args.out, "*.nc"))))
        print(f"体检目录: {args.out}  （{len(files)} 个文件）")
        nbad = 0
        for f in files:
            if not os.path.exists(f):
                print(f"  MISS {os.path.basename(f)}  文件不存在")
                nbad += 1
                continue
            r = check_file(f)
            report(r)
            nbad += 0 if r["ok"] else 1
        print(f"\n结论: {len(files) - nbad} 好 / {nbad} 坏")
        return 1 if nbad else 0

    if not args.years:
        ap.error("生成模式必须给 --years（或用 --check-only 只体检）")
    years = parse_years(args.years)

    print(f"源目录 : {args.src}")
    print(f"输出   : {args.out}   格式={args.format}  年份={years}")
    print("-" * 92)

    fails = []
    for y in years:
        out_path = os.path.join(args.out, args.pattern.format(year=y))
        if os.path.exists(out_path) and not args.overwrite:
            print(f"{y}: 已存在，跳过（{os.path.basename(out_path)}，用 --overwrite 覆盖）")
            continue
        t0 = time.time()
        print(f"{y}: 合并中 ...", end="", flush=True)
        try:
            r = merge_year(args.src, y, out_path, lat_ascending=not args.no_lat_flip,
                           fmt=args.format)
            print(f" 完成 {time.time() - t0:.0f}s")
            report(r)
            if not r["ok"]:
                fails.append(y)
        except Exception as exc:  # noqa: BLE001
            print(f" 失败: {type(exc).__name__}: {exc}")
            fails.append(y)

    print("-" * 92)
    print("全部完成" if not fails else f"失败年份: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
