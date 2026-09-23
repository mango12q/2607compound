# Phase 6 审计报告 · 复合与统计（task-4 / D-4）

> **审计对象**：`python/phase6_cesm.py` 的 `cmd_compound`（L483-540）、`_annual_per_pair`（L546-569）、
> `_obs_annual_threshold`（L572-588）、`_pr_boot`（L591-613）、`cmd_attrib`（L616-691）；
> 对照 `python/compound_events.py`（`identify_compound_events` / `_pair_maps` / `_event_daily_mask`）、
> `config.py`（`N_BOOTSTRAP=1000` L108、`CI_ALPHA=(0.05,0.95)` L109）与论文 `results/paper_text.txt`。
> **审计日期**：2026-09-23　|　**审计员**：baseline-stats-auditor　|　**数据**：CESM1-LE P0 成员 001-003（全量 20 成员未跑）
> **复算脚本**：`results/phase6_audit_stats.py`（阶段 i1 / i1b / i2 / i3 / i4）
> **产物目录**：`results/intermediate/audit/stats/`；**只读** `python/` 与 `results/intermediate/cesm/`（未做任何写入）

> **命名说明**：本文用 **XGHX** 指代反事实组（ALL-but-GHG / FixGHG 世界），数据与文件名中的实验名是 **XGHG**（如 `XGHG_001_T2m.nc`、`mhw_x_XGHG_001.csv`）——两者指同一实验；写代码/路径时必须用 XGHG。

---

## 0. 结论速览

