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
- Python 负责数据 I/O、复合事件识别、WBT 计算、归因统计、全部绘图输出
- R 负责**海陆统一**的热浪检测（`heatwaveR`，通过 `subprocess` 调用 `Rscript`）
- 所有输出图表需与原文一致（图 1–6、补充图 S1、表 1）

### 1.2 技术栈

| 语言/工具 | 用途 | 版本要求 |
|-----------|------|----------|
| **Python** | 数据 I/O、复合事件识别、bootstrap 归因、绘图 | ≥ 3.10（当前 3.13 可用） |
| **R** | 海陆统一热浪检测（`heatwaveR`，经 `Rscript`） | ≥ 4.0（当前 4.6.1，heatwaveR 0.5.5） |
| **conda** | Python 环境管理（推荐） | 最新版 |

> MATLAB **不在**技术栈内——绘图已全部由 Python (matplotlib + cartopy) 承担。

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
| Python | `pandas` | 事件表与中间产物处理 |
| Python | `scipy.io` | `.mat` 导出（⬜ 已弃用，仅历史设计需要） |
| R | `heatwaveR` (v0.5.5 本机 / 论文标 v0.4.6) | 海陆统一热浪检测 |
| R | `ncdf4` | NetCDF 读取 |
| R | `doParallel` + `foreach` | 逐格点检测并行 |
| — | `marineHeatWaves` (v0.15.0) | ⬜ 仅单格点核验用（DEPRECATED，见 §3.3） |

### 1.4 硬件要求

| 组件 | 最低配置 | 推荐配置 | 说明 |
|------|----------|----------|------|
| **内存** | 32 GB | 64 GB | CESM1-LE 需分块加载 |
| **CPU** | 8 核 | 16 核+ | bootstrap 并行受益 |
| **存储** | 500 GB 空闲 | 1 TB+ SSD | 原始数据 + 中间产物 |
| **显卡** | 任意 | 任意 | 本项目基本闲置，无关紧要 |

---

## 2. 项目目录结构

> 标注约定：`✅` 已就位/已实现；`⬜` 规划中（Phase 5/6 尚未开始）。
> 与 `python/config.py` 的真实路径常量保持一致；数据盘通过 Junction 访问。

```
D:\2607compound\                 # 工作区根目录
├── AGENTS.md                    # 项目速览（进度、可运行文件、约束）
├── TECHNICAL_SPEC.md            # 本文档（技术规范）
├── TECHNICAL_SPEC_PHASE_A/B/C.md
├── DATA_REQUIREMENTS.md         # 数据下载要求
├── docs/                        # 论文 PDF、补充材料、复现方案
│
├── data/                        # NTFS Junction → E:\2607compound\data
│   ├── OISST/
│   │   ├── oisst_v2.1_1982_2023.nc        ✅ 全球合并件（720×1440，15340 天）
│   │   ├── oisst_v2.1_eur_1983_2023.nc    ✅ 欧洲裁剪件
│   │   └── temp_raw/                       ✅ NOAA 按年原始文件
│   ├── E-OBS/
│   │   ├── EOBS_tg_1983_2023.nc           ✅ 合并件（201×464，14975 天）
│   │   └── tg_ens_mean_0.25deg_reg_*.nc   ✅ 3 段原始（v33.0e ×2 + v29.0e）
│   ├── ERA5/
│   │   ├── d2m_global_daily/              ✅ 按月 × 573（0.25°）
│   │   ├── sp/                            ✅ 按年 × 46（**1.0°**，待 0.25° 欧洲框替换）
│   │   ├── tmax_eur_daily/                ⬜ 按月（0.25°，仅 1984-01 就位）
│   │   └── sp_eur_daily/                  ⬜ 0.25° 欧洲框（数据集 3b+）
│   ├── OAFlux/
│   │   └── OAFlux_evap_1991_2020_monthly.nc  ⬜ 1° 月度
│   └── CESM1-LE/
│       ├── raw/                           🔶 全时段原始（b.e11.B20TRC5CNBDRD / BRCP85C5CNBDRD
│       │                                     的 pop.h.nday1.SST；B20TRLENS_RCP85.f09_g16.xghg）
│       └── proc/                          🔶 裁剪到 2000–2021 欧洲框（TREFHT_all_*+ xghg 段）
│
├── python/                       # 全部处理 + 绘图代码
│   ├── config.py                 # 路径配置、常量（唯一权威）
│   ├── load_data.py              # 数据加载与预处理
│   ├── preprocess.py             # 原始数据合并预处理
│   ├── detect_events.R           ✅ **海陆统一检测正式链路**（heatwaveR）
│   ├── detect_thw.R              ⚠️ 已归档（吞错风险，勿重跑，见 §4.1 注）
│   ├── detect_thw_wrapper.py     # R 检测入口（当前指向 detect_thw.R）
│   ├── detect_mhw.py             ⚠️ Python 侧 MHW 检测，仅单格点核验用（DEPRECATED）
│   ├── detect_thw.py             ⚠️ 纯 Python 复刻，仅交叉验证用（DEPRECATED）
│   ├── coastal_mask.py           # 沿海格点掩码与配对（KDTree）
│   ├── coastal_buffer.py         ✅ 图6 分析域：海岸向内 100 km 缓冲掩码
│   ├── compound_events.py        # 复合事件识别（逐日共超标）
│   ├── fig_jkl_mhw_envelope.py   # 图1 j–l 的 MHW 包络口径预计算
│   ├── calc_chr.py               # 复合热浪比 (CHR) 与共现概率
│   ├── calc_wbt.py               ⬜ 湿球温度 (WBT) / 比湿
│   ├── attribution.py            ⬜ FAR/PR 计算 + bootstrap
│   ├── gev_return_period.py      ⬜ GEV 重现期（图 4）
│   ├── phase6_cesm.py            ✅ Phase 6 CESM1-LE 归因管线（P0 验证版）
│   ├── fig1_compound_spatial.py  ✅ 图 1: a–i 空间分布, j–l 时间序列, m 共现概率
│   ├── fig2_chr.py               ✅ 图 2: a 复合天数, b standalone, c CHR 时序, d CHR 空间
│   ├── fig3_attribution.py       ⬜ 图 3: a–d FAR/PR 曲线
│   ├── fig4_return_period.py     ⬜ 图 4: a–c 重现期
│   ├── fig5_sst_trend.py         ⬜ 图 5: a–c SST/蒸发/湿度趋势
│   ├── fig6_wbt.py               ⬜ 图 6: a–f WBT/湿度分析
│   ├── table1_attribution.py     ⬜ 表 1: 归因结果
│   ├── supp_fig1.py              ⬜ 补充图 S1（论文 S1 = 1984–2023 年际空间分布）
│   ├── figures.py                # 一键出图（当前：图1/图2/S1）
│   ├── verify_data.py            # 数据/中间产物完整性校验
│   ├── run_all.py                # 一键运行 Phase 0–3
│   └── download_*.py             # OISST / ERA5 / OAFlux / CESM1-LE 下载工具
│
├── results/                      # 中间结果与最终输出
│   ├── intermediate/             # 中间产物（可随时删除重算）
│   │   ├── mhw_events_R_global.csv        ✅ MHW 事件（全球索引）
│   │   ├── thw_events_R.csv               ✅ THW 事件
│   │   ├── coastal_pairs.csv              ✅ 沿海配对（2039 对 / 1434 唯一海点）
│   │   ├── coastal_buffer100km_mask.nc    ✅ 图6 分析域掩码（1952 格点）
│   │   ├── dist_to_ocean_km.nc            ✅ 各陆点到最近海洋格点的距离场
│   │   ├── compound_events.nc             ✅ 复合日场
│   │   ├── standalone_days.nc             ✅ 独立陆地热浪日场
│   │   ├── annual_*.nc / CHR_annual.nc / cooccurrence_prob_annual.nc
│   │   └── bootstrap_results.pkl          ⬜ Phase 6 产物（pickle，非 .mat）
│   ├── figures/                  # 最终图表
│   │   ├── fig1_compound_spatial.pdf|png  ✅
│   │   ├── fig2_chr.pdf|png               ✅
│   │   ├── figS1_jkl_maxcell.*            ✅ 补充（j–l 格点最大值版）
│   │   ├── figS2_jkl_mhw_envelope.*       ✅ 补充（MHW 包络口径）
│   │   ├── fig3.pdf … fig6.pdf            ⬜
│   │   └── supp/figS1.pdf                 ⬜ 论文 S1 尚未复现
│   └── tables/                   # 表格数据
│       ├── fig_stats_new.json / fig_jkl_envelope.json  ✅ 数值快照
│       ├── cesm1le_download_manifest.csv               ✅
│       └── table1.csv                                  ⬜
│
└── logs/                         # 运行日志与文档备份
```

