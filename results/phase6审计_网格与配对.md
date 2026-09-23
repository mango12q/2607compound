# Phase 6 审计 D-1：网格与配对（task-1）

- **审计对象**：`python/phase6_cesm.py` 的 `cmd_prepare` / `cmd_pairs` / `_load_sst_points` / `_pooled_threshold_t2m`
- **复算脚本**：`results/phase6_audit_grid.py`（只读 `data/` 与 `results/intermediate/cesm/`；产物全部写入 `results/intermediate/audit/grid/`）
- **审计员**：grid-auditor ｜ 结论一律以"实测数字"为准，不采信文档自述
- **判定口径**：【确认无误】= 实测与代码意图一致；【有问题】= 实测与代码意图/物理事实不符；【未判定】= 证据不足

---

## §0 结论清单

| 编号 | 一句话结论 | 判定 | 严重度 | 关键数字 |
|---|---|---|---|---|
| **S-1** | `_pooled_threshold_t2m` 的 11 天窗平滑把 206 个陆点塌缩成**一个全欧统一阈值**，v2 的 `thw_x_*.csv` 空间分布被完全扭曲 | **有问题** | **P0** | 365/366 行空间标准差为 0；塌缩阈值南欧超阈 12.8% / 北欧 0.0%，正确阈值 6.3% / 6.5%；两者 max\|Δ\|=24.29 °C；缓存 0/75396 不一致⇒非过期而是代码真实产物 |
| **E-1** | MHW 与 THW 的逐日掩码存在**系统性 1 天错位**（POP SST 标签=物理日+1；`_event_daily_mask` 对 12:00 的 t0 向下取整） | **有问题** | **P1** | v1 ALL 16756→18234(+8.8%)、v1 XGHG 15810→17352(+9.8%)、v2 XGHG 7313→7802(+6.7%)；v2 总暴露比 8.885→8.373(−5.8%)；v2 ALL 偶然对齐 Δ=0 |
| **E-2** | 该错位**不改变**论文 Eq.3 的 PR/FAR 结论 | **确认无误**（限定） | P2 | 原样 PR=48.00 FAR=0.979 CI[14.7,53.0]；修正后**完全相同**（与 `复现报告.md:349` 记录逐位一致） |
| **B-4** | proc 文件 calendar 标为 `proleptic_gregorian` 但数据实为 noleap（无 2-29），doy 集合含 366；ALL SST 两段之间有 1 个物理日缺口 | **有问题** | **P1** | doy∈1..366；ALL SST 段接缝标签步长=2 天（XGHG=1 天）；POP 标签=物理日+1（raw `time_bound` 实证） |
| **A-3** | `binary_erosion` 默认 `border_value=0` 产生 78 个阵列边界伪边缘，但**全部被 1.0 单位距离门限淘汰，未产生任何配对** | 有问题（无影响） | P2 | edge 357，边界 edge 84，纯伪边缘 78（21.9%）；206 对中来自伪边缘 **0**；边界配对 6 个，6 个全是真海岸 |
| **A-2** | 24 个 f09 海格点仅由**欧洲框外** POP 湿点经 `argmin` 夹取到边界列而判为海 | 有问题（低影响） | P2 | 框内湿点 2770 → 通过容差 2986（多 216）；仅靠框外点变海 24 格，24/24 落在 lon=−16.25 边界列 |
| **A-4** | cos 加权单位 ≈ 112 km，但模型侧 1.0 单位的上限约为观测侧 0.5 单位的 **2.1×** | 确认无误（口径需说明） | P2 | 1 单位 = 112.2 km（中位换算）；206 对大圆距 37.7/81.6/134.1 km；观测侧 0.5 单位 ≈ 55.6 km，实测 max 62.5 km |
| **A-5** | 模型/观测配对口径差异**只登记在进度报告，未进入权威规范** | 有问题（文档） | P2 | `results/复现报告.md:338,344,347` 有；`TECHNICAL_SPEC.md`、`TECHNICAL_SPEC_PHASE_A.md`、`docs/复现方案.md`、`AGENTS.md` **均无** |
| **B-1** | CESM 侧经度全程一致；**观测侧 `coastal_pairs.csv` 的 `ocean_lon` 是未换算的 0–360** | 有问题（潜伏） | P2 | POP TLONG 0.0147–359.9960 → −179.9967–179.9992；pairs/mhw 一致(max\|Δ\|=3.6e-15)；观测 pairs 0.125–359.875 vs 观测 mhw −25.125–45.375 |
| **A-1/A-6** | 配对链路 206 对**可逐行复现**，索引维度对齐正确，块读与逐点读取**数值完全相同** | **确认无误** | — | 206 对逐行一致=True；KMT[pj,pi] 全部 >0；块读 vs isel max\|diff\|=0.0（3 点全时段 + 另抽 21 对） |
| **B-2** | 源 XGHG `lat` 是**升序**，`.sel` 未发生纬度翻转，数据**无错位** | **确认无误** | — | 源 lat −90→90 升序；4 个探针 max\|merged−手工NN\|=**0.0000 °C**，纬度翻转假设为 36.98–42.07 °C |
| **B-3** | TREFHT 两段均为 K 且双判据命中、已正确转 °C；SST 为 degC，**无需**换算 | **确认无误** | — | seg1/seg2 units='K' max 319.98/320.18；落盘 XGHG −56.99–45.77 °C；SST 四段 units='degC' −2.88–34.86 |
| **C-1/C-3** | XGHG 001–003 拼接后 8030 天连续无重复，两段单位/坐标/属性一致，`concat` 无静默错误 | **确认无误** | — | 各段 2190+5840=8030；无重复、严格单调；units/dtype/lat/lon/attrs 全一致 |
| **C-2** | 接缝 2005-12-31→2006-01-01 **无单位/坐标不连续证据** | **确认无误** | — | T2m XGHG 接缝 2.5539 vs 跨年基准 p50 1.9535（21 个中排 15，67 分位）；SST XGHG 0.0544 vs 冬季 p50 0.0501（95 分位） |
| **S-2** | `doy=366`（闰年 12-31，共 6 天）在 v2 的 T2m 与 SST 阈值表中均为**全 NaN 行** → 该日恒不超阈 | 有问题 | P2 | 阈值表第 366 行全 NaN；doy=366 在 8030 天中出现 6 次 |

