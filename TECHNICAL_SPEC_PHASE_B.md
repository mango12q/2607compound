# 阶段 B 技术规范：归因分析（图 3、图 4）

## B.1 阶段目标

使用 CESM1-LE 大型集合（ALL 强迫 20 成员 + FixGHG 20 成员）进行归因分析，计算 FAR 和 PR，使用 1000 成员 bootstrap 估计不确定性，输出图 3（FAR/PR 曲线）和图 4（重现期变化）。

## B.2 数据清单

| 数据集 | 路径 | 大小 | 格式 |
|--------|------|------|------|
| CESM1-LE ALL | `data/CESM1-LE/raw/`（`b.e11.B20TRC5CNBDRD.f09_g16.{id}.pop.h.nday1.SST.*` + AWS `TREFHT`）+ `proc/` 裁剪件 | 全量 ~750 GB | NetCDF |
| CESM1-LE XGHG（= 论文 FixGHG） | `data/CESM1-LE/raw/`（`b.e11.B20TRLENS_RCP85.f09_g16.xghg.{id}.{cam.h1.TREFHT,pop.h.nday1.SST}.*`，两段式 1920–2005 / 2006–2080） | 同上 | NetCDF |

> ⚠️ **命名修正**：不存在 `CESM1-LE/ALL/` 与 `CESM1-LE/FixGHG/` 目录，
> 也没有 `B20TRC5CNBDRD.FixGHG` 这种文件名。本书的 "FixGHG" 一律指 **XGHG** 单强迫实验。
> 详见 `DATA_REQUIREMENTS.md` 数据集 5。

**注意**: 本阶段是磁盘压力最大的环节，全量 20 成员 proc 子集约 100 GB
（raw 全量约 800 GB，不推荐）。当前进度：成员 001–003 已就位（raw 109 GB + proc 14 GB）。

## B.3 处理流程（7 个步骤）

### 步骤 1：加载 CESM1-LE 数据

**涉及文件**: `python/config.py`、`python/load_data.py`

**函数要求**:
```python
def load_cesm1le_member(member_id: str, forcing: str, filepath=None) -> xr.Dataset:
    """
    加载单个 CESM1-LE 成员
    返回: (time, lat, lon) Dataset，含 T2m (K) 和 SST (K)
    """

def load_cesm1le_dir(forcing: str) -> xr.Dataset:
    """
    使用 xr.open_mfdataset 加载整个目录（所有成员）
    返回: (member, time, lat, lon) Dataset
    """
```

**技术细节**:
- 使用 `xr.open_mfdataset(pattern, chunks={'time': 365, 'member': 1}, combine='nested', concat_dim='member', parallel=True)`
- 变量名映射：`TREFHT → T2m`，`TEMP`（取 `lev=0`）→ `SST`
- 单位：原始为 K，标注 `units='K'`
- 成员 ID：`001`–`020`

### 步骤 2：逐成员热浪检测

**涉及文件**: `python/detect_mhw.py`、`python/detect_thw.R`、`python/compound_events.py`

**技术细节**:
- 对每个成员重复阶段 A 的 MHW 和 THW 检测流程（海陆同一份 `heatwaveR` 代码）
- **规模**: 20 个 ALL 成员 + 20 个 XGHG 成员 = **40 个模拟**，每个成员取 22 年（2000–2021）
  → 每组 **440 个成员-年**（= 论文的 440 模型年）；两组共 880 个成员-年
- ⚠️ **模型侧检测基准期见步骤 2b**（不能沿用观测的 1983–2012）
- 输出每个成员的 compound_events（建议保存为 per-member 的 NetCDF 或汇总为一个大表）
- **注意**: 检测耗时较长（P0 实测 27 s/成员，全量 40 成员约 20 min + I/O），建议并行化

### 步骤 2b：模型侧检测基准期（⚠️ 论文未明示，口径已定）

论文正文只给出**观测**的气候态 1983–2012；CESM 分析时段是 **2000–2021**，
**无法**用 1983–2012 建立模型侧阈值。

**✅ 已定主口径（2026-09-23 用户确认）**：

> **XGHG 集合合并反事实基准 + leave-one-out**
> 把**除当前被检测成员外**的全部 XGHG 成员的 2000–2021 日值合并池化，
> 计算逐 dayofyear 90 分位阈值（SST 逐 doy 池化；T2m 按 heatwaveR 11 天窗语义合并池化），
> 再对 ALL 与 XGHG 两组分别检测。

**为什么是 leave-one-out**：把被检测成员自身也放进阈值池（in-sample）会
**保守偏高**地放大 PR。P0 阶段（3 成员）未做剔除，正式版必须剔除后再跑。

