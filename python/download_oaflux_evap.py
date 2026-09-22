# -*- coding: utf-8 -*-
"""
download_oaflux_evap.py — OAFlux 月度蒸发 (evap) 下载工具 (Phase 5: 海洋蒸发趋势, 图5)

论文需求 (复现方案: OAFlux 1991-2020, 1° 月度, 海洋蒸发趋势):
    合并输出 data/OAFlux/OAFlux_evap_1991_2020_monthly.nc
    (TECHNICAL_SPEC.md §3.2 load_oaflux 的默认路径)

数据源 (全部为官方分发, 已从 WHOI 官网 data-access 页核实):
    主源   WHOI FTP       ftp://ftp.whoi.edu/pub/science/oaflux/data_v3
    镜像1  WHOI HTTP      http://ftp1.whoi.edu/pub/science/oaflux/data_v3
    镜像2  NOAA PSL       https://psl.noaa.gov/thredds/catalog/Datasets/oaflux/catalog.xml
    镜像3  APDRC (U.Hawaii) http://apdrc.soest.hawaii.edu/dods/public_data/OAFlux/
    本脚本按优先级自动探测各镜像目录树, 定位含 evap 的月值 NetCDF, 无需手工指路。
    (2025-09-22 实测: 各镜像当日网络均不稳定, 故脚本设计为逐镜像降级 + 内容强校验,
     绝不下载未经校验的文件。)

内容校验 (每个年文件必须全部通过, 否则弃用):
    - 能被 xarray 打开
    - 存在名称含 "evap" 的数据变量
    - 网格为全球 (经度 >= 180 格点, 纬度 >= 80 格点, 即 1° 全球)
    - 当年 12 个月步齐全
最终合并件再校验: 1991-2020 共 360 个月步。

用法:
    python python/download_oaflux_evap.py                    # 1991-2020
    python python/download_oaflux_evap.py --start 1985 --end 2023
    python python/download_oaflux_evap.py --merge            # 仅合并 raw/ 已有文件
    python python/download_oaflux_evap.py --probe            # 只探测各镜像可用性, 不下载

依赖: xarray netcdf4 (已装); 无需账号。
"""
import argparse
import calendar
import os
import re
import sys

BASE_DIR = r"D:\2607compound"
OAFLUX_DIR = os.path.join(BASE_DIR, "data", "OAFlux")
RAW_DIR = os.path.join(OAFLUX_DIR, "raw")
MERGED_PATH = os.path.join(OAFLUX_DIR, "OAFlux_evap_1991_2020_monthly.nc")
DEFAULT_START, DEFAULT_END = 1991, 2020
YEAR_RE = re.compile(r"(19|20)\d{2}")
UA = {"User-Agent": "Mozilla/5.0 (research script)"}


def ensure_utf8_console():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _http_get(url, timeout=60, binary=False):
    import urllib.request
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", errors="ignore")


# ---------------------------------------------------------------- 目录发现 --
def parse_index(html, url):
    """解析 Apache 风格目录索引, 返回 [(完整URL, 是否目录)]; 忽略绝对外链/锚点/查询串。"""
    out = []
    for href in re.findall(r'href="([^"?#]+)"', html, re.I):
        h = href.strip()
        if not h or h.startswith(("/", "//", "mailto:", "javascript:", "#")):
            continue
        absolute = h.startswith("http:") or h.startswith("https:")
        if absolute and not h.startswith(url.rstrip("/") + "/"):
            continue
        name = h.rstrip("/").rsplit("/", 1)[-1]
        if not name or name in (".", "..", "Parent Directory"):
            continue
        is_dir = h.endswith("/") or "." not in name
        full = h if absolute else url.rstrip("/") + "/" + h
        out.append((full, is_dir))
    return out


