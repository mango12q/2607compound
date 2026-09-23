# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════
#  快速开始（Phase 6 CESM1-LE 归因数据）
#    python python\download_cesm1le.py probe                 # 先探测可用通道（不下载）
#    python python\download_cesm1le.py aws   --members 20    # ALL 日值 TREFHT（AWS 匿名 zarr）
#    python python\download_cesm1le.py gdex  --members 20    # SST + XGHG（NCAR GDEX）
#    python python\download_cesm1le.py download --manifest ...# 兜底：按 URL 清单整文件下载
#  一键入口: run_p0_download.bat（3 成员）/ run_phase6_download.bat（20 成员，~750 GB，4-5 天）
#  要点：断点续传；自动走系统代理（直连 <0.1 MB/s，走代理 ~2.2 MB/s）；
#        OPeNDAP 只适合小切片，大文件走 fileServer 整文件 + trim。
#  依赖：xarray / netCDF4 / s3fs（可选）。无需账号。
# ══════════════════════════════════════════════════════════════════════════
"""
download_cesm1le.py — Phase 6 (CESM1-LE 归因) 数据下载工具

论文需求 (原文 L514-525):
    ALL 强迫 20 成员 + ALL-but-GHG (XGHG) 20 成员, 2000-2021,
    日值 TREFHT (陆地 2m 气温) + 日值 SST, 用于复合热浪检测与暴露时间归因。

数据源与分工:
    [自动] ALL 集合日值 TREFHT —— AWS 匿名 zarr 镜像 (免账号)
           `aws` 子命令: 切 2000-2021 (+默认欧洲框) → CESM_PROC_DIR
    [自动] SST 日值 + XGHG —— NCAR GDEX d651027 THREDDS (实爬验证匿名可用!)
           `gdex` 子命令: 运行时解析目录取精确文件段 → OPeNDAP(dodsC)
           服务端只切 2000-2021(大气再裁欧洲框) → 直接产出 proc 文件,
           免下整文件, 免 RDA 账号。`manifest` 导出解析清单备查。
    [兜底] `download` 子命令: 吃 URL 清单/RDA wget 脚本整文件下载(断点续传)
           → `trim` 裁到分析时段。仅当 OPeNDAP 对某文件失效时使用。

子命令:
    probe     检查 AWS zarr 元数据 (成员/时段/网格), 不批量拉数据
    aws       ALL 日值 TREFHT: AWS zarr 切片 → CESM_PROC_DIR
    manifest  实爬 GDEX 目录, 导出精确文件段清单（不下载）
    gdex      SST/XGHG: OPeNDAP 服务端切片 → CESM_PROC_DIR (推荐)
    download  按 --urls 清单整文件下载 → CESM_RAW_DIR (断点续传)
    trim      raw/ 全时段文件 → 裁 2000-2021 → proc/

用法示例:
    python download_cesm1le.py probe
    python download_cesm1le.py aws --members 3          # P0: 前 3 个成员
    python download_cesm1le.py gdex --list --members 3  # 先看解析结果
    python download_cesm1le.py gdex --members 3         # P0: SST + XGHG
    python download_cesm1le.py aws --members 20         # 全量
    python download_cesm1le.py gdex --members 20
    python download_cesm1le.py download --urls 清单.txt  # 兜底整文件
    python download_cesm1le.py trim
"""
import argparse
import os
import re
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from urllib.parse import unquote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402

AWS_TREFHT = {
    "20C": f"{C.AWS_LENS_BUCKET}/atm/daily/cesmLE-20C-TREFHT.zarr",
    "RCP85": f"{C.AWS_LENS_BUCKET}/atm/daily/cesmLE-RCP85-TREFHT.zarr",
}
# us-west-2 + 放宽读超时 + botocore 自动重试（此前默认 60s 读超时在慢分块上会断）
AWS_STORAGE_OPTS = {
    "anon": True,
    "client_kwargs": {"region_name": "us-west-2"},
    "config_kwargs": {"connect_timeout": 60, "read_timeout": 600, "retries": {"max_attempts": 5}},
}
GDEX_DIR_HINT = "rda.ucar.edu → 数据集 d651027 → Web Files 标签 → cesmLE/…（目录层次以门户为准）"

