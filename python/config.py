"""
config.py — 项目全局配置
所有路径、阈值、参数集中管理，避免硬编码。
"""
import os

# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────
BASE_DIR = r"E:\2607compound"

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
EOBS_MERGED_FILE = os.path.join(EOBS_DIR, "EOBS_tg_1984_2023.nc")

SST_CLIM_FILE = os.path.join(INTERMEDIATE_DIR, "sst_climatology_1983_2012.nc")
T2M_CLIM_FILE = os.path.join(INTERMEDIATE_DIR, "t2m_climatology_1983_2012.nc")

MHW_EVENTS_CSV = os.path.join(INTERMEDIATE_DIR, "mhw_events.csv")
THW_EVENTS_CSV = os.path.join(INTERMEDIATE_DIR, "thw_events.csv")

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

# ──────────────────────────────────────────────
# 复合事件参数
# ──────────────────────────────────────────────
MAX_GRID_DIST_DEG = 0.5
WBT_THRESHOLD = 25.5
SH_THRESHOLD = 19.0

# ──────────────────────────────────────────────
# Bootstrap 参数（归因分析阶段使用）
# ──────────────────────────────────────────────
N_BOOTSTRAP = 1000
CI_ALPHA = (0.05, 0.95)  # 5%-95% 置信区间（90% CI），对应复现方案 "取 5–95% 置信区间"
N_JOBS = -1

# ──────────────────────────────────────────────
# CESM1-LE 成员列表
# ──────────────────────────────────────────────
CESM_ALL_MEMBERS = [f"{i:03d}" for i in range(1, 21)]
CESM_FIXGHG_MEMBERS = [f"{i:03d}" for i in range(1, 21)]

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
    "Analysis subset to 1984-2023."
)

# ──────────────────────────────────────────────
# 绘图参数
# ──────────────────────────────────────────────
FIG_SIZE = (12, 8)
DPI = 300
CMAP_HEATWAVE = 'YlOrRd'
CMAP_PROBABILITY = 'viridis'
