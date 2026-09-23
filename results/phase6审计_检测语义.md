# Phase 6 检测语义审计（task-2 / D-2）

**审计对象**：`python/phase6_cesm.py` 的 `_run_events`(L259-271)、`_detect_mhw_member`(L336-378)、
`_detect_thw_member`(L381-403)、`_detect_thw_member_ext`(L406-444)、`_pooled_threshold_sst`(L274-295)、
`_pooled_threshold_t2m`(L298-333)
**对照物**：`python/detect_events.R`（观测侧正式链路；heatwaveR **0.5.5**，R 4.6.1）
**审计原则**：不采信任何文档自述（含 `results/复现报告.md` D1/D2、`config.py` 注释、
`results/detect_event_source.txt`、`results/ts2clm_source.txt`）。全部结论 = 本机 heatwaveR 真实函数体 + 判别性实验实测数字。
**复算入口**：
```
Rscript results/phase6_audit_detect.R  <in> <out> {all|fuzz|force}
python  results/phase6_audit_detect.py [--skip-r] [--only export,fuzz,r,e1,e2,e3,e4,e4c,e5,a1]
```
**产物目录**：`results/intermediate/audit/detect/`（`audit_summary.json` 为机器可读汇总）

---

## 0. 结论速览

| 编号 | 结论 | 判定 | 严重度 | 影响量级（实测） |
|---|---|---|---|---|
| **E1** | `_pooled_threshold_t2m` 的 `np.nanpercentile(..., axis=0)` 对 **1-D** `stacked` 求值 → **标量**，广播成 366×206 的**全域同一曲线** | **有问题** | **P0** | 阈值 mean\|Δ\| **8.26 °C**（p90 16.45，max 24.65）；v2 THW 事件被**低估到 1/3–1/4**（XGHG 001：3746 → 11310，0.33×） |
| E1-b | 即使只修 `axis`，仍是"**逐日分位的再分位**"，与 heatwaveR"窗内合并原始样本"不同 | **有问题** | 中 | 阈值 mean\|Δ\| 0.531 °C（p90 0.977，max 5.71） |
| E1-c | 两个池化缓存都**缺 doy=366 行**（全 NaN），闰年 12-31 共 6 天×206 点被永久屏蔽 | **有问题** | 中 | **1236 点·日/序列** 不可能超标 |
| **E2** | 模型侧 MHW（v1 自身气候态 / v2 池化）**只用单日 doy 分位，缺 11 天窗**；观测侧 MHW 走 R `detect_events.R`（`windowHalfWidth=5`）→ **海陆口径不一致** | **有问题** | **高** | v1 MHW 超标日 **1.49×（ALL）/1.53×（XGHG）**；单日分位有 **3/22 = 13.6%** 的系统性超标率（vs 11 天窗 ~10%）；传导到**复合日数 +27%（ALL）/ +31%（XGHG）** |
| E2-b | `smoothPercentile=FALSE` 下 11 天窗**仍然生效**（源码证据） | 确认无误（指 R 侧） | — | 见 §2.1 |
| E2-c | 观测侧 MHW 确实来自 R 11 天窗链路 | 确认无误 | — | `config.MHW_EVENTS_CSV` = `mhw_events_R_global.csv`（152490 事件） |
| **E3** | `_run_events` 是"**先桥接后过滤**"，heatwaveR `proto_event` 是"**先过滤后桥接**" | **有问题** | **P0** | 1350 条模糊用例中 **78–143/150 不等价**；真实 CESM 上**事件数放大 2.0–2.1×** |
| E3-b | heatwaveR 的空档桥接**头尾不对称**：吸收尾部空档（≤maxGap），**不吸收**头部空档 | 确认无误（指 R 侧） | 中 | 独立复核 Lead 结论；`proto_event` 逐行复刻 **0/1350 不一致** |
| E3-c | 项目文档（D1 / `compound_events.py` L21）对 heatwaveR 的描述**是对的**，错的是代码 | 确认无误 | — | — |
| E3-d | 观测侧 Python `detect_mhw._EventTracker` 与 `_run_events` **同语义**（同为先桥接后过滤） | 确认无误 | 低（当前未使用） | 21/21 用例一致 |
| E4 | 严格大于 / 时长含空档 / 跨年不切分 / NA 处理 | **确认无误** | — | 见 §5 |
| E4-b | 阈值 NaN 时 Python 视为"非超标"，R 会产生 NA 判据（本数据未触发） | 未判定（不影响本数据） | 低 | 实测阈值 NaN 占比：缓存 0.273%（doy 366 行），R 产物 0% |
| E5 | `min_valid=730` 在 Python 路径缺失 | **确认无误（无影响）** | 无 | 模型域 206 点有效日 ≥8029 > 730，`<730` 点数 **0** |
| **A1** | `ALL_00x_T2m.nc` 时间轴在 **12:00**（XGHG 在 00:00）→ `_event_daily_mask` 的 `(date − t0).days` 让 ALL 成员三张 00:00 事件表（mhw / mhw_x / thw）掩码整体偏早 **1 天**，而 `thw_x_ALL_*.csv` 带 12:00 故不偏移 → v2 陆海掩码错位 1 天 | **有问题（附加）** | 中 | v2 ALL 复合日 **+1.52%**（63154 vs 62191） |
| **A2** | `ALL_00x` 的 SST 两段拼接后**缺 2006-01-02**（8029 天 vs T2m 8030 天） | **有问题（附加）** | 低 | 1 天/序列；跨该日的游程被当作相邻 |

