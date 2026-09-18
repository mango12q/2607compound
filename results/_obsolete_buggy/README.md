# _obsolete_buggy — 已废弃的分析脚本

这些脚本产出过**错误或已被取代**的结论，统一归档于此，避免误用。

## 为什么废弃

它们全部建立在同一个错误前提上：

```r
clm <- ts2clm(..., clmOnly = TRUE)                     # 366 行的日气候态
ev  <- detect_event(ts_df, seasClim = clm$seas,
                    threshClim = clm$thresh)            # 366 行喂给 14975 行 -> 阈值错位
```

`detect_event()` 会把 366 行循环补齐到 14975 行，阈值与日期整体错位，
只发出一个容易忽略的 `data.table` recycling warning。
因此这些脚本得出的「R 只检出 70,623 个事件」「R 阈值全是 NA」
「R 与 Python 差 44 倍」等结论**全部无效**。

## 各文件的性质

| 文件 | 问题 |
|---|---|
| `compare_top500.py` / `test_r_subset.py` | 调用已删除的 `detect_thw_subset*.R`（同样带 BUG） |
| `compare_full.py` | 同一 BUG 的全量版 |
| `compare_r_py_subset.py` / `compare_r_py_med.py` | 基于 BUG 输出的对比 |
| `compare_thresholds.py` / `2` / `3` | 试图从 BUG 输出反推 R 阈值（阈值本身就是错位的） |
| `analyze_discrepancy.py` / `analyze_event_detail.py` / `2` / `analyze_only_events.py` | 对 BUG 结果的差异分析 |
| `check_eobs_*.R` / `debug_eobs_r*.R` | 排查「数据有问题」方向的诊断（方向本身是错的：数据没问题） |
| `test_heatwaveR*.R` | 早期探针脚本，已被 `results/diag_clm_only.R` 取代 |
| `check_data_meta.py` | 一次性元数据检查 |

## 正确版本

请使用 `results/` 下的这些脚本：

- `diag_clm_only.R` — `clmOnly=TRUE` BUG 的最小复现（对照 `clmOnly=FALSE` 正确用法）
- `diag_detect_event.R` — 单格点拆解 `detect_event` 内部机制
- `compare_thw_full.py` — R vs Python 全量对比（权威版）
- `verify_threshold_method2.py` — 阈值算法隔离实验（11 天窗口 vs 单日）
- `pinpoint_diff.py` — 2×2 消融实验（阈值 × 最小持续时间口径）
- `replicate_heatwaver.py` — heatwaveR `proto_event` 的 Python 精确复刻与校验

结论见 `results/THW_R_vs_Python_结论.md`。