# THREDDS 实爬确认的目录与命名（2025-09-18, results/crawl_tds.py 证据）
TDS_BASE = "https://tds.gdex.ucar.edu/thredds/catalog/files/d651027"
DODS_BASE = "https://tds.gdex.ucar.edu/thredds/dodsC/"
FILE_BASE = "https://tds.gdex.ucar.edu/thredds/fileServer/"
GDEX_CATALOGS = {
    ("atm", "TREFHT"): "cesmLE/CESM-CAM5-BGC-LE/atm/proc/tseries/daily/TREFHT/catalog.xml",
    ("ocn", "SST"): "cesmLE/CESM-CAM5-BGC-LE/ocn/proc/tseries/daily/SST/catalog.xml",
}
CASE_PREFIXES = {
    "ALL": ("b.e11.B20TRC5CNBDRD.f09_g16.{m}.", "b.e11.BRCP85C5CNBDRD.f09_g16.{m}."),
    "XGHG": ("b.e11.B20TRLENS_RCP85.f09_g16.xghg.{m}.",),
}
# 实测细节: 成员001的20C段从1850起; XGHG 分两段(1920-2005/2006-2080);
#           RCP85 atm 分两段(2006-2080/2081-2100); SST 段首日可能是 19200102。
# 以上都由目录实爬解析, 不再手拼。


# ──────────────────────────────────────────────
# 公共小工具
# ──────────────────────────────────────────────
def _ensure_dirs():
    os.makedirs(C.CESM_RAW_DIR, exist_ok=True)
    os.makedirs(C.CESM_PROC_DIR, exist_ok=True)


def _setup_proxy():
    """探测系统代理(Windows 注册表)或环境变量并写入环境变量。

    背景: s3fs/aiobotocore 不读 Windows 系统代理, netCDF4-DAP(libcurl) 只认
    环境变量。实测本机 127.0.0.1:6789 代理 2.24 MB/s vs 直连 <0.02 MB/s,
    差 100 倍以上, 因此所有通道必须显式走代理。返回代理 URL(无则 None)。
    """
    px = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    if not px:
        try:
            g = urllib.request.getproxies()  # Windows 下自动读注册表
            px = g.get("https") or g.get("http")
        except Exception:
            px = None
    if px:
        for k in ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY"):
            os.environ[k] = px
    return px


def _pick(d, names, what):
    for n in names:
        if n in d.coords or n in d.dims or n in d.variables:
            return n
    raise KeyError(f"找不到 {what} 坐标，现有坐标: {list(d.coords)} / 维度: {list(d.dims)}")


def _norm_member(v):
    s = str(v)
    return s.zfill(3) if s.isdigit() else s


def _to_datetimeindex(ds):
    """zarr 时间轴若解码为 cftime，则转回 datetime64（否则字符串切片会失败）。"""
    idx = ds.indexes["time"]
    if idx.dtype == object and not np.issubdtype(idx.dtype, np.datetime64):
        try:
            ds = ds.assign_coords(time=idx.to_datetimeindex())
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"时间轴转换失败: {e}") from e
    return ds


def _slice_time_period(ds):
    y0, y1 = C.CESM_PERIOD
    ds = _to_datetimeindex(ds)
    sub = ds.sel(time=slice(y0, y1))
    if sub.sizes.get("time", 0) == 0:
        raise RuntimeError(
            f"时段切片为空！zarr 时间轴范围 {str(ds.time.values[0])} ~ {str(ds.time.values[-1])}"
        )
    return sub


def _crop_europe(ds):
    """f09 网格经度 0-360 → -180-180 后取欧洲框（仅大气/陆地规则网格用）。"""
    latn = _pick(ds, ("lat", "latitude"), "纬度")
    lonn = _pick(ds, ("lon", "longitude"), "经度")
    if float(ds[lonn].max()) > 180:  # 0-360 换算
        ds = ds.assign_coords(**{lonn: (((ds[lonn] + 180) % 360) - 180)})
        ds = ds.sortby(lonn).sortby(latn)
    lat0, lat1 = C.CESM_EUROPE_LAT
    lon0, lon1 = C.CESM_EUROPE_LON
    out = ds.sel(**{latn: slice(lat0, lat1), lonn: slice(lon0, lon1)})
    if out.sizes.get(latn, 0) == 0 or out.sizes.get(lonn, 0) == 0:
        raise RuntimeError("欧洲框裁剪为空，请检查坐标范围")
    return out