**命名真相提醒**：CESM1-LE 的 "FixGHG" 在本项目中指 **XGHG** 单强迫实验
（`b.e11.B20TRLENS_RCP85.f09_g16.xghg`），不是 `B20TRC5CNBDRD.FixGHG`——
后者是早期文档的误写。完整清单见 `DATA_REQUIREMENTS.md` 数据集 5。

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
BASE_DIR = r"D:\2607compound"   # data 为 NTFS Junction → E:\2607compound\data

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
MAX_GRID_DIST_DEG = 0.5          # 陆点→最近海点的最大配对距离（度）
COASTAL_BUFFER_KM = 100.0        # 图6 分析域：到最近海洋格点 ≤ 100 km 的陆地格点
COASTAL_BUFFER_REGION = {"lon": (5.0, 42.0), "lat": (30.0, 47.0)}  # = fig1j 区域框
                                 # 实现见 python/coastal_buffer.py（已实现，1952/4492 格点）
WBT_THRESHOLD = 25.5             # WBT 阈值 (°C)
SH_THRESHOLD = 19.0              # 比湿阈值 (g/kg)

# ──────────────────────────────────────────────
# Bootstrap 参数
# ──────────────────────────────────────────────
N_BOOTSTRAP = 1000               # 自助采样次数
CI_ALPHA = (0.05, 0.95)          # 置信区间 (5%, 95%)
N_JOBS = -1                      # 并行核心数 (-1 = 全部)
GEV_RETURN_PERIODS = (5, 10, 20, 50, 100)  # 图4 重现期（年）
GEV_CI = (0.025, 0.975)          # 图4 用 2.5–97.5% CI（图3 用 CI_ALPHA 5–95%）

