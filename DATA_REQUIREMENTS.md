# 数据下载要求

> **最后更新**: 2026-09-23（本次：新增 3b+ 0.25° sp 欧洲框下载任务、OISST v2.1/v2.0 版本口径说明；
> 体量按第二轮复核实测值刷新；数据状态与 `config.py` 对齐）

## 当前数据状态总览

> 下表体量为 **2026-09-23 实测值**（`Get-ChildItem | Measure-Object Length -Sum`），
> 与早期按下载清单估算的值可能略有出入。

| 数据集 | 实际文件/目录 | 时间范围 | 空间范围 | 分辨率 | 实际大小 | 状态 |
|--------|-------------|----------|----------|--------|----------|------|
| **OISST v2.1 全球** | `data/OISST/oisst_v2.1_1982_2023.nc` | 1982–2023 | 全球 | 0.25° 日度 | 23.1 GB（15340 天 × 720 × 1440） | ✅ 就位 |
| **OISST v2.1 欧洲裁剪** | `data/OISST/oisst_v2.1_eur_1983_2023.nc` | 1983–2023 | 欧洲 | 0.25° 日度 | 1.1 GB | ✅ 就位 |
| **E-OBS tg 合并** | `data/E-OBS/EOBS_tg_1983_2023.nc` | 1983–2023 | 欧洲 | 0.25° 日度 | 0.5 GB（14975 天 × 201 × 464） | ✅ 就位 |
| **E-OBS tg 分段原始** | `data/E-OBS/tg_ens_mean_0.25deg_reg_*.nc` × 3 | 1980–2023 | 欧洲 | 0.25° 日度 | 0.46 GB | ✅ 就位 |
| **ERA5 d2m** | `data/ERA5/d2m_global_daily/d2m_global_YYYY_MM.nc` × 573 | 1979–2026 | 全球 | 0.25° 日度 | 40.6 GB | ✅ 就位 |
| **ERA5 sp** | `data/ERA5/sp/pres.sfc.daily.era5.YYYY.nc` × 46 | 1979–2024 | 全球 | **1.0°** 日度 | 4.1 GB | ✅ 就位（⬜ 0.25° 欧洲框见 3b+） |
| **ERA5 tmax** | `data/ERA5/tmax_eur_daily/tmax_eur_YYYY_MM.nc` × 1 | 1984–2023 | 欧洲 [66N,10W,30N,40E] | 0.25° 日度 | ~0（仅 1984-01） | ⬜ 待下载 |
| **OAFlux evap** | `data/OAFlux/`（空） | 1991–2020 | 全球 | 1° 月度 | — | ⬜ 待下载 |
| **CESM1-LE raw** | `data/CESM1-LE/raw/` × 18 文件 | 1850/1920–2080 | 全球 | ~1°（f09_g16） | 109.3 GB | 🔶 成员 001–003 部分 |
| **CESM1-LE proc** | `data/CESM1-LE/proc/` × 21 文件 | 2000–2021 | 欧洲裁剪 | ~1°（f09_g16） | 14.0 GB | 🔶 成员 001–003 |