# ──────────────────────────────────────────────
# probe
# ──────────────────────────────────────────────
def cmd_probe(args):
    print("== [1/2] AWS zarr 元数据（匿名）==")
    for tag, url in AWS_TREFHT.items():
        try:
            ds = xr.open_zarr(url, storage_options={"anon": True}, consolidated=True)
        except Exception:
            ds = xr.open_zarr(url, storage_options={"anon": True}, consolidated=False)
        mdim = _pick(ds, ("member", "members", "member_id", "ensemble"), "成员")
        mems = [_norm_member(v) for v in ds[mdim].values]
        tv = ds.time.values
        print(
            f"[{tag}] 维度 {dict(ds.sizes)} | 成员维 '{mdim}' 共 {len(mems)} 个: "
            f"{mems[:5]}...{mems[-3:]} | 时间 {str(tv[0])[:10]} ~ {str(tv[-1])[:10]}"
        )
        del ds
    print("== [2/2] GDEX 匿名可达性 ==")
    try:
        req = Request(C.GDEX_D651027_BASE + "/", method="HEAD")
        with urlopen(req, timeout=30) as r:
            print(f"HEAD {C.GDEX_D651027_BASE}/ -> {r.status}（可匿名访问文件，但目录不可枚举）")
    except Exception as e:
        print(f"HEAD 失败: {e}（若持续失败，改用 RDA 门户 wget 脚本）")
    print("\n下一步: python download_cesm1le.py aws --members 3")


# ──────────────────────────────────────────────
# aws — ALL 日值 TREFHT
# ──────────────────────────────────────────────
def _open_zarr(url):
    opts = dict(AWS_STORAGE_OPTS)
    px = _setup_proxy()
    if px:
        # botocore Config(proxies=...) → aiobotocore/aiohttp 走代理
        opts["config_kwargs"] = {**opts.get("config_kwargs", {}), "proxies": {"http": px, "https": px}}
    try:
        return xr.open_zarr(url, storage_options=opts, consolidated=True)
    except Exception:
        return xr.open_zarr(url, storage_options=opts, consolidated=False)


def _load_with_retry(ds, retries=4):
    """把 dask/zarr 惰性数据整体读入内存；网络抖动时指数退避重试。"""
    delay = 10
    for k in range(1, retries + 1):
        try:
            return ds.load()
        except Exception as e:
            print(f"    读取重试 {k}/{retries}: {type(e).__name__} {str(e)[:140]}")
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("多次读取超时，网络不稳定。脚本支持断点续跑：重跑即可，已完成成员会自动跳过。")


def _select_members(ds, mdim, n_members):
    avail = [_norm_member(v) for v in ds[mdim].values]
    want = [m for m in C.CESM_ALL_MEMBERS if m in avail][:n_members]
    missing = set(C.CESM_ALL_MEMBERS[:n_members]) - set(want)
    if missing:
        print(f"⚠ 以下成员在 zarr 中不存在: {sorted(missing)}（跳过）")
    orig = [o for o, a in zip(ds[mdim].values, avail) if a in want]
    return orig, want


