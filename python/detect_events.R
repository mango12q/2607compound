#!/usr/bin/env Rscript
# =============================================================================
# detect_events.R — 统一的热浪事件检测器（heatwaveR / Hobday et al. 2016）
#
# 海陆共用同一份代码，保证口径完全一致（这是 CHR 有意义的前提）。
#
# 用法:
#   Rscript detect_events.R <nc_file> <varname> <output_csv> <clim_start> <clim_end>
#                           [domains_file] [min_duration] [max_gap] [workers] [work_dir]
#
# 参数:
#   nc_file       NetCDF 文件（E-OBS 的 tg/T2m，或 OISST 的 sst）
#   varname       变量名，如 T2m / sst / tg
#   output_csv    输出事件表
#   clim_start    气候期起始年（1983）
#   clim_end      气候期结束年（2012）
#   domains_file  可选。CSV，含 lat / lon 两列（度），只在这些点上检测。
#                 留空或传 "-" 表示检测整个网格。
#   min_duration  最短事件时长（默认 5）
#   max_gap       允许间隙（默认 2）
#   workers       PSOCK worker 数（默认 4）
#   work_dir      断点续跑目录（默认 <output_csv>.work）
#
# 检测参数（固定，与论文/Hobday 2016 一致）:
#   pctile = 90, windowHalfWidth = 5 (11 天滑动窗口), smoothPercentile = FALSE
#   minDuration = 5, maxGap = 2
#
# 输出列:
#   event_no, event_start, event_end, duration, intensity_mean, intensity_max,
#   lat_idx, lon_idx, lat, lon      (lat_idx/lon_idx 为 0-based 全局索引)
#
# ★ 关键实现要点（踩过的坑，勿改）★
#   1) ts2clm() 必须用 clmOnly = FALSE（默认），返回全长 (t,temp,seas,thresh)。
#      用 clmOnly=TRUE 得到的是 366 行日气候态，detect_event() 会把它循环补齐
#      到全长，阈值与日期整体错位，结果完全不可用。
#   2) ncvar_get() 返回的维度顺序与 nc$var$dim 声明**相反**。
#      E-OBS 文件声明 (lon,lat,time) -> R 侧也是 (lon,lat,time)；
#      OISST 同理由 xarray 写成 (time,lat,lon) -> R 侧 (lon,lat,time)。
#      本脚本一律按 R 侧 (lon, lat, time) 访问。
#   3) 输出索引必须由**坐标反查全局索引**，不能用文件行号（子集文件会错位）。
# =============================================================================

suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))
suppressPackageStartupMessages(library(parallel))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 5) {
  stop(paste("Usage: Rscript detect_events.R <nc_file> <varname> <output_csv>",
             "<clim_start> <clim_end> [domains_file] [min_duration] [max_gap]",
             "[workers] [work_dir]"))
}

nc_file     <- args[1]
varname     <- args[2]
output_file <- args[3]
clim_start  <- as.integer(args[4])
clim_end    <- as.integer(args[5])
domains_file <- if (length(args) >= 6 && args[6] != "-") args[6] else NULL
min_dur     <- if (length(args) >= 7) as.integer(args[7]) else 5L
max_gap     <- if (length(args) >= 8) as.integer(args[8]) else 2L
n_workers   <- if (length(args) >= 9) as.integer(args[9]) else 4L
work_dir    <- if (length(args) >= 10) args[10] else paste0(output_file, ".work")

chunk_dir <- file.path(work_dir, "chunks")
dir.create(chunk_dir, showWarnings = FALSE, recursive = TRUE)
clim_period <- c(sprintf("%04d-01-01", clim_start), sprintf("%04d-12-31", clim_end))

cat("=====================================================================\n")
cat("Heatwave detection via heatwaveR (unified MHW/THW detector)\n")
cat(sprintf("  file        : %s\n", nc_file))
cat(sprintf("  variable    : %s\n", varname))
cat(sprintf("  output      : %s\n", output_file))
cat(sprintf("  climatology : %s .. %s  pctile=90 windowHalfWidth=5\n",
            clim_period[1], clim_period[2]))