# ──────────────────────────────────────────────
# CESM1-LE 成员列表与数据路径
# ──────────────────────────────────────────────
CESM_ALL_MEMBERS = [f"{i:03d}" for i in range(1, 21)]     # 001–020
CESM_FIXGHG_MEMBERS = [f"{i:03d}" for i in range(1, 21)]  # 001–020（= XGHG 实验）
CESM_RAW_DIR = os.path.join(CESM_DIR, "raw")     # RDA/GDEX 下载的全时段原始文件
CESM_PROC_DIR = os.path.join(CESM_DIR, "proc")   # 裁剪到分析时段后的文件
CESM_PERIOD = ("2000-01-01", "2021-12-31")       # 论文 L522：2000–2021
CESM_P0_MEMBERS = 3                              # P0 先跑通用前 N 个成员
CESM_EUROPE_LAT = (28.0, 74.0)                   # f09 大气网格裁剪框
CESM_EUROPE_LON = (-17.0, 47.0)

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
        filepath = os.path.join(EOBS_DIR, "EOBS_tg_1983_2023.nc")
    
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
    加载 ERA5 单个变量（多文件自动合并）。

    参数:
        varname: 变量名 ('tmax', 'd2m', 'sp')
        filepath: 文件路径（可选）

    返回:
        da: xarray DataArray

    实际数据组织（见 DATA_REQUIREMENTS.md 数据集 3）——三个变量都不在单文件里：
        d2m  : data/ERA5/d2m_global_daily/d2m_global_YYYY_MM.nc   （按月 × 573，0.25° 全球）
        sp   : data/ERA5/sp/pres.sfc.daily.era5.YYYY.nc           （按年 × 46，1.0° 全球）
        tmax : data/ERA5/tmax_eur_daily/tmax_eur_YYYY_MM.nc       （按月，0.25° 欧洲框）
    注意：sp 目前为 1.0°，论文口径为 0.25°；0.25° 欧洲框见 DATA_REQUIREMENTS 数据集 3b+。
    """
    patterns = {
        'tmax': os.path.join(ERA5_DIR, 'tmax_eur_daily', 'tmax_eur_*.nc'),
        'd2m':  os.path.join(ERA5_DIR, 'd2m_global_daily', 'd2m_global_*.nc'),
        'sp':   os.path.join(ERA5_DIR, 'sp', 'pres.sfc.daily.era5.*.nc'),
    }

    # ERA5 变量名映射（与各下载脚本写入的 netCDF 变量名一致）
    era5_name_map = {
        'tmax': 'mx2t',   # CDS 请求名 maximum_2m_temperature_since_previous_post_processing
        'd2m': 'd2m',
        'sp': 'sp',
    }

    if filepath is not None:
        ds = xr.open_dataset(filepath, chunks={'time': 365})
        var_key = era5_name_map.get(varname, varname)
        if var_key not in ds:
            var_key = next(iter(ds.data_vars))
    else:
        ds = xr.open_mfdataset(
            patterns[varname], chunks={'time': 365},
            combine='by_coords', parallel=True,
        )
        var_key = era5_name_map.get(varname, varname)
        if var_key not in ds:
            var_key = next(iter(ds.data_vars))

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
        forcing: 'ALL' 或 'XGHG'（= 论文的 FixGHG 反事实实验）
        filepath: 可选，手动指定文件路径

    Returns:
        ds: 包含 TREFHT (T2m) 和 SST 的 Dataset

    ⚠️ 实际数据组织（见 DATA_REQUIREMENTS.md 数据集 5、python/config.py）：
      - 不存在 `CESM1-LE/ALL/` 与 `CESM1-LE/FixGHG/` 目录，也不存在
        `b.e11.B20TRC5CNBDRD.{id}.cam.h1.TREFHT.185001-202312.nc` 这类文件名。
      - ALL 大气：AWS zarr → `TREFHT_all_{id}_2000-2021_europe.nc`（proc/）
      - ALL 海洋：`b.e11.B20TRC5CNBDRD.f09_g16.{id}.pop.h.nday1.SST.*.nc`
      - 反事实  ：`b.e11.B20TRLENS_RCP85.f09_g16.xghg.{id}.cam.h1.TREFHT.*.nc`
                  + `...xghg.{id}.pop.h.nday1.SST.*.nc`（两段式 1920–2005 / 2006–2080）
      - 成员 001 的历史段自 1850 起，002–020 自 1920 起；分析只取 2000–2021。
      - SST 在 POP 网格上（非高斯大气网格），与 TREFHT 不同网格，
        需按 `python/phase6_cesm.py` 的湿点映射方案处理。
    """
    if filepath is None:
        raise ValueError(
            "CESM1-LE 文件名随实验/变量/分段而变，请显式传入 filepath，"
            "或直接使用 python/phase6_cesm.py 的 prepare/pairs 阶段产物。"
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

    return ds


def load_cesm1le_dir(forcing: str = "ALL") -> xr.Dataset:
    """
    加载 proc/ 下某实验的全部成员，使用 open_mfdataset 自动合并。

    Parameters:
        forcing: 'ALL' 或 'XGHG'

    Returns:
        ds: 合并后的 Dataset，维度为 (member, time, lat, lon)

    注意：proc/ 目录中 ALL 与 XGHG 的文件混放，需按文件名模式区分（见下方 pattern）。
    """
    if forcing == "ALL":
        pattern = os.path.join(CESM_PROC_DIR, "TREFHT_all_*_2000-2021_europe.nc")
    else:
        pattern = os.path.join(CESM_PROC_DIR, "*xghg.*")

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

> ⚠️ **状态：DEPRECATED（仅单格点核验用）**。论文 Code availability 同时列出
> `heatwaveR` (v0.4.6, R) 与 `marineHeatWaves` (v0.15.0, Python)；本项目自 2025-09-18 起
> **海陆检测统一走 R `heatwaveR`**（`python/detect_events.R`），因其语义经源码核验与
> `marineHeatWaves` 一致（见 `results/方法与证据.md §4`）。
> 本节保留原 Python 实现仅作单格点交叉验证与历史对照，**不是正式链路**。

**文件路径**: `python/detect_mhw.py`  
**功能**: 调用 `marineHeatWaves` 检测海洋热浪（仅核验用）。

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

### 3.4 `detect_events.R` — 海陆统一热浪检测（R 脚本，**正式链路**）

**文件路径**: `python/detect_events.R`
**功能**: 用 `heatwaveR` 对海（OISST SST）陆（E-OBS T2m）做**同一份代码**的逐格点检测。
**输出**: 事件 CSV（MHW → `mhw_events_R_global.csv`；THW → `thw_events_R.csv`）

**关键参数（必须与论文一致）**:

| 参数 | 值 | 说明 |
|------|-----|------|
| `pctile` | 90 | 90 分位阈值 |
| `windowHalfWidth` | 5 | 11 天滑动窗口（heatwaveR 默认） |
| `smoothPercentile` | **FALSE** | ⚠️ **偏离两包默认（TRUE / 31 天窗）**，见下方注 |
| `minDuration` | 5 | 超标日游程 ≥ 5 天（不含间隙） |
| `maxGap` | 2 | 桥接 ≤ 2 天间隙 |
| 气候期 | 1983-01-01 – 2012-12-31 | 论文口径 |

> **⚠️ 已知偏离（必须在复现报告中保留）**：论文使用的是两包**默认**参数，其中
> `ts2clm(smoothPercentile = TRUE, smoothPercentileWidth = 31)`。本项目为隔离
> "11 天窗口 vs 单日分位"变量而显式设为 `FALSE`。抽样实验（90 个沿海对，
> `（已删；结论见 results/方法与证据.md §4）`）显示影响 < 5%（地中海 2022 复合天数 16.9→15.8、
> 2023 32.5→32.9），故保留 FALSE。若需严格对齐包默认可开启重跑（陆地约 30 min）。
> 详见 `results/复现报告.md` D2 / §5.1#4。

**CLI（实际签名，`python/detect_events.R`）**:

```bash
Rscript python/detect_events.R <nc_file> <varname> <output_csv> \
        <clim_start> <clim_end> [domains_file|-] [min_dur] [max_gap] [n_workers] [work_dir]
# 例（海洋）:
Rscript python/detect_events.R data/OISST/oisst_v2.1_eur_1983_2023.nc sst \
        results/intermediate/mhw_events_R.csv 1983 2012
# 例（陆地，域限配对点）:
Rscript python/detect_events.R data/E-OBS/EOBS_tg_1983_2023.nc T2m \
        results/intermediate/thw_events_R_v2.csv 1983 2012 \
        results/intermediate/domains_ocean_pairs.csv 5 2 12
```

**Python 调用方式**（实际实现：`python/detect_thw_wrapper.py`，指向 `detect_thw.R`；

```python
import subprocess, os
from config import RSCRIPT_PATH, DETECT_THW_R_SCRIPT, HW_MIN_DURATION, HW_MAX_GAP, R_WORKERS

def detect_thw(eobs_filepath, output_csv, clim_period, work_dir=None):
    """调用 R 脚本检测陆地热浪，返回事件 DataFrame（CSV 落地）。"""
    if work_dir is None:
        work_dir = output_csv + ".work"
    result = subprocess.run(
        [RSCRIPT_PATH, DETECT_THW_R_SCRIPT,
         eobs_filepath, output_csv,
         str(clim_period[0]), str(clim_period[1]),
         str(HW_MIN_DURATION), str(HW_MAX_GAP), str(R_WORKERS),
         work_dir, eobs_filepath],
        capture_output=True, text=True, check=True,
    )
    print(result.stdout)
    if result.stderr:
        print("R stderr:", result.stderr)
    return pd.read_csv(output_csv)   # 列名 date_start/date_end → event_start/event_end
```

**§4.1 的 `detect_thw.R` 为历史存档**：该脚本存在 `return`-in-`tryCatch` 静默吞错
的潜在 bug，**已弃用、勿重跑**（其产物 `thw_events_R.csv` 已通过逐行回归与
`detect_events.R` 的 `thw_events_R_v2.csv` 比对一致，故缓存可继续使用）。
`python/run_all.py` 的 THW 环节当前仍指向 `detect_thw_wrapper` → `detect_thw.R`：
**缓存缺失时会走到存档脚本**，正式重检请直接调用 `detect_events.R`。

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

from config import MAX_GRID_DIST_DEG, COASTAL_PAIRS_CSV

# ⚠️ 实际签名与返回类型（python/coastal_mask.py）：
#   find_coastal_grid_pairs(land_mask, ocean_mask, *, max_dist_deg=MAX_GRID_DIST_DEG,
#                           save_path=COASTAL_PAIRS_CSV) -> pd.DataFrame
#   配对走 KDTree 最近邻，距离上限 MAX_GRID_DIST_DEG = 0.5°，返回列：
#   [land_lat_idx, land_lon_idx, ocean_lat_idx, ocean_lon_idx,
#    land_lat, land_lon, ocean_lat, ocean_lon, dist_deg]
#   实测产出 2039 对 / 1434 个唯一海洋格点。
#   下方为等价教学版（4-邻域等距，故"取首个相邻海点"与"最近邻"一致）。


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
**功能**: 识别复合海洋-陆地热浪。

**复合日定义（2025-09-23 方案 B 定稿）**：
- 图1a-i / 图1m / 图2 全系：逐日共超标（论文 L477 simultaneously exceed），由 compound_events.py 实现
- 图1j-l 时序曲线：MHW 包络（论文 L520 fully encompasses），由 fig_jkl_mhw_envelope.py 预计算，fig1_compound_spatial.py 从 fig_jkl_envelope.json 读取
- 论文引言/结果/模型 Methods 均用 encompassment（L30/L77/L104/L520），仅 L477 用 exceedance；两定义产出不同，本复现分别在不同面板使用，与论文实际做法一致

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
    湿球温度的精确解：对 psychrometric 方程做牛顿迭代。

    物理方程（T_w 为未知量，能量平衡 + 饱和混合比）：
        e_w_sat(T_w) - e(Tdew) - gamma * p * (T - T_w) = 0
    其中
        e_w_sat(x) = 6.112 * exp(17.67 * x / (x + 243.5))   [hPa] x 温度下的饱和水汽压
        e(Tdew)    = e_w_sat(Tdew)                          [hPa] 实际水汽压（由露点定）
        gamma      = 0.00066 * (1 + 0.00115 * Tdew)         [1/°C] 湿度计常数
        p          = sp / 100                                [hPa]

    ⚠️ 修正记录：本节原实现存在两处缺陷——
      ① `es_current` 计算后从未使用；
      ② 迭代式 `WBT_new = T - (T - Tdew) / (1 + gamma * p / 10)` **不依赖** `WBT_guess`，
         因此第一次循环即满足 tol 并 break，所谓"迭代"实际只等于一次解析近似。
      现改为对 f(T_w) = e_w_sat(T_w) - e(Tdew) - gamma * p * (T - T_w) 求根的
      牛顿迭代，f'(T_w) 用 de_sat/dT 的解析式。

    Parameters:
        tmax: 日最高气温 (°C)
        d2m: 露点温度 (°C)
        sp: 地表气压 (Pa)
        max_iter: 最大迭代次数
        tol: 收敛容差 (°C)

    Returns:
        WBT: 湿球温度 (°C)
    """
    T = np.asarray(tmax.values, dtype=np.float64)
    Td = np.asarray(d2m.values, dtype=np.float64)
    p = np.asarray(sp.values, dtype=np.float64) / 100.0        # Pa -> hPa

    def es(t):
        return 6.112 * np.exp(17.67 * t / (t + 243.5))

    def des_dt(t):
        return es(t) * 17.67 * 243.5 / (t + 243.5) ** 2

    e = es(Td)                                   # 实际水汽压（由露点定）
    gamma = 0.00066 * (1.0 + 0.00115 * Td)       # 湿度计常数 [1/°C]

    # 初值：Stull (2011) 近似（注意 Stull 用的是 RH，此处用等价形式）
    RH = np.clip(e / es(T) * 100.0, 0.0, 100.0)
    Tw = (T * np.arctan(0.151977 * np.sqrt(RH + 8.313659))
          + np.arctan(T + RH) - np.arctan(RH - 1.676331)
          + 0.00391838 * RH ** 1.5 * np.arctan(0.023101 * RH)
          - 4.686035)
    Tw = np.where(np.isfinite(Tw), Tw, Td)       # 兜底

    for _ in range(max_iter):
        f = es(Tw) - e - gamma * p * (T - Tw)
        df = des_dt(Tw) + gamma * p
        step = np.where(np.abs(df) > 1e-12, f / df, 0.0)
        Tw_new = Tw - step
        if np.nanmax(np.abs(Tw_new - Tw)) < tol:
            Tw = Tw_new
            break
        Tw = Tw_new

    WBT_da = xr.DataArray(
        Tw,
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
    
    FAR = 1 - P_counterfactual / P_factual   （= 1 − P_FixGHG / P_ALL，论文 Eq.2）
    
    表示: 事件在没有 GHG 强迫下不会发生的概率。
    
    Parameters:
        p_factual: 全强迫下事件发生概率
        p_counterfactual: 反事实 (FixGHG) 下事件发生概率
    
    Returns:
        FAR: 0 到 1 之间的值
    """
    if p_counterfactual <= 0:
        return 1.0
    return 1.0 - (p_counterfactual / p_factual)


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
    exposure_annual: np.ndarray,
    threshold: float
) -> float:
    """
    计算给定阈值下事件发生的概率（论文口径，Methods L522 起）。

    论文：把每个成员每年的"区域聚合暴露时间"（地中海&黑海 / 欧洲全岸
    的复合天数）作为样本；ALL 与 FixGHG 各 440 个模型年（20 成员 ×
    22 年，2000–2021）。概率 = 暴露 ≥ 阈值的模型年占比。
    注意：统计样本是"模型-年"，不是"格点-年"。

    Parameters:
        exposure_annual: 区域年暴露时间 (member, year) 或展平数组；
                         上游由复合日数经区域聚合得到
        threshold: 复合热浪暴露天数阈值（图3 x 轴 / Table 1 阈值）

    Returns:
        prob: 概率值 (0-1)
    """
    data = np.asarray(exposure_annual).ravel()
    if data.size == 0:
        return 0.0
    return float((data >= threshold).sum()) / float(data.size)


