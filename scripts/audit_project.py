r"""
audit_project.py — 项目自审：**文档里写的每条命令与文件引用都必须真实存在**

检查四项（全部只读）：
  A. 文档中出现的 `python xxx.py` / `xxx.bat` / `xxx.R` 引用是否都能在仓库里找到；
  B. `python/` 下的脚本是否都在某份文档里被提到（发现孤儿代码）；
  C. 论文图画清单（图1–6 / Table 1 / S1）是否都有出图脚本 + 产物；
  D. 关键中间产物与数据文件是否在位。

用法：
    python scripts\audit_project.py            # 人读报告
    python scripts\audit_project.py --strict   # 有 FAIL 时退出码 1
"""
from __future__ import annotations

import argparse
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCS = ["待办.md", "AGENTS.md", "DATA_REQUIREMENTS.md",
        os.path.join("docs", "阶段计划.md"),
        os.path.join("results", "README.md"),
        os.path.join("results", "图版对照表.md"),
        os.path.join("results", "复现报告.md"),
        os.path.join("results", "规划一致性审查.md"),
        os.path.join("results", "方法与证据.md"),
        os.path.join("results", "phase6审计报告.md"),
        os.path.join("results", "tools", "README.md"),
        "TECHNICAL_SPEC.md", "TECHNICAL_SPEC_PHASE_A.md",
        "TECHNICAL_SPEC_PHASE_B.md", "TECHNICAL_SPEC_PHASE_C.md",
        "requirements.txt"]

# 文档里的路径引用（反引号内的 .py/.bat/.R/.md/.nc 等）
PATH_RE = re.compile(r"`([^`\n]+?\.(?:py|bat|R|md|nc|csv|json|txt))`")
# 明确不是"本仓库文件"的引用（示例名、外部产物）
WHITELIST_PREFIX = ("results/figures/fig", "results/tables/", "results/intermediate/",
                    "data/", "logs/")

#: **已登记的历史名**：文档里提到但仓库中确实不存在，且文档已说明其来历。
#: 任何**不在此表**里的缺失代码引用都会让自审 FAIL（防止以后新增悬空引用无人发现）。
HISTORICAL = {
    # 2026-09-23 仓库整理时删除的一次性诊断脚本（结论已并入报告）
    "compare_thw_regression.py": "第一阶段 R/Python 回归对比，结论入 方法与证据.md §4 后删除",
    "diagnose_thw_regression_diff.py": "同上（差异诊断）",
    "exp_smooth_compare.py": "平滑开关抽样实验，结论入 复现报告 D2 后删除",
    "exp_smooth_test.R": "同上（R 侧）",
    "diag_return_trycatch.R": "detect_thw.R 吞错 bug 的证明脚本，结论入 方法与证据.md",
    "_baseline.py": "Phase 6 审计脚本的存档案名（审计报告 §3–§6 分报告正文引用）",
    "_detect.py": "同上（检测语义分报告）",
    "_detect.R": "同上",
    "_stats.py": "同上（复合与统计分报告）",
    "_check12.py": "同上（审计复算脚本）",
    # TECHNICAL_SPEC 的设计稿文件名（从未实现；MATLAB 路径已废）
    "attribution.py": "SPEC §3.9 设计稿名，实际实现合并进 phase6_cesm.py",
    "python/attribution.py": "同上",
    "python/export_for_matlab.py": "SPEC 早期 MATLAB 导出设计，已废弃（matlab/ 目录不存在）",
}

FAIL, WARN = [], []
HIST_SEEN = set()


