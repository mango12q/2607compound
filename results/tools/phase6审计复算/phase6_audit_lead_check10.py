# Lead 独立复核 第十部分：CAM vs POP 的时间区间约定（决定性检查）
import os

import numpy as np
import xarray as xr

RAW = r"D:\2607compound\data\CESM1-LE\raw"

files = [
    ("b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.19200101-20051231.nc",
     "CAM TREFHT XGHG (raw)"),
    ("b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.pop.h.nday1.SST.19200102-20051231.nc",
     "POP SST XGHG (raw)"),
    ("b.e11.B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.SST.18500102-20051231.nc",
     "POP SST ALL 001 (raw)"),
]

for f, lab in files:
    p = os.path.join(RAW, f)
    if not os.path.exists(p):
        print(f"!! 缺 {f}")
        continue
    print("=" * 78)
    print(lab)
    print(f"  文件: {f}")
    ds = xr.open_dataset(p, decode_times=False)
    tv = ds["time"]
    print(f"  time: units={tv.attrs.get('units')!r} calendar={tv.attrs.get('calendar')!r} "
          f"n={tv.size}")
    print(f"    first5={tv.values[:5]}  last3={tv.values[-3:]}")
    # 找 bounds
    for bn in ("time_bnds", "time_bounds", "time_bounds_e", "average_T1", "average_T2",
               "nbnd", "bnds"):
        if bn in ds.variables:
            v = ds[bn]
            try:
                arr = v.values
                print(f"    {bn}: dims={v.dims} shape={arr.shape} "
                      f"units={v.attrs.get('units')!r}")
                print(f"      [0]={arr[0]}   [1]={arr[1] if arr.shape[0] > 1 else 'NA'}")
            except Exception as e:
                print(f"    {bn}: 读取失败 {e}")
    if "average_T1" in ds.variables and "average_T2" in ds.variables:
        t1 = ds["average_T1"].values.ravel()
        t2 = ds["average_T2"].values.ravel()
        base = "days since 0001-01-01 00:00:00"
        for k in ("average_T1", "average_T2"):
            u = ds[k].attrs.get("units")
            if u:
                base = u
        import cftime
        print(f"    average_T1/T2 单位={base!r}")
        for i in (0, 1, 2):
            d1 = cftime.num2date(t1[i], base, only_use_cftime_datetimes=True) if t1[i] < 1e10 else t1[i]
            print(f"      i={i}: T1={t1[i]} T2={t2[i]}")
        print("      （POP: average_T1/T2 为区间左右端；CAM 通常无此变量）")
    print(f"  变量: {list(ds.data_vars)[:12]}")
    ds.close()
