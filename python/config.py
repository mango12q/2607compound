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
# 欧洲裁剪件（1.2 GB；同一份 OISST v2.1，仅供"只在地中海框内用海洋掩码"的场景，
# 如 coastal_buffer.py）。读全球件 (24.8 GB) 会慢 10 倍以上。
OISST_EUR_FILE = os.path.join(OISST_DIR, "oisst_v2.1_eur_1983_2023.nc")

# ── ERA5（Phase 5 输入；实测结构见 results/规划一致性审查.md 第四轮 §数据探针）──
# tmax   欧洲框 0.25° 日最高（CDS daily-statistics, daily_maximum），变量 mx2t，K，
#        维度 (valid_time, latitude, longitude)，lat 66→30 **降序**，lon −10→40 升序
ERA5_TMAX_DIR = os.path.join(ERA5_DIR, "tmax_eur_daily")
ERA5_TMAX_PATTERN = os.path.join(ERA5_TMAX_DIR, "tmax_eur_*.nc")
ERA5_TMAX_MERGED_FILE = os.path.join(ERA5_DIR, "ERA5_tmax_1984_2023_daily.nc")

# d2m    全球 0.25° 日露点（daily_mean），变量 d2m，K，(valid_time, lat, lon)，
#        lat 90→−90 降序，lon −180..180 升序；573 个月度文件 + yearly/ 47 个年度文件
ERA5_D2M_DIR = os.path.join(ERA5_DIR, "d2m_global_daily")
ERA5_D2M_PATTERN = os.path.join(ERA5_D2M_DIR, "d2m_global_????_??.nc")
ERA5_D2M_YEARLY_PATTERN = os.path.join(ERA5_D2M_DIR, "yearly", "d2m_global_????.nc")

# sp     0.25° 欧洲框（数据集 3b+，⬜ 待下载）：变量 sp，Pa，(valid_time, lat, lon)
ERA5_SP025_DIR = os.path.join(ERA5_DIR, "sp_eur_daily")
ERA5_SP025_PATTERN = os.path.join(ERA5_SP025_DIR, "sp_eur_*.nc")
ERA5_SP025_MERGED_FILE = os.path.join(ERA5_DIR, "ERA5_sp_1984_2023_daily.nc")

# sp     1.0° 全球（旧件，仅作敏感性/兜底）：⚠️ lon 为 0..360、时间戳 11:30、维度名 time
ERA5_SP1_DIR = os.path.join(ERA5_DIR, "sp")
ERA5_SP1_PATTERN = os.path.join(ERA5_SP1_DIR, "pres.sfc.daily.era5.????.nc")

# 欧洲分析框（与下载脚本一致：N, W, S, E = 66, −10, 30, 40）
ERA5_EUROPE_BOX = {"lat": (30.0, 66.0), "lon": (-10.0, 40.0)}
# 论文 Fig.5 三个面板的**地图范围**（第五轮实测拟合：lon −15…43.5、lat 29…69）
# —— 比下载框大；SH 趋势（图5c）按此范围计算，sp 0.25° 的下载框已相应扩大到
#    [70, −16, 28, 44]（见 download_era5_sp025.AREA）
ERA5_MAP_BOX = {"lat": (29.0, 69.0), "lon": (-15.0, 43.5)}

# ── OAFlux 蒸发（Phase 5 图5b 输入）──
OAFLUX_RAW_DIR = os.path.join(OAFLUX_DIR, "raw")
OAFLUX_MERGED_FILE = os.path.join(OAFLUX_DIR, "OAFlux_evap_1991_2020_monthly.nc")