> **与 detection-auditor E1 的对照**：本审计独立复算 `recomputed_thresh_t2m.npz`（`src`=现行源码公式、`fix`=正确逐点公式），得塌缩阈值与正确阈值 **max\|Δ\|=24.29 °C**、正确阈值逐点空间标准差中位 **5.92 °C**。与 E1 报的 mean\|Δ\|=8.26 °C / p90=16.45 °C 同向同量级（本审计给的是极值口径），两路独立复算互证 S-1 成立；E1 报的 v2 THW 事件 3746→11310 也正是该塌缩的量级后果。

---

## §0.5 版本与时效（重要）

**本报告审计的是修订前的版本**：`python/phase6_cesm.py` **714 行**（`cmd_pairs` 在 :148-219、`_load_sst_points` 在 :225-256、`_pooled_threshold_t2m` 在 :298-333、`cmd_compound` 的 `t0` 在 :499、`_annual_per_pair` 的 `t0` 在 :553）。

**该文件已于 2026-09-23 23:26:09 被第三方修改为 862 行**（文件头新增 `# ★ 审计修复 2026-09-23（结果见 results/phase6审计报告.md）★`，列 F1–F5）。本审计在 23:30 后按当前版本逐条复核，结论如下：

| 本报告结论 | 在当前 862 行版本中的状态 | 依据（当前文件行号） |
|---|---|---|
| **S-1**（T2m 阈值空间塌缩，P0） | **已修复**。塌缩式 `np.concatenate([single[w-1]...])` 已不存在；新实现 `np.concatenate(pool_rows, axis=0)` 中 `pool_rows` 是 **2 维**数组列表，`nanpercentile(..., axis=0)` 恢复逐点语义 | `:383-384` |
| **S-2**（doy=366 全 NaN 行） | **已修复**。新增 `cal = 365 if doy_all.max()<=365 and 366 not in doy else 366`，窗口按 366 天日历回绕 | `:377-379` |
| **E-1 的 12:00 取整分量** | **已修复**。`cmd_compound` 的 `t0` 与事件日期都加了 `.normalize()` | `:611, :619, :679-680` |
| **E-1 的 POP SST 标签 = 物理日+1 分量** | **未修复**。`_load_sst_points` 与旧版逐字相同（无 −1 天校正、无物理日重标） | `:243-274`（与旧版 :225-256 同） |
| **A-3**（`border_value=0` 伪边缘） | **未修复**（`binary_erosion(land_mask, structure=s)` 原样；实测本身未产生配对，影响有限） | `:204` |
| **A-4 口径 / A-5 文档 / B-1 观测侧 lon / B-4 calendar 标注** | **未修复**（`MAX_PAIR_DIST_DEG=1.0` 原样） | `:56`、`:217` |

### ⚠️ 由此产生的一条**新**行动项（比 E-1 本身更紧迫）

`.normalize()` 修复**只去掉了一半误差**，且把 v2 ALL 从"偶然对齐"变成了"确定错位"：

- 现状（当前版本）：`t0` 归零后，`THW` 事件（ALL 侧标签 12:00 / XGHG 侧 00:00）都映射到**正确**的物理日索引；而 `MHW` 事件标签来自 POP SST，**= 物理日 + 1**，故 MHW 掩码统一**晚 1 天**。
- 后果：**四种组合（v1/v2 × ALL/XGHG）现在全部是 +1 天错位**；修复前 v2 ALL 因"12:00 取整"与"SST 标签 +1"两处误差相消而**恰好对齐**（本报告 E-1 实测 Δ=0）。
- 量级（本报告 E 节同法实测）：v2 ALL `t0归零` 使 compound 63154→62191（**−1.5%**）、75581→74707（−1.2%）、78973→78045（−1.2%）。
- **建议的最小修复**：在 `_load_sst_points` 返回前把 `time` 整体回退 1 天（`time = time - pd.Timedelta(days=1)`），或在 `cmd_compound` 中对 MHW 侧掩码使用 `shift=-1`。修复后应重跑 `detect --baseline xghg` 与 `compound --tag _x`，并按缓存指纹（`THRESH_VERSION`）确认阈值缓存同步失效。

---

## §1 配对链路（A1–A6）

### A1 复算 `cmd_pairs` 全链路计数 —— 【确认无误】

复算方式：

```
python results/phase6_audit_grid.py --only A1        # 逐行复刻 phase6_cesm.py:148-219
```

关键输出行：

