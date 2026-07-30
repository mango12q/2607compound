# 数据下载要求

## 数据清单总览

| 数据集 | 时间范围 | 空间范围 | 分辨率 | 预计大小 | 用途 |
|--------|----------|----------|--------|----------|------|
| **OISST v2** | 1982–2023 | 全球 | 0.25° 日度 | ~3 GB | 海洋热浪检测 |
| **E-OBS tg** | 1984–2023 | 欧洲 | 0.25° 日度 | ~2 GB | 陆地热浪检测 |
| **ERA5 tmax** | 1984–2023 | 全球 | 0.25° 日度 | ~8 GB | WBT 计算 |
| **ERA5 d2m** | 1984–2023 | 全球 | 0.25° 日度 | ~8 GB | WBT 计算 |
| **ERA5 sp** | 1984–2023 | 全球 | 0.25° 日度 | ~8 GB | WBT 计算 |
| **OAFlux** | 1991–2020 | 全球 | 1° 月度 | ~100 MB | 蒸发趋势 |
| **CESM1-LE ALL** | 1850–2023 | 全球 | ~1° | ~200 GB | 归因分析 |
| **CESM1-LE FixGHG** | 1850–2023 | 全球 | ~1° | ~200 GB | 归因分析 |

**总数据量**: ~430 GB

---

## 目录结构要求

下载完成后，`data/` 目录结构必须如下：

```
F:\2607compound\data\
├── OISST\
│   └── oisst_v2.1_1982_2023.nc
├── E-OBS\
│   └── EOBS_tg_1984_2023.nc
├── ERA5\
│   ├── ERA5_tmax_1984_2023_daily.nc
│   ├── ERA5_d2m_1984_2023_daily.nc
│   └── ERA5_sp_1984_2023_daily.nc
├── OAFlux\
│   └── OAFlux_evap_1991_2020_monthly.nc
└── CESM1-LE\
    ├── ALL\
    │   ├── b.e11.B20TRC5CNBDRD.001.cam.h1.TREFHT.185001-202312.nc
    │   ├── b.e11.B20TRC5CNBDRD.002.cam.h1.TREFHT.185001-202312.nc
    │   └── ... (共 20 个成员)
    └── FixGHG\
        ├── b.e11.B20TRC5CNBDRD.FixGHG.001.cam.h1.TREFHT.185001-202312.nc
        └── ... (共 20 个成员)
```

---

## 数据集 1：OISST v2（NOAA）

**用途**: 海洋热浪检测（SST）

**下载地址**: https://www.ncei.noaa.gov/products/optimum-interpolation-sst

**操作步骤**:

1. **打开网页**: https://www.ncei.noaa.gov/products/optimum-interpolation-sst
2. **点击 "Access Data"**（通常在页面中间位置）
3. **选择数据版本**: 找到 **"OISST v2.1 (1981–present)"** 或最新版本
4. **选择数据格式**: 点击 **"NetCDF"** 格式链接
5. **在下载页面**:
   - 时间范围：**1982-01-01** 至 **2023-12-31**
   - 变量：勾选 **`sst`**（海表温度）
   - 空间范围：默认全球（无需修改）
   - 格式：NetCDF
6. **点击 "Download"** 或 "Submit"
7. **保存文件到**: `F:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc`

**预期文件大小**: ~3 GB

**注意事项**:
- 如果网页只提供按年下载，需逐年下载后合并
- 合并命令（Python）:
  ```python
  import xarray as xr
  ds = xr.open_mfdataset('OISST/*.nc', combine='by_coords')
  ds.to_netcdf('OISST/oisst_v2.1_1982_2023.nc')
  ```

---

## 数据集 2：E-OBS（Copernicus Climate Data Store）

**用途**: 陆地热浪检测（T2m）

**下载地址**: https://cds.climate.copernicus.eu/datasets/insitu-gridded-observations-europe

doubao的链接 https://www.doubao.com/thread/x8PXIKs2BPXh1GfNR

**操作步骤**:

