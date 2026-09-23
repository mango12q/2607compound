# Lead 独立复核 第十一部分：POP nday1 时间标签是区间左端还是右端（决定性）
import os

import cftime
import numpy as np
import xarray as xr

RAW = r"D:\2607compound\data\CESM1-LE\raw"
PROC = r"D:\2607compound\data\CESM1-LE\proc"


def dump(f, lab, fullvars=True):
    print("=" * 78)
    print(lab)
    print(f"  {f}")
    ds = xr.open_dataset(f, decode_times=False)
    ncvars = list(ds.variables)
    print(f"  全部变量（{len(ncvars)}）: {ncvars}")
    tv = ds["time"]
    units = tv.attrs.get("units")
    cal = tv.attrs.get("calendar")
    print(f"  time units={units!r} calendar={cal!r} n={tv.size} "
          f"first={tv.values[0]} last={tv.values[-1]}")
    for bn in ("time_bnds", "time_bound", "time_bounds", "average_T1", "average_T2"):
        if bn in ds.variables:
            v = ds[bn]
            arr = np.asarray(v.values)
            u = v.attrs.get("units", units)
            print(f"  ★ {bn}: dims={v.dims} shape={arr.shape} units={u!r}")
            flat = arr.reshape(arr.shape[0], -1) if arr.ndim > 1 else arr.reshape(-1, 1)
            for i in (0, 1, 2, arr.shape[0] - 1):
                try:
                    row = flat[i]
                    if u and "since" in str(u) and row[0] < 1e7:
                        conv = [str(cftime.num2date(x, u, calendar=cal,
                                                    only_use_cftime_datetimes=True))[:10]
                                for x in row]
                        print(f"      i={i}: raw={row} -> {conv}")
                    else:
                        print(f"      i={i}: raw={row}")
                except Exception as e:
                    print(f"      i={i}: {e}")
    ds.close()


dump(os.path.join(RAW, "b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.pop.h.nday1.SST.19200102-20051231.nc"),
     "POP SST XGHG 001 (raw)")
dump(os.path.join(RAW, "b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.19200101-20051231.nc"),
     "CAM TREFHT XGHG 001 (raw)")
dump(os.path.join(PROC, "b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.pop.h.nday1.SST.19200102-20051231_2000-2021.nc"),
     "POP SST XGHG 001 (proc, 裁剪件)")
dump(os.path.join(PROC, "TREFHT_all_001_2000-2021_europe.nc"),
     "CAM TREFHT ALL 001 (proc/AWS 成品)")

print()
print("=" * 78)
print("【换算核对】time=0 在 days since 1920-01-01 下的日期")
for u, v in (("days since 1920-01-01 00:00:00", 0),
             ("days since 0000-01-01 00:00:00", 700802),
             ("days since 0000-01-01 00:00:00", 700800),
             ("days since 0000-01-01 00:00:00", 700801)):
    print(f"  {u!r} + {v} = {str(cftime.num2date(v, u, calendar='noleap', only_use_cftime_datetimes=True))[:10]}")