# ── Phase 5 计算口径 ──
WBT_METHOD = "iterative"          # {'iterative','stull'}；论文未给公式，见 calc_wbt.py 文档与 D8
WBT_VALID_RANGE = (-20.0, 50.0)   # Stull 公式适用范围（仅用于合理性检查）
SH_MIN, SH_MAX = 0.0, 40.0        # SH 合理性区间（g/kg）
SST_TREND_PERIOD = (1994, 2023)   # 图5a
EVAP_TREND_PERIOD = (1991, 2020)  # 图5b
SH_TREND_PERIOD = (1994, 2023)    # 图5c
TREND_MONTHS = (7, 8, 9)          # 图5 = JAS
WBT_RP_MONTHS = (6, 7, 8)         # 图6c = JJA（论文自身与图5不同，勿统一）
WBT_RP_THRESHOLDS = tuple(round(22.0 + 0.5 * i, 1) for i in range(13))  # 图6c：22–28 °C 步长 0.5
WBT_RP_YEARS = (2003, 2022, 2023)              # 复合年（论文明确）
# ★ 2026-09-24 第五轮：论文 Fig.6c 图例直接列出 11 个"非复合年" —— 以论文为准（不再靠 S1 判读拼凑）：
#   1984 1986 1988 1990 1991 1992 1993 1996 2000 2004 2008
#   （与 caption "compared to 11 non-compound years" 一致，且含正文点名的 2000 年）
WBT_NONCOMPOUND_YEARS = (1984, 1986, 1988, 1990, 1991, 1992, 1993, 1996, 2000, 2004, 2008)
# 以下为"读 Supplementary Fig. S1 逐格判读"得到的旧口径，保留作敏感性对照（第五轮降级）：
WBT_NONCOMPOUND_YEARS_S1 = (1984, 1985, 1986, 1988, 1989, 1991, 1993, 1998)
WBT_NONCOMPOUND_YEARS_S1_10 = WBT_NONCOMPOUND_YEARS_S1 + (1992, 1996)
WBT_NONCOMPOUND_YEAR_PAPER = 2000               # 论文正文点名的"非复合年 2000"
# 图6a/6b 的**超阈频率曲线**阈值轴（论文原图：a 为 25.5–27.0 °C；b 为 19.0–20.7 g/kg）
WBT_EXCEED_THRESHOLDS = tuple(round(25.5 + 0.1 * i, 1) for i in range(16))   # 25.5 … 27.0
SH_EXCEED_THRESHOLDS = tuple(round(19.0 + 0.1 * i, 1) for i in range(21))    # 19.0 … 21.0
DAILY_STATS_TMPL = "ERA5 daily-statistics（daily_maximum / daily_mean, UTC, 1-hourly）"


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
# 区域口径（★ 2026-11-17 第二十七批拍板：只算地中海，纳入西班牙东岸，剔除黑海）
#   - 论文 Fig.6 caption / Methods 原文两处都只写 "land grid cells located up to
#     100 km inland from the **Mediterranean** coast"（logs\_paper_main.txt L356、
#     L396）⇒ 黑海不在图6 域内（黑海只出现在 Fig.1/3/4 的 "Mediterranean & Black Sea"）。
#   - 论文正文点名 "The Mediterranean arc, spanning the **Catalan coast** to …"
#     （L108–110）⇒ 西班牙地中海东岸必须在域内。原框 lon≥5 把整条西班牙东岸
#     （Barcelona 2.2°E / Valencia −0.4°E）和法国 Gulf of Lion 排除在外。
#   - 敏感性实测（logs\_diag_fig6_region.py / .log，同一批 wbt_daily.nc）：
#     2023 年 WBT≥25.5 °C 的区域平均天数 base=1.83 → base_nBS=2.38 → cat=1.79
#     → **cat_nBS=2.26**；6c 的 RP(26 °C) 由 q99 序列给 3.00 → 2.79 年。
#     ⇒ 区域是**二阶**因素（最大 1.23×），解释不了论文的 40 天（见 fig6 残差说明）。
#   - fig1j/k/l 仍用 lat(30,47)/lon(5,42) 的"地中海 & 黑海"框（那是另一张图的口径，
#     不要跟着改）。
COASTAL_BUFFER_KM = 100.0
COASTAL_BUFFER_REGION = {"lon": (0.0, 42.0), "lat": (30.0, 47.0)}
# 从掩码中剔除的框（黑海 + 亚速海；lat>40.5 与 lon>27.5 的湾区）
COASTAL_BUFFER_EXCLUDE = ({"lon": (27.5, 42.0), "lat": (40.5, 47.0)},)

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
MAIN_AGG = "med_mean"            # 区域聚合主口径（D7.3 二次修订 2026-11-08：回到 med_mean）
                                 #   ① 2000–2021 基准（tag _v4）下 med_mean 给 FAR 0.977/0.986/0.987、
                                 #      med_p90 给 0.803/0.846/0.837 —— 当时据此选了 med_p90；
                                 #   ② 换成论文的 1983–2012 气候态（tag _v5）后结论反转：
                                 #      med_mean FAR 0.891/0.940/0.922、PR 9.17/16.76/12.85（论文 0.72/0.95/0.78、4.1/[6–∞)/8），
                                 #      **且唯一复现论文的年际排序**（论文 2003<2023<2022；med_mean 0.891<0.922<0.940，
                                 #      med_p90 0.603>0.674→0.701 反而把 2003 压到最低）。
                                 #   ⇒ 之前的 med_p90 是"错基准下的补偿"，基准纠正后应回归 med_mean。
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