1. **打开网页**: https://cds.climate.copernicus.eu/datasets/ecv-for-temp-ens
2. **注册/登录**: 需要免费注册 Copernicus 账号（点击 "Register"）
3. **登录后点击 "Download data"**
4. **选择选项**:
   - **Version**: 选择最新版本（如 `26.0e` 或 `27.0`）
   - **Variable**: 选择 **`tg`**（日平均气温）
   - **Time range**: `1984-01-01` 至 `2023-12-31`
   - **Spatial coverage**: 默认欧洲区域（无需修改）
   - **Format**: `NetCDF`
5. **点击 "Submit"** 提交订单
6. **等待邮件通知**（通常几分钟到几小时）
7. **下载完成后**，将文件移动到 `F:\2607compound\data\E-OBS\EOBS_tg_1984_2023.nc`

**预期文件大小**: ~2 GB

**注意事项**:
- 需要注册账号，下载有延迟
- 如果只需要欧洲区域，可在下载时裁剪空间范围以减小文件大小
- E-OBS 文件名通常包含版本号，如 `TG_STAID02665_v27.0e.nc`，需统一重命名

---

## 数据集 3：ERA5（Copernicus Climate Data Store）

**用途**: WBT 计算（需要 tmax, d2m, sp）

**下载地址**: https://cds.climate.copernicus.eu/datasets/era5-daily-single-levels

**操作步骤**:

1. **打开网页**: https://cds.climate.copernicus.eu/datasets/era5-daily-single-levels
2. **登录**（使用 Copernicus 账号，与 E-OBS 相同）
3. **点击 "Download data"**
4. **选择变量**（需下载 3 次，每次选一个变量）:

   **第一次 - 日最高气温 (tmax)**:
   - Variable: `Maximum temperature at 2 metres since previous post-processing`
   - Time range: `1984-01-01` 至 `2023-12-31`
   - Spatial coverage: North=66, West=-10, South=30, East=40
   - Format: NetCDF

   **第二次 - 露点温度 (d2m)**:
   - Variable: `2 metre dewpoint temperature`
   - 其他同上

   **第三次 - 地表气压 (sp)**:
   - Variable: `Surface pressure`
   - 其他同上

5. **提交下载**（每次单独提交）
6. **重命名文件**:
   - `ERA5_daily_tmax_1984_2023.nc` → `ERA5_tmax_1984_2023_daily.nc`
   - `ERA5_daily_d2m_1984_2023.nc` → `ERA5_d2m_1984_2023_daily.nc`
   - `ERA5_daily_sp_1984_2023.nc` → `ERA5_sp_1984_2023_daily.nc`