```
[A1] POP 全球湿格点 (KMT>0): 86212
[A1] 映射容差窗口: 0.75*dlat=0.706806°, 0.75*dlon=0.937500°  (dlat=0.942408, dlon=1.250000)
[A1] 落在容差窗内的 POP 湿点: 2986  → 命中的 f09 格 (去重): 1231
[A1] f09 欧洲框 (49, 51): 海格点=1231, 陆格点=1268, 合计=2499
[A1] 陆地边缘格点 (binary_erosion 默认 border_value=0): 357
[A1] 最终配对数: 206 / 357 (上限 1.0°)
[A1] CSV 实测: 行数=206 (文件 206 行数据)
[A1] 唯一陆点=206, 唯一海点=191
[A1] 重复海点: 被 >1 个陆点共享的海点数=15, 多占的对数=15 (最多共享 2 个陆点)
[A1] dist_deg min/median/max = 0.281729 / 0.729999 / 0.999267
[A1] 与已落盘 coastal_pairs_cesm.csv 逐行一致: True
[A1] R 域文件 domains_land_cesm.csv: 206 点
```

- **206 对确认成立**，且与落盘 CSV 逐行一致（我独立重跑全链路后比对 `(land_lat_idx, land_lon_idx, ocean_lat_idx, ocean_lon_idx)` 四列）。
- f09 裁剪网格实测格距 **dlat=0.9424°**（=180/191，不是 0.9°）× **dlon=1.2500°**（=360/288）。代码注释 `phase6_cesm.py:30,56` 说"f09/gx1v6 都是 ~1° 网格"——纬度侧偏小 6%，经度侧偏大 25%。
- 真海岸点 **279** 个（见 A3 的 `border_value=1` 复算），实际配上 **206** 个 ⇒ **73 个真海岸陆点在 1.0 单位内找不到海点而被丢弃（占 26.2%）**。`dist_deg` 最大值 0.9993 紧贴上限 1.0，说明该上限是**紧约束**而非宽松门限。

### A2 映射容差与重复覆盖 —— 【有问题，低影响】

```
[A2] 每个 f09 海格被覆盖的 POP 湿点数: max=7, 中位=2, 只被 1 个覆盖的格数=173
[A2] 容差半宽 lat=0.7068° lon=0.9375°; 相邻格中心距 lat=0.9424° lon=1.2500°
     → 窗口重叠倍数 lat=1.50x lon=1.50x (>1 即重叠, argmin 取最近者)
[A2] 全球 POP 湿点 86212, 落在欧洲框内 2770, 通过 0.75 容差 2986 → 框内但被容差淘汰 -216
[A2] 只用框内 POP 点重算掩码: 海格点 1207 (vs 全量 1231); 仅靠框外点变成海的格数 = 24
[A2]   其中落在阵列边界行/列的 = 24/24; 经纬度样例 = [(39.11,-16.25),(40.052,-16.25),(40.995,-16.25),...]
[A2] POP(gx1v6) 欧洲框内湿点 2770 个; 最近邻间距 (cos 加权单位) p10/p50/p90 = 0.249/0.417/0.506 ≈ 46 km (中位)
```

- 容差半宽 0.75×格距对**两侧相邻格都成立**（重叠 1.5×），但代码用 `argmin`（`phase6_cesm.py:174-175`）只取最近格 ⇒ **一个 POP 湿点只标记 1 个 f09 格，无重复标记问题**。
- 反向：一个 f09 海格最多被 7 个 POP 湿点覆盖（中位 2），这本身无害（只是"该格是海"的证据更多）。
- 实测 POP(gx1v6) 欧洲框内有效分辨率：**最近邻间距中位 0.417 单位 ≈ 46 km**（p10/p90 = 0.249/0.506）⇒ 容差半宽 0.7068° 明显大于 POP 格距，所以"一个 f09 格被多个 POP 点覆盖"是必然结果（最多 7 个），符合预期。
- **发现**：`argmin` 对框外点做**边界夹取**（clamp），使 216 个框外湿点被算进容差、并让 24 个 f09 格（全部在 lon=−16.25 边界列，39–44°N，即大西洋侧）被判为海。物理上确为海洋，故无实际错误，但掩码确实受框外点影响。
- 海陆掩码**完全来自 POP `KMT`，未与 CAM landmask 交叉核对**（代码无此步骤）。若 CAM 与 POP 海陆不一致（近岸常见），会被整格判错——本审计只能指出该风险，**未判定**其实际误差量级。

### A3 阵列边界伪边缘 —— 【有问题，但未产生配对】

```
[A3] 阵列边界格点总数 196 (第0行/末行/第0列/末列)
[A3] 边界上的陆格点 84 —— 这些在 border_value=0 下必然被判为 edge
[A3] edge 总数 357; 其中落在阵列边界 84
[A3] 用 border_value=1 重算 edge 总数 279 (差值 = 纯伪边缘 78)
[A3] 206 对中, 来自「纯边界伪边缘」的配对: 0
[A3] 206 对中, 位于阵列边界上的配对: 6
[A3] 边界 edge 点中获得配对的: 6
[A3] 边界 edge 点中真海岸 (border_value=1 也算 edge): 6
```

- **数量与占比**：纯伪边缘 **78 个 / 357 个 edge = 21.9%**；边界陆格点共 84 个（另 6 个是真海岸）。
- **是否产生配对**：**否**。78 个伪边缘点的最近 POP 湿点距离均 > 1.0 单位，被 `phase6_cesm.py:199` 淘汰。清单见 `results/intermediate/audit/grid/A3_border_edge_points.csv`（含 `got_pair` 列）。
- 6 个位于阵列边界且获得配对的点，全部是 `border_value=1` 下也算 edge 的**真海岸**（样例：`(i=0, j=5, lat=28.7435, lon=−10.0)`）。
- 结论：`border_value=0` 是**真实的代码缺陷**，但本例中距离门限恰好兜住了它。属于健壮性问题：若将来放宽 `MAX_PAIR_DIST_DEG` 或更换域，会立即产生内陆伪配对。

