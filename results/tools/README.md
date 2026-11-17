# results/tools/ — 诊断与复算脚本

> 这些脚本**不参与日常复现**（日常只用 `python/run_all.py` + `python/figures.py` +
> `python/phase6_cesm.py`）。它们的作用是「某个结论是怎么算出来的」可复算。
> 全部只读 `data/` 与 `results/intermediate/`，产物写入各自目录或 `results/intermediate/audit/`。

## 分组

| 目录 | 脚本 | 作用 | 何时用 |
|---|---|---|---|
| `phase6审计/` | `phase6_audit_grid.py` / `_detect.py` / `_detect.R` / `_baseline.py` / `_stats.py` | Phase 6 审计四路（网格配对 / 检测语义 / 基准期 / 复合统计）的完整复算机 | 想重跑审计证据时；`--help` 看子阶段 |
| `phase6审计复算/` | `phase6_audit_lead_check.py` `_2`…`_12` + `.R` | Lead 的 12 步独立复算（T2m 阈值塌缩、`proto_event` 450/450 等价、模糊测试、时间约定、原点错位…） | 复核 Phase 6 审计的关键数字 |
| `图1jl口径诊断/` | `diagnose_*.py`、`fig1j_*.py`、`check_buffer_regions.py` | 图1j/l「绝对量级不可复现」结论的完整证据链（7 种口径穷举、区域框扫描、THW 封顶、缓冲区域对比） | 需要重新论证或改变图1j/l 口径时 |
| `S1读取/` | `s1_extract.py` → `s1_layout.py` → `s1_crop.py` → `s1_quantify.py`（另有 contact/calib/overview） | 从补充材料 PDF 抽取 Supplementary Fig. S1 并判读非复合年 | 需要重新读取 S1 时（**按脚本名顺序跑**） |
| `数据核查/` | `eobs_splice_check.py` | E-OBS v33/v29 拼接断点（2010/2011）四项检验 | 复核「未发现拼接伪影」结论 |
| `锚点核对/` | `snapshot_fig_stats.py` / `check_new_anchors.py` / `show_stats.py` | 图1/图2 数值快照、锚点核对、快照打印 | 改图后重新生成 `tables/fig_stats_*.json` |
| `源码存档/` | `detect_event_source.txt` / `ts2clm_source.txt` / `proto_event_source.txt` | marineHeatWaves 与 heatwaveR 的源码存档（D1 与 Phase 6 审计的证据） | 需要核对包语义时 |

## Phase 6 残差排查脚本（在 `logs/`，不在本目录 —— 2026-11-08 新增）

2026-11-08 第二十三~二十六批把"图4/Table 1 与论文的量级残差"追到结案，证据链脚本全在仓库根的
`logs/`（只读，不参与日常复现）。**结论出处 ↔ 脚本对照**：

| 结论 | 脚本 | 关键产出 |
|---|---|---|
| 暴露量纲不是元凶（`frac` 逐位不变、`events` 更差） | `logs\_diag_v8_metric.py` | `logs\_diag_v8_metric_pre.log`、`_diag_v8_series.npz` |
| 区域年暴露统计（440 模型年分位） | `logs\_diag_exp_series.py` | `logs\_exp_series_{tag}.npz`（**只存 22 长成员平均序列**） |
| 复合面板 13× 残差是 **GEV 外推假象** | `logs\_diag_emp_rp.py` | GEV vs 经验分位逐档对照 |
| 1983–2012 两实验强迫差 δ | `logs\_diag_delta_clim.py` | δ_t2m **1.129 °C** / δ_sst **0.796 °C** |
| CESM 相对观测的暖偏差 β | `logs\_diag_obs_bias.py` | β_t2m +0.783（全对）/ +1.167（Med 框）、β_sst +0.431 / +0.065 |
| 分析域是一阶因子（换全欧 15/15 全掉出 CI） | `logs\_diag_region_sens.py` | 地中海框 vs 206 对对照表 |
| **终局判定：噪声 vs 真残差** | `logs\_cmp_ci.py` | 五档 + bootstrap CI + 论文值 IN/out |
| 全史口径并排（13 个 tag） | `logs\_cmp_gev_tags.py` | 五档 + FixGHG 百年水平 + 各自 Table 1 |
| 主口径一键全链（5.7 min） | `logs\_run_v12w50.ps1` | `results\tables\phase6_gev_v12w50.json` 等 |

> 完整的"哪条假设被证伪"清单见 `results/复现报告.md` §5.2 与 `AGENTS.md` 第二十三~二十六批。

## 约定

- 脚本里的相对路径多按 `<repo>/results/xxx.py` 写成 `os.path.join(BASE, "results", ...)`；
  用 `git mv` 归档后若有脚本报「找不到文件」，改它内部的 `results/` 相对段即可
  （第三轮审查已把**主文档里引用这些脚本的路径**更新为 `results/tools/<主题>/`，
  但**脚本自身的内部常量/用法行**仍指向旧的 `results/` 顶层路径，见下条）。
- **已知遗留（P2，未修）**：`results/tools/phase6审计/phase6_audit_detect.py:42` 的
  `R_AUDIT` 常量仍指 `D:\2607compound\results\phase6_audit_detect.R`（实际在
  `results/tools/phase6审计/`）；各脚本头部「用法」注释里的路径同样过期。
  这些脚本是一次性复算机，运行前需先改路径。
- 所有脚本都是**一次性研究脚本**，不保证互相 import；按需单独运行。
