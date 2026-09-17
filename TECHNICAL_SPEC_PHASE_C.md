# 阶段 C 技术规范：湿热分析（图 5、图 6）

## C.1 阶段目标

使用 ERA5 和 OAFlux 数据计算湿球温度（WBT）、比湿（SH），以及 SST、蒸发、湿度的趋势分析，输出图 5（SST/蒸发/湿度趋势）和图 6（WBT/湿度分析）。

## C.2 数据清单

| 数据集 | 路径 | 大小 | 格式 |
|--------|------|------|------|
| ERA5 tmax | `F:\2607compound\data\ERA5\ERA5_tmax_1984_2023_daily.nc` | ~8 GB | NetCDF |
| ERA5 d2m | `F:\2607compound\data\ERA5\ERA5_d2m_1984_2023_daily.nc` | ~8 GB | NetCDF |
| ERA5 sp | `F:\2607compound\data\ERA5\ERA5_sp_1984_2023_daily.nc` | ~8 GB | NetCDF |
| OAFlux | `F:\2607compound\data\OAFlux\OAFlux_evap_1991_2020_monthly.nc` | ~0.1 GB | NetCDF |

**注意**: WBT 公式未定，需确认论文使用 ERA5 提供变量还是手工计算后再绘制图 5–6。

## C.3 处理流程（9 个步骤）

### 步骤 1：加载数据

**涉及文件**: `python/config.py`、`python/load_data.py`

**函数要求**:
```python
def load_era5_var(varname: str, filepath=None) -> xr.DataArray:
    """
    加载 ERA5 单个变量
    varname: 'tmax', 'd2m', 'sp'
    返回: DataArray，维度 (time, lat, lon)
    """

def load_oaflux(filepath=None) -> xr.Dataset:
    """加载 OAFlux 月度蒸发数据"""
```

**技术细节**:
- ERA5 变量名映射：
  - `maximum_temperature_at_2_metres_since_previous_post_processing` → `tmax`
  - `2_metre_dewpoint_temperature` → `d2m`
  - `surface_pressure` → `sp`
- 单位：tmax 和 d2m 为 `degC`，sp 为 `Pa`
- OAFlux：月度蒸发，单位通常为 `kg/m2/day` 或 `cm/day`，需确认

### 步骤 2：计算相对湿度（Magnus 公式）

**涉及文件**: `python/calc_wbt.py`

**函数要求**:
```python
def calc_relative_humidity(tmax: xr.DataArray, d2m: xr.DataArray) -> xr.DataArray:
    """
    Magnus 公式:
    es(T) = 6.112 * exp(17.67 * T / (T + 243.5))
    RH = (es(d2m) / es(tmax)) * 100
    返回: RH (%)，裁剪到 [0, 100]
    """
```

### 步骤 3：计算湿球温度 WBT

**涉及文件**: `python/calc_wbt.py`

**函数要求**:
```python
def calc_WBT_stull(tmax, d2m, sp) -> xr.DataArray:
    """Stull (2011) 近似公式"""

def calc_WBT_iterative(tmax, d2m, sp, max_iter=100, tol=0.01) -> xr.DataArray:
    """迭代精确计算（psychrometric 方程）"""

def calc_WBT(tmax, d2m, sp, method='stull') -> xr.DataArray:
    """WBT 入口函数，method: 'stull' 或 'iterative'"""
```

**技术细节**:
- Stull 公式：
  ```
  WBT = T * atan(0.151977 * sqrt(RH + 8.313659))
        + atan(T + RH) - atan(RH - 1.676331)
        + 0.00391838 * RH^(3/2) * atan(0.023101 * RH)
        - 4.686035
  ```
- 迭代法：以 Stull 结果为初值，通过 psychrometric 方程迭代优化
- **待确认**: 论文使用哪种方法？需对比原文 Methods 或补充材料
- 输出文件：`wbt_daily.nc`

### 步骤 4：计算比湿 SH

**涉及文件**: `python/calc_wbt.py`

**函数要求**:
```python
def calc_specific_humidity(d2m: xr.DataArray, sp: xr.DataArray) -> xr.DataArray:
    """
    比湿公式:
    e = 6.112 * exp(17.67 * d2m / (d2m + 243.5))  [hPa]
    p = sp / 100  [Pa -> hPa]
    q = 0.622 * e / (p - 0.378 * e)  [kg/kg]
    q_gkg = q * 1000  [g/kg]
    """
```

**输出文件**: `sh_daily.nc`

### 步骤 5：计算 SST 线性趋势

**函数要求**:
```python
def calc_sst_trend(oisst: xr.Dataset, period=(1994, 2023), months=[7, 8, 9]) -> xr.DataArray:
    """
    筛选 JAS 月份，计算每年夏季均值，然后做线性趋势
    返回: (lat, lon) 趋势数组，单位 °C/decade
    """
```

**技术细节**:
- 筛选时间：`time.dt.month.isin([7, 8, 9])` 且 `time.dt.year >= 1994` 且 `time.dt.year <= 2023`
- 年度平均：`sst_jas.groupby('time.year').mean(dim='time')`
- 线性趋势：`scipy.stats.linregress(year, sst_ts)` 对每个格点
- 输出文件：`sst_trend.nc`

