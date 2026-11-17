# logs/ 清理清单（2026-11-17）

本目录是工作日志与一次性诊断脚本的堆积地，**不入 Git**。2026-11-17 做了第一次清理：

- 清理前：387 个文件 / 17.1 MB（198 个 .log、86 个 .py、68 个 .err、11 个 .ps1、7 个 .out、1 个 3.5 MB 的 .dods）
- 本次删除：153 个（一次性探针脚本 `_probe_*` / `_dap*` / `_tmp_*` / `_fix*` / `_cmp_v*`、空 `.err`、`.out`、`.dods`、pid 文件）
- 保留：236 个 —— 文档中被引用的脚本与日志（证据链）+ 仍可复用的入口/预计算脚本 + 论文原文抽取件

## 保留的脚本（可直接复用）

| 文件 | 用途 |
|---|---|
| `_run_v12w50.ps1` | **主口径一键全链**（v12w50，5.7 min） |
| `_run_v5_clim.ps1` | 共用 XGHG 冷基准敏感性口径（`_v5`） |
| `_run_v8_all.ps1` | `--baseline all`（w=1）**已证伪**口径，仅作反例 |
| `_run_v9_scan.ps1` / `_run_v11_scan.ps1` / `_run_v12_scan.ps1` | θ / 双世界偏移 / w 扫描 |
| `_cmp_ci.py` | **判“残差是噪声还是真差”首选**：五档 + bootstrap CI + 论文 IN/out |
| `_cmp_gev_tags.py` | 多 tag 的图4/Table 1 横向对照 |
| `_diag_region_sens.py` | 域敏感性（地中海框 vs 全欧配对，决定性对照） |
| `_diag_fig6_region.py` / `_diag_fig6_stat.py` | 图6 区域四变体 / 逐格点分布与 RP 口径诊断 |
| `_diag_v8_metric.py` / `_diag_exp_series.py` / `_diag_emp_rp.py` | 暴露量纲 / 区域年暴露序列 / GEV vs 经验映射 |
| `_diag_delta_clim.py` / `_diag_obs_bias.py` | 两实验气候态差 δ / CESM 相对观测偏差 β |
| `_pairs_check.py` / `_audit_cesm80.py` / `audit_yearly_d2m.py` | 配对集复核 / CESM 80 件体检 / d2m 年度文件审计 |
| `_check_final_report.py` | 终版 docx 结构核对 |
| `_precompute_thresh.py` / `_precompute_t2m.py` | 阈值缓存预热 |

## 本次删除的文件（含首行说明，便于知道当年在查什么）

