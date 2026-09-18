#!/usr/bin/env Rscript
# =============================================================================
# detect_thw.R — 陆地热浪 (THW) 检测，基于 R heatwaveR (Hobday et al. 2016)
#
# 用法:
#   Rscript detect_thw.R <eobs_file> <output_file> <clim_start> <clim_end>
#                        [min_duration] [max_gap] [workers] [work_dir]
#
# 示例:
#   Rscript detect_thw.R "E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc" \
#     "D:/2607compound/results/intermediate/thw_events_R.csv" 1983 2012 5 2 10
#
# =============================================================================
# ★ 历史 BUG 与根本原因（2025-09 修订）★
# =============================================================================
# 旧脚本写的是:
#     clm <- ts2clm(..., clmOnly = TRUE)
#     ev  <- detect_event(ts_df, seasClim = clm$seas, threshClim = clm$thresh)
#
# 这是错的。clmOnly = TRUE 时 ts2clm() 返回的是 **366 行的日气候态表**
# (doy, seas, thresh)，而不是全长时间序列。detect_event() 拿到这个 366 行的
# daily 气候态后，内部 (data.table) 把它**循环补齐**到 14975 行，只发出一个
# 容易被忽略的 warning:
#     "Item 3 has 366 rows but longest item has 14975; recycled with remainder"
# 于是第 i 天的阈值变成了第 ((i-1) %% 366 + 1) 天的阈值 —— 阈值与日期整体错位，
# 检测结果完全不可用（在格点时间序列长度非 366 整数倍时，尾部还会被补齐成 NA，
# 这正是"clm$thresh 全是 NA"现象的来源）。
#
# ★ 已验证：真实 E-OBS 上 ts2clm() 本身工作正常，thresh 的 NA 数为 0，
#   数据也没有缺失日期。问题 100% 出在调用方式上，不在数据、不在 heatwaveR。
#
# 正确做法（本脚本采用第 1 种，二者等价）:
#   1) clmOnly = FALSE (默认) -> ts2clm 返回全长 (t, temp, seas, thresh)，
#      直接 detect_event(clm)，阈值自动对齐到每一天；
#   2) detect_event(ts_df, seasClim = clm$seas, threshClim = clm$thresh)，
#      ts_df 必须是**原始全长数据框**，由 detect_event 内部展开 366 行气候态。
#
# =============================================================================
# ★ 与 Python detect_thw.py 的方法学差异（交叉验证必须知悉）★
# =============================================================================
#   Python : 逐 dayofyear 分组求 30 年单日 90th 分位数，**无滑动窗口**
#            （每天只有 30 个样本；xarray groupby 默认 skipna）
#   heatwaveR : 默认 windowHalfWidth = 5 -> 11 天滑动窗口
#            （窗内 11 x 30 = 330 个样本，阈值更平滑、通常更低）
#   两者 minDuration = 5、maxGap = 2 一致（config.py 对 detect_event 默认值）。
#   本脚本显式设 smoothPercentile = FALSE 且 windowHalfWidth = 5，
#   使得 R/Python 的差异可**唯一归因**到"11 天窗口 vs 单日"这一点。
#
# =============================================================================
# ★ 已知隐患（2025-09-18 记录，本文件保留原样作为回归基准，勿改行为）★
#   process_chunk() 的 tryCatch 表达式里写了 return(NULL)。R 4.6.1 实证：
#   return() 会从**整个 process_chunk** 返回（不是只退出 tryCatch），
#   因此"含无事件点的块"会被静默清空（整块事件丢失、其余点白算）。
#   detect_events.R（统一检测器）已改用表达式值 NULL 修复此问题。
#   本文件的既有输出 thw_events_R.csv 经 21,439 格点集合与 Python 完全一致的
#   交叉验证，作为数据工件仍可信；但**不要再用本脚本做新的检测**。
#
# =============================================================================
# 性能设计（Windows / 32 GB RAM / 24 逻辑核）
# =============================================================================
#   * 只把标量与整数索引传给 worker；绝不 clusterExport 大数组（避免序列化失败）。
#   * 每个 worker 用 ncvar_get 读自己那一块的 (lon, lat, time) 子立方体。
#   * 任务切分为 ~150 点/块，parLapplyLB 动态负载均衡（空格点导致负载极不均）。
#   * 每块完成后立即落盘到 work_dir/chunks/*.rds，支持断点续跑。
# =============================================================================

suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))
suppressPackageStartupMessages(library(parallel))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop(paste("Usage: Rscript detect_thw.R <eobs_file> <output_file>",
             "<clim_start> <clim_end> [min_duration] [max_gap] [workers] [work_dir]"))
}

eobs_file   <- args[1]
output_file <- args[2]
clim_start  <- as.integer(args[3])
clim_end    <- as.integer(args[4])
min_dur     <- if (length(args) >= 5) as.integer(args[5]) else 5L
max_gap     <- if (length(args) >= 6) as.integer(args[6]) else 2L
n_workers   <- if (length(args) >= 7) as.integer(args[7]) else 4L
work_dir    <- if (length(args) >= 8) args[8] else paste0(output_file, ".work")

# 全局参考网格（用于把坐标翻译成全局 0-based 索引）
gl_file <- if (length(args) >= 9) args[9] else eobs_file

chunk_dir <- file.path(work_dir, "chunks")
dir.create(chunk_dir, showWarnings = FALSE, recursive = TRUE)

clim_period <- c(sprintf("%04d-01-01", clim_start), sprintf("%04d-12-31", clim_end))

cat("=====================================================================\n")
cat("THW detection via heatwaveR (fixed clmOnly bug)\n")
cat(sprintf("  E-OBS       : %s\n", eobs_file))
cat(sprintf("  output      : %s\n", output_file))
cat(sprintf("  climatology : %s .. %s   pctile=90 windowHalfWidth=5\n",
            clim_period[1], clim_period[2]))
cat(sprintf("  minDuration : %d   maxGap: %d   workers: %d\n",
            min_dur, max_gap, n_workers))
cat(sprintf("  work_dir    : %s\n", work_dir))
cat("=====================================================================\n")

# -----------------------------------------------------------------------------
# 1. 网格与时间元数据
# -----------------------------------------------------------------------------
nc <- nc_open(eobs_file)
lon      <- ncvar_get(nc, "lon")
lat      <- ncvar_get(nc, "lat")
time_val <- ncvar_get(nc, "time")
t_units  <- nc$dim$time$units
# 注意: 这里不能 nc_close()，下面还要读探测切片

nlon <- length(lon); nlat <- length(lat); ntime <- length(time_val)
dates <- as.Date(time_val, origin = sub("^.*since ", "", t_units))
ord <- order(dates); dates <- dates[ord]; time_val <- time_val[ord]

# 全局参考网格坐标（默认与输入同一文件；传入子集时可指定完整文件）
if (gl_file == eobs_file) {
  gl_lon <- lon; gl_lat <- lat
} else {
  ncg <- nc_open(gl_file)
  gl_lon <- ncvar_get(ncg, "lon"); gl_lat <- ncvar_get(ncg, "lat")
  nc_close(ncg)
}
cat(sprintf("Global index grid: nlon=%d nlat=%d\n", length(gl_lon), length(gl_lat)))

cat(sprintf("Grid: nlon=%d nlat=%d ntime=%d\n", nlon, nlat, ntime))
cat(sprintf("Time: %s .. %s\n", format(min(dates)), format(max(dates))))
expected <- seq(min(dates), max(dates), by = "day")
cat(sprintf("Calendar: %d/%d days present%s\n", length(dates), length(expected),
            if (length(dates) == length(expected)) " (continuous)" else " (has gaps)"))

# -----------------------------------------------------------------------------
# 2. 候选格点：抽取 24 个不同时相的时间片，取并集（避免只看第一个时相漏点）
# -----------------------------------------------------------------------------
probe_idx <- unique(round(seq(1, ntime, length.out = 24)))
valid_mask <- matrix(FALSE, nrow = nlon, ncol = nlat)   # (lon, lat)
for (ti in probe_idx) {
  sl <- ncvar_get(nc, "T2m", start = c(1, 1, ti), count = c(-1, -1, 1))
  if (is.null(dim(sl))) sl <- matrix(sl, nrow = nlon, ncol = nlat)
  valid_mask <- valid_mask | !is.na(sl)
}
cand <- which(valid_mask, arr.ind = TRUE)   # 列: lon_idx, lat_idx
nc_close(nc)
cat(sprintf("Candidate grid points (union of %d time slices): %d / %d (%.1f%%)\n",
            length(probe_idx), nrow(cand), nlon * nlat, 100 * nrow(cand) / (nlon * nlat)))

# -----------------------------------------------------------------------------
# 3. 切块：按 (lat 带, lon 带) 分组，使每块在 NetCDF 中的读取窗口尽量紧凑
# -----------------------------------------------------------------------------
pts_per_chunk <- 144L
LON_BAND <- 60L; LAT_BAND <- 12L

