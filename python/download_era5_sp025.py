# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════
#  快速开始（Phase 5 湿热应力输入：ERA5 地表气压 sp，0.25° 欧洲框）
#    python python\download_era5_sp025.py --dry-run  # 先看要下多少个月（不下载）
#    python python\download_era5_sp025.py            # 正式下载（默认：一次申请一年 + 2 并发）
#    python python\download_era5_sp025.py --chunk-months 1  # 改成"一次一个月"（排队次数 ×12）
#    python python\download_era5_sp025.py --jobs 3   # 改并发数（默认 2；≥4 实测会被限流拒单）
#  一键入口: run_phase5_downloads.bat
#  ★ 2026-09-25：默认走 download_era5_fast.py 的分块并发引擎，粒度由 --chunk-months 控制
#    （**默认 12 = 一次申请一年**）；输出文件名/校验口径/下游完全不变。
#  为什么需要：现有 data/ERA5/sp/ 是 1.0° 全球件，而论文要求的 WBT/SH 全变量为
#              0.25°；把 1.0° 插到 0.25° 不产生新信息，属方法学降级。
#  前置：同 download_era5_tmax.py（CDS 凭据 + 接受数据集条款）。
# ══════════════════════════════════════════════════════════════════════════
"""
download_era5_sp025.py — Phase 5 (湿热应力) 输入数据: ERA5 地表气压 sp, 0.25° 欧洲框

为什么需要这个脚本（对应 DATA_REQUIREMENTS.md 数据集 3b+）：
    论文 Methods 声明 WBT / SH 所需的 ERA5 变量均为 **0.25°**。
    现有 data/ERA5/sp/ 是 **1.0° 全球**件（pres.sfc.daily.era5.YYYY.nc × 46），
    把 1.0° 插到 0.25° 不产生新信息，属方法学降级。
    本脚本补下 **0.25° 欧洲框**的 sp，使 WBT / SH 全变量统一 0.25°。

数据源（官方）:
    Copernicus CDS 数据集 `derived-era5-single-levels-daily-statistics`
      (DOI: 10.24381/cds.4991cf48)
    - product_type      : reanalysis
    - variable          : surface_pressure
    - daily_statistic   : daily_mean      (气压用日均值; WBT 公式的 p 为当日平均场)
    - time_zone         : utc+00:00
    - frequency         : 1_hourly
    - area              : [70, -16, 28, 44]   (N, W, S, E)
                          ★ 2026-09-24 第五轮扩大：论文 Fig.5c 的地图范围实测为
                          lon −15…43.5、lat 29…69，旧框 [66, −10, 30, 40] 会在
                          西/北/东三侧被裁掉（图与论文不符）。此框同时覆盖
                          Fig.6 的地中海缓冲分析域，故 sp 只需下一份。
    - data_format       : netcdf  (变量短名 sp)

输出:
    data/ERA5/sp_eur_daily/sp_eur_YYYY_MM.nc     按月分文件 (断点续传单位)
    data/ERA5/ERA5_sp_1984_2023_daily.nc         --merge 合并件

    ⚠️ 不覆盖、不删除现有的 1.0° 全球件 data/ERA5/sp/（保留作备查与对照）。

首次使用前（一次性）: 与 download_era5_tmax.py 相同
    1. pip install cdsapi xarray netcdf4
    2. 配置 ~/.cdsapirc（url + key）
    3. 在数据集页接受一次 CC-BY 许可

用法:
    python python/download_era5_sp025.py --dry-run     # 只列出待下载月份, 不联网
    python python/download_era5_sp025.py               # 下载 1984-2023 (缺哪月补哪月)
    python python/download_era5_sp025.py --merge       # 仅合并已有月文件
"""
import argparse
import calendar
import os
import sys
import time

BASE_DIR = r"D:\2607compound"
ERA5_DIR = os.path.join(BASE_DIR, "data", "ERA5")
OUT_DIR = os.path.join(ERA5_DIR, "sp_eur_daily")
MERGED_PATH = os.path.join(ERA5_DIR, "ERA5_sp_1984_2023_daily.nc")