def cmd_aws(args):
    _ensure_dirs()
    print(f"代理: {_setup_proxy() or '未检测到(将直连, 可能极慢)'}")
    n = args.members
    parts = {}
    for tag, url in AWS_TREFHT.items():
        print(f"打开 {url} …")
        ds = _open_zarr(url)
        mdim = _pick(ds, ("member", "members", "member_id", "ensemble"), "成员")
        orig, want = _select_members(ds, mdim, n)
        sub = ds.sel({mdim: orig})
        sub = _slice_time_period(sub)
        if not args.global_region:
            sub = _crop_europe(sub)
        parts[tag] = (sub, orig, want)
        print(f"  [{tag}] 成员 {want} | 时段 {str(sub.time.values[0])[:10]}~{str(sub.time.values[-1])[:10]} | {dict(sub.sizes)}")
    sub20, orig20, want20 = parts["20C"]
    sub85, orig85, want85 = parts["RCP85"]
    common = [m for m in want20 if m in want85]
    if not common:
        raise RuntimeError("两段实验没有任何共同成员")
    latn = _pick(sub20, ("lat", "latitude"), "纬度")
    lonn = _pick(sub20, ("lon", "longitude"), "经度")
    region = "global" if args.global_region else "europe"
    for i, m in enumerate(common):
        out = os.path.join(C.CESM_PROC_DIR, f"TREFHT_all_{m}_2000-2021_{region}.nc")
        if os.path.exists(out):
            print(f"  ✓ 成员 {m} ({i + 1}/{len(common)}) 已存在，跳过")
            continue
        a = sub20.isel({mdim: orig20.index(next(o for o, w in zip(orig20, want20) if w == m))})
        b = sub85.isel({mdim: orig85.index(next(o for o, w in zip(orig85, want85) if w == m))})
        a = a.squeeze(drop=True) if mdim in a.dims else a
        b = b.squeeze(drop=True) if mdim in b.dims else b
        merged = xr.concat([a, b], dim="time").sortby("time")
        merged = _load_with_retry(merged)  # 先整体落地，写盘阶段不再碰网络
        enc = {"TREFHT": {"zlib": True, "complevel": 4}}
        tmp = out + ".part.nc"
        merged.to_netcdf(tmp, encoding=enc)
        os.replace(tmp, out)  # 中断不会留下截断文件
        gb = os.path.getsize(out) / 1e9
        print(f"  ✓ 成员 {m} ({i + 1}/{len(common)}) -> {out} ({gb:.2f} GB)")
    print(f"完成: {len(common)} 个成员的 ALL 日值 TREFHT 已就位。")


# ──────────────────────────────────────────────
# GDEX 目录解析（精确文件段，运行时实爬）
# ──────────────────────────────────────────────
def _fetch_url(url, timeout=120):
    for k in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print(f"  retry {k+1}: {type(e).__name__} {str(e)[:90]}")
            time.sleep(4)
    raise RuntimeError(f"fetch 失败: {url}")


def _resolve_gdex(members, exps=("ALL", "XGHG")):
    """实爬 THREDDS 目录, 返回与我们成员/时段相交的文件段清单。"""
    rows = []
    for (comp, var), cat in GDEX_CATALOGS.items():
        root = ET.fromstring(_fetch_url(f"{TDS_BASE}/{cat}"))
        for el in root.iter():
            if el.tag.split("}")[-1] != "dataset":
                continue
            name = el.get("name") or ""
            if not name.endswith(".nc"):
                continue
            for exp in exps:
                for m in members:
                    for pre in CASE_PREFIXES[exp]:
                        if name.startswith(pre.format(m=m)):
                            seg = re.search(r"(\d{8})-(\d{8})\.nc$", name)
                            s, e = seg.group(1), seg.group(2)
                            if e >= "20000101" and s <= "20211231":  # 与分析时段相交
                                rows.append(dict(
                                    experiment=exp, member=m, component=comp, variable=var,
                                    filename=name, urlpath=el.get("urlPath") or "",
                                    seg_start=s, seg_end=e,
                                    file_url=FILE_BASE + (el.get("urlPath") or ""),
                                    dods_url=DODS_BASE + (el.get("urlPath") or ""),
                                ))
    return rows


