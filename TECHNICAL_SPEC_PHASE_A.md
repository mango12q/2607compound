# 阶段 A 技术规范：观测分析（图 1、图 2）

## A.1 阶段目标

使用 OISST 和 E-OBS 数据完成海洋热浪（MHW）和陆地热浪（THW）检测，识别沿海复合热浪事件，计算 CHR 和共现概率，输出图 1（空间分布+时间序列+共现概率）和图 2（CHR 对比）。

## A.2 数据清单

| 数据集 | 路径 | 大小 | 格式 |
|--------|------|------|------|
| OISST v2 | `F:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc` | ~3 GB | NetCDF |
| E-OBS tg | `F:\2607compound\data\E-OBS\EOBS_tg_1984_2023.nc` | ~2 GB | NetCDF |

**注意**: OISST 和 E-OBS 格点不对齐，需重采样到统一网格。

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

### 步骤 3：海洋热浪检测

**涉及文件**: `python/detect_mhw.py`

**函数要求**:
```python
def detect_mhw_grid(sst: xr.DataArray, clim_period: tuple, duration: int = 5, gap: int = 2) -> pd.DataFrame:
    """单格点 MHW 检测，返回事件 DataFrame"""

def detect_mhw_all_grids(sst: xr.DataArray, clim_period: tuple) -> pd.DataFrame:
    """全网格 MHW 检测，合并所有事件"""

def mhw_events_to_daily(events: pd.DataFrame, time: xr.DataArray, lat: xr.DataArray, lon: xr.DataArray) -> xr.DataArray:
    """将 MHW 事件表转换为日度二值场 (time, lat, lon)"""
```

**技术细节**:
- `marineHeatWaves.detect()` 接口：`temp, t, clim_temp, duration, gap`
- 时间转换：`t = (time_dt - np.datetime64('1970-01-01')).astype(int)`
- 气候期提取：`clim_mask = (t >= clim_start) & (t <= clim_end)`
- 事件表必须包含字段：`event_start`, `event_end`, `duration`, `lat`, `lon`, `lat_idx`, `lon_idx`
- 输出文件：`mhw_events_OISST.nc`

### 步骤 4：陆地热浪检测

**涉及文件**: `python/detect_thw.R`

**调用约定**:
```bash
Rscript detect_thw.R <eobs_file> <output_file> <clim_start> <clim_end>
```

**技术细节**:
- 依赖包：`heatwaveR`, `ncdf4`, `doParallel`, `foreach`
- E-OBS 默认形状为 `(lon, lat, time)`，需 `aperm(t2m, c(3, 2, 1))` 转置
- `heatwaveR::detect_event()` 参数：`threshold=90, minDuration=5, maxGap=2, climatology=TRUE`
- 并行：`registerDoParallel(cores = parallel::detectCores() - 1)`
- 输出文件：`thw_events_EOBS.rds`
- Python 调用：`subprocess.run(["Rscript", "python/detect_thw.R", ...])`

### 步骤 5：构建沿海格点配对

**涉及文件**: `python/coastal_mask.py`

**函数要求**:
```python
def build_land_mask(eobs: xr.Dataset) -> xr.DataArray:
    """从 E-OBS 构建陆地掩码（非 NaN 区域）"""

def build_ocean_mask(oisst: xr.Dataset) -> xr.DataArray:
    """从 OISST 构建海洋掩码（非 NaN 区域）"""

def find_coastal_grid_pairs(land_mask, ocean_mask, lat, lon) -> List[Tuple]:
    """4-连通邻域方法识别沿海格点对"""

def get_grid_pair_info(pairs, lat, lon) -> pd.DataFrame:
    """将配对列表转换为 DataFrame，含 lat_idx/lon_idx 和 lat/lon"""
```

**技术细节**:
- 4-连通结构：`s = generate_binary_structure(2, 4)`
- 陆地边缘：`binary_erosion(land_arr, structure=s)` 后做差集
- 配对规则：每个陆地格点只配一个相邻海洋格点（`break`）
- 输出文件：`coastal_pairs.nc`

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
- 复合判定：MHW 完全涵盖 THW（时间窗口完全包含）
- 独立判定：THW 期间**任何重叠**的 MHW 都视为非独立
- 输出文件：`compound_events.nc`, `standalone_events.nc`

