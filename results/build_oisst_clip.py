"""build_oisst_clip.py — 把 23 GB 全球 OISST 裁剪成欧洲域子集，供 R 检测使用。

为什么必须先裁剪：
  原始 OISST = 15340 x 720 x 1440 = 15.9 G 格点。R 逐点随机读会极慢，
  裁到欧洲域（约 340 x 204 x 14975）后可整块读入内存逐点检测。

★ 性能教训（2025-09-18 修订）★
  旧版先 assign_coords(lon=wrap) 再 sortby("lon") 然后 .sel(lon=slice(...))。
  这会把"需要的经度"变成横跨数组首尾的两段索引，xarray 在 23 GB 文件上
  逐步随机跳读，20 分钟墙钟只用了 173 秒 CPU（纯 I/O 等待）。
  正确做法：**按索引区间切片**（两段连续区间），读完后才改坐标值。
  时间维选 1983-2023 也在读之前完成（连续区间，同样便宜）。

期望输出: (time=14975, lat=204, lon=340)，lat 25.125..75.875，
          lon（卷绕后）-34.875..49.875，升序。
"""
import os
import sys
import time

import numpy as np
import xarray as xr

SRC = r"E:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc"
DST = r"E:\2607compound\data\OISST\oisst_v2.1_eur_1983_2023.nc"
LON_MIN, LON_MAX = -35.0, 50.0
LAT_MIN, LAT_MAX = 25.0, 76.0
YEAR0, YEAR1 = 1983, 2023


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def contiguous_slice(mask, name):
    """bool mask -> (start, stop) 切片参数；要求选中索引连续，否则 fail fast。"""
    idx = np.where(mask)[0]
    if idx.size == 0:
        raise ValueError(f"{name}: no coordinates selected")
    if not np.all(np.diff(idx) == 1):
        raise ValueError(f"{name}: selected indices are not contiguous, "
                         f"got {idx[:5]}...{idx[-5:]}")
    return int(idx[0]), int(idx[-1]) + 1


if os.path.exists(DST):
    log(f"already exists: {DST} ({os.path.getsize(DST)/1e9:.2f} GB)")
    sys.exit(0)

t0 = time.time()
ds = xr.open_dataset(SRC)
ds = ds[["sst"]]
log(f"opened source: {dict(ds.sizes)}")

# ---- 1. 只读坐标，算出连续的索引区间（不碰数据）----
lon_vals = np.asarray(ds.lon.values, dtype=float)
lat_vals = np.asarray(ds.lat.values, dtype=float)
log(f"source lon: {lon_vals[0]} .. {lon_vals[-1]}  ({lon_vals.size} pts)")
log(f"source lat: {lat_vals[0]} .. {lat_vals[-1]}  ({lat_vals.size} pts)")

# 经度域 -35..50 在 0..360 坐标里是两段：[325, 360) 和 [0, 50]
seg_west = lon_vals >= (LON_MIN + 360.0)   # >= 325 -> 卷绕后是负经度
seg_east = lon_vals <= LON_MAX             # 0..50 直接保留
w0, w1 = contiguous_slice(seg_west, "lon(west segment)")
e0, e1 = contiguous_slice(seg_east, "lon(east segment)")
a0, a1 = contiguous_slice((lat_vals >= LAT_MIN) & (lat_vals <= LAT_MAX), "lat")
log(f"index ranges: lon_west [{w0}:{w1}) -> {lon_vals[w0]}..{lon_vals[w1-1]}"
    f" | lon_east [{e0}:{e1}) -> {lon_vals[e0]}..{lon_vals[e1-1]}"
    f" | lat [{a0}:{a1}) -> {lat_vals[a0]}..{lat_vals[a1-1]}")

# ---- 2. 时间切到 1983-2023（连续区间，同样在读数据前完成）----
sub_t = ds.sel(time=slice(f"{YEAR0}-01-01", f"{YEAR1}-12-31"))
ntime = sub_t.sizes["time"]
log(f"time selected: {ntime} days ({str(sub_t.time.values[0])[:10]} .. "
    f"{str(sub_t.time.values[-1])[:10]})")

# ---- 3. 按索引切片读数据：西段在前（卷绕后为负经度），东段在后，
#         concat 后经度天然升序，无需 sortby ----
log("slicing two contiguous lon segments through the 23 GB file (be patient)...")
t_read = time.time()
west = sub_t.isel(lon=slice(w0, w1), lat=slice(a0, a1))
east = sub_t.isel(lon=slice(e0, e1), lat=slice(a0, a1))
sub = xr.concat([west, east], dim="lon")
sub = sub.load()
log(f"loaded in {time.time()-t_read:.0f}s "
    f"(total {time.time()-t0:.0f}s); valid sst fraction "
    f"{float(sub.sst.notnull().mean()):.4f}")

# ---- 4. 读完才卷绕坐标（只改标签，不影响任何读取顺序）----
sub = sub.assign_coords(lon=((sub.lon + 180.0) % 360.0) - 180.0)
lon_final = sub.lon.values
if not np.all(np.diff(lon_final) > 0):
    raise ValueError("wrapped lon is not strictly ascending — unexpected grid order")
log(f"clipped: {dict(sub.sizes)}  lon {lon_final[0]}..{lon_final[-1]}  "
    f"lat {sub.lat.values[0]}..{sub.lat.values[-1]}")

# ---- 5. float32 写盘 ----
sub = sub.astype({"sst": "float32"})
sub.attrs["history"] = (
    f"Clipped from {os.path.basename(SRC)} to European domain "
    f"lon[{LON_MIN},{LON_MAX}] lat[{LAT_MIN},{LAT_MAX}] {YEAR0}-{YEAR1}, "
    f"index-based slicing (two contiguous lon segments), "
    f"longitude wrapped to -180..180 after read")
log(f"writing {DST} ...")
sub.to_netcdf(DST, encoding={"sst": {"zlib": True, "complevel": 4}})
ds.close()
log(f"wrote {DST} ({os.path.getsize(DST)/1e9:.2f} GB) total {time.time()-t0:.0f}s")

# ---- 6. 复读校验 ----
chk = xr.open_dataset(DST)
ok = (chk.sizes["time"] == ntime and chk.sizes["lat"] == a1 - a0
      and chk.sizes["lon"] == (w1 - w0) + (e1 - e0))
log(f"reopen check: {dict(chk.sizes)}  shape_ok={ok}  "
    f"valid={float(chk.sst.notnull().mean()):.4f}  "
    f"lon {chk.lon.values[0]}..{chk.lon.values[-1]}  "
    f"lat {chk.lat.values[0]}..{chk.lat.values[-1]}")
chk.close()
if not ok:
    raise SystemExit("clip shape mismatch — inspect before proceeding")
log("DONE")