def discover_ftp_whoi():
    """WHOI FTP: BFS 走 data_v3 目录树, 返回 [(url, size)]; url 形如 ftp://host/path。"""
    import ftplib
    host, base = "ftp.whoi.edu", "/pub/science/oaflux/data_v3"
    found, stack, visited = [], [(base, 0)], set()
    ftp = ftplib.FTP(host, timeout=60)
    ftp.login()
    ftp.set_pasv(True)
    try:
        while stack:
            path, depth = stack.pop()
            key = path.lower()
            if key in visited or depth > 4:
                continue
            visited.add(key)
            try:
                entries = list(ftp.mlsd(path, facts=["type", "size"]))
            except Exception:
                try:
                    names = ftp.nlst(path)
                    entries = [(n.rstrip("/").rsplit("/", 1)[-1], {"type": "unknown"})
                               for n in names if n not in (".", "..")]
                except Exception:
                    continue
            for name, facts in entries:
                if name in (".", ".."):
                    continue
                full = path.rstrip("/") + "/" + name
                t = facts.get("type", "unknown")
                if t == "dir":
                    stack.append((full, depth + 1))
                elif t == "file":
                    if name.lower().endswith(".nc"):
                        found.append((f"ftp://{host}{full}", int(facts.get("size") or 0)))
                else:
                    # 类型未知: 试探是否目录
                    try:
                        cur = ftp.pwd()
                        ftp.cwd(full)
                        ftp.cwd(cur)
                        stack.append((full, depth + 1))
                    except Exception:
                        if name.lower().endswith(".nc"):
                            found.append((f"ftp://{host}{full}", 0))
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    return found


def discover_http_whoimirror():
    """WHOI HTTP 镜像: 解析目录索引页, BFS 走目录树。"""
    base = "http://ftp1.whoi.edu/pub/science/oaflux/data_v3"
    found, stack, visited = [], [(base, 0)], set()
    while stack:
        url, depth = stack.pop()
        key = url.rstrip("/").lower()
        if key in visited or depth > 4:
            continue
        visited.add(key)
        try:
            html = _http_get(url, timeout=45)
        except Exception:
            continue
        for full, is_dir in parse_index(html, url):
            if is_dir:
                stack.append((full, depth + 1))
            elif full.lower().endswith(".nc"):
                found.append((full, 0))
    return found


def discover_psl_thredds():
    """NOAA PSL THREDDS: 递归解析 catalog.xml (catalogRef 子目录 + dataset urlPath)。"""
    import xml.etree.ElementTree as ET
    TH = "{http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0}"
    XL = "{http://www.w3.org/1999/xlink}"
    base = "https://psl.noaa.gov/thredds/catalog/Datasets/oaflux"
    files_url = "https://psl.noaa.gov/thredds/fileServer/Datasets/oaflux"
    found, stack, visited = [], [("/catalog.xml", 0)], set()
    while stack:
        rel, depth = stack.pop()
        if rel in visited or depth > 4:
            continue
        visited.add(rel)
        try:
            xml_text = _http_get(base + rel, timeout=45)
        except Exception:
            continue
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            continue
        parent_dir = rel.rsplit("/", 1)[0]  # 相对当前 catalog.xml 所在目录
        for ds in root.iter(TH + "dataset"):
            urlpath = ds.get("urlPath")
            if urlpath and urlpath.lower().endswith(".nc"):
                found.append((f"{files_url}/{urlpath}", 0))
        for cat in root.iter(TH + "catalogRef"):
            href = cat.get(XL + "href")
            if not href:
                continue
            # href 相对当前 catalog.xml 所在目录解析
            if href.startswith("/"):
                child = href
            else:
                child = (parent_dir + "/" if parent_dir else "/") + href
            stack.append((child, depth + 1))
    return found


def discover_apdrc():
    """APDRC DODS 目录: 尽力而为, 部分目录不暴露 .nc 直链。"""
    base = "http://apdrc.soest.hawaii.edu/dods/public_data/OAFlux"
    found, stack, visited = [], [(base, 0)], set()
    while stack:
        url, depth = stack.pop()
        key = url.rstrip("/").lower()
        if key in visited or depth > 3:
            continue
        visited.add(key)
        try:
            html = _http_get(url, timeout=45)
        except Exception:
            continue
        for full, is_dir in parse_index(html, url):
            if is_dir:
                stack.append((full, depth + 1))
            elif full.lower().endswith(".nc"):
                found.append((full, 0))
    return found


