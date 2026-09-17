# 技术规范文档：论文复现项目

## 文档信息

- **项目**: Compound coastal marine–terrestrial heatwaves associated with humid-heat stress in Europe
- **原文**: Barkhordarian, A., Brunet, E. & Baehr, J. Sci Rep 15, 43810 (2025)
- **DOI**: https://doi.org/10.1038/s41598-025-32049-z
- **本规范版本**: v1.0
- **适用语言**: Python ≥ 3.10 + R ≥ 4.0

---

## 目录

1. [项目概述](#1-项目概述)
2. [项目目录结构](#2-项目目录结构)
3. [Python 代码详细规范](#3-python-代码详细规范)
4. [R 代码详细规范](#4-r-代码详细规范)
5. [MATLAB 代码详细规范](#5-matlab-代码详细规范)
6. [数据接口规范](#6-数据接口规范)
7. [代码规范](#7-代码规范)
8. [测试与验证](#8-测试与验证)
9. [运行流程](#9-运行流程)
10. [常见问题](#10-常见问题)

---

## 1. 项目概述

### 1.1 复现目标

使用 **Python + R** 混合语言复现论文全部结果：
- Python 负责数据 I/O、热浪检测、复合事件识别、WBT 计算、归因分析、全部绘图输出
- R 负责陆地热浪检测（`heatwaveR`，通过 `subprocess` 调用）
- 所有输出图表需与原文一致（图 1–6、补充图 S1、表 1）

### 1.2 技术栈

| 语言/工具 | 用途 | 版本要求 |
|-----------|------|----------|
| **Python** | 数据 I/O、热浪检测、复合事件识别、bootstrap 归因 | ≥ 3.10（当前 3.13 可用） |
| **R** | 陆地热浪检测（`heatwaveR`） | ≥ 4.0 |
| **conda** | Python 环境管理（推荐） | 最新版 |

### 1.3 必需工具箱

| 语言 | 包/工具箱 | 用途 |
|------|----------|------|
| Python | `xarray` | NetCDF 数据读写 |
| Python | `dask` | 惰性加载 / 核外计算 |
| Python | `numpy` | 数组运算 |
| Python | `scipy` | 科学计算 |
| Python | `matplotlib` | 全部论文图表输出 |
| Python | `cartopy` | 欧洲沿海地图投影与海陆渲染 |
| Python | `joblib` | bootstrap 并行 |
| Python | `rpy2` | 调用 R 的 `heatwaveR` |
| Python | `scipy.io` | 导出 `.mat` 文件 |
| R | `heatwaveR` (v0.4.6) | 陆地热浪检测 |
| R | `ncdf4` | NetCDF 读取 |
| — | — | — |

### 1.4 硬件要求

| 组件 | 最低配置 | 推荐配置 | 说明 |
|------|----------|----------|------|
| **内存** | 32 GB | 64 GB | CESM1-LE 需分块加载 |
| **CPU** | 8 核 | 16 核+ | bootstrap 并行受益 |
| **存储** | 500 GB 空闲 | 1 TB+ SSD | 原始数据 + 中间产物 |
| **显卡** | 任意 | 任意 | 本项目基本闲置，无关紧要 |

---

## 2. 项目目录结构

```
F:\2607compound\
├── README.md                    # 项目说明
├── TECHNICAL_SPEC.md            # 本文档（技术规范）
├── DATA_REQUIREMENTS.md         # 数据下载要求（单独文件）
├── verify_data.py               # 数据完整性校验脚本
│
├── data/                        # 所有原始数据（按 DATA_REQUIREMENTS.md 下载）
│   ├── OISST/
│   │   └── oisst_v2.1_1982_2023.nc
│   ├── E-OBS/
│   │   └── EOBS_tg_1984_2023.nc
│   ├── ERA5/
│   │   ├── ERA5_tmax_1984_2023_daily.nc
│   │   ├── ERA5_d2m_1984_2023_daily.nc
│   │   └── ERA5_sp_1984_2023_daily.nc
│   ├── OAFlux/
│   │   └── OAFlux_evap_1991_2020_monthly.nc
│   └── CESM1-LE/
│       ├── ALL/
│       │   ├── b.e11.B20TRC5CNBDRD.001.cam.h1.TREFHT.185001-202312.nc
│       │   ├── b.e11.B20TRC5CNBDRD.002.cam.h1.TREFHT.185001-202312.nc
│       │   └── ... (共 20 个成员)
│       └── FixGHG/
│           ├── b.e11.B20TRC5CNBDRD.FixGHG.001.cam.h1.TREFHT.185001-202312.nc
│           └── ... (共 20 个成员)
│
├── python/                       # Python 处理+绘图代码
│   ├── __init__.py
│   ├── config.py                 # 路径配置、常量
│   ├── load_data.py              # 数据加载与预处理
│   ├── preprocess.py             # 原始数据合并预处理
│   ├── detect_mhw.py             # 海洋热浪检测 (marineHeatWaves)
│   ├── detect_thw.py             # 陆地热浪检测（纯 Python 实现）
│   ├── detect_thw_wrapper.py     # THW 检测入口（调用 detect_thw）
│   ├── detect_events.py          # 共享事件检测逻辑
│   ├── coastal_mask.py           # 沿海格点掩码与配对 (KDTree)
│   ├── compound_events.py        # 复合事件识别
│   ├── calc_chr.py               # 复合热浪比 (CHR)
│   ├── calc_wbt.py               # 湿球温度 (WBT) 计算
│   ├── attribution.py            # FAR/PR 计算 + bootstrap
│   ├── fig1_compound_spatial.py  # 图 1: a-i 空间分布, j-l 时间序列, m 共现概率
│   ├── fig2_chr.py               # 图 2: a-d CHR 对比
│   ├── fig3_attribution.py       # 图 3: a-d FAR/PR 曲线
│   ├── fig4_return_period.py     # 图 4: a-c 重现期
│   ├── fig5_sst_trend.py         # 图 5: a-c SST/蒸发/湿度趋势
│   ├── fig6_wbt.py               # 图 6: a-f WBT/湿度分析
│   ├── table1_attribution.py     # 表 1: 归因结果
│   ├── supp_fig1.py              # 补充图 S1
│   ├── figures.py                # 一键生成全部图表
│   ├── verify_data.py            # 数据完整性校验
│   └── run_all.py                # 一键运行完整流程
│
├── results/                      # 中间结果与最终输出
│   ├── intermediate/             # 中间产物（可随时删除重算）
│   │   ├── mhw_events_OISST.nc
│   │   ├── thw_events_EOBS.nc
│   │   ├── compound_events.nc
│   │   └── bootstrap_results.mat
│   ├── figures/                  # 最终图表
│   │   ├── fig1.pdf
│   │   ├── fig2.pdf
│   │   ├── fig3.pdf
│   │   ├── fig4.pdf
│   │   ├── fig5.pdf
│   │   ├── fig6.pdf
│   │   └── supp/
│   │       └── figS1.pdf
│   └── tables/                   # 表格数据
│       └── table1.csv
│
└── logs/                         # 运行日志
    ├── download.log
    ├── detection.log
    └── attribution.log
```

---

## 3. Python 代码详细规范

### 3.1 `config.py` — 路径与常量配置

**文件路径**: `python/config.py`  
**功能**: 集中管理所有路径、阈值、参数，避免硬编码。

```python
"""
config.py — 项目全局配置
"""
import os

# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────
BASE_DIR = r"F:\2607compound"

DATA_DIR = os.path.join(BASE_DIR, "data")
OISST_DIR = os.path.join(DATA_DIR, "OISST")
EOBS_DIR = os.path.join(DATA_DIR, "E-OBS")
ERA5_DIR = os.path.join(DATA_DIR, "ERA5")
OAFLUX_DIR = os.path.join(DATA_DIR, "OAFlux")
CESM_DIR = os.path.join(DATA_DIR, "CESM1-LE")

RESULTS_DIR = os.path.join(BASE_DIR, "results")
INTERMEDIATE_DIR = os.path.join(RESULTS_DIR, "intermediate")
FIGURES_DIR = os.path.join(RESULTS_DIR, "figures")
TABLES_DIR = os.path.join(RESULTS_DIR, "tables")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# ──────────────────────────────────────────────
# 热浪检测参数
# ──────────────────────────────────────────────
CLIM_PERIOD = (1983, 2012)       # 气候学基准期
DURATION_THRESH = 5              # 持续时间阈值（天）
GAP_TOLERANCE = 2                # 允许中断天数
PERCENTILE = 90                  # 90 百分位阈值

# ──────────────────────────────────────────────
# 复合事件参数
# ──────────────────────────────────────────────
COASTAL_BUFFER_KM = 100          # 分析缓冲区（km）
WBT_THRESHOLD = 25.5             # WBT 阈值 (°C)
SH_THRESHOLD = 19.0              # 比湿阈值 (g/kg)

# ──────────────────────────────────────────────
# Bootstrap 参数
# ──────────────────────────────────────────────
N_BOOTSTRAP = 1000               # 自助采样次数
CI_ALPHA = (0.05, 0.95)          # 置信区间 (5%, 95%)
N_JOBS = -1                      # 并行核心数 (-1 = 全部)

# ──────────────────────────────────────────────
# CESM1-LE 成员列表
# ──────────────────────────────────────────────
CESM_ALL_MEMBERS = [f"{i:03d}" for i in range(1, 21)]     # 001–020
CESM_FIXGHG_MEMBERS = [f"{i:03d}" for i in range(1, 21)]  # 001–020

# ──────────────────────────────────────────────
# 欧洲沿海区域定义（用于裁剪和分析）
# ──────────────────────────────────────────────
EUROPEAN_COASTS = {
    'Mediterranean': {'lon': [5, 35], 'lat': [30, 45]},
    'BlackSea': {'lon': [28, 42], 'lat': [40, 47]},
    'Baltic': {'lon': [10, 30], 'lat': [53, 66]},
    'Atlantic': {'lon': [-10, 5], 'lat': [35, 60]},
}

# ──────────────────────────────────────────────
# 绘图参数
# ──────────────────────────────────────────────
FIG_SIZE = (12, 8)
DPI = 300
CMAP_HEATWAVE = 'YlOrRd'
CMAP_PROBABILITY = 'viridis'
```

---

### 3.2 `load_data.py` — 数据加载与预处理

**文件路径**: `python/load_data.py`  
**功能**: 统一加载 OISST、E-OBS、ERA5、OAFlux、CESM1-LE，返回标准化的 xarray Dataset。

```python
"""
load_data.py — 数据加载与预处理
"""
import os
import xarray as xr
import numpy as np
from typing import Dict, Optional

from config import (
    OISST_DIR, EOBS_DIR, ERA5_DIR, OAFLUX_DIR, CESM_DIR,
    CLIM_PERIOD
)


def load_oisst(filepath: Optional[str] = None) -> xr.Dataset:
    """
    加载 OISST v2 日度 SST 数据。
    
    Parameters:
        filepath: 文件路径，默认从 config.OISST_DIR 拼接
    
    Returns:
        ds: 包含 SST 的 xarray Dataset，坐标统一为 (time, lat, lon)
    """
    if filepath is None:
        filepath = os.path.join(OISST_DIR, "oisst_v2.1_1982_2023.nc")
    
    ds = xr.open_dataset(filepath, chunks={'time': 365})
    
    # 统一坐标名和变量名
    rename_dict = {}
    if 'sst' in ds.data_vars:
        rename_dict['sst'] = 'SST'
    ds = ds.rename(rename_dict)
    
    # 确保坐标名一致
    if 'latitude' in ds.dims:
        ds = ds.rename({'latitude': 'lat', 'longitude': 'lon'})
    
    # 设置属性
    ds['SST'].attrs['units'] = 'degC'
    ds['SST'].attrs['long_name'] = 'Sea Surface Temperature'
    
    return ds


def load_eobs(filepath: Optional[str] = None) -> xr.Dataset:
    """
    加载 E-OBS 日度 T2m 数据。
    
    Parameters:
        filepath: 文件路径
    
    Returns:
        ds: 包含 T2m 的 xarray Dataset
    """
    if filepath is None:
        filepath = os.path.join(EOBS_DIR, "EOBS_tg_1984_2023.nc")
    
    ds = xr.open_dataset(filepath, chunks={'time': 365})
    
    rename_dict = {}
    if 'tg' in ds.data_vars:
        rename_dict['tg'] = 'T2m'
    ds = ds.rename(rename_dict)
    
    if 'latitude' in ds.dims:
        ds = ds.rename({'latitude': 'lat', 'longitude': 'lon'})
    
    ds['T2m'].attrs['units'] = 'degC'
    ds['T2m'].attrs['long_name'] = '2m Temperature'
    
    return ds


def load_era5_var(varname: str, filepath: Optional[str] = None) -> xr.DataArray:
    """
    加载 ERA5 单个变量。
    
    Parameters:
        varname: 变量名 ('tmax', 'd2m', 'sp')
        filepath: 文件路径
    
    Returns:
        da: xarray DataArray
    """
    if filepath is None:
        fname_map = {
            'tmax': 'ERA5_tmax_1984_2023_daily.nc',
            'd2m': 'ERA5_d2m_1984_2023_daily.nc',
            'sp': 'ERA5_sp_1984_2023_daily.nc',
        }
        filepath = os.path.join(ERA5_DIR, fname_map[varname])
    
    ds = xr.open_dataset(filepath, chunks={'time': 365})
    
    # ERA5 变量名映射
    era5_name_map = {
        'tmax': 'maximum_temperature_at_2_metres_since_previous_post_processing',
        'd2m': '2_metre_dewpoint_temperature',
        'sp': 'surface_pressure',
    }
    
    var_key = era5_name_map.get(varname, varname)
    da = ds[var_key]
    da.name = varname
    
    return da


def load_oaflux(filepath: Optional[str] = None) -> xr.Dataset:
    """加载 OAFlux 月度蒸发数据。"""
    if filepath is None:
        filepath = os.path.join(OAFLUX_DIR, "OAFlux_evap_1991_2020_monthly.nc")
    
    ds = xr.open_dataset(filepath)
    return ds


def load_cesm1le_member(
    member_id: str,
    forcing: str = "ALL",
    filepath: Optional[str] = None
) -> xr.Dataset:
    """
    加载单个 CESM1-LE 成员的 T2m + SST。
    
    Parameters:
        member_id: 成员编号，如 '001', '002', ...
        forcing: 'ALL' 或 'FixGHG'
        filepath: 可选，手动指定文件路径
    
    Returns:
        ds: 包含 TREFHT (T2m) 和 TEMP_0m (SST) 的 Dataset
    """
    if filepath is None:
        if forcing == "ALL":
            filepath = os.path.join(
                CESM_DIR, "ALL",
                f"b.e11.B20TRC5CNBDRD.{member_id}.cam.h1.TREFHT.185001-202312.nc"
            )
        else:
            filepath = os.path.join(
                CESM_DIR, "FixGHG",
                f"b.e11.B20TRC5CNBDRD.FixGHG.{member_id}.cam.h1.TREFHT.185001-202312.nc"
            )
    
    # 使用 dask 惰性加载，避免一次性读入内存
    ds = xr.open_dataset(filepath, chunks={'time': 365, 'lat': 10, 'lon': 10})
    
    # 统一变量名
    rename_dict = {}
    if 'TREFHT' in ds.data_vars:
        rename_dict['TREFHT'] = 'T2m'
    if 'TEMP' in ds.data_vars:
        # 取 0m 层作为 SST
        ds['TEMP'] = ds['TEMP'].sel(lev=0, method='nearest')
        rename_dict['TEMP'] = 'SST'
    ds = ds.rename(rename_dict)
    
    ds['T2m'].attrs['units'] = 'K'
    ds['SST'].attrs['units'] = 'K'
    
    return ds


def load_cesm1le_dir(forcing: str = "ALL") -> xr.Dataset:
    """
    加载整个 CESM1-LE 目录（所有成员），使用 open_mfdataset 自动合并。
    
    Parameters:
        forcing: 'ALL' 或 'FixGHG'
    
    Returns:
        ds: 合并后的 Dataset，维度为 (member, time, lat, lon)
    """
    if forcing == "ALL":
        pattern = os.path.join(CESM_DIR, "ALL", "*.nc")
    else:
        pattern = os.path.join(CESM_DIR, "FixGHG", "*.nc")
    
    ds = xr.open_mfdataset(
        pattern,
        chunks={'time': 365, 'member': 1},
        combine='nested',
        concat_dim='member',
        parallel=True
    )
    
    return ds


def calc_climatology(
    da: xr.DataArray,
    clim_period: tuple = CLIM_PERIOD
) -> xr.DataArray:
    """
    计算气候学阈值（90 百分位）。
    
    Parameters:
        da: 日度数据 (time, lat, lon)
        clim_period: (start_year, end_year)
    
    Returns:
        clim: 气候学阈值 (dayofyear, lat, lon)
    """
    start_year, end_year = clim_period
    
    # 筛选气候期数据
    clim_data = da.sel(
        time=slice(f"{start_year}-01-01", f"{end_year}-12-31")
    )
    
    # 计算逐日 90 百分位
    clim = clim_data.groupby('time.dayofyear').quantile(0.9, dim='time')
    
    return clim


def preprocess_all() -> Dict[str, xr.Dataset]:
    """
    加载并预处理所有观测数据。
    
    Returns:
        data_dict: 包含所有预处理后数据的字典
    """
    print("Loading OISST...")
    oisst = load_oisst()
    
    print("Loading E-OBS...")
    eobs = load_eobs()
    
    print("Loading ERA5...")
    era5_tmax = load_era5_var('tmax')
    era5_d2m = load_era5_var('d2m')
    era5_sp = load_era5_var('sp')
    
    print("Loading OAFlux...")
    oaflux = load_oaflux()
    
    print("Calculating climatology...")
    sst_clim = calc_climatology(oisst['SST'])
    t2m_clim = calc_climatology(eobs['T2m'])
    
    return {
        'oisst': oisst,
        'eobs': eobs,
        'era5_tmax': era5_tmax,
        'era5_d2m': era5_d2m,
        'era5_sp': era5_sp,
        'oaflux': oaflux,
        'sst_clim': sst_clim,
        't2m_clim': t2m_clim,
    }
```

---

### 3.3 `detect_mhw.py` — 海洋热浪检测

**文件路径**: `python/detect_mhw.py`  
**功能**: 调用 `marineHeatWaves` 检测海洋热浪。

```python
"""
detect_mhw.py — 海洋热浪检测 (marineHeatWaves)
"""
import numpy as np
import pandas as pd
import xarray as xr
from marineHeatWaves import detect as mhw_detect
from typing import Optional

from config import DURATION_THRESH, GAP_TOLERANCE


def detect_mhw_grid(
    sst: xr.DataArray,
    clim_period: tuple = (1983, 2012),
    duration: int = DURATION_THRESH,
    gap: int = GAP_TOLERANCE
) -> pd.DataFrame:
    """
    对单个格点检测海洋热浪。
    
    Parameters:
        sst: 日度 SST 时间序列 (time,)
        clim_period: 气候学基准期
        duration: 持续时间阈值（天）
        gap: 允许中断天数
    
    Returns:
        events: MHW 事件 DataFrame，每行一个事件
    """
    # 提取数值
    temp = sst.values.astype(np.float64)
    
    # 转换为 marineHeatWaves 需要的时间格式（自 1970-01-01 的天数）
    time_dt = sst.time.values.astype('datetime64[D]')
    t = (time_dt - np.datetime64('1970-01-01')).astype(int)
    
    # 提取气候期数据
    start_year, end_year = clim_period
    clim_start = (np.datetime64(f"{start_year}-01-01") - np.datetime64("1970-01-01")).astype(int)
    clim_end = (np.datetime64(f"{end_year}-12-31") - np.datetime64("1970-01-01")).astype(int)
    clim_mask = (t >= clim_start) & (t <= clim_end)
    clim_temp = temp[clim_mask]
    
    # 调用 marineHeatWaves 检测
    # detect 返回字典，包含 events DataFrame
    result = mhw_detect(
        temp, t,
        clim_temp=clim_temp,
        duration=duration,
        gap=gap
    )
    
    events = result['events']
    
    # 添加格点坐标
    if 'lat' in sst.dims:
        events['lat'] = float(sst.lat.values)
        events['lon'] = float(sst.lon.values)
    
    return events


def detect_mhw_all_grids(
    sst: xr.DataArray,
    clim_period: tuple = (1983, 2012)
) -> pd.DataFrame:
    """
    对整个网格逐格点检测 MHW，合并所有事件。
    
    Parameters:
        sst: 日度 SST (time, lat, lon)
        clim_period: 气候学基准期
    
    Returns:
        all_events: 合并后的 MHW 事件 DataFrame
    """
    all_events = []
    
    for lat_idx in range(len(sst.lat)):
        for lon_idx in range(len(sst.lon)):
            grid_point = sst.isel(lat=lat_idx, lon=lon_idx)
            events = detect_mhw_grid(grid_point, clim_period)
            if len(events) > 0:
                events['lat_idx'] = lat_idx
                events['lon_idx'] = lon_idx
                all_events.append(events)
    
    if all_events:
        return pd.concat(all_events, ignore_index=True)
    else:
        return pd.DataFrame()


def mhw_events_to_daily(
    events: pd.DataFrame,
    time: xr.DataArray,
    lat: xr.DataArray,
    lon: xr.DataArray
) -> xr.DataArray:
    """
    将 MHW 事件表转换为日度格点数据（1=热浪日, 0=非热浪日）。
    
    Parameters:
        events: MHW 事件 DataFrame
        time: 时间坐标
        lat: 纬度坐标
        lon: 经度坐标
    
    Returns:
        mhw_daily: (time, lat, lon) 二值 DataArray
    """
    nt = len(time)
    nlat = len(lat)
    nlon = len(lon)
    
    mhw_daily = np.zeros((nt, nlat, nlon), dtype=np.int8)
    
    for _, event in events.iterrows():
        # 找到对应时间索引
        time_start = pd.Timestamp(event['event_start'])
        time_end = pd.Timestamp(event['event_end'])
        
        time_mask = (time >= time_start) & (time <= time_end)
        li = int(event['lat_idx'])
        lo = int(event['lon_idx'])
        
        mhw_daily[time_mask, li, lo] = 1
    
    return xr.DataArray(
        mhw_daily,
        dims=['time', 'lat', 'lon'],
        coords={'time': time, 'lat': lat, 'lon': lon},
        name='MHW',
        attrs={'long_name': 'Marine Heatwave Day', 'units': '0/1'}
    )
```

---

### 3.4 `detect_thw.R` — 陆地热浪检测（R 脚本）

**文件路径**: `python/detect_thw.R`  
**功能**: 使用 `heatwaveR` 检测陆地热浪。

```r
#!/usr/bin/env Rscript
# detect_thw.R — 陆地热浪检测 (heatwaveR)
#
# 用法:
#   Rscript detect_thw.R <eobs_file> <output_file> <clim_start> <clim_end>
#
# 示例:
#   Rscript detect_thw.R data/E-OBS/EOBS_tg_1984_2023.nc results/thw_events.rds 1983 2012

suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))
suppressPackageStartupMessages(library(doParallel))
suppressPackageStartupMessages(library(foreach))

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 4) {
  stop("Usage: Rscript detect_thw.R <eobs_file> <output_file> <clim_start> <clim_end>")
}

eobs_file <- args[1]
output_file <- args[2]
clim_start <- as.integer(args[3])
clim_end <- as.integer(args[4])

cat(sprintf("Loading E-OBS from: %s\n", eobs_file))

# 读取 NetCDF
nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")  # (lon, lat, time) — 注意 E-OBS 通常是 (lon, lat, time)
lat <- ncvar_get(nc, "latitude")
lon <- ncvar_get(nc, "longitude")
time <- ncvar_get(nc, "time")
nc_close(nc)

# 转置为 (time, lat, lon)
t2m <- aperm(t2m, c(3, 2, 1))

cat(sprintf("Data shape: %d time x %d lat x %d lon\n", dim(t2m)[1], dim(t2m)[2], dim(t2m)[3]))

# 设置日期
start_date <- as.Date(paste0(clim_start, "-01-01"))
dates <- seq(start_date, by = "day", length.out = dim(t2m)[1])

# 逐格点检测热浪
nlat <- dim(t2m)[2]
nlon <- dim(t2m)[3]

cat("Detecting terrestrial heatwaves...\n")

# 使用 foreach 并行
registerDoParallel(cores = parallel::detectCores() - 1)

all_events <- foreach(li = 1:nlat, .combine = c) %:%
  foreach(lo = 1:nlon, .combine = rbind) %dopar% {
    
    temp_ts <- t2m[, li, lo]
    
    # 跳过全 NA 格点
    if (all(is.na(temp_ts))) {
      return(NULL)
    }
    
    # 转换为 ts 对象
    # heatwaveR 需要至少两年的数据
    if (sum(!is.na(temp_ts)) < 730) {
      return(NULL)
    }
    
    tryCatch({
      # 检测热浪
      events <- heatwaveR::detect_event(
        temp_ts,
        climatology = TRUE,
        threshold = 90,
        minDuration = 5,
        maxGap = 2,
        start_date = min(dates, na.rm = TRUE)
      )
      
      if (!is.null(events$event) && nrow(events$event) > 0) {
        ev <- events$event
        ev$lat_idx <- li
        ev$lon_idx <- lo
        ev$lat <- lat[li]
        ev$lon <- lon[lo]
        return(ev)
      } else {
        return(NULL)
      }
    }, error = function(e) {
      # 某些格点可能检测失败，跳过
      return(NULL)
    })
  }

stopImplicitCluster()

cat(sprintf("Total THW events detected: %d\n", nrow(all_events)))

# 保存结果
saveRDS(all_events, output_file)
cat(sprintf("Saved to: %s\n", output_file))
```

**Python 调用方式**:
```python
import subprocess
import os

def detect_thw(eobs_filepath: str, output_path: str, clim_period: tuple):
    """调用 R 脚本检测陆地热浪。"""
    result = subprocess.run(
        [
            "Rscript",
            os.path.join("python", "detect_thw.R"),
            eobs_filepath,
            output_path,
            str(clim_period[0]),
            str(clim_period[1]),
        ],
        capture_output=True,
        text=True,
        check=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        raise RuntimeError("R heatwaveR detection failed")
```

---

### 3.5 `coastal_mask.py` — 沿海格点掩码与配对

**文件路径**: `python/coastal_mask.py`  
**功能**: 构建陆地-海洋邻接掩码，识别配对的沿海格点对。

```python
"""
coastal_mask.py — 沿海格点掩码与配对
"""
import numpy as np
from scipy.ndimage import binary_erosion, generate_binary_structure
from typing import List, Tuple, Dict
import xarray as xr

from config import COASTAL_BUFFER_KM


def build_land_mask(eobs: xr.Dataset) -> xr.DataArray:
    """
    从 E-OBS 构建陆地掩码（非海洋区域）。
    
    Parameters:
        eobs: E-OBS Dataset
    
    Returns:
        land_mask: (lat, lon) 1=陆地, 0=海洋
    """
    # 使用 T2m 的非 NaN 值作为陆地掩码
    # 取时间均值，排除海洋格点
    land_mask = ~np.isnan(eobs['T2m'].mean(dim='time').values)
    land_mask = land_mask.astype(np.int8)
    
    return xr.DataArray(
        land_mask,
        dims=['lat', 'lon'],
        coords={'lat': eobs.lat, 'lon': eobs.lon},
        name='land_mask'
    )


def build_ocean_mask(oisst: xr.Dataset) -> xr.DataArray:
    """
    从 OISST 构建海洋掩码（有效 SST 区域）。
    
    Parameters:
        oisst: OISST Dataset
    
    Returns:
        ocean_mask: (lat, lon) 1=有效海洋, 0=无效
    """
    # 取时间均值，排除陆地/冰区
    sst_mean = oisst['SST'].mean(dim='time')
    ocean_mask = ~np.isnan(sst_mean.values)
    ocean_mask = ocean_mask.astype(np.int8)
    
    # 注意：OISST 和 E-OBS 的格点可能不对齐
    # 实际项目中需做重采样到统一网格
    return xr.DataArray(
        ocean_mask,
        dims=['lat', 'lon'],
        coords={'lat': oisst.lat, 'lon': oisst.lon},
        name='ocean_mask'
    )


def find_coastal_grid_pairs(
    land_mask: np.ndarray,
    ocean_mask: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray
) -> List[Tuple[int, int, int, int]]:
    """
    使用 4-连通邻域方法识别沿海格点对。
    
    Parameters:
        land_mask: (lat, lon) 1=陆地, 0=海洋
        ocean_mask: (lat, lon) 1=海洋, 0=陆地
        lat: 纬度数组
        lon: 经度数组
    
    Returns:
        pairs: [(land_lat_idx, land_lon_idx, ocean_lat_idx, ocean_lon_idx), ...]
    """
    s = generate_binary_structure(2, 4)  # 4-connected
    nlat, nlon = land_mask.shape
    pairs = []
    
    for i in range(1, nlat - 1):
        for j in range(1, nlon - 1):
            if land_mask[i, j] == 1:
                # 检查 4 邻域是否有海洋格点
                neighbors = [
                    (i-1, j), (i+1, j), (i, j-1), (i, j+1)
                ]
                for ni, nj in neighbors:
                    if 0 <= ni < nlat and 0 <= nj < nlon:
                        if ocean_mask[ni, nj] == 1:
                            pairs.append((i, j, ni, nj))
                            break  # 每个陆地格点只配一个海洋格点
    
    return pairs


def build_coastal_mask(
    land_mask: xr.DataArray,
    ocean_mask: xr.DataArray
) -> xr.DataArray:
    """
    构建沿海掩码：陆地格点且相邻海洋格点。
    
    Parameters:
        land_mask: 陆地掩码 DataArray
        ocean_mask: 海洋掩码 DataArray
    
    Returns:
        coastal_mask: (lat, lon) 1=沿海格点, 0=内陆/远海
    """
    land_arr = land_mask.values.astype(np.int8)
    ocean_arr = ocean_mask.values.astype(np.int8)
    
    # 找到陆地边缘
    s = generate_binary_structure(2, 4)
    land_eroded = binary_erosion(land_arr, structure=s)
    land_edge = land_arr & ~land_eroded
    
    # 找到海洋边缘（靠近陆地的海洋格点）
    ocean_eroded = binary_erosion(ocean_arr, structure=s)
    ocean_edge = ocean_arr & ~ocean_eroded
    
    # 沿海 = 陆地边缘 OR 靠近陆地的海洋边缘
    coastal = land_edge | ocean_edge
    
    return xr.DataArray(
        coastal,
        dims=['lat', 'lon'],
        coords={'lat': land_mask.lat, 'lon': land_mask.lon},
        name='coastal_mask'
    )


def get_grid_pair_info(
    pairs: List[Tuple[int, int, int, int]],
    lat: xr.DataArray,
    lon: xr.DataArray
) -> pd.DataFrame:
    """
    将配对列表转换为 DataFrame，方便后续查询。
    
    Returns:
        pair_df: DataFrame with columns [land_lat_idx, land_lon_idx, ocean_lat_idx, ocean_lon_idx,
                                         land_lat, land_lon, ocean_lat, ocean_lon]
    """
    rows = []
    for li, lj, oi, oj in pairs:
        rows.append({
            'land_lat_idx': li,
            'land_lon_idx': lj,
            'ocean_lat_idx': oi,
            'ocean_lon_idx': oj,
            'land_lat': float(lat[li].values),
            'land_lon': float(lon[lj].values),
            'ocean_lat': float(lat[oi].values),
            'ocean_lon': float(lon[oj].values),
        })
    return pd.DataFrame(rows)
```

---

### 3.6 `compound_events.py` — 复合事件识别

**文件路径**: `python/compound_events.py`  
**功能**: 识别复合海洋-陆地热浪（MHW 完全涵盖 THW）。

```python
"""
compound_events.py — 复合事件识别
"""
import numpy as np
import pandas as pd
import xarray as xr
from typing import List, Tuple, Optional

from config import DURATION_THRESH, GAP_TOLERANCE


def is_event_contained(
    thw_start: pd.Timestamp,
    thw_end: pd.Timestamp,
    mhw_start: pd.Timestamp,
    mhw_end: pd.Timestamp
) -> bool:
    """
    判断 MHW 是否完全涵盖 THW。
    
    Parameters:
        thw_start, thw_end: 陆地热浪起止时间
        mhw_start, mhw_end: 海洋热浪起止时间
    
    Returns:
        True if MHW completely covers THW
    """
    return (mhw_start <= thw_start) and (mhw_end >= thw_end)


def identify_compound_events(
    mhw_events: pd.DataFrame,
    thw_events: pd.DataFrame,
    grid_pairs: pd.DataFrame
) -> pd.DataFrame:
    """
    识别复合海洋-陆地热浪事件。
    
    Parameters:
        mhw_events: MHW 事件表（来自 detect_mhw_all_grids）
        thw_events: THW 事件表（来自 R heatwaveR）
        grid_pairs: 配对的格点 DataFrame（来自 get_grid_pair_info）
    
    Returns:
        compound_events: 复合事件 DataFrame
    """
    compound = []
    
    for _, thw in thw_events.iterrows():
        # 获取当前 THW 格点对应的海洋格点
        land_pair = grid_pairs[
            (grid_pairs['land_lat_idx'] == thw['lat_idx']) &
            (grid_pairs['land_lon_idx'] == thw['lon_idx'])
        ]
        
        if len(land_pair) == 0:
            continue
        
        ocean_lat_idx = int(land_pair.iloc[0]['ocean_lat_idx'])
        ocean_lon_idx = int(land_pair.iloc[0]['ocean_lon_idx'])
        
        # 查找该海洋格点的 MHW 事件
        mhw_at_ocean = mhw_events[
            (mhw_events['lat_idx'] == ocean_lat_idx) &
            (mhw_events['lon_idx'] == ocean_lon_idx)
        ]
        
        thw_start = pd.Timestamp(thw['event_start'])
        thw_end = pd.Timestamp(thw['event_end'])
        
        for _, mhw in mhw_at_ocean.iterrows():
            mhw_start = pd.Timestamp(mhw['event_start'])
            mhw_end = pd.Timestamp(mhw['event_end'])
            
            if is_event_contained(thw_start, thw_end, mhw_start, mhw_end):
                compound.append({
                    'thw_start': thw_start,
                    'thw_end': thw_end,
                    'thw_duration': thw['duration'],
                    'mhw_start': mhw_start,
                    'mhw_end': mhw_end,
                    'mhw_duration': mhw['duration'],
                    'land_lat_idx': thw['lat_idx'],
                    'land_lon_idx': thw['lon_idx'],
                    'ocean_lat_idx': ocean_lat_idx,
                    'ocean_lon_idx': ocean_lon_idx,
                    'land_lat': thw['lat'],
                    'land_lon': thw['lon'],
                })
                break  # 每个 THW 只匹配第一个涵盖它的 MHW
    
    return pd.DataFrame(compound)


def compound_events_to_daily(
    compound_events: pd.DataFrame,
    time: xr.DataArray,
    lat: xr.DataArray,
    lon: xr.DataArray
) -> xr.DataArray:
    """
    将复合事件表转换为日度格点数据。
    
    Parameters:
        compound_events: 复合事件 DataFrame
        time: 时间坐标
        lat: 纬度坐标
        lon: 经度坐标
    
    Returns:
        compound_daily: (time, lat, lon) 二值 DataArray，1=复合热浪日
    """
    nt = len(time)
    nlat = len(lat)
    nlon = len(lon)
    
    compound_daily = np.zeros((nt, nlat, nlon), dtype=np.int8)
    
    for _, event in compound_events.iterrows():
        time_start = pd.Timestamp(event['thw_start'])
        time_end = pd.Timestamp(event['thw_end'])
        
        time_mask = (time >= time_start) & (time <= time_end)
        li = int(event['land_lat_idx'])
        lo = int(event['land_lon_idx'])
        
        compound_daily[time_mask, li, lo] = 1
    
    return xr.DataArray(
        compound_daily,
        dims=['time', 'lat', 'lon'],
        coords={'time': time, 'lat': lat, 'lon': lon},
        name='compound_mhw_thw',
        attrs={'long_name': 'Compound MHW-THW Day', 'units': '0/1'}
    )


def calc_standalone_days(
    thw_events: pd.DataFrame,
    mhw_events: pd.DataFrame,
    grid_pairs: pd.DataFrame,
    time: xr.DataArray,
    lat: xr.DataArray,
    lon: xr.DataArray
) -> xr.DataArray:
    """
    计算独立陆地热浪天数（THW 期间无并发 MHW）。
    
    Parameters:
        thw_events: 陆地热浪事件表
        mhw_events: 海洋热浪事件表
        grid_pairs: 格点配对 DataFrame
        time, lat, lon: 坐标
    
    Returns:
        standalone_daily: (time, lat, lon) 二值 DataArray
    """
    nt = len(time)
    nlat = len(lat)
    nlon = len(lon)
    
    standalone_daily = np.zeros((nt, nlat, nlon), dtype=np.int8)
    
    for _, thw in thw_events.iterrows():
        land_pair = grid_pairs[
            (grid_pairs['land_lat_idx'] == thw['lat_idx']) &
            (grid_pairs['land_lon_idx'] == thw['lon_idx'])
        ]
        
        if len(land_pair) == 0:
            continue
        
        ocean_lat_idx = int(land_pair.iloc[0]['ocean_lat_idx'])
        ocean_lon_idx = int(land_pair.iloc[0]['ocean_lon_idx'])
        
        thw_start = pd.Timestamp(thw['event_start'])
        thw_end = pd.Timestamp(thw['event_end'])
        
        # 检查 THW 期间是否有 MHW
        mhw_at_ocean = mhw_events[
            (mhw_events['lat_idx'] == ocean_lat_idx) &
            (mhw_events['lon_idx'] == ocean_lon_idx)
        ]
        
        has_concurrent_mhw = False
        for _, mhw in mhw_at_ocean.iterrows():
            mhw_start = pd.Timestamp(mhw['event_start'])
            mhw_end = pd.Timestamp(mhw['event_end'])
            
            # 如果有任何重叠，就不是独立的
            if not (mhw_end < thw_start or mhw_start > thw_end):
                has_concurrent_mhw = True
                break
        
        if not has_concurrent_mhw:
            time_mask = (time >= thw_start) & (time <= thw_end)
            li = int(thw['lat_idx'])
            lo = int(thw['lon_idx'])
            standalone_daily[time_mask, li, lo] = 1
    
    return xr.DataArray(
        standalone_daily,
        dims=['time', 'lat', 'lon'],
        coords={'time': time, 'lat': lat, 'lon': lon},
        name='standalone_thw',
        attrs={'long_name': 'Stand-alone THW Day', 'units': '0/1'}
    )
```

---

### 3.7 `calc_chr.py` — 复合热浪比 (CHR)

**文件路径**: `python/calc_chr.py`  
**功能**: 计算 CHR = 复合天数 / 独立陆地热浪天数，以及共现概率。

```python
"""
calc_chr.py — 复合热浪比 (CHR) 和共现概率计算
"""
import numpy as np
import xarray as xr
from typing import Optional


def calc_CHR(
    compound_days: xr.DataArray,
    standalone_days: xr.DataArray
) -> xr.DataArray:
    """
    计算复合热浪比 (Compound Heatwave Ratio)。
    
    CHR = 复合热浪天数 / 独立陆地热浪天数
    
    Parameters:
        compound_days: 年度复合热浪天数 (year, lat, lon)
        standalone_days: 年度独立陆地热浪天数 (year, lat, lon)
    
    Returns:
        CHR: 复合热浪比 (year, lat, lon)
    """
    CHR = compound_days / standalone_days
    CHR = CHR.where(standalone_days > 0, np.nan)  # 避免除零
    CHR.attrs['long_name'] = 'Compound Heatwave Ratio'
    CHR.attrs['units'] = 'dimensionless'
    return CHR


def calc_cooccurrence_prob(
    compound_days: xr.DataArray,
    thw_days: xr.DataArray
) -> xr.DataArray:
    """
    计算共现概率 = 复合天数 / 陆地热浪天数。
    
    Parameters:
        compound_days: 年度复合热浪天数 (year, lat, lon)
        thw_days: 年度陆地热浪总天数 (year, lat, lon)
    
    Returns:
        prob: 共现概率 (year, lat, lon)
    """
    prob = compound_days / thw_days
    prob = prob.where(thw_days > 0, np.nan)
    prob.attrs['long_name'] = 'Co-occurrence Probability'
    prob.attrs['units'] = 'fraction'
    return prob


def calc_annual_days(daily: xr.DataArray) -> xr.DataArray:
    """
    将日度数据转换为年度总和。
    
    Parameters:
        daily: (time, lat, lon) 日度二值数据
    
    Returns:
        annual: (year, lat, lon) 年度天数
    """
    annual = daily.groupby('time.year').sum(dim='time')
    annual = annual.rename({'year': 'time'})
    annual.attrs['units'] = 'days/year'
    return annual


def calc_spatial_mean(
    da: xr.DataArray,
    lat_range: Optional[tuple] = None,
    lon_range: Optional[tuple] = None
) -> xr.DataArray:
    """
    计算空间平均值（可选裁剪区域）。
    
    Parameters:
        da: (time, lat, lon) 数据
        lat_range: (south, north) 纬度范围
        lon_range: (west, east) 经度范围
    
    Returns:
        spatial_mean: (time,) 空间平均时间序列
    """
    if lat_range is not None:
        da = da.sel(lat=slice(lat_range[0], lat_range[1]))
    if lon_range is not None:
        da = da.sel(lon=slice(lon_range[0], lon_range[1]))
    
    return da.mean(dim=['lat', 'lon'])
```

---

### 3.8 `calc_wbt.py` — 湿球温度计算

**文件路径**: `python/calc_wbt.py`  
**功能**: 从 ERA5 的 Tmax、露点温度、地表气压计算 WBT。

```python
"""
calc_wbt.py — 湿球温度 (WBT) 计算
"""
import numpy as np
import xarray as xr
from typing import Optional


def calc_relative_humidity(
    tmax: xr.DataArray,
    d2m: xr.DataArray
) -> xr.DataArray:
    """
    从 Tmax 和露点温度计算相对湿度。
    
    使用 Magnus 公式计算饱和水汽压:
    es(T) = 6.112 * exp(17.67 * T / (T + 243.5))
    
    Parameters:
        tmax: 日最高气温 (°C)
        d2m: 露点温度 (°C)
    
    Returns:
        RH: 相对湿度 (%)
    """
    # 饱和水汽压
    es_tmax = 6.112 * np.exp(17.67 * tmax / (tmax + 243.5))
    es_d2m = 6.112 * np.exp(17.67 * d2m / (d2m + 243.5))
    
    # 实际水汽压
    e = es_d2m
    
    # 相对湿度
    RH = (e / es_tmax) * 100
    RH = xr.where(RH > 100, 100, RH)
    RH = xr.where(RH < 0, 0, RH)
    
    RH.attrs['long_name'] = 'Relative Humidity'
    RH.attrs['units'] = '%'
    
    return RH


def calc_WBT_stull(
    tmax: xr.DataArray,
    d2m: xr.DataArray,
    sp: xr.DataArray
) -> xr.DataArray:
    """
    使用 Stull (2011) 近似公式计算湿球温度。
    
    公式:
    WBT ≈ T * atan(0.151977 * sqrt(RH + 8.313659))
          + atan(T + RH) - atan(RH - 1.676331)
          + 0.00391838 * RH^(3/2) * atan(0.023101 * RH)
          - 4.686035
    
    注意: Stull 公式在高温高湿条件下可能有偏差，
    如需更高精度，请使用 calc_WBT_iterative。
    
    Parameters:
        tmax: 日最高气温 (°C)
        d2m: 露点温度 (°C)
        sp: 地表气压 (Pa)
    
    Returns:
        WBT: 湿球温度 (°C)
    """
    RH = calc_relative_humidity(tmax, d2m)
    
    T = tmax.values
    RH_arr = RH.values
    
    WBT = (
        T * np.arctan(0.151977 * np.sqrt(RH_arr + 8.313659))
        + np.arctan(T + RH_arr)
        - np.arctan(RH_arr - 1.676331)
        + 0.00391838 * RH_arr**1.5 * np.arctan(0.023101 * RH_arr)
        - 4.686035
    )
    
    WBT_da = xr.DataArray(
        WBT,
        dims=tmax.dims,
        coords=tmax.coords,
        name='WBT'
    )
    WBT_da.attrs['long_name'] = 'Wet-Bulb Temperature'
    WBT_da.attrs['units'] = 'degC'
    
    return WBT_da


def calc_WBT_iterative(
    tmax: xr.DataArray,
    d2m: xr.DataArray,
    sp: xr.DataArray,
    max_iter: int = 100,
    tol: float = 0.01
) -> xr.DataArray:
    """
    使用迭代方法精确计算湿球温度。
    
    通过求解以下方程的根:
    e_ws(T_w) - e_w(T_w, p) * (A / p) * (B - C * T_w)
    
    其中:
    - e_ws: 饱和水汽压（T_w 的函数）
    - e_w: 实际水汽压（由露点温度计算）
    - A, B, C:  psychrometric 常数
    
    本实现使用数值迭代（简化版）:
    T_w(n+1) = T * atan(0.151977 * sqrt(RH + 8.313659)) + ...
    
    为简化，这里使用二分法或固定点迭代。
    
    Parameters:
        tmax: 日最高气温 (°C)
        d2m: 露点温度 (°C)
        sp: 地表气压 (Pa)
        max_iter: 最大迭代次数
        tol: 收敛容差
    
    Returns:
        WBT: 湿球温度 (°C)
    """
    # 先从露点计算实际水汽压
    e = 6.112 * np.exp(17.67 * d2m / (d2m + 243.5))  # hPa
    
    # 气压转换为 hPa
    p = sp.values / 100.0  # Pa -> hPa
    
    # 初始猜测：使用 Stull 公式
    WBT_guess = calc_WBT_stull(tmax, d2m, sp).values
    
    # 迭代优化（简化版）
    for _ in range(max_iter):
        # 计算当前猜测下的饱和水汽压
        es_current = 6.112 * np.exp(17.67 * WBT_guess / (WBT_guess + 243.5))
        
        # 计算新的 WBT 估计
        # 简化 psychrometric 方程
        gamma = 0.00066 * (1 + 0.00115 * e)  # psychrometric 常数近似
        WBT_new = tmax.values - (tmax.values - d2m.values) / (1 + gamma * p / 10)
        
        # 检查收敛
        if np.max(np.abs(WBT_new - WBT_guess)) < tol:
            break
        
        WBT_guess = WBT_new
    
    WBT_da = xr.DataArray(
        WBT_guess,
        dims=tmax.dims,
        coords=tmax.coords,
        name='WBT'
    )
    WBT_da.attrs['long_name'] = 'Wet-Bulb Temperature (iterative)'
    WBT_da.attrs['units'] = 'degC'
    
    return WBT_da


def calc_WBT(
    tmax: xr.DataArray,
    d2m: xr.DataArray,
    sp: xr.DataArray,
    method: str = 'stull'
) -> xr.DataArray:
    """
    WBT 计算入口函数。
    
    Parameters:
        tmax: 日最高气温 (°C)
        d2m: 露点温度 (°C)
        sp: 地表气压 (Pa)
        method: 'stull' (快速) 或 'iterative' (精确)
    
    Returns:
        WBT: 湿球温度 (°C)
    """
    if method == 'stull':
        return calc_WBT_stull(tmax, d2m, sp)
    elif method == 'iterative':
        return calc_WBT_iterative(tmax, d2m, sp)
    else:
        raise ValueError(f"Unknown method: {method}. Choose 'stull' or 'iterative'.")


def calc_specific_humidity(
    d2m: xr.DataArray,
    sp: xr.DataArray
) -> xr.DataArray:
    """
    从露点温度和地表气压计算比湿。
    
    q = 0.622 * e / (p - 0.378 * e)
    
    其中 e 为实际水汽压，p 为气压。
    
    Parameters:
        d2m: 露点温度 (°C)
        sp: 地表气压 (Pa)
    
    Returns:
        q: 比湿 (g/kg)
    """
    e = 6.112 * np.exp(17.67 * d2m / (d2m + 243.5))  # hPa
    p = sp.values / 100.0  # Pa -> hPa
    
    q = 0.622 * e / (p - 0.378 * e)  # kg/kg
    q = q * 1000  # kg/kg -> g/kg
    
    q_da = xr.DataArray(
        q,
        dims=d2m.dims,
        coords=d2m.coords,
        name='specific_humidity'
    )
    q_da.attrs['long_name'] = 'Specific Humidity'
    q_da.attrs['units'] = 'g/kg'
    
    return q_da
```

---

### 3.9 `attribution.py` — FAR/PR 计算 + Bootstrap

**文件路径**: `python/attribution.py`  
**功能**: 对 CESM1-LE 数据进行归因分析，计算 FAR 和 PR，使用并行 bootstrap。

```python
"""
attribution.py — 归因分析 (FAR/PR) + Bootstrap
"""
import numpy as np
import xarray as xr
import pandas as pd
from joblib import Parallel, delayed
from typing import Dict, Tuple

from config import N_BOOTSTRAP, CI_ALPHA, N_JOBS


# ──────────────────────────────────────────────
# FAR / PR 计算公式
# ──────────────────────────────────────────────

def calc_FAR(p_factual: float, p_counterfactual: float) -> float:
    """
    可归因风险比例 (Fraction of Attributable Risk)。
    
    FAR = 1 - P_factual / P_counterfactual
    
    表示: 事件在没有 GHG 强迫下不会发生的概率。
    
    Parameters:
        p_factual: 全强迫下事件发生概率
        p_counterfactual: 反事实 (FixGHG) 下事件发生概率
    
    Returns:
        FAR: 0 到 1 之间的值
    """
    if p_counterfactual <= 0:
        return 1.0
    return 1.0 - (p_factual / p_counterfactual)


def calc_PR(p_factual: float, p_counterfactual: float) -> float:
    """
    概率比 (Probability Ratio)。
    
    PR = P_factual / P_counterfactual
    
    表示: 全强迫下事件发生概率是反事实的多少倍。
    
    Parameters:
        p_factual: 全强迫下事件发生概率
        p_counterfactual: 反事实下事件发生概率
    
    Returns:
        PR: 正实数，可能为 inf
    """
    if p_counterfactual <= 0:
        return np.inf
    return p_factual / p_counterfactual


# ──────────────────────────────────────────────
# Bootstrap 核心
# ──────────────────────────────────────────────

def calc_probability(
    ds: xr.Dataset,
    threshold: float,
    varname: str = 'T2m'
) -> float:
    """
    计算给定阈值下事件发生的概率（超过阈值的天数比例）。
    
    Parameters:
        ds: CESM1-LE Dataset (member, time, lat, lon)
        threshold: 复合热浪天数阈值（注意：这里实际处理的是已检测的热浪天数）
        varname: 变量名
    
    Returns:
        prob: 概率值 (0-1)
    """
    # 将温度数据转换为热浪天数（需先检测热浪）
    # 这里简化：假设输入已经是热浪天数
    data = ds[varname]
    
    # 计算每年每个格点的热浪天数
    annual_days = data.groupby('time.year').sum(dim='time')
    
    # 计算超过阈值的概率
    exceed_count = (annual_days >= threshold).sum().values
    total_count = annual_days.size
    
    if total_count == 0:
        return 0.0
    
    return float(exceed_count) / float(total_count)


def single_bootstrap_iteration(
    all_data: xr.Dataset,
    fixghg_data: xr.Dataset,
    threshold: float,
    all_members: list,
    fixghg_members: list,
    n_all: int = 20,
    n_fixghg: int = 20
) -> Tuple[float, float]:
    """
    单次 bootstrap 迭代：有放回抽样成员，计算 FAR 和 PR。
    
    Parameters:
        all_data: ALL 强迫数据
        fixghg_data: FixGHG 数据
        threshold: 复合热浪天数阈值
        all_members: ALL 成员列表
        fixghg_members: FixGHG 成员列表
        n_all: ALL 抽样成员数
        n_fixghg: FixGHG 抽样成员数
    
    Returns:
        far_val, pr_val
    """
    # 有放回抽样
    all_sample_idx = np.random.choice(all_members, size=n_all, replace=True)
    fixghg_sample_idx = np.random.choice(fixghg_members, size=n_fixghg, replace=True)
    
    all_sample = all_data.sel(member=all_sample_idx)
    fixghg_sample = fixghg_data.sel(member=fixghg_sample_idx)
    
    # 计算概率
    p_all = calc_probability(all_sample, threshold)
    p_fixghg = calc_probability(fixghg_sample, threshold)
    
    # 计算 FAR 和 PR
    far = calc_FAR(p_all, p_fixghg)
    pr = calc_PR(p_all, p_fixghg)
    
    return far, pr


def bootstrap_FAR_PRC(
    all_data: xr.Dataset,
    fixghg_data: xr.Dataset,
    thresholds: np.ndarray,
    n_bootstrap: int = N_BOOTSTRAP,
    n_jobs: int = N_JOBS,
    all_members: Optional[list] = None,
    fixghg_members: Optional[list] = None
) -> Dict[str, np.ndarray]:
    """
    并行 bootstrap 计算 FAR 和 PR 曲线。
    
    这是整个项目最耗时的步骤（预计 2-4 周，取决于 CPU 核数）。
    
    Parameters:
        all_data: ALL 强迫 CESM1-LE 数据 (member, time, lat, lon)
        fixghg_data: FixGHG 数据
        thresholds: 复合热浪天数阈值数组
        n_bootstrap: 自助采样次数
        n_jobs: 并行核心数
        all_members: ALL 成员 ID 列表
        fixghg_members: FixGHG 成员 ID 列表
    
    Returns:
        results: 包含 FAR/PR 均值、置信区间的字典
    """
    if all_members is None:
        all_members = all_data.member.values.tolist()
    if fixghg_members is None:
        fixghg_members = fixghg_data.member.values.tolist()
    
    n_thresh = len(thresholds)
    
    # 存储所有 bootstrap 结果
    far_array = np.zeros((n_bootstrap, n_thresh))
    pr_array = np.zeros((n_bootstrap, n_thresh))
    
    # 单次 bootstrap 的函数（闭包捕获 threshold 索引）
    def run_single(b: int):
        results_thresh = []
        for ti, thresh in enumerate(thresholds):
            far_val, pr_val = single_bootstrap_iteration(
                all_data, fixghg_data, thresh,
                all_members, fixghg_members
            )
            results_thresh.append((far_val, pr_val))
        return results_thresh
    
    # 并行执行
    print(f"Running {n_bootstrap} bootstrap iterations with {n_jobs} cores...")
    parallel_results = Parallel(n_jobs=n_jobs, backend='loky', verbose=5)(
        delayed(run_single)(b) for b in range(n_bootstrap)
    )
    
    # 汇总结果
    for b in range(n_bootstrap):
        for ti, (far_val, pr_val) in enumerate(parallel_results[b]):
            far_array[b, ti] = far_val
            pr_array[b, ti] = pr_val
    
    # 计算统计量
    far_mean = far_array.mean(axis=0)
    far_ci_lower = np.percentile(far_array, CI_ALPHA[0] * 100, axis=0)
    far_ci_upper = np.percentile(far_array, CI_ALPHA[1] * 100, axis=0)
    
    pr_mean = pr_array.mean(axis=0)
    pr_ci_lower = np.percentile(pr_array, CI_ALPHA[0] * 100, axis=0)
    pr_ci_upper = np.percentile(pr_array, CI_ALPHA[1] * 100, axis=0)
    
    return {
        'thresholds': thresholds,
        'FAR_mean': far_mean,
        'FAR_ci_lower': far_ci_lower,
        'FAR_ci_upper': far_ci_upper,
        'PR_mean': pr_mean,
        'PR_ci_lower': pr_ci_lower,
        'PR_ci_upper': pr_ci_upper,
        'FAR_all_samples': far_array,   # 保留原始样本用于后续分析
        'PR_all_samples': pr_array,
    }
```

---

### 3.10 `fig1_compound_spatial.py` — 图 1: 复合事件空间分布与时间序列

**文件路径**: `python/fig1_compound_spatial.py`  
**功能**: 生成论文图 1（a-i 空间分布、j-l 时间序列、m 共现概率）。

```python
"""
fig1_compound_spatial.py — Figure 1
"""
import os, numpy as np, matplotlib.pyplot as plt
import cartopy.crs as ccrs, cartopy.feature as cfeature
import xarray as xr
from config import INTERMEDIATE_DIR, FIGURES_DIR

def plot_figure1(output_dir=None):
    # ...（详见实际代码）
    pass
```

---

### 3.11 `fig2_chr.py` — 图 2: CHR 分析

**文件路径**: `python/fig2_chr.py`  
**功能**: 生成论文图 2（a-d CHR 对比分析）。

---

### 3.12 `figures.py` — 一键生成全部图表

**文件路径**: `python/figures.py`  
**功能**: 统一入口，按顺序生成图 1-6、补充图 S1、表 1。

---

### 3.11 `run_all.py` — 一键运行入口

**文件路径**: `python/run_all.py`  
**功能**: 串联所有步骤，一键运行完整流程。

```python
#!/usr/bin/env python3
"""
run_all.py — 一键运行完整复现流程

Usage:
    python run_all.py                          # 全量运行
    python run_all.py --skip-download          # 跳过下载（数据已就绪）
    python run_all.py --skip-detection         # 跳过热浪检测
    python run_all.py --skip-attribution       # 跳过归因分析（最耗时）
    python run_all.py --help                   # 查看帮助

预计总运行时间（含归因）: 2-4 周（取决于 CPU 核数）
"""
import argparse
import os
import sys
import time
from datetime import datetime

# 确保 python/ 在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from config import (
    DATA_DIR, INTERMEDIATE_DIR, RESULTS_DIR,
    CLIM_PERIOD, N_BOOTSTRAP, N_JOBS,
    CESM_ALL_MEMBERS, CESM_FIXGHG_MEMBERS
)
from load_data import preprocess_all, load_oisst, load_eobs, load_era5_var
from detect_mhw import detect_mhw_all_grids, mhw_events_to_daily
from detect_thw import detect_thw  # R 调用
from coastal_mask import (
    build_land_mask, build_ocean_mask,
    find_coastal_grid_pairs, get_grid_pair_info
)
from compound_events import (
    identify_compound_events,
    compound_events_to_daily,
    calc_standalone_days
)
from calc_chr import calc_CHR, calc_cooccurrence_prob, calc_annual_days
from calc_wbt import calc_WBT, calc_specific_humidity
from attribution import bootstrap_FAR_PRC, load_cesm1le_dir
from figures import generate_all_figures


def parse_args():
    parser = argparse.ArgumentParser(description="Run full heatwave attribution pipeline")
    parser.add_argument('--skip-download', action='store_true', help='Skip data download')
    parser.add_argument('--skip-detection', action='store_true', help='Skip heatwave detection')
    parser.add_argument('--skip-attribution', action='store_true', help='Skip attribution analysis')
    parser.add_argument('--n-jobs', type=int, default=N_JOBS, help='Number of parallel jobs')
    return parser.parse_args()


def log(msg: str):
    """带时间戳的日志输出。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")


def main():
    args = parse_args()
    
    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(RESULTS_DIR, "figures"), exist_ok=True)
    os.makedirs(os.path.join(RESULTS_DIR, "tables"), exist_ok=True)
    
    # ──────────────────────────────────────────────
    # Step 1: 加载数据
    # ──────────────────────────────────────────────
    log("[Step 1/6] Loading and preprocessing data...")
    t0 = time.time()
    
    data = preprocess_all()
    oisst = data['oisst']
    eobs = data['eobs']
    era5_tmax = data['era5_tmax']
    era5_d2m = data['era5_d2m']
    era5_sp = data['era5_sp']
    
    log(f"Data loaded in {time.time() - t0:.1f}s")
    
    # ──────────────────────────────────────────────
    # Step 2: 热浪检测
    # ──────────────────────────────────────────────
    if not args.skip_detection:
        log("[Step 2/6] Detecting marine heatwaves...")
        t0 = time.time()
        
        mhw_events = detect_mhw_all_grids(oisst['SST'], CLIM_PERIOD)
        mhw_daily = mhw_events_to_daily(
            mhw_events, oisst.time, oisst.lat, oisst.lon
        )
        mhw_events.to_netcdf(os.path.join(INTERMEDIATE_DIR, "mhw_events.nc"))
        mhw_daily.to_netcdf(os.path.join(INTERMEDIATE_DIR, "mhw_daily.nc"))
        log(f"MHW detection done: {len(mhw_events)} events in {time.time() - t0:.1f}s")
        
        log("[Step 2b/6] Detecting terrestrial heatwaves (R/heatwaveR)...")
        t0 = time.time()
        
        thw_output = os.path.join(INTERMEDIATE_DIR, "thw_events.rds")
        detect_thw(
            os.path.join(DATA_DIR, "E-OBS", "EOBS_tg_1984_2023.nc"),
            thw_output,
            CLIM_PERIOD
        )
        log(f"THW detection done in {time.time() - t0:.1f}s")
        
        # 加载 R 结果
        import rpy2.robjects as ro
        thw_events = ro.r('readRDS')(thw_output)
        # 转换为 pandas DataFrame（需要 rpy2 的 pandas 接口）
        from rpy2.robjects import pandas2ri
        with pandas2ri.localconverter():
            thw_events_df = ro.conversion.rpy2py(thw_events)
    else:
        log("[Step 2/6] Skipping detection, loading cached results...")
        mhw_daily = xr.open_dataarray(os.path.join(INTERMEDIATE_DIR, "mhw_daily.nc"))
        # ... 加载其他缓存
    
    # ──────────────────────────────────────────────
    # Step 3: 沿海格点配对与复合事件识别
    # ──────────────────────────────────────────────
    log("[Step 3/6] Building coastal mask and identifying compound events...")
    t0 = time.time()
    
    land_mask = build_land_mask(eobs)
    ocean_mask = build_ocean_mask(oisst)
    pairs = find_coastal_grid_pairs(
        land_mask.values, ocean_mask.values,
        eobs.lat.values, eobs.lon.values
    )
    pair_df = get_grid_pair_info(pairs, eobs.lat, eobs.lon)
    
    compound_events = identify_compound_events(mhw_events, thw_events_df, pair_df)
    compound_daily = compound_events_to_daily(
        compound_events, eobs.time, eobs.lat, eobs.lon
    )
    standalone_daily = calc_standalone_days(
        thw_events_df, mhw_events, pair_df,
        eobs.time, eobs.lat, eobs.lon
    )
    
    # 保存
    compound_events.to_csv(os.path.join(INTERMEDIATE_DIR, "compound_events.csv"))
    compound_daily.to_netcdf(os.path.join(INTERMEDIATE_DIR, "compound_daily.nc"))
    standalone_daily.to_netcdf(os.path.join(INTERMEDIATE_DIR, "standalone_daily.nc"))
    
    log(f"Compound events identified in {time.time() - t0:.1f}s")
    
    # ──────────────────────────────────────────────
    # Step 4: 计算 CHR 和 WBT
    # ──────────────────────────────────────────────
    log("[Step 4/6] Calculating CHR and WBT...")
    t0 = time.time()
    
    # 年度天数
    compound_days = calc_annual_days(compound_daily)
    standalone_days = calc_annual_days(standalone_daily)
    thw_days = calc_annual_days(mhw_daily)  # 陆地热浪总天数
    
    CHR = calc_CHR(compound_days, standalone_days)
    cooccurrence_prob = calc_cooccurrence_prob(compound_days, thw_days)
    
    # CHR 时间序列（地中海平均）
    CHR_ts = calc_spatial_mean(CHR, lat_range=(30, 45), lon_range=(5, 35))
    # CHR 空间分布（2003-2023 平均）
    CHR_spatial = CHR.sel(time=slice(2003, 2023)).mean(dim='time')
    
    # WBT
    WBT = calc_WBT(era5_tmax, era5_d2m, era5_sp, method='stull')
    SH = calc_specific_humidity(era5_d2m, era5_sp)
    
    # WBT 年度统计
    WBT_compound = WBT.where(compound_daily == 1).groupby('time.year').mean()
    WBT_noncompound = WBT.where(standalone_daily == 1).groupby('time.year').mean()
    
    log(f"CHR and WBT calculated in {time.time() - t0:.1f}s")
    
    # ──────────────────────────────────────────────
    # Step 5: 归因分析（最耗时）
    # ──────────────────────────────────────────────
    if not args.skip_attribution:
        log("[Step 5/6] Running attribution analysis (this is the slowest step)...")
        t0 = time.time()
        
        log("Loading CESM1-LE data...")
        cesm_all = load_cesm1le_dir("ALL")
        cesm_fixghg = load_cesm1le_dir("FixGHG")
        
        # 定义阈值范围
        thresholds = np.arange(10, 100, 5)  # 10, 15, 20, ..., 95 天
        
        log(f"Running {N_BOOTSTRAP} bootstrap iterations...")
        attr_results = bootstrap_FAR_PRC(
            cesm_all, cesm_fixghg, thresholds,
            n_bootstrap=N_BOOTSTRAP,
            n_jobs=args.n_jobs,
            all_members=CESM_ALL_MEMBERS,
            fixghg_members=CESM_FIXGHG_MEMBERS
        )
        
        log(f"Attribution done in {time.time() - t0:.1f}s")
        
        # 保存中间结果
        import pickle
        with open(os.path.join(INTERMEDIATE_DIR, "attr_results.pkl"), 'wb') as f:
            pickle.dump(attr_results, f)
    else:
        log("[Step 5/6] Skipping attribution...")
        attr_results = None
    
    # ──────────────────────────────────────────────
    # Step 6: 生成全部图表
    # ──────────────────────────────────────────────
    log("[Step 6/6] Generating figures...")
    
    generate_all_figures()
    
    log("=" * 60)
    log("ALL DONE! Results and figures saved to:")
    log(f"  {INTERMEDIATE_DIR}")
    log(f"  {FIGURES_DIR}")
    log("=" * 60)


if __name__ == "__main__":
    main()
```

---

## 4. R 代码详细规范

### 4.1 `detect_thw.R` — 陆地热浪检测

**文件路径**: `python/detect_thw.R`  
**功能**: 使用 `heatwaveR` 逐格点检测陆地热浪。

```r
#!/usr/bin/env Rscript
# detect_thw.R — 陆地热浪检测 (heatwaveR)
#
# 用法:
#   Rscript detect_thw.R <eobs_file> <output_file> <clim_start> <clim_end>
#
# 示例:
#   Rscript detect_thw.R data/E-OBS/EOBS_tg_1984_2023.nc results/thw_events.rds 1983 2012

suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))
suppressPackageStartupMessages(library(doParallel))
suppressPackageStartupMessages(library(foreach))

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 4) {
  stop("Usage: Rscript detect_thw.R <eobs_file> <output_file> <clim_start> <clim_end>")
}

eobs_file <- args[1]
output_file <- args[2]
clim_start <- as.integer(args[3])
clim_end <- as.integer(args[4])

cat(sprintf("Loading E-OBS from: %s\n", eobs_file))

# 读取 NetCDF
nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")
lat <- ncvar_get(nc, "latitude")
lon <- ncvar_get(nc, "longitude")
time <- ncvar_get(nc, "time")
nc_close(nc)

# 转置为 (time, lat, lon) — E-OBS 默认是 (lon, lat, time)
t2m <- aperm(t2m, c(3, 2, 1))

cat(sprintf("Data shape: %d time x %d lat x %d lon\n", dim(t2m)[1], dim(t2m)[2], dim(t2m)[3]))

# 设置日期
start_date <- as.Date(paste0(clim_start, "-01-01"))
dates <- seq(start_date, by = "day", length.out = dim(t2m)[1])

nlat <- dim(t2m)[2]
nlon <- dim(t2m)[3]

# 注册并行后端
n_cores <- parallel::detectCores() - 1
if (n_cores < 1) n_cores <- 1
registerDoParallel(cores = n_cores)
cat(sprintf("Using %d cores for parallel detection\n", n_cores))

cat("Detecting terrestrial heatwaves...\n")

# 逐格点检测
all_events <- foreach(li = 1:nlat, .combine = c) %:%
  foreach(lo = 1:nlon, .combine = rbind) %dopar% {
    
    temp_ts <- t2m[, li, lo]
    
    # 跳过全 NA 格点
    if (all(is.na(temp_ts))) {
      return(NULL)
    }
    
    # 至少需要 2 年数据
    if (sum(!is.na(temp_ts)) < 730) {
      return(NULL)
    }
    
    tryCatch({
      events <- heatwaveR::detect_event(
        temp_ts,
        climatology = TRUE,
        threshold = 90,
        minDuration = 5,
        maxGap = 2,
        start_date = min(dates, na.rm = TRUE)
      )
      
      if (!is.null(events$event) && nrow(events$event) > 0) {
        ev <- events$event
        ev$lat_idx <- li
        ev$lon_idx <- lo
        ev$lat <- lat[li]
        ev$lon <- lon[lo]
        return(ev)
      } else {
        return(NULL)
      }
    }, error = function(e) {
      return(NULL)
    })
  }

stopImplicitCluster()

cat(sprintf("Total THW events detected: %d\n", nrow(all_events)))

# 保存
saveRDS(all_events, output_file)
cat(sprintf("Saved to: %s\n", output_file))
```

**调用方式（Python 端）**:
```python
import subprocess
import os

def detect_thw(eobs_filepath: str, output_path: str, clim_period: tuple):
    """调用 R 脚本检测陆地热浪。"""
    result = subprocess.run(
        [
            "Rscript",
            os.path.join("python", "detect_thw.R"),
            eobs_filepath,
            output_path,
            str(clim_period[0]),
            str(clim_period[1]),
        ],
        capture_output=True,
        text=True,
        check=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        raise RuntimeError("R heatwaveR detection failed")
```

---

## 5. Python 绘图规范

### 5.1 统一绘图配置

所有图表的绘图参数集中定义在 `config.py` 中：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FIG_SIZE` | (12, 8) | 默认图形尺寸（英寸） |
| `DPI` | 300 | 输出分辨率 |
| `CMAP_HEATWAVE` | `'YlOrRd'` | 热浪填色图色标 |
| `CMAP_PROBABILITY` | `'viridis'` | 概率图色标 |

地图统一使用 `cartopy.crs.PlateCarree()` 投影，欧洲区域范围为 `[-15, 45]` 经度 × `[30, 72]` 纬度，海陆渲染使用 `cartopy.feature`。

### 5.2 `fig1_compound_spatial.py` — 图 1

**文件**: `python/fig1_compound_spatial.py`  
**面板**: a-i 年度复合热浪天数（9 个最多年份的 3×3 地图）、j-l 时空平均时间序列（复合/独立/总 THW）、m 多年均值共现概率地图  
**输出**: `results/figures/fig1_compound_spatial.pdf`

### 5.3 `fig2_chr.py` — 图 2

**文件**: `python/fig2_chr.py`  
**面板**: a 各区域年度复合天数堆叠柱状图、b 独立天数堆叠柱状图、c CHR 时间序列、d CHR 多年均值空间分布  
**输出**: `results/figures/fig2_chr.pdf`

### 5.4 `figures.py` — 一键生成

**文件**: `python/figures.py`  
**功能**: 统一入口，按顺序调用 fig1–6、supp_fig1、table1 的生成函数。

```python
from fig1_compound_spatial import plot_figure1
from fig2_chr import plot_figure2
# ...

def generate_all_figures():
    plot_figure1()
    plot_figure2()
    # ...
```

---

## 7. 代码规范

### 7.1 Python 代码风格

```python
# 遵循 PEP 8
# 使用类型注解
# 函数文档字符串使用 Google 风格

def detect_mhw_grid(
    sst: xr.DataArray,
    clim_period: tuple = (1983, 2012),
    duration: int = 5,
    gap: int = 2
) -> pd.DataFrame:
    """
    对单个格点检测海洋热浪。
    
    Args:
        sst: 日度海表温度时间序列
        clim_period: 气候学基准期 (start_year, end_year)
        duration: 持续时间阈值（天）
        gap: 允许中断天数
    
    Returns:
        events: MHW 事件 DataFrame
    
    Raises:
        ValueError: 如果输入数据时间范围不足
    """
```

### 7.2 R 代码风格

```r
# detect_thw.R
#
# 陆地热浪检测脚本
#
# 用法:
#   Rscript detect_thw.R <eobs_file> <output_file> <clim_start> <clim_end>

suppressPackageStartupMessages(library(heatwaveR))

# 参数解析
args <- commandArgs(trailingOnly = TRUE)
```

### 7.3 Python 绘图代码风格

```python
# 遵循 PEP 8
# 使用 matplotlib + cartopy
# 每个 figure 脚本包含一个 plot_figureN() 函数
# 地图统一使用 PlateCarree 投影
# 颜色映射使用 colorbrewer 色标

def plot_figure1(output_dir=None):
    fig = plt.figure(figsize=(16, 14))
    # 使用 GridSpec 布局
    gs = fig.add_gridspec(3, 5, ...)
    # 添加地图子图
    ax = fig.add_subplot(gs[row, col], projection=ccrs.PlateCarree())
    # 绘制 pcolormesh
    im = ax.pcolormesh(lon, lat, data, cmap='YlOrRd', ...)
    # 添加海陆、海岸线
    ax.add_feature(cfeature.LAND, ...)
    ax.add_feature(cfeature.COASTLINE, ...)
    # 保存
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
```

---

## 8. 测试与验证

### 8.1 数据完整性校验

```python
# verify_data.py
import os

required = {
    "data/OISST/oisst_v2.1_1982_2023.nc": 3e9,
    "data/E-OBS/EOBS_tg_1984_2023.nc": 2e9,
    "data/ERA5/ERA5_tmax_1984_2023_daily.nc": 8e9,
    "data/ERA5/ERA5_d2m_1984_2023_daily.nc": 8e9,
    "data/ERA5/ERA5_sp_1984_2023_daily.nc": 8e9,
    "data/OAFlux/OAFlux_evap_1991_2020_monthly.nc": 1e8,
}

for path, min_size in required.items():
    if not os.path.exists(path):
        print(f"❌ Missing: {path}")
    elif os.path.getsize(path) < min_size:
        print(f"⚠️ Too small: {path}")
    else:
        print(f"✅ {path}")
```

### 8.2 关键数值验证

| 验证项 | 期望值 | 容差 | 验证方法 |
|--------|--------|------|----------|
| 2022 年地中海 MHW 天数 | ~78 天 | ±5 天 | 对比 Table 1 |
| 2023 年 CHR 峰值 | 3.5 | ±0.2 | 对比正文 |
| 2022 年 FAR (Mediterranean) | 0.95 | ±0.02 | 对比 Table 1 |
| WBT ≥ 25.5°C 天数 (2023) | ~40 天 | ±5 天 | 对比正文 |
| 共现概率 (地中海) | >0.8 | - | 对比图 1m |

---

## 9. 运行流程

### 9.1 环境搭建

```bash
# Python 环境
conda create -n heatwave python=3.13 -y
conda activate heatwave

pip install xarray dask numpy scipy matplotlib joblib scipy.io rpy2

# R 环境（需单独安装 R）
# 然后在 R 中运行:
# install.packages("heatwaveR")
# install.packages("ncdf4")
# install.packages("doParallel")
# install.packages("foreach")
```

### 9.2 数据下载

按照 `DATA_REQUIREMENTS.md` 下载所有数据到 `data/` 目录。

```bash
python verify_data.py
```

### 9.3 运行完整流程

```bash
# 全量运行（含归因分析，预计 2-4 周）
cd F:\2607compound
python python/run_all.py

# 跳过归因（仅测试数据流程）
python python/run_all.py --skip-attribution

# 指定并行核心数
python python/run_all.py --n-jobs 16
```

### 9.4 生成全部图表

```bash
python python/figures.py
```

---

## 10. 常见问题

### Q1: CESM1-LE 数据太大，下载不完怎么办？

A: 可以先下载 1-2 个成员测试流程。完整归因分析需要全部 40 个成员，但观测分析（图 1-2, 5-6）只需 OISST + E-OBS + ERA5。

### Q2: R 的 `heatwaveR` 检测太慢怎么办？

A: 已使用 `foreach` + `doParallel` 并行。如果仍慢，可以考虑：
- 只检测欧洲区域（裁剪空间范围）
- 降低时间分辨率（如用月度数据近似）

### Q3: Bootstrap 跑了几天没反应，是不是卡住了？

A: 正常现象。1000 次 × 40 成员 = 4 万次计算，每次需遍历数十年数据。建议：
- 先用 `--n-jobs 1` 跑 10 次测试
- 确认无误后再全量并行
- 每 100 次保存一次中间结果

### Q4: 32GB 内存不够用怎么办？

A: 
- 确保使用 `dask` 惰性加载（`chunks={'time': 365}`）
- CESM1-LE 用 `xr.open_mfdataset` + `chunks`，不要全量加载
- 关闭其他占内存的程序
- 考虑用 `swap` 虚拟内存（会变慢但能跑）
