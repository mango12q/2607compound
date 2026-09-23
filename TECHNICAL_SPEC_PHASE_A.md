# 阶段 A 技术规范：观测分析（图 1、图 2）

## A.1 阶段目标

使用 OISST 和 E-OBS 数据完成海洋热浪（MHW）和陆地热浪（THW）检测，识别沿海复合热浪事件，计算 CHR 和共现概率，输出图 1（空间分布+时间序列+共现概率）和图 2（CHR 对比）。

## A.2 数据清单

| 数据集 | 路径 | 大小 | 格式 |
|--------|------|------|------|
| OISST v2.1 全球合并 | `D:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc` | 23.1 GB | NetCDF |
| OISST v2.1 欧洲裁剪 | `D:\2607compound\data\OISST\oisst_v2.1_eur_1983_2023.nc` | 1.1 GB | NetCDF |
| E-OBS tg 合并 | `D:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc` | 0.5 GB（14975 天） | NetCDF |
| E-OBS tg 分段原始 | `D:\2607compound\data\E-OBS\tg_ens_mean_0.25deg_reg_*.nc` × 3 | ~0.5 GB | NetCDF |

**注意**: OISST 与 E-OBS 纬度栅格均含 0.25°，但经度/纬度轴不完全重合；
本项目用 **KDTree 最近邻 + 0.5° 上限**（`MAX_GRID_DIST_DEG`）做陆点→海点配对，
不做重采样（实测 2039 对 / 1434 个唯一海洋格点）。数据盘经 NTFS Junction
`D:\2607compound\data` → `E:\2607compound\data` 访问。

## A.3 处理流程（8 个步骤）

### 步骤 1：数据加载

**涉及文件**: `python/config.py`、`python/load_data.py`

**函数要求**:
```python
def load_oisst(filepath=None) -> xr.Dataset:
    """加载 OISST v2 日度 SST，统一坐标为 (time, lat, lon)，变量名为 SST"""

def load_eobs(filepath=None) -> xr.Dataset:
    """加载 E-OBS 日度 T2m，统一坐标为 (time, lat, lon)，变量名为 T2m"""
```

**技术细节**:
- 使用 `xarray.open_dataset(..., chunks={'time': 365})` 惰性加载
- OISST 坐标名 `latitude/longitude` 需 rename 为 `lat/lon`
- E-OBS 变量名 `tg` 需 rename 为 `T2m`
- 单位标注：SST 和 T2m 均为 `degC`

### 步骤 2：计算气候学阈值

**涉及文件**: `python/load_data.py`

**函数要求**:
```python
def calc_climatology(da: xr.DataArray, clim_period: tuple = (1983, 2012)) -> xr.DataArray:
    """
    计算逐日 90 百分位阈值
    返回: (dayofyear, lat, lon) DataArray
    """
```

**技术细节**:
- 筛选气候期数据：`da.sel(time=slice("1983-01-01", "2012-12-31"))`
- 逐日分组：`clim_data.groupby('time.dayofyear').quantile(0.9, dim='time')`

### 步骤 3：海洋热浪检测（⚠️ 已切换为 R 链路）

**涉及文件**: `python/detect_events.R`（正式）／`python/detect_mhw.py`（DEPRECATED，仅单格点核验）

**调用约定（实际签名）**:
```bash
Rscript python/detect_events.R <nc_file> <varname> <output_csv> \
        <clim_start> <clim_end> [domains_file|-] [min_dur] [max_gap] [n_workers] [work_dir]

# 例:
Rscript python/detect_events.R data/OISST/oisst_v2.1_eur_1983_2023.nc sst \
        results/intermediate/mhw_events_R.csv 1983 2012
```

**技术细节**:
- 海陆共用同一份 `heatwaveR` 检测代码：`pctile=90, windowHalfWidth=5, minDuration=5, maxGap=2`
- ⚠️ `smoothPercentile = FALSE`（偏离两包默认 TRUE/31 天窗，理由见 `TECHNICAL_SPEC.md` §3.4）
- MHW 只检测**沿海配对涉及的 1434 个唯一海洋格点**
- 输出经 `results/globalize_mhw_idx.py` 把裁剪件局部索引换算回全球 OISST 索引
  → `results/intermediate/mhw_events_R_global.csv`

<details>
<summary>历史设计（Python marineHeatWaves，DEPRECATED）</summary>

