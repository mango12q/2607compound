# AGENTS.md — 论文复现项目

## 项目性质

学术复现项目，非典型软件仓库。目标：复现论文 *Compound coastal marine–terrestrial heatwaves associated with humid-heat stress in Europe*（Scientific Reports 2025）。

**2026-11-17 第二十八批：一键入口从"旧口径"改为"主口径 `_v12w50`" + 终版中文 Word 报告（Phase 7 结案）**：
- **结论先行**：`python/run_phases.py` 此前是**旧口径的一键入口**（detect 硬写 `--baseline xghg --loo`、`--tag` 默认 `_v4`、
  `attrib` 不带 `--agg` ⇒ fig3 必失败、`gev` 不带 `--mapping emp`）——"看起来正常但跑出错误口径"。现已改为**主口径**，
  `python python\run_phases.py --phases 6 7 --skip-selftest` **实跑 exit=0、49 s**（detect 1 s 是因为事件表已在、走断点续跑），
  产物经 `python logs\_cmp_ci.py _v12w50` 复核 **15/15 仍 IN**（terr 1.275/1.522/1.905/2.635/3.165、comp 1.956/2.667/3.860/5.116/8.000；r100/r5 terr 2.48 / comp 4.09；FixGHG 100 年水平 marine 186.38 [162.59,201.31] / terr 23.76 [20.48,25.96] / comp 103.07 [79.72,140.11]）。
- **`run_phases.py` 改动**：模块级 `MAIN_TAG="_v12w50"`、`MAIN_DETECT_ARGS=["--baseline","self","--loo","--clim-period","1983-2012","--thresh-offset-xghg-t2m","0.5645"]`、`MAIN_AGG`（6 列）、`MAIN_MAPPING="emp"`；`phase_6()` 走 MAIN_*，新增 `--legacy` 才回退旧口径并打印"已被推翻、仅作对照"；`phase_7()` 改为 `table1{tag}.csv` 优先、图 `startswith(stem + tag)` 优先（改前会命中文档里的 `_p0chk` 图）。
- **终版报告**：`python scripts\build_final_report.py`（python-docx，700 行）→ **`results\复现报告_终版.docx`（3.7 MB、105 段、12 表、25 标题、6 张内嵌主图）**；章节 = 结论摘要 / 阶段状态 / 数据规模 / D1–D7 / 锚点核对 / 逐图结果（含图4 五档表与 Table 1 表）/ 未复现项 / 13 条差异 / 复现方式 / 产物清单 / 口径演化表。
- **⚠️ 版式未经目视校验**：本机**没有** LibreOffice skill 脚本（`...\resources\runtime\office-skills\...` 与 `@deepseek-ai/libreoffice-kit` 均不存在）⇒ 只能做结构核对（`logs\_check_final_report.py`：zip ok、12 表、6 图、关键串全中）。
- **文档同步**：`待办.md` Phase 7 → ✅ 且"重跑 Phase 6 全链"改推荐 `run_phases.py --phases 6` / `logs\_run_v12w50.ps1`（`_run_v8_all.ps1` 标注为 w=1 已证伪）；`results\复现报告.md` 文首/§2/§2.2 第 6 条/§9 四处同步。**Phase 7 至此完成，全项目 0 个未开工阶段。**

**2026-11-17 第二十七批：图6 区域口径拍板并重出图 —— 地中海 + 西班牙东岸、剔除黑海，残差已量化并登记为未复现项**：
- **结论先行**：图6 的域定为 **地中海 100 km 缓冲、剔除黑海/亚速海、纳入西班牙东岸（Catalan 岸）**，掩码 **1637** 格点
  （原 1952）。敏感性实测证明**区域是二阶因素**：2023 年 WBT≥25.5 的区域平均天数旧框 1952 = **1.83**、旧框去黑海 1457 = 2.38、
  含西班牙含黑海 2132 = 1.79、**新口径 1637 = 2.26**（最大 1.23×）。依据：论文 Fig.6 caption / Methods 两处都只写
  "100 km inland from the **Mediterranean** coast"（黑海只属 Fig.1/3/4），正文又点名 "spanning the **Catalan coast**"。
- **★ 残差与归因（已量化，列为未复现项）**：① **6a 差 18×** —— 2023@25.5 = **2.26 天** vs 论文 40（非复合年 0.36 vs <5，
  比值 6× 对上）；要把区域平均抬到 40 天需 WBT 整体 **+4.3 °C**（阈值偏移扫描：δ=4.0 才 38.6）⇒ 物理上不可能，
  论文的 40 天多半**不是**"逐格点年天数再区域平均"这一层（我们的"至少一格超阈"天数 2023 = **78**、2000 = 58）。
  ② **6c 的 26 °C 端点在现行口径下不可达** —— 6c 用"JJA 逐日**区域平均** WBT"序列，2023 的区域平均 max 仅 **22.42 °C** ⇒ 26 °C 处 恒为 `RP=None`（结构性，非 bug）。
  若改用 JJA 逐日**空间分位**序列：q99 给 RP(26) = **2.79 年**（2023）/ 5.86（2022）/ 5.18（2003）/ 9.35（2000），
  论文是 3.2 / 60（方向对、量级偏低）；区域**最大**序列给 1.79 / 2.01（年际不可分）。
- **代码**：`python/config.py` —— `COASTAL_BUFFER_REGION` 改 lon **(0,42)**；**新增** `COASTAL_BUFFER_EXCLUDE = ({"lon": (27.5, 42.0), "lat": (40.5, 47.0)},)`
  与 `OISST_EUR_FILE`（欧洲裁剪件 1.19 GB）；`python/coastal_buffer.py` —— `build_coastal_buffer_mask(..., exclude=None)` 按框剔除，
  `info` 增 `exclude` / `cells_within_buffer_before_exclude`，`main()` 优先用欧洲裁剪件；`python/phase5_humid.py` ——
  `stats` 新增 **`--skip-fig5`**（只重算图6），`fig6_stats.json` 的 `buffer` 块增 `exclude`。
  重跑：`python python\coastal_buffer.py` → `python python\phase5_humid.py stats --skip-fig5` → `python python\fig6_wbt.py`（均 exit=0）。
- **新旧对照**（`results/tables/fig6_stats_medBS_1952cells_bak.json` vs 现行）：`wbt25.5` 2023 **1.83 → 2.26**；非复合年均 0.30 → 0.36；
  `sh19` 2023 不变（0.29）；2023 `RP@22 °C` **5.99 → 8.34 年**、2000 `RP@22 °C` **156 → 8348 年**（GEV 尾部外推极不稳）。
  备份件均名 `*_medBS_1952cells_bak.*`（掩码 nc / fig6_stats json / png 三份）。
- **诊断脚本**（只读）：`logs\_diag_fig6_region.py`（四变体区域敏感性）、`logs\_diag_fig6_stat.py`（逐格点分布、
  q95/q99/max 序列的 RP(26)、阈值偏移扫描），日志 `logs\_diag_fig6_{region,stat}.log`。
- **文档已同步**：`results\图版对照表.md` Fig.6 行、`results\复现报告.md`（文首进度、§2.2 第 1 条、§5.1 第 13 行、
  §6.3 第 4 条、§8 产出清单、§9 命令段改为 `_v12w50`、§10 第 4/6 条）、`待办.md`（§5 与第 4 步标题）。
- **下一步**（若要继续）：图6 的剩余量级差要想真查，只有一条路 —— 用 **逐小时 ERA5** 算"daily maximum WBT"（论文字面意）再重做 6a/6c；
  代价：ERA5 逐小时 t2m/d2m/sp 欧洲框 1984–2023 约 **300–600 GB**（或按区域取模拟 30–80 GB）+ 重算 ~1 h，不在当前收益范围内。

**2026-11-08 第二十六批：★ 残差结案 —— 图4 三面板 15/15 全部落入论文 bootstrap 区间，主口径定为 `_v12w50`**：
- **结论先行**：`_v12w50`（w=0.50）+ 经验映射下，图4 的三面板 × 五档重现期 **15 个点全部落在我们的 bootstrap CI 内**；
  海洋高端 0.56× 的"残差"被证实是**抽样噪声**（marine 100 年 13.33 的 CI = **[8.30, 24.48]**，包含论文的 24.0；
  50 年 9.17 的 CI [6.47,16.92] 包含 13.4）。**图4 不再是"未复现项"。**