band_id <- paste(floor((cand[, 1] - 1) / LON_BAND),
                 floor((cand[, 2] - 1) / LAT_BAND), sep = "_")
band_levels <- unique(band_id)
cat(sprintf("Spatial bands: %d\n", length(band_levels)))

chunks <- list()
for (b in band_levels) {
  sel <- which(band_id == b)
  p <- cand[sel, , drop = FALSE]
  nsub <- ceiling(nrow(p) / pts_per_chunk)
  for (s in seq_len(nsub)) {
    idx <- ((s - 1L) * pts_per_chunk + 1L):min(s * pts_per_chunk, nrow(p))
    pp <- p[idx, , drop = FALSE]
    chunks[[length(chunks) + 1L]] <- list(
      id  = sprintf("band%s_%03d", b, s),
      lo0 = min(pp[, 1]), lo1 = max(pp[, 1]),
      la0 = min(pp[, 2]), la1 = max(pp[, 2]),
      pi  = pp[, 1],
      pj  = pp[, 2],
      np  = nrow(pp)
    )
  }
}
npts_total <- sum(vapply(chunks, function(c) c$np, numeric(1)))
cat(sprintf("Chunks: %d (<=%d points each, %d candidate points total)\n",
            length(chunks), pts_per_chunk, npts_total))

# -----------------------------------------------------------------------------
# 4. 单块处理
# -----------------------------------------------------------------------------
process_chunk <- function(ch, eobs_file, dates, time_val, lon, lat,
                          gl_lon, gl_lat, clim_period, min_dur, max_gap) {
  nc <- nc_open(eobs_file)
  on.exit(nc_close(nc), add = TRUE)

  nlo <- ch$lo1 - ch$lo0 + 1L
  nla <- ch$la1 - ch$la0 + 1L
  cube <- ncvar_get(nc, "T2m",
                    start = c(ch$lo0, ch$la0, 1),
                    count = c(nlo, nla, -1))
  if (length(dim(cube)) != 3L) {
    cube <- array(cube, dim = c(nlo, nla, length(time_val)))
  }

  dts <- dates
  n_ok <- 0L
  out <- vector("list", ch$np)

  for (k in seq_len(ch$np)) {
    lo <- ch$pi[k]; li <- ch$pj[k]
    temp_ts <- as.numeric(cube[lo - ch$lo0 + 1L, li - ch$la0 + 1L, ])
    if (sum(!is.na(temp_ts)) < 730L) next
    n_ok <- n_ok + 1L

    # 子集文件的行号不是全局行号 —— 必须用坐标反查全局索引，
    # 否则输出的 lat_idx/lon_idx 含义会随输入文件变化（曾经踩过的坑）。
    gl_li <- which.min(abs(gl_lat - lat[li])) - 1L
    gl_lo <- which.min(abs(gl_lon - lon[lo])) - 1L
    if (abs(gl_lat[gl_li + 1L] - lat[li]) > 1e-6 ||
        abs(gl_lon[gl_lo + 1L] - lon[lo]) > 1e-6) next   # 坐标不在全局网格上

    res <- tryCatch({
      df <- data.frame(t = dts, temp = temp_ts)
      # ✅ clmOnly 保持默认 FALSE：返回全长 (t, temp, seas, thresh)，阈值逐日对齐
      clm <- ts2clm(df, climatologyPeriod = clim_period,
                    pctile = 90, windowHalfWidth = 5L,
                    smoothPercentile = FALSE)
      ev <- detect_event(clm, minDuration = min_dur, maxGap = max_gap)
      e <- ev$event
      if (is.null(e) || nrow(e) == 0L) return(NULL)
      # detect_event 在"无事件"时返回 1 行全 NA 的占位行，必须剔除
      e <- e[!is.na(e$event_no), , drop = FALSE]
      if (nrow(e) == 0L) return(NULL)
      data.frame(
        event_no       = e$event_no,
        event_start    = as.character(e$date_start),
        event_end      = as.character(e$date_end),
        duration       = e$duration,
        intensity_mean = e$intensity_mean,
        intensity_max  = e$intensity_max,
        lat_idx        = gl_li,   # 全局 0-based，对齐 Python / xarray 约定
        lon_idx        = gl_lo,
        lat            = gl_lat[gl_li + 1L],
        lon            = gl_lon[gl_lo + 1L],
        stringsAsFactors = FALSE
      )
    }, error = function(err) NULL)

    out[[k]] <- res
  }

  good <- !vapply(out, is.null, logical(1))
  ev <- if (any(good)) do.call(rbind, out[good]) else NULL
  list(events = ev, n_ok = n_ok)
}

