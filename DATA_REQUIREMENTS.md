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
| **OISST temp_raw（未合并原始）** | `data/OISST/temp_raw/oisst-avhrr-v02r01.YYYYMMDD.nc` × 15340 | 1982–2023 | 全球 | 0.25° 日度 | 23.9 GB（**第三轮补登**） | ✅ 就位（合并后仍保留） |
| **E-OBS tg 合并** | `data/E-OBS/EOBS_tg_1983_2023.nc` | 1983–2023 | 欧洲 | 0.25° 日度 | 0.5 GB（14975 天 × 201 × 464） | ✅ 就位 |
| **E-OBS tg 分段原始** | `data/E-OBS/tg_ens_mean_0.25deg_reg_*.nc` × 3 | 1980–2023 | 欧洲 | 0.25° 日度 | 0.46 GB | ✅ 就位 |
| **ERA5 d2m** | `data/ERA5/d2m_global_daily/d2m_global_YYYY_MM.nc` × 573 | 1979–2026 | 全球 | 0.25° 日度 | 40.6 GB（另有未登记 `yearly/` × 47 = 37.7 GiB，见 3a） | ✅ 就位 |
| **ERA5 sp** | `data/ERA5/sp/pres.sfc.daily.era5.YYYY.nc` × 46 | 1979–2024 | 全球 | **1.0°** 日度 | 4.1 GB | ✅ 就位（⬜ 0.25° 欧洲框见 3b+） |
| **ERA5 tmax** | `data/ERA5/tmax_eur_daily/tmax_eur_YYYY_MM.nc` × 1 | 1984–2023 | 欧洲 [66N,10W,30N,40E] | 0.25° 日度 | ~0（仅 1984-01） | ⬜ 待下载 |
| **OAFlux evap** | `data/OAFlux/`（空） | 1991–2020 | 全球 | 1° 月度 | — | ⬜ 待下载 |
| **CESM1-LE raw** | `data/CESM1-LE/raw/` × 18 文件 | 1850/1920–2080 | 全球 | ~1°（f09_g16） | 109.3 GB | 🔶 成员 001–003 部分 |
| **CESM1-LE proc** | `data/CESM1-LE/proc/` × 21 文件 | 2000–2021 | 欧洲裁剪 | ~1°（f09_g16） | 14.0 GB | 🔶 成员 001–003 |