cat(sprintf("  minDuration : %d   maxGap: %d   workers: %d\n",
            min_dur, max_gap, n_workers))
cat(sprintf("  domains     : %s\n",
            if (is.null(domains_file)) "ENTIRE GRID" else domains_file))
cat("=====================================================================\n")

# -----------------------------------------------------------------------------
# 1. 网格与时间元数据
# -----------------------------------------------------------------------------
nc <- nc_open(nc_file)
lon      <- ncvar_get(nc, "lon")
lat      <- ncvar_get(nc, "lat")
time_val <- ncvar_get(nc, "time")
t_units  <- nc$dim$time$units
if (is.null(t_units)) t_units <- nc$var[[varname]]$dim[[3]]$units
# 不能在这里 nc_close()，下面还要读探测切片

nlon <- length(lon); nlat <- length(lat); ntime <- length(time_val)
dates <- as.Date(time_val, origin = sub("^.*since ", "", t_units))
ord <- order(dates)
dates <- dates[ord]; time_val <- time_val[ord]

cat(sprintf("Grid: nlon=%d nlat=%d ntime=%d\n", nlon, nlat, ntime))
cat(sprintf("lon: %.3f .. %.3f   lat: %.3f .. %.3f\n",
            min(lon), max(lon), min(lat), max(lat)))
cat(sprintf("Time: %s .. %s  (units: %s)\n",
            format(min(dates)), format(max(dates)), t_units))
expected <- seq(min(dates), max(dates), by = "day")
cat(sprintf("Calendar: %d/%d days present%s\n", length(dates), length(expected),
            if (length(dates) == length(expected)) " (continuous)"
            else sprintf(" (%d gaps)", length(expected) - length(dates))))

# 经度去卷绕：OISST 用 0..360，统一到 -180..180 便于与 E-OBS 比较
lon_disp <- ifelse(lon > 180, lon - 360, lon)

# -----------------------------------------------------------------------------
# 2. 候选格点
# -----------------------------------------------------------------------------
if (!is.null(domains_file)) {
  dom <- read.csv(domains_file)
  if (!all(c("lat", "lon") %in% names(dom))) {
    stop("domains_file must contain 'lat' and 'lon' columns")
  }
  dlon <- ifelse(dom$lon > 180, dom$lon - 360, dom$lon)
  # 最近邻匹配到网格索引（OISST 经度卷绕需按角度差取模）
  cand <- matrix(NA_integer_, nrow = nrow(dom), ncol = 2)
  for (i in seq_len(nrow(dom))) {
    di <- abs(lat - dom$lat[i])
    dj <- pmin(abs(lon_disp - dlon[i]), 360 - abs(lon_disp - dlon[i]))
    cand[i, ] <- c(which.min(dj), which.min(di))
  }
  bad <- abs(lat[cand[, 2]] - dom$lat) > 0.26 |
         pmin(abs(lon_disp[cand[, 1]] - dlon), 360 - abs(lon_disp[cand[, 1]] - dlon)) > 0.26
  if (any(bad)) {
    cat(sprintf("  WARNING: %d domain points have no grid point within 0.26 deg\n",
                sum(bad)))
  }
  cand <- unique(cand[!bad, , drop = FALSE])
  cat(sprintf("Domain points: %d requested -> %d matched to grid\n",
              nrow(dom), nrow(cand)))
} else {
  probe_idx <- unique(round(seq(1, ntime, length.out = 24)))
  valid_mask <- matrix(FALSE, nrow = nlon, ncol = nlat)
  for (ti in probe_idx) {
    sl <- ncvar_get(nc, varname, start = c(1, 1, ti), count = c(-1, -1, 1))
    if (is.null(dim(sl))) sl <- matrix(sl, nrow = nlon, ncol = nlat)
    valid_mask <- valid_mask | !is.na(sl)
  }
  cand <- which(valid_mask, arr.ind = TRUE)
  cat(sprintf("Candidate grid points (union of %d slices): %d / %d (%.1f%%)\n",
              length(probe_idx), nrow(cand), nlon * nlat,
              100 * nrow(cand) / (nlon * nlat)))
}
nc_close(nc)
if (is.null(dim(cand))) cand <- matrix(cand, nrow = 1)