| 文件 | 大小 | 修改时间 | 首行/说明 |
|---|---|---|---|
| `_audit_fix.py` | 4.9 KB | 2026-11-17 17:40 | def edit(path, pairs): |
| `_audit_ocn_files.py` | 1.0 KB | 2026-10-28 17:32 | bad = [] |
| `_cesm_atm_shard1.err` | 1.2 KB | 2026-10-27 23:03 | — |
| `_cesm_atm_shard2.err` | 2.3 KB | 2026-10-27 23:25 | — |
| `_cesm_atm_shard3.err` | 2.3 KB | 2026-10-27 23:14 | — |
| `_cesm_atm_shard4.err` | 1.2 KB | 2026-10-27 23:03 | — |
| `_cesm_atm_shard5.err` | 1.2 KB | 2026-10-27 23:03 | — |
| `_cesm_atm_shard6.err` | 2.3 KB | 2026-10-27 23:33 | — |
| `_cesm_dap2_atm_shard0.err` | 0.0 KB | 2026-10-28 10:10 | — |
| `_cesm_dap2_atm_shard1.err` | 0.0 KB | 2026-10-28 10:08 | — |
| `_cesm_dap2_atm_shard1b.err` | 0.0 KB | 2026-10-28 10:43 | — |
| `_cesm_dap2_atm_shard2.err` | 0.0 KB | 2026-10-28 10:08 | — |
| `_cesm_dap2_atm_shard3.err` | 0.0 KB | 2026-10-28 10:08 | — |
| `_cesm_dap2_atm_shard4.err` | 0.0 KB | 2026-10-28 10:08 | — |
| `_cesm_dap2_atm_shard5.err` | 0.0 KB | 2026-10-28 10:08 | — |
| `_cesm_dap2_atm_shard6.err` | 0.3 KB | 2026-10-28 10:08 | — |
| `_cesm_dap2_atm_shardA.err` | 0.0 KB | 2026-10-28 11:40 | — |
| `_cesm_dap2_atm_shardB.err` | 0.0 KB | 2026-10-28 11:40 | — |
| `_cesm_dap2_ocn_shard0.err` | 0.0 KB | 2026-10-28 11:49 | — |
| `_cesm_dap2_ocn_shard1.err` | 0.0 KB | 2026-10-28 11:49 | — |
| `_cesm_dap2_ocn_shard2.err` | 0.0 KB | 2026-10-28 11:49 | — |
| `_cesm_dap2_ocn_shard3.err` | 0.0 KB | 2026-10-28 11:49 | — |
| `_cesm_dap2_ocn_shard4.err` | 0.0 KB | 2026-10-28 11:49 | — |
| `_cesm_dap2_ocn_shard5.err` | 0.0 KB | 2026-10-28 11:49 | — |
| `_cesm_dap2_ocn_shard6.err` | 0.3 KB | 2026-10-28 10:08 | — |
| `_cesm_ocn_001.err` | 0.0 KB | 2026-10-28 09:27 | — |
| `_check_006.py` | 0.5 KB | 2026-10-28 09:29 | p = r"D:\2607compound\data\CESM1-LE\proc\trefht_all_006_2000-2021.nc" |
| `_check_clim.py` | 0.5 KB | 2026-11-07 23:54 | pdf = pd.read_csv(p6.PAIRS_CSV) |
| `_check_numbers.py` | 1.1 KB | 2026-11-17 17:40 | t1 = list(csv.DictReader(io.open("results/tables/table1_v12w50.csv", encoding="utf-8"))) |
| `_check_refs.py` | 0.5 KB | 2026-11-17 17:40 | docs = ["results/图版对照表.md", "results/复现报告.md", "待办.md", "AGENTS.md"] |
| `_cmp_agg.py` | 0.3 KB | 2026-11-08 00:57 | for tag in ("v5","v5e"): |
| `_cmp_all_xghg.py` | 0.6 KB | 2026-11-08 01:42 | for var in ("trefht","sst"): |
| `_cmp_exp.py` | 0.5 KB | 2026-11-08 00:58 | d=pd.read_csv("results/intermediate/cesm/exposure_members_v5e.csv") |
| `_cmp_thresh.py` | 0.5 KB | 2026-11-07 20:14 | f = sorted(glob.glob(r"results\intermediate\cesm\thresh_t2m_xghg_v3_w11_loo_1983-2012_*001 |
| `_cmp_v11.py` | 0.7 KB | 2026-11-08 18:06 | P={"marine":[2.30,3.80,6.30,13.4,24.0],"terrestrial":[1.26,1.46,1.75,2.44,3.26],"compound" |
| `_cmp_v12.py` | 0.6 KB | 2026-11-08 18:12 | P={"marine":[2.30,3.80,6.30,13.4,24.0],"terrestrial":[1.26,1.46,1.75,2.44,3.26],"compound" |
| `_cmp_v12b.py` | 0.5 KB | 2026-11-08 18:17 | P={"marine":[2.30,3.80,6.30,13.4,24.0],"terrestrial":[1.26,1.46,1.75,2.44,3.26],"compound" |
| `_cmp_v567.py` | 2.7 KB | 2026-11-08 09:44 | PAPER = { |
| `_cmp_v5_v6.py` | 0.5 KB | 2026-11-08 01:26 | for tag in ("_v5","_v6"): |
| `_cmp_v5_v6b.py` | 1.1 KB | 2026-11-08 01:41 | rows = [] |
| `_cmp_v7e.py` | 1.0 KB | 2026-11-08 09:50 | P={"marine":{50:11.5,100:20.7},"terrestrial":{100:3.2},"compound":{100:8.0}} |
| `_dap1year.dods` | 3567.0 KB | 2026-10-27 23:25 | — |
| `_dap2_dbg.py` | 0.7 KB | 2026-10-27 23:29 | sys.path.insert(0, "python") |
| `_dap2_dbg2.py` | 0.9 KB | 2026-10-27 23:30 | sys.path.insert(0, "python") |
| `_dap2_fix.py` | 0.9 KB | 2026-10-27 23:42 | sys.path.insert(0, "python") |
| `_dap2_ocn_probe.py` | 0.9 KB | 2026-10-28 09:11 | u = "https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/ocn/pro |
| `_dap2_ocn_test1.py` | 1.0 KB | 2026-10-28 09:13 | ref_p = r"D:\2607compound\data\CESM1-LE\proc\b.e11.B20TRC5CNBDRD.f09_g16.001.pop.h.nday1.S |
| `_dap2_ocn_test3.py` | 0.8 KB | 2026-10-28 09:19 | ref = xr.open_dataset(r"D:\2607compound\data\CESM1-LE\proc\b.e11.B20TRC5CNBDRD.f09_g16.001 |
| `_dap2_path_test.py` | 0.9 KB | 2026-10-27 23:46 | sys.path.insert(0, "python") |
| `_dap2_smoke.py` | 1.3 KB | 2026-10-27 23:27 | sys.path.insert(0, "python") |
| `_dap_block_test.py` | 1.2 KB | 2026-10-27 23:15 | sys.path.insert(0, "python") |
| `_dap_smoke.py` | 1.0 KB | 2026-10-27 22:57 | sys.path.insert(0, "python") |
| `_dist.py` | 0.5 KB | 2026-11-08 09:46 | for tag in ("v5","v7"): |
| `_dodsrc` | 0.1 KB | 2026-10-27 22:38 | — |
| `_fix27.py` | 0.4 KB | 2026-11-17 14:33 | p="AGENTS.md" |
| `_fix27b.py` | 1.8 KB | 2026-11-17 14:33 | p="AGENTS.md" |
| `_fix28.py` | 3.1 KB | 2026-11-17 14:52 | p = "AGENTS.md" |
| `_gdex_par_test.py` | 1.9 KB | 2026-10-27 22:22 | 用法: python logs\_gdex_par_test.py |
| `_gev_detail.py` | 0.5 KB | 2026-11-08 09:45 | for tag in ("v5","v6","v7"): |
| `_migrate_batches.py` | 7.1 KB | 2026-11-17 14:32 | # -*- coding: utf-8 -*- |
| `_peek_paper.py` | 0.4 KB | 2026-11-08 10:16 | # -*- coding: utf-8 -*- |
| `_probe_adopt.py` | 0.8 KB | 2026-10-29 10:07 | sys.path.insert(0, r"D:\2607compound\python") |
| `_probe_c.err` | 0.0 KB | 2026-10-28 11:32 | — |
| `_probe_c.out` | 0.1 KB | 2026-10-28 11:40 | — |
| `_probe_das.err` | 0.0 KB | 2026-10-28 11:35 | — |
| `_probe_das.out` | 0.1 KB | 2026-10-28 11:36 | — |
| `_probe_das.py` | 0.6 KB | 2026-10-28 11:35 | base = "https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/atm/ |
| `_probe_dds.err` | 0.0 KB | 2026-10-28 11:34 | — |
| `_probe_dds.out` | 0.1 KB | 2026-10-28 11:35 | — |
| `_probe_dds.py` | 0.8 KB | 2026-10-28 11:34 | base = "https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/atm/ |
| `_probe_jobid.py` | 0.7 KB | 2026-10-29 10:07 | sys.path.insert(0, r"D:\2607compound\python") |
| `_probe_jobid2.py` | 0.7 KB | 2026-10-29 10:08 | sys.path.insert(0, r"D:\2607compound\python") |
| `_probe_speed.py` | 0.7 KB | 2026-11-07 18:36 | sys.path.insert(0, r"python") |
| `_probe_time.err` | 1.0 KB | 2026-10-28 11:44 | — |
| `_probe_time.out` | 0.7 KB | 2026-10-28 11:43 | — |
| `_probe_time.py` | 0.8 KB | 2026-10-28 11:39 | cases = { |
| `_probe_xghg020.py` | 1.3 KB | 2026-10-28 11:05 | u = "https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/atm/pro |
| `_probe_xghg020b.py` | 0.6 KB | 2026-10-28 11:09 | u = "https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/atm/pro |
| `_probe_xghg020c.py` | 0.8 KB | 2026-10-28 11:24 | u = "https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/atm/pro |
| `_pydap_probe.py` | 0.7 KB | 2026-10-27 22:46 | u = ("https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/" |
| `_pydap_probe2.py` | 0.7 KB | 2026-10-27 22:46 | u = ("https://tds.gdex.ucar.edu/thredds/dodsC/files/d651027/cesmLE/CESM-CAM5-BGC-LE/" |
| `_ref_timechk.py` | 0.8 KB | 2026-10-28 10:24 | a = xr.open_dataset(r"D:\2607compound\data\CESM1-LE\proc\b.e11.B20TRC5CNBDRD.f09_g16.001.p |
| `_scan_refs2.py` | 0.5 KB | 2026-11-17 17:41 | docs = glob.glob("*.md") + glob.glob("results/*.md") + glob.glob("docs/*.md") + glob.glob( |
| `_show_gev.py` | 0.8 KB | 2026-11-08 00:14 | d = json.load(open(r"results\tables\phase6_gev_v5.json", encoding="utf-8")) |
| `_sizes.py` | 0.3 KB | 2026-11-17 14:32 | p="AGENTS.md" |
| `_sst_slab_probe.py` | 1.4 KB | 2026-10-27 22:32 | 用法: python logs\_sst_slab_probe.py |
| `_sweep_peek.py` | 0.5 KB | 2026-11-08 00:15 | for agg in ("eur_p90", "eur_mean", "med_mean", "med_p90"): |
| `_sync28.py` | 3.4 KB | 2026-11-17 14:52 | def edit(path, pairs): |
| `_tmp_cmp.py` | 1.1 KB | 2026-11-17 14:27 | def load(p): |
| `_tmp_patch.py` | 0.6 KB | 2026-11-17 14:20 | p=r"python\config.py" |
| `_tmp_patch2.py` | 0.2 KB | 2026-11-17 14:21 | p=r"python\coastal_buffer.py" |
| `_tmp_patch3.py` | 1.3 KB | 2026-11-17 14:29 | p=r"results\复现报告.md" |
| `_tmp_patch4.py` | 1.7 KB | 2026-11-17 14:30 | p=r"results\复现报告.md" |
| `_tmp_patch5.py` | 1.8 KB | 2026-11-17 14:31 | p=r"results\复现报告.md" |
| `_tmp_patch6.py` | 2.0 KB | 2026-11-17 14:31 | p=r"待办.md" |
| `_tmp_patch7.py` | 0.5 KB | 2026-11-17 14:32 | p=r"待办.md" |
| `_tmp_patch8.py` | 5.8 KB | 2026-11-17 14:32 | p=r"AGENTS.md" |
| `_tmp_peek.py` | 0.2 KB | 2026-11-17 14:28 | p=r"results\复现报告.md" |
| `_tmp_peek2.py` | 0.1 KB | 2026-11-17 14:30 | p=r"results\复现报告.md" |
| `_tmp_sum.py` | 0.7 KB | 2026-11-17 14:19 | d=json.load(open(r"logs\_diag_fig6_stat.json",encoding="utf-8")) |
| `_val2.err` | 0.0 KB | 2026-10-28 11:47 | — |
| `_val2.out` | 0.3 KB | 2026-10-28 11:48 | — |
| `_val_ocn_nan.err` | 0.0 KB | 2026-10-28 11:44 | — |
| `_val_ocn_nan.out` | 0.5 KB | 2026-10-28 11:45 | — |
| `_val_ocn_nan.py` | 1.5 KB | 2026-10-28 11:44 | C.CESM_PERIOD = ("2000-01-01", "2000-12-31") |
| `_val_ocn_one_year.err` | 0.0 KB | 2026-10-28 11:41 | — |
| `_val_ocn_one_year.out` | 0.4 KB | 2026-10-28 11:43 | — |
| `_val_ocn_one_year.py` | 1.5 KB | 2026-10-28 11:41 | C.CESM_PERIOD = ("2000-01-01", "2000-12-31")   # 只取一年做校验 |
| `_val_ocn_one_year2.py` | 1.1 KB | 2026-10-28 11:47 | C.CESM_PERIOD = ("2000-01-01", "2000-12-31") |
| `_wait_then_v7.ps1` | 2.1 KB | 2026-11-08 02:08 | $ErrorActionPreference = 'Continue' |
| `cesm1983_all_ocn_pids.txt` | 0.1 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard1.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard10.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard2.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard3.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard4.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard5.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard6.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard7.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard8.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_all_ocn_shard9.log.err` | 0.0 KB | 2026-11-08 01:43 | — |
| `cesm1983_shard1.err` | 0.0 KB | 2026-11-07 16:54 | — |
| `cesm1983_shard2.err` | 0.0 KB | 2026-11-07 16:54 | — |
| `cesm1983_shard3.err` | 0.0 KB | 2026-11-07 16:54 | — |
| `cesm1983_shard4.err` | 0.0 KB | 2026-11-07 16:54 | — |
| `cesm1983_shard5.err` | 0.0 KB | 2026-11-07 16:54 | — |
| `cesm1983_shard6.err` | 0.0 KB | 2026-11-07 16:54 | — |
| `cesm1983b_pids.txt` | 0.1 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard1.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard10.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard2.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard3.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard4.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard5.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard6.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard7.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard8.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983b_shard9.err` | 0.0 KB | 2026-11-07 17:04 | — |
| `cesm1983c_pids.txt` | 0.1 KB | 2026-11-07 17:35 | — |
| `cesm1983d_pids.txt` | 0.1 KB | 2026-11-07 18:15 | — |
| `cesm1983e_pids.txt` | 0.1 KB | 2026-11-07 18:25 | — |
| `cesm1983s_pids.txt` | 0.1 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard1.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard10.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard2.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard3.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard4.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard5.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard6.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard7.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard8.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm1983s_shard9.err` | 0.0 KB | 2026-11-07 16:57 | — |
| `cesm_1983_probe.err` | 0.0 KB | 2026-11-07 16:52 | — |

> 被删除的脚本本身没有长期价值（都是一次性探针/打补丁/取数），其**结论已写进** `AGENTS.md`、`docs/批次历史.md`、`results/复现报告.md`。