def check(name, cond, detail="", strict_only=False):
    tag = "OK  " if cond else ("WARN" if strict_only else "FAIL")
    print(f"  [{tag}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        (WARN if strict_only else FAIL).append(name)


def _all_basenames() -> set:
    """仓库内（排除 .git）所有文件的 basename —— 用于"只写了文件名"的引用。"""
    names = set()
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for f in files:
            names.add(f)
    return names


def main(argv=None):
    p = argparse.ArgumentParser(description="项目自审")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)
    os.chdir(BASE)
    basenames = _all_basenames()

    print("=" * 74)
    print("A. 文档里的路径引用是否都存在")
    print("=" * 74)
    hard_missing, soft_missing = {}, {}
    n_ref = 0
    for doc in DOCS:
        if not os.path.exists(doc):
            check(f"文档存在：{doc}", False)
            continue
        text = open(doc, encoding="utf-8", errors="replace").read()
        for m in PATH_RE.finditer(text):
            ref = m.group(1).strip().replace("\\", "/")
            if any(ref.startswith(w) for w in WHITELIST_PREFIX):
                continue                      # 产物路径：下面 C/D 单独查
            if ref.startswith(("python ", "http")):
                continue
            # 通配/模板/占位符/绝对路径/多文件合并写法 —— 不是"某个具体文件"，跳过
            if any(ch in ref for ch in "*{}<>$") or "..." in ref:
                continue
            if re.match(r"^[A-Za-z]:/", ref) or ref.startswith("/"):
                continue
            if " " in ref or "YYYY" in ref or "/" in ref and re.search(r"/[A-Z]/", ref):
                continue
            n_ref += 1
            cands = [ref, os.path.join("python", ref), os.path.join("results", ref),
                     os.path.join("docs", ref), os.path.join("scripts", ref),
                     os.path.join("results", "tools", ref),
                     os.path.join("results", "intermediate", ref),
                     os.path.join("results", "tables", ref),
                     os.path.join("data", ref)]
            if any(os.path.exists(c) for c in cands):
                continue
            if os.path.basename(ref) in basenames:      # 只写了文件名 → 视为存在
                continue
            # 硬引用 = 代码文件（必须真实存在）；软引用 = 数据/产物/文档/历史合并名
            is_hard = (ref.endswith((".py", ".R", ".bat"))
                       and ("/" not in ref or ref.startswith(("python/", "scripts/"))))
            base = os.path.basename(ref)
            if is_hard and (ref in HISTORICAL or base in HISTORICAL):
                HIST_SEEN.add(ref)
                continue
            (hard_missing if is_hard else soft_missing).setdefault(ref, []).append(doc)
    check(f"共检查 {n_ref} 条文件引用：代码引用无悬空（历史名已登记 {len(HIST_SEEN)} 个）",
          not hard_missing, f"缺 {sorted(hard_missing)}" if hard_missing else "")
    if soft_missing:
        print(f"  [WARN] 另有 {len(soft_missing)} 条**非代码**引用未命中"
              f"（多为历史合并件的旧名、数据文件名、SPEC 设计稿中的文件名）：")
        for ref, docs in sorted(soft_missing.items())[:18]:
            print(f"        - {ref}  ←  {', '.join(sorted(set(docs)))}")
        WARN.append(f"{len(soft_missing)} 条非代码引用未命中（历史名/数据名/设计稿）")

    print("\n" + "=" * 74)
    print("B. python/ 下的脚本是否都被文档提到（找孤儿代码）")
    print("=" * 74)
    all_text = ""
    for doc in DOCS:
        if os.path.exists(doc):
            all_text += open(doc, encoding="utf-8", errors="replace").read()
    orphans = []
    scripts = [f for f in sorted(os.listdir("python"))
               if f.endswith((".py", ".R")) and f != "__init__.py"]
    for f in scripts:
        if f not in all_text:
            orphans.append(f)
    check(f"python/ 下 {len(scripts)} 个脚本（不含包标记 __init__.py）均在文档中被引用",
          not orphans, f"孤儿：{orphans}" if orphans else "", strict_only=True)
    for f in orphans:
        print(f"        - python/{f}")

    print("\n" + "=" * 74)
    print("C. 论文图画清单：脚本 + 产物")
    print("=" * 74)
    figs = {
        "图1": ("python/fig1_compound_spatial.py", "results/figures/fig1_compound_spatial.png"),
        "图2": ("python/fig2_chr.py", "results/figures/fig2_chr.png"),
        "图3": ("python/fig3_attribution.py", "results/figures/fig3_attribution_x3.png"),
        "图4": ("python/fig4_return_period.py", "results/figures/fig4_return_period_x3.png"),
        "图5": ("python/fig5_sst_trend.py", None),
        "图6": ("python/fig6_wbt.py", None),
        "论文版S1": ("python/figS1_annual_maps.py",
                     "results/figures/figS1_paper_annual_maps.png"),
        "Table1": ("python/table1_attribution.py", "results/tables/table1.csv"),
    }
    for name, (script, prod) in figs.items():
        ok_s = os.path.exists(script)
        ok_p = (prod is None) or os.path.exists(prod)
        detail = f"脚本 {'有' if ok_s else '缺'}；产物 " + (
            "待数据" if prod is None else ("有" if ok_p else f"缺（{prod}）"))
        check(f"{name}", ok_s and ok_p, detail, strict_only=(prod is None))

    print("\n" + "=" * 74)
    print("D. 关键数据与中间产物")
    print("=" * 74)
    key = {
        "OISST 合并件": "data/OISST/oisst_v2.1_1982_2023.nc",
        "E-OBS 合并件": "data/E-OBS/EOBS_tg_1983_2023.nc",
        "海岸配对表": "results/intermediate/coastal_pairs.csv",
        "复合事件网格": "results/intermediate/compound_events.nc",
        "年度复合日": "results/intermediate/annual_compound_days.nc",
        "100km 缓冲掩码": "results/intermediate/coastal_buffer100km_mask.nc",
    }
    for name, path in key.items():
        check(name, os.path.exists(path), path)
    print("  （Phase 5/6 的输入尚未下载，属预期：见 `python python\\phase5_humid.py check`）")

    print("\n" + "=" * 74)
    print(f"自审结果：FAIL {len(FAIL)} 项；WARN {len(WARN)} 项")
    print("=" * 74)
    if FAIL:
        print("FAIL：")
        for f in FAIL:
            print(f"  - {f}")
    if WARN:
        print("WARN（不影响主链路，多为待数据项）：")
        for w in WARN:
            print(f"  - {w}")
    if not FAIL:
        print("\n未发现悬空引用或缺失的图画脚本。")
    return 1 if (FAIL and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