**必须保留的敏感性对照**：
- **ALL 自身 2000–2021 气候态** —— 会**构造性抵消** GHG 趋势信号
  （P0 v1 实测 PR ≈ 1.0，几乎无量级），因此**不可作主口径**，仅作反例对照留档。
- 现行 in-sample 版（P0）结果保留，用于说明 leave-one-out 的修正幅度。

**落地要求**：
1. `python/phase6_cesm.py` 的阈值构造需支持 `exclude_member` 参数（✅ **2026-09-23 已实现**：
   CLI = `python python\phase6_cesm.py detect --baseline xghg --loo --members N`；池按成员剔除自身，
   缓存名带成员名单指纹 `thresh_{sst,t2m}_xghg_v3_w11_loo_<members>.npz`）。
   3 成员实测：LOO 使 XGHG 复合暴露 +4.2%/+11.0%/+29.1%，阈值 |Δ| 均 0.07–0.12 °C（SST）/0.24 °C（T2m）。
   **注意**：3 成员下 LOO 后池只剩 2 个，成员数噪声会高估影响；20 成员时（19 vs 20）小得多。
   详见 `results/phase6审计_基准期.md`。
2. 三项口径（leave-one-out / in-sample / ALL 自身）的 PR-FAR 曲线需同图对比并写入复现报告。
3. 本节口径与理由必须同步进 `results/复现报告.md` 的偏差清单。

> 实现参考：`python/phase6_cesm.py` 的 `cmd_prepare` / `cmd_pairs` / `cmd_detect`
> （`thresh` 构造见该文件 L292/L324/L330/L358 附近）。

### 步骤 3：识别复合热浪并计算年度天数

**涉及文件**: `python/compound_events.py`、`python/calc_chr.py`

**函数要求**:
```python
def calc_annual_compound_days(compound_events, time, lat, lon) -> xr.DataArray:
    """计算每个成员每年的复合热浪天数 (member, year, lat, lon)"""
```

**技术细节**:
- 按成员分组计算年度天数
- 输出维度：`(member, year, lat, lon)`
- 进入 bootstrap 前，先按目标区域（欧洲全岸 / 地中海&黑海）聚合为**区域年暴露时间**
  `(member, year)`——论文的统计样本是"模型-年"，不是"格点-年"

### 步骤 4：1000 成员非参数自助法（Bootstrap）

**涉及文件**: `python/attribution.py`

**函数要求**:
```python
def single_bootstrap_iteration(all_exposure, fixghg_exposure, threshold) -> Tuple[float, float]:
    """单次 bootstrap：有放回抽样模型年（440 池化样本），计算 FAR 和 PR"""

def bootstrap_FAR_PRC(all_data, fixghg_data, thresholds, n_bootstrap=1000, n_jobs=-1) -> Dict[str, np.ndarray]:
    """
    并行 bootstrap 计算 FAR/PR 曲线
    返回: {
        'thresholds': thresholds,
        'FAR_mean': (n_thresh,),
        'FAR_ci_lower': (n_thresh,),
        'FAR_ci_upper': (n_thresh,),
        'PR_mean': (n_thresh,),
        'PR_ci_lower': (n_thresh,),
        'PR_ci_upper': (n_thresh,),
        'FAR_all_samples': (n_bootstrap, n_thresh),
        'PR_all_samples': (n_bootstrap, n_thresh),
    }
    """
```

**技术细节**:
- 抽样：对**池化的区域年暴露样本**（20 成员 × 22 年 = 440 模型年/组）有放回重采样：
  `np.random.choice(exposure, size=exposure.size, replace=True)`
- 概率计算：`p = (区域年暴露时间 >= threshold).sum() / 440`（样本 = 模型年，非格点-年）
- FAR/PR 公式（论文 Eq.2/3）：`FAR = 1 - P_counterfactual / P_factual`（= 1 − P_FixGHG/P_ALL），
  `PR = P_factual / P_counterfactual`
- 除零保护：`P_counterfactual <= 0` 时 `FAR=1`, `PR=inf`
- 并行：`joblib.Parallel(n_jobs=n_jobs, backend='loky', verbose=5)`
- 中间保存：每 100 次迭代保存一次 `pickle.dump`
- 置信区间：5% 和 95% 分位数

### 步骤 5：GEV 重现期分析（图 4a–c）

**论文口径**（Methods "Return level and period estimation using GEV"）：
1. 对 FixGHG 区域年暴露序列去缺测后做 **1000 次有放回 bootstrap**，每次 **MLE 拟合 GEV**，
   求出 **5/10/20/50/100 年**重现水平 → 报告**中位数 + 2.5–97.5% CI**。
2. 将 FixGHG 各重现水平映射为 ALL 的**等效重现期**；对 ALL 重复 bootstrap 估计不确定性。
3. 图 4 三个面板分别对应 **a 沿海海洋热浪天数、b 沿海陆地热浪天数、c 复合 MHW-THW 天数**
   （地中海 & 黑海）——需要三类事件的年暴露序列，不能只算复合。

