# Phase 6 审计修复：前后对比与验证证据（2026-09-23）

> 配套：`results/phase6审计报告.md`（问题清单）、四份分报告（`phase6审计_网格与配对.md` /
> `_检测语义.md` / `_基准期.md` / `_复合与统计.md`）。
> 原则：**先报告后改**；改动必须给出前后对比与可复算证据；**不覆盖**旧 P0 产物。

---

## 0. 改了什么

全部改动集中在 `python/phase6_cesm.py`（唯一被修改的代码文件）。

| 编号 | 修复 | 对照的审计结论 |
|---|---|---|
| F1 | `_run_events` 由「先桥接后过滤」改为**逐行复刻 `heatwaveR::proto_event`** | D-2 E3（P0） |
| F2 | `_pooled_threshold_t2m` 的 axis 崩溃 → 改为**逐点独立**求分位 | D-2 E1 / D-1 S-1 / D-3 C4（P0） |
| F3 | 阈值分位统一为 `ts2clm` 语义：**11 天窗内合并原始样本**再取分位（SST 此前完全无窗，T2m 此前是"分位的再分位"） | D-2 E1-b / E2 |
| F4 | 阈值缓存文件名带**成员名单 + 版本指纹**，并在读缓存时校验 `n_members` | D-3 C3 |
| F5 | `--members N` 改为作用于**全量 20 人名单**，越界显式报错 | D-3 C2（P0） |
| F6 | 新增 `--loo`（leave-one-out），对每个成员剔除自身建阈 | D-3 C1 / `PHASE_B` 步骤 2b |
| F7 | bootstrap **不再静默丢弃 `inf`**；`0/0 → nan`；用**次序统计量**求经验分位数（避免 inf−inf→nan）；输出 inf 比例与两套 CI | D-4 S10 / S12 |
| F8 | 日期原点统一 `.normalize()`（消除 ALL 组 MHW 掩码早 1 天） | D-4 S6 / D-2 A1（Lead 确证） |

**未改（属口径决策，不是代码错误，已在报告中登记待用户拍板）**：归因阈值用 62/78/72 vs 128；
主口径 `med_mean` vs `med_max`；Phase 6 复合定义（论文模型 Methods `paper_text.txt:546` 用
"fully encompasses"，代码用 L477 共超标）；doy=366 行；20 成员 bootstrap 分层块。

---

## 1. 核心验证：`proto_event` 等价性（F1）

**方法**：把事件逻辑与阈值计算解耦——自建一个带 `thresh` 列的"气候态"数据框（`temp∈{0,1}`，
`thresh=0.5`）直接喂 `heatwaveR::detect_event(minDuration, maxGap)`，与 Python 实现比对事件数与
各事件时长。

```
# 权威实现
Rscript -e "cat(deparse(heatwaveR:::proto_event), sep='\n')"
```

| 实现 | 模糊用例不一致数 | 备注 |
|---|---|---|
| 旧 `_run_events`（先桥接后过滤） | **429 / 450**（95.3%） | Lead，150 随机序列 × 3 组参数 |
| 「先过滤后桥接 + gap ≤ maxGap」近似 | 5 / 450 | 差别在**尾部空档** |
| **新 `_run_events`（`proto_event` 逐行复刻）** | **0 / 450** | Lead |
| 新实现（detection-auditor 独立复跑 9 组参数） | **0 / 1350** | 独立互证 |

手工边界用例（R 权威 vs 复刻，全部一致）：

| 序列 | heatwaveR `duration` | 新实现 |
|---|---|---|
| 5超 + 2天空档（到序列末） | `[7]` | `[7]` |
| 2天空档 + 5超（序列首） | `[5]` | `[5]` |
| 5超 + 1空 + 5超 | `[11]` | `[11]` |
| 5超+2空+1超+2空+5超 | `[5, 5]` | `[5, 5]` |
| 3超 + 2空 + 3超 | `[]` | `[]` |

⇒ **头尾不对称**（吸收尾部空档、不吸收首部空档）是 heatwaveR 的真实语义，已实现。
复算：`python results/phase6_audit_lead_check7.py`、`Rscript results/phase6_audit_lead_check.R`。

---

## 2. 核心验证：T2m 阈值 axis 崩溃（F2/F3）

```
python -c "import numpy as np; z=np.load(r'results/intermediate/cesm/thresh_t2m_xghg.npz'); t=z['thresh']; print(t.shape, np.nanmax(t,1)-np.nanmin(t,1))"
```

| 项 | 旧（崩溃） | 新（逐点 11 天窗合并） |
|---|---|---|
| `thresh` 行内极差 | **恒为 0**（206 陆点共用一条曲线） | 逐点不同（空间标准差中位 5.92 °C） |
| 阈值 mean | 21.36 °C | 13.43 °C |
| 阈值 mean\|Δ\| | — | **8.26 °C**（p90 16.45，max 24.65） |
| 系统性方向 | 最冷点被抬高 **+18.49 °C**、最暖点被压低 **−2.86 °C** | — |
| ALL 001 超阈率（南欧 <40N / 北欧 >60N） | 12.8% / **0.0%** | 6.3% / 6.5% |

