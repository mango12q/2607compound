# -*- coding: utf-8 -*-
"""
download_era5_tmax.py — Phase 5 (湿热应力) 输入数据: ERA5 日最高气温 (tmax)

论文需求 (复现方案 Phase 5 / DATA_REQUIREMENTS.md 数据集 3):
    ERA5 日最高气温, 1984-2023, 0.25°, 欧洲框 (N66 W-10 S30 E40),
    与已就位的 d2m_global_daily (0.25° 日值) / sp (1.0° 日值) 配合计算 WBT。

数据源 (官方, 已核实):
    Copernicus CDS 数据集 `derived-era5-single-levels-daily-statistics`
      ("ERA5 post-processed daily statistics on single levels from 1940 to present",
       DOI: 10.24381/cds.4991cf48)
    - product_type : reanalysis
    - variable     : maximum_2m_temperature_since_previous_post_processing
    - daily_statistic : daily_maximum   (注意: 键名是 daily_statistic, 不是 statistic)
    - time_zone    : utc+00:00          (欧洲午后最高值均落在同一 UTC 日内,
                                          对欧洲区域 UTC 日最大值 == 当地日最大值)
    - frequency    : 1_hourly
    - data_format  : netcdf  (CDS netcdf 变量名为 GRIB 短名 mx2t, 与本地 d2m/sp 短名约定一致)

输出:
    data/ERA5/tmax_eur_daily/tmax_eur_YYYY_MM.nc   按月分文件 (断点续传单位)
    data/ERA5/ERA5_tmax_1984_2023_daily.nc         --merge 合并件 (TECHNICAL_SPEC 命名)

首次使用前 (一次性):
    1. pip install cdsapi xarray netcdf4
    2. 注册 https://cds.climate.copernicus.eu/ -> Profile 页获取 Personal Access Token
    3. 写 C:\\Users\\<用户>\\.cdsapirc :
         url: https://cds.climate.copernicus.eu/api
         key: <你的 Personal Access Token>
    4. 在数据集页面 https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics
       登录后点击一次 "Accept terms" (CC-BY 许可), 否则 API 会拒绝请求。

用法:
    python python/download_era5_tmax.py                 # 下载 1984-2023 (缺哪月补哪月)
    python python/download_era5_tmax.py --start 1983 --end 2023
    python python/download_era5_tmax.py --merge         # 仅合并已有月文件
"""
import argparse
import calendar
import os
import sys
import time

BASE_DIR = r"D:\2607compound"
ERA5_DIR = os.path.join(BASE_DIR, "data", "ERA5")
OUT_DIR = os.path.join(ERA5_DIR, "tmax_eur_daily")
MERGED_PATH = os.path.join(ERA5_DIR, "ERA5_tmax_1984_2023_daily.nc")

DATASET = "derived-era5-single-levels-daily-statistics"
VARIABLE = "maximum_2m_temperature_since_previous_post_processing"
AREA = [66, -10, 30, 40]          # CDS area 顺序: [N, W, S, E]
DEFAULT_START, DEFAULT_END = 1984, 2023
MAX_RETRY = 5


def ensure_utf8_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check_credentials():
    """校验 CDS 凭据 (环境变量 CDSAPI_URL/CDSAPI_KEY 或 ~/.cdsapirc), 不通过则给出明确指引。"""
    if os.environ.get("CDSAPI_URL") and os.environ.get("CDSAPI_KEY"):
        print("凭据: 使用环境变量 CDSAPI_URL / CDSAPI_KEY")
        return
    p = os.path.expanduser("~/.cdsapirc")
    if os.path.exists(p):
        txt = open(p, encoding="utf-8", errors="ignore").read()
        has_url = "url" in txt
        has_key = "key" in txt and any(
            ln.split(":", 1)[1].strip() for ln in txt.splitlines()
            if ln.lower().startswith("key")
        )
        if has_url and has_key:
            print(f"凭据: 使用 {p}")
            return
    sys.exit(
        "\n[错误] 未找到 CDS API 凭据。请按以下步骤配置 (一次性):\n"
        "  1. 注册/登录 https://cds.climate.copernicus.eu/\n"
        "  2. 打开 https://cds.climate.copernicus.eu/profile 复制 Personal Access Token\n"
        '  3. 在 ~/.cdsapirc (即 ' + p + ') 写入两行:\n'
        "       url: https://cds.climate.copernicus.eu/api\n"
        "       key: <你的Personal Access Token>\n"
        "  4. 在数据集页面接受一次 CC-BY 许可条款:\n"
        "     https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics\n"
    )