def cmd_manifest(args):
    members = C.CESM_ALL_MEMBERS[: args.members]
    rows = _resolve_gdex(members, ("ALL", "XGHG"))
    if not rows:
        raise SystemExit("目录解析为空")
    df = pd.DataFrame(rows).sort_values(["experiment", "member", "component", "seg_start"])
    _ensure_dirs()
    os.makedirs(C.TABLES_DIR, exist_ok=True)
    out = os.path.join(C.TABLES_DIR, "cesm1le_download_manifest.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"清单已写入: {out}（{len(df)} 个文件段, {df.filename.nunique()} 个唯一文件）")
    print(df.groupby(["experiment", "component"]).size().to_string())
    return out


def _mask_sst_box(ds):
    """POP 曲线网格: 按 TLAT/TLON 掩膜到欧洲框(略放宽)后裁掉全空行列。"""
    tlat, tlon = ds["TLAT"], ds["TLON"]
    lon2 = (tlon + 180) % 360 - 180
    mask = (tlat >= 26) & (tlat <= 76) & (lon2 >= -25) & (lon2 <= 55)
    ds = ds.where(mask)
    mv = np.asarray(mask.values)
    js = np.where(mv.any(axis=1))[0]
    iis = np.where(mv.any(axis=0))[0]
    if len(js) == 0 or len(iis) == 0:
        raise RuntimeError("SST 欧洲框掩膜为空")
    vdim = ds["SST"].dims[-2]
    hdim = ds["SST"].dims[-1]
    return ds.isel({vdim: slice(int(js[0]), int(js[-1]) + 1),
                    hdim: slice(int(iis[0]), int(iis[-1]) + 1)})


def cmd_gdex(args):
    """OPeNDAP 服务端切片: 只传输 2000-2021(大气再裁欧洲框), 直接产出 proc 文件。"""
    _ensure_dirs()
    print(f"代理: {_setup_proxy() or '未检测到(将直连, 可能极慢)'}")
    members = C.CESM_ALL_MEMBERS[: args.members]
    rows = _resolve_gdex(members, ("ALL", "XGHG"))
    if not rows:
        raise SystemExit("目录解析为空")
    groups = defaultdict(list)
    for r in rows:
        groups[(r["experiment"], r["member"], r["component"])].append(r)
    print(f"解析到 {len(groups)} 个 (实验,成员,变量) 组 / {len(rows)} 个文件段")

    if args.list:
        out = os.path.join(C.TABLES_DIR, "cesm1le_download_manifest.csv")
        pd.DataFrame(rows).sort_values(["experiment", "member", "component", "seg_start"]).to_csv(
            out, index=False, encoding="utf-8-sig")
        print(f"清单 -> {out}（未下载任何数据）")
        return

    y0, y1 = C.CESM_PERIOD
    todo = [(k, v) for k, v in sorted(groups.items())]
    done = 0
    for gi, ((exp, mem, comp), segs) in enumerate(todo, 1):
        var = segs[0]["variable"]
        out = os.path.join(C.CESM_PROC_DIR, f"{var.lower()}_{exp.lower()}_{mem}_{y0[:4]}-{y1[:4]}.nc")
        if os.path.exists(out):
            print(f"  [{gi}/{len(todo)}] 已存在，跳过 {os.path.basename(out)}")
            done += 1
            continue
        try:
            parts = []
            for r in sorted(segs, key=lambda x: x["seg_start"]):
                ds = xr.open_dataset(r["dods_url"])  # netCDF4 DAP
                ds = ds[[var]]                        # 只取目标变量, 大幅减少传输
                ds = _slice_time_period(ds)
                if comp == "atm":
                    ds = _crop_europe(ds)
                parts.append(_load_with_retry(ds))
            merged = xr.concat(parts, dim="time").sortby("time") if len(parts) > 1 else parts[0]
            if comp == "ocn":
                merged = _mask_sst_box(merged)
            tmp = out + ".part.nc"
            enc = {v: {"zlib": True, "complevel": 4} for v in merged.data_vars}
            merged.to_netcdf(tmp, encoding=enc)
            os.replace(tmp, out)
            done += 1
            print(f"  [{gi}/{len(todo)}] ✓ {os.path.basename(out)} ({os.path.getsize(out)/1e9:.2f} GB)")
            del merged, parts
        except Exception as e:
            print(f"  [{gi}/{len(todo)}] ✗ {exp}/{mem}/{comp}: {type(e).__name__} {str(e)[:140]}")
            print("      （可重跑续传；若 OPeNDAP 持续失败, 改用 download --urls 走 fileServer 整文件）")
    print(f"完成 {done}/{len(todo)} 组 → {C.CESM_PROC_DIR}")


# ──────────────────────────────────────────────
# download — 吃 URL 清单 / RDA wget 脚本
# ──────────────────────────────────────────────
def _extract_urls(path):
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path)
        if "file_url" in df.columns:
            return [u for u in df["file_url"].dropna().astype(str) if u.startswith("http")]
        raise SystemExit(f"{path} 缺少 file_url 列")
    text = open(path, "r", encoding="utf-8", errors="replace").read()
    urls = re.findall(r"https?://[^\s'\",<>]+", text)
    seen, out = set(), []
    for u in urls:
        u = u.rstrip("\\")
        if u not in seen and re.search(r"\.nc(\?|$)", u) and "/dodsC/" not in u:
            # 只保留 fileServer 直链; dodsC 整文件走 OPeNDAP 反而更慢(服务端逐记录抽取)
            seen.add(u)
            out.append(u)
    return out


