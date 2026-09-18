#!/usr/bin/env Rscript
# diag_detect_event.R — 拆解 detect_event() 的内部机制，解释 R/Python 事件数差异
suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))

f <- "D:/2607compound/results/intermediate/_smoke/eobs_small.nc"
nc <- nc_open(f)
lon <- ncvar_get(nc, "lon"); lat <- ncvar_get(nc, "lat")
tval <- ncvar_get(nc, "time")
dates <- as.Date(tval, origin = "1950-01-01")
nc_close(nc)

# 取一个已知的陆地格点：lat_idx=0, lon_idx=24 -> 在子集中
li <- 1L   # R 1-based
lo <- 25L
nc <- nc_open(f)
ts <- as.numeric(ncvar_get(nc, "T2m", start = c(lo, li, 1), count = c(1, 1, -1)))
nc_close(nc)
cat(sprintf("Grid (lon=%.3f, lat=%.3f): %d valid / %d\n",
            lon[lo], lat[li], sum(!is.na(ts)), length(ts)))

df <- data.frame(t = dates, temp = ts)
clm <- ts2clm(df, climatologyPeriod = c("1983-01-01", "2012-12-31"),
              pctile = 90, windowHalfWidth = 5L, smoothPercentile = FALSE)

cat("\n=== ts2clm 输出 ===\n")
cat("nrow:", nrow(clm), " cols:", paste(colnames(clm), collapse = ", "), "\n")
cat("thresh NA:", sum(is.na(clm$thresh)), "  range:",
    paste(round(range(clm$thresh, na.rm = TRUE), 2), collapse = " ~ "), "\n")
cat("temp  > thresh 的天数 :", sum(clm$temp > clm$thresh, na.rm = TRUE), "\n")
cat("temp  > seas   的天数 :", sum(clm$temp > clm$seas,   na.rm = TRUE), "\n")
cat("thresh > seas 的天数  :", sum(clm$thresh > clm$seas, na.rm = TRUE), "\n")

ev <- detect_event(clm, minDuration = 5, maxGap = 2)
e <- ev$event
cat("\n=== detect_event 输出 ===\n")
cat("events:", nrow(e), "\n")
cat("列名:", paste(colnames(e), collapse = ", "), "\n")
cat("duration 合计:", sum(e$duration), "\n")
cat("duration 分布:\n"); print(summary(e$duration))

# 手工复现: 仅 temp > thresh 的游程
exceed <- !is.na(clm$temp) & !is.na(clm$thresh) & clm$temp > clm$thresh
r <- rle(exceed)
runs <- data.frame(len = r$lengths[r$values], val = TRUE)
cat("\n=== 仅 temp>thresh 的连续游程 ===\n")
cat("游程总数:", nrow(runs), "\n")
cat("长度 >= 5 的游程数:", sum(runs$len >= 5), "\n")
cat("长度 >= 5 的游程合计天数:", sum(runs$len[runs$len >= 5]), "\n")

# 前 5 个事件的 index_start / index_end 对应日期
cat("\n=== 前 5 个事件 ===\n")
print(head(e[, c("event_no", "index_start", "index_end", "duration",
                 "intensity_mean", "date_start", "date_end")], 5))

# 检查事件起点处的 temp 与 thresh / seas
if (nrow(e) > 0) {
  i <- e$index_start[1]
  cat(sprintf("\n第 1 个事件起点 idx=%d: temp=%.2f thresh=%.2f seas=%.2f\n",
              i, clm$temp[i], clm$thresh[i], clm$seas[i]))
  cat("事件前 3 天:\n")
  print(clm[max(1, i - 3):i, c("t", "temp", "seas", "thresh")])
}

# ---- 与 Python 单日阈值对比：看阈值本身是否真的等价 ----
# Python 侧用的是逐 DOY 单日 90th 分位数（原始 dayofyear，不补 2/29）
clim_idx <- which(dates >= as.Date("1983-01-01") & dates <= as.Date("2012-12-31"))
doy <- as.integer(format(dates[clim_idx], "%j"))
th_single <- tapply(ts[clim_idx], doy, quantile, probs = 0.9, na.rm = TRUE)
th_single_full <- th_single[as.character(as.integer(format(dates, "%j")))]
cat("\n=== 阈值对比 (该格点) ===\n")
cat("heatwaveR thresh 均值:", round(mean(clm$thresh, na.rm = TRUE), 3),
    " Python单日均值:", round(mean(th_single_full, na.rm = TRUE), 3), "\n")
d <- clm$thresh - th_single_full
cat("差值 mean:", round(mean(d, na.rm = TRUE), 3),
    " range:", paste(round(range(d, na.rm = TRUE), 2), collapse = " ~ "), "\n")
cat("Python 单日阈值超标天数:", sum(clm$temp > th_single_full, na.rm = TRUE), "\n")