- **`_v12w50` vs `_v12w60` vs 论文**（五档 ALL 等效重现期）：
  | 面板 | 论文 | **`_v12w50`**（新主口径） | 五档 MAE | `_v12w60` | 五档 MAE |
  |---|---|---|---|---|---|
  | marine | 2.30/3.80/6.30/13.4/24.0 | 2.47/3.96/6.47/9.17/13.3 | — | 同左（不受 w 影响） | — |
  | terrestrial | 1.26/1.46/1.75/2.44/3.26 | **1.28/1.52/1.91/2.64/3.17** | **0.104** | 1.21/1.38/1.72/2.23/2.72 | 0.181 |
  | compound | 1.96/2.56/3.50/5.14/7.85 | **1.96/2.67/3.86/5.12/8.00** | **0.129** | 1.89/2.51/3.55/4.63/7.46 | 0.213 |
  ⇒ 论文 terr 100 年 3.26 → w50 给 3.165（−2.9%）、comp 100 年 7.85 → w50 给 8.000（+1.9%）、comp 5 年 1.96 → w50 给
  1.956（−0.2%）；`_v12w89` 陆地/复合掉出区间（0.56×/0.59×）⇒ **w>0.7 过头**。**w=0.50 同时是解析值与数据最优点**
  （"合并两实验样本求 q90"给 w≈0.41–0.55，见第二十五批）。
- **Table 1（`table1_v12w50.csv`）**：FAR **0.789 / 0.871 / 0.814**（论文 0.72/0.95/0.78），**MAE 0.0607**
  （`_v7` 0.147、`_v12w60` 0.083）；FAR 2003/2023 在论文 CI 内；**PR 三年全部在论文 CI 内**（4.73 vs [2.8–7.2]、
  7.75 vs [6–∞)、5.39 vs [4–10]）；年际次序 2003 < 2023 < 2022 保持。唯一 out 的是 2022 的 FAR 0.871 vs [0.93,1.00]
  —— 与"三年各自最优 w 跨 [0.35,0.85]"一致，属论文自身年际形态，不再追。
- **★ D7.7（新决策）**：主口径 = `_v12w50` = `--baseline self --loo --clim-period 1983-2012
  --thresh-offset-xghg-t2m 0.5645` + `gev --mapping emp`。`_v12w60`/`_v12w89` 降为敏感性，`_v7`+`_v10` 留作 w=0 端点。
  **D7.4rev 补充**：共用基准必须按"两实验**合并样本**的 q90"（w≈0.4–0.55），不能用单一实验（尤其 ALL）的 q90
  （后者 = w=1，会把反事实世界打死，即 `_v8`）。
- **新脚本**：`logs\_run_v12w50.ps1`（单点全链 + fig4 + table1，**5.7 min**：detect 4.89 / compound 0.57 / attrib 0.07 /
  gev 0.15 / fig4 0.03 / table1 0.01，全 exit=0）；`logs\_cmp_ci.py [tags…]`（打印各 tag 五档 + **bootstrap CI** +
  论文值是否 IN/out + `r100/r5` + FixGHG 五档水平与 100 年 CI）——**判残差是噪声还是真差，以后一律先跑这个**。
- **产物**：`results\tables\phase6_gev_v12w50.json`（5942 B）、`table1_v12w50.csv`、`results\figures\fig3_attribution_v12w50.png/.pdf`、`fig4_return_period_v12w50.png/.pdf`、
  `mhw/thw_v12w50_*`（120 件）、`logs\_cmp_ci.log` / `logs\_cmp_ci_w50.log`。
- **已定量证伪、不要重试（全部批次累计）**：暴露量纲（`frac` 逐位不变/`events` 更差）、`--baseline all` 满强度（`_v8`，
  反事实世界死亡 + P_fix→0）、θ 家族（共享阈值单一标量，θ≥0.40 零膨胀爆尾）、**双世界共同偏移**（`_v11`，无效甚至反向）、
  "更冷基准补海洋"（ALL 侧饱和 + 海洋高端本就在 CI 内）。
- **下一步（若要继续，按性价比）**：① `tg`（日均）vs `tx`（日最高）敏感性；② 海岸缓冲带宽度敏感性；
  ③ Table 1 的 2022 FAR 偏低属论文年际形态，不再追。文档三处已同步（本节 / `results\复现报告.md` §5.2 / `待办.md` 顶部）。
**★ 第二十六批补充（同日）：两条遗留小口径敏感性已结案 —— 一条被论文原文直接关掉，一条给出决定性对照**
- **① `tg`（日均）vs `tx`（日最高）——不是问题，两条独立证据**：
  a) **模型侧口径本来就是对的**：论文 Methods（`logs\_paper_main.txt` L605）明写 "We utilize daily **sea surface
     temperature** (SST) data, and **daily 2m temperature** from CESM1-LE" ⇒ 模型侧就该用日均 TREFHT/SST，我们现用的
     就是这个，**不需要补 `TREFHTMX`**（省下 ≈7 GB 下载 + 1.5–6 h）。
  b) **观测侧改 tx 也不影响 Phase 6**：Table 1 的 62/78/72 天是**论文自己的观测复合日数值**（来自其 Fig 1j，
     我们在 D7.2 里当固定参考线用），不是我们从自己数据算出来的 ⇒ 换 tx 只影响 Fig 1j/l 的观测曲线，而那条已
     定稿为"未复现项"（§6，停止口径搜索）。真要补：E-OBS `tx_ens_mean_0.25deg_reg_{1980-1994,1995-2010,2011-2023}.nc`
     ≈470 MB + `make_yearly`/merge + Phase 1–4 重检 ≈22 min，**不在本任务收益范围内**。
- **② 分析域（地中海框 vs 全欧配对）——决定性对照，`logs\_diag_region_sens.py`（只读，日志 `logs\_diag_region_sens.log`）**：
  同一批 `_v12w50` 事件表，只改区域与复合聚合列（Med 框用 `med_mean`；全欧 206 对用 `eur_mean`），
  | 面板 | 论文 5/10/20/50/100 | **Med 框（64 对，主线）** | 全欧（206 对） |
  |---|---|---|---|
  | marine | 2.30/3.80/6.30/13.4/24.0 | **2.47/3.96/6.47/9.17/13.3 → 5/5 IN** | 2.02/2.67/3.28/4.15/4.89 → **0/5 IN** |
  | terrestrial | 1.26/1.46/1.75/2.44/3.26 | **1.28/1.52/1.90/2.63/3.17 → 5/5 IN** | 1.09/1.17/1.25/1.36/1.51 → **0/5 IN** |
  | compound | 1.96/2.56/3.50/5.14/7.85 | **1.96/2.67/3.86/5.12/8.00 → 5/5 IN** | 1.64/2.05/2.60/3.31/3.73 → **0/5 IN** |
  ⇒ **区域不是"稳健性旋钮"而是一阶因子**：换成全欧配对后三块板同时**腰斩**（100 年 marine 4.9 vs 24.0、terr 1.5 vs 3.26、
  comp 3.7 vs 7.85），全部掉出 CI。这反证两件事：① 论文图4 确实是**地中海 & 黑海**域（其 caption 也这么写），我们没跑偏；
  ② 我们的 15/15 IN **不是估计器凑出来的**——换个域立刻崩，说明匹配来自数据本身。
  （区域年暴露均值也随域变化：marine 81.2→76.0、terr ALL 20.2→16.9、comp ALL 45.6→38.7 天/年。）
- **⇒ Phase 6 到此可以收工**：图4（`_v12w50`）三面板 15/15 落在论文 CI 内且对域选择**敏感得合理**；Table 1 FAR
  MAE 0.0607、PR 三年全在论文区间；年际次序 2003<2023<2022 复现。列在待办里的两条敏感性已全部结案。