### A4 KDTree cos 加权的物理含义 —— 【确认无误，口径需说明】

```
[A4] cos 加权空间定义: d = sqrt(dlat^2 + (dlon*cos(lat))^2)  [近似平面]
[A4] 206 对的 dist_deg min/med/max = 0.2817/0.7300/0.9993
[A4] 同 206 对真实大圆距离 gc_km min/med/max = 37.7/81.6/134.1 km
[A4] 换算系数 gc_km/dist_deg: min=79.71, med=112.21, max=152.38 km/单位
[A4] 1.0 单位 ≈ 112.2 km (≈ 1° 纬度 = 111.2 km)
[A4] 45N: 1 单位经度 = 78.72 km, 1 单位纬度 = 111.13 km, cos 加权把 1° 经度压缩为 0.7071 单位
[A4] 注: 建树用 cos(ocean_lat), 查询用 cos(land_lat), 两侧 cos 不同 → 最大失配 0.01414
[A4][观测侧对照] 2039 对, dist_deg med=0.1973, gc_km med=21.9, max=62.5, 换算 111.2 km/单位
```

- **45°N 处 1.0 单位**：纬度方向 = 111.13 km（=1°）；经度方向 = 78.72 km（=1°经度×cos45）。即该度量把"1 单位"归一为**约 1° 大圆角距 ≈ 112 km**，这正是 cos 加权的设计意图。
- `A4_pairs_with_gc.csv`：大圆距离 **max=134.1 km、median=81.6 km**。max/median 的换算系数 152.4/112.2 说明该平面近似在高纬与大连通差时**失真最大 36%**（建树与查询用不同 cos 是原因之一），但不足以改变配对结果。
- **口径结论**：`MAX_PAIR_DIST_DEG=1.0` 的物理含义 ≈ **112 km 允许分离**（观测侧 `MAX_GRID_DIST_DEG=0.5` ≈ **55.6 km**，实测观测侧 max 仅 62.5 km）。⇒ **模型侧配对的实际距离上限约为观测侧的 2.1 倍**，两套网格的"沿海配对"严格程度不可直接互译。

### A5 口径差异的文档登记情况 —— 【有问题（文档）】

复算方式：`python results/phase6_audit_grid.py --only A5`（全工作区 `*.py` / `*.md` 正则扫描，命中 39 行 .md + 101 行代码 → `A5_doc_scan.txt`）

**登记了模型侧口径的文档**：

| 文件:行 | 内容要点 |
|---|---|
| `results/复现报告.md:338` | "pairs（POP KMT 湿点映射 f09 → 陆缘 357 → KDTree 配对 206 对，上限 1.0°）" |
| `results/复现报告.md:344` | "观测 0.25°×1434 对 vs 模型 1°×206 对，…在两套网格上不可直接互译" |
| `results/复现报告.md:347` | 同上，列为"20 成员前必须决策"的缺口 #2 |

**未登记模型侧口径、只有观测侧数字的文档**：

| 文件:行 | 只有观测侧 |
|---|---|
| `AGENTS.md:81` | `MAX_GRID_DIST_DEG = 0.5°`，2039 对 / 1434 唯一海点 |
| `TECHNICAL_SPEC.md:214,787,790` | `MAX_GRID_DIST_DEG = 0.5`、2039 对 / 1434 海点 |
| `TECHNICAL_SPEC_PHASE_A.md:17,18,150,151,295` | 0.5° 上限、2039 对 / 1434 海点 |
| `docs/复现方案.md:155` | `MAX_GRID_DIST_DEG=0.5`，沿海对 1434 个 |

**结论**：模型侧 206 对 / 1.0° 只在 `results/复现报告.md` 出现（3 处，且其中 2 处是"已知缺口"列表而非规范定义）；**四份权威/约束文档（AGENTS.md、TECHNICAL_SPEC.md、TECHNICAL_SPEC_PHASE_A.md、docs/复现方案.md）完全没有登记**。差异本身被承认过，但**没有升格为规范条目**，Phase 6 全量/写作阶段极易被当成同一口径引用。建议：在 `config.py` 旁增加 `CESM_MAX_PAIR_DIST_DEG` 并写入 `TECHNICAL_SPEC.md` §3.5 的偏差表。

### A6 `_load_sst_points` 块读校验 —— 【确认无误】

```
[A6] SST dims = ('time','nlat','nlon'), KMT dims = ('nlat','nlon') (nlat=384, nlon=320, time=2191)
[A6] 206 对配对点 KMT[pj, pi]: min=3.0, max=50.0, <=0 的点数=0
[A6] 块读 v[:, 277:366, :] = (2191, 89, 320) (249.6 MB) 耗时 3.1 s
[A6] rows=block[:, pj-j0, :] shape=(2191, 206, 320); take_along_axis(..., pi) → got shape=(2191, 206)
[A6] pair#0 (nlat=277, nlon=26): 标量 isel 耗时 3.1 s; 全时段 max|块读-isel| = 0.000e+00 一致
[A6] pair#100 (nlat=320, nlon=35): 全时段 max|块读-isel| = 0.000e+00 一致
[A6] pair#205 (nlat=353, nlon=79): 全时段 max|块读-isel| = 0.000e+00 一致
[A6] 另抽 21 对做全时段交叉: max|diff|=0.000e+00, 不一致对数=0
```

