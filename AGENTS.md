# AGENTS.md — 论文复现项目

## 项目性质

学术复现项目，非典型软件仓库。目标：复现论文 *Compound coastal marine–terrestrial heatwaves associated with humid-heat stress in Europe*（Scientific Reports 2025）。

**当前进度（2026-09-23）**：Phase 1-4（观测链路：检测→配对→复合→图1/图2/S1/S2）完成；图1j-l 已切换为 MHW 包络口径（方案 B），共超标口径备份为 fig1_compound_spatial_exceedance_backup.*；**图1j/l 的绝对量级已定稿为"未复现项"**（定性一致、定量不可复现、原文口径不足以唯一确定——见 `results/复现报告.md` §6，停止口径搜索）；Phase 6 P0（CESM 3 成员管线 + v2 反事实基准）验证通过，全量未跑；Phase 5（湿热应力）与 Phase 7（写作）未开始。详见 `results/复现报告.md`。

**2026-09-23 第四批：Phase 6 归因管线正确性审计 + 修复（任务 D）**：Lead + 3 名独立审计员四路并行，逐项核验 `python/phase6_cesm.py`。**发现 2 个 P0 级检测层错误**——① `_pooled_threshold_t2m` 的 `axis` 崩溃使 206 个陆点共用一条全欧阈值曲线（阈值 mean\|Δ\| 8.26 °C）；② `_run_events` 是「先桥接后过滤」而 heatwaveR `proto_event` 是「先过滤后桥接」（450 例模糊测试 429/450 不一致）；另模型侧 MHW 阈值缺 11 天窗。**3 个 P0 级工程缺陷**：`--members 20` 静默只跑 3 个成员、阈值缓存无成员指纹、不支持 leave-one-out。已修复 8 项（F1–F8）并给出前后对比：THW 的 ALL/XGHG 事件比 1.73→3.01，`PR=48.0/FAR=0.98` **作废**（修复后该阈值下 P_fix=0），可判读阈值（20.7 天）下 PR=52.0/FAR=0.981。**观测链路（Phase 1–4）不受影响**（全部走 R heatwaveR）。详见 `results/phase6审计报告.md` + `results/phase6审计_修复前后对比.md` + 4 份分报告（`results/phase6审计_{网格与配对,检测语义,基准期,复合与统计}.md`）。

**2026-09-23 第三批：下载脚本就绪 + 图1j/l 定稿**：① Phase 5/6 下载脚本全部编辑就绪并 dry-run 验证（**均未运行**）——新增 `python/download_era5_sp025.py`（0.25° sp 欧洲框，数据集 3b+），给 `download_era5_tmax.py` 补 `--dry-run`，新增两个一键入口 `run_phase5_downloads.bat` / `run_phase6_download.bat`；② 图1j/l 定稿为未复现项（THW 硬约束 23.2/35.1/48.3 天 ⇒ 共超标口径封顶；MHW 包络对区域框高度敏感；8 区域框扫描无一口径满足论文四约束）；③ 修正 `diagnose_subbasin.py` 的归一化（`Σwi·d/n` → `Σwi·d/Σwi`），并据此**撤销**复现报告与修订报告中不可复算的"西地中海弧 76.0/68.5 唯一全面命中"结论。详见 `results/复现报告.md` §6 与 `results/S1读取与图6年份判据.md`。

**2026-09-23 规划文件一致性审查与修正**：对照论文 Methods/Results 全文审查全部规划文档，6 处实质性不一致已修正——① FAR 公式写反（SPEC §3.9 / PHASE_B，实际代码本正确）；② 归因统计单元改为"区域年暴露时间池化 440 模型年"（论文口径）；③ 新增 GEV 重现期规范（SPEC §3.9b + PHASE_B 步骤5；图4 marine/terrestrial/compound 三类，2.5–97.5% CI 与图3 的 5–95% 区分，config 新增 `GEV_RETURN_PERIODS`/`GEV_CI`）；④ `DATA_REQUIREMENTS` 立项 ERA5 sp 0.25° 欧洲框下载任务（数据集 3b+，现 sp 为 1.0° 偏差）；⑤ PHASE_A 图1 面板年份/区域、PHASE_C 蒸发/SST 验证锚点按论文更正；⑥ `docs/复现方案.md` 全面同步（E-OBS 1983–2023、复合定义方案 B、MHW 工具 R heatwaveR、XGHG=GHG 固定已实证 co2vmr 恒定 303 ppm）。详见 `results/规划文件与论文一致性审查.md`。

