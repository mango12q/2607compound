#!/usr/bin/env Rscript
# =============================================================================
# exp_smooth_test.R — 验证 smoothPercentile 对复合天数的影响（抽样实验）
#
# 背景: 论文 Methods 用 heatwaveR v0.4.6 + marineHeatWaves v0.15.0，两者默认都是
#   ts2clm/calc_clim: windowHalfWidth=5, pctile=90, **smoothPercentile=TRUE (31天)**
#   detect: minDuration=5, joinAcrossGaps=TRUE, maxGap=2
# 我们当前的统一检测器为隔离变量实验设了 smoothPercentile=FALSE —— 与论文口径不符。
#
# 本脚本: 抽样 Med/Baltic/Atlantic 沿海对，用 smoothPercentile=TRUE 重检
#         陆地(E-OBS)与海洋(OISST clip)两侧事件，输出供 Python 侧对比。
#
# 用法: Rscript exp_smooth_test.R <sample_csv> <out_csv>
#   sample_csv 列: land_lat, land_lon, ocean_lat, ocean_lon, region
#   out_csv    列: side, lat, lon, event_start, event_end, duration
# =============================================================================

suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))
suppressPackageStartupMessages(library(parallel))

args <- commandArgs(trailingOnly = TRUE)
sample_csv <- args[1]
out_csv    <- args[2]

EOBS <- "E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc"
CLIP <- "E:/2607compound/data/OISST/oisst_v2.1_eur_1983_2023.nc"

samp <- read.csv(sample_csv)
cat(sprintf("sampled pairs: %d (regions: %s)\n", nrow(samp),
            paste(unique(samp$region), collapse = ",")))

clim_period <- c("1983-01-01", "2012-12-31")

# ---- 读坐标/时间 ----
nc_l <- nc_open(EOBS)
lon_l <- ncvar_get(nc_l, "lon"); lat_l <- ncvar_get(nc_l, "lat")
tv_l <- ncvar_get(nc_l, "time")
dates_l <- as.Date(tv_l, origin = sub("^.*since ", "", nc_l$dim$time$units))
nc_o <- nc_open(CLIP)
lon_o <- ncvar_get(nc_o, "lon"); lat_o <- ncvar_get(nc_o, "lat")
tv_o <- ncvar_get(nc_o, "time")
dates_o <- as.Date(tv_o, origin = sub("^.*since ", "", nc_o$dim$time$units))

idx_of <- function(coord, vec) {
  sapply(coord, function(x) {
    hits <- which(abs(vec - x) < 1e-6)
    if (length(hits) != 1) NA_integer_ else hits
  })
}
samp$li <- idx_of(samp$land_lat, lat_l)   # 1-based
samp$lj <- idx_of(samp$land_lon, lon_l)
samp$oi <- idx_of(samp$ocean_lat, lat_o)
samp$oj <- idx_of(samp$ocean_lon, lon_o)
stopifnot(!any(is.na(c(samp$li, samp$lj, samp$oi, samp$oj))))

# ---- 抽取时间序列（逐点读；两个文件都小/裁剪过，几十秒量级）----
cat("extracting land series...\n")
land_ts <- vector("list", nrow(samp))
for (i in seq_len(nrow(samp))) {
  land_ts[[i]] <- as.numeric(ncvar_get(nc_l, "T2m",
      start = c(samp$lj[i], samp$li[i], 1), count = c(1, 1, -1)))
}
cat("extracting ocean series...\n")
ocean_ts <- vector("list", nrow(samp))
for (i in seq_len(nrow(samp))) {
  ocean_ts[[i]] <- as.numeric(ncvar_get(nc_o, "sst",
      start = c(samp$oj[i], samp$oi[i], 1), count = c(1, 1, -1)))
}
nc_close(nc_l); nc_close(nc_o)

# ---- 检测（平滑 ON，包默认）----
detect_one <- function(ts, dates) {
  df <- data.frame(t = dates, temp = ts)
  clm <- tryCatch(ts2clm(df, climatologyPeriod = clim_period, pctile = 90,
                         windowHalfWidth = 5, smoothPercentile = TRUE),
                  error = function(e) NULL)
  if (is.null(clm)) return(NULL)
  ev <- tryCatch(detect_event(clm, minDuration = 5, maxGap = 2),
                 error = function(e) NULL)
  if (is.null(ev)) return(NULL)
  e <- ev$event
  if (is.null(e) || nrow(e) == 0L) return(NULL)
  e <- e[!is.na(e$event_no), , drop = FALSE]
  if (nrow(e) == 0L) return(NULL)
  data.frame(event_start = as.character(e$date_start),
             event_end = as.character(e$date_end),
             duration = e$duration, stringsAsFactors = FALSE)
}

jobs <- data.frame(side = c(rep("land", nrow(samp)), rep("ocean", nrow(samp))),
                   k = c(seq_len(nrow(samp)), seq_len(nrow(samp))))
series_all <- c(land_ts, ocean_ts)
dates_all <- c(rep(list(dates_l), nrow(samp)), rep(list(dates_o), nrow(samp)))

cl <- makeCluster(12, type = "PSOCK")
clusterExport(cl, c("detect_one", "series_all", "dates_all", "clim_period"),
              envir = environment())
clusterEvalQ(cl, { suppressPackageStartupMessages(library(heatwaveR)); NULL })
cat("detecting with smoothPercentile=TRUE on 12 workers...\n")
res <- parLapplyLB(cl, seq_len(nrow(jobs)), function(i) {
  detect_one(series_all[[i]], dates_all[[i]])
})
stopCluster(cl)

out <- do.call(rbind, lapply(seq_len(nrow(jobs)), function(i) {
  if (is.null(res[[i]])) return(NULL)
  data.frame(side = jobs$side[i],
             pair_row = jobs$k[i],
             region = samp$region[jobs$k[i]],
             lat = if (jobs$side[i] == "land") samp$land_lat[jobs$k[i]] else samp$ocean_lat[jobs$k[i]],
             lon = if (jobs$side[i] == "land") samp$land_lon[jobs$k[i]] else samp$ocean_lon[jobs$k[i]],
             smooth = TRUE, res[[i]], stringsAsFactors = FALSE)
}))
write.csv(out, out_csv, row.names = FALSE)
cat(sprintf("done: %d events -> %s\n", nrow(out), out_csv))