| 编号 | 结论 | 分类 | 严重度 |
|---|---|---|---|
| **S1** | `cmd_compound` 确实 import（L485）并调用（L504）`compound_events.identify_compound_events`（共超标口径）；其输出段天数与 `exposure_members_x.csv` 的 `compound_days` **6/6 成员逐值一致** | 【确认无误】 | — |
| **S2** | 键空间一致：MHW 事件表 lat/lon_idx ∈ POP 海索引（277-365 / 26-87）= `pairs.ocean_*_idx`；THW ∈ f09 陆索引（⊂ 0-44 / 0-50）= `pairs.land_*_idx`。12 张事件表**无一越界** | 【确认无误】 | — |
| **S3** | `_pair_maps` 206 个陆键（= 配对数，无键覆盖/丢失）；191 个唯一海键，15 个海点被 2 个陆点共用（多对一，符合论文 L518） | 【确认无误】 | — |
| **S4** | `_event_daily_mask` 的 `t0/nt` 取自同成员 T2m 文件（= `cmd_compound` 的 time_da）⇒ 对齐口径自洽；但**索引映射本身有两个缺陷**（S5、S6） | 【确认无误】 | — |
| **S5** | **noleap 日期被按公历做差**：`(event − t0).days` 会把闰年 2/29 计入 ⇒ 索引累积漂移 +6 天（2000-2021 有 6 个闰年）。表现为**右端静默截断**：`max_e` 达 8034/8035 而 `nt−1 = 8029`，每个成员 1-5 个事件被整段丢弃、13-196 个事件被裁尾 | 【有问题】 | 中 |
| **S6** | **【P1·已确证】ALL 组 MHW 掩码整体早 1 天**：`ALL_{m}_T2m.nc` 时间原点 t0 = 2000-01-01 **12:00**（AWS 成品）、`XGHG_{m}_T2m.nc` t0 = **00:00**（raw CAM 裁剪件）；`_detect_mhw_member` 的事件时刻继承 **SST** 轴（00:00），`_detect_thw_member_ext` 继承 **T2m** 轴（ALL 12:00 / XGHX 00:00）；`cmd_compound` 用 `t0 = t2m.time.values[0]`（ALL 12:00）给两张掩码取索引 ⇒ `floor((D 00:00 − t0 12:00)/1天) = D−1`，ALL 组 THW 索引正确而 **MHW 掩码早 1 天**，XGHX 组两者都正确。量化（显式原点 `(date−2000-01-01).days` 重算）：ALL 001/002/003 复合日 63154→**62191**（−1.52%）/75581→**74707**（−1.16%）/78973→**78045**（−1.18%），等量转入 standalone（+963/+874/+928）；XGHX 三成员**逐位不变**；THW(配对) 日不变 ⇒ 只动陆–海交叉那一层。PR(128 天) 48.0→47.0。**这是代码级一致性缺陷（同码对两组不同时间原点），不是标签语义问题** | 【有问题·已确证】 | **P1** |
| **S7** | 暴露口径：`_annual_per_pair` 给 4 列，`cmd_attrib` 只用 `med_mean`/`med_max`；**样本 = 成员×年 = 66（20 成员时 440）**，"区域年暴露池化 440 模型年"在**样本构造上满足**；但**论文阈值对应的聚合口径应是区域暴露（med_mean 一类），不是格点极值（med_max）** | 【有问题】 | 中高 |
| **S8** | 观测阈值 128 天（`med_max` 口径）与论文 Fig.3c 的 62/78/72 **不是同一聚合量**：我们的 2022 各口径为 med_mean 20.7 / p90 43.2 / p95 75.0 / max 128；2003：14.1/40/53/73；2023：37.7/**72.0**/96.6/171 ⇒ 论文值落在 p90~max 之间，**无单一聚合口径可复现**（与 `复现报告.md` §6 的已知残差一致） | 【有问题】 | 高 |
| **S9** | 公式方向正确：论文 Eq.3 `PR = P_ALL/P_fix`（L566）、Eq.2 `FAR = 1 − P_fix/P_ALL`（L561）；代码 `pr = p_all/p_fix`（L596-600）、`far = 1 − 1/point ≡ 1 − p_fix/p_all`（L612，数值恒等已验证） | 【确认无误】 | — |
| **S10** | **丢弃 inf 严重压低 CI**：med_max 口径 1000 次里有 **372 次（37.2%）为 inf** 被 `boots[np.isfinite]` 丢弃，剩下的给出 [14.67, 53.0]；二项精确（Clopper-Pearson）区间为 **[8.9, 1050]**，上界差 20 倍。med_mean 口径 **1000/1000 全为 inf** ⇒ CI = nan | 【有问题】 | 高 |
| **S11** | 独立重采样**符合论文描述**（L585-587 "sampling with replacement from the original data ... for both climates"），但**忽略模型年自相关/成员结构**：成员 block、成员内分层、成员内 5 年移动块三种对照的 CI 略宽（med_max：[19.5,54.0] / [15.6,53.0] / [16.7,54.0] vs 现状 [14.67,53.0]）；3 成员下差异不显著，**20 成员时应改用分层/块 bootstrap** | 【有问题】 | 中 |
| **S12** | `p_all = 0 且 p_fix = 0` 时 `pr()` 返回 **inf**（只判 `p_fix == 0`）⇒ v1 的 128 天口径（"两组均无样本"）被打印成 **PR=∞ / FAR=nan**，误导为"风险无限"；数学上应为未定义 | 【有问题】 | 中 |
| **S13** | **CI 标签错误**：`_pr_boot` 的 lo/hi 是 **PR 的 5–95% 分位**（L610 作用于 `boots`=PR 重复），但 `复现报告.md` L40/L349 写成 "FAR = 0.98（bootstrap 90% CI 14.7-53.0）"（FAR∈[0,1]，14.7 不可能是 FAR 的 CI）；`cmd_attrib` **根本不计算 FAR 的 CI** | 【有问题】 | 中（文档） |
| **S14** | `_pr_boot` docstring（L592）写"返回 (PR, FAR, lo, hi)"，实际 `return point, far, lo, hi, boots`（L613）**返回 5 个** | 【有问题】 | 低 |
| **S15** | `far = nan` 时 `f"{far:.2f}"` **不抛错**，输出字符串 `'nan'`（最小用例实测）——任务书假设的"会抛错"不成立 | 【确认无误】 | — |
| **S16** | 点估计 vs bootstrap 中位数：med_max 口径 点估计 PR=48.0 vs 有限重采样中位数 **45.0**（−6%），一致；med_mean 口径两者都退化（∞） | 【确认无误】 | — |
| **S17** | **P0 数字复算**：22 年总暴露均值比 v2 = **8.885**（报告 8.88）、v1 = **1.002**（报告 1.00）；PR/FAR：v2 med_max = **48.0 / 0.9792 / CI [14.67, 53.0]**（报告 48.0 / 0.98 / 14.7-53.0 ✓）、v2 med_mean = ∞/nan（fig7 标题 ✓）、v1 med_mean = **1.0 / 0.00**（fig7 标题 ✓）、v1 med_max = ∞/nan（fig7 标题 ✓） | 【确认无误】 | — |