DATASET = "derived-era5-single-levels-daily-statistics"
VARIABLE = "surface_pressure"
DAILY_STATISTIC = "daily_mean"
AREA = [70, -16, 28, 44]          # CDS area 顺序: [N, W, S, E]
# ★ 第五轮（2026-09-24）由 [66,-10,30,40] 扩大而来：论文 Fig.5c 的地图范围是
#   lon −15…43.5 / lat 29…69，旧框会在西、北、东三侧裁掉（复现图与论文不一致）。
#   本框也是 Fig.5c/Fig.6 的并集，故 sp 0.25° 只需下载这一份。
DEFAULT_START, DEFAULT_END = 1984, 2023
MAX_RETRY = 5

# sp 合理性区间 (Pa)
# ★ 第五轮：下载框扩到 lat 28–70 / lon −16…44 后，框内含阿尔卑斯、挪威等高海拔格点，
#   地面气压可低至 ~6.5e4 Pa（不再只是"海平面附近 9.5e4~1.04e5"）。
#   这里放宽为 6.0e4 ~ 1.06e5 Pa；真正的范围检查在 phase5_humid 侧按域统计。
SP_MIN, SP_MAX = 6.0e4, 1.06e5


def ensure_utf8_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def check_credentials():
    """校验 CDS 凭据 (环境变量 CDSAPI_URL/CDSAPI_KEY 或 ~/.cdsapirc)。"""
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
        "daily_statistic": [DAILY_STATISTIC],
        "time_zone": ["utc+00:00"],
        "frequency": ["1_hourly"],
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


def verify_month(path, year, month):
    """校验月文件: 可打开、日数正确、纬度覆盖欧洲框、数值为合理的气压 (Pa)。"""
    import numpy as np
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
            # ★ 2026-09-24 修复：此处的期望纬度范围必须与 AREA 一起改。
            #   上次把 AREA 由 [66,-10,30,40] 扩到 [70,-16,28,44] 时漏改本行
            #   （仍写着 29~67），会使**每一个下载成功的月文件都被判为坏文件**、
            #   进而被删除并无限重下。现在按 AREA 推导期望范围并留 1° 容差。
            lat_lo, lat_hi = float(AREA[2]), float(AREA[0])
            if not (lat.min() >= lat_lo - 1.0 and lat.max() <= lat_hi + 1.0):
                return False, (f"纬度范围异常: {lat.min()}~{lat.max()}"
                               f"（期望 {lat_lo}~{lat_hi}±1）")

        # 量纲/变量正确性: 必须是地面气压量级 (Pa)
        v = ds[dvars[0]]
        sample = v.isel({tname: 0}).values
        sample = sample[np.isfinite(sample)]
        if sample.size == 0:
            return False, "首时次全为 NaN"
        vmin, vmax = float(sample.min()), float(sample.max())
        if vmin < SP_MIN or vmax > SP_MAX:
            return False, f"数值不在气压量级(Pa): {vmin:.0f}~{vmax:.0f}"
        return True, f"{n} 天, 变量 {dvars[0]}, {vmin:.0f}~{vmax:.0f} Pa"
    finally:
        ds.close()


def plan(start, end):
    """返回 (todo, present) —— 待下载月份与已就位月份（含校验）。"""
    todo, present, bad = [], [], []
    for y in range(start, end + 1):
        for m in range(1, 13):
            out = os.path.join(OUT_DIR, f"sp_eur_{y}_{m:02d}.nc")
            if os.path.exists(out):
                ok, why = verify_month(out, y, m)
                if ok:
                    present.append((y, m))
                    continue
                bad.append((y, m, why))
            todo.append((y, m, out))
    return todo, present, bad


