# results/ — 产物与文档导航

> 2026-09-23 整理：原 80 个顶层过程文件已合并/归档为下表结构。
> 合并前的分报告与一次性诊断脚本仍可在 git 历史里查到（`git log --diff-filter=D --name-only`）。

## 文档（先读这几份）

| 文件 | 内容 | 什么时候读 |
|---|---|---|
| `复现报告.md` | **主报告**：进度、锚点验证总表 §4、方法学决策 **D1–D7（含 D7.1–D7.7 及 -rev 修订，Phase 6 主口径 = D7.7 `_v12w50`）**、偏差清单 §5.1、**Phase 6 残差排查全过程 §5.2**、图1j/l 定稿 §6 | 任何时候，第一份 |
| `复现报告_终版.docx` | **终版中文交付报告**（2026-11-17，3.7 MB）：10 章 + 6 张主图 + 12 张表，结论摘要 / 阶段状态 / D1–D7 / 锚点核对 / 逐图结果 / 未复现项 / 13 条差异 / 复现方式 / 产物清单 / 口径演化表。重建：`python scripts\build_final_report.py` | 对外交付、汇报 |
| `phase6审计报告.md` | Phase 6 归因管线审计（6 份合并）：问题清单、逐维度结论、修复前后对比、4 份分报告全文 | 跑 Phase 6 之前 |
| `规划一致性审查.md` | 规划文件 vs 论文**四轮**审查（含第二轮对第一轮的 3 处更正、第三轮的 P0 阻塞项、第四轮的图版式逐像素校准与数据探针） | 动 Phase 5/6 规格之前 |
| `方法与证据.md` | 目视比对、E-OBS 版本核查、S1 读取、R/Python 检测交叉验证 + 2 份历史存档 | 追溯某个结论怎么来的 |
| `图版对照表.md` | **论文原图 ↔ 本复现产物**逐图对照（12 张图的脚本、产物、状态、锚点摘要 + 目视验收方法） | 最终目视验收时 |

> 另外两份在**仓库根目录 / docs/**：根目录 `待办.md`（操作指引）、`docs/阶段计划.md`（阶段计划与验收锚点）。

## 代码（留在本目录的）

| 文件 | 用途 |
|---|---|
| `globalize_mhw_idx.py` | **被 `python/run_all.py` 运行时调用**，勿移动 |
| `build_oisst_clip.py` | Phase 0：23 GB 全球 OISST → 欧洲裁剪件 |
| `build_domains.py` | Phase 1：生成 R 检测用的海/陆域点清单 |
| `run_detection_R.py` | Phase 1：手动重跑海陆检测（`--help` 看用法） |
| `phase6_selftest.py` | Phase 6 口径**纯合成**自检（不读数据），应输出 `ALL SELFTESTS PASSED` |

> Phase 5 的公式自检在 `python/calc_wbt.py` 与 `python/gev_return_period.py` 的 `__main__` 里
> （各自直接 `python python\calc_wbt.py` / `python python\gev_return_period.py` 即可）。

## 子目录

| 目录 | 内容 |
|---|---|
| `figures/` | 全部出图（**论文图画清单已全部有脚本**）：图1（a–m）、图2（a–d）、图3（`fig3_attribution{tag}.*`）、图4（`fig4_return_period{tag}.*`）、图5（`fig5_sst_trend.*`）、图6（`fig6_wbt.*`）、**论文版 S1**（`figS1_paper_annual_maps.*`，1984–2023 年际组图）、本项目补充图 S2（`figS2_jkl_mhw_envelope.*`）。另有 `*_synthetic_demo.*` / `*_demo.*` / `fig7_p0_validation*.png` 等**版式自检与流程验证图，不是结果** |
| `figures/*_pyEvents.pdf`、`fig1_compound_spatial_exceedance_backup.*` | **历史存档**：`_pyEvents` 是早期 **Python 检测口径**（D1 已弃用、改用 R heatwaveR）的图1/图2 版本；`_exceedance_backup` 是**方案 A（逐日共超标）**的图1 主图备份（2026-09-23 切到 MHW 包络后留档）。**均不代表当前口径**，仅作对照 |
| `tables/` | 数值快照 JSON/CSV（`fig_stats_*.json`、`fig5_stats.json`、`fig6_stats.json`、`phase6_attrib_sweep*.csv` 等，**不入 Git**） |
| `intermediate/` | 中间产物（不入 Git；OISST/E-OBS/CESM 检测结果、年度指标、逐日 WBT/SH、趋势场） |
| `tools/` | 诊断与复算脚本，按主题分组，见 `tools/README.md` |
| `s1/` | 补充材料 Fig. S1 的裁剪图（不入 Git，由 `tools/S1读取/` 复现） |

## 非 Git 跟踪的本地文件

- `paper_text.txt` / `paper_supp_text.txt`：论文与补充材料正文提取（版权原因不入库）
- `results/tables/`（整目录，见 `.gitignore`；第三轮补登）
- `data/`（NTFS Junction → `E:\2607compound\data`）
- `logs/`：**存在且很重要**（早期"目录已不存在"的说法已过期，2026-11-08 更正）——存放跑批日志
  `logs\run_{tag}.log`、逐步日志 `logs\steps\<tag>_<step>.log`、一键脚本 `logs\_run_v12w50.ps1`，
  以及 **Phase 6 残差排查的诊断脚本**（只读，不进 `python/` 主链）：
  | 脚本 | 用途 |
  |---|---|
  | `logs\_cmp_gev_tags.py` | 各 tag 五档重现期 + FixGHG 百年水平 + 各自 Table 1 并排（全史对照） |
  | `logs\_cmp_ci.py [tag…]` | **判"噪声 vs 真残差"专用**：五档 + bootstrap CI + 论文值 IN/out + `r100/r5` |
  | `logs\_diag_emp_rp.py` | GEV 外推 vs 经验分位映射的逐档对照（N=440 模型年） |
  | `logs\_diag_region_sens.py` | 分析域敏感性（地中海框 vs 全欧 206 对） |
  | `logs\_diag_delta_clim.py` | δ = ALL−XGHG 的 1983–2012 强迫差（T2m 1.129 / SST 0.796 °C） |
  | `logs\_diag_obs_bias.py` | β = CESM ALL 相对观测的暖偏差（T2m +0.783 / SST +0.431 °C） |
  | `logs\_diag_v8_metric.py` / `logs\_diag_exp_series.py` | 暴露量纲敏感性 / 区域年暴露统计 |