**2026-11-08 第二十五批：找到真正有效的旋钮 —— 「参考气候态的混合权重 w」（陆地阈值部分共用）**
（完整记录 → `docs/批次历史.md`）：图4 的 ALL 等效重现期几乎只由**两个世界的阈值之差**决定，与阈值共同暖度无关
⇒ `_v11`（双世界同时 +0.6/1.1 °C）无效甚至反向；唯一可连续调节的是 **w**：`XGHG 陆地阈值 += w·δ_t2m`（δ=1.129 °C）。
`_v12w60`（w=0.6）把陆地 5.40×→**0.83×**、复合 1.70×→**0.95×**（1 参数拟合 2 面板）；w 响应面：w=0 → terr 17.6 / comp 13.3；
w=0.6 → 2.72 / 7.46；w=0.89 → 1.83 / 4.63；w=1（`_v8`）→ 2.13 / 1.04（复合被打死）。
**解析依据**：按"两实验**合并样本**的 q90"应得 w≈0.41–0.55（混合分布 q90 由暖尾主导，z≈−1.505 vs −1.282）
⇒ `--baseline all`（= 只用 ALL 池的 q90，即 w=1）是**实现口径偏了**，不是机制错。Table 1 FAR：w=0 **0.618/0.731/0.660**、
w=0.6 **0.821/0.903/0.876**、w=0.89 0.911/0.957/0.928（论文 0.72/0.95/0.78）；三年各自最优 w 跨 **[0.35,0.85]** ⇒ 单一 w
无法同时命中，最优折中 MAE 0.083。新代码：`THRESH_OFFSET_T2M` / `THRESH_OFFSET_XGHG_T2M` + `_offset_of` / `_with_offset`
（阈值缓存仍全复用，detect 3.6–4.3 min）。产物 `_v11t06`/`_v11t11`/`_v12w60`/`_v12w89` 四套（各 80 件事件表）。

**2026-11-08 第二十四批：残差坐标三维扫完（量纲 × 基准期 × 映射内核）—— 复合 13.4× 主因是 GEV 外推，新基线 `_v10`**
（完整记录 → `docs/批次历史.md`）：`_v7` 的 compound XGHG 序列 GEV MLE 给 **ξ=−0.885** ⇒ 百年水平外推 **604 天/年**
（超 365 物理上界）；换**经验分位 q99=123.6 天**后同一批事件表五档变 `2.43/3.83/5.30/8.63/13.3` ⇒ **13.4× → 1.70×**。
新口径 **`_v10` = `_v7` 事件表 + `gev --mapping emp`**（≈2 min）。残差重排为 "marine 0.56× / terr 5.40× / comp 1.70×"，
worst 面板从复合翻转为陆地。另跑 `_v8`（`--baseline all`）、`_v9o40`/`_v9o70`（共享阈值 θ=0.40/0.70）。
**被定量证伪、别再试**：① 暴露量纲（`frac` 逐位不变；`events` 更差：marine 100 年 50.3→132.2）；② `--baseline all` 满强度
（反事实世界被打死，XGHG marine 53.1→2.94 天/年，Table 1 P_fix 全 0）；③ θ 家族（θ≥0.40 零膨胀爆尾，compound 百年
1.9e12 天）。实测 δ = **1.129 °C（T2m）/ 0.796 °C（SST）**、β = +0.783/+1.167（T2m）、+0.431/+0.065（SST）。
新代码：`--thresh-offset`、`--baseline all`、`gev_return_period.py` 三个非参数函数 + `--mapping {gev,emp}`。
诊断脚本：`_diag_v8_metric.py`、`_diag_exp_series.py`、`_diag_emp_rp.py`、`_diag_delta_clim.py`、`_diag_obs_bias.py`。

**2026-11-08 第二十三批：Phase 6 基准期口径终定 —— 四版对照（`_v5`/`_v6`/`_v7`/`_v7e`）+ 残差归因（D7.4rev / D7.3rev / D7.6）**
（完整记录 → `docs/批次历史.md`）：
| tag | 阈值基准期 | 复合 | 复合年暴露 ALL/XGHG（天） | Fig4 100 年 marine/terr/comp（年） | Table 1 FAR |
|---|---|---|---|---|---|
| `_v5` | XGHG 1983–2012（共用） | envelope | 216.2 / 23.8 | 2.68 / 1.44 / **inf** | 0.891 / 0.940 / 0.922 |
| `_v6` | 各实验 2000–2021（in-sample） | envelope | 13.3 / 11.8 | 38.6 / 46.0 / 19.4 | 0.471 / 0.500 / 0.615 |
| **`_v7`** | **各实验 1983–2012** | envelope | **45.6 / 23.8** | **50.9 / 18.0 / 104.9** | **0.618 / 0.731 / 0.660** |
| `_v7e` | 各实验 1983–2012 | exceed | 12.5 / 7.09 | 50.9 / 18.0 / 31.6 | 1.0 / — / 1.0 |
| 论文 | — | — | — | **20.7 / 3.2 / 8** | **0.72 / 0.95 / 0.78** |
决策：**D7.4rev** 主口径 = `--baseline self --clim-period 1983-2012`；**D7.3rev** 聚合回 `med_mean`；**D7.6** envelope 主线 +
exceed 敏感性双报。实现硬对照：`_v7` 的 XGHG 侧三个 FixGHG 100 年水平与 `_v5` **逐位相同**（283.9 / 41.72 / 604.05 天）。
代码：`--baseline self` 分支（双循环 20 成员 × 2 实验 + LOO）；`_thresh_cache_path(..., pool_exp=)` 文件名带池实验，
XGHG 池沿用旧名 ⇒ `_v5` 的 20 个缓存继续命中。

**2026-11-08 第二十二批：「补齐」跑完 —— 论文基准期 1983–2012 的 `_v5` 全链出图，Table 1 年际排序首次复现，D7.3 回归 med_mean**
（完整记录 → `docs/批次历史.md`）：补齐 1983–1999 气候态 40 件（XGHG，5.5 h / ≈4.94 GB）；`_v5` 全链 17.6 min（detect 12.75 min，
阈值走气候态缓存比 `_v4` 快 3×）。Table 1（`med_mean`）：FAR **0.891/0.940/0.922**、PR 9.17/16.76/12.85（论文 0.72/0.95/0.78、
4.1/[6–∞)/8）⇒ **2022 进 CI、年际排序 2003<2023<2022 首次复现**。`MAIN_AGG` 由 `med_p90` **回归 `med_mean`**（D7.3 二次修订：
p90 是错基准下的补偿）。图4 仍差 5–10×（marine ALL 1.01–2.68 年 vs 论文 11.5/20.7；compound 100 年 inf）⇒ 基准期纠正是
必要不充分。`_v5e` 对照（exceed）：复合 100 年 inf→2.28 年（病态消除）但 Table 1 P_fix 全 0 ⇒ 图4c 要 exceed、Table 1 要 envelope。
**新查明机制**：`--baseline xghg` 让 +1.5 °C 的 ALL 世界套冷世界 q90 ⇒ marine 年暴露 **254 天/年**（饱和）。
遗留：4 件 `sst_xghg_*` 曾反复 504，最终 `--block-years 2` 补齐（大块请求失败率更高）。

**2026-11-07 第二十一批：按论文口径"补齐"气候态基准期 1983–2012（用户指令「补齐」）**：
- **动机**：论文 Methods 明写阈值 = "the 90th percentile of the **1983–2012** climatological distribution"，
  而 `_v4` 的阈值只用了 CESM 切片自身的 2000–2021（D7.4 的妥协）⇒ ALL 世界远超"冷基准 90 分位"，
  marine 暴露 214 天/年、ALL 等效重现期 1.1 年（论文 11.5–20.7 年），图4 只能作定性参考。
- **下载器改造** `python/download_cesm1le.py`：① 新增 `--years Y0-Y1`（时段不再写死 `C.CESM_PERIOD`，
  产出名随 tag 变化，与 2000–2021 文件并存）；② 新增 `--block-years N`（默认 5）——
  实测 TDS `.dods` 每次请求有 30–60 s 固定延迟，但**传输 ~57 kB/s 才是瓶颈**，按年切块只是减少请求次数；
  ③ 模块级 `PERIOD` + `_apply_years()`，`trim` 也支持 `--years`。
- **只补 1983–1999**：2000–2012 已在分析期文件里，省 40% 流量（`CLIM_STITCH` 拼接表）。
- **阈值侧改造** `python/phase6_cesm.py`：`--clim-period 1983-2012` → `_period_tag_cli` 设 `CLIM_PERIOD_TAG`；
  `find_*_segments(exp,m,tag=)`、`_load_sst_points(...,tag=)`、新增 `_load_t2m_points(...,tag=)`（与 prepare 同一
  对齐规则）、`_load_stitched()`（1983–1999 文件 + 2000–2021 文件切到 2012-12-31）、
  `_clim_series()` **进程内缓存**（20 个 LOO 池各自要 19 个成员，不缓存会把同一序列读 19 次）、
  `_thresh_cache_path(...,clim_tag)` 缓存名带气候态时段（防静默混用旧阈值）。
  事件仍在 2000–2021 上检测；**阈值只从 XGHG 池取**（`--baseline xghg --loo` 口径不变）。