**函数要求**（详细规范见 `TECHNICAL_SPEC.md` §3.9b）:
```python
def fit_return_levels(annual_values, n_bootstrap=1000, seed=42) -> dict:
    """FixGHG 年值 → {5/10/20/50/100 年: median + 2.5/97.5% CI}"""

def map_return_period(all_annual, return_levels, n_bootstrap=1000, seed=43) -> dict:
    """FixGHG 重现水平 → ALL 等效重现期（含 bootstrap CI）"""
```

**⚠️ 置信区间区分**: 图 3（FAR/PR 曲线）用 **5–95%**；图 4（重现期）用 **2.5–97.5%**。
config 中 `CI_ALPHA=(0.05,0.95)` 与 `GEV_CI=(0.025,0.975)` 并存，勿混用。

### 步骤 6：保存中间结果 —— ⬜ **导出 .mat 已弃用**

> **状态：作废**。项目已切换 Python (matplotlib) 出图，`matlab/` 目录不存在，
> 不再导出 `.mat`。改为 pickle/NetCDF 落盘：

**实际输出**: `results/intermediate/bootstrap_results.pkl`（`pickle.dump`）
与 `results/tables/table1.csv`（⬜ Table 1 待补，见下）

**原 MATLAB 变量清单（存档，仅作字段命名参照）**:

| 变量名 | 维度 | 说明 |
|--------------|------|------|
| `thresholds` | (n_thresh,) | 阈值数组（如 10, 15, 20, ..., 95 天） |
| `FAR_mean` | (n_thresh,) | FAR 均值 |
| `FAR_ci_lower` | (n_thresh,) | FAR 5% 分位 |
| `FAR_ci_upper` | (n_thresh,) | FAR 95% 分位 |
| `PR_mean` | (n_thresh,) | PR 均值 |
| `PR_ci_lower` | (n_thresh,) | PR 5% 分位 |
| `PR_ci_upper` | (n_thresh,) | PR 95% 分位 |
| `gev_return_levels_FixGHG` | (5,) | FixGHG 5/10/20/50/100 年重现水平（中位数） |
| `gev_return_levels_FixGHG_ci` | (5, 2) | 对应 2.5/97.5% CI |
| `gev_return_period_ALL` | (5,) | ALL 等效重现期（中位数） |
| `gev_return_period_ALL_ci` | (5, 2) | 对应 2.5/97.5% CI |

## B.4 阶段 B 的绘图代码 —— ⬜ **MATLAB 版已弃用，仅作对照**

> **状态：作废**。实际用 Python (matplotlib) 出图，`matlab/` 目录不存在。
> 下方代码**不要执行**；面板定义（a–d / a–c）已按论文 Fig.3、Fig.4 caption 核对无误，
> 保留供实现 `python/fig3_attribution.py` / `python/fig4_return_period.py` 时对照。

**涉及文件**: `matlab/fig3_attribution.m`、`matlab/fig4_return_period.m`

### `matlab/fig3_attribution.m`

```matlab
function fig3_attribution(thresholds, FAR_mean, FAR_ci, PR_mean, PR_ci)
% fig3_attribution — 图 3: FAR/PR 归因曲线
%
% 布局 (2x2):
%   a: FAR - European coastlines      (y 线性 0-1)
%   b: PR  - European Coastlines      (y **对数** 1e0-1e3)
%   c: FAR - Mediterranean & Black Sea（标注 2003/2022/2023 观测事件）
%   d: PR  - Mediterranean & Black Sea（y **对数**；含年份标注）
%
% 轴标签（按论文原图）:
%   x: "Thresholds (Compound heatwave days)"   0-100
%   y: "Fraction of Attributable Risk (FAR)" / "Probability Ratio (PR)"
%
% Output: results/figures/fig3.pdf
%
% 实现要求:
% - fill()/fill_between 绘制置信区间带，alpha=0.3；图例两项：FAR/PR 与 Uncertainty
% - **PR 面板必须用对数 y 轴**（论文原图 1e0-1e3；PR 在高阈值发散到 1e3 以上）
% - 仅 c/d 面板加三条观测阈值垂直线（2003 红=62 / 2022 绿=78 / 2023 黑=72），
%   a/b（欧洲全岸）不加
% - ylim([0, 1.05]) for FAR plots
% - PR 在阈值 >85 后发散：需按 §3.9 的除零保护返回 inf，并在图上断开或截断到轴上限
```

### `matlab/fig4_return_period.m`