**一句话**：复合链路的**接线是对的**（S1-S4、S9、S17 全部复现既有产物），
但有三个必须分开处理的问题——① 抽样/假设层面：inf 被丢弃使 CI 失去意义（S10）、p=0/0 被当成 ∞（S12）、CI 标签写错（S13）；
② 口径层面：论文阈值对应的聚合口径是区域暴露而非格点极值（S7/S8）；
③ 索引层面：noleap→公历漂移导致尾部静默截断（S5）与 ALL/XGHG 组间 1 天不一致（S6）。

---

## 1. I1 复合链路（`identify_compound_events` 复用与参数语义）

### I1.1 复用为真（**S1**，确认无误）

复算：`python results/phase6_audit_stats.py i1` → `i1_structure.json` / `i1_identify_vs_exposure.csv`

- 文件:行证据：`phase6_cesm.py` **L485** `from compound_events import (identify_compound_events, _pair_maps, _event_daily_mask,)`；
  **L504** `comp = identify_compound_events(mhw, thw, pairs_df, time_da.time)`
  （注意：传入的是 `time_da.time` 这个**坐标 DataArray**——`identify_compound_events` 内部用 `time.values[0]` 取 t0，
  传数据本体（温度数组）会取到温度值。这一细节实现正确，见下）。
- 一致性交叉验证：把既有 v2 事件表喂给 `identify_compound_events`，其输出段的**天数合计**与
  `exposure_members_x.csv` 的 `compound_days` **6/6 成员相等**（63154/75581/78973/7313/7658/9532），
  说明 `cmd_compound` 里两套写法（`identify_compound_events` 与紧随其后的掩码求和）口径一致。

### I1.2 键空间一致（**S2**，确认无误）

| 侧 | 取值范围（实测 12 张事件表 + pairs） | 判定 |
|---|---|---|
| `pairs.ocean_lat_idx / ocean_lon_idx` | 277-365 / 26-87（POP 网格索引） | — |
| `mhw_x_{ALL,XGHG}_*.csv` 的 `lat_idx / lon_idx` | 277-365 / 26-87 | ⊂ 海索引 ✓ |
| `pairs.land_lat_idx / land_lon_idx` | 0-44 / 0-50（f09 大气网格索引） | — |
| `thw_x_*.csv` 的 `lat_idx / lon_idx` | 0-22 / 5-50（⊂ 陆索引） | ⊂ 陆索引 ✓ |

⇒ `identify_compound_events` 里 `ocean_mask`（键 = MHW 表的 (lat_idx,lon_idx)）与
`land_pair_dict` 的值（= pairs 的 (ocean_lat_idx,ocean_lon_idx)）**在同一坐标空间**，不存在静默错配。

### I1.3 `_pair_maps` 的多对一（**S3**，确认无误）

206 个陆键 = 206 个配对（陆点唯一，**无键覆盖**）；191 个唯一海键，其中 15 个海点被 2 个陆点共用（最大重数 2）。
这与论文 L517-518 一致（"Each coastal land grid cell are therefore matched to a single unique ocean grid cell …
multiple land cells could share the same adjacent ocean cell"）。字典以陆点为键，故多对一不会丢键。

