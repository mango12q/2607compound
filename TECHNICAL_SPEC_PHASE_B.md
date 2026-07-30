# 阶段 B 技术规范：归因分析（图 3、图 4）

## B.1 阶段目标

使用 CESM1-LE 大型集合（ALL 强迫 20 成员 + FixGHG 20 成员）进行归因分析，计算 FAR 和 PR，使用 1000 成员 bootstrap 估计不确定性，输出图 3（FAR/PR 曲线）和图 4（重现期变化）。

## B.2 数据清单

| 数据集 | 路径 | 大小 | 格式 |
|--------|------|------|------|
| CESM1-LE ALL | `F:\2607compound\data\CESM1-LE\ALL\`（20 个 .nc 文件） | ~200 GB | NetCDF |
| CESM1-LE FixGHG | `F:\2607compound\data\CESM1-LE\FixGHG\`（20 个 .nc 文件） | ~200 GB | NetCDF |

**注意**: 本阶段是磁盘压力最大的环节，开始前请确认磁盘空闲空间 ≥ 420 GB。

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
- 对每个成员重复阶段 A 的 MHW 和 THW 检测流程
- 需要将检测逻辑封装为可对单个成员调用的函数
- 输出每个成员的 compound_events（建议保存为 per-member 的 NetCDF 或汇总为一个大表）
- **注意**: 40 个成员 × 40 年数据，检测耗时较长，建议并行化

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

### 步骤 4：1000 成员非参数自助法（Bootstrap）

**涉及文件**: `python/attribution.py`

**函数要求**:
```python
def single_bootstrap_iteration(all_data, fixghg_data, threshold, all_members, fixghg_members, n_all=20, n_fixghg=20) -> Tuple[float, float]:
    """单次 bootstrap：有放回抽样成员，计算 FAR 和 PR"""

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
- 抽样：`np.random.choice(members, size=n, replace=True)`
- 概率计算：`p = (annual_days >= threshold).sum() / annual_days.size`
- FAR/PR 公式：`FAR = 1 - P_factual / P_counterfactual`，`PR = P_factual / P_counterfactual`
- 除零保护：`P_counterfactual <= 0` 时 `FAR=1`, `PR=inf`
- 并行：`joblib.Parallel(n_jobs=n_jobs, backend='loky', verbose=5)`
- 中间保存：每 100 次迭代保存一次 `pickle.dump`
- 置信区间：5% 和 95% 分位数

### 步骤 5：计算重现期变化

**函数要求**:
```python
def calc_return_period(all_data, fixghg_data, thresholds) -> Dict[str, np.ndarray]:
    """
    计算重现期 = 1 / 概率
    返回: {
        'thresholds': thresholds,
        'return_period_ALL': (n_thresh,),
        'return_period_FixGHG': (n_thresh,),
    }
    """
```

### 步骤 6：导出 .mat 供 MATLAB 绘图

**输出文件**: `results/intermediate/bootstrap_results.mat`

**变量清单**:

| MATLAB 变量名 | 维度 | 说明 |
|--------------|------|------|
| `thresholds` | (n_thresh,) | 阈值数组（如 10, 15, 20, ..., 95 天） |
| `FAR_mean` | (n_thresh,) | FAR 均值 |
| `FAR_ci_lower` | (n_thresh,) | FAR 5% 分位 |
| `FAR_ci_upper` | (n_thresh,) | FAR 95% 分位 |
| `PR_mean` | (n_thresh,) | PR 均值 |
| `PR_ci_lower` | (n_thresh,) | PR 5% 分位 |
| `PR_ci_upper` | (n_thresh,) | PR 95% 分位 |
| `return_period_ALL` | (n_thresh,) | 全强迫重现期 |
| `return_period_FixGHG` | (n_thresh,) | FixGHG 重现期 |

## B.4 阶段 B 的 MATLAB 绘图代码

**涉及文件**: `matlab/fig3_attribution.m`、`matlab/fig4_return_period.m`

### `matlab/fig3_attribution.m`

```matlab
function fig3_attribution(thresholds, FAR_mean, FAR_ci, PR_mean, PR_ci)
% fig3_attribution — 图 3: FAR/PR 归因曲线
%
% 布局:
%   a: FAR - European Coastlines（含 5-95% CI 填充）
%   b: PR - European Coastlines（含 5-95% CI 填充）
%   c: FAR - Mediterranean & Black Sea（标注 2003/2022/2023 观测事件）
%   d: PR - Mediterranean & Black Sea
%
% Output: results/figures/fig3.pdf
%
% 实现要求:
% - fill() 绘制置信区间带，FaceAlpha=0.3
% - 标注观测事件垂直线（2003: 红色, 2022: 绿色, 2023: 黑色）
% - ylim([0, 1.05]) for FAR plots
```

### `matlab/fig4_return_period.m`

```matlab
function fig4_return_period(return_thresholds, return_period_ALL, return_period_FixGHG)
% fig4_return_period — 图 4: 重现期对比
%
% 布局:
%   a: 沿海海洋热浪重现期（ALL vs FixGHG）
%   b: 沿海陆地热浪重现期（ALL vs FixGHG）
%   c: 复合热浪重现期（ALL vs FixGHG）
%
% Output: results/figures/fig4.pdf
%
% 实现要求:
% - bar() 绘制 ALL，hold on + plot() 绘制 FixGHG 虚线
% - legend('ALL', 'FixGHG', 'Location', 'northwest')
```

## B.5 阶段 B 的验证标准

| 验证项 | 期望值 | 容差 | 验证方法 |
|--------|--------|------|----------|
| FAR 曲线单调性 | 随阈值递增 | - | 目视检查 |
| PR 曲线单调性 | 随阈值递增 | - | 目视检查 |
| 2022 年地中海 FAR | 0.95 | ±0.02 | 对比 Table 1 |
| Bootstrap 样本数 | 1000 | - | 检查输出数组维度 |
| 重现期 ALL > FixGHG | - | - | 物理意义验证 |

## B.6 阶段 B 的磁盘管理

**⚠️ 数据清理由用户手动执行，必须用户确认当前阶段完成才能进入下一阶段。**

画完图 3、图 4 并与原文目视比对一致后，**由用户手动删除**以下原始数据：
- `F:\2607compound\data\CESM1-LE\ALL\` 下全部 20 个 `.nc` 文件（释放 ~200 GB）
- `F:\2607compound\data\CESM1-LE\FixGHG\` 下全部 20 个 `.nc` 文件（释放 ~200 GB）

**必须保留**:
- `results/intermediate/bootstrap_results.mat`（< 1 GB）
- `results/figures/fig3.pdf`、`fig4.pdf`