复算：`python results/phase6_audit_lead_check.py`、`results/phase6_audit_lead_check2.py`。

---

## 3. 端到端前后对比（3 成员 P0，同一套代码、两个 tag）

命令（**新旧产物并存**，旧 `_x` 一个字都没被覆盖）：

```powershell
# 旧口径（崩溃阈值 + 先桥接后过滤 + MHW 无 11 天窗）
python python\phase6_cesm.py attrib --members 3 --tag _x
# 新口径（本轮修复）
python python\phase6_cesm.py detect   --baseline xghg --members 3 --tag _x2
python python\phase6_cesm.py compound --members 3 --tag _x2
python python\phase6_cesm.py attrib   --members 3 --tag _x2
```

### 3.1 事件数与暴露时间

| 量 | 旧 `_x` | 新 `_x2` | 变化 |
|---|---|---|---|
| THW 事件 ALL 001 / 002 / 003 | 6,468 / 6,468* / 6,468* | **18,185 / 20,037 / 18,750** | ~2.9× |
| THW 事件 XGHG 001 / 002 / 003 | 3,746 / 3,718 / 3,435 | **6,042 / 6,483 / 6,862** | ~1.7× |
| MHW 事件 ALL 001 | 17,111 | 16,416 | −4% |
| MHW 事件 XGHG 001 | 6,862 | 5,470 | −20%（11 天窗生效） |
| 复合暴露 ALL 001 / 002 / 003 | 63,154 / 75,581 / 78,973 | **122,282 / 150,090 / 134,485** | ~1.8× |
| 复合暴露 XGHG 001 / 002 / 003 | 7,313 / 7,658 / 9,532 | **10,099 / 13,715 / 19,492** | ~1.6× |
| **THW 的 ALL/XGHG 事件比** | **1.73** | **3.01** | 强迫信号**未被阈值缺陷掩盖** |
| 22 年总暴露比 ALL/XGHG | 8.88 | 9.39 | +5.7% |

\* 旧 `_x` 各成员事件数不同，此处按 `exposure_members_x.csv` 口径列示；精确值见该 CSV。

### 3.2 归因指标（这是论文最大的科学主张）

| 阈值口径 | 旧 `_x` | 新 `_x2` |
|---|---|---|
| **med_mean = 20.7 天**（区域均值，论文口径更像这个） | PR=**∞**、FAR=nan（P_fix=0，**1000/1000 bootstrap 为 inf**） | PR=**52.0**、FAR=**0.981**（P_fix=0.015；344/1000 inf；90% CI 含 inf 时上界 **inf**、仅有限样本 [16.3, 57.0]） |
| **med_max = 128 天**（格点极值） | PR=**48.0**、FAR=**0.979**、CI [14.7, 53.0]（**372/1000 inf 被静默丢弃**） | PR=**∞**、FAR=nan（P_fix=0，**1000/1000 inf**） |

**结论（必须写进报告与后续规划）**：

1. `复现报告.md` §11.6 的 **`PR=48.0 / FAR=0.98` 是"阈值缺陷 + 格点极值阈值(128 天)"的产物**：
   修复检测层后，该阈值下反事实世界一次都没达到 128 天 ⇒ **P_fix=0，PR 发散**，该数字**不可再用**。
2. 修复后**可判读的阈值下移到 ~20 天**：PR≈52、FAR≈0.98 —— 与论文 `FAR=0.95` **仍然同方向同量级**，
   但**不是同一个量**（阈值口径不同：20.7 天是本复现的区域均值，论文是 62/78/72）。
3. 旧报告写的 "CI 14.7-53.0" 是 **PR 的 CI 且丢弃了 372/1000 的 inf 重复**；
   修复后同一处同时给出「保留 inf」与「仅有限样本」两套区间。
4. ⇒ **P0 的方向性结论（GHG 强迫显著提高复合热浪暴露、FAR 接近 1）在修复后依然成立，且信号更强
   （THW 的 ALL/XGHG 事件比从 1.73 升到 3.01）；但绝对数字全部作废，20 成员全量必须用修复后的代码跑。**

产物：`results/figures/fig7_p0_validation_x.png`（旧）与 `fig7_p0_validation_x2.png`（新），
日志 `results/intermediate/audit/lead/fix_v3_{detect,compound,attrib}.log`。

---

## 4. 回归基线

```
python python\verify_data.py     # 期望：All data files present and valid.
```

旧 P0 产物完整性：`results/intermediate/cesm/` 下**既有文件全部保留**
（`thw_x_*.csv` / `mhw_x_*.csv` / `annual_x_*.csv` / `exposure_members_x.csv` /
`thresh_*_xghg.npz` mtime 仍为 2026-09-19）；新产物一律用 `_x2` 后缀与
`*_v3_w11_loo_<members>.npz` 新缓存名。