### I1.4 `t0/nt` 与事件日期：**P1 已确证——ALL 组 MHW 掩码早 1 天**（**S6**），另有 noleap 漂移（**S5**）

复算：`i1_event_bounds.csv`（对 18 张事件表逐事件算 `s=(start−t0).days`、`e=(end−t0).days`）

| 组 | 文件样例 | t0 时刻 | 事件时刻 | n | 全在界内 | 左裁 | 右裁 | 整段丢弃 | min_s | max_e |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | `mhw_x_ALL_001.csv` | **12:00** | 00:00 | 17111 | 16921 | **16** | 174 | 0 | **−1** | 8034 |
| ALL | `thw_x_ALL_001.csv` | 12:00 | 12:00 | 6468 | 6453 | 0 | 14 | 1 | 0 | 8035 |
| XGHG | `mhw_x_XGHG_001.csv` | 00:00 | 00:00 | 6862 | 6835 | 0 | 25 | 2 | 0 | 8035 |
| XGHG | `thw_x_XGHG_001.csv` | 00:00 | 00:00 | 3746 | 3745 | 0 | 0 | 1 | 1 | 8035 |

#### （P1【已确证】）ALL 组 MHW 掩码早 1 天：三处 t0 不一致

**机理**（我实测 + lead 独立复现，结论一致）：

1. 时间原点不同：`ALL_{m}_T2m.nc` 的 t0 = **2000-01-01 12:00:00**（来自 AWS 成品
   `TREFHT_all_{m}_2000-2021_europe.nc`，units `days since 2000-01-01 12:00:00`）；
   `XGHG_{m}_T2m.nc` 的 t0 = **2000-01-01 00:00:00**（来自 raw CAM 裁剪件）。
2. 事件表各自继承自己序列的时间轴：`_detect_thw_member_ext` 的事件时刻来自 **T2m** 轴
   （ALL 为 `D 12:00`，XGHX 为 `D 00:00`）；`_detect_mhw_member` 的事件时刻来自 **SST** 轴（两组都是 `D 00:00`）。
3. `cmd_compound`（L499）与 `_annual_per_pair`（L553）都用 `t0 = pd.Timestamp(t2m.time.values[0])`
   ——ALL 组即 **12:00**——给**两张掩码**取索引。于是
   `floor((event D 00:00 − t0 D0 12:00)/1 天) = (D − D0) − 1`：**ALL 组 MHW 掩码整体早 1 天**，
   而 THW 掩码（12:00 对 12:00）正确；XGHX 组两者都正确。

**量化**（对既有 v2 事件表改用显式原点 `index = (date − 2000-01-01).days` 重算；与"ALL 组 MHW +1 天"等价）：

| 成员 | compound（现状 → 修正） | 变化 | standalone | THW(配对) |
|---|---|---|---|---|
| ALL 001 | 63,154 → **62,191** | **−1.52%**（−963） | 15,976 → 16,939（+963） | 79,130（不变） |
| ALL 002 | 75,581 → **74,707** | **−1.16%**（−874） | 14,695 → 15,569（+874） | 90,276（不变） |
| ALL 003 | 78,973 → **78,045** | **−1.18%**（−928） | 12,385 → 13,313（+928） | 91,358（不变） |
| XGHG 001/002/003 | **逐位不变** | 0 | 不变 | 不变 |

（`compound + standalone = THW(配对)` 恒等保持，说明只是共超标交叉那一层错位；PR(med_max,128 天) 48.0 → **47.0**。）

**含义**：归因的**分子（ALL 组暴露）被系统性低估 1.2-1.5%**，而分母（XGHX 组）不受影响
⇒ 现状 PR/FAR 是**保守偏低**方向；更严重的是**两组口径不可比**（同一个 `_event_daily_mask` 对两组用了不同原点）。
**修法**：`cmd_compound` 统一用"该成员 T2m 日期序列的日期部分（00:00）"作 origin，或先对 `event_start/event_end`
做 `.normalize()`；两类事件表也应在写出前统一时刻约定。