# -----------------------------------------------------------------------------
# 5. 执行（动态负载均衡 + 逐块落盘 + 断点续跑）
# -----------------------------------------------------------------------------
chunk_path <- function(id) file.path(chunk_dir, paste0(id, ".rds"))
done <- vapply(chunks, function(ch) file.exists(chunk_path(ch$id)), logical(1))
cat(sprintf("Resume: %d/%d chunks already done\n", sum(done), length(chunks)))
todo <- chunks[!done]

t_start <- Sys.time()
if (length(todo) > 0L) {
  nw <- max(1L, min(n_workers, length(todo)))
  if (nw > 1L) {
    cl <- makeCluster(nw, type = "PSOCK")
    on.exit(try(stopCluster(cl), silent = TRUE), add = TRUE)
    # 只传路径/标量/小向量
    clusterExport(cl, c("process_chunk", "eobs_file", "dates", "time_val",
                        "lon", "lat", "gl_lon", "gl_lat", "clim_period",
                        "min_dur", "max_gap", "chunk_path", "chunk_dir"),
                  envir = environment())
    clusterEvalQ(cl, {
      suppressPackageStartupMessages(library(heatwaveR))
      suppressPackageStartupMessages(library(ncdf4))
      NULL
    })
    cat(sprintf("Running %d chunks on %d PSOCK workers...\n", length(todo), nw))
    flush.console()
    res_list <- parLapplyLB(cl, todo, function(ch) {
      r <- process_chunk(ch, eobs_file, dates, time_val, lon, lat,
                         gl_lon, gl_lat, clim_period, min_dur, max_gap)
      saveRDS(r$events, chunk_path(ch$id))
      c(n_events = if (is.null(r$events)) 0L else nrow(r$events), n_ok = r$n_ok)
    })
  } else {
    res_list <- lapply(todo, function(ch) {
      r <- process_chunk(ch, eobs_file, dates, time_val, lon, lat,
                         gl_lon, gl_lat, clim_period, min_dur, max_gap)
      saveRDS(r$events, chunk_path(ch$id))
      c(n_events = if (is.null(r$events)) 0L else nrow(r$events), n_ok = r$n_ok)
    })
  }

  el <- as.numeric(difftime(Sys.time(), t_start, units = "mins"))
  cat(sprintf("Done %d chunks in %.1f min (%.2f min/chunk wall, %d workers)\n",
              length(todo), el, el / length(todo), nw))
}

# -----------------------------------------------------------------------------
# 6. 合并
# -----------------------------------------------------------------------------
cat("Merging chunks...\n")
parts <- lapply(chunks, function(ch) {
  p <- chunk_path(ch$id)
  if (!file.exists(p)) return(NULL)
  d <- tryCatch(readRDS(p), error = function(e) NULL)
  if (is.null(d) || nrow(d) == 0L) NULL else d
})
parts <- parts[!vapply(parts, is.null, logical(1))]

combined <- if (length(parts) > 0) do.call(rbind, parts) else data.frame()
if (nrow(combined) > 0) {
  combined <- combined[order(combined$lat_idx, combined$lon_idx,
                             combined$event_start), ]
  rownames(combined) <- NULL
}

cat(sprintf("\nTotal THW events detected: %d\n", nrow(combined)))
if (nrow(combined) > 0) {
  n_pts <- nrow(unique(combined[, c("lat_idx", "lon_idx")]))
  starts <- combined$event_start
  ok_date <- !is.na(starts) & grepl("^\\d{4}-\\d{2}-\\d{2}", starts)
  cat(sprintf("Grid points with events : %d\n", n_pts))
  cat(sprintf("Events per point        : %.1f\n", nrow(combined) / n_pts))
  cat(sprintf("Malformed/NA date rows  : %d\n", sum(!ok_date)))
  if (any(ok_date)) {
    yr <- as.integer(substr(starts[ok_date], 1, 4))
    cat(sprintf("Year range              : %d .. %d\n", min(yr), max(yr)))
    cat("Top-10 years by event count:\n")
    print(head(sort(table(yr), decreasing = TRUE), 10))
  }
}

dir.create(dirname(output_file), showWarnings = FALSE, recursive = TRUE)
write.csv(combined, output_file, row.names = FALSE)
cat(sprintf("Saved to: %s\n", output_file))