**当前磁盘占用**: ~210 GB（数据实际存放在 `E:\2607compound\data\`，通过 NTFS Junction `D:\2607compound\data` 访问）

---

## 目录结构（实际）

`config.py` 中 `BASE_DIR = r"D:\2607compound"`，`DATA_DIR = os.path.join(BASE_DIR, "data")`。
`D:\2607compound\data` 是 NTFS Junction → `E:\2607compound\data`。

```
D:\2607compound\                     ← 工作区根目录（代码/文档/结果）
├── data/                            ← NTFS Junction → E:\2607compound\data
│   ├── OISST/
│   │   ├── oisst_v2.1_1982_2023.nc            # 全球合并件 (23.1 GB)
│   │   ├── oisst_v2.1_eur_1983_2023.nc        # 欧洲裁剪件 (1.1 GB)
│   │   └── temp_raw/                           # NOAA 按年原始文件
│   ├── E-OBS/
│   │   ├── EOBS_tg_1983_2023.nc               # 合并件 (0.5 GB)
│   │   ├── tg_ens_mean_0.25deg_reg_1980-1994_v33.0e.nc
│   │   ├── tg_ens_mean_0.25deg_reg_1995-2010_v33.0e.nc
│   │   └── tg_ens_mean_0.25deg_reg_2011-2023_v29.0e.nc
│   ├── ERA5/
│   │   ├── d2m_global_daily/                   # 按月分文件 × 573 (40.6 GB)
│   │   │   ├── d2m_global_1979_01.nc
│   │   │   └── ...
│   │   ├── sp/                                 # 按年分文件 × 46 (4.1 GB)
│   │   │   ├── pres.sfc.daily.era5.1979.nc
│   │   │   └── ...
│   │   ├── tmax_eur_daily/                     # 按月分文件 (待下载)
│   │   │   └── tmax_eur_1984_01.nc
│   │   └── t2m/                                # (空)
│   ├── OAFlux/                                 # (空, 待下载)
│   └── CESM1-LE/
│       ├── raw/                                # 全时段原始文件 × 18 (109.3 GB)
│       └── proc/                               # 裁剪 2000-2021 欧洲子集 × 21 (14.0 GB)
├── python/
├── results/
├── logs/
└── ...
```

---

## 数据集 1：OISST v2.1（NOAA）

**用途**: 海洋热浪检测（SST）

**状态**: ✅ 已下载完成

**已就位文件**:
- `data/OISST/oisst_v2.1_1982_2023.nc` — 全球合并件，23.1 GB（15340 天 × 720 × 1440）
- `data/OISST/oisst_v2.1_eur_1983_2023.nc` — 欧洲区域裁剪件，1.1 GB
- `data/OISST/temp_raw/` — 按年原始 NetCDF 文件

**config.py 关键路径**:
```python
OISST_MERGED_FILE = os.path.join(OISST_DIR, "oisst_v2.1_1982_2023.nc")
```

**数据集信息**:
- 来源: NOAA NCEI Optimum Interpolation SST v2.1
- 变量: `sst`（海表温度）
- 分辨率: 0.25° × 0.25° 日度
- 网格: 720 lat × 1440 lon
- 时间范围: 1982-01-01 至 2023-12-31
- ⚠️ 版本口径: 论文正文写 OISST v2.0（引 Reynolds et al. 2007）；本项目使用 NOAA 现行
  **v2.1**（v2.0 的维护版本、同一 0.25° 日值产品线）。v2.0 已停更且 2023 年数据仅 v2.1 提供，
  属记录在案的可接受偏差

**下载地址**（备查）: https://www.ncei.noaa.gov/products/optimum-interpolation-sst

---

## 数据集 2：E-OBS（Copernicus Climate Data Store）

**用途**: 陆地热浪检测（日平均气温 tg）

**状态**: ✅ 已下载完成

**⚠️ 时间范围修正**: 实际分析使用 **1983–2023**（气候态基准期 1983–2012），不是早期文档写的 1984–2023。

**已就位文件**:

| 文件 | 版本 | 时间段 | 大小 |
|------|------|--------|------|
| `tg_ens_mean_0.25deg_reg_1980-1994_v33.0e.nc` | v33.0e | 1980–1994 | 167 MB |
| `tg_ens_mean_0.25deg_reg_1995-2010_v33.0e.nc` | v33.0e | 1995–2010 | 181 MB |
| `tg_ens_mean_0.25deg_reg_2011-2023_v29.0e.nc` | v29.0e | 2011–2023 | 146 MB |
| **EOBS_tg_1983_2023.nc** (合并件) | — | 1983–2023 | 499 MB |

**config.py 关键路径**:
```python
EOBS_RAW_FILES = [
    os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_1980-1994_v33.0e.nc"),
    os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_1995-2010_v33.0e.nc"),
    os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_2011-2023_v29.0e.nc"),
]
EOBS_MERGED_FILE = os.path.join(EOBS_DIR, "EOBS_tg_1983_2023.nc")
```

**版本说明**（`config.py: EOBS_VERSION_NOTE`）:
> Mixed versions: v33.0e (1980–2010) + v29.0e (2011–2023). Analysis subset to 1983–2023.

**数据集信息**:
- 变量: `tg`（日平均气温, daily mean）
- 分辨率: 0.25° × 0.25° 日度
- 空间范围: 欧洲区域（约 25N–71.5N, 25W–45E）
- 网格: 201 lat × 464 lon

**下载地址**: https://cds.climate.copernicus.eu/datasets/insitu-gridded-observations-europe

**注意事项**:
- 文件是 E-OBS **网格数据**（`tg_ens_mean_0.25deg_reg_*` 格式），不是站点数据
- E-OBS 数据集按时间段分段发布（约 15 年一段），需下载多段后用 xarray 合并
- `EOBS_tg_1983_2023.nc` 由上述 3 个分段文件合并生成，分析子集从 1983 年起

---

## 数据集 3：ERA5（Copernicus Climate Data Store）

**用途**: WBT 计算（Phase 5 湿热应力需要 tmax, d2m, sp 三个变量）

### 3a. ERA5 d2m（2m 露点温度）— ✅ 已就位

| 项目 | 实际值 |
|------|--------|
| 目录 | `data/ERA5/d2m_global_daily/` |
| 文件格式 | `d2m_global_YYYY_MM.nc`（按月分文件 × 573） |
| 时间范围 | 1979-01 至 2026-09 |
| 空间范围 | 全球 |
| 分辨率 | 0.25° 日度 |
| 总大小 | 40.6 GB |

### 3b. ERA5 sp（地表气压）— ✅ 已就位

| 项目 | 实际值 |
|------|--------|
| 目录 | `data/ERA5/sp/` |
| 文件格式 | `pres.sfc.daily.era5.YYYY.nc`（按年分文件 × 46） |
| 时间范围 | 1979–2024 |
| 空间范围 | 全球 |
| 分辨率 | **1.0°** 日度（⚠️ 不是 0.25°） |
| 总大小 | 4.1 GB |

### 3b+. ERA5 sp 0.25°（欧洲框）— ⬜ 待下载（P1，修正论文分辨率偏差）

| 项目 | 目标值 |
|------|--------|
| 目录 | `data/ERA5/sp_eur_daily/` |
| 文件格式 | `sp_eur_YYYY_MM.nc`（按月分文件） |
| 时间范围 | 1984–2023（与 tmax 一致，覆盖图 5c/6 分析期） |
| 空间范围 | 欧洲 [N=66, W=-10, S=30, E=40]（与 tmax 下载框一致） |
| 分辨率 | **0.25°** 日度（论文口径） |
| 预计总大小 | ~1 GB |
| 当前进度 | 未开始 |

**为什么需要**: 论文 Methods 声明 WBT/SH 相关 ERA5 变量均为 0.25°；现有 sp 为 1.0° 全球件，
把 1.0° 重采样到 0.25° 不产生新信息，属方法学降级。0.25° sp 就位后 WBT/SH 全变量统一 0.25°。
CDS 数据集与 tmax 相同（`derived-era5-single-levels-daily-statistics`，sp 取逐日均值
`daily_statistic=mean`）；复用 `download_era5_tmax.py` 框架改变量与输出目录即可。

> 决策记录：若最终不下载，则必须在复现报告偏差清单中明确 "sp 1.0° 重采样到 0.25°"
> 的降级理由，不得默认无声降级。

### 3c. ERA5 tmax（日最高气温）— ⬜ 待下载

| 项目 | 目标值 |
|------|--------|
| 目录 | `data/ERA5/tmax_eur_daily/` |
| 文件格式 | `tmax_eur_YYYY_MM.nc`（按月分文件） |
| 时间范围 | 1984–2023 |
| 空间范围 | 欧洲 [N=66, W=-10, S=30, E=40] |
| 分辨率 | 0.25° 日度 |
| 预计总大小 | ~1–2 GB |
| 当前进度 | 仅 1984-01（1 个文件） |

**自动化下载**:
```powershell
python python\download_era5_tmax.py          # 1984-2023 按月下载+校验, 断点续传
python python\download_era5_tmax.py --merge  # 生成 data\ERA5\ERA5_tmax_1984_2023_daily.nc
```

- 数据集: CDS `derived-era5-single-levels-daily-statistics`（日最高气温 = hourly mx2t 的逐日最大）
- 键名注意: 日统计键是 **`daily_statistic`**（不是 `statistic`）; `time_zone=utc+00:00` 对欧洲区域与当地日最大值一致
- 首次运行前置: `pip install cdsapi`；`~/.cdsapirc` 已配置有效；若数据集页面未接受过 CC-BY 许可，需先在线接受一次
- 下载脚本空间范围: `AREA = [66, -10, 30, 40]`（欧洲区域，非全球）

**下载地址**: https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics

**注意事项**:
- ~~旧 hourly API 片段已删除~~：`reanalysis-era5-single-levels` 是 **hourly** 数据集（24 时次 × 40 年体积过大且语义错误）。日值请用 `derived-era5-single-levels-daily-statistics`
- d2m 和 sp 是全球数据但分辨率不一致（d2m 0.25° / sp 1.0°）。**已立项下载 0.25° sp 欧洲框（数据集 3b+），届时以 0.25° 为准，1.0° 件仅作全球备查**

---

## 数据集 4：OAFlux（WHOI）

**用途**: 海洋蒸发趋势（Phase 5）

**状态**: ⬜ 未下载；下载脚本已就绪

**自动化（推荐）**:
```powershell
python python\download_oaflux_evap.py            # 1991-2020, 自动镜像降级+强校验+合并
python python\download_oaflux_evap.py --probe    # 只探测各镜像可用性
```

- **官方主源**: `ftp://ftp.whoi.edu/pub/science/oaflux/data_v3`（WHOI 官网 data-access 页列出）
- **官方镜像**: WHOI HTTP（ftp1.whoi.edu）、NOAA PSL THREDDS、APDRC、UCAR RDA ds260.1
- **免账号**; 脚本按官方镜像优先级自动探测 evap 月值文件, 逐文件内容校验后合并
- 输出: `data/OAFlux/OAFlux_evap_1991_2020_monthly.nc`
- 注意（2025-09-22 实测）: WHOI FTP 端口本网络不通、PSL THREDDS 维护中、APDRC 502, 均为临时状况; 换网络/稍后重试即可
- UCAR climatedataguide 页面只是**介绍页**（非直接下载入口），手动下载请走 WHOI 官网

