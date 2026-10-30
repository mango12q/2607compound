# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════
#  download_era5_fast.py — Phase 5 的 ERA5 输入「按年分块 + 并发」下载引擎
#
#  为什么需要它（2026-09-25 实测）：
#     download_era5_tmax.py / download_era5_sp025.py 原本是**一个月一个 CDS 请求**
#     （tmax 479 个、sp 480 个）。CDS 的耗时几乎全在**排队**上，与请求大小关系不大：
#     同一脚本实测单月 25 s ~ 29 min（1984-02 用 25 s，1984-04 排了 29 min），
#     479 次排队要几天。本脚本把 12 个月并成 1 个请求（每变量 40 个请求）。
#
#  ★ 并发上限的实测结论（2026-09-25 02:00，重要）：
#     CDS 对**同一数据集同时排队的请求数**有临时限制，服务器原文：
#       "Number queued requests for this dataset is temporarily limited.
#        Please configure your scripts accordingly"
#     超限时**新提交的请求（哪怕只有一个月）也会被 rejected**（HTTP 201 接受后再变
#     rejected，cdsapi 表现为 400 on /retrieve/v1/jobs/<id>）。
#     实测该数据集一次排 ~4 个就开始拒单，因此本脚本默认 **--jobs 2**；
#     命中限流后会自动全局暂停并指数退避重试同一个请求（不会丢月份）。
#     想更激进可 --jobs 3~4，但被拒的概率随之上升（被拒也会自动重试，只是浪费一次排队）。
#
#  ★ 2026-10-15 实测补充（这一轮"6 小时零产出"的根因与三条对策）：
#     ① 限流是**平台按数据集算的全局拥塞**，不只取决于我们自己的并发。当天 200 条任务里
#        141 条 rejected、只有 10 条 successful（全是 10-14 的），被拒原因原文：
#        `Number queued requests for this dataset is temporarily limited`。
#        在队 24 h 的 2004 号任务 `updated == created` ⇒ 平台连"开始算"都没排到。
#     ② **队列里的任务能精确识别年份**：平台把请求体放在
#        `GET /retrieve/v1/jobs/<id>?request=true&log=true` 的 `metadata.request.ids`
#        （**普通 GET 看不到**）⇒ 提交前先问平台"这一年是不是已经在队里"，可同时消灭
#        "上一轮留下的在队任务被重投"和"POST 撞 SSLError 但平台其实已受理"两种重复。
#     ③ 运行中每 10 分钟收割一次（`harvest_loop`，复用 adopt_cds_jobs.py 同一套逻辑）：
#        平台替我们跑完的任务当场落盘，不必等下次重开窗口。
#
#  输出与旧脚本**完全一致**：
#     data/ERA5/tmax_eur_daily/tmax_eur_YYYY_MM.nc
#     data/ERA5/sp_eur_daily/sp_eur_YYYY_MM.nc
#  年请求回来的文件在本地按 12 个月切开，**逐月过旧脚本的 verify_month() 校验**，
#  所以 config.py / phase5_humid.py / download_phase5.py 下游一行都不用改。
#
#  用法:
#     python python\download_era5_fast.py --dry-run     # 只看计划（不联网）
#     python python\download_era5_fast.py               # 下载 tmax + sp（缺哪补哪）
#     python python\download_era5_fast.py --only tmax   # 只补 tmax
#     python python\download_era5_fast.py --jobs 3      # 并发数（默认 2）
#     python python\download_era5_fast.py --chunk-months 1   # 改成"一次一个月"（排队次数 ×12）
#     python python\download_era5_fast.py --chunk-months 6   # 半年一请求（折中）
#     python python\download_era5_fast.py --selftest    # 纯本地自检（不联网、不写 data/）
#
#  ★ 请求粒度：**默认 12 = 一次申请一年**（2026-09-25 实测拍板）
#     CDS 排队按"任务(job)"计，**与请求大小基本无关**：实测同一拥塞时段里，
#       · 年请求 3.1 h / 6.1 h 各交付 8 / 12 个月  → 约 3.3 个月/小时（2 并发）
#       · 月请求 12:16 提交、到 13:26 仍排队 69 min 未出数据 → ≤1.3 个月/小时
#     故一年一请求把排队次数由 936 降到 78，整体快 2.5–12 倍。
#     平台单请求 size 上限 = **400 天**（costing 接口实测：2 年 731 > 400 会被拒），
#     所以 12 个月已是允许的最大块，不可能再合并。
#     粒度仍可用 --chunk-months 自由切，输出文件名/校验/下游完全一样。
#
#  旧脚本也已接上本引擎（同一套代码，无第二份实现）：
#     python python\download_era5_tmax.py                   # 默认 = 一次一年 + 2 并发
#     python python\download_era5_tmax.py --chunk-months 1  # = 一次一个月
#
#  ⚠️ 两套入口**不要同时跑**：都会写同一个 .part，会互相踩。
# ══════════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import queue
import re
import socket
import sys
import threading
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# 复用旧脚本的：路径常量 / 数据集与变量定义 / verify_month() / merge()
# —— 避免出现"第二套校验口径"。
import download_era5_tmax as T   # noqa: E402
import download_era5_sp025 as S  # noqa: E402

DEFAULT_START, DEFAULT_END = 1984, 2023
DEFAULT_JOBS = 2                 # ★ CDS 对同数据集排队数有限制，默认只用 2 路
DEFAULT_MPR = 12                 # ★ 每个 CDS 请求含几个月：**默认 12 = 一次申请一年**
                                 #   实测依据：CDS 排队按"任务"计、与请求大小无关，
                                 #   年请求 3.1/6.1 h 各交付 8/12 个月，月请求同拥塞下 69 min
                                 #   仍未出数据 ⇒ 一年一请求把排队次数 936→78，快 2.5–12 倍。
                                 #   平台 size 上限 400 天（2 年 731 会被拒），12 已是最大块；
                                 #   想改粒度用 --chunk-months 1（月）或 6（半年）。
MAX_RETRY = 4                    # 瞬时错误重试次数
MAX_RATE_RETRY = 20              # "排队限流"拒绝的重试次数（会等很久，别轻易放弃）
CHUNK_SUBDIR = "_chunks"         # 年文件的临时落脚点（在各自 OUT_DIR 下）
LIVE_CAP_MIN = 6                 # 我们最多同时占几个 CDS 队列槽位（实测平台上限 3~6，随全局拥塞浮动）