**2026-09-23 第二轮独立复核**：对第一轮结论做独立重核，发现第一轮有 3 处错误/过度声明（其中「100 km 海岸缓冲已在 config」实为**未实现**）、并遗漏 **5 项与论文实质不符**（陆地检测变量 tg vs tx 未论证、图6c 缺 JJA 季节与 22–28 °C 范围、图6 非复合年选取判据未定义、模型侧检测基准期在规划中缺失、论文 Supplementary Fig. S1 未复现）。随后执行"零风险批次"清理：过期文件名/盘符/CESM 命名、SPEC §5.2–5.4 图1/图2 面板、§3.13 run_all（原误编为 §3.11）、§3.8 WBT 迭代实现、三份 PHASE 文档的 MATLAB 残留、AGENTS.md 检测链路口径统一。**方法学新增项（100 km 缓冲、CESM 基准期、图6c 规格等）待用户拍板后再改。** 详见 `results/规划文件与论文一致性审查_第二轮复核.md`。

## 当前可运行文件

主链路（Phase 1-4，已验证）：
- `python/run_all.py` — Phase 0–3 四阶段主控（预处理→检测→复合→年度指标/CHR/共现概率）
- `python/figures.py` — 图1/图2/S1 出图；`python/fig_jkl_mhw_envelope.py` — S2
- `python/detect_events.R` — **海陆统一热浪检测正式链路**（R heatwaveR）
- `python/phase6_cesm.py` — Phase 6 归因管线（P0 验证版；**2026-09-23 审计修复 F1–F8**：
  检测端与 R heatwaveR 等价、阈值逐点、缓存带指纹、`--members` 作用于全量 20 人名单、新增 `--loo`）
- `python/coastal_buffer.py` — 图6 分析域：海岸向内 100 km 缓冲掩码（Phase 5 前置，已实现待接入）

⚠️ **检测链路口径提示**：`python/detect_thw.R` 有吞错 bug，**仅存档勿用**；
但 `python/run_all.py` 的 THW 环节当前仍经 `detect_thw_wrapper` 指向它（缓存命中时不会重跑）。
正式重检请直接调用 `detect_events.R`。另：全链路 `smoothPercentile=FALSE`，
偏离两包默认（TRUE/31 天窗），理由见 `results/复现报告.md` D2。

下载工具：
- `python/download_cesm1le.py` + `run_p0_download.bat`（P0 3 成员）/ `run_phase6_download.bat`（全量 20 成员）
  — CESM1-LE（AWS zarr / GDEX，断点续传，走系统代理）
- `python/download_era5_tmax.py` — ERA5 日最高气温（CDS daily-statistics；支持 `--dry-run`）
- `python/download_era5_sp025.py` — ERA5 **0.25°** 地表气压欧洲框（数据集 3b+；支持 `--dry-run`）
- `python/download_oaflux_evap.py` — OAFlux 蒸发（WHOI 多镜像自动降级）
- `run_phase5_downloads.bat` — 一键跑 tmax + sp 0.25° + OAFlux（Phase 5 的全部输入）
- `scripts/translate_to_word.py` — 读取 `pdf_extract/` 图片生成中文翻译 Word（注意：其引用的图片文件名与当前 `pdf_extract/` 实际文件名不一致，需先核对）

> 下载脚本 2026-09-23 已全部就绪并 dry-run 验证通过（**尚未运行**）：
> tmax 待下 479 个月、sp 0.25° 待下 480 个月、OAFlux 待下、CESM 待下 17 个成员。
> 建议先跑 Phase 5 那三项（几小时），同时后台启动 CESM 全量（4–5 天）。