**下载地址**: https://oaflux.whoi.edu/data-access/

**数据集信息**:
- 变量: `evap`（月度蒸发）
- 分辨率: 1° 月度
- 预计大小: ~100 MB

---

## 数据集 5：CESM1-LE（NCAR GDEX / AWS）

**用途**: Phase 6 归因分析（ALL 强迫 + XGHG 反事实；论文口径 ALL-but-GHG）

**⚠️ 重要命名修正**: 本项目的"FixGHG"实为 CESM1-LE 的 **XGHG** 单强迫实验（`b.e11.B20TRLENS_RCP85.f09_g16.xghg`），不是早期文档写的 `B20TRC5CNBDRD.FixGHG`。

**当前状态**: 已下 raw 109.3 GB + proc 14.0 GB（成员 001–003 部分文件），断点续传续补。

**实际数据组织**:

```
data/CESM1-LE/
├── raw/                          # 全时段全球原始文件（仅 P0 已下部分）
│   ├── b.e11.B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.SST.18500102-20051231.nc
│   ├── b.e11.B20TRC5CNBDRD.f09_g16.002.pop.h.nday1.SST.19200102-20051231.nc
│   ├── b.e11.B20TRC5CNBDRD.f09_g16.003.pop.h.nday1.SST.19200102-20051231.nc
│   ├── b.e11.BRCP85C5CNBDRD.f09_g16.001.pop.h.nday1.SST.20060102-20801231.nc
│   ├── b.e11.BRCP85C5CNBDRD.f09_g16.002.pop.h.nday1.SST.20060102-20801231.nc
│   ├── b.e11.BRCP85C5CNBDRD.f09_g16.003.pop.h.nday1.SST.20060102-20801231.nc
│   ├── b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.19200101-20051231.nc
│   ├── b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.20060101-20801231.nc
│   ├── b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.pop.h.nday1.SST.19200102-20051231.nc
│   ├── ... (共 18 文件, 109.3 GB)
│   └── ...
└── proc/                         # 裁剪到 2000-2021 欧洲框后的文件
    ├── b.e11.B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.SST.18500102-20051231_2000-2021.nc
    ├── b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.19200101-20051231_2000-2021.nc
    ├── TREFHT_all_001_2000-2021_europe.nc
    ├── ... (共 21 文件, 14.0 GB)
    └── ...
```

