# AGENTS.md — 论文复现项目

## 项目性质

学术复现项目，非典型软件仓库。目标：复现论文 *Compound coastal marine–terrestrial heatwaves associated with humid-heat stress in Europe*（Scientific Reports 2025）。

**当前进度（2025-09-22）**：Phase 1-4（观测链路：检测→配对→复合→图1/图2/S1/S2）完成，锚点基本命中；Phase 6 P0（CESM 3 成员管线 + v2 反事实基准）验证通过，全量未跑；Phase 5（湿热应力）与 Phase 7（写作）未开始。详见 `results/复现报告.md`。

## 当前可运行文件

主链路（Phase 1-4，已验证）：
- `python/run_all.py` — 四阶段主控（检测→复合→年度指标→CHR/共现概率）
- `python/figures.py` — 图1/图2/S1 出图；`python/fig_jkl_mhw_envelope.py` — S2
- `python/detect_events.R` — 陆地热浪检测正式链路（R heatwaveR；`python/detect_thw.R` 有吞错 bug 仅存档勿用）
- `python/phase6_cesm.py` — Phase 6 归因管线（P0 验证版）

下载工具：
- `python/download_cesm1le.py` + `run_p0_download.bat` — CESM1-LE（AWS zarr / GDEX，断点续传，走系统代理）
- `python/download_era5_tmax.py` — ERA5 日最高气温（CDS daily-statistics；需 CDS 凭据，已配置）
- `python/download_oaflux_evap.py` — OAFlux 蒸发（WHOI 多镜像自动降级）
- `scripts/translate_to_word.py` — 读取 `pdf_extract/` 图片生成中文翻译 Word（注意：其引用的图片文件名与当前 `pdf_extract/` 实际文件名不一致，需先核对）

## 目录结构（已建成；`data` 为 NTFS Junction → `E:\2607compound\data`）

```
D:\2607compound\        ← 工作区根目录（代码、文档、结果）
├── data/                # NTFS Junction → E:\2607compound\data（~430 GB 原始数据）
│   ├── OISST/
│   ├── E-OBS/
│   ├── ERA5/
│   ├── OAFlux/
│   └── CESM1-LE/
├── python/              # 数据处理代码
├── matlab/              # 绘图代码
├── results/             # 中间结果 + 图表
├── logs/
├── pdf_extract/         # 从 PDF 提取的图片
├── scripts/             # 工具脚本（如 translate_to_word.py）
└── docs/                # 文档
```

## 技术栈（全量）

- **Python ≥ 3.10**：xarray, numpy, scipy, matplotlib, cartopy, joblib, rpy2, marineHeatWaves
- **R ≥ 4.0**：heatwaveR (v0.4.6), ncdf4 — 通过 `Rscript` 调用
- **MATLAB ≥ R2020b**：全部绘图（依赖 Image Processing / Mapping Toolbox）
- **conda**：推荐环境管理

## 关键约束与陷阱

1. **数据依赖极重**：总数据量 ~430 GB，CESM1-LE 归因部分 ~200 GB 且计算密集（1000 bootstrap × 40 成员）。先跑 P0/P1 数据验证观测流程，再下载 CESM1-LE。
2. **路径硬编码**：`config.py` 中 `BASE_DIR = D:\2607compound`，`DATA_DIR = D:\2607compound\data`（NTFS Junction → `E:\2607compound\data`）；`translate_to_word.py` 使用工作区内的 `pdf_extract` 和 `results` 目录。已统一。
3. **混合语言调用**：陆地热浪检测必须走 R (`heatwaveR`)，通过 `subprocess.run(["Rscript", ...])` 调用，`detect_thw.R` 路径在 `python/detect_thw.R`。
4. **海洋-陆地网格对齐**：OISST 与 E-OBS 格点不对齐，需要重采样到统一网格后再做沿海配对。
5. **WBT 公式未定**：论文用的是 ERA5 提供变量还是手工公式尚未确认（`TECHNICAL_SPEC.md` 提供了两种实现）。
6. **无包管理/CI 配置**：没有 `requirements.txt`、`pyproject.toml`、`environment.yml`、`Makefile` 或 CI 工作流。环境需手动搭建。
7. **无测试框架**：项目无单元测试或集成测试，验证方式为与论文图表目视比对（锚点总表见 `results/复现报告.md` §4）+ `python/verify_data.py` 数据完整性检查。

## 快速参考

| 任务 | 命令/说明 |
|------|----------|
| 一键复现 Phase 1-3 | `python python\run_all.py`（检测已缓存 ~1 min；全量重检 ~22 min）|
| 出图 1/2/S1/S2 | `python python\figures.py` + `python python\fig_jkl_mhw_envelope.py` |
| 下 ERA5 tmax | `python python\download_era5_tmax.py`（`--merge` 合并） |
| 下 OAFlux | `python python\download_oaflux_evap.py` |
| 下 CESM1-LE | `run_p0_download.bat`（P0）/ `python python\download_cesm1le.py --members 20` |
| 检查数据完整性 | `python python\verify_data.py` |
| 环境搭建 | 见 §技术栈；关键包 xarray/cartopy/heatwaveR(R)/cdsapi |

## 权威文档

- `TECHNICAL_SPEC.md` — 详细代码规范、API 设计、算法说明（最权威）
- `DATA_REQUIREMENTS.md` — 数据下载步骤、目录结构、验证脚本
- `复现方案.md` — 论文基本信息、阶段规划、注意事项