> 影响面界定：**观测侧结论不受影响**。`config.MHW_EVENTS_CSV`/`THW_EVENTS_CSV` 均由 R `detect_events.R`（heatwaveR）产出。
> 受影响的只有 **Phase 6 模型侧**：v2 的 THW（Python `_detect_thw_member_ext`）与 MHW（Python `_detect_mhw_member(thresh_ext=...)`），
> 以及 v1 的 MHW（Python 自身气候态）。v1 的 THW 走 R，不受影响。

---

## 1. E1 ★ `_pooled_threshold_t2m` 的 axis 崩溃

### 1.1 实测：缓存文件本身

复算方式：`python -c` 读 `results/intermediate/cesm/thresh_*_xghg.npz`，逐行算 `ptp`（NaN-aware）。

| 变量 | shape | 文件字节 | 全 NaN 行 | 有数据行 | **行内 max−min 最大值** | 所有有限行是否行内全等 |
|---|---|---|---|---|---|---|
| **t2m** | (366, 206) | **2547** | [365] | 365 | **0.000000 °C** | **True** |
| sst | (366, 206) | 298590 | [365] | 365 | 22.822289 °C | False |

**t2m 的 365 个有效行，每一行在 206 个陆点上取值完全相同**（行内极差恒为 0）。
即：**v2（XGHG 基准）的 THW 检测对全部 206 个陆点使用了同一条"欧洲全域阈值曲线"**。
SST 侧没有这个问题（行内极差 22.8 °C），文件大小差 **117×**（2547 B vs 298590 B）。

### 1.2 机制确认（可复算）

`results/phase6_audit_detect.py::e1` 按被审计代码原样复算：

```python
single[d-1] = np.nanpercentile(rows, 90, axis=0)                 # (206,)
stacked = np.concatenate([single[w-1] for w in win], axis=0)     # (11*206,) —— 1 维!
thresh[d-1] = np.nanpercentile(stacked, 90, axis=0)              # ← 标量
```

`np.concatenate` 把 11 个 `(206,)` 拼成 **1 维 `(2266,)`**，`np.nanpercentile(..., axis=0)` 于是返回**标量**，
再广播填入 `thresh[d-1]` 的 206 列 → 行内全等。

- **复算 vs 磁盘缓存：最大差 = 0.000e+00**（逐位一致）。
- 把 `concatenate` 换成 `np.stack(..., axis=0)` 并保留 `axis=0`（只修 axis）后：**行内极差最大回升到 30.737 °C**，证明崩溃点确在此处。

### 1.3 量化一：阈值差（75190 = 365 doy × 206 点的点·日）

| 情形 | mean\|Δ\| | 有符号均值 | p50 | p90 | p99 | max | >1 °C 占比 | >2 °C 占比 |
|---|---|---|---|---|---|---|---|---|
| **broken（缓存，全域同一曲线） vs 正确池化 11 天窗** | **8.264** | **+7.931** | 7.786 | **16.453** | 20.477 | **24.652** | **91.2%** | **84.0%** |
| 仅修 axis（逐日分位再分位） vs 正确池化 11 天窗 | 0.531 | +0.531 | 0.445 | 0.977 | 1.830 | 5.710 | 9.4% | 0.7% |
| 单日分位（pandas doy） vs 正确池化 11 天窗 | 0.377 | −0.125 | 0.285 | 0.808 | 1.660 | 4.033 | 5.5% | 0.5% |
| 单日分位（heatwaveR doy） vs 正确池化 11 天窗 | 0.367 | −0.122 | 0.275 | 0.787 | 1.662 | 4.783 | 5.2% | 0.5% |

- 有符号均值 **+7.93 °C**：崩溃阈值被**系统性抬高约 8 °C**（89.4% 的点·日偏暖），
  于是 v2 的 THW 被系统性**漏检**。这与"缓存行 = 逐日空间 90 分位（暖尾）的再分位"一致。
- 阈值均值（365×206 平均）：
  **broken 21.357 °C** ｜ 仅修 axis 13.957 °C ｜ 单日分位(pandas doy) 13.301 °C ｜ **正确池化 11 天窗 13.426 °C**。
- 逐点平均偏差（broken − correct）：**最暖处被抬高 +18.49 °C**（点 p195，地中海/北非侧），
  **最冷处被压低 −2.87 °C**（点 p14）；其余点绝大多数被抬高。
  → 崩溃版不是"整体平移"，而是**把空间差异抹平成暖尾常数**，因此对冷点杀伤最大。
- **"只修 axis"仍有 0.531 °C 的系统偏差**：`_pooled_threshold_t2m` 的注释写"11 天窗圆周平滑
  (heatwaveR windowHalfWidth=5 语义: 窗内样本合并求分位)"，但**若只修 axis，用的是"11 个逐日分位的分位"**，
  与 heatwaveR 的"窗内合并**原始样本**再取分位"（见 §2.1 源码）**不是**同一件事。

### 1.4 量化二：检测影响（成员 001，逐点跑被审计的 `_run_events`）

