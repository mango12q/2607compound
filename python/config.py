"""
config.py — 项目全局配置
所有路径、阈值、参数集中管理，避免硬编码。
"""
import os

# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────
BASE_DIR = r"D:\2607compound"
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
# 规范文件名
# ──────────────────────────────────────────────
OISST_RAW_PATTERN = os.path.join(OISST_DIR, "temp_raw", "oisst-avhrr-v02r01.*.nc")
OISST_MERGED_FILE = os.path.join(OISST_DIR, "oisst_v2.1_1982_2023.nc")

EOBS_RAW_FILES = [
    os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_1980-1994_v33.0e.nc"),
    os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_1995-2010_v33.0e.nc"),
    os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_2011-2023_v29.0e.nc"),
]
EOBS_MERGED_FILE = os.path.join(EOBS_DIR, "EOBS_tg_1983_2023.nc")

SST_CLIM_FILE = os.path.join(INTERMEDIATE_DIR, "sst_climatology_1983_2012.nc")
T2M_CLIM_FILE = os.path.join(INTERMEDIATE_DIR, "t2m_climatology_1983_2012.nc")

# ★ 2025-09-18 起海陆检测统一为 R heatwaveR (python/detect_events.R)：
#   海洋 = mhw_events_R_global.csv（R 输出经 results/globalize_mhw_idx.py
#          把裁剪文件局部索引换算回全球 OISST 索引，与 coastal_pairs 同空间）
#   陆地 = thw_events_R.csv（detect_thw.R 产物；detect_events.R 的陆地重跑
#          thw_events_R_v2.csv 已通过逐行回归对比，二者一致）
#   旧的 Python 检测结果备份为 mhw_events_py.csv.bak / thw_events.csv.bak。
MHW_EVENTS_CSV = os.path.join(INTERMEDIATE_DIR, "mhw_events_R_global.csv")
THW_EVENTS_CSV = os.path.join(INTERMEDIATE_DIR, "thw_events_R.csv")

COASTAL_PAIRS_CSV = os.path.join(INTERMEDIATE_DIR, "coastal_pairs.csv")

COMPOUND_NC = os.path.join(INTERMEDIATE_DIR, "compound_events.nc")
STANDALONE_NC = os.path.join(INTERMEDIATE_DIR, "standalone_days.nc")

ANNUAL_COMPOUND_NC = os.path.join(INTERMEDIATE_DIR, "annual_compound_days.nc")
ANNUAL_STANDALONE_NC = os.path.join(INTERMEDIATE_DIR, "annual_standalone_days.nc")
ANNUAL_THW_NC = os.path.join(INTERMEDIATE_DIR, "annual_thw_days.nc")
CHR_ANNUAL_NC = os.path.join(INTERMEDIATE_DIR, "CHR_annual.nc")
COOCCURRENCE_PROB_NC = os.path.join(INTERMEDIATE_DIR, "cooccurrence_prob_annual.nc")

# ──────────────────────────────────────────────
# 热浪检测参数
# ──────────────────────────────────────────────
CLIM_PERIOD = (1983, 2012)
DURATION_THRESH = 5
GAP_TOLERANCE = 2
PERCENTILE = 90

# R heatwaveR 侧参数（与上面共用同一组数值，显式命名以免混淆）
HW_MIN_DURATION = DURATION_THRESH
HW_MAX_GAP = GAP_TOLERANCE
HW_WINDOW_HALF_WIDTH = 5      # 11 天滑动窗口（heatwaveR 默认）
R_WORKERS = 12                # PSOCK worker 数（本机 24 逻辑核）

# ⚠️ 已知方法学差异（交叉验证结论，详见 results/方法与证据.md §4）
# 1) 阈值：Python detect_thw.py 用逐 dayofyear 的**单日**分位数（无窗口）；
#    heatwaveR 用 11 天滑动窗口分位数。两者在 E-OBS 上仅差 +0.23 °C。
# 2) 最小持续时间口径（**主因**）：
#    detect_thw.py      -> 事件"跨度"(含间隙) >= 5 天
#    heatwaveR          -> "超标日游程"(不含间隙) >= 5 天
#    该口径差异使 R 的事件数约为 Python 的 53%（消融实验 -45%）。

# ──────────────────────────────────────────────
# 复合事件参数
# ──────────────────────────────────────────────
MAX_GRID_DIST_DEG = 0.5
WBT_THRESHOLD = 25.5
SH_THRESHOLD = 19.0

# 图6 分析域：地中海海岸向内 100 km 的陆地格点
# 论文原文：“spatial averages over land grid cells located up to 100 km inland
#          from the Mediterranean coast”（Methods / Fig.6 caption）
# 实现见 python/coastal_buffer.py（KDTree 最近海洋格点距离，与 coastal_pairs 同口径）
#
# 区域口径说明：
#   - 论文 Fig.6 只写 "Mediterranean coast"；但论文 Fig.1j caption 把黑海并入
#     "the Mediterranean region (including the Black Sea)"。
#   - 本项目 fig1j/k/l（fig1_compound_spatial.py:60、fig_jkl_mhw_envelope.py:29）
#     统一使用 lat(30,47) / lon(5,42) 作为"地中海 & 黑海"框。
#   - 此处沿用同一框，避免在工作区里出现第三套"地中海"定义。
#   - 若要严格按 Fig.6 字面（仅地中海、不含黑海），把 lat 上限降到 46、
#     lon 上限降到 30 即可（见 results/规划一致性审查.md（第二轮））。
COASTAL_BUFFER_KM = 100.0
COASTAL_BUFFER_REGION = {"lon": (5.0, 42.0), "lat": (30.0, 47.0)}   # = fig1j 区域框