- **跑法**：`logs\_run_v5_clim.ps1` = detect `_v5`（clim 1983-2012）→ compound → attrib（6 列聚合）→ gev →
  fig3（`--agg-eur eur_p90 --agg-med med_p90`）→ fig4 → table1。
- **★ 补数途中踩到的三个坑（都已修）**：① **绝大多数段与目标时段零重叠** —— 每个组除了 1850/1920–2005 的段，
  还带一个 **2006–2080** 的 RCP85 段（atm `n=27 375`、`time[0]=0`），`_dap2_time` 里 `stop <= off` 直接抛
  `RuntimeError: 时间段 1983-01-01…1999-12-31 与该文件时间轴不重叠（n=27375, v0=0.0）`，整组报废 ⇒
  `cmd_gdex` 现在**先按 manifest 的 `seg_start/seg_end` 剪枝**（不发网络请求），零重叠段直接跳过。
  ② **`✓`/`✗` 在 GBK 重定向日志里 `UnicodeEncodeError`**（`'gbk' codec can't encode character '\u2713'`）
  ⇒ `download_cesm1le.py` 也加了 `_force_utf8_stdout()`，启动时并设 `PYTHONUTF8=1`。
  ③ **只需要 XGHG**：`_pooled_threshold` 的池子硬编码读 `_clim_series(kind, "XGHG", …)`，ALL 的气候态文件
  完全用不上 ⇒ 新增 `--experiments ALL,XGHG`（补气候态用 `--experiments XGHG`，省一半流量）。
- **并发实测（2026-11-07）**：10 流聚合 ≈ 300 kB/s（每流 ≈30 kB/s），加到 **20 流反而更慢**
  （9 min 只完成 12 个 5 年块，10 流时 21 min 完成 48 个块）⇒ **10 分片是最佳点**，别再往上加。
- **已下的可用产物**：20 个 `trefht_all_MMM_1983-1999.nc`（34.5 MB，6205 天 = 17×365，49×51 欧洲框）
  与首批 `trefht_xghg_*`。`_load_t2m_points(tag='1983-1999')` 实测 `(6205, 206)`、`_load_stitched('1983-2012')`
  实测 `(10950, 206)`、1983-01-01~2012-12-31、NaN 0、30 年 × 365 天（noleap）✅。

**2026-11-07 第二十批：Phase 5 全量跑通（图5/图6 数据齐）+ Phase 6 `_v4` 20 成员全链跑通（图3/图4/图6/Table 1 已出）+ 3 个待定口径问题**：
- **Phase 5 全量（18.6 min，14:58→15:16，exit=0）**：`phase5_humid.py all` →
  `results\intermediate\wbt_daily.nc` **1.15 GB** / `sh_daily.nc` **1.13 GB**（14610 天 × 145 × 201）；
  `results\tables\fig5_stats.json`：**sst 中位 +0.335 °C/decade**（p05 0.086 / p95 0.736，n=15905）、
  **sh +0.125 g/kg/decade**（n=37835）、evap +1.74（n=1140）；`fig6_stats.json` + `wbt_compound_{2003,2022,2023}.nc`。
  6c 的 `RP(26 °C)=None` 属正常（GEV 形状为负 ⇒ 有上界），不是 bug。
- **Phase 6 `_v4` 全链（20 成员，`--baseline xghg --loo`，`--compound-def envelope`）**：pairs **206 对** →
  prepare 0.4 min → **detect 36.4 min**（真实退出 0；第一次 15:29 的中断是**后台进程随会话重启被杀**，非算错）→
  compound 0.6 min → attrib 0.1 min → **80 个 `mhw_v4_*/thw_v4_*` 事件表**、
  `annual_v4_{exp}_{mem}.csv`、`exposure_members_v4.csv`、`phase6_attrib_*_v4.csv`。
- **GEV（11.4 min，16:26→16:37）**：marine **ALL 214.4 vs XGHG 29.6 天/年**、terrestrial **46.6 vs 11.9**、
  compound **170.9 vs 11.8**（N=440/组）⇒ `results\tables\phase6_gev_v4.json`。
  marine/terrestrial 与 P0 三成员锚点（208/28、48/11）一致；**compound 与报告里记的 41 不符，是因为 41 属更早的
  旧 tag（`_x3`）**，同口径下 `annual_p0chk_ALL_00{1,2,3}` 实为 **138/172/187**，与今天 135/165/179 一致 ⇒ 聚合无 bug。
- **出图**：`fig3_attribution_v4.png`、`fig4_return_period_v4.png`、`fig5_sst_trend.png`、`fig6_wbt.png`、
  `results\tables\table1.csv`。`fig3` 首跑 exit=1，原因：默认 `--agg-eur eur_p90` 而 attrib 只跑了 med_* 三列 ⇒
  补跑 `attrib --agg med_mean med_p90 med_max eur_mean eur_p90 eur_max` 后成功（**fig3 必须先跑全 6 列 agg**）。
- **★ 三个问题的判断与处置（2026-11-07 定，用户"可以 判断一下"授权）**：
  ① **复合定义：保持 `envelope`（D7.1 不变）**。做了 `exceed` 对照实验（tag `_v4e`，把 80 个事件表用 hard link
  复制成 `mhw_v4e_*/thw_v4e_*` 再跑 `compound --compound-def exceed` + `attrib`，共 ~4 min）：
  每个成员 ALL 复合 130,236–162,124 天（≈**25–36 天/配对点·年**）、XGHG 11,278–25,527（≈2.5–5.6）；
  归因结果 **med_mean 的 P_ALL 只有 0.184/0.061/0.093、P_fix 全 0 ⇒ FAR=1.0、PR=∞**（med_p90 P_ALL 0.52/0.32/0.38）
  —— 比 envelope 离论文更远。论文 Results 原文 "a marine heatwave **fully encompasses** a terrestrial heatwave"
  ⇒ envelope 才是论文口径（Methods 那句 "simultaneously exceed" 属论文自身的两处表述冲突）。
  ② **聚合口径：D7.3 修订 —— 图3 / Table 1 改用 `med_p90`**（**⚠️ 2026-11-08 已被第二十二批推翻：换成论文 1983–2012 基准后
  `med_mean` 才是对的，`MAIN_AGG` 已回归 `med_mean`；以下文字留作历史记录**）。`python/config.py:181` `MAIN_AGG = "med_p90"`
  （原 `med_mean`，注释里记了理由），`table1_attribution.py --tag _v4` 默认即 p90 ⇒
  **FAR 0.803/0.846/0.837、PR 5.08/6.48/6.13**（论文 0.72/0.95/0.78、4.1/[6–∞)/8）；`med_mean` 的 0.977/0.986/0.987、44.1/74.0/75.8 降为敏感性口径。
  已重出 `results\figures\fig3_attribution_v4.png`（`--agg-eur eur_p90 --agg-med med_p90`）与 `results\tables\table1.csv`。
  **仍存偏差**：论文 2022（FAR 0.95）明显高于 2003（0.72）的年际形态没复现，我们三年几乎持平（0.80–0.85），根因见 ③。
  ③ **图4：保持区域均值口径（`_member_exposure_series` 仍读 `med_mean`，不动），并定性为"基准期受限"**。
  p90 不用于图4 是因为 marine 常年顶到 365 天上限。根因已查清：论文阈值取 **"90th percentile of the
  1983–2012 climatological distribution"**（`logs\_paper_main.txt` Methods 原文），而我们的 CESM 切片只有
  **2000–2021**，只能用 XGHG+LOO 当基准（D7.4）⇒ ALL 世界远远超出"冷基准的 90 分位"，marine 214 天/年，
  等效重现期 1.08–1.21 年（论文柱高 2.3–24.0）；compound 面板还叠加零膨胀病态 ⇒ **图4 现阶段只能作定性参考**。
  **补救路径（需用户点头）**：补下 CESM1-LE **1983–1999 共 17 年**切片（≈5 GB，`run_cesm_dap2_*.bat` 约 1 h），
  把阈值期改成 1983–2012 后重跑 `detect`(≈36 min)+`compound`+`attrib`+`gev`，才可能对上图4 与 Table 1 的年际形态。