- `pj = ocean_lat_idx` **是** KMT/SST 的 nlat（第 1 维）索引，`pi = ocean_lon_idx` **是** nlon（第 2 维）索引 —— 与 `SST(time,nlat,nlon)` 完全对齐。决定性证据：206 个配对点的 `KMT[pj,pi]` **全部 > 0**（min=3, max=50）；若维度颠倒会大面积 ≤0 并把整列置 NaN。
- 3 个抽样点（pair#0/#100/#205）**全时段 2191 天逐值比对，max|块读−isel| = 0.000e+00**；另抽 21 对同样 0.000e+00。
- 副产品性能数据：`v[:, j0:j1, :]` 一次大读 249.6 MB / 3.1 s，每个成员每段一次，可接受。
- ⚠️ 审计过程中发现（**非被审计代码的问题**）：在本机对 1 GB 级 POP 文件使用 xarray 的**矢量 isel**（`isel(nlat=DataArray(pj), nlon=DataArray(pi))`）会退化为全量读，>300 s 未完成。被审计代码 `_load_sst_points` 用的是 netCDF4 块读，未踩此坑；但 `_pooled_threshold_t2m` / `_detect_thw_member_ext` / `_obs_annual_threshold` 用的是矢量 isel（对象是 80 MB 小文件，实测可用）。

---

## §2 经度与坐标（B1–B4）

### B1 经度 0–360 vs ±180 —— 【CESM 侧确认无误；观测侧有问题（潜伏）】

```
[B1] POP TLONG 原始范围: 0.0147 .. 359.9960 (>180 的点数=64492/122880)
[B1] np.where(tlon>180, tlon-360, tlon) 之后: -179.9967 .. 179.9992
[B1] 欧洲框 lon 范围: -16.2500 .. 46.2500
[B1] 结论: 转换后仍有 >180 的点 0 个
[B1] coastal_pairs_cesm.csv  ocean_lon = -17.8450..47.2025 (已 -180..180)
[B1] coastal_pairs_cesm.csv  land_lon  = -16.2500..46.2500
[B1][观测侧] coastal_pairs.csv ocean_lon = 0.1250..359.8750  ← **0..360 未换算**
[B1][观测侧] land_lon = -24.8750..44.8750
[B1] mhw_ALL_001.csv: lon -17.8450..47.2025 (n=10069)    ← 12 个 mhw_*.csv 全部同一范围
[B1] mhw_ALL_001.csv 的 (lat_idx,lon_idx) 集合 ⊆ pairs 海点集合: True (191/191)
[B1] mhw lon 与 pairs ocean_lon 一致: True (max|diff|=3.553e-15)
[B1][观测侧] mhw_events_R_global.csv lon 范围 -25.1250..45.3750
```

- **POP TLONG 原始 0.0147–359.9960**（64492/122880 个点 >180），换算后 **−179.9967–179.9992**，欧洲框内无残留 >180 的点。
- **配对表与 mhw_*.csv 的 lon 符号一致**：12 个 `mhw_*.csv`（v1+v2，6 成员组）lon 全部为 −17.8450..47.2025，与 `coastal_pairs_cesm.csv` 的 `ocean_lon` 逐点一致（max|diff|=3.6e-15）。阈值（`_pooled_threshold_sst`）与检测（`_detect_mhw_member`）都只用**列索引**取值，与 pairs 同源 ⇒ **CESM 侧配对/阈值/检测三处经度口径全程一致（无遗漏换算）**。
- **发现（观测侧）**：`python/coastal_mask.py:77` 算了 `ocean_lons_unified`（−180..180）**但 :124 写入 CSV 的却是原始 `ocean_lon[oj]`（0..360）**。于是观测侧出现**两张 lon 约定不同的表**：`coastal_pairs.csv`（0–360，land_lon 却是 −180..180）vs `mhw_events_R_global.csv`（−180..180）。已 grep 全 `python/*.py`：当前**没有任何消费者用 `pairs.ocean_lon` 做数值运算**（`compound_events._pair_maps` 只用整型索引），故**暂无实际影响**；但 `land_lon − ocean_lon` 一算就会差 360°，属高危潜伏陷阱。

### B2 坐标对齐（纬度翻转） —— 【确认无误：无翻转，数据未错位】

> **明确回答：源 XGHG `lat` 是升序；`.sel` 之后**没有**发生纬度翻转；陆地/海洋数据**没有**错位。**

```
[B2] 参考(已裁剪 AWS 成品) lat 28.7435→73.9791, 升序=True
[B2] 源 XGHG seg1(1920-2005): lat -90.0000→90.0000 升序=True; lon 0.0000→358.7500 (0-360 约定=True)
[B2] 源 XGHG seg2(2006-2080): lat -90.0000→90.0000 升序=True; lon 0.0000→358.7500 (0-360 约定=True)
[B2] .sel 之后 lat 序列 = 28.7435→73.9791, 升序=True
[B2] .sel 返回的 lat 是否 == ref_lat 顺序: True
[B2] 落盘 XGHG_001_T2m.nc: lat 28.7435→73.9791 (== ref: True), lon == ref: True
[B2] 探针 2001-07-15 (merged t=560, 源日期 2001-07-15): max|merged-手工NN| = 0.0000 °C  (对照: 纬度翻转假设 40.4327 °C)
[B2] 探针 2004-01-20 (merged t=1479, 源日期 2004-01-20): max|merged-手工NN| = 0.0000 °C  (对照: 纬度翻转假设 38.2357 °C)
[B2] 探针 2006-07-15 (merged t=2385, 源日期 2006-07-15): max|merged-手工NN| = 0.0000 °C  (对照: 纬度翻转假设 42.0674 °C)
[B2] 探针 2020-08-10 (merged t=7521, 源日期 2020-08-10): max|merged-手工NN| = 0.0000 °C  (对照: 纬度翻转假设 36.9847 °C)
```