7. **保存到**: `F:\2607compound\data\ERA5\`

**预期文件大小**: 每个 ~8 GB，共 ~24 GB

**注意事项**:
- 下载可能需要几小时到几天
- 可使用 CDS API 批量下载（更稳定）:
  ```python
  import cdsapi
  c = cdsapi.Client()
  c.retrieve(
      'reanalysis-era5-single-levels',
      {
          'product_type': 'reanalysis',
          'variable': 'maximum_temperature_at_2_metres_since_previous_post_processing',
          'year': list(range(1984, 2024)),
          'month': [f'{m:02d}' for m in range(1, 13)],
          'day': [f'{d:02d}' for d in range(1, 32)],
          'time': [f'{h:02d}:00' for h in range(24)],
          'area': [66, -10, 30, 40],
          'format': 'netcdf',
      },
      'ERA5_tmax_1984_2023.nc'
  )
  ```

---

## 数据集 4：OAFlux（UCAR）

**用途**: 海洋蒸发趋势

**下载地址**: https://climatedataguide.ucar.edu/climate-data/oaflux-objectively-analyzed-air-sea-fluxes-global-oceans

**操作步骤**:

1. **打开网页**: https://climatedataguide.ucar.edu/climate-data/oaflux-objectively-analyzed-air-sea-fluxes-global-oceans
2. **滚动到 "Data Access" 部分**（页面下方）
3. **点击下载链接**: 找到 **"OAFlux monthly evaporation (1958–present)"**
4. **注册账号**: 需要注册 UCAR 账号（免费）
5. **选择时间范围**: 1991-01 至 2020-12
6. **下载文件**
7. **保存到**: `F:\2607compound\data\OAFlux\OAFlux_evap_1991_2020_monthly.nc`

**预期文件大小**: ~100 MB

**注意事项**:
- 如果下载的是多个文件（如每年一个），需合并为一个文件
- 合并命令:
  ```python
  import xarray as xr
  ds = xr.open_mfdataset('OAFlux/*.nc', combine='by_coords')
  ds.to_netcdf('OAFlux/OAFlux_evap_1991_2020_monthly.nc')
  ```

---

## 数据集 5：CESM1-LE（Earth System Grid Federation）

**用途**: 归因分析（ALL 强迫 + FixGHG）

**下载地址**: https://www.earthsystemgrid.org/dataset/

**操作步骤**:

1. **打开网页**: https://www.earthsystemgrid.org/dataset/
2. **注册账号**: 需要免费注册 ESG 账号
3. **搜索数据集**: 在搜索框输入 **"CESM1 large ensemble"**
4. **选择数据集**: `CESM1-CAM5 Large Ensemble`
5. **选择变量**:
   - `TREFHT` (2米气温，陆地)
   - `TEMP` (海表温度，海洋，取 0m 层)
   - 注意：每个变量需要单独下载
6. **选择实验**:
   - **ALL 强迫**: 实验名 `b.e11.B20TRC5CNBDRD`，选择 20 个成员 (001–020)
   - **FixGHG**: 实验名 `b.e11.B20TRC5CNBDRD.FixGHG`，选择 20 个成员 (001–020)
7. **选择时间范围**: 1850-01-01 至 2023-12-31
8. **选择格式**: NetCDF
9. **提交下载**

**目录结构要求**:
```
F:\2607compound\data\CESM1-LE\
├── ALL\
│   ├── b.e11.B20TRC5CNBDRD.001.cam.h1.TREFHT.185001-202312.nc
│   ├── b.e11.B20TRC5CNBDRD.002.cam.h1.TREFHT.185001-202312.nc
│   └── ... (共 20 个成员，每个约 5-10 GB)
└── FixGHG\
    ├── b.e11.B20TRC5CNBDRD.FixGHG.001.cam.h1.TREFHT.185001-202312.nc
    └── ... (共 20 个成员)
```

**预期文件大小**: 每个成员 ~5-10 GB，40 个成员共 **~200-400 GB**

**注意事项**:
- **数据量巨大**，下载需数天到数周
- **存储要求**: 确保 `D:\` 盘有 ≥ 500 GB 空闲空间
- 建议先下载 1-2 个成员测试流程，确认无误再批量下载
- 可使用 Globus 或 wget 脚本批量下载（ESG 提供）

---

## 快速验证脚本

下载完成后，运行以下脚本检查所有数据是否就位：

```python
# verify_data.py
import os

BASE_DIR = r"F:\2607compound"

required = {
    "data/OISST/oisst_v2.1_1982_2023.nc": 3e9,
    "data/E-OBS/EOBS_tg_1984_2023.nc": 2e9,
    "data/ERA5/ERA5_tmax_1984_2023_daily.nc": 8e9,
    "data/ERA5/ERA5_d2m_1984_2023_daily.nc": 8e9,
    "data/ERA5/ERA5_sp_1984_2023_daily.nc": 8e9,
    "data/OAFlux/OAFlux_evap_1991_2020_monthly.nc": 1e8,
}

print("Data verification results:")
print("=" * 60)

all_ok = True
for rel_path, min_size in required.items():
    full_path = os.path.join(BASE_DIR, rel_path)
    if not os.path.exists(full_path):
        print(f"❌ MISSING: {rel_path}")
        all_ok = False
    elif os.path.getsize(full_path) < min_size:
        actual = os.path.getsize(full_path) / 1e9
        expected = min_size / 1e9
        print(f"⚠️  TOO SMALL: {rel_path}")
        print(f"   Expected: ~{expected:.1f} GB, Got: {actual:.1f} GB")
        all_ok = False
    else:
        actual = os.path.getsize(full_path) / 1e9
        print(f"✅ OK: {rel_path} ({actual:.1f} GB)")