**当前磁盘占用**: **实测 254.7 GiB / 273.4 GB**（16,053 文件，`E:\2607compound\data\`，
经 NTFS Junction `D:\2607compound\data` 访问）。早期文档写的 "~210 GB" 既与自身分量之和不符
（OISST 24 + E-OBS 0.5 + ERA5 45 + CESM 123 = 192.5），也未计入 OISST `temp_raw`（23.9 GB）
与 ERA5 `d2m_global_daily/yearly/`（37.7 GiB）——已按实测更正。
**E: 盘容量 465.8 GB、剩余 190.1 GB（2026-09-23 实测，exFAT）**，是 CESM 全量下载的硬前提。

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
│   │   └── temp_raw/                           # NOAA 原始文件 × 15340（**按日**，23.9 GB；
│   │                                           #   `oisst-avhrr-v02r01.YYYYMMDD.nc`，早期写"按年"有误）
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
- 变量: 分段原始文件为 `tg`（日平均气温, daily mean）；**合并件 `EOBS_tg_1983_2023.nc` 中已改名为 `T2m`**
  （`load_data.py` 读取时依赖此名）
- 分辨率: 0.25° × 0.25° 日度
- 空间范围: 欧洲区域（**合并件实测** lat 25.375–75.375N / lon −40.375–75.375E；早期文档写的
  "25N–71.5N, 25W–45E" 为估值，已按实测更正）
- 网格: 201 lat × 464 lon

**⚠️ 论文口径提示（未决）**: 论文 Methods 只写陆地用 E-OBS "daily near-surface temperature, T2m"，
**未说明是日平均（tg）还是日最高（tx）**；本项目全程使用 `tg`。该选择已登记为偏差候选
（`results/复现报告.md` §10 待办 6 / `results/规划一致性审查.md` 第二轮 P0-N1），
tx 敏感性实验为低优先级待做项。

**⚠️ 气候态跨版本边界**: 本项目气候态为 1983–2012，其中 **2011–2012 落在 v29.0e 段**、
1983–2010 落在 v33.0e 段——即 90 分位阈值跨了 E-OBS 版本切换点。已做四项拼接检验
（`results/方法与证据.md` §2：未发现 2011 伪影），但"统一版本重拼"仍是可选的最干净收尾。

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
`daily_statistic = daily_mean`）。

**自动化下载（脚本已就绪，2026-09-23；尚未运行）**:
```powershell
python python\download_era5_sp025.py --dry-run   # 只列计划: 0 已就位 / 480 待下载, 不联网不写盘
python python\download_era5_sp025.py             # 1984-2023 按月下载+校验, 断点续传
python python\download_era5_sp025.py --merge     # 生成 data\ERA5\ERA5_sp_1984_2023_daily.nc
```
- 变量短名 `sp`，单位 Pa；脚本内置量纲校验（首时次必须在 9.0e4–1.06e5 Pa，
  可捕获"下错变量"这类错误）
- **不覆盖**现有 1.0° 全球件 `data/ERA5/sp/`（保留作对照）

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
| 当前进度 | 仅 1984-01（1 个文件）；dry-run 实测 1 已就位 / **479 待下载** |

**自动化下载**:
```powershell
python python\download_era5_tmax.py --dry-run # 只列计划, 不联网不写盘
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
- 论文写的是 CESM1-LE「1920 to 2100, RCP8.5 from 2006」（`results/paper_text.txt:627`）；
  但**本地实际档案要按实验区分**（第三轮更正，避免"档案至 2080"被误读成论文口径）：
  - **ALL 实验**：RCP85 延伸段在本项目的 GDEX/AWS 清单里到 **2080**（已下载段
    `20060102-20801231`）；论文声称到 2100，2081–2100 段本地未下载、未证实存在。
  - **XGHG 单强迫实验**：**本身只到 2080**（`results/复现报告.md` §11.5）。
  - 成员 001 的历史段从 **1850** 起（`18500101-20051231`），成员 002–020 从 **1920** 起。
  - 分析实际只取 **2000–2021**（`config.py: CESM_PERIOD`），故上述差异不影响本复现结论。
- 因此文档中凡写「档案至 2080」处，其准确含义是**本地已下载/可得段止于 2080**，不是论文时序。

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
  —— **E: 盘 2026-09-23 实测总 465.8 GB、剩余 190.1 GB**，故 raw 路径（~800 GB）在本机**不可行**；
  proc 路径（~+100 GB）可行，但需在下载前后用 `Get-Volume` 确认余量。