# -----------------------------------------------------------------------------
# 3. 切块（按空间带分组，使 NetCDF 读取窗口紧凑）
# -----------------------------------------------------------------------------
pts_per_chunk <- 144L
LON_BAND <- 60L; LAT_BAND <- 12L
band_id <- paste(floor((cand[, 1] - 1) / LON_BAND),
                 floor((cand[, 2] - 1) / LAT_BAND), sep = "_")
chunks <- list()
for (b in unique(band_id)) {
  p <- cand[band_id == b, , drop = FALSE]
  nsub <- ceiling(nrow(p) / pts_per_chunk)
  for (s in seq_len(nsub)) {
    idx <- ((s - 1L) * pts_per_chunk + 1L):min(s * pts_per_chunk, nrow(p))
    pp <- p[idx, , drop = FALSE]
    chunks[[length(chunks) + 1L]] <- list(
      id = sprintf("band%s_%03d", b, s),
      lo0 = min(pp[, 1]), lo1 = max(pp[, 1]),
      la0 = min(pp[, 2]), la1 = max(pp[, 2]),
      pi = pp[, 1], pj = pp[, 2], np = nrow(pp))
  }
}
cat(sprintf("Chunks: %d (<=%d points each, %d points total)\n",
            length(chunks), pts_per_chunk, sum(vapply(chunks, function(c) c$np, numeric(1)))))

