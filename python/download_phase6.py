r"""
download_phase6.py — Phase 6（图3/图4/Table 1）的 CESM1-LE 全量下载，**无需参数，点开即可运行**

    python python\download_phase6.py               # 全量 20 成员（ALL + XGHG），约 +80–100 GB
    python python\download_phase6.py --dry-run     # 只打印计划
    python python\download_phase6.py --members 5   # 先下 5 个成员试水

本脚本把下面 3 条官方命令按顺序跑一遍（每步失败即停）：

    1) python python\download_cesm1le.py aws  --members 20   # ALL 集合日值 TREFHT（AWS 匿名 zarr 切片）
    2) python python\download_cesm1le.py gdex --members 20   # SST 日值 + XGHG 全部（NCAR GDEX THREDDS）
    3) python python\download_cesm1le.py trim                # 裁到 2000–2021 欧洲框，落地 proc/

预计：约 80–100 GB、1–2 天（走系统代理实测 2.2 MB/s）。**可断点续传、可分夜跑**：
中断后原样重跑本脚本，已完成的成员/文件段会自动跳过。

磁盘：E: 盘（data\ 指向它）需 ≥120 GB 余量。**不要**走 raw 全时段路径（那需要 ~750 GB）。
跑完用 `python python\phase6_cesm.py prepare --members 20` 生成检测用文件。
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
    ap = argparse.ArgumentParser(description="Phase 6 数据下载（CESM1-LE 20 成员）")
    ap.add_argument("--members", type=int, default=20, help="成员数（默认 20 = 全量）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划")
    a = ap.parse_args(argv)
    m = str(int(a.members))

    print(f"Phase 6 输入下载：CESM1-LE ALL + XGHG，{m} 个成员/组")
    print(f"工作目录：{ROOT}")
    if a.dry_run:
        print("（--dry-run：只打印命令，不联网）")

    steps = [
        ("1/3 ALL 日值 TREFHT（AWS zarr 切片）", ["download_cesm1le.py", "aws", "--members", m]),
        ("2/3 SST 日值 + XGHG（GDEX THREDDS）", ["download_cesm1le.py", "gdex", "--members", m]),
        ("3/3 裁剪到 2000–2021 欧洲框（trim）", ["download_cesm1le.py", "trim"]),
    ]
    t0 = time.time()
    for name, args in steps:
        if not run(name, args, a.dry_run):
            print("\n⚠️ 上一步失败，已停止。修好网络后**原样重跑本脚本**即可续传"
                  "（已完成的成员/段会自动跳过）。")
            return 1

    print(f"\n{'=' * 74}\n全部完成，总用时 {time.time() - t0:.0f} s\n{'=' * 74}")
    if not a.dry_run:
        print("下一步：python python\\phase6_cesm.py pairs")
        print("        python python\\phase6_cesm.py prepare --members %s" % m)
        print("        python python\\phase6_cesm.py detect --members %s --baseline xghg --loo --tag _v4" % m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