| exp | 阈值 | 事件数 | 超标日 | mean 时长 |
|---|---|---|---|---|
| ALL 001 | broken（实际 v2） | **6468** | **92910** | 12.24 |
| ALL 001 | 仅修 axis | 21320 | 261186 | 8.83 |
| ALL 001 | 正确池化 11 天窗 | **28466** | **340750** | 9.54 |
| XGHG 001 | broken（实际 v2） | **3746** | **50482** | 10.17 |
| XGHG 001 | 仅修 axis | 6897 | 109037 | 7.40 |
| XGHG 001 | 正确池化 11 天窗 | **11310** | **156869** | 7.77 |

- **倍数**：ALL 001 事件 **0.23×**、超标日 **0.27×**；XGHG 001 事件 **0.33×**、超标日 **0.32×**。
- **复算忠实度自检**：用 broken 阈值复算得到 ALL 001 = **6468** 事件、XGHG 001 = **3746** 事件，
  与磁盘产物 `thw_x_ALL_001.csv`（6468 行）、`thw_x_XGHG_001.csv`（3746 行）**完全一致** →
  证明本审计的重算忠实于被审计代码，上表其余行可信。

### 1.5 正确参考实现的校验（关键：不是"我说了算"）

本审计用 Python 忠实复刻 heatwaveR `clim_spread`+`clim_calc`（含 `make_whole_fast` 的 doy 规则、
Feb-29 槽用 `round(mean(doy59,doy61),2)` 填充、366 天圆形 11 天窗、`type=7` 分位），
并用本机 R `ts2clm(windowHalfWidth=5L, smoothPercentile=FALSE)` 在**同一条序列**上校验：

| 序列 | 比较点数 | **max\|Δ\|** | mean\|Δ\| | 精确时间戳匹配率 |
|---|---|---|---|---|
| XGHG_001 T2m | 8030 × 206 | **9.96e-05 °C** | 3.21e-05 °C | 1.000 |
| ALL_001 T2m | 8030 × 206 | 9.01e-03 °C | 3.23e-05 °C | **0.000** |

残差 ~1e-4 °C 来自 R 的 `roundClm=4` 舍入 → **参考实现与 heatwaveR 等价**。
（`ALL_001` 的"精确时间戳匹配率 = 0.000"是 A1 那条发现的一个旁证：该文件时间轴在 **12:00**。）

### 1.6 补充：doy=366 整行缺失

`_pooled_threshold_t2m` / `_pooled_threshold_sst` 都只循环 `np.arange(1, 366)`（doy 1..365），
故两缓存的 **index 365（doy 366）全为 NaN**。CESM 数据经 `pd.DatetimeIndex.dayofyear` 后
**doy=366 出现在 6 个闰年的 12-31**（2000/2004/2008/2012/2016/2020）。

- `thr_t = thresh[doy-1]` → 这 6 天阈值为 NaN → `arr > NaN` 恒为 False →
  **6 天 × 206 点 = 1236 点·日/序列**永远不可能被判为超标（v2 THW 与 v2 MHW 都中招）。
- v1 MHW 用 `for d in np.unique(doy)`，含 doy=366，**无此缺口**（这也说明该缺口是 v2 池化函数专有）。

---

## 2. E2 模型侧 MHW 阈值缺 11 天窗

### 2.1 源码证据：`smoothPercentile=FALSE` 下 11 天窗**仍然生效**

证据文件：`results/intermediate/audit/detect/heatwaveR_source_evidence.txt`
（由 `Rscript -e 'print(heatwaveR::ts2clm)'` 等从**本机安装包**
`C:/Program Files/R/R-4.6.1/library/heatwaveR` 现场提取；行号为 deparse 后函数体内行号）

`ts2clm`（证据 1）：
```r
73|     ts_wide <- clim_spread(ts_whole, clim_start, clim_end, windowHalfWidth)
76|         ts_mat <- clim_calc(ts_wide, windowHalfWidth, pctile)
80|         ts_mat <- clim_calc_cpp(ts_wide, windowHalfWidth, pctile)
83|     if (smoothPercentile) {
84|         ts_clim <- smooth_percentile(ts_mat, smoothPercentileWidth, ...
88|         ts_clim <- data.table::data.table(ts_mat)
```
→ `clim_spread`/`clim_calc` **无条件**执行；`smoothPercentile` 只控制是否**再做 31 天滚动均值**平滑。
**`smoothPercentile=FALSE` 只是不做平滑，11 天窗合并照样发生。**

`clim_calc`（证据 2）：
```r
 6|     for (i in (windowHalfWidth + 1):((nrow(data) - windowHalfWidth))) {
 9|         thresh[i] <- stats::quantile(c(t(data[(i - (windowHalfWidth)):(i +
10|             windowHalfWidth), seq_len(ncol(data))])), probs = pctile/100,
```
→ 明确是"**窗内合并原始样本后取分位**"（`type = 7`，`na.rm = TRUE`）。

`clim_spread`（另存 `heatwaveR_clim_spread_dump.txt`）确认：`begin_pad <- tail(ts_spread, windowHalfWidth)`、
`end_pad <- head(ts_spread, windowHalfWidth)` → **366 天圆形环绕**；非闰年 `doy>59` 者 +1，
Feb-29 空槽用 `round(mean(相邻两行),2)` 填充。

### 2.2 (c) 观测侧 MHW 走的就是 11 天窗链路

- `config.MHW_EVENTS_CSV = results/intermediate/mhw_events_R_global.csv`（存在，**152490 事件**）。
- `python/run_all.py` L176-177：`detect_with_R("ocean", OISST_CLIP, "sst", …/mhw_events_R.csv, DOMAINS_CSV)`
  → `globalize_mhw_idx` → `MHW_EVENTS_CSV`；
  `detect_with_R` 传 `ts2clm(pctile=90, windowHalfWidth=5L, smoothPercentile=FALSE)` + `detect_event(5,2)`。