### 步骤 6：计算海洋蒸发趋势

**函数要求**:
```python
def calc_evap_trend(oaflux: xr.Dataset, period=(1991, 2020), months=[7, 8, 9]) -> xr.DataArray:
    """OAFlux JAS 蒸发线性趋势，单位 cm/yr/decade"""
```

### 步骤 7：计算比湿趋势

**函数要求**:
```python
def calc_sh_trend(sh_daily: xr.DataArray, period=(1994, 2023), months=[7, 8, 9]) -> xr.DataArray:
    """ERA5 JAS 比湿线性趋势，单位 g/kg/decade"""
```

### 步骤 8：筛选复合年份并统计极端值

**函数要求**:
```python
def select_compound_years(compound_days: xr.DataArray) -> List[int]:
    """识别复合热浪年份（如 2003, 2022, 2023）"""

def calc_wbt_sh_stats(WBT: xr.DataArray, SH: xr.DataArray, compound_daily: xr.DataArray) -> Dict:
    """
    计算复合年份与非复合年份的:
    - WBT >= 25.5°C 天数频率
    - SH >= 19 g/kg 天数频率
    - 重现期（基于 GEV 分布或简单分位数）
    """
```

**技术细节**:
- 复合年份判定：该年有复合热浪天数
- WBT 阈值：25.5°C（ISO 7243 标准）
- SH 阈值：19 g/kg
- 重现期计算：对地中海区域平均序列拟合 GEV 分布

### 步骤 9：导出 .mat 供 MATLAB 绘图

**输出文件**: `results/intermediate/trend_fields.mat`、`results/intermediate/humid_extreme_stats.mat`

**trend_fields.mat 变量清单**:

| 变量名 | 维度 | 说明 |
|--------|------|------|
| `lon` | (lon,) | 经度 |
| `lat` | (lat,) | 纬度 |
| `sst_trend` | (lat, lon) | SST 趋势 (°C/decade) |
| `evap_trend` | (lat, lon) | 蒸发趋势 (cm/yr/decade) |
| `sh_trend` | (lat, lon) | 比湿趋势 (g/kg/decade) |

**humid_extreme_stats.mat 变量清单**:

| 变量名 | 维度 | 说明 |
|--------|------|------|
| `WBT_compound_freq` | (year,) 或标量 | 复合年份 WBT≥25.5°C 频率 |
| `WBT_noncompound_freq` | (year,) 或标量 | 非复合年份频率 |
| `SH_compound_freq` | - | 复合年份 SH≥19 g/kg 频率 |
| `SH_noncompound_freq` | - | 非复合年份频率 |
| `return_period_WBT` | (threshold,) | WBT 重现期 |
| `return_period_SH` | (threshold,) | SH 重现期 |

## C.4 阶段 C 的 MATLAB 绘图代码

**涉及文件**: `matlab/fig5_sst_trend.m`、`matlab/fig6_wbt.m`

### `matlab/fig5_sst_trend.m`

```matlab
function fig5_sst_trend(lon, lat, sst_trend, evap_trend, sh_trend)
% fig5_sst_trend — 图 5: SST/蒸发/湿度趋势
%
% 布局:
%   a: SST 趋势 (°C/decade)，范围 [−0.1, 0.6]
%   b: 蒸发趋势 (cm/yr/decade)
%   c: 比湿趋势 (g/kg/decade)
%
% 区域: 地中海 [lat 30-46, lon 5-36]
%
% Output: results/figures/fig5.pdf
```

### `matlab/fig6_wbt.m`

```matlab
function fig6_wbt(...)
% fig6_wbt — 图 6: WBT 和湿度分析
%
% 布局 (a-f):
%   a: WBT >= 25.5°C 天数频率（复合 vs 非复合）
%   b: SH >= 19 g/kg 天数频率（复合 vs 非复合）
%   c: WBT 重现期
%   d-f: 空间分布图
%
% Output: results/figures/fig6.pdf
```

## C.5 阶段 C 的验证标准

| 验证项 | 期望值 | 容差 | 验证方法 |
|--------|--------|------|----------|
| WBT 范围 | -20°C 到 40°C | - | 合理性检查 |
| 2023 年地中海 WBT≥25.5°C 天数 | ~40 天 | ±5 天 | 对比正文 |
| SST 趋势（地中海夏季） | ~0.2–0.3°C/decade | ±0.1 | 对比已知文献 |
| 蒸发趋势符号 | 负趋势（地中海水域） | - | 物理合理性 |

## C.6 阶段 C 的磁盘管理

**⚠️ 数据清理由用户手动执行，必须用户确认当前阶段完成才能进入下一阶段。**

画完图 5、图 6 并与原文目视比对一致后，**由用户手动删除**以下原始数据：
- `F:\2607compound\data\ERA5\` 下全部 3 个 `.nc` 文件（释放 ~24 GB）
- `F:\2607compound\data\OAFlux\OAFlux_evap_1991_2020_monthly.nc`（释放 ~0.1 GB）

**必须保留**:
- `results/intermediate/` 下的 `.nc` 和 `.mat` 文件（共数 GB）
- `results/figures/fig5.pdf`、`fig6.pdf`