### 步骤 7：计算年度天数与核心指标

**涉及文件**: `python/calc_chr.py`

**函数要求**:
```python
def calc_annual_days(daily: xr.DataArray) -> xr.DataArray:
    """日度 → 年度求和 (year, lat, lon)"""

def calc_CHR(compound_days, standalone_days) -> xr.DataArray:
    """CHR = compound / standalone，除零保护"""

def calc_cooccurrence_prob(compound_days, thw_days) -> xr.DataArray:
    """共现概率 = compound / thw_days"""

def calc_spatial_mean(da, lat_range, lon_range) -> xr.DataArray:
    """空间平均，用于生成时间序列"""
```

**技术细节**:
- 年度聚合：`daily.groupby('time.year').sum(dim='time')`，然后 `rename({'year': 'time'})`
- CHR 时间序列：地中海平均 `lat_range=(30, 45), lon_range=(5, 35)`
- CHR 空间分布：`CHR.sel(time=slice(2003, 2023)).mean(dim='time')`

### 步骤 8：导出 .mat 供 MATLAB 绘图

**涉及文件**: `python/export_for_matlab.py`

**函数要求**:
```python
def _to_matlab_compatible(obj):
    """将 xarray/pandas 转换为 MATLAB 兼容格式（scipy.io.savemat 不支持 xarray）"""

def export_for_matlab(results_dict, output_path):
    """保存为 .mat 文件，使用 do_compression=True"""

def build_results_dict(lon, lat, time, compound_days, standalone_days, CHR_ts, CHR_spatial, cooccurrence_prob):
    """构建阶段 A 结果字典"""
```

**输出变量清单**:

| MATLAB 变量名 | 维度 | 说明 |
|--------------|------|------|
| `lon` | (lon,) | 经度 |
| `lat` | (lat,) | 纬度 |
| `time` | (year,) | 年份 |
| `compound_days` | (year, lat, lon) | 年度复合热浪天数 |
| `standalone_days` | (year, lat, lon) | 年度独立热浪天数 |
| `CHR_ts` | (year,) | CHR 时间序列（地中海平均） |
| `CHR_spatial` | (lat, lon) | CHR 空间分布（2003-2023 均值） |
| `cooccurrence_prob` | (lat, lon) | 共现概率 |

**输出文件**: `results/intermediate/results_for_phase_A.mat`

## A.4 阶段 A 的 MATLAB 绘图代码

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
%   a-i: 1985, 1990, 1995, 2000, 2003, 2010, 2015, 2018, 2022 年空间分布
%   j-l: 时间序列（地中海平均复合天数、独立天数、CHR）
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

| 验证项 | 期望值 | 容差 | 验证方法 |
|--------|--------|------|----------|
| 2022 年地中海 MHW 天数 | ~78 天 | ±5 天 | 对比 Table 1 |
| 2023 年 CHR 峰值 | 3.5 | ±0.2 | 对比正文 |
| 共现概率（地中海） | >0.8 | - | 对比图 1m |
| 沿海格点对数量 | 500–2000 对 | - | 合理性检查 |
| 复合事件数 < THW 事件总数 | - | - | 逻辑检查 |

## A.6 阶段 A 的磁盘管理

**⚠️ 数据清理由用户手动执行，必须用户确认当前阶段完成才能进入下一阶段。**

画完图 1、图 2 并与原文目视比对一致后，**由用户手动删除**以下原始数据：
- `F:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc`（释放 ~3 GB）
- `F:\2607compound\data\E-OBS\EOBS_tg_1984_2023.nc`（释放 ~2 GB）

**必须保留**:
- `results/intermediate/` 下的 `.nc` 和 `.rds` 文件（共 < 1 GB）
- `results/figures/fig1.pdf`、`fig2.pdf`