#### （P2）noleap→公历漂移导致尾部静默截断（**S5**）

`nt = 8030`（2000-2021 noleap），但 `max_e` 可达 **8035**：`_event_daily_mask` 用 pandas 的**绝对时刻差**取索引，
而 noleap 解码成 datetime64 后按**公历**做差（6 个闰年的 2 月 29 日虽无数据却被计入），索引最大漂移 **+6 天**。
后果：2021-12 下旬的事件被 `min(b, nt−1)` **静默压到最后一天**（右裁 13-196 个/成员），
完全越界的事件被整段丢弃（1-5 个/成员，约 0.03%）。两组受同样漂移，相对对齐不变，但年末尾段会被压缩/丢失。
修法同 P1（改用日期/序号索引）。

## 2. I2 暴露时间口径与统计单元

### I2.1 样本 = 66（20 成员时 440）：**结构上满足**，口径需选（**S7**，中高）

- 复算：`i2_unit_and_threshold.json`。`_annual_per_pair` 输出 `year, med_mean, med_max, eur_mean, eur_max`；
  `cmd_attrib` 只用 `med_mean` 与 `med_max`（L653），样本由 `glob(annual{tag}_{exp}_*.csv)` 拼成
  **3 成员 × 22 年 = 66**（20 成员时 2×440 中的 440/组）——与论文 L548-551「pooling the exposure time …
  across 20 ensemble members … 440 model years」的**统计单元一致**（区域→年→池化）。
- **哪个列对应论文口径？** `med_mean`（Med 框 64 个配对点的**区域平均**年复合天数）。
  理由：论文 Fig.3c/d 的横轴是"an observed exposure duration of compound events over the Mediterranean & Black Sea"
  （L235-236），即**区域暴露时间**；`med_max` 是**格点极值**，属另一种量纲。
- 现状的实际使用是**双口径都算、但结论只引用 med_max**（§11.6 的 PR=48/FAR=0.98），
  而 med_mean 口径在 3 成员下 `P_fix = 0` ⇒ PR=∞ 不可判读。**这是"口径与样本量两头不讨好"的组合**。
- 年份归属：`years = time_da.time.dt.year.values` ⇒ **22 个唯一年份 2000-2021**（每年 365 天，noleap）✓。

### I2.2 区域框（确认无误，但需声明密度差）

- `land_lat.between(30,47) & land_lon.between(5,42)`：**CESM 64/206 对 = 31.1%**（唯一海点 61）；
  观测 `coastal_pairs.csv` 同框 **615/2039 = 30.2%**。
- 该框即 fig1j 的"地中海 & 黑海"框（config L103）；黑海（lon 28-42, lat 40-47）在内，
  但 `lon ≥ 5` **排除西班牙地中海东岸/巴利阿里**——与论文 Fig.3c 的"Mediterranean & Black Sea"大体一致，
  与 Fig.3a/b 的"European coastlines"（全部 206 对）不同（代码注释未明确这一点）。
- ⚠️ **密度不可比**：观测 615 个 0.25° 点 vs 模型 64 个 1° 点，`med_mean` 的"区域平均"在两套网格上不是同一个统计量
  （这是 `复现报告.md` §6 记录的口径残差在归因侧的延伸）。

### I2.3 观测阈值：128 天属于**口径错配**（**S8**，高）

复算：`i2_unit_and_threshold.json`；`_obs_annual_threshold()` 实测 `med_mean(2022)=20.721951`、`med_max(2022)=128.0`。

| 年 | 论文 Fig.3c 参考线 | 本复现 med_mean | p90 | p95 | med_max |
|---|---|---|---|---|---|
| 2003 | **62**（红） | 14.11 | 40.0 | 53.0 | 73.0 |
| 2022 | **78**（绿） | 20.72 | 43.2 | 75.0 | 128.0 |
| 2023 | **72**（黑） | 37.65 | **72.0** | 96.6 | 171.0 |

