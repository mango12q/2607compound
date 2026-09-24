r"""
download_phase5.py — Phase 5（图5/图6）的三项数据下载，**无需参数，点开即可运行**

    python python\download_phase5.py              # 正式下载（断点续传，中断后原样重跑）
    python python\download_phase5.py --dry-run    # 只打印计划，不联网、不写盘
    python python\download_phase5.py --skip-oaflux

本脚本只是把下面这 5 条官方命令按顺序跑一遍（每步失败即停并给出原因）：

    1) python python\download_era5_tmax.py           # ERA5 日最高气温 0.25°（CDS）
    2) python python\download_era5_tmax.py --merge   # 合并为 ERA5_tmax_1984_2023_daily.nc
    3) python python\download_era5_sp025.py          # ERA5 地表气压 0.25°（CDS，框 [70,-16,28,44]）
    4) python python\download_era5_sp025.py --merge  # 合并为 ERA5_sp_1984_2023_daily.nc
    5) python python\download_oaflux_evap.py         # OAFlux 月蒸发（WHOI 多镜像自动降级）

预计：tmax 479 个月 + sp 480 个月 ≈ 3 GB，几小时（取决于 CDS 队列）。
中断后**原样重跑**即可：已完成的月份会自动跳过。

跑完用 `python python\phase5_humid.py check` 确认三项都变成 [OK]。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def run(step: str, args: list, dry: bool) -> bool:
    cmd = [PY, os.path.join(HERE, args[0])] + args[1:]
    print(f"\n{'=' * 74}\n[{step}] {' '.join(cmd)}\n{'=' * 74}", flush=True)
    if dry:
        return True
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT)
    ok = (p.returncode == 0)
    print(f"[{step}] {'完成' if ok else f'失败（退出码 {p.returncode}）'}"
          f"  用时 {time.time() - t0:.0f} s", flush=True)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="Phase 5 数据下载（ERA5 tmax + sp0.25° + OAFlux）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划")
    ap.add_argument("--skip-oaflux", action="store_true", help="跳过 OAFlux（图5b 会留空）")
    a = ap.parse_args(argv)

    print("Phase 5 输入下载：ERA5 tmax / ERA5 sp 0.25° / OAFlux 蒸发")
    print(f"工作目录：{ROOT}")
    if a.dry_run:
        print("（--dry-run：只打印命令，不联网）")

    steps = [
        ("1/5 ERA5 tmax 月度下载", ["download_era5_tmax.py"]),
        ("2/5 ERA5 tmax 合并", ["download_era5_tmax.py", "--merge"]),
        ("3/5 ERA5 sp 0.25° 月度下载", ["download_era5_sp025.py"]),
        ("4/5 ERA5 sp 0.25° 合并", ["download_era5_sp025.py", "--merge"]),
    ]
    if not a.skip_oaflux:
        steps.append(("5/5 OAFlux 蒸发下载", ["download_oaflux_evap.py"]))

    t0 = time.time()
    for name, args in steps:
        if not run(name, args, a.dry_run):
            print("\n⚠️ 上一步失败，已停止。修好网络/CDS 条款后**原样重跑本脚本**即可续传。")
            return 1

    print(f"\n{'=' * 74}\n全部完成，总用时 {time.time() - t0:.0f} s\n{'=' * 74}")
    if not a.dry_run:
        print("下一步：python python\\phase5_humid.py check")
        print("全 OK 后跑：python python\\phase5_humid.py all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