# ──────────────────────────────────────────────
# Bootstrap 参数（归因分析阶段使用）
# ──────────────────────────────────────────────
N_BOOTSTRAP = 1000
CI_ALPHA = (0.05, 0.95)  # 5%-95% 置信区间（90% CI），对应复现方案 "取 5–95% 置信区间"
N_JOBS = -1

# 图4 GEV 重现期（论文 Methods：1000 bootstrap + MLE，2.5–97.5% CI）
GEV_RETURN_PERIODS = (5, 10, 20, 50, 100)
GEV_CI = (0.025, 0.975)   # 区别于图3 的 CI_ALPHA=(0.05, 0.95)

# ──────────────────────────────────────────────
# Phase 6 归因口径（决策 D7，2026-09-23 用户拍板）
#   原散落在 python/phase6_cesm.py:61,72-83,314；2026-09-23 第三轮规划一致性审查时
#   下沉到此处，使 SPEC §3.1「参数集中管理，避免硬编码」成立。
#   phase6_cesm.py 仍以同名变量引用（值不变），CLI 默认值亦不变。
# ──────────────────────────────────────────────
COMPOUND_DEF = "envelope"        # 模型侧复合定义 {"envelope","exceed"}（D7.1：MHW 包络）
MAIN_AGG = "med_mean"            # 区域聚合主口径（D7.3；med_p90 敏感性、med_max 参考）
AGG_COLS = ("med_mean", "med_p90", "med_max")
SWEEP_MIN, SWEEP_MAX, SWEEP_STEP = 0.0, 100.0, 1.0   # 归因阈值扫描 0–100 天（D7.2）
PAPER_THR_REFS = {2003: 62.0, 2022: 78.0, 2023: 72.0}  # 论文 Fig.3c 三条年份参考线
BOOT_MODE = "indep"              # bootstrap 主口径 {"indep","block"}（D7.5）
THRESH_VERSION = "v3_w11_loo"    # 阈值缓存指纹版本（审计 F4）
SST_TIME_LABEL_SHIFT_DAYS = -1   # ★ POP SST 标签（=物理日+1）校正，第三轮 F10
MAX_PAIR_DIST_DEG = 1.0          # CESM 侧配对上限（度；观测侧为 MAX_GRID_DIST_DEG=0.5°）

# ──────────────────────────────────────────────
# CESM1-LE 成员列表
# ──────────────────────────────────────────────
CESM_ALL_MEMBERS = [f"{i:03d}" for i in range(1, 21)]
CESM_FIXGHG_MEMBERS = [f"{i:03d}" for i in range(1, 21)]

# ──────────────────────────────────────────────
# CESM1-LE (Phase 6 归因) 下载与处理参数 — download_cesm1le.py
# 数据源: AWS 镜像 s3://ncar-cesm-lens (仅 ALL 日值 TREFHT, 匿名)
#         NCAR GDEX d651027 (SST 日值 + XGHG 全部, 需 RDA 账号取 URL)
# ──────────────────────────────────────────────
CESM_DIR = os.path.join(DATA_DIR, "CESM1-LE")
CESM_RAW_DIR = os.path.join(CESM_DIR, "raw")    # RDA 下载的全时段原始文件
CESM_PROC_DIR = os.path.join(CESM_DIR, "proc")  # 裁剪到分析时段后的文件
CESM_PERIOD = ("2000-01-01", "2021-12-31")      # 论文 L522: 2000-2021
CESM_P0_MEMBERS = 3                             # P0 先跑通用前 N 个成员
CESM_EUROPE_LAT = (28.0, 74.0)                  # f09 大气网格裁剪框
CESM_EUROPE_LON = (-17.0, 47.0)                 # 脚本内自动做 0-360 换算
AWS_LENS_BUCKET = "s3://ncar-cesm-lens"
GDEX_D651027_BASE = "https://data.gdex.ucar.edu/d651027"

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
# E-OBS 版本说明
# ──────────────────────────────────────────────
EOBS_VERSION_NOTE = (
    "Mixed versions: v33.0e (1980-2010) + v29.0e (2011-2023). "
    "Analysis subset to 1983-2023."
)

# ──────────────────────────────────────────────
# R 调用配置
# ──────────────────────────────────────────────
RSCRIPT_PATH = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
DETECT_THW_R_SCRIPT = os.path.join(BASE_DIR, "python", "detect_thw.R")

# ──────────────────────────────────────────────
# 绘图参数
# ──────────────────────────────────────────────
FIG_SIZE = (12, 8)
DPI = 300
CMAP_HEATWAVE = 'YlOrRd'
CMAP_PROBABILITY = 'viridis'