# -----------------------------------------------------------------------------
# 4. 单块处理
# -----------------------------------------------------------------------------
process_chunk <- function(ch, nc_file, varname, dates, time_val, lon, lat,
                          clim_period, min_dur, max_gap, min_valid = 730L) {
  nc <- nc_open(nc_file)
  on.exit(nc_close(nc), add = TRUE)
  nlo <- ch$lo1 - ch$lo0 + 1L
  nla <- ch$la1 - ch$la0 + 1L
  cube <- ncvar_get(nc, varname, start = c(ch$lo0, ch$la0, 1),
                    count = c(nlo, nla, -1))
  if (length(dim(cube)) != 3L) {
    cube <- array(cube, dim = c(nlo, nla, length(time_val)))
  }
  n_ok <- 0L
  out <- vector("list", ch$np)
  for (k in seq_len(ch$np)) {
    lo <- ch$pi[k]; li <- ch$pj[k]
    ts <- as.numeric(cube[lo - ch$lo0 + 1L, li - ch$la0 + 1L, ])
    if (sum(!is.na(ts)) < min_valid) next
    n_ok <- n_ok + 1L
    res <- tryCatch({
      df <- data.frame(t = dates, temp = ts)
      # ✅ clmOnly = FALSE（默认）：全长 (t,temp,seas,thresh)，阈值逐日对齐
      clm <- ts2clm(df, climatologyPeriod = clim_period, pctile = 90,
                    windowHalfWidth = 5L, smoothPercentile = FALSE)
      ev <- detect_event(clm, minDuration = min_dur, maxGap = max_gap)
      e <- ev$event
      # ★ 绝对不要在 tryCatch 表达式里写 return(NULL)：R 的 return() 会从
      #   **整个 process_chunk** 返回（实证: R 4.6.1），导致整块事件被静默丢弃、
      #   worker 计数向量缺 n_ok 名（vapply 崩溃）。用表达式值 NULL 代替。
      if (!is.null(e) && nrow(e) > 0L) {
        e <- e[!is.na(e$event_no), , drop = FALSE]  # 剔除"无事件"占位行
      }
      if (is.null(e) || nrow(e) == 0L) NULL
      else data.frame(
        event_no = e$event_no,
        event_start = as.character(e$date_start),
        event_end = as.character(e$date_end),
        duration = e$duration,
        intensity_mean = e$intensity_mean,
        intensity_max = e$intensity_max,
        lat_idx = li - 1L,        # 0-based 全局索引
        lon_idx = lo - 1L,
        lat = lat[li], lon = lon[lo],
        stringsAsFactors = FALSE)
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
    clusterExport(cl, c("process_chunk", "nc_file", "varname", "dates",
                        "time_val", "lon", "lat", "clim_period", "min_dur",
                        "max_gap", "chunk_path", "chunk_dir"),
                  envir = environment())
    clusterEvalQ(cl, {
      suppressPackageStartupMessages(library(heatwaveR))
      suppressPackageStartupMessages(library(ncdf4))
      NULL
    })
    cat(sprintf("Running %d chunks on %d PSOCK workers...\n", length(todo), nw))
    flush.console()
    res_list <- parLapplyLB(cl, todo, function(ch) {
      r <- process_chunk(ch, nc_file, varname, dates, time_val, lon, lat,
                         clim_period, min_dur, max_gap)
      # 防御: r 或 r$n_ok 意外为 NULL 时也不让计数向量缺名
      ev_v <- if (is.null(r)) NULL else r$events
      n_ok_v <- if (is.null(r)) 0L else if (is.null(r$n_ok)) 0L else r$n_ok
      saveRDS(ev_v, chunk_path(ch$id))
      c(n_events = if (is.null(ev_v)) 0L else nrow(ev_v), n_ok = n_ok_v)
    })
  } else {
    res_list <- lapply(todo, function(ch) {
      r <- process_chunk(ch, nc_file, varname, dates, time_val, lon, lat,
                         clim_period, min_dur, max_gap)
      ev_v <- if (is.null(r)) NULL else r$events
      n_ok_v <- if (is.null(r)) 0L else if (is.null(r$n_ok)) 0L else r$n_ok
      saveRDS(ev_v, chunk_path(ch$id))
      c(n_events = if (is.null(ev_v)) 0L else nrow(ev_v), n_ok = n_ok_v)
    })
  }
  el <- as.numeric(difftime(Sys.time(), t_start, units = "mins"))
  n_valid <- sum(vapply(res_list, function(x) x[["n_ok"]], numeric(1)))
  cat(sprintf("Done %d chunks in %.1f min on %d workers; %d valid points\n",
              length(todo), el, nw, n_valid))
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

cat(sprintf("\nTotal events detected: %d\n", nrow(combined)))
if (nrow(combined) > 0) {
  n_pts <- nrow(unique(combined[, c("lat_idx", "lon_idx")]))
  ok <- !is.na(combined$event_start) & grepl("^\\d{4}-\\d{2}-\\d{2}", combined$event_start)
  cat(sprintf("Points with events : %d\n", n_pts))
  cat(sprintf("Events per point   : %.1f\n", nrow(combined) / n_pts))
  cat(sprintf("Mean duration      : %.2f days\n", mean(combined$duration)))
  cat(sprintf("Malformed date rows: %d\n", sum(!ok)))
  if (any(ok)) {
    yr <- as.integer(substr(combined$event_start[ok], 1, 4))
    cat(sprintf("Year range         : %d .. %d\n", min(yr), max(yr)))
    cat("Top-10 years by event count:\n")
    print(head(sort(table(yr), decreasing = TRUE), 10))
  }
}

dir.create(dirname(output_file), showWarnings = FALSE, recursive = TRUE)
write.csv(combined, output_file, row.names = FALSE)
cat(sprintf("Saved to: %s\n", output_file))