```python
def detect_mhw_grid(sst: xr.DataArray, clim_period: tuple, duration: int = 5, gap: int = 2) -> pd.DataFrame:
    """单格点 MHW 检测，返回事件 DataFrame"""

def detect_mhw_all_grids(sst: xr.DataArray, clim_period: tuple) -> pd.DataFrame:
    """全网格 MHW 检测，合并所有事件"""

def mhw_events_to_daily(events: pd.DataFrame, time, lat, lon) -> xr.DataArray:
    """将 MHW 事件表转换为日度二值场 (time, lat, lon)"""
```

- `marineHeatWaves.detect()` 接口：`temp, t, clim_temp, duration, gap`
- 时间转换：`t = (time_dt - np.datetime64('1970-01-01')).astype(int)`
- 事件表字段：`event_start`, `event_end`, `duration`, `lat`, `lon`, `lat_idx`, `lon_idx`
</details>

### 步骤 4：陆地热浪检测

**涉及文件**: `python/detect_events.R`（正式）／`python/detect_thw.R`（**已归档，勿重跑**）

**调用约定（实际签名）**:
```bash
Rscript python/detect_events.R <nc_file> <varname> <output_csv> \
        <clim_start> <clim_end> [domains_file|-] [min_dur] [max_gap] [n_workers] [work_dir]

# 例（陆地，域限配对点）:
Rscript python/detect_events.R data/E-OBS/EOBS_tg_1983_2023.nc T2m \
        results/intermediate/thw_events_R_v2.csv 1983 2012 \
        results/intermediate/domains_ocean_pairs.csv 5 2 12
```

**技术细节**:
- 依赖包：`heatwaveR`, `ncdf4`, `doParallel`, `foreach`
- 与步骤 3 共用同一份检测代码（海陆口径一致），参数：
  `pctile=90, windowHalfWidth=5, minDuration=5, maxGap=2`，
  ⚠️ `smoothPercentile=FALSE`（偏离两包默认，见 `TECHNICAL_SPEC.md` §3.4）
- E-OBS 合并件的变量名为 `T2m`，坐标名为 `lat` / `lon`（原始分段文件才是 `latitude`/`longitude`）
- 输出文件：`results/intermediate/thw_events_R.csv`（**CSV，非 .rds**）
- Python 调用：`python/detect_thw_wrapper.py` → `subprocess.run([RSCRIPT_PATH, ...])`

### 步骤 5：构建沿海格点配对

**涉及文件**: `python/coastal_mask.py`

**函数要求（已按实际签名更正）**:
```python
def build_land_mask(eobs: xr.Dataset) -> xr.DataArray:
    """从 E-OBS 构建陆地掩码（非 NaN 区域）"""

def build_ocean_mask(sst: xr.DataArray) -> xr.DataArray:
    """从 OISST 构建海洋掩码（非 NaN 区域）"""

def find_coastal_grid_pairs(land_mask, ocean_mask, *,
                            max_dist_deg=MAX_GRID_DIST_DEG,
                            save_path=COASTAL_PAIRS_CSV) -> pd.DataFrame:
    """KDTree 最近邻识别沿海格点对；返回带 dist_deg 的 DataFrame 并落盘 CSV"""

def get_grid_pair_info(pairs, lat, lon) -> pd.DataFrame:   # 历史接口
    """将配对列表转换为 DataFrame，含 lat_idx/lon_idx 和 lat/lon"""
```

**技术细节**:
- 4-连通结构定"沿海陆点"：`s = generate_binary_structure(2, 4)`；
  陆地边缘 = `land_arr & ~binary_erosion(land_arr, structure=s)`
- 配对规则（论文 Methods）：每个沿海陆点配 **1 个最近**海洋格点，
  距离上限 `MAX_GRID_DIST_DEG = 0.5°`；多个陆点可共享同一海点
- 输出文件：`results/intermediate/coastal_pairs.csv`（实测 2039 对 / 1434 唯一海点）
  —— **不是** `coastal_pairs.nc`

### 步骤 6：识别复合热浪事件

**涉及文件**: `python/compound_events.py`

