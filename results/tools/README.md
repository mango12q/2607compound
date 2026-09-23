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

## 约定

- 脚本里的相对路径多按 `<repo>/results/xxx.py` 写成 `os.path.join(BASE, "results", ...)`；
  用 `git mv` 归档后若有脚本报「找不到文件」，改它内部的 `results/` 相对段即可。
- 所有脚本都是**一次性研究脚本**，不保证互相 import；按需单独运行。
