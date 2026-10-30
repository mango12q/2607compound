#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""续传补洞：把 CDS 上**已经跑完、但本机没收走**的任务结果收下来。

为什么需要它
------------
CDS 的任务在**服务端**排队/计算，关窗口、关电脑、断网都**不会取消**它们。
所以"下午关机时留在队列里的年请求"，晚上很可能已经是 `successful` 了。
但 `download_era5_fast.py` 只会按"本机缺哪个月"**重新提交**请求，
**不会**去认领这些旧任务 —— 于是它们白占过排队额度，结果也没人取。
本脚本补这个洞：列出最近任务 → 下载结果 → 按年切成月文件 → 过 verify_month。

顺序（晚上开机后）
------------------
    python python\\adopt_cds_jobs.py --list     # 先看有什么可收
    python python\\adopt_cds_jobs.py            # 收下来（默认最多 5 个）
    run_phase5_fast_download.bat                # 再按老样子续传，缺月自然少一批

已收过的 jobID 记在 `logs\\cds_adopted_jobs.json`，重跑不会重复下载。
**不要**在下这个之前跑 `download_era5_fast.py --clean-queue` —— 那会删掉在队任务。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

BASE = os.path.dirname(HERE)
LOGS = os.path.join(BASE, "logs")
STATE = os.path.join(LOGS, "cds_adopted_jobs.json")
TMPDIR = os.path.join(BASE, "logs", "_adopt")

import download_era5_fast as D  # noqa: E402  （复用 creds / unpack_if_zip / split_to_months）


def say(msg):
    print(msg, flush=True)


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"adopted": {}, "skipped": {}}