**函数要求**:
```python
def is_event_contained(thw_start, thw_end, mhw_start, mhw_end) -> bool:
    """判定 MHW 是否完全涵盖 THW: mhw_start <= thw_start AND mhw_end >= thw_end"""

def identify_compound_events(mhw_events, thw_events, grid_pairs) -> pd.DataFrame:
    """识别复合事件，每个 THW 只匹配第一个涵盖它的 MHW"""

def compound_events_to_daily(compound_events, time, lat, lon) -> xr.DataArray:
    """复合事件 → 日度二值场 (time, lat, lon)"""

def calc_standalone_days(thw_events, mhw_events, grid_pairs, time, lat, lon) -> xr.DataArray:
    """计算独立 THW 天数（THW 期间无任何重叠 MHW）"""
```

**技术细节**:
- ⚠️ **实现现状（方案 B）**：`python/compound_events.py` 实现的是**逐日共超标**
  （论文 L502-503 "simultaneously exceed"），用于图1a–i / 图1m / 图2；
  图1 j–l 曲线另用 **MHW 包络**（论文 L505-506 "fully encompasses"），
  由 `python/fig_jkl_mhw_envelope.py` 预计算 → `results/tables/fig_jkl_envelope.json`。
  `is_event_contained`（下）为事件级涵盖判定，保留供包络口径复用。
- 独立判定：THW 按日扣除共超标日（保证 复合日 + 独立日 = 全部 THW 日）
- 输出文件：`compound_events.nc`, `standalone_days.nc`（**不是** `standalone_events.nc`）

### 步骤 7：计算年度天数与核心指标

**涉及文件**: `python/calc_chr.py`

**函数要求**:
```python
def calc_annual_days(daily: xr.DataArray, output_path=None) -> xr.DataArray:
    """日度 → 年度求和 (year, lat, lon)"""

def calc_CHR(compound_days, standalone_days, output_path=None) -> xr.DataArray:
    """CHR = compound / standalone，除零保护"""

def calc_cooccurrence_prob(compound_days, thw_days, output_path=None) -> xr.DataArray:
    """共现概率 = compound / thw_days"""

def calc_spatial_mean(da, lat_range, lon_range) -> xr.DataArray:
    """空间平均，用于生成时间序列"""
```

**技术细节**:
- 年度聚合：`daily.groupby('time.year').sum(dim='time')`，然后 `rename({'year': 'time'})`
- 陆地热浪总天数：`all_thw_daily = xr.where(compound_daily > 0, 1, standalone_daily)`
- CHR 时间序列：cos 加权总和之比，欧洲范围 `lat=30–72, lon=-15–45`
  （`fig2_chr.py` 口径；不是逐格点比值的算术平均）
- CHR 空间分布：`CHR` 的 2003–2023 **总和之比**（`comp_sum / std_sum`）
- 输出：`annual_compound_days.nc`, `annual_standalone_days.nc`, `annual_thw_days.nc`,
  `CHR_annual.nc`, `cooccurrence_prob_annual.nc`

### 步骤 8：导出 .mat 供 MATLAB 绘图 —— ⬜ **已弃用，不再执行**

> **状态：作废**。项目已全面切换 Python (matplotlib + cartopy) 出图
> （`python/figures.py`）。`python/export_for_matlab.py` 不存在，也不需要创建。
> 本节与其下的变量清单仅作历史设计对照，**勿按此实现**。

**原设计（存档）**: 输出 `results/intermediate/results_for_phase_A.mat`，
含 `lon/lat/time/compound_days/standalone_days/CHR_ts/CHR_spatial/cooccurrence_prob`。

## A.4 阶段 A 的 MATLAB 绘图代码 —— ⬜ **已弃用，仅作对照**

> **状态：作废**。项目已改用 Python (matplotlib + cartopy) 出图，实际入口：
> `python/figures.py`（图1/图2/S1）与 `python/fig_jkl_mhw_envelope.py`（S2）。
> 下方 MATLAB 代码**不要执行**，仅保留原始设计供面板布局对照；
> 面板定义已按论文更正（见 `TECHNICAL_SPEC.md` §5.2/§5.3）。
> `matlab/` 目录当前不存在。

**涉及文件**: `matlab/config.m`、`matlab/load_results.m`、`matlab/fig1_spatial.m`、`matlab/fig2_chr.m`

### `matlab/fig1_spatial.m`