# ── 限流熔断（2026-10-17）：平台拥塞时**别再反复申请**，就好好等 ──────────────
#   病根：每个年份各自重试 MAX_RATE_RETRY=20 次（每次冷却 60..600 s），限流期间就会
#   一年接一年地投、一个一个被拒，日志刷满 rejected 记录，进度却为零。
#   熔断：CONG_WINDOW 秒内累计被限流 CONG_TRIP 次 ⇒ 全体暂停提交 CONG_COOLDOWN 秒，
#   这段时间只跑收割线程（平台已经算完的照样收），冷却结束再试着投一个。
CONG_TRIP = 6                    # 窗口内被限流几次就熔断
CONG_WINDOW = 900                # 统计窗口（秒，15 分钟）
CONG_COOLDOWN = 1800             # 熔断后暂停提交多久（秒，30 分钟）

# 平台"请求过大/不合法"类拒绝的判据 —— 命中后自动降级为更小的分块，而不是傻等重试
SIZE_ERROR_HINTS = (
    "too large", "too big", "exceeds", "exceed the", "cost limit", "request cost",
    "maximum number", "too many", "please reduce", "reduce the", "not valid", "invalid",
)
# 平台"同数据集排队请求数受限"的判据（来自 /jobs/<id>/results 的 traceback 字段）
QUEUE_LIMIT_HINTS = ("temporarily limited", "queued requests", "queue limit")
JOB_ID_RE = re.compile(r"/jobs/([0-9a-fA-F][0-9a-fA-F\-]{5,})")
# 上一轮已提交、还在 CDS 队列里的年份 —— 记在盘上，重启后不重复排同一年
PENDING_FILE = os.path.join(os.path.dirname(HERE), "logs", "era5_pending_years.json")
PENDING_TTL_H = 24.0        # 超过这个小时数的记录视为失效（那一轮多半已经被杀了）


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class _Tee:
    """同时写到控制台与日志文件（UTF-8）—— 避免 shell 重定向把中文编成乱码。"""

    def __init__(self, path, stream):
        self._stream = stream
        self._file = open(path, "a", encoding="utf-8", buffering=1)

    def write(self, s):
        try:
            self._stream.write(s)
        except Exception:
            pass
        self._file.write(s)

    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass
        self._file.flush()

    def reconfigure(self, *a, **k):      # 兼容 ensure_utf8_console()
        pass

    def isatty(self):
        return False


def group(seq, n):
    seq = list(seq)
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def looks_like_size_error(msg: str) -> bool:
    m = (msg or "").lower()
    return any(h in m for h in SIZE_ERROR_HINTS)


# ──────────────────────────────────────────────────────────────────────────
#  在队年份登记 —— 关窗口/被杀/重启后，不会把"已经排上队的那几年"再排一遍
#  （CDS 的 job 详情接口不返回请求内容，所以在提交时自己记：年 -> 提交时间）
# ──────────────────────────────────────────────────────────────────────────
def _pending_load() -> dict:
    try:
        with open(PENDING_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _pending_save(d: dict) -> None:
    try:
        os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    except Exception:
        pass


def mark_pending(key: str, year: int) -> None:
    """这一年的请求刚提交（可能还在 CDS 排队）—— 登记下来。"""
    d = _pending_load()
    d.setdefault(key, {})[str(year)] = time.strftime("%F %T")
    _pending_save(d)


def unmark_pending(key: str, year: int) -> None:
    d = _pending_load()
    if str(year) in (d.get(key) or {}):
        d[key].pop(str(year), None)
        _pending_save(d)


def pending_years(key: str) -> set:
    """上一轮提交、TTL 内、还没出结果的年份（顺带把过期记录清掉）。"""
    d = _pending_load()
    now = time.time()
    changed = False
    out = set()
    for k, years in list(d.items()):
        keep = {}
        for y, ts in (years or {}).items():
            try:
                age_h = (now - time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))) / 3600.0
            except Exception:
                age_h = 0.0
            if age_h <= PENDING_TTL_H:
                keep[y] = ts
            else:
                changed = True
        d[k] = keep
        if k == key:
            out = {int(y) for y in keep}
    if changed:
        _pending_save(d)
    return out


# ──────────────────────────────────────────────────────────────────────────
# 目标定义（tmax / sp 共用同一套逻辑）
# ──────────────────────────────────────────────────────────────────────────
class Target:
    def __init__(self, key, mod, prefix, daily_statistic):
        self.key = key
        self.mod = mod
        self.prefix = prefix                  # tmax_eur / sp_eur
        self.daily_statistic = daily_statistic
        self.out_dir = mod.OUT_DIR
        self.dataset = mod.DATASET
        self.variable = mod.VARIABLE
        self.area = mod.AREA
        self.merged_path = mod.MERGED_PATH
        self.chunk_dir = os.path.join(self.out_dir, CHUNK_SUBDIR)

    def month_path(self, y, m):
        return os.path.join(self.out_dir, f"{self.prefix}_{y}_{m:02d}.nc")


TARGETS = {
    "tmax": Target("tmax", T, "tmax_eur", "daily_maximum"),
    "sp": Target("sp", S, "sp_eur", S.DAILY_STATISTIC),
}


class Task:
    __slots__ = ("year", "months")

    def __init__(self, year, months):
        self.year = year
        self.months = list(months)

    def label(self):
        return f"{self.year}-{self.months[0]:02d}..{self.months[-1]:02d}"


class Opts:
    """run_target 需要的几个参数（脱离 argparse 也能被旧脚本调用）。"""

    def __init__(self, months_per_request=DEFAULT_MPR, jobs=DEFAULT_JOBS,
                 keep_chunks=False):
        self.months_per_request = months_per_request
        self.jobs = jobs
        self.keep_chunks = keep_chunks


# ──────────────────────────────────────────────────────────────────────────
#  计划：缺哪几个月（复用旧脚本的 verify_month，坏文件删掉重下）
# ──────────────────────────────────────────────────────────────────────────
def build_plan(target, start, end):
    todo = {}
    present = 0
    for y in range(start, end + 1):
        miss = []
        for m in range(1, 13):
            p = target.month_path(y, m)
            if os.path.exists(p):
                ok, why = target.mod.verify_month(p, y, m)
                if ok:
                    present += 1
                    continue
                log(f"  坏文件重下: {os.path.basename(p)} ({why})")
                try:
                    os.remove(p)
                except OSError:
                    pass
            miss.append(m)
        if miss:
            todo[y] = miss
    return todo, present


