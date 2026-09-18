# -*- coding: utf-8 -*-
"""
run_p0_download.py — 一键 P0 下载（双击运行）

内容: CESM1-LE 归因数据 (图7用), 成员 001-003, ALL + XGHG, 2000-2021
  [1/3] ALL 日值 TREFHT —— AWS zarr 切片           (~30 分钟)
  [2/3] SST + XGHG 整文件 —— fileServer 走代理      (~11 小时)
  [3/3] 整文件裁剪到 2000-2021                      (~10 分钟)

输出: E:\\2607compound\\data\\CESM1-LE\\proc  (约 90 GB)
随时可以关窗口, 重新双击会自动跳过已完成部分（断点续传）。
"""
import os
import subprocess
import sys
import time

BASE = r"D:\2607compound"
TOOL = os.path.join(BASE, "python", "download_cesm1le.py")
URLS = os.path.join(BASE, "results", "tables", "cesm1le_p0_urls.csv")
PROC = os.path.join(BASE, "data", "CESM1-LE", "proc")

STEPS = [
    ("[1/3] AWS zarr 切片: ALL 日值 TREFHT (~30 分钟)",
     [TOOL, "aws", "--members", "3"]),
    ("[2/3] fileServer 整文件: SST + XGHG, 走代理 (~11 小时)",
     [TOOL, "download", "--urls", URLS]),
    ("[3/3] 整文件裁剪到 2000-2021 (~10 分钟)",
     [TOOL, "trim"]),
]


def list_proc():
    if not os.path.isdir(PROC):
        return
    fs = sorted(f for f in os.listdir(PROC) if f.endswith(".nc"))
    print(f"\nproc 目录现有 {len(fs)} 个成品文件:")
    for f in fs:
        p = os.path.join(PROC, f)
        print(f"  {f}  ({os.path.getsize(p)/1e6:.0f} MB)")


def ensure_urls():
    """下载清单被 gitignore, 缺失时自动重建: manifest 实爬 → 剔除 ALL-atm(AWS 覆盖)。"""
    if os.path.exists(URLS):
        return
    print(f"清单缺失, 自动重建: {URLS}")
    rc = subprocess.run([sys.executable, TOOL, "manifest", "--members", "3"]).returncode
    if rc != 0:
        raise SystemExit("manifest 生成失败, 无法继续")
    import pandas as pd
    src = os.path.join(BASE, "results", "tables", "cesm1le_download_manifest.csv")
    df = pd.read_csv(src)
    keep = ~((df.experiment == "ALL") & (df.component == "atm"))
    df[keep].to_csv(URLS, index=False, encoding="utf-8-sig")
    print(f"已重建: {int(keep.sum())} 个整文件 (ALL-atm {int((~keep).sum())} 个由 AWS 覆盖)")


def main():
    os.chdir(BASE)
    ensure_urls()
    print("=" * 62)
    print("CESM1-LE P0 下载  (成员 001-003, ALL + XGHG, 2000-2021)")
    print(f"输出: {PROC}")
    print("随时可以关窗口; 重新双击会跳过已完成部分 (断点续传)")
    print("=" * 62)

    for label, cmd in STEPS:
        print(f"\n>>> {label}", flush=True)
        rc = subprocess.run([sys.executable] + cmd).returncode
        if rc != 0:
            print(f"\n!!! 该步骤失败 (exit {rc})")
            print("!!! 窗口保持打开; 直接重新双击本脚本即可从断点继续")
            return rc

    print("\n" + "=" * 62)
    print("全部完成 ✓  把下面文件清单发给助手, 开始写 Phase 6 管线:")
    list_proc()
    print("=" * 62)
    return 0


if __name__ == "__main__":
    try:
        _rc = main()
    except Exception as _e:  # 双击运行时异常也不能让窗口闪退
        print(f"\n发生异常: {type(_e).__name__}: {_e}")
        _rc = 1
    try:
        input("\n按回车键关闭窗口...")
    except Exception:
        pass
    sys.exit(_rc)