def _head_size(url):
    req = Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length", 0))


def _download_one(url, dest, retries=5):
    part = dest + ".part"
    fresh = dest + ".fresh.part"
    if os.path.exists(dest):
        # 自愈: 已存在的成品也要校验长度(此前出现过代理断流导致的截断文件)
        try:
            cl = _head_size(url)
            if cl and abs(os.path.getsize(dest) - cl) > 1024:
                print(f"    已有文件不完整 ({os.path.getsize(dest)/1e9:.2f}/{cl/1e9:.2f} GB), 删除重下")
                os.remove(dest)
            else:
                return dest, 0
        except Exception:
            return dest, 0  # HEAD 失败时保留原文件, 视为已完成
    for attempt in range(1, retries + 1):
        try:
            have = os.path.getsize(part) if os.path.exists(part) else 0
            headers = {"User-Agent": "Mozilla/5.0"}
            if have:
                headers["Range"] = f"bytes={have}-"
            req = Request(url, headers=headers)
            with urlopen(req, timeout=120) as r:
                status = getattr(r, "status", 200)
                resuming = bool(have) and status == 206
                if have and not resuming:
                    print("    服务器不支持断点续传, 改写临时副本(保留断点)")
                    have = 0
                cl = r.headers.get("Content-Length")
                expected = (have + int(cl)) if cl else None
                got = 0
                last_gb = -1
                # 206 续传写 .part; 非 206 全新下载写 .fresh.part, 失败不损 .part
                target = part if resuming else fresh
                with open(target, "ab" if resuming else "wb") as f:
                    while True:
                        chunk = r.read(8 << 20)
                        if not chunk:
                            break
                        got += len(chunk)
                        f.write(chunk)
                        if got >> 30 > last_gb:  # 每过 1 GB 报一次进度
                            last_gb = got >> 30
                            exp = f"/{expected/1e9:.1f} GB" if expected else ""
                            print(f"    {got/1e9:.1f}{exp}", flush=True)
                if expected is not None and got != expected:
                    raise RuntimeError(f"传输不完整: 收到 {got/1e9:.2f} / 应为 {expected/1e9:.2f} GB")
                if expected is None:
                    # chunked/无 CL 响应 → 事后 HEAD 校验, 否则断流会被漏判
                    cl2 = _head_size(url)
                    if cl2 and got != cl2:
                        raise RuntimeError(f"传输不完整(chunked): 收到 {got/1e9:.2f} / HEAD {cl2/1e9:.2f} GB")
            os.replace(target, dest)
            for p in (part, fresh):
                if os.path.exists(p):
                    os.remove(p)
            return dest, attempt
        except Exception as e:
            print(f"    重试 {attempt}/{retries}: {type(e).__name__} {str(e)[:120]}")
            time.sleep(5 * attempt)
    # 兜底: curl.exe 独立 HTTP 栈, -C - 自动从 .part 续传
    try:
        proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
        cmd = ["curl.exe", "-sfL", "--retry", "3", "-C", "-"]
        if proxy:
            cmd += ["-x", proxy]
        cmd += ["-o", part, url]
        print(f"    curl 兜底: {' '.join(cmd[:6])} ...")
        subprocess.run(cmd, check=True, timeout=14400)
        cl = _head_size(url)
        if cl and abs(os.path.getsize(part) - cl) <= 1024:
            os.replace(part, dest)
            if os.path.exists(fresh):
                os.remove(fresh)
            return dest, retries + 1
        raise RuntimeError(f"curl 后大小不符: {os.path.getsize(part)/1e9:.2f}/{cl/1e9:.2f} GB")
    except Exception as e:
        print(f"    curl 兜底失败: {type(e).__name__} {str(e)[:100]}")
    raise RuntimeError(f"下载失败: {url}")