def dry_run(target, start, end, mpr, jobs):
    todo, present = build_plan(target, start, end)
    pend = pending_years(target.key)
    skipped = sorted(y for y in todo if y in pend)
    for y in skipped:
        todo.pop(y, None)
    n_missing = sum(len(v) for v in todo.values())
    n_req = sum(len(group(v, mpr)) for v in todo.values())
    print(f"\n── {target.key} ── {target.variable} / {target.daily_statistic}")
    print(f"   输出目录 : {target.out_dir}")
    print(f"   合并件   : {target.merged_path}")
    print(f"   area={target.area}  0.25°")
    print(f"   已就位   : {present} 个月")
    print(f"   待下载   : {n_missing} 个月")
    if skipped:
        print(f"   排队中   : {', '.join(str(y) for y in skipped)}"
              f"（{len(skipped)} 个年份已在 CDS 队列里，本轮不重复提交）")
    if n_missing:
        print(f"   请求数   : {n_req} 个（每月一请求则需 {n_missing} 个）"
              f"，{jobs} 路并发")
        for y in sorted(todo):
            print(f"     {y}: {len(todo[y])} 个月 -> {todo[y][0]:02d}..{todo[y][-1]:02d}")
    return n_missing, n_req


# ──────────────────────────────────────────────────────────────────────────
#  CDS 请求
# ──────────────────────────────────────────────────────────────────────────
def chunk_request(target, year, months):
    """一个请求含多个月：year/month/day 三个字段本来就是列表（CDS 表单已确认）。"""
    return {
        "product_type": ["reanalysis"],
        "variable": [target.variable],
        "year": [str(year)],
        "month": [f"{m:02d}" for m in months],
        "day": [f"{d:02d}" for d in range(1, 32)],   # 短月由 CDS 自动忽略
        "daily_statistic": [target.daily_statistic],
        "time_zone": ["utc+00:00"],
        "frequency": ["1_hourly"],
        "area": target.area,
        "data_format": "netcdf",
        "download_format": "unarchived",             # 平台会 warning 后回落 as_source，正常
    }


def new_client():
    import cdsapi
    return cdsapi.Client(quiet=True)


# ── 网络前提：系统代理指向"没人监听的端口"时，requests 会一路报 ProxyError ──
def ensure_network():
    """开工前探一次系统代理；连不上就把本进程改成直连（并把原因写进日志）。

    2026-10-16 实测：代理客户端没开、但系统代理仍写着 127.0.0.1:7890 ⇒ cdsapi/requests
    读它 → 所有请求 `ProxyError`；同一时刻**直连 CDS 反而正常**（HTTP 200 / 0.9 s）。
    """
    import urllib.request
    try:
        proxies = urllib.request.getproxies()
    except Exception:
        return
    url = proxies.get("https") or proxies.get("http")
    if not url:
        log("代理: 系统未设置代理，直连")
        return
    hostport = url.split("://")[-1].split("/")[0]
    host, _, port = hostport.partition(":")
    try:
        with socket.create_connection((host, int(port or 80)), timeout=3):
            log(f"代理: 系统代理 {hostport} 可用，按系统设置走代理")
            return
    except OSError:
        pass
    os.environ["NO_PROXY"] = "*"      # 让 requests/urllib 彻底忽略系统代理（实测有效）
    log(f"⚠️ 系统代理 {hostport} 连不上（多半代理客户端没开）⇒ 本进程改走直连；"
        f"实测直连 CDS 正常。要恢复走代理：打开代理客户端后重启本窗口即可")


# ── CDS 排队限流的识别与全局节流 ─────────────────────────────────────────
_CREDS = {}


def creds():
    """取 CDS 凭据（环境变量优先，其次 ~/.cdsapirc），用于查任务被拒的真实原因。"""
    if _CREDS:
        return _CREDS
    url = os.environ.get("CDSAPI_URL")
    key = os.environ.get("CDSAPI_KEY")
    if not (url and key):
        p = os.path.expanduser("~/.cdsapirc")
        try:
            for ln in open(p, encoding="utf-8", errors="ignore"):
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    k, v = k.strip().lower(), v.strip()
                    if k == "url" and not url:
                        url = v
                    elif k == "key" and not key:
                        key = v
        except OSError:
            pass
    _CREDS["url"] = (url or "https://cds.climate.copernicus.eu/api").rstrip("/")
    _CREDS["key"] = key or ""
    return _CREDS


# ── 平台实况：队列里现在有哪些 (变量, 年份) ────────────────────────────────
class AlreadyQueued(Exception):
    """这一年已经在 CDS 队列里（平台实况），本轮不再重复提交。"""


_LIVE = {"t": 0.0, "keys": set(), "log_t": 0.0, "ok": False}
_LIVE_TTL = 90.0                 # 秒；避免每个任务都去问一次平台
_CONG = {"hits": [], "until": 0.0, "log_t": 0.0}   # 限流熔断状态（见 CONG_* 常量）


def live_job_keys(force=False):
    """平台实况：仍在队/在跑的任务分别是哪个变量、哪一年。

    平台把请求体放在 `GET /retrieve/v1/jobs/<id>?request=true&log=true` 的
    `metadata.request.ids` 里（**普通 GET 看不到**，2026-10-15 才查明），
    所以"排队中的年份"可以精确识别 —— 这是"不重复排队"的权威依据：
    本地台账只记我们自己发过什么，平台实况还能看到"响应丢失但其实已受理"的那条。
    """
    if not force and time.time() - _LIVE["t"] < _LIVE_TTL:
        return set(_LIVE["keys"])
    c = creds()
    import requests
    H = {"PRIVATE-TOKEN": c["key"]}
    keys = set()
    try:
        # 必须按状态过滤：接口按 -created 倒序，被拒记录一多（2026-10-17 已 391 条）
        # 前 200 条就全是 rejected，在队任务会被挤出视野 ⇒ 引擎误判"队列为空"而重复提交。
        js = requests.get(f"{c['url']}/retrieve/v1/jobs", headers=H, timeout=45,
                          params=[("limit", 200), ("status", "accepted"),
                                  ("status", "running")]).json().get("jobs", [])
    except Exception as e:
        log(f"（查 CDS 在队任务失败，退回本地台账判断: {type(e).__name__}）")
        _LIVE["t"] = time.time()        # 失败也记时间：避免网络抖时每个任务都去撞一次
        _LIVE["ok"] = False             # 让"对账"知道这次没读到实况，别误清台账
        return set(_LIVE["keys"])
    for j in js:
        if j.get("status") not in ("accepted", "running"):
            continue
        ids = {}
        for _ in range(2):                  # 这个接口偶发返回空 ids，重试一次
            try:
                md = requests.get(f"{c['url']}/retrieve/v1/jobs/{j['jobID']}"
                                  "?request=true&log=true",
                                  headers=H, timeout=45).json().get("metadata", {})
                ids = (md.get("request") or {}).get("ids") or {}
            except Exception:
                ids = {}
            if ids:
                break
            time.sleep(2)
        for y in ids.get("year") or []:
            for v in ids.get("variable") or [""]:
                keys.add((v, int(y)))
    _LIVE["t"], _LIVE["keys"] = time.time(), keys
    _LIVE["ok"] = True
    return set(keys)