**config.py 关键路径与参数**:
```python
CESM_DIR = os.path.join(DATA_DIR, "CESM1-LE")
CESM_RAW_DIR = os.path.join(CESM_DIR, "raw")    # RDA 下载的全时段原始文件
CESM_PROC_DIR = os.path.join(CESM_DIR, "proc")  # 裁剪到分析时段后的文件
CESM_PERIOD = ("2000-01-01", "2021-12-31")      # 论文 L522: 2000-2021
CESM_P0_MEMBERS = 3
CESM_EUROPE_LAT = (28.0, 74.0)
CESM_EUROPE_LON = (-17.0, 47.0)
```

**实验与变量**:

| 实验 | 模式 | 变量 | 段名 | 说明 |
|------|------|------|------|------|
| ALL（大气） | CAM5 | TREFHT | `B20TRC5CNBDRD` (1920–2005) + `BRCP85C5CNBDRD` (2006–2080) | 2m 气温，日值 |
| ALL（海洋） | POP | SST | `B20TRC5CNBDRD` + `BRCP85C5CNBDRD` | 海表温度，nday1 |
| XGHG（大气） | CAM5 | TREFHT | `B20TRLENS_RCP85.f09_g16.xghg` | 反事实（温室气体固定） |
| XGHG（海洋） | POP | SST | `B20TRLENS_RCP85.f09_g16.xghg` | 反事实 |

