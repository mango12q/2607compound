# -*- coding: utf-8 -*-
"""
ERA5 NetCDF 文件体检工具
========================

为什么需要它：GrADS 里 ``sdfopen`` 报
    Error: nc_open failed to open file ...
    NetCDF: Unknown file format
表示文件**第 1 个字节起就不是 NetCDF**（被截断 / 存成了 HTML、ZIP、GRIB、纯 0），
而 ``NetCDF: HDF error`` 表示是 HDF5(netCDF-4) 但数据块读不出来。
两者病因完全不同，必须先看魔数（magic bytes）而不是靠猜。

用法：
    python results/tools/check_era5_files.py                 # 默认扫 d2m_global_daily
    python results/tools/check_era5_files.py --dir E:\\2607compound\\data\\ERA5\\d2m_global_daily
    python results/tools/check_era5_files.py --dir G:\\ERA5\\surface --glob "d2m.era5.daily.*.nc"
    python results/tools/check_era5_files.py --dir <dir> --deep      # 再真读一遍数据（慢）
    python results/tools/check_era5_files.py --dir <dir> --csv out.csv

退出码：0 = 全部健康；1 = 有坏文件（坏文件清单见输出 / --csv）。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict

MAGIC = {
    b"CDF\x01": "netCDF classic (CDF-1)",
    b"CDF\x02": "netCDF 64-bit offset (CDF-2)",
    b"CDF\x05": "netCDF 64-bit data (CDF-5)",
    b"\x89HDF\r\n\x1a\n": "HDF5 / netCDF-4",
    b"PK\x03\x04": "ZIP 压缩包（不是 NetCDF！CDS 多文件请求会回 zip）",
    b"PK\x05\x06": "ZIP 空包",
    b"GRIB": "GRIB 格式（不是 NetCDF）",
    b"<!DO": "HTML 错误页",
    b"<?xm": "XML 错误页",
    b"{\"": "JSON 错误回包",
    b"{\n": "JSON 错误回包",
}


def sniff(path: str, n: int = 8) -> str:
    """只看前 8 个字节判断真实格式。"""
    size = os.path.getsize(path)
    if size == 0:
        return "空文件 (0 字节)"
    with open(path, "rb") as fh:
        head = fh.read(n)
    for magic, name in MAGIC.items():
        if head.startswith(magic):
            return name
    # 兜底：打印可打印字符，便于人工判断
    txt = "".join(chr(b) if 32 <= b < 127 else "·" for b in head[:8])
    return f"未知格式 (head={txt!r})"


def header_of(path: str):
    """用 netCDF4 只读元数据（快）。返回 (ok, info_or_error)。"""
    try:
        from netCDF4 import Dataset
    except Exception as exc:  # pragma: no cover
        return False, f"netCDF4 不可用: {exc}"
    try:
        with Dataset(path, "r") as ds:
            dims = {k: len(v) for k, v in ds.dimensions.items()}
            variables = list(ds.variables)
            return True, {"dims": dims, "variables": variables, "format": ds.file_format}
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def deep_check(path: str):
    """真读一遍变量数据（慢，用于确认 HDF error / 截断）。"""
    try:
        import numpy as np
        import xarray as xr
    except Exception as exc:  # pragma: no cover
        return False, f"xarray 不可用: {exc}"
    try:
        with xr.open_dataset(path, engine="netcdf4") as ds:
            var = next(iter(ds.data_vars))
            da = ds[var]
            # 逐时间步读，最容易暴露"读到一半 HDF error"
            total = 0.0
            n_nan = 0
            n = 0
            for i in range(da.sizes.get("time", da.sizes.get("valid_time", 1))):
                slab = da.isel({list(da.dims)[0]: i}).values
                slab = np.asarray(slab, dtype="float64")
                total += float(np.nansum(slab))
                n_nan += int(np.isnan(slab).sum())
                n += slab.size
            return True, {
                "var": var,
                "sum": total,
                "nan_frac": n_nan / max(n, 1),
                "shape": dict(da.sizes),
            }
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=r"E:\2607compound\data\ERA5\d2m_global_daily")
    ap.add_argument("--glob", default="*.nc", help="文件名通配，默认 *.nc")
    ap.add_argument("--deep", action="store_true", help="真读数据（慢）")
    ap.add_argument("--csv", default=None, help="把逐文件结果写成 csv")
    args = ap.parse_args()

    import fnmatch

    if not os.path.isdir(args.dir):
        print(f"[错误] 目录不存在: {args.dir}")
        return 2

    paths = [
        os.path.join(args.dir, f)
        for f in sorted(os.listdir(args.dir))
        if os.path.isfile(os.path.join(args.dir, f)) and fnmatch.fnmatch(f, args.glob)
    ]
    if not paths:
        print(f"[错误] {args.dir} 下没有匹配 {args.glob} 的文件")
        return 2

    print(f"目录 : {args.dir}")
    print(f"匹配 : {len(paths)} 个文件（{args.glob}）")
    print("-" * 100)

    rows = []
    fmt_counter = Counter()
    bad = []
    dim_sig = Counter()
    sizes = []

    for p in paths:
        name = os.path.basename(p)
        size = os.path.getsize(p)
        sizes.append(size)
        fmt = sniff(p)
        fmt_counter[fmt] += 1
        ok, info = header_of(p)
        dimsig = ""
        if ok:
            dimsig = ",".join(f"{k}={v}" for k, v in info["dims"].items())
            dim_sig[(info["format"], dimsig)] += 1
        else:
            bad.append((name, size, fmt, info))
        deep_note = ""
        if args.deep and ok:
            dok, dinfo = deep_check(p)
            if not dok:
                deep_note = f"DEEP_FAIL {dinfo}"
                bad.append((name, size, fmt, f"deeph: {dinfo}"))
            else:
                deep_note = f"sum={dinfo['sum']:.3g} nan={dinfo['nan_frac']*100:.2f}% {dinfo['shape']}"
                if dinfo["nan_frac"] > 0.99:
                    deep_note += "  <-- 全 NaN"
        rows.append([name, size, fmt, "OK" if ok else "FAIL", dimsig, deep_note])
        print(f"{name:28s} {size/1048576:8.2f} MB  {fmt:52s} "
              f"{('OK  ' + dimsig) if ok else ('FAIL ' + info)} {deep_note}")

    print("-" * 100)
    print("格式统计：")
    for fmt, n in fmt_counter.most_common():
        print(f"  {n:5d}  {fmt}")
    print("维度签名统计（正常的年/月文件应只有 1–2 种）：")
    for (fmt, dimsig), n in dim_sig.most_common():
        print(f"  {n:5d}  [{fmt}] {dimsig}")
    if sizes:
        print(f"体积：最小 {min(sizes)/1048576:.2f} MB / 中位 "
              f"{sorted(sizes)[len(sizes)//2]/1048576:.2f} MB / 最大 {max(sizes)/1048576:.2f} MB")

    if bad:
        print()
        print(f"### 坏文件 {len(bad)} 个 ###")
        for name, size, fmt, err in bad:
            print(f"  {name}  ({size} B)  格式={fmt}\n      {err}")
        # 按年份汇总，便于看"哪几年连片坏"
        years = defaultdict(list)
        for name, *_ in bad:
            ys = [t for t in name.replace(".", "_").split("_") if len(t) == 4 and t.isdigit() and t[:2] in ("19", "20")]
            years[ys[0] if ys else "?"].append(name)
        print("按年份汇总：")
        for y in sorted(years):
            print(f"  {y}: {len(years[y])} 个  {', '.join(years[y])}")
    else:
        print("\n全部文件头正常。")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "bytes", "format", "status", "dims", "deep"])
            w.writerows(rows)
        print(f"\n逐文件结果已写: {args.csv}")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