def queued_years(target, force=False):
    """该变量当前在 CDS 队列里的年份集合（平台实况）。"""
    return {y for (v, y) in live_job_keys(force=force) if v == target.variable}


def reconcile_pending(targets):
    """开局对账：本地台账里"已提交"的年份，平台上若已无对应在队任务，
    说明它已被拒/已跑完/已被收走 —— 从台账里删掉，免得被白跳过 24 小时。"""
    live = live_job_keys(force=True)
    if not _LIVE.get("ok"):
        log("（对账跳过：这次没能从平台读回在队任务列表，保留台账）")
        return
    for key, target in targets.items():
        for y in sorted(pending_years(key)):
            if (target.variable, y) not in live:
                unmark_pending(key, y)
                log(f"{key}: 台账里的 {y} 在平台上已无在队任务（多半被拒了），"
                    f"解除跳过、本轮重新申请")


def harvest_loop(stop_event, interval=600):
    """运行中每 10 分钟收割一次：把"平台已经算完、我们还没拿下来"的任务变成月文件。

    引擎自己的 worker 只认自己那一次提交；上一次运行留下的、或"响应丢失但平台其实
    已受理"的任务，靠这里在**本轮运行期间**收下来（复用 adopt_cds_jobs.py 的同一套逻辑，
    收齐一年的 12 个月后它会顺手把本地台账里的那一年注销）。
    """
    while not stop_event.wait(interval):
        try:
            import adopt_cds_jobs as A
            A.main(["--max-jobs", "10", "--since-hours", "72"])
        except BaseException as e:
            log(f"（收割线程: {type(e).__name__}: {str(e)[:120]}）")


def job_reject_reason(err_text):
    """cdsapi 对"被拒任务"只报 `400 ... /jobs/<id>`；这里用 job id 问服务器真正原因。"""
    m = JOB_ID_RE.search(err_text or "")
    if not m:
        return None
    c = creds()
    try:
        import requests
        r = requests.get(f"{c['url']}/retrieve/v1/jobs/{m.group(1)}/results",
                         headers={"PRIVATE-TOKEN": c["key"]}, timeout=30)
        return r.text
    except Exception:
        return None


def is_queue_limit(reason):
    t = (reason or "").lower()
    return any(h in t for h in QUEUE_LIMIT_HINTS)


def _cong_hit():
    """记一次"被平台限流"。窗口内连着被拒 -> 熔断：全体暂停提交，只等平台消化。

    用户 2026-10-17 的反馈就是这条："在等待的时候也别反复申请，为什么不好好等？"
    """
    now = time.time()
    _CONG["hits"] = [t for t in _CONG["hits"] if now - t <= CONG_WINDOW] + [now]
    if len(_CONG["hits"]) >= CONG_TRIP and _CONG["until"] < now:
        _CONG["until"] = now + CONG_COOLDOWN
        _CONG["hits"] = []
        _CONG["log_t"] = 0.0
        log(f"  ⛔ 这 {CONG_WINDOW // 60} 分钟内已被限流 {CONG_TRIP} 次 ⇒ 暂停提交 "
            f"{CONG_COOLDOWN // 60} 分钟，不再反复申请；"
            f"这段时间只收割平台已经跑完的任务（每 10 分钟一次）")


def _cong_until():
    return max(0.0, _CONG["until"] - time.time())


def _wait_congested(year=None, stop_event=None):
    """熔断期间：只等，不提交。每 5 分钟报一次还剩多久。"""
    while _cong_until() > 0:
        if stop_event is not None and stop_event.is_set():
            return
        left = int(_cong_until())
        if time.time() - _CONG["log_t"] > 300:
            _CONG["log_t"] = time.time()
            log(f"  ⏳ 平台在限流：暂停提交{(' ' + str(year)) if year else ''}，"
                f"还等 {left // 60} 分 {left % 60} 秒（期间仍在收割已完成的任务）")
        time.sleep(min(120, max(5, left)))


def clean_queue():
    """清掉本账号在该数据集上仍在排队/运行的任务。

    用途：进程被杀（Ctrl-C / 关窗口）**不会取消服务端任务**，被遗弃的 accepted 任务会继续
    占"同数据集排队数"额度，导致新请求被限流拒单。换入口重跑前先跑一次本开关。
    """
    c = creds()
    import requests
    H = {"PRIVATE-TOKEN": c["key"]}
    try:
        jobs = requests.get(f"{c['url']}/retrieve/v1/jobs?limit=50",
                            headers=H, timeout=45).json().get("jobs", [])
    except Exception as e:
        print(f"查询任务失败: {type(e).__name__}: {e}")
        return 1
    n = 0
    for j in jobs:
        if j.get("status") in ("accepted", "running"):
            try:
                d = requests.delete(f"{c['url']}/retrieve/v1/jobs/{j['jobID']}",
                                    headers=H, timeout=45)
                print(f"  DELETE {j['jobID'][:8]} {j['status']} -> HTTP {d.status_code}")
                n += 1
            except Exception as e:
                print(f"  DELETE {j['jobID'][:8]} 失败: {type(e).__name__}: {e}")
    from collections import Counter
    left = Counter(x.get("status") for x in jobs)
    print(f"清掉 {n} 个在队任务；当前状态统计: {dict(left)}")
    return 0