DISCOVERERS = [
    ("WHOI FTP (主源)", discover_ftp_whoi),
    ("WHOI HTTP 镜像", discover_http_whoimirror),
    ("NOAA PSL THREDDS 镜像", discover_psl_thredds),
    ("APDRC 镜像", discover_apdrc),
]


def collect_candidates():
    """依次尝试各镜像, 返回首个成功发现 [(url, size)] 的 (名称, 列表)。"""
    for name, fn in DISCOVERERS:
        print(f"探测镜像: {name} ...", flush=True)
        try:
            items = fn()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  失败: {type(e).__name__}: {str(e)[:100]}")
            continue
        evaps = [(u, s) for (u, s) in items if "evap" in os.path.basename(u).lower()]
        print(f"  发现 .nc {len(items)} 个, 其中 evap {len(evaps)} 个")
        if evaps:
            return name, evaps
    return None, []


def pick_by_year(cands, year):
    """从候选中选出文件名含目标年份者 (多个时: 月值目录/文件优先, 其次取更大者)。"""
    picks = []
    for u, s in cands:
        base = os.path.basename(u)
        ys = {m.group(0) for m in re.finditer(r"(?:19|20)\d{2}", base)}
        if str(year) in ys:
            picks.append((u, s))
    if not picks:
        return None

    def rank(item):
        u, s = item
        return ("month" in u.lower(), s, u)

    return sorted(picks, key=rank, reverse=True)[0][0]