def dry_run(start, end):
    todo, present, bad = plan(start, end)
    print(f"目标: {VARIABLE} / {DAILY_STATISTIC}, {start}-{end}, "
          f"area={AREA}, 0.25°")
    print(f"输出目录: {OUT_DIR}")
    print(f"合并件  : {MERGED_PATH}")
    print()
    print(f"已就位且校验通过: {len(present)} 个月")
    if bad:
        print(f"已存在但校验失败(将重下): {len(bad)} 个月")
        for y, m, why in bad[:10]:
            print(f"   {y}-{m:02d}: {why}")
    print(f"待下载: {len(todo)} 个月")
    if todo:
        by_year = {}
        for y, m, _ in todo:
            by_year.setdefault(y, []).append(m)
        for y in sorted(by_year):
            print(f"   {y}: {len(by_year[y])} 个月 -> {by_year[y][0]:02d}..{by_year[y][-1]:02d}")
    print()
    print("[dry-run] 未联网、未写盘。去掉 --dry-run 才会真正下载。")
    return 0


def download_months(start, end):
    try:
        import cdsapi
    except ImportError:
        sys.exit("[错误] 缺少 cdsapi 库。请先运行: pip install cdsapi")
    os.makedirs(OUT_DIR, exist_ok=True)
    todo, _present, bad = plan(start, end)
    for y, m, why in bad:
        p = os.path.join(OUT_DIR, f"sp_eur_{y}_{m:02d}.nc")
        print(f"  已存在但校验失败, 将重新下载: {os.path.basename(p)} ({why})")
        os.remove(p)

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
    import xarray as xr
    files = []
    for y in range(start, end + 1):
        for m in range(1, 13):
            p = os.path.join(OUT_DIR, f"sp_eur_{y}_{m:02d}.nc")
            if os.path.exists(p):
                files.append(p)
            else:
                print(f"[缺失] {p}")
    if not files:
        print("没有任何月文件可合并。")
        return 1
    dss = []
    for p in files:
        ds = xr.open_dataset(p)
        tname = "valid_time" if "valid_time" in ds.dims else "time"
        var = [v for v in ds.data_vars if ds[v].ndim >= 1][0]
        da = ds[var].rename({tname: "time"}).sortby("time")
        dss.append(da.load())
        ds.close()
    merged = xr.concat(dss, dim="time").sortby("time")
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
    ap = argparse.ArgumentParser(
        description="ERA5 地表气压 sp 0.25° 欧洲框下载 (CDS daily-statistics; 数据集 3b+)")
    ap.add_argument("--start", type=int, default=DEFAULT_START)
    ap.add_argument("--end", type=int, default=DEFAULT_END)
    ap.add_argument("--merge", action="store_true", help="仅把已下载的月文件合并为单文件")
    ap.add_argument("--dry-run", action="store_true", help="只列计划, 不联网不写盘")
    ap.add_argument("--chunk-months", type=int, default=12, dest="chunk_months",
                    help="每个 CDS 请求含几个月：**默认 12 = 一次申请一年**（排队次数最少）；"
                         "1 = 一次一个月；6 = 半年。平台 size 上限 400 天，最多 12 个月")
    ap.add_argument("--jobs", "-j", type=int, default=2,
                    help="并发请求数（默认 2；CDS 对同数据集排队请求数有临时限制，"
                         "实测 ≥4 会开始拒单；1=串行）")
    args = ap.parse_args()

    if args.merge:
        return merge(args.start, args.end)
    if args.dry_run:
        return dry_run(args.start, args.end)
    if args.chunk_months > 1 or args.jobs > 1:
        # 分块 + 并发：交由 download_era5_fast.py（同一套 verify_month / merge）
        import download_era5_fast as F
        return F.run_one("sp", args.start, args.end,
                         months_per_request=args.chunk_months, jobs=args.jobs)
    # 以下为旧的逐月串行路径（--chunk-months 1 --jobs 1）
    check_credentials()
    return download_months(args.start, args.end)


if __name__ == "__main__":
    sys.exit(main())