- 代码风险点（`phase6_cesm.py:125-127`）确实存在：`da.sel(...)` 后紧跟 `assign_coords(lat=ref_lat.values)`，**若源 lat 为降序且 `.sel` 保留源序，标签会被整体翻转**。
- **实测排除了该风险**：源 f09 全球网格 lat 从 −90 到 +90 **升序**（`b.e11.B20TRLENS_RCP85...TREFHT...nc`），`.sel` 返回的 lat 序列已升序且与 `ref_lat` 完全相等。
- **独立探针**（绕过 xarray，手工做经度换算 + 最近邻索引）4 个日期（跨两段：2001/2004/2006/2020，各自源文件不同）**max|merged−手工NN| = 0.0000 °C**；作为对照，假设纬度翻转则差 **36.98–42.07 °C**。⇒ 对齐正确，**结论为"否（未翻转）"**。
- 详见 `results/intermediate/audit/grid/B2_alignment_probe.csv`（含 `verdict` 列）。

### B3 K→°C 换算与 SST 单位 —— 【确认无误】

```
[B3] XGHG TREFHT seg1: units='K', min=174.960, max=319.979, dtype=float32
[B3] XGHG TREFHT seg2: units='K', min=160.371, max=320.184, dtype=float32
[B3] ALL TREFHT(AWS 成品): units='K', min=226.050, max=321.108, dtype=float32
[B3] 落盘 ALL_001_T2m.nc:  units='degC', min=-47.100, max=47.958
[B3] 落盘 XGHG_001_T2m.nc: units='degC', min=-56.988, max=45.766
[B3]   XGHG_001_T2m.nc 年 2005: 均值=8.694 °C (若漏减 273.15 应 ≈ 281.8)   [2006: 8.819, 2020: 9.282]
[B3]   ALL_001_T2m.nc  年 2005: 均值=10.470 °C (若漏减 273.15 应 ≈ 283.6)  [2006: 10.083, 2020: 11.414]
[B3] ALL SST seg1: units='degC', min=-2.479, max=33.794   [XGHG seg1: -2.558..33.444]
[B3] ALL SST seg2: units='degC', min=-2.496, max=34.862   [XGHG seg2: -2.880..33.659]
[B3] 代码佐证: '_load_sst_points' 内出现 '273.15' 的次数 = 0
```

- **TREFHT 两段（1920-2005 / 2006-2080）units 均为 `'K'`**，量级 160–320；判据 `units.startswith("K") or float(da.max())>150` 的**两个条件都命中**，两段都被正确减 273.15（落盘 `degC`，两段年份均值 8.7–11.4 °C，量级正确）。
- **SST units 均为 `'degC'`**，范围 −2.88–34.86 ⇒ **不需要换算**，`_load_sst_points` 无 273.15 是**正确**的（代码中 `273.15` 出现 0 次）。
- 小提示（非缺陷）：`startswith('K')` 对 `'kelvin'`（小写）不命中，届时仅靠 `>150` 兜底；本数据双命中，无风险。

### B4 时间解码 / 日历 / doy 边界 —— 【有问题：calendar 标注与数据不符 + ALL SST 有 1 天物理缺口】

```
[B4] T2m merged XGHG_001: 文件 calendar 属性='proleptic_gregorian', 解码后 dtype=datetime64[ns],
     n=8030, 2000-01-01~2021-12-31
[B4]   doy 集合: min=1, max=366, 是否含 366=True, 唯一 doy 数=366
[B4] SST ALL  seg1: calendar='proleptic_gregorian', n=2191, 2000-01-01~2006-01-01
[B4] 11 天圆形窗 win=[(d+k-1)%365+1 for k in -5..5]: d=1..365 全范围 越界/重复的 d 个数 = 0
[B4] 窗口 d=1  -> [361, 362, 363, 364, 365, 1, 2, 3, 4, 5, 6]
[B4] 窗口 d=365-> [360, 361, 362, 363, 364, 365, 1, 2, 3, 4, 5]
[B4] ALL  SST 段接缝: seg1 末 2006-01-01 → seg2 首 2006-01-03  步长=2 天 (!! 有缺口)
[B4] XGHG SST 段接缝: seg1 末 2006-01-01 → seg2 首 2006-01-02  步长=1 天 (连续)
```