- 结论：**观测侧 MHW = 11 天窗；模型侧 v1/v2 MHW = 单日分位 → 口径不一致**（这是 v1/v2 都存在的缺陷）。

### 2.3 (a) 真实数据量化：单日分位 vs 11 天窗

**(i) R `ts2clm` 官方口径**（24 个抽样配对点，2000-2021，全时段）：

| 变量 | mean\|Δ\| | 有符号均值 | p90 | p99 | max |
|---|---|---|---|---|---|
| **SST ALL_001（24 点）** | **0.116 °C** | +0.099 | 0.260 | 0.503 | 0.839 |
| T2m ALL_001（24 点） | 0.675 °C | +0.318 | 1.495 | 3.097 | 6.374 |

SST 的季节梯度弱 → 阈值差只有 **~0.12 °C**；T2m 的季节梯度强 → **~0.68 °C**。
**但阈值差小 ≠ 影响小**——见下面的超标率机制。

**(ii) 全 206 点、池化 XGHG 口径**（Python 参考实现，已按 §1.5 校验）：

| 情形 | mean\|Δ\| | 有符号均值 | p90 | max |
|---|---|---|---|---|
| v2 实际（单日 pandas doy，66 样本/doy） vs 正确池化 11 天窗 | 0.0816 | −0.0619 | 0.185 | 0.707 |
| 单日（heatwaveR doy） vs 正确池化 11 天窗 | 0.0775 | −0.0657 | 0.169 | 0.850 |
| v2 实际 vs 单日（heatwaveR doy）—— 纯 doy 映射差 | 0.0496 | +0.0038 | 0.116 | 0.512 |

**(iii) 机制：小样本 `type=7` 分位造成系统性超标率**

单成员单日分位每组只有 **22** 个样本（22 年）。`type=7` 分位在 n=22、p=0.9 时
`h = (n−1)p + 1 = 19.9`，即 Q 严格落在第 19、20 大值之间 → **必然有 3/22 = 13.64% 的值超过 Q**。
实测 R 官方 24 点单日口径超标率 = 17807/(8029×24) = **9.24%…13.57%**（SST ALL_001 单日= **13.57%**，
11 天窗 = **9.24%**）；n=242 时 `h = 217.9` → 25/242 = **10.33%**。
→ **单日分位不是"更噪声"，而是"更松"**，这是确定的、与数据无关的偏差。

### 2.4 (a) 事件/超标天数影响（成员 001，全 206 点，R 官方阈值口径）

**(i) v1 MHW**（成员自身气候态，`_detect_mhw_member` 默认路径）：

| exp | 阈值口径 | 事件数 | 超标日 | 平均时长 |
|---|---|---|---|---|
| ALL 001 | 自身单日分位（**实际 v1**） | **10069** | **225364** | 21.45 |
| ALL 001 | 自身 11 天窗（正确） | **7380** | **151449** | 19.27 |
| XGHG 001 | 自身单日分位（**实际 v1**） | **10636** | **225568** | 20.20 |
| XGHG 001 | 自身 11 天窗（正确） | **7675** | **147711** | 17.95 |

→ 超标日 **1.49×（ALL）/ 1.53×（XGHG）**；事件数 **1.36× / 1.39×**。
**复算自检**：复算 10069 / 10636 与磁盘产物 `mhw_ALL_001.csv`（10069）、`mhw_XGHG_001.csv`（10636）**完全一致**。

**(ii) v2 MHW**（XGHG 池化阈值，`_detect_mhw_member(thresh_ext=...)`）：

| exp | 阈值口径 | 事件数 | 超标日 |
|---|---|---|---|
| XGHG 001 | 池化单日分位（**实际 v2**） | 6862 | 133505 |
| XGHG 001 | 池化 11 天窗（正确） | 5828 | 110496 |
| ALL 001 | 池化单日分位（**实际 v2**） | 17111 | 867822 |
| ALL 001 | 池化 11 天窗（正确） | 16657 | 814110 |

→ XGHG 上超标日 **1.21×**（池化后每组 66 样本，`h = 59.5` → 超标率 7/66 = 10.6% vs 73/726 = 10.1%，偏差已大幅缩小）；
ALL 上 **1.066×**（ALL 相对 XGHG 基准本来就极暖，超标率 ~50%，边际影响小）。
**结论：E2 的严重度在 v1 上最高（1.5×），v2 上中等（1.07–1.21×）**，但两者都与观测侧口径不一致。

### 2.5 (c) 传播到**复合暴露**的影响（成员 001，THW 固定为实际产物以隔离 E2）

用修正后的 11 天窗阈值重建 MHW 逐日掩码，按 `cmd_compound` 同一口径重算复合日数：

| exp | 复合日（实际单日分位 MHW） | 复合日（正确 11 天窗 MHW） | 倍数 |
|---|---|---|---|
| ALL 001 | **16756** | **13159** | **1.273×** |
| XGHG 001 | **15810** | **12080** | **1.309×** |

→ 仅 E2（MHW 缺 11 天窗）一项，就使 v1 的复合暴露日数**高估约 27–31%**。
（此表把 THW 固定为磁盘产物，故是 E2 的**边际**效应；E3 的游程逻辑若同时修正会再改变 THW 侧。）