def single_bootstrap_iteration(
    all_exposure: np.ndarray,
    fixghg_exposure: np.ndarray,
    threshold: float
) -> Tuple[float, float]:
    """
    单次 bootstrap 迭代：有放回抽样模型年，计算 FAR 和 PR。

    Parameters:
        all_exposure: ALL 区域年暴露池化样本（20 成员 × 22 年 = 440）
        fixghg_exposure: FixGHG 区域年暴露池化样本（440）
        threshold: 复合热浪暴露天数阈值

    Returns:
        far_val, pr_val
    """
    # 有放回抽样（论文 Methods：从原始模型年样本中重采样）
    all_sample = np.random.choice(all_exposure, size=all_exposure.size, replace=True)
    fixghg_sample = np.random.choice(fixghg_exposure, size=fixghg_exposure.size, replace=True)

    # 计算概率
    p_all = calc_probability(all_sample, threshold)
    p_fixghg = calc_probability(fixghg_sample, threshold)

    # 计算 FAR 和 PR（论文 Eq.2/3）
    far = calc_FAR(p_all, p_fixghg)
    pr = calc_PR(p_all, p_fixghg)

    return far, pr


def bootstrap_FAR_PRC(
    all_data: np.ndarray,
    fixghg_data: np.ndarray,
    thresholds: np.ndarray,
    n_bootstrap: int = N_BOOTSTRAP,
    n_jobs: int = N_JOBS
) -> Dict[str, np.ndarray]:
    """
    并行 bootstrap 计算 FAR 和 PR 曲线。

    开销说明：样本是**池化后的 440 个模型年标量**（非逐日格点场），
    1000 次 × 若干阈值在单机上为秒级到分钟级。
    本项目真正的计算瓶颈在**前一步**——40 个 CESM 成员的逐格点热浪检测。
    
    Parameters:
        all_data: ALL 区域年暴露时间 (member, year)，池化后 440 模型年
                  （上游已完成复合检测与区域聚合，见 calc_probability）
        fixghg_data: FixGHG 区域年暴露时间（同上）
        thresholds: 复合热浪暴露天数阈值数组（图3 x 轴，如 10, 15, …, 95 天）
        n_bootstrap: 自助采样次数
        n_jobs: 并行核心数
    
    Returns:
        results: 包含 FAR/PR 均值、置信区间的字典
    """
    # 池化为模型年样本（member × year → 440 个模型年）
    all_exposure = np.asarray(all_data).ravel()
    fixghg_exposure = np.asarray(fixghg_data).ravel()
    
    n_thresh = len(thresholds)
    
    # 存储所有 bootstrap 结果
    far_array = np.zeros((n_bootstrap, n_thresh))
    pr_array = np.zeros((n_bootstrap, n_thresh))
    
    # 单次 bootstrap 的函数（闭包捕获 threshold 索引）
    def run_single(b: int):
        results_thresh = []
        for ti, thresh in enumerate(thresholds):
            far_val, pr_val = single_bootstrap_iteration(
                all_exposure, fixghg_exposure, thresh
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

### 3.9b `gev_return_period.py` — GEV 重现期（图 4）

**文件路径**: `python/gev_return_period.py`
**功能**: 按论文 Methods "Return level and period estimation using GEV" 计算重现期变化（图 4a–c）。

**论文口径（必须遵循）**:
- 输入：ALL 与 FixGHG 的**区域年暴露时间**（地中海&黑海）；图 4 覆盖三类事件：
  a 沿海海洋热浪天数、b 沿海陆地热浪天数、c 复合 MHW-THW 天数。
- 第一步：对 FixGHG 年值去缺测后做 **1000 次有放回 bootstrap**，每次用 **MLE 拟合 GEV**，
  经逆 CDF 求 5/10/20/50/100 年重现水平；报告**中位数 + 2.5–97.5% CI**。
- 第二步：把 FixGHG 的各重现水平映射到 ALL 的**等效重现期**；对 ALL 重复 bootstrap 估计其不确定性。
- 置信区间与图 3 不同：图 3 FAR/PR 用 **5–95%**（`CI_ALPHA`），图 4 用 **2.5–97.5%**（`GEV_CI`）。

```python
from scipy.stats import genextreme

def fit_return_levels(annual_values: np.ndarray,
                      n_bootstrap: int = N_BOOTSTRAP,
                      seed: int = 42) -> dict:
    """FixGHG 年值 → GEV 重现水平分布（1000 bootstrap, MLE）。

    Returns: {rp: {'median', 'ci_lower', 'ci_upper'}}，rp ∈ GEV_RETURN_PERIODS
    """
    rng = np.random.default_rng(seed)
    vals = annual_values[np.isfinite(annual_values)]      # 先去缺测
    levels = {rp: [] for rp in GEV_RETURN_PERIODS}
    for _ in range(n_bootstrap):
        sample = rng.choice(vals, size=vals.size, replace=True)
        c, loc, scale = genextreme.fit(sample)            # MLE
        for rp in GEV_RETURN_PERIODS:
            levels[rp].append(genextreme.ppf(1 - 1 / rp, c, loc=loc, scale=scale))
    out = {}
    for rp, arr in levels.items():
        arr = np.asarray(arr)
        out[rp] = {'median': float(np.median(arr)),
                   'ci_lower': float(np.quantile(arr, GEV_CI[0])),
                   'ci_upper': float(np.quantile(arr, GEV_CI[1]))}
    return out


def map_return_period(all_annual: np.ndarray,
                      return_levels: dict,
                      n_bootstrap: int = N_BOOTSTRAP,
                      seed: int = 43) -> dict:
    """FixGHG 重现水平 → ALL 等效重现期（对 ALL 重复 bootstrap 估计不确定性）。"""
    rng = np.random.default_rng(seed)
    vals = all_annual[np.isfinite(all_annual)]
    rps = {rp: [] for rp in return_levels}
    for _ in range(n_bootstrap):
        sample = rng.choice(vals, size=vals.size, replace=True)
        c, loc, scale = genextreme.fit(sample)
        for rp, st in return_levels.items():
            p = genextreme.cdf(st['median'], c, loc=loc, scale=scale)
            rps[rp].append(1.0 / (1.0 - p) if p < 1 else np.inf)
    return {rp: {'median': float(np.median(a)),
                 'ci_lower': float(np.quantile(a, GEV_CI[0])),
                 'ci_upper': float(np.quantile(a, GEV_CI[1]))}
            for rp, a in rps.items()}
```

> 实现注意：`genextreme.fit` 默认 MLE；若极端分位不稳定，可锁定 location/scale
> 或改用 L 矩估计并记录敏感性。图 4 每个面板对 marine / terrestrial / compound
> 三类年暴露序列各执行一遍上述流程。

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
**功能**: 统一入口，生成图 1、图 2、补充图 S1（图 S2 由 fig_jkl_mhw_envelope.py 出；图 3–6 尚未实现）。

---

### 3.13 `run_all.py` — 一键运行入口

> 编号说明：本节原误编为 §3.11（与 `fig2_chr.py` 重号），2026-09-23 复核时改为 §3.13，
> 使 §3.10 → §3.11 → §3.12 → §3.13 按文档顺序递增。

**文件路径**: `python/run_all.py`  
**功能**: 串联 **Phase 0–3**（数据预处理 → 热浪检测 → 沿海配对与复合事件 → 年度指标/CHR/共现概率）。  
**当前实际步骤数**: 4 个 Phase（不是 6 步）；**不含归因与湿热环节**。

> ⚠️ **规范与实现的差异说明**（2026-09-23 复核）：
> 本节此前按"6 步含归因"的旧设计书写，与实现不符，已按实际代码重写要点。
> - Phase 5（WBT/SH，图 5–6）与 Phase 6（CESM 归因，图 3–4）**尚未接入 run_all.py**；
>   Phase 6 目前是独立入口 `python/phase6_cesm.py`（prepare → pairs → detect → compound → attrib）。
> - 陆地检测经 `detect_thw_wrapper` → `python/detect_thw.R`（**已归档脚本**）；
>   正式链路是 `python/detect_events.R`，缓存缺失时需注意此差异。
> - 缓存命中时各 Phase 直接读 `results/intermediate/` 下已有产物（~1 min）；
>   全量重检陆地约 22 min。

```python
#!/usr/bin/env python
"""
run_all.py — 一键运行入口（Phase 0-3）

Phase 0: 数据预处理（合并 OISST / E-OBS）
Phase 1: 热浪检测（MHW + THW）
Phase 2: 沿海配对 + 复合事件识别
Phase 3: CHR / 共现概率计算
"""
import os, sys, time
import numpy as np, pandas as pd, xarray as xr

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    OISST_MERGED_FILE, EOBS_MERGED_FILE,
    SST_CLIM_FILE, T2M_CLIM_FILE,
    MHW_EVENTS_CSV, THW_EVENTS_CSV,
    COASTAL_PAIRS_CSV,
    COMPOUND_NC, STANDALONE_NC,
    ANNUAL_COMPOUND_NC, ANNUAL_STANDALONE_NC, ANNUAL_THW_NC,
    CHR_ANNUAL_NC, COOCCURRENCE_PROB_NC,
    CLIM_PERIOD,
    INTERMEDIATE_DIR, FIGURES_DIR, TABLES_DIR, LOGS_DIR,
)

import preprocess, load_data, detect_mhw, detect_thw_wrapper
import coastal_mask, compound_events, calc_chr


def phase0_preprocess():
    """合并 OISST / E-OBS（已存在则跳过）。对应 preprocess.merge_oisst / merge_eobs。"""
    ...


def phase1_detection():
    """沿海配对 + MHW/THW 检测。缓存命中（COASTAL_PAIRS_CSV / MHW_EVENTS_CSV /
    THW_EVENTS_CSV 已存在）则直接读 CSV，否则调用检测。

    ⚠️ THW 走 detect_thw_wrapper.detect_thw() → python/detect_thw.R（归档脚本）。
    正式重检请改用 python/detect_events.R。
    """
    ...


def phase2_compound(data, mhw_df, thw_df, pairs_df):
    """identify_compound_events（逐日共超标）→ compound_events.nc / standalone_days.nc"""
    ...


def phase3_metrics(compound_daily, standalone_daily):
    """年度天数 → CHR / 共现概率 → annual_*.nc / CHR_annual.nc / cooccurrence_prob_annual.nc

    关键口径：陆地热浪总天数 = 复合日 ∪ standalone 日
        all_thw_daily = xr.where(compound_daily > 0, 1, standalone_daily)
    （**不是** mhw_daily —— 后者是海洋热浪日场）
    """
    ...


def main():
    phase0_preprocess()
    data, mhw_df, thw_df, pairs_df = phase1_detection()
    compound_daily, standalone_daily, pairs_df = phase2_compound(data, mhw_df, thw_df, pairs_df)
    results = phase3_metrics(compound_daily, standalone_daily)


if __name__ == "__main__":
    main()
```

**Phase 5 / Phase 6 尚未接入本入口**，各自的入口与产物为：

| 阶段 | 入口 | 主要产物 | 状态 |
|---|---|---|---|
| Phase 5 湿热应力（图5–6） | ⬜ `python/calc_wbt.py` + `fig5_sst_trend.py` + `fig6_wbt.py` | `wbt_daily.nc`、`sh_daily.nc`、`sst_trend.nc` | 未实现 |
| Phase 6 归因（图3–4） | ✅ `python/phase6_cesm.py`（prepare/pairs/detect/compound/attrib） | `bootstrap_results.pkl`、`fig7_p0_validation.png`（P0 版） | P0 验证完成，全量未跑 |

Phase 6 的 bootstrap 调用形态与 §3.9 一致（**只传池化后的区域年暴露序列，不传成员列表**）：

```python
# 每类事件 / 每个区域各取一条 (member, year) 的区域年暴露序列，先池化为 440 模型年
exposure_all = region_annual_exposure(cesm_all)     # shape (440,)
exposure_fix = region_annual_exposure(cesm_fixghg)  # shape (440,)

thresholds = np.arange(10, 100, 5)                  # 10, 15, …, 95 天
attr = bootstrap_FAR_PRC(exposure_all, exposure_fix, thresholds,
                         n_bootstrap=N_BOOTSTRAP, n_jobs=N_JOBS)
```

---

## 4. R 代码详细规范

### 4.1 `detect_thw.R` — 陆地热浪检测（**历史存档，勿重跑**）

> ⚠️ **状态：已归档**。本脚本存在 `return`-in-`tryCatch` 的静默吞错风险
> （见下方 `error = function(e) return(NULL)`），**正式链路是 `python/detect_events.R`**（§3.4）。
> 保留本节仅作历史对照；其产物 `thw_events_R.csv` 已与 `detect_events.R` 的
> `thw_events_R_v2.csv` 逐行回归比对一致，缓存可继续使用。
> 下方代码中的 `saveRDS` / `.rds` 写法为原始设计，实际产物是 **CSV**。

**文件路径**: `python/detect_thw.R`  
**功能**: 使用 `heatwaveR` 逐格点检测陆地热浪。

```r
#!/usr/bin/env Rscript
# detect_thw.R — 陆地热浪检测 (heatwaveR)  【已归档】
#
# 用法:
#   Rscript detect_thw.R <eobs_file> <output_csv> <clim_start> <clim_end>
#
# 示例:
#   Rscript detect_thw.R data/E-OBS/EOBS_tg_1983_2023.nc results/intermediate/thw_events_R.csv 1983 2012

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
**面板（严格按论文 Fig. 1 caption）**:

| 面板 | 内容 |
|---|---|
| a–i | 9 个**论文指定年份**的复合热浪天数空间分布：**2003, 2006, 2010, 2012, 2018, 2019, 2020, 2022, 2023** |
| j–l | 复合热浪天数**时间序列**（1983–2023）× **三个区域**：地中海（含黑海）/ 波罗的海沿岸 / 全欧洲海岸 |
| m | 共现概率（复合天数 ÷ 陆地热浪天数）空间分布，**2003–2023 平均** |

**输出**: `results/figures/fig1_compound_spatial.pdf`
**口径提醒**: j–l 用 **MHW 包络**（论文 L520 "fully encompasses"），a–i/m 用 **逐日共超标**（L477）；
详见 §3.6 与 `results/复现报告.md` 方案 B。

### 5.3 `fig2_chr.py` — 图 2

**文件**: `python/fig2_chr.py`
**面板（严格按论文 Fig. 2 caption）**:

| 面板 | 内容 |
|---|---|
| a | 复合 MHW–THW 天数**空间分布**（2003–2023 平均）—— **不是**区域柱状图 |
| b | stand-alone 陆地热浪天数**空间分布**（2003–2023 平均） |
| c | CHR 时间序列（1983–2023），含 y=1 参考线 |
| d | CHR **空间分布**（2003–2023 平均） |

**输出**: `results/figures/fig2_chr.pdf`
**统计口径**: 图2 a/b 为区间**均值场**；图2 d 为区间**总和之比**（论文 caption "ratio ... over the
period 2003–2023" 的字面读法，见 `复现报告.md` D4）；图2 c 为逐年 cos 加权总和之比。

### 5.4 `figures.py` — 一键生成

**文件**: `python/figures.py`
**功能（当前实现）**: 统一入口，调用 **图 1、图 2、补充图 S1** 的生成函数。
补充图 S2 由独立脚本 `python/fig_jkl_mhw_envelope.py` 生成；**图 3–6 与表 1 尚未实现**。

```python
from fig1_compound_spatial import plot_figure1
from fig2_chr import plot_figure2

def generate_all_figures():
    plot_figure1()
    plot_figure2()
```

> 规划中的完整形态（Phase 5/7 完成后）才包含 fig3–fig6、supp_fig1、table1。

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

**实际脚本**: `python/verify_data.py`（**不是**硬编码路径清单——它全部走 `config.py` 常量），
检查的是**预处理产物与中间产物**，不是原始下载数据（原始数据完整性由各下载脚本内置校验保障）。

```python
# python/verify_data.py（要点）
from config import (
    OISST_MERGED_FILE, EOBS_MERGED_FILE,      # 合并件
    SST_CLIM_FILE, T2M_CLIM_FILE,             # 气候态
    MHW_EVENTS_CSV, THW_EVENTS_CSV,           # 检测结果
    COASTAL_PAIRS_CSV,                        # 沿海配对
    COMPOUND_NC, STANDALONE_NC,               # 复合 / 独立日场
)

def verify_all():
    check_nc_file(OISST_MERGED_FILE, "OISST merged",
                  expected_dims={'time': 15340, 'lat': 720, 'lon': 1440})
    check_nc_file(EOBS_MERGED_FILE, "E-OBS merged",
                  expected_dims={'time': 14975, 'lat': 201, 'lon': 464})
    check_nc_file(SST_CLIM_FILE, "SST climatology", min_size_mb=10)
    check_nc_file(T2M_CLIM_FILE, "T2m climatology", min_size_mb=1)
    check_file(MHW_EVENTS_CSV, "MHW events CSV", min_size_mb=0.1)
    check_file(THW_EVENTS_CSV, "THW events CSV", min_size_mb=0.1)
    check_file(COASTAL_PAIRS_CSV, "Coastal pairs CSV", min_size_mb=0.1)
    check_nc_file(COMPOUND_NC, "Compound events NC", min_size_mb=1)
    check_nc_file(STANDALONE_NC, "Standalone days NC", min_size_mb=1)
```

**期望维度依据**（勿再写旧值）：

| 文件 | time | lat × lon | 说明 |
|---|---|---|---|
| `oisst_v2.1_1982_2023.nc` | 15340 | 720 × 1440 | 1982-01-01 – 2023-12-31 |
| `EOBS_tg_1983_2023.nc` | **14975** | 201 × 464 | 1983-01-01 – 2023-12-31（**原写 14245 是 1984 起口径，已废**） |
| `sst_climatology_1983_2012.nc` | 365 | 720 × 1440 | 逐 dayofyear 90 分位 |
| `t2m_climatology_1983_2012.nc` | 366 | 201 × 464 | 逐 dayofyear 90 分位 |

### 8.2 关键数值验证

| 验证项 | 期望值 | 容差 | 验证方法 |
|--------|--------|------|----------|
| 2022 年地中海复合暴露天数 | ~78 天 | ±5 天 | 对比 Table 1 |
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

pip install xarray dask numpy scipy matplotlib joblib pandas cdsapi

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
# Phase 0-3：预处理 → 检测 → 复合 → 年度指标（缓存命中 ~1 min；全量重检陆地 ~22 min）
cd D:\2607compound
python python\run_all.py

# 出图（当前：图1 / 图2 / 补充图 S1）
python python\figures.py
python python\fig_jkl_mhw_envelope.py     # 补充图 S2

# Phase 6 归因（独立入口，P0 验证版）
python python\phase6_cesm.py prepare --members 3
python python\phase6_cesm.py pairs
python python\phase6_cesm.py detect
python python\phase6_cesm.py compound
python python\phase6_cesm.py attrib
```

> ⚠️ `run_all.py` **没有** `--skip-attribution` / `--n-jobs` 等参数——它是 Phase 0–3 的
> 四段式脚本，归因与湿热分析不由它调度（见 §3.13）。

### 9.4 生成全部图表

```bash
python python\figures.py
```

---

## 10. 常见问题

### Q1: CESM1-LE 数据太大，下载不完怎么办？

A: 可以先下载 1–3 个成员测试流程（`run_p0_download.bat`）。完整归因分析需要
**20 个 ALL 成员 + 20 个 XGHG 成员**；观测分析（图 1–2、5–6）只需 OISST + E-OBS + ERA5。

### Q2: R 的 `heatwaveR` 检测太慢怎么办？

A: 已使用 `foreach` + `doParallel` 并行（`R_WORKERS`，本机 12 worker）。如果仍慢，可以考虑：
- 只检测欧洲区域（裁剪空间范围）
- 只检测近岸配对点（MHW 侧实际只检测 1434 个唯一海点）

### Q3: Bootstrap 跑了很久没反应，是不是卡住了？

A: **不是**。按论文口径（§3.9），bootstrap 的样本是**区域年暴露时间池化后的 440 个模型年**
（不是 40 个成员 × 数十年逐日数据），因此 1000 次 × 若干阈值在单机上只需秒级到分钟级。
真正的耗时在**前一步**：40 个 CESM 成员的逐格点热浪检测。建议：
- 先用 `--members 3` 跑通 P0 管线，再放全量
- 检测阶段的逐成员产物落盘，支持断点续跑

### Q4: 32GB 内存不够用怎么办？

A: 
- 确保使用 `dask` 惰性加载（`chunks={'time': 365}`）
- CESM1-LE 用 `xr.open_mfdataset` + `chunks`，不要全量加载
- 关闭其他占内存的程序
- 考虑用 `swap` 虚拟内存（会变慢但能跑）