- **calendar 属性 = `proleptic_gregorian`，但 raw 文件的真实 calendar 是 `noleap`**（`raw/...pop.h.nday1.SST...nc`: `{'units':'days since 0000-01-01 00:00:00','calendar':'noleap'}`；CAM 侧 `{'units':'days since 1920-01-01','calendar':'noleap'}`）。成因：`download_cesm1le.py:_to_datetimeindex` 用 `CFTimeIndex.to_datetimeindex()` 把 noleap 日期按同名 Y-M-D 映射为 `datetime64`，写盘时丢了日历信息。
- 实测解码成功（`pd.DatetimeIndex` 无异常，dtype `datetime64[ns]`），序列中 **2-29 标签数 = 0**（noleap 正确），跨闰年处出现 6 处 +2 天步进。
- **`doy` 集合实测 min=1 / max=366（含 366）**：因为 2000/2004/…/2020 的 **12-31 在标准日历下 doy=366**。这一点与 "noleap ⇒ doy 只到 365" 的直觉相反，**必须按 366 行表处理**。
- **窗口公式不越界**：`(d+k-1)%365+1` 在 d=1..365 全域得到 1..365、无重复（d=1→[361..365,1..6]；d=365→[360..365,1..5]）✓。`thresh` 366 行，`doy-1 ∈ 0..365` 恒在范围内 ✓。⚠️ 但 **doy=366 会取到第 366 行**——见 S-2。
- **POP 标签 = 物理日 + 1（实证）**：raw B20TR POP `time_bound[0]=[675251.0417, 675252.0]`、首条 stamp 675252 = 1850-01-03，文件名却是 `...SST.18500102-20051231...`；末条 stamp 732190 = 2006-01-01，`time_bound=[732189,732190]`，文件名末尾 20051231 —— 两条元数据独立互证"记录标签 = 其日均区间的**结束**时刻 = 物理日 + 1"。对照 CAM TREFHT 的 `date` 变量（首条 19200101，`time_bnds=[t,t+1]`）⇒ **T2m 标签 = 物理日，SST 标签 = 物理日 + 1**。
- **ALL SST 段接缝存在 1 个物理日缺口**：B20TR 段（物理到 2005-12-31）+ RCP85 段（文件名起点 20060102 ⇒ 物理从 2006-01-02 起）⇒ **物理 2006-01-01 缺失**；因标签 +1，表现为标签从 `2006-01-01` 直跳 `2006-01-03`。XGHG 侧 RCP85 SST 文件名起点是 20060101 ⇒ **无缺口**。⇒ 该项在 ALL/XGHG 之间**不对称**（P1）。`_load_sst_points` 只做 `pd.DatetimeIndex` 拼接、不检查连续性，故该缺口会被静默桥接（`_run_events` 按行号相邻判断连续）。

---

## §3 XGHG 拼接与接缝（C1–C3）

### C1 段文件 / 时间范围 / 天数 / 连续性 —— 【确认无误】

```
[C1] XGHG 001: 2 段
[C1]   b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.19200101-20051231_2000-2021.nc  n=2190  2000-01-01~2005-12-31
[C1]   b.e11.B20TRLENS_RCP85.f09_g16.xghg.001.cam.h1.TREFHT.20060101-20801231_2000-2021.nc  n=5840  2006-01-01~2021-12-31
[C1] 落盘 XGHG_001_T2m.nc: n=8030 2000-01-01~2021-12-31, 重复=False, 严格单调=True, 步长集合=[1,2]
[C1] XGHG 001: 2 天步进 6 处 ['2000-02-28→2000-03-01','2004-02-28→2004-03-01','2008-02-28→2008-03-01',
                            '2012-02-28→2012-03-01','2016-02-28→2016-03-01','2020-02-28→2020-03-01']; 序列中 2-29 标签数=0
[C1] XGHG 001: 缺口判定 —— 以 noleap(365天) 计 2000-01-01..2021-12-31 = 8030 天, 实测 8030 天 → 无缺口
```

- 成员 **001 / 002 / 003 完全同构**：各 2 段，**2190 天（2000-01-01~2005-12-31）+ 5840 天（2006-01-01~2021-12-31）= 8030 天**，= 22 年 × 365 天（noleap）。
- 落盘文件 **无重复、严格单调**；步长集合 {1,2} 中的 6 处 2 天步进**全部**是闰年 2-28→3-1（noleap 缺 2-29），属正确行为；**2-29 标签数 = 0**。
- ⇒ **2000-01-01..2021-12-31 连续 8030 天，无重复无缺口** ✓

### C2 接缝跳跃检验 —— 【确认无误：无不连续证据】

```
[C2] T2m XGHG(两段拼接,2005-12-31|2006-01-01 为文件接缝)
[C2]   |ΔT2m| 全域均值: 接缝=2.5539 °C; 全体 8029 个日间跳变 p50=1.2756 p95=2.4523 p99=3.0712 °C
[C2]   跨年(12-31→01-01)跳变 21 个: p50=1.9535, 接缝在其中排名 15/21 (分位 67%)
[C2]   同季节基准更公平: 接缝 2.5539 vs 其它跨年跳变 median 1.9535 → 无明显不连续
[C2] T2m ALL(单段,无文件接缝→仅作参照): 接缝=2.0303 °C; 跨年 21 个 p50=1.6867 (76 分位)
[C2] SST XGHG 接缝 |ΔSST| 全网格均值 = 0.0544 °C (seg1 末条标签 2006-01-01 → seg2 首条标签 2006-01-02)
[C2]   随机 120 个日间跳变: p50=0.0442 p95=0.0529 p99=0.0566 → 接缝分位 96.7%
[C2]   同季节(12/1月) 60 个跳变: p50=0.0501, p95=0.0544 → 接缝分位 95.0% (偏高但在分布内)
[C2] SST ALL 接缝 |ΔSST| 全网格均值 = 0.0523 °C (seg1 末条标签 2006-01-01 → seg2 首条标签 2006-01-03)
[C2]   同季节(12/1月) 60 个跳变: p50=0.0524, p95=0.0583 → 接缝分位 48.3% (无明显不连续)
```

