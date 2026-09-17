# AGENTS.md — 论文复现项目

## 项目性质

学术复现项目，非典型软件仓库。目标：复现论文 *Compound coastal marine–terrestrial heatwaves associated with humid-heat stress in Europe*（Scientific Reports 2025）。代码尚未写完，当前仅有文档和一个 Word 生成脚本。

## 当前可运行文件

- `translate_to_word.py` — 唯一可执行的 Python 脚本，读取 `D:\work\2607\extracted_images\` 下的图片，生成中文翻译 Word 文档。依赖 `python-docx`。**Windows 硬编码路径**：`IMG_DIR = r"D:\work\2607\extracted_images"`，`OUT_DIR = r"D:\work\2607"`。

## 计划目录结构（尚未全部创建）

```
F:\2607compound\        ← 数据根目录（硬编码在 config.py 中）
├── data/                # ~430 GB 原始数据
│   ├── OISST/
│   ├── E-OBS/
│   ├── ERA5/
│   ├── OAFlux/
│   └── CESM1-LE/        # ~400 GB，ALL + FixGHG 各 20 成员
├── python/              # 数据处理代码（尚未创建）
├── matlab/              # 绘图代码（尚未创建）
├── results/             # 中间结果 + 图表
└── logs/
```

## 技术栈（全量）

- **Python ≥ 3.10**：xarray, numpy, scipy, matplotlib, cartopy, joblib, rpy2, marineHeatWaves
- **R ≥ 4.0**：heatwaveR (v0.4.6), ncdf4 — 通过 `Rscript` 调用
- **MATLAB ≥ R2020b**：全部绘图（依赖 Image Processing / Mapping Toolbox）
- **conda**：推荐环境管理

## 关键约束与陷阱

1. **数据依赖极重**：总数据量 ~430 GB，CESM1-LE 归因部分 ~200 GB 且计算密集（1000 bootstrap × 40 成员）。先跑 P0/P1 数据验证观测流程，再下载 CESM1-LE。
2. **路径硬编码**：计划中所有 Python 代码使用 `F:\2607compound` 作为 `BASE_DIR`；当前 `translate_to_word.py` 使用 `D:\work\2607`。迁移时需统一。
3. **混合语言调用**：陆地热浪检测必须走 R (`heatwaveR`)，通过 `subprocess.run(["Rscript", ...])` 调用，`detect_thw.R` 路径在 `python/detect_thw.R`。
4. **海洋-陆地网格对齐**：OISST 与 E-OBS 格点不对齐，需要重采样到统一网格后再做沿海配对。
5. **WBT 公式未定**：论文用的是 ERA5 提供变量还是手工公式尚未确认（`TECHNICAL_SPEC.md` 提供了两种实现）。
6. **无包管理/CI 配置**：没有 `requirements.txt`、`pyproject.toml`、`environment.yml`、`Makefile` 或 CI 工作流。环境需手动搭建。
7. **无测试框架**：项目无单元测试或集成测试，验证方式为与论文图表目视比对 + `verify_data.py` 数据完整性检查（脚本内嵌于 `DATA_REQUIREMENTS.md`，未独立成文件）。

## 快速参考

| 任务 | 命令/说明 |
|------|----------|
| 生成 Word 翻译文档 | `python translate_to_word.py`（需 `extracted_images/` 就位）|
| 检查数据完整性 | 复制 `DATA_REQUIREMENTS.md` 中 `verify_data.py` 代码后运行 |
| 环境搭建 | conda 创建 env，手动 `pip install` 列出的依赖 |

## 权威文档

- `TECHNICAL_SPEC.md` — 详细代码规范、API 设计、算法说明（最权威）
- `DATA_REQUIREMENTS.md` — 数据下载步骤、目录结构、验证脚本
- `复现方案.md` — 论文基本信息、阶段规划、注意事项
