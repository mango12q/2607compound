# results/ — 产物与文档导航

> 2026-09-23 整理：原 80 个顶层过程文件已合并/归档为下表结构。
> 合并前的分报告与一次性诊断脚本仍可在 git 历史里查到（`git log --diff-filter=D --name-only`）。

## 文档（先读这几份）

| 文件 | 内容 | 什么时候读 |
|---|---|---|
| `复现报告.md` | **主报告**：进度、锚点验证总表 §4、方法学决策 **D1–D11**、偏差清单 §5.1、图1j/l 定稿 §6 | 任何时候，第一份 |
| `phase6审计报告.md` | Phase 6 归因管线审计（6 份合并）：问题清单、逐维度结论、修复前后对比、4 份分报告全文 | 跑 Phase 6 之前 |
| `规划一致性审查.md` | 规划文件 vs 论文**四轮**审查（含第二轮对第一轮的 3 处更正、第三轮的 P0 阻塞项、第四轮的图版式逐像素校准与数据探针） | 动 Phase 5/6 规格之前 |
| `方法与证据.md` | 目视比对、E-OBS 版本核查、S1 读取、R/Python 检测交叉验证 + 2 份历史存档 | 追溯某个结论怎么来的 |

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
| `tables/` | 数值快照 JSON/CSV（`fig_stats_*.json`、`fig5_stats.json`、`fig6_stats.json`、`phase6_attrib_sweep*.csv` 等，**不入 Git**） |
| `intermediate/` | 中间产物（不入 Git；OISST/E-OBS/CESM 检测结果、年度指标、逐日 WBT/SH、趋势场） |
| `tools/` | 诊断与复算脚本，按主题分组，见 `tools/README.md` |
| `s1/` | 补充材料 Fig. S1 的裁剪图（不入 Git，由 `tools/S1读取/` 复现） |

## 非 Git 跟踪的本地文件

- `paper_text.txt` / `paper_supp_text.txt`：论文与补充材料正文提取（版权原因不入库）
- `results/tables/`（整目录，见 `.gitignore`；第三轮补登）
- `data/`、`logs/`（`logs/` 目录当前已不存在）