## 目录结构（已建成；`data` 为 NTFS Junction → `E:\2607compound\data`）

```
D:\2607compound\        ← 工作区根目录（代码、文档、结果）
├── data/                # NTFS Junction → E:\2607compound\data（原始数据 ~210 GB）
│   ├── OISST/           # 全球合并件 23.1 GB + 欧洲裁剪件 1.1 GB
│   ├── E-OBS/           # 合并件 0.5 GB（14975 天）+ 3 个分段原始
│   ├── ERA5/            # d2m（0.25°，按月×573）、sp（1.0°，按年×46）、tmax（0.25°，待下载）
│   ├── OAFlux/          # 空，待下载
│   └── CESM1-LE/        # raw/ + proc/（当前成员 001–003）
├── python/              # 全部处理 + 绘图代码
├── results/             # intermediate/ + figures/ + tables/ + 报告
│   ├── 复现报告.md
│   ├── 规划文件与论文一致性审查.md
│   └── 规划文件与论文一致性审查_第二轮复核.md
├── docs/                # 主论文/补充材料 PDF、复现方案.md
├── logs/                # 文档备份
├── pdf_extract/         # 从 PDF 提取的图片
└── scripts/             # 工具脚本（如 translate_to_word.py）
```

> 注：`matlab/` 目录**不存在**——绘图已全面切换 Python (matplotlib + cartopy)，
> 三份 PHASE 文档中的 MATLAB 段落均标注为"已弃用，仅作对照"。

## 技术栈（全量）

- **Python ≥ 3.10**：xarray, numpy, scipy, matplotlib, cartopy, joblib, pandas（`marineHeatWaves` 仅作单格点核验，DEPRECATED）
- **R ≥ 4.0**：heatwaveR (**本机 v0.5.5**；论文标注 v0.4.6，两版语义已核验一致), ncdf4, doParallel, foreach — 通过 `Rscript` 调用（**不用 rpy2**）
- **conda**：推荐环境管理

## 关键约束与陷阱

1. **数据依赖极重**：已下载 ~210 GB（OISST 24 GB + E-OBS 0.5 GB + ERA5 45 GB + CESM1-LE 123 GB）。
   真正的计算瓶颈是 **40 个 CESM 模拟的逐格点热浪检测**（P0 实测 27 s/成员）；
   归因 bootstrap 本身很轻（样本是池化后的 440 个模型年标量）。先跑 P0 数据验证观测流程，再下载 CESM1-LE 全量。
2. **路径硬编码**：`config.py` 中 `BASE_DIR = D:\2607compound`，`DATA_DIR = D:\2607compound\data`（NTFS Junction → `E:\2607compound\data`）；`translate_to_word.py` 使用工作区内的 `pdf_extract` 和 `results` 目录。已统一。
3. **混合语言调用**：陆地/海洋热浪检测统一走 R，经 `subprocess.run([RSCRIPT_PATH, ...])` 调用
   `python/detect_events.R`（正式链路）；`RSCRIPT_PATH` 与 `DETECT_THW_R_SCRIPT` 定义在 `config.py`。
4. **海洋-陆地网格对齐**：OISST 与 E-OBS 格点不对齐。**不重采样**——用 KDTree 最近邻配对
   （`MAX_GRID_DIST_DEG = 0.5°`，实测 2039 对 / 1434 唯一海点），下游全部按配对索引匹配。
   **CESM 侧另有一套**：POP gx1v6 → f09（实测 0.9424°×1.25°）KMT 湿点映射 + 4-连通海岸边缘 +
   KDTree cos 加权，上限 `MAX_PAIR_DIST_DEG = 1.0` 单位 ≈ **112.2 km**（观测侧 0.5 单位 ≈ 55.6 km，
   **模型侧允许分离约为观测侧 2.1×**），实测 **206 对 / 唯一陆点 206 / 唯一海点 191**。
   `python/phase6_cesm.py` 的 `cmd_pairs`。