**⚠️ 时间范围说明**:
- 文件命名中的实际时段与文档早期描述不同：
  - 成员 001 的历史段从 **1850** 起（`18500101-20051231`）
  - 成员 002–020 的历史段从 **1920** 起（`19200101-20051231`）
  - RCP85 延伸段到 **2080**（`20060101-20801231`）
  - 分析实际只取 **2000–2021**（`config.py: CESM_PERIOD`）

**自动化（推荐，已实爬验证源可用）**:
```powershell
# P0 验证（成员 001-003, 双击或命令行均可, 断点续传）
run_p0_download.bat
# 全量 20 成员
python python\download_cesm1le.py aws --members 20    # ALL 日值 TREFHT 走 AWS zarr
python python\download_cesm1le.py gdex --members 20   # SST + XGHG 走 NCAR GDEX
```

- 精确文件清单（实爬生成）: `results/tables/cesm1le_download_manifest.csv`
- 走系统代理实测 2.24 MB/s（直连 <0.1）; 工具已自动接入
- 数据选型依据（为何不用 CMIP6）见 `results/复现报告.md` §11

**下载地址**: https://gdex.ucar.edu/datasets/d651027/ （GDEX d651027, 匿名可用）· AWS 镜像 `s3://ncar-cesm-lens`（仅 ALL 日值 TREFHT）