---

## 3. E3 ★ `_run_events` 的桥接/过滤顺序

### 3.1 源码判决：heatwaveR = **先过滤后桥接**

`detect_event` 调用 `proto_event`（证据 3）：
```r
38|     t_series[is.na(ts_y), `:=`(ts_y, ts_seas)]
39|     t_series[, `:=`(threshCriterion, !is.na(ts_y) & ts_y > ts_thresh)]
40|     events_clim <- proto_event(t_series, criterion_column = t_series$threshCriterion,
```
`heatwaveR:::proto_event`（证据 4，完整函数体见证据文件）：
```r
65|     ex1 <- rle(criterion_column)                                   # (a) 原始超标游程
68|     proto_events <- do.call(rbind, lapply(s1[ex1$values == TRUE], ...))
70|     duration <- proto_events$index_end - proto_events$index_start + 1
81|     proto_events <- proto_events[proto_events$duration >= minDuration, ]   # (b) ★先过滤
83|     durationCriterion <- rep(FALSE, nrow(t_series))
84|     for (i in seq_len(nrow(proto_events))) { durationCriterion[...] <- TRUE }
88|     if (joinAcrossGaps) { ... }                                    # (c) 再桥接
101|         proto_gaps <- proto_gaps[proto_gaps$index_end > proto_events$index_start[1], ]
104|         if (any(proto_gaps$duration >= 1 & proto_gaps$duration <= maxGap)) {
109|             for (i in seq_len(nrow(proto_gaps))) { event[...] <- TRUE }
```
→ **不足 `minDuration` 的短游程在桥接之前就被丢弃，永远无法被桥接成事件**。
`_run_events`（L265-271）先 `merged` 桥接原始游程，再 `if b-a+1 >= min_dur` 过滤 → **顺序相反**。

### 3.2 合成判别性用例（21 例；R = 本机 heatwaveR 实测）

| 用例 | `_run_events` | heatwaveR | 判定 |
|---|---|---|---|
| 3超+2空+3超 | 1 事件 / 8 天 | **0 事件** | **不等价** |
| 1超+2空+4超 | 1 / 7 | **0** | **不等价** |
| 4超+2空+4超 | 1 / 10 | **0** | **不等价** |
| 2超+2空+5超（首游程不足） | 1 / 9（从第1天） | 1 / 5（从第5天） | **不等价** |
| 5超+2空+4超 | 1 / 11 | 1 / **5** | **不等价** |
| 4超+2空+5超 | 1 / 11 | 1 / **5** | **不等价** |
| 5超+2空+3超+2空+5超 | 1 / 17 | **2 事件** / 5;5 | **不等价** |
| 5超+2空+2超+2空+5超 | 1 / 16 | **2** / 5;5 | **不等价** |
| 5超+1空+5超 | 1 / 11 | 1 / 11 | 等价 |
| 5超+2空+5超 | 1 / 12 | 1 / **12**（时长含空档） | 等价 |
| 5超+3空+5超 | 2 / 5;5 | 2 / 5;5 | 等价（maxGap 边界） |
| 5超×3，空档各 2 天（链式） | 1 / 19 | 1 / 19 | 等价 |
| 6超+2空+6超 | 1 / 14 | 1 / 14 | 等价 |
| 10 天连续 | 1 / 10 | 1 / 10 | 等价 |
| 4 天连续（<5） | 0 | 0 | 等价 |

### 3.3 独立复核 Lead 的 ③：空档桥接**头尾不对称**

Lead 指出 `proto_event` 的空档过滤是 `index_end > proto_events$index_start[1]`——
**尾部空档会被吸收（使末事件延长 ≤maxGap 天），头部空档不会**。我用 6 个专门用例独立验证：

| 用例 | heatwaveR 实测 | `_run_events` | `proto_event` 逐行复刻 |
|---|---|---|---|
| TAIL：5 超(20-24)，n=26（尾空档 2 ≤ maxGap） | 1 事件 **20..26，时长 7** | 1 事件 20..24，时长 **5** | 20..26，7 ✓ |
| TAIL：5 超(25-29)，n=30（尾空档 1） | **25..30，时长 6** | 25..29，时长 **5** | 25..30，6 ✓ |
| TAIL：5 超(22-26)，n=30（尾空档 4 > maxGap） | 22..26，5 | 22..26，5 | ✓ |
| HEAD：5 超(3-7)，n=30（头空档 2，**应不吸收**） | 3..7，**5** | 3..7，5 | ✓ |
| HEAD：5 超(1-5)，n=30（无头空档） | 1..5，5 | 1..5，5 | ✓ |
| HEAD+TAIL：5 超(3-7)，n=9（头空档 2、尾空档 2） | 3..**9**，**7** | 3..7，**5** | 3..9，7 ✓ |

→ **Lead 的 ③ 成立**：尾部空档被吸收、头部空档不被吸收，两者**不对称**。

### 3.4 模糊测试（1350 例 = 150 条随机 0/1 序列 × 9 组 (min_dur, max_gap)）

用例由 Python 生成（`fuzz_cases.csv`，seed=20260923，n∈[20,60]，p∈[0.15,0.6]）后由 R 读取，
保证两侧输入逐位一致；阈值与事件逻辑解耦（自建 `seas=0 / thresh=0.5` 气候态）。