⇒ 论文的三个参考值落在本复现的 **p90–max 之间**（2023 恰好等于 p90=72，2022 接近 p95=75），
**没有任何单一聚合口径能同时复现 62/78/72**。因此：
- 用 `med_max(2022)=128` 当阈值 **不是论文口径**（论文阈值是区域暴露天数；且论文自己的 Supplementary Fig. S1
  色标上限为 50 天/格点，说明 78 天不可能是单格值——见 `复现报告.md` §6.3）；
- 128 天又把检验推到**最深的尾部**，在 66 个模型年里 `P_fix = 1/66`，PR 的方差极大（见 §3.2）。

---

## 3. I3 FAR / PR / bootstrap

### 3.1 公式方向（**S9**，确认无误）

论文（`paper_text.txt` 行号）：
- L559-563：`FAR = 1 − P^days_fixGHG / P^days_ALL`（Eq.2）
- L565-568：`PR = P^days_ALL / P^days_fixGHG`（Eq.3）
- L585-589："1000 bootstrapped datasets by sampling with replacement from the original data … for both climates …
  5–95% confidence intervals were derived from the 0.05 and 0.95 quantiles"

代码：`pr = p_all/p_fix`（L595-600）、`far = 1 − 1/point`（L612）——数值验证 `1−1/PR ≡ 1−p_fix/p_all`（相等，`i3_formulas.json`）✓ 方向正确。
`CI = (0.05,0.95)`（config L109）⇒ 取 [5,95] 分位 ⇒ **90% CI**，与论文 5–95% 一致 ✓。

### 3.2 inf 的处理：**丢弃 inf 使 CI 失去意义**（**S10**，高）

复算：`i3_bootstrap.csv`（`python results/phase6_audit_stats.py i3`）

| 口径 | 阈值 | P_ALL | P_fix | 点估计 PR | 点估计 FAR | inf 次数/1000 | 丢弃 inf 后 CI | 有限重采样中位数 | Clopper-Pearson PR 区间 |
|---|---|---|---|---|---|---|---|---|---|
| med_mean | 20.72 天 | 0.818 | **0/66** | **∞** | nan | **1000（100%）** | nan–nan | — | [16.3, ∞) |
| med_max | 128 天 | 0.727 | 1/66 | 48.0 | 0.979 | **372（37.2%）** | [14.67, 53.0] | 45.0 | **[8.9, 1050]** |

- 机制：`boots[np.isfinite(boots)]`（L609）直接删掉"反事实世界一次都没发生"的重采样——这正是归因里最强的证据。
- 后果：med_mean 口径 CI 直接变 nan（`fig7_p0_validation_x.png` 左下面板空白即此）；
  med_max 口径的上界被压到 53.0，而二项精确区间给出 **1050**（差约 20 倍）。
- 建议：保留 inf 语义（上界记 ∞），或对 `p_fix` 用 Clopper-Pearson/加性平滑（Agresti-Coull）后再算比值。

### 3.3 bootstrap 结构与自相关（**S11**，中）

现有做法（L604-607）：ALL 与 XGHX **各自独立**按"模型年"有放回重采样（n=66）。
这与论文 L585-587 的描述一致（对两个气候各自从原始数据重采样），**不是偏离**；
但"模型年"在同一成员内高度自相关（22 个连续年），i.i.d. 年会低估不确定性。三种对照（同 seed=42，1000 次）：

| 变体 | med_max 口径 CI | med_mean 口径 CI |
|---|---|---|
| 现状（i.i.d. 年，两组独立） | [14.67, 53.0] | nan（1000 inf） |
| 成员 block（3 个成员有放回） | [19.5, 54.0] | nan |
| 成员内分层（每成员内 22 年各自重采样） | [15.6, 53.0] | nan |
| 成员内 5 年移动块 | [16.7, 54.0] | nan |

