# 阶段 C 技术规范：湿热分析（图 5、图 6）

## C.1 阶段目标

使用 ERA5 和 OAFlux 数据计算湿球温度（WBT）、比湿（SH），以及 SST、蒸发、湿度的趋势分析，输出图 5（SST/蒸发/湿度趋势）和图 6（WBT/湿度分析）。

## C.2 数据清单

| 数据集 | 路径 | 大小 | 格式 |
|--------|------|------|------|
| ERA5 tmax（日最高） | `D:\2607compound\data\ERA5\tmax_eur_daily\tmax_eur_YYYY_MM.nc`（按月，0.25° 欧洲框 [66N,10W,30N,40E]） | ~1–2 GB（全量） | NetCDF |
| ERA5 d2m（2m 露点） | `D:\2607compound\data\ERA5\d2m_global_daily\d2m_global_YYYY_MM.nc`（按月 × 573，0.25° 全球） | 40.6 GB | NetCDF |
| ERA5 sp（地表气压） | `D:\2607compound\data\ERA5\sp\pres.sfc.daily.era5.YYYY.nc`（按年 × 46，**1.0°** 全球） | 4.1 GB | NetCDF |
| ERA5 sp 0.25°（欧洲框） | `D:\2607compound\data\ERA5\sp_eur_daily\`（⬜ 待下载，见 DATA_REQUIREMENTS 数据集 3b+） | ~1 GB | NetCDF |
| OAFlux | `D:\2607compound\data\OAFlux\OAFlux_evap_1991_2020_monthly.nc`（⬜ 待下载） | ~0.1 GB | NetCDF |

**注意**:
1. **WBT 公式已由论文明确**：由 ERA5 的 **Tmax + 露点温度 + 地表气压**估算**日最高 WBT**
   （"Daily maximum WBT is estimated from ERA5 reanalysis using maximum temperature,
   dew point temperature, and surface pressure"）。具体近似式论文未给，见
   `TECHNICAL_SPEC.md` §3.8 的 Stull / 迭代双实现，经锚点验证后定稿。
2. **sp 分辨率偏差**：论文声明 ERA5 相关变量均为 0.25°，现有 sp 为 1.0°；
   0.25° 欧洲框下载任务已立项（数据集 3b+）。在就位前，WBT/SH 会在 1.0° 气压场上
   混合 0.25° 温露场——**属需登记的降级**，不得无声带过。

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

### 步骤 9：导出 .mat 供 MATLAB 绘图 —— ⬜ **已弃用，不再执行**

> **状态：作废**。项目已全面切换 Python (matplotlib + cartopy)，`matlab/` 目录不存在。
> 改为 NetCDF / JSON 落盘：`results/intermediate/sst_trend.nc`、`sh_daily.nc`、
> `wbt_daily.nc`、`results/tables/fig_stats_*.json`。
> 下方变量清单仅作历史设计对照。

**原设计（存档）**: 输出 `results/intermediate/trend_fields.mat`、`humid_extreme_stats.mat`

**trend_fields 变量清单**:

| 变量名 | 维度 | 说明 |
|--------|------|------|
| `lon` | (lon,) | 经度 |
| `lat` | (lat,) | 纬度 |
| `sst_trend` | (lat, lon) | SST 趋势 (°C/decade) |
| `evap_trend` | (lat, lon) | 蒸发趋势 (cm/yr/decade) |
| `sh_trend` | (lat, lon) | 比湿趋势 (g/kg/decade) |

**humid_extreme_stats 变量清单**:

| 变量名 | 维度 | 说明 |
|--------|------|------|
| `WBT_compound_freq` | (year,) 或标量 | 复合年份 WBT≥25.5°C 频率 |
| `WBT_noncompound_freq` | (year,) 或标量 | 非复合年份频率 |
| `SH_compound_freq` | - | 复合年份 SH≥19 g/kg 频率 |
| `SH_noncompound_freq` | - | 非复合年份频率 |
| `return_period_WBT` | (threshold,) | WBT 重现期 |
| `return_period_SH` | (threshold,) | SH 重现期 |

## C.4 阶段 C 的绘图代码 —— ⬜ **MATLAB 版已弃用，仅作对照**

> **状态：作废**。实际用 Python (matplotlib + cartopy) 出图，`matlab/` 目录不存在。
> 下方代码**不要执行**；面板布局已按论文 Fig.5、Fig.6 caption 核对，保留供实现
> `python/fig5_sst_trend.py` / `python/fig6_wbt.py` 时对照。

**图 6 面板补充口径（论文 caption / 正文，必须实现）**:

| 面板 | 关键口径 |
|---|---|
| a | **年度** WBT ≥ 25.5 °C 天数，复合年（2003/2022/2023）vs 非复合年 |
| b | **年度** SH ≥ 19 g/kg 天数，同上分组 |
| c | WBT 极端值 **22–28 °C** 范围的重现期（年），统计窗口为 **JJA 90 天夏季**（June–August）——⚠️ **不是 JAS**（图 5 才是 JAS） |
| d–f | 2003 / 2022 / 2023 三个复合年的复合日 **平均（正文）/ 最大（caption）** WBT 空间分布；与地形相关，低海拔变化大 |

## C.5 阶段 C 的验证标准

| 验证项 | 期望值 | 容差 | 验证方法 |
|--------|--------|------|----------|
| WBT 范围 | -20°C 到 40°C | - | 合理性检查 |
| 2023 年地中海 WBT≥25.5°C 天数 | ~40 天 | ±5 天 | 对比正文 |
| 非复合年 WBT≥25.5°C 天数 | < 5 天 | ±3 天 | 对比正文 |
| SST 趋势（地中海夏季 JAS，1994–2023） | ~0.5°C/decade（论文 "up to 0.5"） | ±0.15 | 对比论文正文/图5a |
| 蒸发趋势符号 | 正趋势（增强）：论文锚点局部 >10 cm yr⁻¹ decade⁻¹（JAS） | - | 对比论文正文/图5b |
| SH 趋势（ERA5 JAS 1994–2023） | 达 0.3 g kg⁻¹ decade⁻¹ | ±0.1 | 对比论文正文/图5c |
| 图6c 重现期：2023 年 WBT≈26 °C | ~3–4 年（复合年）vs 非复合年 2000 约 60 年 | - | 对比论文正文/图6c |
| 图6d–f 2023 年 WBT 空间 | 大片 >25 °C、局部 >26 °C | - | 对比论文正文/图6d–f |

> ⚠️ **两项待定规则（Phase 5 开工前必须落实，见第二轮复核 §三）**：
> 1. **非复合年的可操作判据**：论文 Fig.6 caption 写 11 个、正文写 10 个非复合年，
>    并说明依据 Supplementary Fig. S1 的检测结果。步骤 8 现在的"该年有复合热浪天数"
>    不可用（2010–2023 几乎年年有）。需补一个阈值型判据（如地中海&黑海区域年复合天数 ≤ N）。
> 2. **100 km 海岸缓冲**：论文 Fig.6 的空间域是"地中海海岸向内 100 km 的陆地格点"。
>    `config.py` 目前**没有** `COASTAL_BUFFER_KM`，也无任何缓冲实现——Phase 5 必须补上。

## C.6 阶段 C 的磁盘管理

**⚠️ 数据清理由用户手动执行，必须用户确认当前阶段完成才能进入下一阶段。**

画完图 5、图 6 并与原文目视比对一致后，**由用户手动删除**以下原始数据：
- `D:\2607compound\data\ERA5\d2m_global_daily\`（573 个文件，释放 ~40 GB；如后续不再做 WBT 敏感性实验）
- `D:\2607compound\data\OAFlux\OAFlux_evap_1991_2020_monthly.nc`（释放 ~0.1 GB）
- ⚠️ 保留 `tmax_eur_daily/`（体积小）与 0.25° `sp_eur_daily/`（供复现核对分辨率口径）


**必须保留**:
- `results/intermediate/` 下的 `.nc` 和 `.mat` 文件（共数 GB）
- `results/figures/fig5.pdf`、`fig6.pdf`