| min_dur / max_gap | **A `_run_events`** | **B `proto_event` 逐行复刻** | C 先过滤后桥接（头尾都不吸收） | **D 先过滤后桥接 + 尾吸收（头不吸收）** | E C + 头尾都吸收 |
|---|---|---|---|---|---|
| 5 / 2 | **131 / 150** | **0** | 4 | **0** | 2 |
| 5 / 1 | **104 / 150** | **0** | 1 | **0** | 1 |
| 5 / 3 | **137 / 150** | **0** | 5 | **0** | 6 |
| 3 / 2 | **140 / 150** | **0** | 9 | **0** | 12 |
| 7 / 2 | **115 / 150** | **0** | 1 | **0** | 1 |
| （其余 4 组） | 78–143 | 0 | 0–12 | 0 | 1–19 |

**结论（三重一致）**：
1. `_run_events` 与 heatwaveR **不等价**，随机序列上不一致率 **52%–95%**；
2. `proto_event` 逐行复刻在 **全部 9 组、1350 例中 0 不一致** → 语义已被完整刻画；
3. **变体 D（先过滤后桥接 + 只吸收尾空档）同样 0 不一致**，而 C（不吸收尾）与 E（头尾都吸收）都有残差
   → **头尾不对称是 D 与 C 的唯一差别**，独立确认 §3.3。

### 3.5 真实 CESM 数据上的影响（**同一条 R 官方 11 天窗阈值**下，纯游程逻辑差异）

| 序列 | R `detect_event` | Python `_run_events` | 倍数 | 完全相同的事件 | 仅 R | 仅 Python | 超标日 R / Python |
|---|---|---|---|---|---|---|---|
| t2m_ALL_001（206 点） | **5609** | **11890** | **2.12×** | 3676（占 R 的 65.5%） | 1933 | 8214 | 166227 / **166227** |
| t2m_XGHG_001（206 点） | **6062** | **12108** | **2.00×** | 3977（65.6%） | 2085 | 8131 | 166121 / **166121** |

→ 在真实数据上，`_run_events` 把 THW 事件数**放大约 2.0–2.1×**（合并了大量本应被丢弃的短游程）。
**关键对照**：两条序列的**超标日数 R 与 Python 完全相等**（166227、166121），
说明差异**纯粹来自游程/桥接逻辑**，与阈值无关（两者用的是同一份 R `ts2clm` 阈值）。
**旁证**：本审计用 R `ts2clm`+`detect_event` 独立复跑 v1 路径得到
`t2m_ALL_001 = 5609` / `t2m_XGHG_001 = 6062`，与磁盘产物 `thw_ALL_001.csv`（5611）/`thw_XGHG_001.csv`（6065）
差 2–3 个事件（**0.04%**，来自 `roundClm=4` 舍入的边界翻转）→ 佐证 R 侧复现忠实。

### 3.6 观测侧 Python 是否同病

`python/detect_mhw.py::_EventTracker`（L43-66）在 `gap_count > max_gap` 时才 `end_idx - start_idx >= min_dur` 判定
→ **同为先桥接后过滤**。实测：21/21 判别用例下 `_EventTracker` 与 `_run_events` **完全一致**。
但 `run_all.py` 的观测 MHW 走 R，`detect_mhw.py` 当前**未被观测结果使用**（`detect_events.py` 同理）。
→ **影响面仅限 Phase 6 模型侧**；观测侧 `mhw_events_R_global.csv` / `thw_events_R.csv` 不受影响。

### 3.7 为什么文档没错

`compound_events.py` L21-22 写"先连续超标游程>=5 天再桥接 <=2 天间隙"——**这是对的**；
`results/复现报告.md` D1 同理。**错的是 `phase6_cesm.py` 的 `_run_events` 实现**。
可解释的成因：项目归档的 `results/detect_event_source.txt` **只 dump 了 `detect_event` 的函数体，
没有 dump `proto_event`**——判决性逻辑在被调用的那个函数里，所以文档作者没能据此发现代码偏差。

---

## 4. E4 游程状态机的其它细节

| 项 | 实测 | heatwaveR 对照 | 判定 |
|---|---|---|---|
| 判据为**严格大于** | `temp==thresh`（0.5 vs 0.5）→ **0 事件**；`temp=1.0>0.5` → 1 事件 | 源码 `!is.na(ts_y) & ts_y > ts_thresh`（证据 3 L39） | **确认无误** |
| 时长 `b-a+1` **含空档** | 5超+2空+5超 → duration **12** | 合成实验 R 实测 **12** | **确认无误** |
| **跨年/跨段不切分** | 2001-12-28..2002-01-04 连续 8 天 → 1 事件 8 天 | `proto_event` 无年份分组，全程 `rle` | **确认无误** |
| **NaN 温度** | `x[isnan(vals)]=False` → 事件中间的 NaN 算 1 天空档（10 天连续中 1 天 NaN → 1 事件 10 天） | `t_series[is.na(ts_y), ts_y := ts_seas]` 后用 `!is.na(ts_y) & ts_y > ts_thresh`；因 `seas < thresh` 通常亦为非超标 | **确认无误（本数据 NaN 温度占比 0）** |
| **阈值 NaN** | Python：`arr > NaN` = False → 当作空档（3 天阈值 NaN 会把 30 天连续超标切成 2 个事件 15+12） | R：`TRUE & NA` → 判据为 NA，`rle` 中 NA 自成一段，`ex1$values == TRUE` 产生 NA 索引（行为未定义/未在本数据触发） | **未判定**（本数据阈值 NaN 仅出现在缓存 doy 366 行，占比 0.273%；R 产物阈值 NaN = 0%） |