```matlab
function fig1_spatial(lon, lat, compound_days, cooccurrence_prob, time_vec)
% fig1_spatial — 图 1: 复合热浪空间分布与时间演变
%
% Inputs:
%   lon: (lon,) 经度
%   lat: (lat,) 纬度
%   compound_days: (year, lat, lon) 年度复合热浪天数
%   cooccurrence_prob: (lat, lon) 共现概率
%   time_vec: (year,) 年份数组
%
% 布局:
%   a-i: 2003, 2006, 2010, 2012, 2018, 2019, 2020, 2022, 2023 年空间分布（论文正文年份）
%   j-l: 复合天数时间序列 1983–2023，三个区域：地中海（含黑海）/ 波罗的海沿岸 / 全欧海岸
%   m: 共现概率空间分布
%
% Output:
%   results/figures/fig1.pdf

% 实现要求:
% - 使用 tiledlayout(3, 4)
% - 地图投影: 'miller', lat=[30, 66], lon=[-10, 40]
% - 海岸线: load coastlines; geoshow(...)
% - 色标: 复合天数用 turbo(256)，共现概率用 parula(256)
% - 输出: exportgraphics(gcf, 'fig1.pdf', 'ContentType', 'vector')
```

### `matlab/fig2_chr.m`

```matlab
function fig2_chr(lon, lat, compound_days_mean, standalone_days_mean, CHR_ts, CHR_spatial, year_vec)
% fig2_chr — 图 2: CHR 对比分析
%
% Inputs:
%   compound_days_mean: (lat, lon) 2003-2023 年均复合天数
%   standalone_days_mean: (lat, lon) 年均独立天数
%   CHR_ts: (year,) CHR 时间序列
%   CHR_spatial: (lat, lon) CHR 空间分布
%   year_vec: (year,) 年份
%
% 布局:
%   a: 复合天数空间分布
%   b: 独立天数空间分布
%   c: CHR 时间序列（含 y=1 参考线）
%   d: CHR 空间分布
%
% Output:
%   results/figures/fig2.pdf

% 实现要求:
% - 使用 tiledlayout(2, 2)
% - caxis([0, 30]) for a, caxis([0, 15]) for b, caxis([0, 4]) for d
% - 色标: 热浪天数用 YlOrRd/turbo
```

## A.5 阶段 A 的验证标准

| 验证项 | 期望值 | 容差 | 验证方法 | 现状 |
|--------|--------|------|----------|------|
| 2022 年地中海复合暴露天数 | ~78 天 | ±5 天 | 对比 Table 1 | ⚠ 未命中（主图口径 20.7；见复现报告 §6） |
| 图2c 早期（1983–2002）CHR "在 1 附近" | ~1 | - | 对比正文 | ⚠ 中位数仅 **0.374**（0.06–0.79，约低 2.7 倍）；2003 起中位数 1.20 ✅（第三轮补登，见复现报告 §4/§1.4） |
| 2023 年 CHR 峰值 | 3.5 | ±0.2 | 对比正文 | ✅ 3.19（−9%） |
| 共现概率（地中海） | >0.8 | - | 对比图 1m | ✅ max 0.879 |
| 图2a 复合天数（若干南欧/东欧沿岸 > 20 天/年） | >20 | - | 对比图 2a | ✅ p95 = 22.3 |
| 图2b standalone 天数（多数沿岸 < 10 天/年） | 多数 <10 | - | 对比图 2b | ✅ p50 = 7.4 |
| 沿海格点对数量 | 500–2000 对 | - | 合理性检查 | ✅ 2039 对 / 1434 唯一海点 |
| 复合事件数 < THW 事件总数 | - | - | 逻辑检查 | ✅ |

## A.6 阶段 A 的磁盘管理

**⚠️ 数据清理由用户手动执行，必须用户确认当前阶段完成才能进入下一阶段。**

画完图 1、图 2 并与原文目视比对一致后，**由用户手动删除**以下原始数据：
- `D:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc`（释放 ~23 GB；欧洲裁剪件可保留）
- ⚠️ **不要删除 E-OBS**：`EOBS_tg_1983_2023.nc` 与 3 个分段文件是 Phase 5/6 的复现输入，
  且在气候态重算时需要（原文档写"释放 ~2 GB"为早期值，实际仅 ~0.5 GB，收益不抵风险）。

**必须保留**:
- `results/intermediate/` 下的 `.csv` / `.nc` 中间产物
- `results/figures/fig1_compound_spatial.pdf`、`fig2_chr.pdf`