⇒ 3 成员下差异不显著（下界 +1~+5），因为主宰不确定性的仍是"尾部一次都没发生"；
**但 20 成员时成员内自相关会显现**，届时建议用"成员内分层 + 年块"bootstrap 作为主口径并做对照。

### 3.4 其它实现问题

- **S12（p_all=0 且 p_fix=0 → PR=inf，中）**：`pr()` 只判 `p_fix == 0`（L598-600）。
  v1 的 128 天口径两组都是 0/66，被打印成 `PR=∞ FAR=nan`（`fig7_p0_validation.png` 右上标题），
  实际是 **0/0 未定义**，不应表述为"风险无限"。最小用例：`P6._pr_boot(1000, [1,2,3], [1,2,3])` → `PR=inf, FAR=nan`。
- **S13（CI 标签错误，中／文档）**：`_pr_boot` 的 `lo, hi` 是 **PR** 的 5/95 分位（L610 作用于 PR 重复序列 `boots`）；
  `cmd_attrib` L660-662 打印 `PR={prs} FAR={far:.2f} (bootstrap CI {lo:.1f}-{hi:.1f})`；
  `复现报告.md` **L40** 写"PR=48.0、FAR=0.98（90% CI 14.7-53.0）"、**L349** 写"FAR = 0.98（bootstrap 90% CI 14.7-53.0）"——
  把 PR 的 CI 挂在了 FAR 上（FAR∈[0,1]，14.7 不可能是 FAR 的 CI）。**`cmd_attrib` 从未计算 FAR 的 CI**，这是文档层面的口径错误。
- **S14（docstring 与返回值不符，低）**：L592 写"返回 (PR, FAR, lo, hi)"，L613 实际 `return point, far, lo, hi, boots`（5 个）。
- **S15（nan 格式化，确认无误）**：`far = nan` 时 `f"{far:.2f}"` → `'nan'`，**不抛异常**（实测）。
- **S16（点估计 vs bootstrap 中位数，确认无误）**：med_max 48.0 vs 45.0（−6%）；med_mean 两者均 ∞/nan。

---

## 4. I4 复算 P0 数字（**S17**，与报告/图逐一对齐）

复算：`i4_recompute.csv`、`i4_ratios.json`；数据源为 `results/intermediate/cesm/` 既有产物（只读）。

| 指标 | 报告/图上的值 | 本次独立复算 | 判定 |
|---|---|---|---|
| v2 22 年总暴露均值比 | 8.88（`复现报告.md` L349） | **8.885**（ALL 72569.3 / XGHG 8167.7） | ✓ |
| v1 22 年总暴露均值比 | 1.00（L340：ALL 17795 / XGHG 17761） | **1.002**（17795.3 / 17761.0） | ✓ |
| v2 `med_max` PR / FAR / CI | 48.0 / 0.98 / 14.7-53.0 | **48.000 / 0.9792 / [14.667, 53.0]**（372/1000 inf） | ✓（CI 属 PR，见 S13） |
| v2 `med_mean` PR / FAR | fig7 标题 `PR=∞ FAR=nan` | **∞ / nan**（1000/1000 inf） | ✓ |
| v1 `med_mean` PR / FAR | fig7 标题 `PR=1.0 FAR=0.00` | **1.0 / 0.000**（CI [0.0, 2.0]，344 inf） | ✓ |
| v1 `med_max` PR / FAR | fig7 标题 `PR=∞ FAR=nan`（报告：两组均无样本） | **∞ / nan**（P_ALL=0、P_fix=0 ⇒ 实为 0/0，见 S12） | ✓（但表述误导） |

**与文字对齐的结论**：`复现报告.md` §11.6（L336-349）的**数字全部可复算**，无编造；
唯一需要修订的是 ① CI 的归属标签（S13），② 把"PR=48/FAR=0.98"与论文 FAR=0.95 并列对照的写法——
前者是 128 天阈值（且是 T2m 轴崩溃版的结果，见 task-3 报告 C6），后者是 78 天阈值，**不同阈值不可并列**。