class Pacer:
    """全局提交节流：任一 worker 撞上限流，所有 worker 一起等，避免继续堆请求。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._until = 0.0

    def wait(self):
        while True:
            with self._lock:
                d = self._until - time.time()
            if d <= 0:
                return
            time.sleep(min(d, 5.0))

    def pause(self, secs):
        with self._lock:
            self._until = max(self._until, time.time() + secs)


def _rm_part(p):
    try:
        if os.path.exists(p):
            os.remove(p)
    except OSError:
        pass


def retrieve_with_retry(client, target, req, tmp, pacer=None, stop_event=None):
    """下载到 tmp。三类错误分开处理：
       ① 排队限流（rejected）-> 熔断/长退避，重试**同一个请求**（不丢月份、不换年份乱投）
       ② 请求过大/不合法      -> 抛出，交给上层拆成更小的分块
       ③ 其它瞬时错误          -> 指数退避重试 MAX_RETRY 次

    另加三道"别重复排队"的闸门（2026-10-15 / 10-17）：
       · 熔断期内先等（`_wait_congested`）：平台明显拥塞时**一次都不投**，省得刷 rejected；
       · 提交前先看平台实况：这一年已经在队里 -> 抛 AlreadyQueued，交给收割线程/adopt 收；
       · 我们自己占的队列槽位 >= LIVE_CAP_MIN 时先不提交（平台反正会拒），等空出来再试。
    """
    last = None
    rate_try = 0
    attempt = 0
    year = int(req["year"][0])
    while True:
        if pacer is not None:
            pacer.wait()
        _wait_congested(year, stop_event)      # 熔断期：只等，不提交
        if year in queued_years(target):
            raise AlreadyQueued(f"{target.key} {year}（平台队列里已有，不重复提交）")
        n_live = len(live_job_keys())
        if n_live >= LIVE_CAP_MIN:
            if time.time() - _LIVE["log_t"] > 600:
                _LIVE["log_t"] = time.time()
                log(f"  ⏳ 我们已有 {n_live} 个任务在 CDS 队列里（暂不再提交），"
                    f"等平台跑完一个再申请 {year}")
            time.sleep(60)
            continue
        try:
            try:
                client.retrieve(target.dataset, req, tmp)
            except Exception as e:                      # 平台不认 format 键时降级重试
                msg = str(e)
                if "data_format" in msg or "download_format" in msg:
                    req2 = {k: v for k, v in req.items()
                            if k not in ("data_format", "download_format")}
                    client.retrieve(target.dataset, req2, tmp)
                else:
                    raise
            return
        except Exception as e:
            last = e
            txt = str(e)
            _rm_part(tmp)
            # 提交时连接断了（SSLError 等）并不代表没提交成功：问一次平台实况，
            # 若这一年已经在队里，就说明"已受理但响应丢失"，绝不能再投一次。
            if year in queued_years(target, force=True):
                raise AlreadyQueued(f"{target.key} {year}（提交响应丢失，但平台已受理）")
            reason = job_reject_reason(txt)
            if is_queue_limit(reason):
                rate_try += 1
                if rate_try > MAX_RATE_RETRY:
                    raise
                wait = min(60 * rate_try, 600)
                _cong_hit()                     # 连续被限流就熔断，别再一年接一年地投
                if pacer is not None:
                    pacer.pause(wait)
                log(f"  ⏳ CDS 排队限流（同数据集排队请求数临时受限），"
                    f"冷却 {wait}s 后重试同一请求 [{rate_try}/{MAX_RATE_RETRY}]")
                continue
            if looks_like_size_error(txt):
                raise
            attempt += 1
            if attempt > MAX_RETRY:
                raise
            wait = 20 * 2 ** (attempt - 1)
            log(f"  第 {attempt}/{MAX_RETRY} 次失败: {type(e).__name__}: "
                f"{txt[:100]}; {wait}s 后重试")
            time.sleep(wait)


def unpack_if_zip(tmp):
    """把落到 tmp 的结果解成**一个或多个** .nc 路径。

    跨月请求的返回形态平台没写死：可能是单个多月 .nc，也可能是 zip 里**每月一个 .nc**
    （as_source 回落时尤其如此）。两种都吃掉，否则整批任务会以"zip 内文件数异常"失败。
    """
    with open(tmp, "rb") as f:
        if f.read(2) != b"PK":
            return [tmp]
    exdir = tmp + "_x"
    os.makedirs(exdir, exist_ok=True)
    with zipfile.ZipFile(tmp) as z:
        z.extractall(exdir)
    ncs = sorted(os.path.join(r, f) for r, _d, fs in os.walk(exdir) for f in fs
                 if f.lower().endswith(".nc"))
    if not ncs:
        raise RuntimeError("zip 内没有 .nc 文件")
    if len(ncs) == 1:
        out = tmp + ".nc"
        if os.path.exists(out):
            os.remove(out)
        os.replace(ncs[0], out)
        os.remove(tmp)
        return [out]
    # 多文件：搬到 _chunks 下按序号命名，交由 split_to_months 逐月挑
    outs = []
    for i, p in enumerate(ncs, 1):
        out = "%s.part%02d.nc" % (tmp, i)
        if os.path.exists(out):
            os.remove(out)
        os.replace(p, out)
        outs.append(out)
    os.remove(tmp)
    _rm(exdir)
    log(f"  （zip 内含 {len(outs)} 个 .nc，按多文件处理）")
    return outs


# ──────────────────────────────────────────────────────────────────────────
#  年文件 -> 12 个月文件（逐月过 verify_month）
# ──────────────────────────────────────────────────────────────────────────
def split_to_months(nc_paths, target, year, months, out_dir=None,
                    lock=None, counter=None):
    """把跨月请求的结果切成 YYYY_MM 月文件。

    `nc_paths` 可以是单个路径，也可以是**多个文件**（平台把每月一个 .nc 打包时）：
    逐文件挑月份，只要某个文件里有该月就切出来；全部文件都没有该月才算失败。
    """
    import numpy as np
    import xarray as xr

    if isinstance(nc_paths, (str, os.PathLike)):
        nc_paths = [nc_paths]
    out_dir = out_dir or target.out_dir
    os.makedirs(out_dir, exist_ok=True)
    todo = set(months)

    for nc_path in nc_paths:
        if not todo:
            break
        ds = xr.open_dataset(nc_path)
        try:
            ds = ds.load()
            tname = "valid_time" if "valid_time" in ds.dims else "time"
            mon = ds[tname].dt.month.values
            dvars = [v for v in ds.data_vars if ds[v].ndim >= 1]
            enc = {v: {"zlib": True, "complevel": 4} for v in dvars}

            for m in sorted(todo):
                idx = np.where(mon == m)[0]
                if idx.size == 0:
                    continue          # 这个文件里没有该月，留给别的文件
                sub = ds.isel({tname: idx})
                out = os.path.join(out_dir, f"{target.prefix}_{year}_{m:02d}.nc")
                tmp = out + ".part"
                sub.to_netcdf(tmp, encoding=enc)
                ok, why = target.mod.verify_month(tmp, year, m)
                if not ok:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                    _fail(f"{year}-{m:02d} 校验失败: {why}", lock, counter, year, m)
                    todo.discard(m)
                    continue
                os.replace(tmp, out)
                _ok(f"{target.prefix} {year}-{m:02d}  {why}", counter, lock)
                todo.discard(m)
        finally:
            ds.close()

    for m in sorted(todo):
        _fail(f"{year}-{m:02d} 平台返回的文件里没有该月", lock, counter, year, m)


def _ok(msg, counter, lock):
    if lock is None or counter is None:
        log(msg)
        return
    with lock:
        counter["done"] += 1
        done, total = counter["done"], counter["total"]
    log(f"[{done}/{total}] {msg}")


def _fail(msg, lock, counter, year=None, m=None):
    if lock is None or counter is None:
        log("  ✗ " + msg)
        return
    if year is not None:
        with lock:
            counter["failed"].append((year, m))
    log("  ✗ " + msg)


# ──────────────────────────────────────────────────────────────────────────
#  并发执行
# ──────────────────────────────────────────────────────────────────────────
def handle_task(task, target, state, lock, counter, q, client):
    cap = state["cap"]
    if len(task.months) > cap:                 # 之前触发过降级 —— 后续任务也照此拆分
        for grp in group(task.months, cap):
            q.put(Task(task.year, grp))
        return

    req = chunk_request(target, task.year, task.months)
    mark_pending(target.key, task.year)     # 已提交 -> 登记，重启后不再重复排这一年
    os.makedirs(target.chunk_dir, exist_ok=True)
    tmp = os.path.join(target.chunk_dir,
                       f"{target.prefix}_{task.year}_{task.months[0]:02d}.part")
    log(f"→ 请求 {target.prefix} {task.label()}（{len(task.months)} 个月合 1 个请求）")
    t0 = time.time()
    with lock:
        counter["inflight"] = counter.get("inflight", 0) + 1
    try:
        retrieve_with_retry(client, target, req, tmp, pacer=state.get("pacer"),
                            stop_event=state["stop"])
    except AlreadyQueued as e:
        with lock:
            counter["inflight"] = counter.get("inflight", 0) - 1
            counter["queued"].extend((task.year, m) for m in task.months)
        log(f"  ⏸ {task.label()} 已在 CDS 队列里（{e}），不重复提交；"
            f"它出结果后由本轮收割线程或 adopt_cds_jobs.py 收下")
        return
    except Exception as e:
        with lock:
            counter["inflight"] = counter.get("inflight", 0) - 1
        if looks_like_size_error(str(e)) and len(task.months) > 1:
            new_cap = max(1, len(task.months) // 2)
            with lock:
                state["cap"] = min(state["cap"], new_cap)
                cap_now = state["cap"]
            log(f"  ↳ 平台拒绝该请求（{str(e)[:90]}）；改为每 {cap_now} 个月一个请求")
            for grp in group(task.months, cap_now):
                q.put(Task(task.year, grp))
            _rm(tmp)
            return
        raise

    with lock:
        counter["inflight"] = counter.get("inflight", 0) - 1
    ncs = unpack_if_zip(tmp)
    el = time.time() - t0
    log(f"  ← {task.label()} 结果到位（{el:.0f} s，{len(ncs)} 个文件），开始按月切分")
    split_to_months(ncs, target, task.year, task.months, lock=lock, counter=counter)
    if not state.get("keep_chunks"):
        for p in ncs:
            _rm(p)
    _rm(tmp + "_x")
    if all(os.path.exists(target.month_path(task.year, m)) for m in range(1, 13)):
        unmark_pending(target.key, task.year)      # 这一年齐了，不再是"在队年份"


def _rm(p):
    try:
        if os.path.isdir(p):
            import shutil
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p):
            os.remove(p)
    except OSError:
        pass


def worker_loop(target, q, state, lock, counter):
    client = None
    while True:
        try:
            task = q.get(timeout=0.5)
        except queue.Empty:
            if state["stop"].is_set():
                return
            continue
        try:
            if client is None:
                client = new_client()
            handle_task(task, target, state, lock, counter, q, client)
        except Exception as e:
            with lock:
                counter["failed"].extend((task.year, m) for m in task.months)
            log(f"  ✗ {target.prefix} {task.label()} 本轮先放下: "
                f"{type(e).__name__}: {str(e)[:160]}"
                f"（缺的月份留在待办里，下一轮自动重排，不会丢）")
            unmark_pending(target.key, task.year)   # 这次没成，别把这一年一直锁着
        finally:
            q.task_done()


def heartbeat_loop(target, counter, lock, stop_event, interval=300):
    """每 5 分钟报一次心跳。

    CDS 排队动辄几十分钟到几小时，期间日志一行不涨，很容易被误判为"卡死"。
    """
    while not stop_event.wait(interval):
        with lock:
            done, total = counter["done"], counter["total"]
            nfail = len(counter["failed"])
            nq = len(counter["queued"])
            nf = counter.get("inflight", 0)
        if done + nfail + nq + nf >= total:
            return
        log(f"…心跳 {target.key}: 已完成 {done}/{total} 个月"
            f"（失败 {nfail}，仍在 CDS 队列 {nq}，本进程正在等 {nf} 个请求）"
            f"；日志长时间不涨 = 正在等 CDS 队列，不是卡死")


def run_target(target, todo, opts):
    live = queued_years(target)                     # 平台实况（权威）
    pend = pending_years(target.key)                # 本地台账（补"刚提交、实况还没刷出来"的几秒）
    queued = live | pend
    if queued:
        drop = sorted(y for y in todo if y in queued)
        if drop:
            for y in drop:
                todo.pop(y, None)
            log(f"{target.key}: ⏸ 跳过 {len(drop)} 个「CDS 队列里已经有」的年份："
                f"{', '.join(str(y) for y in drop)}"
                f"（平台实况 {len(set(drop) & live)} 个 / 本地台账 {len(set(drop) & pend)} 个；"
                f"出结果后由本轮收割线程或 adopt_cds_jobs.py 收下，不必重复排队）")
            if not todo:
                log(f"{target.key}: 其余月份都已就位，本轮没有新请求要发。")
                return []

    n_missing = sum(len(v) for v in todo.values())
    if n_missing == 0:
        log(f"{target.key}: 已全部就位，跳过")
        return []

    q = queue.Queue()
    for y in sorted(todo):
        for grp in group(todo[y], opts.months_per_request):
            q.put(Task(y, grp))

    lock = threading.Lock()
    counter = {"done": 0, "total": n_missing, "failed": [], "queued": [], "inflight": 0}
    state = {"cap": opts.months_per_request, "stop": threading.Event(),
             "keep_chunks": opts.keep_chunks, "pacer": Pacer()}

    n_req = q.qsize()
    n_threads = max(1, min(opts.jobs, n_req))
    log(f"{target.key}: 待下 {n_missing} 个月 / {n_req} 个请求，{n_threads} 路并发")
    log(f"{target.key}: 日志每 5 分钟会打一次心跳；排队期间没有新行属正常")
    t0 = time.time()
    hb = threading.Thread(target=heartbeat_loop,
                          args=(target, counter, lock, state["stop"]), daemon=True)
    hb.start()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_threads) as ex:
        futs = [ex.submit(worker_loop, target, q, state, lock, counter)
                for _ in range(n_threads)]
        # Queue.join() 会连同"处理过程中新加入的任务"一起等（分块降级时靠这个）
        q.join()
        state["stop"].set()
        for f in futs:
            f.result()

    el = time.time() - t0
    log(f"{target.key}: 本轮结束，用时 {el / 60:.1f} min，"
        f"成功 {counter['done']}/{n_missing}，失败 {len(counter['failed'])}，"
        f"仍在 CDS 队列 {len(counter['queued'])} 个月")
    return counter["failed"] + counter["queued"]


def run_one(key, start=DEFAULT_START, end=DEFAULT_END,
            months_per_request=DEFAULT_MPR, jobs=DEFAULT_JOBS,
            merge_flag=False, keep_chunks=False):
    """单变量入口（供旧脚本 download_era5_tmax.py / download_era5_sp025.py 调用）。"""
    target = TARGETS[key]
    T.check_credentials()
    os.makedirs(target.out_dir, exist_ok=True)
    todo, present = build_plan(target, start, end)
    n_missing = sum(len(v) for v in todo.values())
    log(f"{key}: 已就位 {present} 个月，待下 {n_missing} 个月")
    failed = run_target(target, todo, Opts(months_per_request, jobs, keep_chunks))
    if merge_flag:
        do_merge(target, start, end)
    if failed:
        print(f"\n[未完成] {key}: {len(failed)} 个月失败 -> "
              f"{[f'{y}-{m:02d}' for y, m in failed[:12]]}"
              f"{' ...' if len(failed) > 12 else ''}")
        print("原样重跑即可只补这些月份。")
        return 1
    return 0


# ──────────────────────────────────────────────────────────────────────────
#  合并（直接调旧脚本的 merge()，保证与正式链路同口径）
# ──────────────────────────────────────────────────────────────────────────
def all_present(target, start, end):
    for y in range(start, end + 1):
        for m in range(1, 13):
            if not os.path.exists(target.month_path(y, m)):
                return False
    return True


def do_merge(target, start, end):
    if not all_present(target, start, end):
        print(f"\n[{target.key}] 月份不齐，跳过合并（补齐后重跑本脚本或 --merge 即可）")
        return False
    print(f"\n[{target.key}] 合并为 {target.merged_path} ...", flush=True)
    return target.mod.merge(start, end) == 0


# ──────────────────────────────────────────────────────────────────────────
#  纯本地自检：合成一个闰年文件，验证"切分 + 校验"链路（不联网、不碰 data/）
# ──────────────────────────────────────────────────────────────────────────
def selftest():
    import calendar as _cal
    import shutil
    import tempfile

    import numpy as np
    import pandas as pd
    import xarray as xr

    tmp = tempfile.mkdtemp(prefix="era5fast_selftest_")
    try:
        target = TARGETS["tmax"]
        times = pd.date_range("1984-01-01", "1984-12-31", freq="D")   # 闰年 366 天
        lat = np.arange(66.0, 29.9, -0.25)
        lon = np.arange(-10.0, 40.1, 0.25)
        rng = np.random.default_rng(0)
        data = (280.0 + rng.normal(0, 3, (times.size, lat.size, lon.size))).astype("float32")
        ds = xr.Dataset(
            {"mx2t": (("valid_time", "latitude", "longitude"), data)},
            coords={"valid_time": times, "latitude": lat, "longitude": lon},
        )
        src = os.path.join(tmp, "tmax_eur_1984.nc")
        ds.to_netcdf(src)

        out = os.path.join(tmp, "months")
        split_to_months(src, target, 1984, list(range(1, 13)), out_dir=out)

        bad = []
        for m in range(1, 13):
            p = os.path.join(out, f"tmax_eur_1984_{m:02d}.nc")
            if not os.path.exists(p):
                bad.append(f"{m:02d} 缺文件")
                continue
            ok, why = T.verify_month(p, 1984, m)
            if not ok:
                bad.append(f"{m:02d} {why}")
            elif why.split(" ")[0] != str(_cal.monthrange(1984, m)[1]):
                bad.append(f"{m:02d} 天数不符: {why}")
        if bad:
            print("[FAIL] " + "; ".join(bad))
            return 1
        print("[OK] 12 个月文件全部生成，days/变量/纬度校验通过（366 天 = 1984 闰年）")

        # 分支 2：zip 里**每月一个 .nc**（平台 as_source 可能的另一种形态）
        multi = os.path.join(tmp, "multi")
        os.makedirs(multi, exist_ok=True)
        for m in range(1, 13):
            ds.sel(valid_time=(ds.valid_time.dt.month == m)).to_netcdf(
                os.path.join(multi, f"m{m:02d}.nc"))
        zp = os.path.join(tmp, "chunk.part")
        with zipfile.ZipFile(zp, "w") as z:
            for f in sorted(os.listdir(multi)):
                z.write(os.path.join(multi, f), f)
        out2 = os.path.join(tmp, "months_zip")
        ncs = unpack_if_zip(zp)
        split_to_months(ncs, target, 1984, list(range(1, 13)), out_dir=out2)
        bad2 = []
        for m in range(1, 13):
            p = os.path.join(out2, f"tmax_eur_1984_{m:02d}.nc")
            if not os.path.exists(p):
                bad2.append(f"{m:02d} 缺文件")
                continue
            ok, why = T.verify_month(p, 1984, m)
            if not ok or why.split(" ")[0] != str(_cal.monthrange(1984, m)[1]):
                bad2.append(f"{m:02d} {why}")
        if bad2:
            print("[FAIL] zip 多文件分支: " + "; ".join(bad2))
            return 1
        print(f"[OK] zip 多文件分支通过（解出 {len(ncs)} 个 .nc，切成 12 个月）")

        # 请求构造自检：一年一请求 / 一月一请求
        r_year = chunk_request(target, 1984, list(range(1, 13)))
        r_mon = chunk_request(target, 1984, [7])
        assert len(r_year["month"]) == 12 and len(r_year["day"]) == 31, r_year
        assert len(r_mon["month"]) == 1 and r_mon["variable"] == [T.VARIABLE]
        assert len(group([1, 2, 3, 4, 5], 2)) == 3
        print("[OK] 请求构造（年/月两档）与分块函数自检通过")
        print("ALL ERA5 FAST SELFTESTS PASSED")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ──────────────────────────────────────────────────────────────────────────
def main(argv=None):
    T.ensure_utf8_console()
    ap = argparse.ArgumentParser(
        description="ERA5 日最高气温 / 地表气压下载（按年分块 + 并发，输出与旧脚本一致）")
    ap.add_argument("--start", type=int, default=DEFAULT_START)
    ap.add_argument("--end", type=int, default=DEFAULT_END)
    ap.add_argument("--only", choices=("both", "tmax", "sp"), default="both")
    ap.add_argument("--jobs", "-j", type=int, default=DEFAULT_JOBS,
                    help=f"并发请求数（默认 {DEFAULT_JOBS}；CDS 对同数据集排队请求数"
                         f"有临时限制，实测 ≥4 会开始拒单，建议 ≤3）")
    ap.add_argument("--chunk-months", "--months-per-request", type=int,
                    default=DEFAULT_MPR, dest="months_per_request",
                    help=f"每个 CDS 请求含几个月：**默认 {DEFAULT_MPR} = 一次申请一年**"
                         f"（排队次数最少、整体最快）；1 = 一次一个月；6 = 半年。"
                         f"平台 size 上限 400 天，最多只能 12 个月")
    ap.add_argument("--no-merge", action="store_true", help="下完不执行合并")
    ap.add_argument("--keep-chunks", action="store_true", help="保留年文件与中间产物")
    ap.add_argument("--log", default=None,
                    help="同时把输出写入该日志文件（UTF-8；不依赖 shell 重定向）")
    ap.add_argument("--dry-run", action="store_true", help="只列计划，不联网、不写盘")
    ap.add_argument("--selftest", action="store_true", help="纯本地自检（不联网）")
    ap.add_argument("--clean-queue", action="store_true", dest="clean_queue",
                    help="清掉本账号在该数据集上仍在排队/运行的任务（换入口重跑前用；"
                         "被遗弃的任务会占 CDS 的排队额度）")
    ap.add_argument("--loop-minutes", type=int, default=0,
                    help="一轮跑完后等这么多分钟再重新规划一轮（0=只跑一轮）。"
                         "拥塞期建议 10：窗口不关，平台一放行就继续补，跑完的自动落盘")
    args = ap.parse_args(argv)

    if args.log:
        d = os.path.dirname(os.path.abspath(args.log))
        os.makedirs(d, exist_ok=True)
        sys.stdout = _Tee(args.log, sys.stdout)
        sys.stderr = sys.stdout
        log(f"日志同步写入: {os.path.abspath(args.log)}")

    ensure_network()

    if args.selftest:
        return selftest()
    if args.clean_queue:
        return clean_queue()

    keys = ["tmax", "sp"] if args.only == "both" else [args.only]

    if args.dry_run:
        print("目标: ERA5 daily-statistics（与旧脚本同一数据集/变量/框）")
        tot_m = tot_r = 0
        for k in keys:
            n_missing, n_req = dry_run(TARGETS[k], args.start, args.end,
                                       args.months_per_request, args.jobs)
            tot_m += n_missing
            tot_r += n_req
        print(f"\n合计: 待下 {tot_m} 个月；按当前设置需 {tot_r} 个 CDS 请求"
              f"（每月一请求 = {tot_m} 个）")
        print("[dry-run] 未联网、未写盘。")
        return 0

    T.check_credentials()
    stop_evt = threading.Event()
    threading.Thread(target=harvest_loop, args=(stop_evt,), daemon=True).start()
    reconcile_pending({k: TARGETS[k] for k in keys})     # 台账 vs 平台实况对账
    failed = {}
    rnd = 0
    while True:
        rnd += 1
        if rnd > 1:
            reconcile_pending({k: TARGETS[k] for k in keys})
        failed = {}
        for k in keys:
            target = TARGETS[k]
            os.makedirs(target.out_dir, exist_ok=True)
            todo, present = build_plan(target, args.start, args.end)
            log(f"{k}: 已就位 {present} 个月，"
                f"待下 {sum(len(v) for v in todo.values())} 个月"
                + (f"（第 {rnd} 轮）" if rnd > 1 else ""))
            bad = run_target(target, todo,
                             Opts(args.months_per_request, args.jobs, args.keep_chunks))
            if bad:
                failed[k] = bad
        if not failed or args.loop_minutes <= 0:
            break
        n_left = sum(len(v) for v in failed.values())
        log(f"本轮仍有 {n_left} 个月没下来（CDS 全局拥塞属正常），"
            f"{args.loop_minutes} 分钟后重新规划一轮；窗口保持打开，收割线程继续收结果")
        for _ in range(max(1, args.loop_minutes * 6)):
            if stop_evt.wait(10):
                break
    stop_evt.set()

    if not args.no_merge:
        for k in keys:
            do_merge(TARGETS[k], args.start, args.end)

    print("\n" + "=" * 74)
    if failed:
        for k, v in failed.items():
            print(f"[未完成] {k}: {len(v)} 个月失败 -> "
                  f"{[f'{y}-{m:02d}' for y, m in v[:12]]}{' ...' if len(v) > 12 else ''}")
        print("原样重跑本脚本即可只补这些月份。")
        return 1
    print("全部完成。下一步：")
    print("  python python\\phase5_humid.py check")
    print("  python python\\phase5_humid.py all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