- **T2m XGHG**：接缝跳变 2.5539 °C，看似在全体分布的 96 分位，但用**同季节基准**（其它 20 个 12-31→01-01 跳变，中位 1.9535）衡量只排 15/21（67 分位）⇒ **正常冬季日间变率，无接缝不连续**。
- **T2m ALL**：`find_t2m_segments("ALL", m)` 只返回 1 个文件（AWS 产品整段），**不存在文件接缝**；其 2.0303 °C 仅作跨年参照。
- **SST XGHG**：0.0544 °C，在冬季分布 95 分位（偏高但未越界）；**SST ALL**：0.0523 °C 恰在冬季中位（48 分位）。⇒ 无单位/坐标跳变证据（若一段 K 一段 degC，|Δ| 会是 ~273）。
- ⚠️ 归因提示：ALL SST 的接缝实际跨 **2 个物理日**（含 B4 的 1 天缺口），并非严格 1 天，故其 |Δ| 不可与 XGHG 直接等量比较。

### C3 `xr.concat` 静默风险 —— 【确认无误（健壮性缺口 P2）】

```
[C3] XGHG TREFHT: units A='K' B='K' → 一致;  dtype A=float32 B=float32; shape A=(2190,192,288) B=(5840,192,288)
[C3]   lat 升序 A=True B=True; A==B: True
[C3]   lon A 0.0000..358.7500 B 0.0000..358.7500; A==B: True
[C3]   attrs 仅 A 有=[], 仅 B 有=[]; attrs 同名但取值不同: []
[C3] XGHG SST: units A='degC' B='degC'; TLAT/TLONG A==B: True; KMT: A==B: True, 非零格点数=86212
[C3] ALL  SST: units A='degC' B='degC'; TLAT/TLONG A==B: True; KMT: A==B: True
```

- **实测无静默错误**：TREFHT 两段 `units/dtype/lat/lon/attrs` 完全一致（同名属性无冲突）；SST 两段 `units/TLAT/TLONG/KMT` 完全一致。故 `xr.concat(dim="time")`（`phase6_cesm.py:135`）不会因单位或坐标不一致而拼错。
- **但代码无任何断言**：`xr.concat` 默认 `join='outer'`，且不校验 units/shape；`cmd_prepare` 的 `assert` 只查时间重复（`phase6_cesm.py:137`）。若未来某段单位变为 `K` 或 lat 变序，会**静默**产出错误文件。属健壮性缺口（P2），建议加 `units` 与 `np.allclose(lat, ref_lat)` 断言。

---

## §4 复算命令

```bat
:: 全量（约 8 分钟，产物写入 results/intermediate/audit/grid/）
python results\phase6_audit_grid.py                 > results\intermediate\audit\grid\log_full.txt 2>&1

:: 分段
python results\phase6_audit_grid.py --only A1,A2,A3,A4    :: 配对链路计数/容差/边界伪边缘/cos 加权
python results\phase6_audit_grid.py --only A5,A6          :: 文档口径登记 / 块读校验
python results\phase6_audit_grid.py --only B1,B2,B3,B4    :: 经度 / 坐标对齐 / K→°C / 时间解码
python results\phase6_audit_grid.py --only C1,C2,C3       :: 拼接 / 接缝 / concat 风险
python results\phase6_audit_grid.py --only E,E2           :: 标签对齐 + PR/FAR 敏感度（副产物）
python results\phase6_audit_grid.py --only S              :: T2m 阈值空间塌缩（P0，副产物）
python results\phase6_audit_grid.py --list                :: 列出全部段号
```

**产物清单**（`results/intermediate/audit/grid/`）：

| 文件 | 内容 |
|---|---|
| `audit_grid_summary.json` | 全部关键数字的结构化汇总 |
| `A3_border_edge_points.csv` | 84 个边界 edge 点的经纬度 + `got_pair` 标记 |
| `A4_pairs_with_gc.csv` | 206 对 + 大圆距离 `gc_km` + 换算系数 |
| `A5_doc_scan.txt` | 全工作区口径关键词命中（.md 39 行 / 代码 101 行） |
| `B2_alignment_probe.csv` | 4 个纬度翻转探针 + `verdict` |
| `S_exceedance_by_point.csv` | 206 陆点逐点超阈率（塌缩阈值 vs 正确阈值） |
| `recomputed_thresh_t2m.npz` | 独立复算的 T2m 阈值：`src`（现行源码公式）/ `fix`（正确逐点公式） |
| `log_full.txt` 及分段日志 | 原始输出。**分段日志（log_A / log_A56 / log_A6B1 / log_B234 / log_C13 / log_C2 / log_C2E / log_E2 / log_S / log_A2S）是本报告各节数字的直接出处**；`log_full.txt` 为一次性全量 roll-up（等价复现，耗时约 8 分钟） |

---

## §5 审计边界与未判定项

1. **A2 未判定**：海陆掩码完全来自 POP `KMT`，未与 CAM landmask 交叉核对。近岸 CAM/POP 海陆不一致的实际误差量级**未判定**（需 CAM landmask 对照实验）。
2. **A3 未判定**：`border_value=0` 的伪边缘本次恰好被 1.0 单位门限兜住；若放宽门限或扩大域，伪配对数量**未判定**。
3. **E 段的"正确对齐"以 POP 标签=物理日+1 为前提**，该前提由 raw 文件 `time_bound` + 文件名两条独立元数据互证；若上游 GDEX/裁剪流程对该约定另有处理，结论需相应修正。
4. 本审计**未修改** `python/` 下任何文件、`results/intermediate/cesm/` 下任何既有文件；S-1/E-1 触及检测与复合口径，可能与 detection/compound 审计员结论重叠，以交叉印证为准。