---

## 5. 建议

| # | 动作 | 位置 | 理由 |
|---|---|---|---|
| **G1** | bootstrap 保留 inf（上界记 ∞）或对 p_fix 做连续性校正后算比值 | `_pr_boot` | S10；现状上界被压 20 倍 |
| **G2** | `p_all == 0 and p_fix == 0` 返回 `nan` 而不是 `inf`；打印时区分"未定义"与"发散" | `_pr_boot` L598-600 | S12 |
| **G3** | 补算 **FAR 的 CI**（对 PR 重复序列做 `1−1/pr` 变换后取分位），并修正报告 L40/L349 的标签 | `cmd_attrib` + `复现报告.md` | S13 |
| **G4** | 把主口径切到**区域暴露**（`med_mean`，必要时加面积权重），`med_max` 只作敏感性；论文阈值 62/78/72 的对应聚合必须在报告里写明不可复现（§6 已定稿） | `cmd_attrib` | S7/S8 |
| **G5** | 20 成员时用"成员内分层 + 年块"bootstrap 作主口径并保留 i.i.d. 对照 | `_pr_boot` | S11 |
| **G6** | `cmd_compound` 统一 origin（T2m 日期部分 00:00）或先 `.normalize()`；`_event_daily_mask` 改用日期/序号索引（不用绝对时刻差） | `phase6_cesm.py` L499/L553 + `compound_events._event_daily_mask` | **P1 已确证**（ALL 组 MHW 早 1 天，−1.2~1.5%）+ S5 漂移 |
| **G7** | 修正 `_pr_boot` docstring（5 个返回值） | L592 | S14 |

---

## 6. 局限

1. 仅 3 成员 P0（全量未下载，任务书禁止下载/全量跑）⇒ 所有 PR/CI 的尾部计数都受 66 样本限制（`P_fix ∈ {0,1}/66`），
   本报告不对"归因强度"下任何数值结论。
2. 未运行 `cmd_compound`/`cmd_attrib` 本体（会写 `results/intermediate/cesm/`），全部以**读取既有产物 + 复刻同一逻辑**的方式复算；
   复刻的忠实性由 I4 与 S1 的逐值一致保证。
3. 未评估观测侧 `annual_compound_days.nc` 的生成链路（属 Phase 1-3 范围）；本报告只把它当作给定的阈值来源。
4. `-1 天/±1 天` 的对齐敏感性是在**既有事件表**上做日期平移，未重跑检测；平移只影响掩码落位，不改变事件本身的判定。

---

## 附录 · 产物与复算命令

```powershell
cd D:\2607compound
python results\phase6_audit_stats.py i1    # §1 结构与键空间、t0/nt 越界审计
python results\phase6_audit_stats.py i1b   # §1.4 掩码位移敏感性（组间不一致）
python results\phase6_audit_stats.py i2    # §2 口径/区域框/观测阈值
python results\phase6_audit_stats.py i3    # §3 公式/inf/bootstrap 变体
python results\phase6_audit_stats.py i4    # §4 复算 P0 数字
```

| 产物（`results/intermediate/audit/stats/`） | 内容 |
|---|---|
| `i1_structure.json` / `i1_event_bounds.csv` / `i1_identify_vs_exposure.csv` | 复用证据、键空间、逐事件越界审计、段天数一致性 |
| `i1b_alignment.csv` | 掩码 ±1 天位移的复合日/PR 变化 |
| `i2_unit_and_threshold.json` | 样本量、年份、区域框、观测各聚合口径 |
| `i3_bootstrap.csv` / `i3_formulas.json` | inf 比例、四种 bootstrap 变体、Clopper-Pearson、公式与 docstring 证据 |
| `i4_recompute.csv` / `i4_ratios.json` | P0 比值与 PR/FAR 复算 |
| `verify_c11.py` / `verify_lag.py` / `recon.py` | C11 复核（CAM `date`/`time_bnds`）与侦察脚本 |