5. **WBT 计算输入已确认**：论文明确由 ERA5 的 **Tmax + 露点 + 地表气压**估算**日最高 WBT**；
   具体近似式未给，`TECHNICAL_SPEC.md` §3.8 提供 Stull / 牛顿迭代双实现待定稿。
   **图6 的 100 km 海岸缓冲已实现**：`python/coastal_buffer.py` + `config.COASTAL_BUFFER_KM`
   （实测 1952/4492 格点落入缓冲区；区域口径待确认，见 PHASE_C 步骤 8）。
6. **无包管理/CI 配置**：没有 `requirements.txt`、`pyproject.toml`、`environment.yml`、`Makefile` 或 CI 工作流。环境需手动搭建。
7. **无测试框架**：项目无单元测试或集成测试，验证方式为与论文图表目视比对（锚点总表见 `results/复现报告.md` §4）+ `python/verify_data.py` 数据完整性检查。

## 快速参考

| 任务 | 命令/说明 |
|------|----------|
| 一键复现 Phase 0-3 | `python python\run_all.py`（缓存命中 ~1 min；全量重检陆地 ~22 min）|
| 出图 1/2/S1/S2 | `python python\figures.py` + `python python\fig_jkl_mhw_envelope.py` |
| **下 Phase 5 全部输入** | `run_phase5_downloads.bat`（= ERA5 tmax + ERA5 sp 0.25° + OAFlux） |
| **下 CESM 全量** | `run_phase6_download.bat`（20 成员，~750 GB，4–5 天） |
| 下 ERA5 tmax | `python python\download_era5_tmax.py [--dry-run]`（`--merge` 合并） |
| 下 ERA5 sp 0.25° | `python python\download_era5_sp025.py [--dry-run]`（数据集 3b+） |
| 下 OAFlux | `python python\download_oaflux_evap.py [--probe]` |
| 下 CESM1-LE | `run_p0_download.bat`（P0 3 成员）/ `python python\download_cesm1le.py aws\|gdex --members 20` |
| Phase 6 归因（全量，口径已定） | `pairs` → `prepare --members 20` → `detect --members 20 --baseline xghg --loo --tag _v4` → `compound --members 20 --tag _v4 --compound-def envelope` → `attrib --members 20 --tag _v4 --compound-def envelope` |
| Phase 6 口径决策 | 复合=**MHW 包络**(D7.1)；归因=**阈值扫描+62/78/72 参考线**(D7.2)；主口径 **med_mean**(D7.3)；基准期 **XGHG+LOO**(D7.4)；bootstrap **indep**(D7.5) —— 见 `results/复现报告.md` §5 D7 |
| Phase 6 逻辑自检（不读数据） | `python results\phase6_selftest.py` → `ALL SELFTESTS PASSED` |
| 检查数据完整性 | `python python\verify_data.py` |
| 环境搭建 | 见 §技术栈；关键包 xarray/cartopy/heatwaveR(R)/cdsapi |

## 权威文档

- `TECHNICAL_SPEC.md` — 详细代码规范、API 设计、算法说明（最权威）
- `TECHNICAL_SPEC_PHASE_A/B/C.md` — 阶段 A（观测，图1–2）／B（归因，图3–4）／C（湿热，图5–6）；
  MATLAB 段落均为"已弃用，仅作对照"
- `DATA_REQUIREMENTS.md` — 数据下载步骤、目录结构、验证脚本、优先级
- `docs/复现方案.md` — 论文基本信息、阶段规划、注意事项
- `results/复现报告.md` — 进度、锚点验证总表、方法学决策记录（D1–D6）、偏差清单 §5.1
- `results/规划文件与论文一致性审查.md` — 第一轮审查（2026-09-23）
- `results/规划文件与论文一致性审查_第二轮复核.md` — 第二轮独立复核（2026-09-23），
  含第一轮的错误更正与 5 项方法学问题的处置（**Phase 5/6 开工前必须先读**）
- `results/S1读取与图6年份判据.md` — 读取论文 Supplementary Fig. S1：图6 非复合年判据（D）
  + 图1j/l 缺口的量化定位（**读 §五 的定稿结论即可**）