print("=" * 60)

# 检查 CESM1-LE（仅检查数量，不检查大小）
cesm_all_dir = os.path.join(BASE_DIR, "data/CESM1-LE/ALL")
cesm_fixghg_dir = os.path.join(BASE_DIR, "data/CESM1-LE/FixGHG")

if os.path.exists(cesm_all_dir):
    all_files = [f for f in os.listdir(cesm_all_dir) if f.endswith('.nc')]
    print(f"CESM1-LE ALL: {len(all_files)}/20 members")
    if len(all_files) < 20:
        all_ok = False
else:
    print("❌ CESM1-LE ALL directory not found")
    all_ok = False

if os.path.exists(cesm_fixghg_dir):
    fixghg_files = [f for f in os.listdir(cesm_fixghg_dir) if f.endswith('.nc')]
    print(f"CESM1-LE FixGHG: {len(fixghg_files)}/20 members")
    if len(fixghg_files) < 20:
        all_ok = False
else:
    print("❌ CESM1-LE FixGHG directory not found")
    all_ok = False

print("=" * 60)
if all_ok:
    print("✅ All data ready! You can now run: python python/run_all.py")
else:
    print("⚠️  Some data is missing or incomplete. Please check the errors above.")
```

**使用方法**:
```bash
cd F:\2607compound
python verify_data.py
```

---

## 下载优先级建议

考虑到数据量和下载时间，建议按以下顺序进行：

| 优先级 | 数据集 | 大小 | 用途 |
|--------|--------|------|------|
| **P0** | OISST | 3 GB | MHW 检测（观测部分必需） |
| **P0** | E-OBS | 2 GB | THW 检测（观测部分必需） |
| **P1** | ERA5 (3个文件) | 24 GB | WBT 计算 |
| **P1** | OAFlux | 100 MB | 蒸发趋势 |
| **P2** | CESM1-LE ALL | ~200 GB | 归因分析（最耗时，可最后下载） |
| **P2** | CESM1-LE FixGHG | ~200 GB | 归因分析 |

**建议**: 先下载 P0 和 P1 数据，验证观测分析流程（图 1-2, 5-6）跑通后，再下载 CESM1-LE 做归因分析。

---

## 存储空间规划

```
F:\2607compound\
├── data/                    # 原始数据（~430 GB）
│   ├── OISST/               # 3 GB
│   ├── E-OBS/               # 2 GB
│   ├── ERA5/                # 24 GB
│   ├── OAFlux/              # 0.1 GB
│   └── CESM1-LE/            # ~400 GB
│       ├── ALL/             # ~200 GB
│       └── FixGHG/          # ~200 GB
│
├── results/                 # 中间结果（~10-50 GB）
│   ├── intermediate/        # 可随时删除重算
│   ├── figures/             # ~1 GB
│   └── tables/              # 可忽略
│
└── 总需求: ~500 GB
```

**建议**: 确保 `D:\` 盘有至少 **600 GB** 空闲空间，以应对中间产物和临时文件。

---

## 网络要求

| 数据集 | 下载方式 | 预计时间 | 注意事项 |
|--------|----------|----------|----------|
| OISST | HTTP/FTP | 10-30 分钟 | 稳定，直接下载 |
| E-OBS | 网页提交 + 邮件通知 | 几小时到1天 | 需注册 |
| ERA5 | CDS API（推荐） | 几小时 | 稳定，可后台运行 |
| OAFlux | HTTP | 几分钟 | 稳定 |
| CESM1-LE | Globus/HTTP | 数天到数周 | 数据量大，建议用 Globus |

**推荐**: 使用 **CDS API** 下载 ERA5，**Globus** 下载 CESM1-LE，速度更快且稳定。