def save_state(st):
    os.makedirs(LOGS, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def list_jobs(url, key, limit=200, status=None):
    """列任务。

    ⚠️ 2026-10-16 查明：平台 `GET /retrieve/v1/jobs` **默认只回 10 条**、按 created 倒序，
    而这两天被限流拒掉的记录已有 160+ 条 ⇒ 旧代码写死 `limit=50` 会把真正成功的任务挤出
    视野（实测 successful 共 14 条，而"最近 50 条"里只看得到 10 条）。现在：
      · 条数上限提到 200；
      · `status` 把过滤交给平台（可传字符串或列表；平台支持重复 query 参数，但**不支持逗号**，
        逗号会 422）。例如 status="successful" 只要成功任务、status=("accepted","running") 只要在队的。
    """
    import requests
    H = {"PRIVATE-TOKEN": key}
    params = [("limit", limit)]
    if status:
        if isinstance(status, str):
            status = [status]
        params += [("status", s) for s in status]
    r = requests.get(f"{url}/retrieve/v1/jobs", headers=H, params=params, timeout=45)
    r.raise_for_status()
    return r.json().get("jobs", [])


def job_result(url, key, job):
    import requests
    H = {"PRIVATE-TOKEN": key}
    r = requests.get(f"{url}/retrieve/v1/jobs/{job['jobID']}/results",
                     headers=H, timeout=45)
    if r.status_code != 200:
        txt = ""
        try:
            txt = r.text
        except Exception:
            pass
        if "expired" in txt.lower():
            return None, "expired"
        return None, f"HTTP {r.status_code}"
    try:
        return (r.json().get("asset") or {}).get("value") or {}, None
    except Exception:
        return None, "bad-json"


def fetch(href, dest, size, tries=5):
    """带 Range 断点续传的下载（CDS 对象存储经常中途断，cdsapi 也是这么干的）。"""
    import requests
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    got = os.path.getsize(dest) if os.path.exists(dest) else 0
    last_say = got
    for i in range(1, tries + 1):
        if size and got >= size:
            break
        headers = {"Range": f"bytes={got}-"} if got else {}
        try:
            with requests.get(href, headers=headers, stream=True, timeout=90) as r:
                if r.status_code not in (200, 206):
                    say(f"    HTTP {r.status_code}（第 {i}/{tries} 次）")
                    time.sleep(15)
                    continue
                with open(dest, "ab" if got else "wb") as f:
                    for chunk in r.iter_content(1024 * 256):
                        if not chunk:
                            continue
                        f.write(chunk)
                        got += len(chunk)
                        if size and got - last_say >= 2 * 1024 * 1024:
                            last_say = got
                            say(f"    {got / 1048576:.1f}/{size / 1048576:.1f} MB "
                                f"({100.0 * got / size:.0f}%)")
        except Exception as e:
            say(f"    {type(e).__name__}: {e}（第 {i}/{tries} 次，{got} B 后断，续传）")
            time.sleep(15)
        if size:
            say(f"    {got}/{size} B ({100.0 * got / size:.0f}%)")
    return got


def pick_target_and_years(nc_paths):
    """从文件内容判断这是 tmax 还是 sp，以及覆盖哪些年份（不依赖任务元数据）。"""
    import numpy as np
    import xarray as xr

    tgt_kind, years = None, set()
    for p in nc_paths:
        try:
            ds = xr.open_dataset(p)
        except Exception:
            continue
        try:
            names = {str(v).lower() for v in ds.data_vars}
            if any(n.startswith("mx2t") or "maximum_2m_temperature" in n for n in names):
                tgt_kind = tgt_kind or "tmax"
            elif any(n == "sp" or "surface_pressure" in n for n in names):
                tgt_kind = tgt_kind or "sp"
            tn = "valid_time" if "valid_time" in ds.dims else "time"
            if tn in ds.coords or tn in ds:
                years |= {int(y) for y in np.unique(ds[tn].dt.year.values)}
        finally:
            ds.close()
    return tgt_kind, sorted(years)


def live_jobs(url, key):
    """还在 CDS 队列里的任务（accepted / running）。"""
    return [j for j in list_jobs(url, key, status=("accepted", "running"))
            if j.get("status") in ("accepted", "running")]


def wait_for_live(url, key, poll_sec=60, max_wait_min=0.0):
    """等在队任务出结果（每轮一行心跳）。max_wait_min<=0 = 一直等。"""
    from datetime import datetime, timezone
    t0 = time.time()
    while True:
        live = live_jobs(url, key)
        el = (time.time() - t0) / 60.0
        if not live:
            say(f"⏳ 在队任务已清空（等了 {el:.1f} 分钟）⇒ 接着收割。")
            return
        bits = []
        for j in live:
            age = "?"
            try:
                t = datetime.fromisoformat(j["created"]).replace(
                    tzinfo=timezone.utc).timestamp()
                age = f"{(time.time() - t) / 60:.0f}min"
            except Exception:
                pass
            bits.append(f"{j['jobID'][:8]}({j.get('status')},{age})")
        say(f"⏳ 仍在 CDS 排队 {len(live)} 个，已等 {el:.1f} 分钟：" + " ".join(bits))
        if max_wait_min and el >= max_wait_min:
            say(f"⚠ 到 --max-wait-min {max_wait_min:.0f} 分钟上限，不再等。"
                f"这些年份下次运行 adopt 时再收（引擎不会重复排它们）。")
            return
        time.sleep(max(5, int(poll_sec)))


def main(argv=None):
    try:                                  # 中文输出别乱码
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="认领 CDS 上已完成但未收走的任务结果")
    ap.add_argument("--list", action="store_true", help="只列出可收的任务，不下载")
    ap.add_argument("--max-jobs", type=int, default=5, help="本次最多收几个（默认 5）")
    ap.add_argument("--since-hours", type=float, default=72.0,
                    help="只看最近 N 小时内创建的任务（默认 72）")
    ap.add_argument("--all", action="store_true",
                    help="忽略 since-hours，看列表里的全部历史任务")
    ap.add_argument("--wait-live", action="store_true",
                    help="先等在队任务出结果再收割（重启前把队列清干净，避免重复提交）")
    ap.add_argument("--poll-sec", type=int, default=60, help="--wait-live 轮询间隔秒（默认 60）")
    ap.add_argument("--max-wait-min", type=float, default=0.0,
                    help="--wait-live 最多等多少分钟（0 = 一直等）")
    args = ap.parse_args(argv)

    c = D.creds()
    say(f"CDS: {c['url']}（凭据来自环境变量或 ~/.cdsapirc）")
    jobs = list_jobs(c["url"], c["key"], status="successful")
    say(f"任务列表: successful {len(jobs)} 条（已按状态过滤；最多 200 条。"
        f"注意这不是平台任务总数，被拒的 160+ 条不在此列）")

    if args.wait_live:
        wait_for_live(c["url"], c["key"], args.poll_sec, args.max_wait_min)
        jobs = list_jobs(c["url"], c["key"], status="successful")

    st = load_state()
    done = st.get("adopted", {})
    expired_done = st.get("expired", {})
    now = time.time()
    cands = []
    for j in jobs:
        if j.get("status") != "successful":
            continue
        if j["jobID"] in done or j["jobID"] in expired_done:
            continue
        if not args.all and args.since_hours is not None:
            from datetime import datetime, timezone
            try:
                # created 形如 2026-10-14T02:08:24.187427（UTC）
                t = datetime.fromisoformat(j["created"]).replace(
                    tzinfo=timezone.utc).timestamp()
            except Exception:
                t = None
            if t is not None and (now - t) > args.since_hours * 3600:
                continue
        cands.append(j)

    if not cands:
        say("没有可收的任务（要么都收过了，要么还没跑完）。"
            "若确认有旧任务没收，可加 --all 放宽时间范围。")
        return 0

    say(f"可收 {len(cands)} 个：")
    for j in cands:
        say(f"  {j['jobID'][:8]}  created={j.get('created')}")

    if args.list:
        say("（--list：只看不下载）")
        return 0

    os.makedirs(TMPDIR, exist_ok=True)
    ok = skip = fail = 0
    for j in cands[:args.max_jobs]:
        jid = j["jobID"]
        asset, reason = job_result(c["url"], c["key"], j)
        if reason == "expired":
            say(f"[{jid[:8]}] 平台已删除结果（results expired）⇒ 这几个月只能重新申请，记账跳过")
            st.setdefault("expired", {})[jid] = {"seen_at": time.strftime("%F %T")}
            save_state(st)
            skip += 1
            continue
        if not asset:
            say(f"[{jid[:8]}] 取结果链接失败（{reason}），跳过")
            fail += 1
            continue
        href = asset.get("href")
        size = asset.get("file:size") or asset.get("contentLength") or asset.get("content_length")
        if not href:
            say(f"[{jid[:8]}] 结果里没有 href，跳过")
            fail += 1
            continue
        say(f"[{jid[:8]}] {size} B  {asset.get('type')}")
        tmp = os.path.join(TMPDIR, f"adopt_{jid[:8]}.bin")
        got = fetch(href, tmp, size)
        if size and got < size:
            say(f"[{jid[:8]}] 只下到 {got}/{size} B，留给下次再试")
            fail += 1
            continue
        try:
            ncs = D.unpack_if_zip(tmp)
            kind, years = pick_target_and_years(ncs)
            if kind is None or not years:
                say(f"[{jid[:8]}] 认不出变量/年份，原文件留在 {TMPDIR}")
                fail += 1
                continue
            tgt = D.TARGETS[kind]
            wrote = 0
            for y in years:
                miss = [m for m in range(1, 13) if not os.path.exists(tgt.month_path(y, m))]
                if not miss:
                    continue
                say(f"[{jid[:8]}] {kind} {y}: 缺 {miss} → 切月文件")
                D.split_to_months(ncs, tgt, y, miss)
                wrote += len(miss)
                if all(os.path.exists(tgt.month_path(y, m)) for m in range(1, 13)):
                    # 该年 12 个月已齐 ⇒ 从"在队年份台账"注销，别再让引擎当它是排队中而跳过
                    D.unmark_pending(kind, y)
            done[jid] = {"kind": kind, "years": years, "adopted_at": time.strftime("%F %T")}
            st["adopted"] = done
            save_state(st)
            if wrote:
                ok += 1
                say(f"[{jid[:8]}] 完成（补了 {wrote} 个月）")
            else:
                skip += 1
                say(f"[{jid[:8]}] 完成（这些月份本机已全有，没写文件）")
        except Exception as e:
            fail += 1
            say(f"[{jid[:8]}] 处理失败: {type(e).__name__}: {e}")
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass

    say(f"合计：收下 {ok} 个、无新月份 {skip} 个、失败 {fail} 个；"
        f"已收记录 {STATE}")
    say("接着跑 run_phase5_fast_download.bat 即可（缺月会自动少一批）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