def cmd_download(args):
    _ensure_dirs()
    print(f"代理: {_setup_proxy() or '未检测到(将直连, 可能极慢)'}")
    urls = _extract_urls(args.urls)
    if not urls:
        raise SystemExit("提供的文件里没有找到 .nc 的 http(s) URL")
    print(f"共 {len(urls)} 个文件待下载 → {C.CESM_RAW_DIR}")
    for i, u in enumerate(urls, 1):
        fname = unquote(u.split("?")[0].rstrip("/").split("/")[-1])
        dest = os.path.join(C.CESM_RAW_DIR, fname)
        try:
            dest, _ = _download_one(u, dest)
            gb = os.path.getsize(dest) / 1e9
            print(f"  [{i}/{len(urls)}] ✓ {fname} ({gb:.2f} GB)")
        except RuntimeError as e:
            print(f"  [{i}/{len(urls)}] ✗ {e}")
    print("全部处理完毕。下一步: python download_cesm1le.py trim")


# ──────────────────────────────────────────────
# trim — 裁 2000-2021
# ──────────────────────────────────────────────
def cmd_trim(args):
    _ensure_dirs()
    y0, y1 = C.CESM_PERIOD
    raws = sorted(f for f in os.listdir(C.CESM_RAW_DIR) if f.endswith(".nc"))
    if not raws:
        raise SystemExit(f"{C.CESM_RAW_DIR} 里没有 .nc 文件")
    for i, f in enumerate(raws, 1):
        src = os.path.join(C.CESM_RAW_DIR, f)
        out = os.path.join(C.CESM_PROC_DIR, f.replace(".nc", f"_{y0[:4]}-{y1[:4]}.nc"))
        if os.path.exists(out):
            print(f"  [{i}/{len(raws)}] 已存在，跳过 {os.path.basename(out)}")
            continue
        print(f"  [{i}/{len(raws)}] {f} …")
        ds = xr.open_dataset(src, chunks={"time": 365})
        ds = _slice_time_period(ds)
        if args.region == "europe" and "TLAT" not in ds.coords:
            ds = _crop_europe(ds)  # 规则网格(大气)才裁框; POP 曲线网格保持全球
        enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
        ds.to_netcdf(out, encoding=enc)
        gb = os.path.getsize(out) / 1e9
        del ds
        print(f"        -> {os.path.basename(out)} ({gb:.2f} GB)")
    if not args.keep_raw:
        print("（保留 raw/ 原始文件；加 --keep-raw 也一样，默认从不删除）")
    print("完成。proc/ 可直接进入检测流程。")


# ──────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="检查 AWS zarr 元数据与 GDEX 可达性")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("aws", help="ALL 日值 TREFHT: AWS zarr 切片下载")
    p.add_argument("--members", type=int, default=C.CESM_P0_MEMBERS, help=f"成员数 (默认 P0={C.CESM_P0_MEMBERS}, 全量 20)")
    p.add_argument("--global-region", action="store_true", help="不裁欧洲框，存全球（体积大）")
    p.set_defaults(func=cmd_aws)

    p = sub.add_parser("manifest", help="实爬 GDEX 目录, 导出精确文件段清单（不下载）")
    p.add_argument("--members", type=int, default=C.CESM_P0_MEMBERS, help="成员数 (默认 P0=3, 全量 20)")
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("gdex", help="SST/XGHG: THREDDS OPeNDAP 服务端切片（推荐, 免账号）")
    p.add_argument("--members", type=int, default=C.CESM_P0_MEMBERS, help="成员数 (默认 P0=3, 全量 20)")
    p.add_argument("--list", action="store_true", help="仅解析目录并导出清单, 不下载")
    p.set_defaults(func=cmd_gdex)

    p = sub.add_parser("download", help="按 URL 清单/RDA wget 脚本下载 (断点续传)")
    p.add_argument("--urls", required=True, help="URL 清单或 RDA wget 脚本路径")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("trim", help="raw/ 全时段文件裁到 2000-2021 → proc/")
    p.add_argument("--region", default="none", choices=["none", "europe"], help="大气规则网格可裁欧洲框")
    p.add_argument("--keep-raw", action="store_true", help="保留原始文件（默认也保留，仅提示）")
    p.set_defaults(func=cmd_trim)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