> ⚠️ **P0 阻塞项（第三轮审查 2026-09-23 发现，开跑全量前必须先修）**：
> `run_phase6_download.bat` 第 2/3 步执行的是 `python python\download_cesm1le.py gdex --members 20`，
> 其产出命名为 **`{var}_{exp}_{mem}_2000-2021.nc`**
> （如 `trefht_xghg_004_2000-2021.nc`、`sst_all_004_2000-2021.nc`，见 `download_cesm1le.py:382`）；
> 而 `python/phase6_cesm.py::find_t2m_segments/find_sst_segments`（`:111-136`）只识别
> **raw 派生名**（`TREFHT_all_{m}_2000-2021_europe.nc`、`*xghg.{m}.cam.h1.TREFHT.*_2000-2021.nc`、
> `*B20TRC5CNBDRD.f09_g16.{m}.pop.h.nday1.SST.*_2000-2021.nc`）。
> 后果：`prepare` 对成员 004–020 打印「!! 无 TREFHT 段文件, 跳过」，`detect` 在成员 004
> 抛 `FileNotFoundError`（`:274`）——**全量口径实际只会跑 3 个成员**（与 F5 修复的"静默只跑 3 成员"同类）。
> 修法（三选一）：① 统一 `gdex` 输出命名；② 给 `find_*_segments` 加该命名分支；
> ③ 全量改走 `download --urls <manifest>` + `trim`（raw 派生名，但需要 ~800 GB 空间，本机不可行）。
>
> ✅ **已按 ②+① 组合修复（2026-09-23，第三轮；仅改代码未运行）**：
> - `python/phase6_cesm.py` **F11**：`find_t2m_segments` / `find_sst_segments` 现在同时接受
>   gdex 命名与 aws/trim 派生名；`cmd_prepare` / `cmd_pairs` 不再硬编码
>   `TREFHT_all_001_2000-2021_europe.nc`；新增 `_norm_latlon()` 兼容 `latitude/longitude`。
> - `python/download_cesm1le.py`：`cmd_gdex` 对 ocn 件保留 **KMT/TLAT/TLONG**（否则下游 KeyError），
>   且 `_mask_sst_box` **改为只掩膜、不做空间裁剪**——保持 POP 全局网格，使
>   `coastal_pairs_cesm.csv` 的网格索引与文件来源无关。
> - **仍需注意**：gdex 件若在本修复之前生成，需重下；首次运行前先 `py_compile` 与跑自检（均未执行）。

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

> **2026-09-23 更新**：下载脚本已全部就绪（**均未运行**）。
> 两个一键入口：`run_phase5_downloads.bat`（tmax + sp 0.25° + OAFlux）、
> `run_phase6_download.bat`（CESM1-LE 全量 20 成员）。

| 优先级 | 数据集 | 状态 | 剩余工作 |
|--------|--------|------|----------|
| **P0** | OISST | ✅ 完成 | — |
| **P0** | E-OBS | ✅ 完成 | — |
| **P0** | ERA5 d2m | ✅ 完成 | — |
| **P1** | ERA5 tmax | ⬜ 待下载 | `python\download_era5_tmax.py`（479 个月） |
| **P1** | ERA5 sp 0.25°（欧洲框） | ⬜ 待下载 | `python\download_era5_sp025.py`（480 个月，数据集 3b+） |
| **P1** | OAFlux | ⬜ 待下载 | `python\download_oaflux_evap.py` |
| **P2** | CESM1-LE 全量（20 成员） | 🔶 成员 001–003 就位 | `run_phase6_download.bat`（~750 GB，4–5 天） |

**建议顺序**：
1. **Phase 5 数据优先**（tmax + sp 0.25° + OAFlux）—— 这是 Phase 5（图5–6）的**唯一阻塞**；
   100 km 海岸缓冲、图6c 规格、S1 非复合年判据**均已就绪**，数据一到即可全跑。
2. **同时启动 CESM 全量**（后台，4–5 天连续）—— Phase 6（图3–4）全靠它，宜尽早并行。

**注意**：不要再用备查的 1.0° 全球 sp 件（`data/ERA5/sp/`）做 WBT/SH，
除非在复现报告中登记该降级；0.25° 件就位后以后者为准。

---

## 存储空间规划

数据实际存放在 **E:\2607compound\data\**（通过 `D:\2607compound\data` NTFS Junction 访问）。

```
E:\2607compound\data\              ← 数据盘
├── OISST/                         # 24 GB (全球 23.1 + 欧洲 1.1)
├── E-OBS/                         # 1 GB
├── ERA5/                          # 现在 45 GB (d2m 40.6 + sp 4.1)
│                                  # 补齐后 +3 GB (tmax ~2 + sp 0.25° ~1)
├── OAFlux/                        # 0.1 GB
└── CESM1-LE/                      # 已有 123 GB (raw 109 + proc 14)
                                   # 全量 20 成员约再 +750 GB

总计（全量完成后）: ~950 GB
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