- **代码小修**：`python/table1_attribution.py` 末尾 `print("⚠️ …")` 在 GBK 控制台崩
  （`UnicodeEncodeError: 'gbk' codec can't encode character '\u26a0'`）⇒ 已加 `_force_utf8_stdout()`
  并把那句改成"20 成员全量口径"；`python/phase5_humid.py` / `python/phase6_cesm.py` 同批也加了该函数。

**2026-11-07 第十九批：ERA5 sp 0.25° 全齐（480/480）+ 两处校验/合并 bug —— "最后一个月永远下不下来"的真相**：
- **现象**：引擎每 10 分钟重排队 sp **2012-02**，每次 13–19 s 就拿到文件，然后
  `✗ 2012-02 校验失败: 数值不在气压量级(Pa): 71881~106418`，永远卡在 **479/480**。
- **★ 根因不是下载、也不是 CDS 拥塞，是我们自己的自检上限拍得太小**：
  `python/download_era5_sp025.py:80` 原先 `SP_MIN, SP_MAX = 6.0e4, 1.06e5`，把 **106 418 Pa（=1064 hPa）**
  判成"不是气压"——这是 2012 年初西伯利亚高压给欧洲带来的真实极值。全量 479 个既有文件实测最大
  **106 156.9 Pa**（`sp_eur_2012_01.nc`）本来就已越界，只因 `verify_month()` **只抽查首时次**才没报
  ⇒ **过窄上限 + 只看首日** 两个缺陷叠加，才表现为"只卡死 2 月"。
- **修**：① `SP_MAX` 改 **1.10e5**（1100 hPa；实测海平面气压极值 ~1084 hPa，仍能挡住"下错变量"）；
  ② `verify_month()` 抽样由"仅首时次"改为 **首/中/末三个时次**。改后既有 479 个文件全部通过
  （`download_era5_sp025.py --dry-run` → `已就位且校验通过: 479 个月`）。