def month_request(year, month):
    days = list(range(1, calendar.monthrange(year, month)[1] + 1))
    return {
        "product_type": ["reanalysis"],
        "variable": [VARIABLE],
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": [f"{d:02d}" for d in days],
        "daily_statistic": ["daily_maximum"],
        "time_zone": ["utc+00:00"],
        "frequency": ["1_hourly"],
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def verify_month(path, year, month):
    """校验月文件: 可打开、单数据变量、日数正确、纬度范围正确。返回 (ok, 原因)。"""
    import xarray as xr
    try:
        ds = xr.open_dataset(path)
    except Exception as e:
        return False, f"无法打开: {type(e).__name__}: {e}"
    try:
        tname = "valid_time" if "valid_time" in ds.dims else ("time" if "time" in ds.dims else None)
        if tname is None:
            return False, "找不到时间维 (valid_time/time)"
        ndays = calendar.monthrange(year, month)[1]
        n = ds.sizes[tname]
        if n != ndays:
            return False, f"时间步数 {n} != {ndays}"
        dvars = [v for v in ds.data_vars if ds[v].dims and ds[v].ndim >= 1]
        if not dvars:
            return False, "无数据变量"
        lname = next((c for c in ("latitude", "lat") if c in ds.coords), None)
        if lname is not None:
            lat = ds[lname].values
            if not (lat.min() <= 30 and lat.max() >= 66 or (30 in lat or 66 in lat)
                    or (lat.min() >= 29 and lat.max() <= 67)):
                # 欧洲框裁剪后纬度应覆盖 30-66 区间; 放宽 ±1° 判定
                return False, f"纬度范围异常: {lat.min()}~{lat.max()}"
        return True, f"{n} 天, 变量 {dvars[0]}"
    finally:
        ds.close()


def download_months(start, end):
    try:
        import cdsapi
    except ImportError:
        sys.exit("[错误] 缺少 cdsapi 库。请先运行: pip install cdsapi")
    os.makedirs(OUT_DIR, exist_ok=True)
    todo = []
    for y in range(start, end + 1):
        for m in range(1, 13):
            out = os.path.join(OUT_DIR, f"tmax_eur_{y}_{m:02d}.nc")
            if os.path.exists(out):
                ok, why = verify_month(out, y, m)
                if ok:
                    continue
                print(f"  已存在但校验失败, 将重新下载: {os.path.basename(out)} ({why})")
                os.remove(out)
            todo.append((y, m, out))

    if not todo:
        print(f"全部 {start}-{end} 月文件已就位, 无需下载。")
        return 0

    print(f"待下载 {len(todo)} 个月 (CDS 队列通常每次 1-5 分钟, 全程约几小时; 可随时中断, 重跑续传)")
    client = cdsapi.Client(quiet=True)
    failed = []
    for i, (y, m, out) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {y}-{m:02d} ...", flush=True)
        tmp = out + ".part"
        ok = False
        req_full = month_request(y, m)
        # 平台对个别可选键不支持时, 自动降级为最小请求 (只含表单必填键)
        req_min = {k: v for k, v in req_full.items()
                   if k not in ("data_format", "download_format")}
        for attempt in range(1, MAX_RETRY + 1):
            try:
                try:
                    client.retrieve(DATASET, req_full, tmp)
                except Exception as e:
                    msg = str(e)
                    if "data_format" in msg or "download_format" in msg:
                        print("    平台不接受 format 键, 用最小请求重试")
                        client.retrieve(DATASET, req_min, tmp)
                    else:
                        raise
                # netcdf 单文件 (unarchived) 直接落盘; 若平台返回 zip 需解包
                if tmp.lower().endswith(".zip") or _is_zip(tmp):
                    import zipfile
                    with zipfile.ZipFile(tmp) as z:
                        z.extractall(os.path.dirname(tmp))
                        ncs = []
                        for root, _dirs, fs in os.walk(os.path.dirname(tmp)):
                            ncs += [os.path.join(root, f) for f in fs
                                    if f.lower().endswith(".nc") and not f.endswith(".part")]
                        if len(ncs) != 1:
                            raise RuntimeError(f"zip 内 .nc 文件数异常: {len(ncs)}")
                        if os.path.exists(out):
                            os.remove(out)
                        os.replace(ncs[0], out)
                    os.remove(tmp)
                else:
                    if os.path.exists(out):
                        os.remove(out)
                    os.replace(tmp, out)
                ok, why = verify_month(out, y, m)
                if ok:
                    print(f"    OK ({why})")
                    break
                print(f"    校验失败: {why}; 重试...")
                os.remove(out)
            except KeyboardInterrupt:
                print("\n用户中断; 已完成的月份已保留, 重跑本脚本可续传。")
                return 1
            except Exception as e:
                wait = 30 * 2 ** (attempt - 1)
                print(f"    第 {attempt}/{MAX_RETRY} 次尝试失败: {type(e).__name__}: {str(e)[:120]}; "
                      f"{wait}s 后重试")
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                time.sleep(wait)
        if not ok:
            failed.append((y, m))
    if failed:
        print(f"\n[未完成] {len(failed)} 个月仍失败: {failed}")
        print("通常是 CDS 队列/许可问题; 稍后重跑本脚本即可只补这些月份。")
        return 1
    print("\n全部月文件下载并校验通过。运行 --merge 生成合并件:")
    print(f"  python {os.path.abspath(__file__)} --merge")
    return 0


def _is_zip(path):
    with open(path, "rb") as f:
        return f.read(2) == b"PK"


def merge(start, end):
    """把月文件合并为 TECHNICAL_SPEC 规定的单文件 (若齐全)。"""
    import numpy as np
    import xarray as xr
    files = []
    for y in range(start, end + 1):
        for m in range(1, 13):
            p = os.path.join(OUT_DIR, f"tmax_eur_{y}_{m:02d}.nc")
            if not os.path.exists(p):
                print(f"[缺失] {p}")
            else:
                files.append(p)
    if not files:
        print("没有任何月文件可合并。")
        return 1
    dss = []
    for p in files:
        ds = xr.open_dataset(p)
        tname = "valid_time" if "valid_time" in ds.dims else "time"
        var = [v for v in ds.data_vars if ds[v].ndim >= 1][0]
        da = ds[var]
        da = da.rename({tname: "time"}).sortby("time")
        dss.append(da.load())
        ds.close()
    merged = xr.concat(dss, dim="time").sortby("time")
    # 统一经度到 -180..180 (与 d2m_global_daily 约定一致)
    lon_name = "longitude" if "longitude" in merged.coords else "lon"
    lon = merged[lon_name].values
    if lon.max() > 180:
        merged = merged.assign_coords({lon_name: (((lon + 180) % 360) - 180)}).sortby(lon_name)
    enc = {v: {"zlib": True, "complevel": 4} for v in merged.data_vars}
    merged.to_netcdf(MERGED_PATH, encoding=enc)
    n = merged.sizes["time"]
    exp = sum(366 if calendar.isleap(y) else 365 for y in range(start, end + 1))
    status = "OK" if n == exp else f"警告: {n} != 预期 {exp} 天 (有缺失月)"
    print(f"合并完成: {MERGED_PATH}  时间步 {n}  {status}")
    return 0


def main():
    ensure_utf8_console()
    ap = argparse.ArgumentParser(description="ERA5 日最高气温下载 (CDS daily-statistics)")
    ap.add_argument("--start", type=int, default=DEFAULT_START)
    ap.add_argument("--end", type=int, default=DEFAULT_END)
    ap.add_argument("--merge", action="store_true", help="仅把已下载的月文件合并为单文件")
    args = ap.parse_args()

    if args.merge:
        return merge(args.start, args.end)
    check_credentials()
    return download_months(args.start, args.end)


if __name__ == "__main__":
    sys.exit(main())
