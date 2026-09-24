r"""
run_phases.py — **全流程一键入口**（Phase 0 → Phase 7）：数据检查 → 处理 → 全部论文图

设计原则
--------
* 每一步都调用**文档里写明的同一条命令**（`subprocess`），不复制逻辑、不隐藏参数；
* **数据缺什么就跳过什么**并明确告知缺哪一项，绝不静默产出半成品；
* 单步失败不中断整体（记入汇总），最后打印一张"完成/跳过/失败"总表；
* `--dry-run` 只打印将要执行的命令，不真正跑。

用法
----
    python python\run_phases.py                 # 能跑的都跑（缺数据自动跳过）
    python python\run_phases.py --dry-run       # 只看计划
    python python\run_phases.py --phases 4      # 只跑 Phase 4（观测出图）
    python python\run_phases.py --tag _v4       # Phase 6 用的产物后缀
    python python\run_phases.py --skip-selftest # 跳过前置自检

阶段与命令对照（与 `待办.md` / `docs/阶段计划.md` 完全一致）
----------------------------------------------------------
    Phase 0-3  python python\run_all.py
    Phase 4    python python\figures.py
               python python\fig_jkl_mhw_envelope.py
               python python\figS1_annual_maps.py
    Phase 5    python python\coastal_buffer.py
               python python\phase5_humid.py all
               python python\fig5_sst_trend.py
               python python\fig6_wbt.py
    Phase 6    python python\phase6_cesm.py pairs|prepare|detect|compound|attrib|gev
               python python\fig3_attribution.py --tag …
               python python\fig4_return_period.py --tag …
               python python\table1_attribution.py --tag …
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)

import config as C                                    # noqa: E402
from load_data import check_phase5_inputs             # noqa: E402

PY = sys.executable
RESULTS = []


# ──────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────
def _exists(*paths) -> bool:
    return all(os.path.exists(p) for p in paths)


def _cesm_members(tag: str = "_v4") -> int:
    """
    可用的 CESM 成员数 = max(prepare 产物数, proc/ 源文件覆盖的成员数)。

    ⚠️ 早先版本只看 `proc/{m}_T2m.nc`，而 prepare 的产物其实落在
    `results/intermediate/cesm/{EXP}_{m}_T2m.nc`、源文件又是
    `TREFHT_all_001_2000-2021_europe.nc` 这种名字 ⇒ 会把"已有 3 成员"误判成"没有数据"。
    """
    import glob
    prepared = len(glob.glob(os.path.join(C.INTERMEDIATE_DIR, "cesm", "ALL_*_T2m.nc")))
    src = set()
    for pat in ("TREFHT_all_*.nc", "trefht_all_*.nc", "*ALL*TREFHT*.nc"):
        for f in glob.glob(os.path.join(C.CESM_PROC_DIR, pat)):
            for tok in os.path.basename(f).replace("-", "_").split("_"):
                if tok.isdigit() and len(tok) == 3:
                    src.add(tok)
    return max(prepared, len(src))


def run(step: str, cmd: list, dry: bool = False, optional: bool = False) -> bool:
    """执行一条命令；返回是否成功。`optional=True` 时失败只记录不报错。"""
    line = " ".join(cmd)
    print(f"\n{'=' * 74}\n[{step}] {line}\n{'=' * 74}")
    if dry:
        RESULTS.append((step, "DRY", ""))
        return True
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=_ROOT)
    except KeyboardInterrupt:
        RESULTS.append((step, "中断", ""))
        raise
    ok = (p.returncode == 0)
    dt = time.time() - t0
    RESULTS.append((step, "完成" if ok else ("失败(可跳过)" if optional else "失败"),
                    f"{dt:.0f} s"))
    if not ok:
        print(f"[{step}] 退出码 {p.returncode}（{dt:.0f} s）")
    return ok


def skip(step: str, why: str):
    print(f"\n[跳过] {step} —— {why}")
    RESULTS.append((step, "跳过", why))


# ──────────────────────────────────────────────
# 各阶段
# ──────────────────────────────────────────────
def phase_0_3(args):
    if not _exists(C.OISST_MERGED_FILE, C.EOBS_MERGED_FILE):
        skip("Phase 0-3", f"缺 {C.OISST_MERGED_FILE} 或 {C.EOBS_MERGED_FILE}")
        return
    run("Phase 0-3 观测链路", [PY, os.path.join(_HERE, "run_all.py")], args.dry_run)


def phase_4(args):
    if not _exists(os.path.join(C.INTERMEDIATE_DIR, "annual_compound_days.nc")):
        skip("Phase 4 出图", "缺 results/intermediate/annual_compound_days.nc（先跑 Phase 0-3）")
        return
    run("Phase 4 图1/图2/S1(j-l)",
        [PY, os.path.join(_HERE, "figures.py")], args.dry_run, optional=True)
    run("Phase 4 图S2",
        [PY, os.path.join(_HERE, "fig_jkl_mhw_envelope.py")], args.dry_run, optional=True)
    run("Phase 4 论文版 S1（年际组图）",
        [PY, os.path.join(_HERE, "figS1_annual_maps.py")], args.dry_run, optional=True)


def phase_5(args):
    rep = check_phase5_inputs(verbose=True)
    need = [k for k in ("ERA5 tmax（图6 WBT 分子）", "ERA5 d2m（WBT/SH）",
                        "ERA5 sp 0.25°（WBT 气压）", "OISST（图5a）", "E-OBS（图6 陆地）")
            if k in rep and not rep[k]["ok"]]
    if need:
        skip("Phase 5", "缺 " + "、".join(need) + "（先跑 run_phase5_downloads.bat）")
        return
    run("Phase 5 海岸缓冲掩码", [PY, os.path.join(_HERE, "coastal_buffer.py")],
        args.dry_run, optional=True)
    run("Phase 5 处理链路（WBT/SH + 图5 趋势 + 图6 统计）",
        [PY, os.path.join(_HERE, "phase5_humid.py"), "all"], args.dry_run)
    if rep.get("OAFlux 蒸发（图5b）", {}).get("ok") is False:
        print("  [提示] OAFlux 未就位 ⇒ 图5b 面板会留空（脚本会明确标注）")
    run("Phase 5 图5", [PY, os.path.join(_HERE, "fig5_sst_trend.py")],
        args.dry_run, optional=True)
    run("Phase 5 图6", [PY, os.path.join(_HERE, "fig6_wbt.py")],
        args.dry_run, optional=True)


def phase_6(args):
    tag = args.tag
    n_cesm = _cesm_members(tag)
    if n_cesm == 0:
        skip("Phase 6", "proc/ 下没有 prepare 好的 CESM 成员（先跑 run_phase6_download.bat）")
        return
    if n_cesm < 20:
        print(f"  [提示] 只发现 {n_cesm} 个 CESM 成员 —— 结果仅用于验证流程，"
              f"不能作为归因结论（论文口径需要 20 成员/组）")
    P = [PY, os.path.join(_HERE, "phase6_cesm.py")]
    run("Phase 6 pairs", P + ["pairs"], args.dry_run, optional=True)
    run("Phase 6 prepare", P + ["prepare", "--members", str(n_cesm)],
        args.dry_run, optional=True)
    run("Phase 6 detect",
        P + ["detect", "--members", str(n_cesm), "--baseline", "xghg", "--loo",
             "--tag", tag], args.dry_run, optional=True)
    run("Phase 6 compound",
        P + ["compound", "--members", str(n_cesm), "--tag", tag,
             "--compound-def", C.COMPOUND_DEF], args.dry_run, optional=True)
    run("Phase 6 attrib",
        P + ["attrib", "--members", str(n_cesm), "--tag", tag,
             "--compound-def", C.COMPOUND_DEF], args.dry_run, optional=True)
    run("Phase 6 gev", P + ["gev", "--members", str(n_cesm), "--tag", tag],
        args.dry_run, optional=True)
    run("Phase 6 图3", [PY, os.path.join(_HERE, "fig3_attribution.py"), "--tag", tag],
        args.dry_run, optional=True)
    run("Phase 6 图4", [PY, os.path.join(_HERE, "fig4_return_period.py"), "--tag", tag],
        args.dry_run, optional=True)
    run("Phase 6 Table 1", [PY, os.path.join(_HERE, "table1_attribution.py"), "--tag", tag],
        args.dry_run, optional=True)


def phase_selftest(args):
    if args.skip_selftest:
        skip("前置自检", "--skip-selftest")
        return
    ok = True
    for name, path in (("calc_wbt", os.path.join(_HERE, "calc_wbt.py")),
                       ("gev_return_period", os.path.join(_HERE, "gev_return_period.py")),
                       ("phase6_selftest", os.path.join(_ROOT, "results", "phase6_selftest.py")),
                       ("phase5_selftest", os.path.join(_ROOT, "results", "phase5_selftest.py"))):
        ok &= run(f"自检 {name}", [PY, path], args.dry_run, optional=True)
    return ok


def phase_7(args):
    """Phase 7：汇总 —— 只做核对与提示，不改数据。"""
    print(f"\n{'=' * 74}\n[Phase 7] 产物核对\n{'=' * 74}")
    figs = sorted(f for f in os.listdir(C.FIGURES_DIR)
                  if f.endswith((".png", ".pdf"))) if os.path.isdir(C.FIGURES_DIR) else []
    print(f"results/figures 下共 {len(figs)} 个文件：")
    for f in figs:
        print(f"  - {f}")
    print("\n论文图画清单核对（详见 docs/阶段计划.md §0）：")
    want = {"图1": "fig1_compound_spatial", "图2": "fig2_chr", "图3": "fig3_attribution",
            "图4": "fig4_return_period", "图5": "fig5_sst_trend", "图6": "fig6_wbt",
            "论文版S1": "figS1_paper_annual_maps", "Table1": None}
    for k, stem in want.items():
        if stem is None:
            p = os.path.join(C.TABLES_DIR, "table1.csv")
        else:
            p = next((os.path.join(C.FIGURES_DIR, f) for f in figs
                      if f.startswith(stem) and not f.endswith("_demo.pdf")
                      and "_synthetic" not in f and not f.endswith("_demo.png")), None)
        print(f"  [{'有' if p and os.path.exists(p) else '缺'}] {k}")
    RESULTS.append(("Phase 7 核对", "完成", f"{len(figs)} 个图文件"))


# ──────────────────────────────────────────────
def main(argv=None):
    p = argparse.ArgumentParser(description="全流程一键入口（Phase 0→7）",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("--phases", nargs="+", default=["0", "4", "5", "6", "7"],
                   choices=["0", "4", "5", "6", "7"],
                   help="要跑的阶段（0=Phase0-3；默认 0 4 5 6 7）")
    p.add_argument("--tag", default="_v4", help="Phase 6 产物后缀（默认 _v4）")
    p.add_argument("--dry-run", action="store_true", help="只打印将执行的命令")
    p.add_argument("--skip-selftest", action="store_true")
    args = p.parse_args(argv)

    t0 = time.time()
    print(f"工作区：{_ROOT}")
    print(f"阶段：{' '.join(args.phases)}　tag={args.tag}　"
          f"{'DRY-RUN' if args.dry_run else '正式执行'}")
    phase_selftest(args)
    for ph in args.phases:
        {"0": phase_0_3, "4": phase_4, "5": phase_5,
         "6": lambda a: phase_6(a), "7": phase_7}[ph](args)

    print(f"\n{'=' * 74}\n汇总（用时 {time.time() - t0:.0f} s）\n{'=' * 74}")
    width = max(len(s) for s, _, _ in RESULTS) if RESULTS else 10
    for step, status, extra in RESULTS:
        print(f"  {step:<{width}}  {status:<10} {extra}")
    bad = [s for s, st, _ in RESULTS if st == "失败"]
    if bad:
        print(f"\n⚠️ 有 {len(bad)} 步失败：{bad}")
        print("   （标了“失败(可跳过)”的属可选环节，不影响主结论）")
        return 1
    print("\n全部可执行的步骤已完成。缺数据的阶段见上面的 [跳过] 行与其原因。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