阈值 NaN 统计：
```
{"t2m_XGHG_001(R产物)": nan_frac 0.0,
 "cache_t2m": nan_frac 0.002732 (=1/366 行), nan_rows [365],
 "cache_sst": nan_frac 0.002732,             nan_rows [365]}
```

---

## 5. E5 v1 / v2「模型侧 vs 观测侧」参数差异表

| 链路 | 检测器 | pctile | 窗口 | smoothPercentile | 气候期 | min_dur | max_gap | min_valid | 游程顺序 |
|---|---|---|---|---|---|---|---|---|---|
| **观测-海洋 MHW** | R `detect_events.R`（heatwaveR） | 90 | **11 天窗** | FALSE | 1983-2012 | 5 | 2 | **730** | 先过滤后桥接 |
| **观测-陆地 THW** | R `detect_events.R` | 90 | **11 天窗** | FALSE | 1983-2012 | 5 | 2 | **730** | 先过滤后桥接 |
| 模型 v1-海洋 MHW | Python `_detect_mhw_member` | 90 | **单日（无窗）** | n/a | 成员自身 2000-2021 | 5 | 2 | **无** | **先桥接后过滤** |
| 模型 v1-陆地 THW | R `detect_events.R` | 90 | 11 天窗 | FALSE | 2000-2021 | 5 | 2 | 730 | 先过滤后桥接 |
| 模型 v2-海洋 MHW | Python `_detect_mhw_member(thresh_ext)` | 90 | **单日（无窗）** | n/a | XGHG 3 成员池化 | 5 | 2 | **无** | **先桥接后过滤** |
| 模型 v2-陆地 THW | Python `_detect_thw_member_ext` | 90 | **11 天窗（写法有误，见 E1）** | n/a | XGHG 3 成员池化 | 5 | 2 | **无** | **先桥接后过滤** |

**`min_valid=730` 缺失的影响 = 0**：模型域 206 个配对点在 T2m/SST 上的有效日数
最少 **8029**（ALL 的 SST 因缺 2006-01-02 少 1 天）、其余 **8030**，
`< 730` 的点数在 **全部 6 条 (exp, member) 序列上均为 0**。故该门槛在模型路径上不会剔除任何点。

`phase6_cesm.py` 头部 docstring 声称"检测参数完全一致: pctile=90, 11 天窗(heatwaveR), min_dur=5, max_gap=2；
MHW 气候态 = 逐 dayofyear 单日 90 分位（与观测 load_data.calc_climatology 相同）"——
前半句与事实不符（MHW 无 11 天窗；游程顺序与 heatwaveR 相反），后半句本身也承认了与观测口径不同。

---

## 6. 附加发现（超出 E1–E5，但同属"检测语义/时间轴"，已实测）

### A1 `ALL_00x_T2m.nc` 时间轴在 12:00 → 掩码偏移 1 天

实测：
```
ALL : t0 = 2000-01-01 12:00:00    T2m 8030 天;  SST 8029 天（缺 2006-01-02）
XGHG: t0 = 2000-01-01 00:00:00    T2m 8030 天;  SST 8030 天
```
各事件表首行 `event_start` 与 `compound_events._event_daily_mask`（L48-49，`(event_start - t0).days`）
实际落点相对真实日历索引的偏移：

| exp | `mhw_*.csv` | `mhw_x_*.csv` | `thw_*.csv` | `thw_x_*.csv` |
|---|---|---|---|---|
| **ALL** | **−1 天** | **−1 天** | **−1 天** | **0 天** |
| XGHG | 0 | 0 | 0 | 0 |

（`thw_x_ALL_001.csv` 的 `event_start` 带 `12:00:00`，故 `(date−t0).days` 恰为整数、不偏移；
其余三张表的日期都在 00:00。）

**对复合日数的实测影响**（复刻 `cmd_compound` 口径，把 `t0` 换成 `t0.normalize()` 即"对齐"）：

| exp | 变体 | compound_days（实际） | compound_days（对齐） | 偏差 |
|---|---|---|---|---|
| ALL | v1 | 16756 | 16755 | −0.006% |
| **ALL** | **v2** | **63154** | **62191** | **+1.52%（多算 963 个复合点·日）** |
| XGHG | v1 | 15810 | 15810 | 0 |
| XGHG | v2 | 7313 | 7313 | 0 |

→ v1 下 THW 与 MHW 掩码**同向偏移**，几乎抵消；**v2 下 THW(x) 不偏移而 MHW(x) 偏移 → 陆海掩码错位 1 天**，
使 ALL 成员的 v2 复合日被高估约 **1.5%**。
（旁证：`ALL_001_T2m.nc` 的时间轴在 12:00 时，`DatetimeIndex.get_indexer` 对 00:00 的日期串
**匹配率 = 0.000**，必须归一化才能对齐——同一根因。）

### A2 `ALL_00x` 的 SST 拼接后缺 2006-01-02