**注意事项**:
- 自动化脚本默认走 proc 流程（服务端切片 2000-2021 + 欧洲裁剪），产出 proc/ 子集而非全量原始文件
- 全量 20 成员 proc 子集约 100 GB（基于 P0 成员 001–003 的 14 GB 外推）
- 如需全量原始文件（raw），每成员约 40 GB，20 成员约 800 GB（不推荐，除非有特殊需求）
- 存储在 E: 盘（E:\2607compound\data\CESM1-LE\）

---

## 数据验证

**使用方法**:
```powershell
cd D:\2607compound
python python\verify_data.py
```

**实际验证内容**（`python/verify_data.py`）:
1. OISST 合并件（检查存在、大小、维度 time×lat×lon）
2. E-OBS 合并件（检查存在、大小、维度）
3. SST/T2m 气候态文件
4. MHW/THW 事件 CSV
5. 沿海配对 CSV
6. 复合事件/独立事件 NC 文件

**注意**: 上述脚本检查的是**中间产物**而非原始下载数据的完整性。原始数据完整性由各下载脚本内置校验保障。

---

## 下载优先级建议

| 优先级 | 数据集 | 状态 | 剩余工作 |
|--------|--------|------|----------|
| **P0** | OISST | ✅ 完成 | — |
| **P0** | E-OBS | ✅ 完成 | — |
| **P0** | ERA5 d2m + sp | ✅ 完成 | — |
| **P1** | ERA5 tmax | ⬜ 待下载 | 运行 `python\download_era5_tmax.py` |
| **P1** | OAFlux | ⬜ 待下载 | 运行 `python\download_oaflux_evap.py` |
| **P1** | ERA5 sp 0.25°（欧洲框） | ⬜ 待下载 | 新增任务：修正论文分辨率偏差（数据集 3b+） |
| **P2** | CESM1-LE 全量 | 🔶 P0 已就位 | `run_p0_download.bat` 验证通过后跑全量 20 成员 |

**建议**: 先补齐 P1 数据（tmax + OAFlux），跑通 Phase 5（湿热应力）观测流程，再下载 CESM1-LE 全量做归因分析。

---

## 存储空间规划

数据实际存放在 **E:\2607compound\data\**（通过 `D:\2607compound\data` NTFS Junction 访问）。

```
E:\2607compound\data\              ← 数据盘
├── OISST/                         # 24 GB (全球 23.1 + 欧洲 1.1)
├── E-OBS/                         # 1 GB
├── ERA5/                          # 47 GB (d2m 40.6 + sp 4.1 + tmax ~2)
├── OAFlux/                        # 0.1 GB
└── CESM1-LE/                      # 已有 132 GB (raw 117 + proc 15)
                                   # 全量 20 成员 proc 约 +100 GB

总计（全量完成后）: ~310 GB
建议 E:\ 盘预留: 400 GB
```

---

## 网络要求

| 数据集 | 下载方式 | 预计时间 | 注意事项 |
|--------|----------|----------|----------|
| OISST | HTTP (NCEI) | — | ✅ 已完成 |
| E-OBS | CDS 网页/API | — | ✅ 已完成 |
| ERA5 tmax | CDS API | 数小时 | 可后台运行, 断点续传 |
| OAFlux | HTTP/FTP (WHOI) | 几分钟 | 多镜像自动降级 |
| CESM1-LE | AWS zarr / GDEX THREDDS | 数天 | 走系统代理 2.24 MB/s |

**推荐**: 使用 **CDS API** 下载 ERA5 tmax，**AWS zarr** 下载 CESM1-LE ALL TREFHT，**GDEX THREDDS** 下载 SST + XGHG。