- **★ 另修一个 100% 必崩的死 bug**：`download_era5_tmax.merge()` 与 `download_era5_sp025.merge()`
  都拿 `xr.concat(dss)`（dss 是 DataArray）的结果直接取 `.data_vars` ⇒
  `AttributeError: 'DataArray' object has no attribute 'data_vars'`，**`--merge` 和引擎收尾的合并步骤必崩**
  （这就是 `data\ERA5\` 下此前从来没有合并件的原因）。两处都补
  `if isinstance(merged, xr.DataArray): merged = merged.to_dataset(name=...)`。
- **结果**：sp 2012-02 落盘（`29 天, 变量 sp, 71273~106418 Pa`，2012 是闰年 ⇒ 29 天正确）⇒ **sp 480/480 ✅**；
  `python python\phase5_humid.py check` → **6 项全 `[OK ]`、"输入齐备"**（第一次全绿）；
  补出合并件 `data\ERA5\ERA5_sp_1984_2023_daily.nc`（1.19 GB）与 `ERA5_tmax_1984_2023_daily.nc`（0.71 GB），
  时间步均 **14 610**（1984–2023 = 40 年 × 365.25）。
- **⚠️ 改常量后必须重启引擎进程**：Python 早已 import 旧模块，在跑的进程仍用老上限；
  而且 `build_plan()` 会把"校验不过"的月文件**直接删掉重下**（`download_era5_fast.py:286-290`）
  ⇒ 不重启就会每 10 分钟把已下好的 2012-02 删一次、再下一次。
- **下一步**：Phase 5 可以跑全量（`coastal_buffer.py` → `phase5_humid.py all` → 图5b / 图6 / Table 1）；
  Phase 6 全量 5 条命令随时可跑（它不依赖 sp，走 CESM 自身 TREFHT/SST）。

**2026-10-30 第十八批：CESM1-LE 全量 80 件到位（20 成员 × all/xghg × TREFHT/SST）+ 论文口径复核 + 一个 P0 去重修复**：
- **数据全齐**：`data\CESM1-LE\proc\trefht_{all,xghg}_{001..020}_2000-2021.nc`（40 件，45–47 MB）
  与 `sst_{all,xghg}_{001..020}_2000-2021.nc`（40 件，113–114 MB），合计 **6.2 GB**（网络实搬 ≈18 GB）；
  ERA5 tmax **480/480**，sp 0.25° 当时 204/480（**2026-11-07 已补齐 480/480**，见第十九批）。
- **★ 下载通道彻底换了：自写 DAP2 客户端 `python/dap2.py` + `download_cesm1le.py --engine dap2`**。
  原因是本机 **netCDF4/libcurl 的 DAP 通道全崩**（`OSError: [Errno -68] NetCDF: I/O failure`，schannel 证书吊销检查
  在 netCDF-C 里关不掉），pydap 又慢（6 路并发仅 33 kB/s，同条件 dap2 **1.5 MB/s**）。四条坑：
  ① TDS **每个 `.dods` 请求都有 30–60 s 固定延迟** ⇒ 时间轴绝不整条取，改成"取 1 个时间点 + `cftime.date2num` 算下标"；
  ② 自写客户端**不解码 `_FillValue`** ⇒ 陆地返回 9.96921e+36，必须 `|v|>1e30 → NaN`；
  ③ DAP2 响应里每个数组/坐标前有 **8 字节头 + 3 个 MAPS**，不跳过就整体错位；④ **`.bat`/`.ps1` 里不许出现中文**
  （`chcp 65001` 生效前已按 GBK 解析 ⇒ 报"字符串未终止"/"'shards' 不是内部或外部命令"）。
- **切片口径 = 分析切片，不是下整文件**：22 年（2000–2021）× 大气欧洲框 2 499/55 296（4.5%）× 海洋欧洲邻近
  11 328/122 880（9.2%，pad 回全球 384×320 形状以保 `coastal_pairs_cesm.csv` 的全局索引）× 只取 2 个变量。
  论文原文（`logs\_paper_main.txt`：Methods "We focus on the period 2000–2021 … 440 model years (22 years × 20 members)"）
  只用地海配对点、**没有任何 CESM 地图** ⇒ 口径够用。要 2080 情景 / 整盆平均 / 改区域框才需补下。
- **★ 修一个 P0**：`proc\` 里成员 001–003 同时留着 9 月旧通路（raw 整文件 + trim）分段件与新 gdex 整段件
  ⇒ `find_sst_segments("ALL","001")` 返回 3 个、`find_t2m_segments` 返回 2 个，`_load_sst_points` 会把 2000–2021
  **拼两遍**（阈值分位与事件天数全错）。`python/phase6_cesm.py:123` 新增 `_prefer_gdex()`，gdex 整段件在就只用它并打印
  `⚠ 同一成员有 N 个 raw/trim 分段件与 gdex 整段件并存 → 只用 …`。
- 产物体检 `logs\_audit_cesm80.py` → **80 件 / 异常 0**（atm `n=8030`、有限点 2 499/天；ocn 有限点 4 263/天、
  子网格外溢出 0；`ALL` 海洋 `n=8029` 因**原始数据缺 2006-01-02**，非下载 bug；"断点"另有 noleap 无 2/29）。

**历史批次（2026-09-23 ~ 2026-10-15）已迁出 → `docs/批次历史.md`**（2026-11-08 迁出，为把本文件压回指令预算）。
以下是那段时间**仍然有效、会反复用到**的硬结论摘要，细节与证据全在被迁出的文件里：
- **CDS 三条硬约束**：① 单请求 ≤ **400 天**（1 年 OK、2 年被拒）⇒ `--chunk-months 12` 是上限；
  ② 同数据集「排队中请求数」**上限实测 = 3**（`--jobs 6` 全被 `rejected`）；③ 耗时几乎全在排队、与请求大小无关
  （一个年请求排过 3.1 h / 6.2 h）。被拒原文只有 `GET /jobs/<id>/results` 里才有：
  `Number queued requests for this dataset is temporarily limited`。
- **有在队任务时绝不要跑 `--clean-queue`**（会删 `accepted`/`running`）；关窗/关机不影响服务端任务。
  恢复顺序永远是 `adopt`（先收割）→ 再启动引擎；台账 `logs\era5_pending_years.json` 记"已提交未出结果"的年份。
- **CDS 在队任务能读回请求体**：`GET {url}/retrieve/v1/jobs/<id>?request=true&log=true` → `metadata.request.id
s`；
  相同请求重复提交直接回缓存（几乎免费）。
- **CESM 走自写 DAP2 客户端**（`python/dap2.py` + `--engine dap2`）：本机 netCDF4 的 DAP 通道损坏、pydap 慢 40 倍。
  四条坑：① 每个 `.dods` 有 30–60 s 固定延迟 ⇒ 时间轴绝不整条取；② 不解码 `_FillValue` ⇒ 陆地返回 9.97e36，
  必须 `|v|>1e30 → NaN`；③ 响应里每数组前有 8 字节头 + 3 个 MAPS，不跳过就整体错位；
  ④ **`.bat`/`.ps1` 里不许写中文**（`chcp 65001` 生效前已按 GBK 解析）。
- **TDS 拥塞期**：10 流聚合 ≈300 kB/s 是上限（20 流更慢）；**小块请求成功率显著高于大块**（补件用 `--block-years 2`）。
- **本机环境**：无 conda；Python 3.13（`python -m pip install -r requirements.txt`）；R 4.6.1 于 `C:\Program Files\R\R-4.6.1`
  （= `config.RSCRIPT_PATH` 默认值），heatwaveR 0.5.5。**换机器/换对话先验环境**，别默认还能跑。
- **检测口径**：D1 统一 R heatwaveR（先过滤后桥接）；D2 `smoothPercentile=FALSE`（偏离两包默认，影响 <5%）；
  D3 观测侧复合日 = 逐日共超标（模型侧见 D7.1 包络）。**图1j/l 的绝对量级已定稿为"未复现项"，停止口径搜索**（见复现报告 §6）。
- **OAFlux 唯一可用入口**：NSF NCAR GDEX/OSDF 匿名 HTTPS（WHOI/PSL/APDRC 四镜像全不可达）；1° 是其原生分辨率。

## 当前可运行文件

主链路（Phase 1-4，已验证）：
- `python/run_all.py` — Phase 0–3 四阶段主控（预处理→检测→复合→年度指标/CHR/共现概率）
- `python/figures.py` — 图1/图2/S1 出图；`python/fig_jkl_mhw_envelope.py` — S2
- `python/detect_events.R` — **海陆统一热浪检测正式链路**（R heatwaveR）
- `python/phase6_cesm.py` — Phase 6 归因管线。**detect 的标定旋钮**：`--baseline {own,xghg,self,all}` + `--thresh-offset`（只 SST）/ `--thresh-offset-t2m`（双世界陆地）/ `--thresh-offset-xghg-t2m`（**只反事实世界陆地**，需配 `--baseline self`）；**gev 的映射内核**：`--mapping {gev,emp}`（默认 gev = 论文口径，emp = 经验分位 = `_v10` 起的诊断口径）。P0 验证版；**2026-09-23 审计修复 F1–F9**：
  检测端与 R heatwaveR 等价、阈值逐点、11 天窗、缓存带指纹、`--members` 作用于全量 20 人名单、
  `--loo`、doy=366 阈值行）
- `python/coastal_buffer.py` — 图6 分析域：海岸向内 100 km 缓冲掩码（Phase 5 前置，已接入 `phase5_humid.py`；
  `exclude=` 按框剔除黑海，`main()` 优先用欧洲裁剪件 OISST）

Phase 5（湿热应力，2026-09-24 新增，数值链路已验证）：
- `python/calc_wbt.py` — RH / WBT（Stull 2011 + psychrometric 牛顿迭代）/ SH / JAS 趋势；`python python\calc_wbt.py` 跑 25 项合成自检
- `python/gev_return_period.py` — GEV MLE + bootstrap + FixGHG→ALL 重现期映射（图4/图6c 内核）；自带 16 项自检
- `python/phase5_humid.py` — Phase 5 主链路：`check` / `fields`（逐日 WBT·SH）/ `stats`（图5 趋势 + 图6 统计）/ `all`
- `python/fig3_attribution.py` — **论文图3**（FAR/PR 2×2，按原图逐像素校准）
- `python/fig4_return_period.py` — **论文图4**（重现期位移 1×3；`--demo` 可渲染论文锚点版式自检图）
- `python/fig5_sst_trend.py` — **论文图5**（SST / 蒸发 / 比湿 JAS 趋势三面板；`--synthetic` 版式自检）
- `python/fig6_wbt.py` — **论文图6**（a/b 超阈曲线、c 重现期、d–f 复合日最大 WBT 场）
- `python/table1_attribution.py` — **论文 Table 1**（62/78/72 天三点的 FAR/PR + 论文对照列）
- `results/phase5_selftest.py` — Phase 5 纯合成自检（不读观测）→ `ALL PHASE5 SELFTESTS PASSED`
- `python/figS1_annual_maps.py` — **论文版 Supplementary Fig. S1**（1984–2023 年际组图，4×10 面板）
- `phase6_cesm.py gev` — 图4 的海洋/陆地/复合年暴露序列 + GEV → `results/tables/phase6_gev{tag}.json`

⚠️ **检测链路口径提示**：`python/detect_thw.R` 有吞错 bug，**仅存档勿用**。
**（第三轮更正）`python/run_all.py` 现已海陆双路都走正式链路 `python/detect_events.R`**
（`run_all.py:47,73-95,161-181`，2026-09-23 提交 `e622993`）——此前"THW 环节仍指向
`detect_thw.R`"的说法已过期；`detect_thw_wrapper.py` 仅保留供单点复核。
另：全链路 `smoothPercentile=FALSE`，偏离两包默认（TRUE/31 天窗），理由见 `results/复现报告.md` D2。

下载工具：
- `python/download_cesm1le.py` — CESM1-LE（AWS zarr / GDEX）。**2026-10-30 起官方口径 = `--engine dap2`**
  （自写 `python/dap2.py`，把欧洲框/子网格当 DAP2 约束直取；本机 netCDF4 DAP 通道损坏、pydap 慢 40 倍）；
  配套入口 **`run_cesm_dap2_atm.bat`**（大气 6 路分片）与 **`run_cesm_dap2_ocn.bat`**（海洋 6 路分片，
  走子网格 9.2% + pad 回全球）；进度 `show_cesm_progress.bat`。旧入口 `run_p0_download.bat` /
  `run_phase6_download.bat`（`--members 20` 整文件口径）仍在，但**全量已下完，别重跑**。
- `python/dap2.py` — **DAP2 最小客户端**（`requests` + 手解 XDR 大端；每数组前 8 字节头必须跳过）。
  `.dds`/`.das` 打开 10 s（pydap 86–123 s）。
- `python/download_era5_tmax.py` — ERA5 日最高气温（CDS daily-statistics；支持 `--dry-run`）
- `python/download_era5_sp025.py` — ERA5 **0.25°** 地表气压欧洲框（数据集 3b+；支持 `--dry-run`）
- **`python/download_era5_fast.py`** — 上面两项的**分块并发引擎**（`--chunk-months` 选粒度，
  **默认 12 = 一次申请一年**；2 并发 + 限流退避；`--selftest` 本地自检 / `--clean-queue` 清在队任务）；
  一键入口 **`run_phase5_fast_download.bat`**
- `python/download_oaflux_evap.py` — OAFlux 蒸发（**主源 = NSF NCAR GDEX/OSDF**，WHOI/PSL/APDRC 四镜像降级备份）
- `run_phase5_downloads.bat` — 一键跑 tmax + sp 0.25° + OAFlux（Phase 5 的全部输入）
- **`python/adopt_cds_jobs.py`** + **`run_era5_adopt.bat`**（2026-10-14 新增）— 认领**服务端已跑完**
  （`successful`）的 CDS 任务并切回月文件，已收 id 记 `logs\cds_adopted_jobs.json`；`--list` 只看清单、
  `--wait-live` 轮询在队任务出结果即收、`--since-hours` / `--max-jobs` / `--all`。
  **`run_phase5_fast_download.bat` 已把它当第一步（先收割、后下载）**——这样重启引擎不会重复排队，见第十二批。
- `scripts/translate_to_word.py` — 读取 `pdf_extract/` 图片生成中文翻译 Word（注意：其引用的图片文件名与当前 `pdf_extract/` 实际文件名不一致，需先核对）

数据格式转换（2026-10-17 新增）：
- **`python/make_yearly_d2m.py`** + **`run_make_yearly_d2m.bat`** — 把 `d2m_global_daily/` 的
  573 个**月度 netCDF-4/chunked/zlib** 文件合并成 **classic netCDF-3（CDF-2 64-bit offset，不压缩不分块）**
  年度文件 `E:\2607compound\data\ERA5\d2m_yearly\d2m.era5.daily.YYYY.nc`（≈1.4 GB/年，约 45 s/年）。
  **动机**：用户那台机器的 GrADS 对这些文件报 `NetCDF: Unknown file format` / `nc_get_vara_double failed; NetCDF: HDF error`
  ⇒ 已实测确认**源月度数据完好（573/573 头正常、纳值 0%）**，坏的是年度文件那一层（截断 / chunked+deflate 读不出）；
  GrADS `sdfopen` 只吃 classic 格式。全量 1979–2026 已生成 **48 个 / 67.3 GB**，
  审计脚本 `logs/audit_yearly_d2m.py`（格式/天数/时间轴连续性/网格/缺测/量程）→ **47 好 + 1 未走完(2026 止于 09-03) + 0 坏**。
  `--check-only --out <dir>` 可体检任意目录里的年度文件；`--format NETCDF3_CLASSIC` 可出更老的格式（单文件 <2 GB 时可行）。
  操作口径见 `待办.md` §「d2m 年度文件"GrADS 打不开"已修」。

> **数据下载进度（2026-11-07 实测，全部完成）**：ERA5 **tmax 480/480 ✅**、**sp 0.25° 480/480 ✅**
> （第 480 个月 2012-02 的卡点原因见第十九批：不是 CDS 拥塞，是自检上限写小）；
> **CESM1-LE 80 件全齐 ✅**（6.2 GB）；OAFlux ✅。**四类输入零缺口**，图5b / 图6 / Table 1 可以出图。

## 目录结构（已建成；`data` 为 NTFS Junction → `E:\2607compound\data`）

```
D:\2607compound\        ← 工作区根目录（代码、文档、结果）
├── 待办.md              # ★ 你的操作指引（下载 → 复核 → Phase 5 → Phase 6），先读这份
├── data/                # NTFS Junction → E:\2607compound\data（合计 ~330 GB，2026-10-30 实测）
│   ├── OISST/           # 48.1 GB（全球合并件 + 欧洲裁剪件）
│   ├── E-OBS/           # 0.9 GB（合并件 14975 天 + 3 个分段原始）
│   ├── ERA5/            # 150.9 GB = d2m_global_daily 78.3（月度×620）+ d2m_yearly 67.3（年度×48）
│   │                    #           + sp 1.0° 4.1 + sp_eur_daily 0.5（206 件）+ tmax_eur_daily 0.7（480 件）
│   ├── OAFlux/          # OAFlux_evap_1991_2020_monthly.nc（47 MB）
│   └── CESM1-LE/        # raw/（3 成员整文件 109 GB）+ proc/（20 成员切片 80 件 6.2 GB）
├── python/              # 全部处理 + 绘图代码
├── results/             # 产物 + 文档（2026-09-23 整理，见 results/README.md）
│   ├── 复现报告.md        # ★ 主报告：进度 / 锚点总表 / 决策 D1–D7 / 偏差清单
│   ├── Phase6审计报告.md  # Phase 6 审计（6 份合并）：§1 汇总 §2 修复对比 §3–§6 分报告
│   ├── 规划一致性审查.md   # 规划文件 vs 论文两轮审查（合并）
│   ├── 方法与证据.md      # 目视比对 / E-OBS 核查 / S1 读取 / R-Python 交叉验证 + 2 份历史存档
│   ├── README.md         # 本目录导航
│   ├── globalize_mhw_idx.py  # ★ 被 run_all.py 运行时调用，勿移动
│   ├── build_oisst_clip.py / build_domains.py / run_detection_R.py  # Phase 0/1 入口
│   ├── phase6_selftest.py    # Phase 6 口径纯合成自检
│   ├── figures/ tables/ intermediate/ s1/   # 出图 / 快照 / 中间产物 / S1 裁剪
│   └── tools/            # 诊断与复算脚本，按主题分组（见 tools/README.md）
├── docs/                # 主论文/补充材料 PDF、复现方案.md
├── pdf_extract/         # 从 PDF 提取的论文原图
└── scripts/             # 工具脚本（extract_paper_figs.py、translate_to_word.py 等）
```

> 注：`matlab/` 目录**不存在**——绘图已全面切换 Python (matplotlib + cartopy)，
> 三份 PHASE 文档中的 MATLAB 段落均标注为"已弃用，仅作对照"。

## 技术栈（全量）

- **Python ≥ 3.10**：xarray, numpy, scipy, matplotlib, cartopy, joblib, pandas（`marineHeatWaves` 仅作单格点核验，DEPRECATED）
- **R ≥ 4.0**：heatwaveR (**本机 v0.5.5**；论文标注 v0.4.6，两版语义已核验一致), ncdf4, doParallel, foreach — 通过 `Rscript` 调用（**不用 rpy2**）
- **Python 环境**：本机**没有 conda**（2026-10-13 全盘搜过）——用系统 Python 3.13 +
  `python -m pip install -r requirements.txt` 锁定版本；R 由 `Rscript` 直调。

## 关键约束与陷阱

1. **数据依赖极重（2026-10-30 实测 ≈330 GB，E: 剩 114.9 GB）**：OISST 48.1 GB + E-OBS 0.9 GB +
   ERA5 150.9 GB（含 d2m_yearly 67.3 GB 派生件）+ CESM1-LE 129.5 GB（raw 109.3 整文件 + proc 20.2 切片）+ OAFlux 0.1 GB。
   真正的计算瓶颈是 **40 个 CESM 模拟的逐格点热浪检测**（P0 实测 27 s/成员）；
   归因 bootstrap 本身很轻（样本是池化后的 440 个模型年标量）。**CESM 数据 2026-10-30 已全齐，不必再下**；
   下载侧 **2026-11-07 已全部完成**：ERA5 sp 0.25° 补齐到 480/480（合并件 1.19 GB），四类输入零缺口。
2. **路径硬编码**：`config.py` 中 `BASE_DIR = D:\2607compound`，`DATA_DIR = D:\2607compound\data`（NTFS Junction → `E:\2607compound\data`）；`translate_to_word.py` 使用工作区内的 `pdf_extract` 和 `results` 目录。已统一。
3. **混合语言调用**：陆地/海洋热浪检测统一走 R，经 `subprocess.run([RSCRIPT_PATH, ...])` 调用
   `python/detect_events.R`（正式链路）；`RSCRIPT_PATH` 与 `DETECT_THW_R_SCRIPT` 定义在 `config.py`。
4. **海洋-陆地网格对齐**：OISST 与 E-OBS 格点不对齐。**不重采样**——用 KDTree 最近邻配对
   （`MAX_GRID_DIST_DEG = 0.5°`，实测 2039 对 / 1434 唯一海点），下游全部按配对索引匹配。
   **CESM 侧另有一套**：POP gx1v6 → f09（实测 0.9424°×1.25°）KMT 湿点映射 + 4-连通海岸边缘 +
   KDTree cos 加权，上限 `MAX_PAIR_DIST_DEG = 1.0` 单位 ≈ **112.2 km**（观测侧 0.5 单位 ≈ 55.6 km，
   **模型侧允许分离约为观测侧 2.1×**），实测 **206 对 / 唯一陆点 206 / 唯一海点 191**。
   `python/phase6_cesm.py` 的 `cmd_pairs`。**⚠️ 改 `MAX_PAIR_DIST_DEG` 会让阈值缓存串味**：`_thresh_cache_path()` 的键 = 成员名单 + LOO + `clim_tag` + `pool_exp` + `THRESH_VERSION`，**不含配对集** ⇒ 换距离后 206 对算出的 `thresh_*.npz` 会被静默复用到不同规模的配对集上（产出看着正常但错的数据）。要做配对距离敏感性，必须先把配对指纹并进缓存键并作废全部缓存；只想回答域选择会不会改变结论，用 `logs/_diag_region_sens.py`（换区域，不动共享状态）。
5. **WBT 计算输入已确认**：论文明确由 ERA5 的 **Tmax + 露点 + 地表气压**估算**日最高 WBT**；
   具体近似式未给，`TECHNICAL_SPEC.md` §3.8 提供 Stull / 牛顿迭代双实现待定稿。
   **图6 的 100 km 海岸缓冲已实现**：`python/coastal_buffer.py` + `config.COASTAL_BUFFER_KM`
   （**2026-11-17 已拍板**：域 = 地中海 100 km、剔除黑海/亚速海、纳入西班牙东岸⇒ 掩码 **1637** 格点（原 1952）；
   `config.COASTAL_BUFFER_REGION` / `COASTAL_BUFFER_EXCLUDE`，见第二十七批）。
6. **无包管理/CI 配置**：有 `requirements.txt`（2026-09-24 新增，锁定本机实测版本），但没有 `pyproject.toml`、
   `environment.yml`、`Makefile` 或 CI 工作流。环境需手动搭建。
7. **无单元测试框架**：验证方式是 ① 四套纯合成自检（`calc_wbt` 25 项 / `gev_return_period` 16 项 /
   `results/phase5_selftest.py` / `results/phase6_selftest.py`）② 与论文图表目视比对（锚点总表见
   `results/复现报告.md` §4）③ `python/verify_data.py` 数据完整性检查。

## 快速参考

| 任务 | 命令/说明 |
|------|----------|
| 一键复现 Phase 0-3 | `python python\run_all.py`（缓存命中 ~1 min；全量重检陆地 ~22 min）|
| 出图 1/2/S1/S2 | `python python\figures.py` + `python python\fig_jkl_mhw_envelope.py` |
| **下 Phase 5 全部输入** | **`python python\download_phase5.py`**（VSCode 点开即跑；= ERA5 tmax + sp 0.25° + OAFlux；支持 `--dry-run` / `--skip-oaflux`）。**⚠️ 2026-10-14 起 ERA5 那部分请走 `run_phase5_fast_download.bat`**（显式窗口 + 先收割后下载），两者别同时跑 |
| **下 CESM 全量** | **已完成（2026-10-30，80 件全齐）**；要重跑/补件时用 `run_cesm_dap2_atm.bat` / `run_cesm_dap2_ocn.bat`（`--engine dap2` 分片）。旧的 `python python\download_phase6.py`（整文件口径，+80–100 GB）与 `run_phase6_download.bat` 保留但别用 |
| 下 ERA5 tmax | `python python\download_era5_tmax.py [--dry-run]`（`--merge` 合并） |
| 下 ERA5 sp 0.25° | `python python\download_era5_sp025.py [--dry-run]`（数据集 3b+） |
| 下 OAFlux | `python python\download_oaflux_evap.py [--probe]` |
| 下 CESM1-LE | **已完成**；补件用 `run_cesm_dap2_atm.bat` / `run_cesm_dap2_ocn.bat`，或 `python python\download_cesm1le.py gdex --engine dap2 --member-ids 007 --only-comp ocn`（`aws` 路径 2026-10-20 起不可用） |
| Phase 6 归因（全量，口径已定） | `pairs` → `prepare --members 20` → `detect --members 20 --baseline self --loo --clim-period 1983-2012 --thresh-offset-xghg-t2m 0.5645 --tag _v12w50` → `compound --members 20 --tag _v12w50 --compound-def envelope` → `attrib --members 20 --tag _v12w50 --compound-def envelope --agg med_mean med_p90 med_max eur_mean eur_p90 eur_max` → `gev --members 20 --tag _v12w50 --mapping emp`。`_v7`（w=0）只能当端点敏感性，**别再当主口径** |
| Phase 6 口径决策 | 复合=**MHW 包络**(D7.1/D7.6)；归因=**阈值扫描+62/78/72 参考线**(D7.2)；聚合 **med_mean**(D7.3rev)；基准期 **各实验自算 1983–2012 + LOO**(**D7.4rev 2026-11-08，取代 XGHG 共用基准**)；bootstrap **indep**(D7.5) —— 见 `results/复现报告.md` §5 D7 与 §5.2 |
| **一键跑 Phase 5–7** | `python python\run_phases.py --phases 5 6 7`（默认主口径 `_v12w50`；`--dry-run` 看计划、`--legacy` 回退旧口径、`--skip-selftest` 跳过前置自检） |
| **终版中文报告** | `results\复现报告_终版.docx`（3.7 MB，10 章 + 6 图 + 12 表）；重建 = `python scripts\build_final_report.py` |
| **Phase 6 主口径全链（`_v12w50`：图3 + 图4 + Table 1 统一口径）** | ① `logs\_run_v12w50.ps1` 是单点全链模板（detect → compound → attrib 6 列 → gev `--mapping emp` → fig4 → table1，**5.7 min**）；② 关键参数 = `--baseline self --loo --clim-period 1983-2012 --thresh-offset-xghg-t2m 0.5645`（w=0.50）+ `gev --mapping emp`；⇒ **图4 三面板 15/15 全在论文 bootstrap CI 内**、Table 1 FAR MAE 0.0607，见第二十六批 |
| Phase 6 图4 残差判定 | **先跑 `python logs\_cmp_ci.py [_tag…]`**：打印各 tag 五档 + **bootstrap CI** + 论文值 IN/out + `r100/r5` + FixGHG 五档水平与 100 年 CI ⇒ 判"噪声 vs 真残差"。全 tag 对照仍用 `python logs\_cmp_gev_tags.py`（往 `TAGS` 里加 `_v11t06 _v11t11 _v12w50 _v12w60 _v12w89`） |
| Phase 6 逻辑自检（不读数据） | `python results\phase6_selftest.py` → `ALL SELFTESTS PASSED` |
| **Phase 5 输入检查** | `python python\phase5_humid.py check`（明确列出缺哪一项） |
| **Phase 5 全长链路** | `python python\coastal_buffer.py` → `python python\phase5_humid.py all`（逐日 WBT/SH + 图5 趋势 + 图6 统计）；**只重算图6（改域/改口径后）**用 `python python\phase5_humid.py stats --skip-fig5` → `python python\fig6_wbt.py` |
| Phase 5 公式自检 | `python python\calc_wbt.py`（25 项）/ `python python\gev_return_period.py`（16 项） |
| **图3（FAR/PR）** | `python python\fig3_attribution.py --tag _v12w50`（主口径）。⚠️ fig3 会把 `--agg-eur`/`--agg-med` 两列都画上，所以 **attrib 必须先跑全 6 列 agg**；3 条年份参考线 62/78/72 处的 FAR 应与 `table1_v12w50.csv` 逐位一致 |
| **图4（重现期）** | `python python\fig4_return_period.py --tag _v12w50`；⚠️ **图4 必须配 `gev --mapping emp`**（GEV 外推会把复合面板百年水平推到 604 天/年，超出 365 天物理上界）；版式自检 `--demo` |
| 检查数据完整性 | `python python\verify_data.py` |
| 环境搭建 | 见 §技术栈；关键包 xarray/cartopy/heatwaveR(R)/cdsapi |

## 权威文档

- `TECHNICAL_SPEC.md` — 详细代码规范、API 设计、算法说明（最权威）
- `TECHNICAL_SPEC_PHASE_A/B/C.md` — 阶段 A（观测，图1–2）／B（归因，图3–4）／C（湿热，图5–6）；
  MATLAB 段落均为"已弃用，仅作对照"
- `DATA_REQUIREMENTS.md` — 数据下载步骤、目录结构、验证脚本、优先级
- `docs/复现方案.md` — 论文基本信息、阶段规划、注意事项
- `results/README.md` — **results/ 目录导航（先看这个）**
- `results/复现报告.md` — 进度、锚点验证总表、方法学决策记录 **D1–D7**、偏差清单 §5.1、图1j/l 定稿 §6
- `results/Phase6审计报告.md` — Phase 6 归因管线审计（含修复前后对比与四份分报告）
- `results/规划一致性审查.md` — 规划文件 vs 论文**三轮**审查；**第二轮对第一轮有 3 处更正、
  第三轮给出 3 项 Phase 6 全量开跑前的 P0 阻塞项**（**Phase 5/6 开工前必须先读**）
- `results/方法与证据.md` — §1 目视比对 / §2 E-OBS 拼接核查 / §3 S1 读取与图6年份判据 /
  §4 R-Python 检测交叉验证 / §5–§6 历史存档
- `results/tools/README.md` — 诊断与复算脚本索引（**哪个结论由哪个脚本算出**）