```matlab
function fig4_return_period(return_thresholds, return_period_ALL, return_period_FixGHG)
% fig4_return_period — 图 4: 重现期对比
%
% 布局 (1x3，按论文原图):
%   a: "Coastal Marine Heatwave Days"
%   b: "Coastal Terrestrial Heatwave Days"
%   c: "Coastal Marine-Terrestrial Heatwave Days"
%
% 轴（按论文原图，**双对数**）:
%   x: "Return Period in FixGHG forcing"   5/10/20/50/100   **对数**
%   y: "Return Period in ALL forcing"      **对数 (1e0-1e2)**
%
% Output: results/figures/fig4.pdf
%
% 实现要求（对照 pdf_extract/fig4_p06.png）:
% - bar() 绘制 ALL 重现期（浅蓝 #A8D5F0 类）
% - **绿色虚线的语义 = 1:1 参考线**：因 x 轴本身就是 FixGHG 重现期，
%   画 (x, x) 即"无变化"基准。**不要再画第二条 FixGHG 数据曲线**。
% - **每根柱必须带：误差棒 + 两个数字标注（CI 上下界）**；论文原图即如此
% - **panel c 需红色竖线 + "Gap: <值>" 文字**（论文原图为 Gap: 44.8 @50年、92.1 @100年）
% - 图例：'Return Period in FixGHG'（绿虚线）、'Return Period in ALL'（浅蓝柱）
```

## B.5 阶段 B 的验证标准

> 锚点来自论文正文 **与 `pdf_extract/fig4_p06.png` 原图读出**（读图精度约 ±5%）。
> 完整对照见 `results/图1图2与论文原图目视比对.md` §四。

| 验证项 | 期望值 | 容差 | 验证方法 |
|--------|--------|------|----------|
| FAR 曲线单调性 | 随阈值递增 | - | 目视检查 |
| PR 曲线单调性 | 随阈值递增（对数轴） | - | 目视检查 |
| 图3a FAR 饱和阈值（欧岸） | 阈值 >90 天处饱和于 1.0 | - | 对比正文 |
| **图3c FAR @62（2003）** | **0.72** | ±0.03 | 对比 Table 1 / 原图 |
| **图3c FAR @78（2022）** | **0.95** | ±0.03 | 对比 Table 1 |
| **图3c FAR @72（2023）** | **0.78** | ±0.03 | 对比 Table 1 |
| Bootstrap 样本数 | 1000 | - | 检查输出数组维度 |
| 重现期 ALL < FixGHG（强迫下事件更频繁） | - | - | 物理意义验证 |
| **图4a 海洋** FixGHG 5/10/20/50/100 年 → ALL | **2.1 / 3.3 / 5.5 / 11.5 / 20.7** 年 | ±20% | 对比原图（正文明示 11.5 与 20.7） |
| **图4b 陆地** 同上 | **1.2 / 1.3 / 1.6 / 2.1 / 2.8** 年 | ±20% | 对比原图（正文 100 年 = 3.2 [2.8–3.8]） |
| **图4c 复合** 同上 | **1.6 / 2.0 / 2.6 / 3.5 / 5.0** 年 | ±25% | 对比原图（正文 100 年 = 8 [5–12]） |
| **图4c Gap 标注** | 50 年 ≈ **44.8**；100 年 ≈ **92.1** | ±20% | 对比原图（正文"up to 92 years"） |
| **Table 1**（地中海&黑海，5–95% CI） | 2003/62d：FAR 0.72 [0.64–0.80]、PR 4.1 [2.8–7.2]；2022/78d：FAR 0.95 [0.93–1.0]、PR [6–∞)；2023/72d：FAR 0.78 [0.7–0.88]、PR 8 [4–10] | FAR ±0.02 / PR ±20% | 对比 Table 1 |

> ⚠️ **Table 1 产出缺口**：`TECHNICAL_SPEC.md` §2 的目录树里列了 `table1_attribution.py`，
> 但 B.3 的 7 个步骤中没有它的位置。**正式版必须补一步**：用三个观测阈值
> （62 / 78 / 72 天）在 FAR/PR 曲线上取样，输出 `results/tables/table1.csv`。
> 注意 2022 的 PR 上界为 **∞**（反事实概率为 0），需按 `calc_PR` 的除零保护写成 `inf` 而非数值。

## B.6 阶段 B 的磁盘管理

**⚠️ 数据清理由用户手动执行，必须用户确认当前阶段完成才能进入下一阶段。**

画完图 3、图 4 并与原文目视比对一致后，**由用户手动删除**以下原始数据：
- `data/CESM1-LE/raw/` 下全部全时段原始文件（释放 ~800 GB 全量；当前 P0 为 109 GB）
- `data/CESM1-LE/proc/` 下的中间裁剪件（可保留轻量子集）

**必须保留**:
- `results/intermediate/bootstrap_results.pkl`（< 1 GB）
- `results/tables/table1.csv`
- `results/figures/fig3.pdf`、`fig4.pdf`