# ---------------------------------------------------------------- 下载/校验 --
def fetch(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if url.startswith("ftp://"):
        import ftplib
        from urllib.parse import urlparse
        pu = urlparse(url)
        ftp = ftplib.FTP(pu.hostname, timeout=90)
        ftp.login()
        try:
            with open(dest, "wb") as f:
                ftp.retrbinary(f"RETR {pu.path}", f.write)
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()
    else:
        data = _http_get(url, timeout=600, binary=True)
        with open(dest, "wb") as f:
            f.write(data)


def verify_year_file(path, year):
    import xarray as xr
    try:
        ds = xr.open_dataset(path)
    except Exception as e:
        return False, f"打不开: {type(e).__name__}"
    try:
        evap = [v for v in ds.data_vars if "evap" in v.lower()]
        if not evap:
            return False, f"无 evap 变量 (现有: {list(ds.data_vars)})"
        latn = next((c for c in ("lat", "latitude") if c in ds.coords), None)
        lonn = next((c for c in ("lon", "longitude") if c in ds.coords), None)
        if latn is None or lonn is None:
            return False, "缺经纬度坐标"
        if ds.sizes.get(lonn, ds[lonn].size) < 180 or ds.sizes.get(latn, ds[latn].size) < 80:
            return False, "非全球 1° 网格"
        tn = next((c for c in ("time", "valid_time") if c in ds.dims or c in ds.coords), None)
        if tn is None:
            return False, "缺时间维"
        n = ds[tn].size
        if n != 12:
            return False, f"时间步 {n} != 12"
        return True, f"{ds[evap[0]].dims}, {n} 月"
    finally:
        ds.close()


def download(start, end, allow_partial=False):
    os.makedirs(RAW_DIR, exist_ok=True)
    mirror, cands = collect_candidates()
    if not cands:
        print("\n[失败] 所有官方镜像均不可达或无 evap 数据。")
        print("WHOI FTP 端口 21 可能被本网络封锁; 请换网络/开系统代理后重跑,")
        print("或手动从 https://oaflux.whoi.edu/data-access/ 列出的镜像下载 evap 月值,")
        print(f"放到 {RAW_DIR} 后运行 --merge。")
        return 1
    print(f"\n使用镜像: {mirror}")
    got, missed = 0, []
    for y in range(start, end + 1):
        dest = os.path.join(RAW_DIR, f"evap_{y}.nc")
        if os.path.exists(dest):
            ok, why = verify_year_file(dest, y)
            if ok:
                got += 1
                continue
            print(f"  {y}: 已存在但校验失败 ({why}), 重新下载")
            os.remove(dest)
        url = pick_by_year(cands, y)
        if url is None:
            print(f"  {y}: 镜像中未找到对应年份文件")
            missed.append(y)
            continue
        try:
            print(f"  {y}: 下载 {url}")
            fetch(url, dest)
            ok, why = verify_year_file(dest, y)
            if ok:
                print(f"       OK ({why})")
                got += 1
            else:
                print(f"       校验失败: {why}; 弃用")
                os.remove(dest)
                missed.append(y)
        except KeyboardInterrupt:
            print("\n用户中断; 已完成年份保留, 重跑续传。")
            return 1
        except Exception as e:
            print(f"       下载失败: {type(e).__name__}: {str(e)[:100]}")
            missed.append(y)
    print(f"\n就位 {got}/{end - start + 1} 年")
    if missed and not allow_partial:
        print("缺: ", missed)
        return 1
    return merge(start, end)


# ---------------------------------------------------------------- 合并 --
TIME_ALIASES = ("time", "valid_time", "T")
LAT_ALIASES = ("lat", "latitude", "y")
LON_ALIASES = ("lon", "longitude", "x")


def _rename_std(obj):
    for a in TIME_ALIASES[1:]:
        if a in obj.dims or a in getattr(obj, "coords", {}):
            obj = obj.rename({a: "time"})
    for a in LAT_ALIASES[1:]:
        if a in obj.dims or a in getattr(obj, "coords", {}):
            obj = obj.rename({a: "lat"})
    for a in LON_ALIASES[1:]:
        if a in obj.dims or a in getattr(obj, "coords", {}):
            obj = obj.rename({a: "lon"})
    return obj


def merge(start, end):
    import numpy as np
    import xarray as xr
    das, missing = [], []
    for y in range(start, end + 1):
        p = os.path.join(RAW_DIR, f"evap_{y}.nc")
        if not os.path.exists(p):
            missing.append(y)
            continue
        ds = xr.open_dataset(p)
        var = [v for v in ds.data_vars if "evap" in v.lower()][0]
        da = _rename_std(ds[var]).load()
        ds.close()
        das.append(da)
    if not das:
        print("raw/ 中没有可合并文件。")
        return 1
    merged = xr.concat(das, dim="time").sortby("time")
    merged.attrs.update({
        "source": "WHOI OAFlux (objectively analyzed air-sea fluxes), monthly evaporation",
        "period": f"{start}-{end}",
        "history": "merged by python/download_oaflux_evap.py",
    })
    os.makedirs(OAFLUX_DIR, exist_ok=True)
    enc = {"evap": {"zlib": True, "complevel": 4, "_FillValue": np.float32(9.96921e36)}} \
        if "evap" in merged.data_vars else {v: {"zlib": True, "complevel": 4} for v in merged.data_vars}
    merged.to_netcdf(MERGED_PATH, encoding=enc)
    n = merged.sizes["time"]
    exp = (end - start + 1) * 12
    status = "OK" if n == exp else f"警告: {n} != 预期 {exp} 月 (缺 {missing})"
    print(f"合并完成: {MERGED_PATH}  时间步 {n}  {status}")
    return 0


def probe():
    for name, fn in DISCOVERERS:
        print(f"探测: {name}")
        try:
            items = fn()
            evaps = [u for (u, s) in items if "evap" in os.path.basename(u).lower()]
            print(f"  .nc 共 {len(items)}, evap {len(evaps)}")
            for u in evaps[:5]:
                print("    例:", u)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"  失败: {type(e).__name__}: {str(e)[:120]}")


def main():
    ensure_utf8_console()
    ap = argparse.ArgumentParser(description="OAFlux 月度蒸发下载 (官方多镜像自动降级)")
    ap.add_argument("--start", type=int, default=DEFAULT_START)
    ap.add_argument("--end", type=int, default=DEFAULT_END)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--probe", action="store_true", help="只探测镜像, 不下载")
    ap.add_argument("--allow-partial", action="store_true", help="允许缺年合并")
    args = ap.parse_args()
    if args.probe:
        probe()
        return 0
    if args.merge:
        return merge(args.start, args.end)
    return download(args.start, args.end, args.allow_partial)


if __name__ == "__main__":
    sys.exit(main())