`_load_sst_points` 把两段 POP 文件顺序 concat，第一段末 = 2006-01-01、第二段首 = 2006-01-03
→ **ALL 成员 SST 序列缺 2006-01-02**（8029 天，T2m 为 8030 天）。
后果：`_run_events` 把 2006-01-01 与 2006-01-03 当相邻日，跨该日的游程/duration 会偏差 1 天；
且 SST 轴与 T2m 轴在 2006-01-02 之后整体错位 1 个索引（对按索引对齐的下游有影响）。
量级：1 天 / 8030 天（0.012%），影响面为跨该日的个别事件。该条与 Lead 已确认的事实一致。

---

## 7. 与 Lead 独立实现的交叉核对

| 项 | Lead 独立测得 | 本审计测得 | 一致性 |
|---|---|---|---|
| t2m 缓存行内极差 = 0 | 是（全 366 行） | 是（365 个有效行，max ptp = 0.000） | ✅ 一致 |
| 复算 == 磁盘 npz | 逐位一致 | max diff = 0.000e+00 | ✅ 一致 |
| broken vs 正确 阈值差 mean | +7.93 | **+7.931** | ✅ 一致 |
| 正确阈值 mean | 13.43 °C | 13.426 °C | ✅ 一致 |
| broken 阈值 mean | 21.36 °C | 21.357 °C | ✅ 一致 |
| 逐点偏差极值 | 最冷点被抬高 +18.49、最暖点被压低 −2.86 | 某点被抬高 **+18.491**（p195）、某点被压低 **−2.873**（p14） | ✅ 量级一致（符号约定不同） |
| "只修 axis"仍有偏差 | mean +0.53、p95 +1.16 | mean **+0.531**、p90 0.977 | ✅ 一致 |
| ALL 001 THW 事件 崩溃 → 修正 | 6468 → 28552 | **6468 → 28466** | ⚠️ 崩溃值一致；修正值差 0.3%（参考实现细节不同） |
| ALL 001 超阈天数 崩溃 → 修正 | 79140 → 272469 | **92910 → 340750** | ⚠️ 绝对数差 17–25%（"超阈天数"定义/阈值实现细节不同）；**倍数 3.4× vs 3.67×，结论一致** |
| `proto_event` ③ 尾部空档被吸收 | 有 | **独立复核成立**（§3.3，heatwaveR 实测 duration 7 / 6） | ✅ 一致 |
| `_run_events` 与 heatwaveR 不等价 | 429/450 (95.3%) | **131/150 (87.3%)** @(5,2)；9 组 52–95% | ✅ 一致 |
| `proto_event` 逐行复刻 | 0/450 | **0/1350** | ✅ 一致 |
| 简单"先过滤后桥接" | 5/450 | C 变体 0–12/150（残差即尾空档） | ✅ 一致 |
| v2 ALL 复合日受影响 | — | **+1.52%**（本审计新增量化） | — |
| "POP SST 标签滞后 1 天" | 已否证 | 本审计**未涉及**该命题（A1 说的是 CAM T2m 的 12:00 时间轴与掩码索引，两者不同） | 采纳 Lead 结论，不写入 |

---

## 8. 修复建议（按优先级）

1. **P0 · E1**：`_pooled_threshold_t2m` 改为
   `stacked = np.concatenate([rows_of_doy[w] for w in win], axis=0)` —— 即**在窗内直接合并原始样本矩阵**
   （每行是 `(n_samples, nland)`），再 `np.nanpercentile(..., 90, axis=0)`；
   循环范围改为 `np.arange(1, 367)`，并把 doy 映射换成 heatwaveR 的 366 天规格化
   （非闰年 `doy>59 → +1`，Feb-29 槽用 `round(mean(相邻两日),2)` 填充）。
2. **P0 · E3**：`_run_events` 改为"先过滤后桥接"，并按 heatwaveR 的**头尾不对称**规则
   （只吸收尾部空档）。最稳妥的做法是**直接复用 R 链路**（`detect_events.R` 可传入外置阈值），
   或按 `proto_event` 逐行改写并用本审计的 1350 例模糊用例做回归。
3. **高 · E2**：模型侧 MHW 必须补 11 天窗（与 `detect_events.R` 对齐）；否则模型/观测 MHW 口径不可比。
4. **中 · A1/A2**：统一时间轴（把 ALL 的 T2m 归一到 00:00），并对 SST 段拼接做**日期重索引**
   （`reindex` 到完整日序列，缺日显式置 NaN），避免索引错位。
5. **低 · E4/E5**：`min_valid` 无影响可不补；但应在 Python 路径显式处理阈值 NaN 行（doy 366）。

## 9. 未判定 / 局限

- **阈值 NaN 下 heatwaveR 的行为**（`rle` 遇 NA 判据）：本数据未触发，未做隔离实验，判定为"未判定"。
- **`_pooled_threshold_*` 的设计本身**（用 XGHG 3 成员池化 + 应用到 ALL 成员）属归因方法学口径问题，
  不在 D-2 检测语义范围内，本报告不评价其对错。
- **A1/A2 的下游影响**只在复合日数上做了量化（A2）；对图 7 暴露时间与 FAR 的传播未展开（属其他任务）。
- `ALL_001` 的参考实现校验 max\|Δ\| 为 9.01e-03 °C（vs XGHG 的 9.96e-05），
  因 ALL 时间轴在 12:00，比较时需按日期归一化；该残差量级仍远小于任何结论所需精度。

---

*审计执行：detection-auditor（task-2）。全部数字可由 `results/phase6_audit_detect.R` + `results/phase6_audit_detect.py` 复算；
未修改 `python/` 与 `results/intermediate/cesm/` 下任何文件。*
