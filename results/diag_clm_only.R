#!/usr/bin/env Rscript
# diag_clm_only.R — 定位 ts2clm(clmOnly=TRUE) 的 thresh 结构问题
suppressPackageStartupMessages(library(heatwaveR))

cat("heatwaveR:", as.character(packageVersion("heatwaveR")), "\n\n")

# ---- 1. 合成数据（基线：已知可用）----
set.seed(42)
d <- seq(as.Date("1983-01-01"), as.Date("2023-12-31"), by = "day")
n <- length(d)
temp <- 15 + 10 * sin(2 * pi * as.numeric(format(d, "%j")) / 365) + rnorm(n, 0, 2)
# 注入一个已知热浪
inj <- which(d == as.Date("2019-07-01")):(which(d == as.Date("2019-07-01")) + 9)
temp[inj] <- temp[inj] + 12
df <- data.frame(t = d, temp = temp)

cat("=== 合成数据 ===\n")
clmT <- ts2clm(df, climatologyPeriod = c("1983-01-01", "2012-12-31"),
               pctile = 90, smoothPercentile = FALSE, clmOnly = TRUE)
cat("clmOnly=TRUE -> class:", paste(class(clmT), collapse=","), " nrow:", nrow(clmT),
    " ncol:", ncol(clmT), "\n")
cat("colnames:", paste(colnames(clmT), collapse=", "), "\n")
cat("head:\n"); print(head(clmT, 3))
cat("doy class:", class(clmT$doy), " length:", length(clmT$doy), "\n")
cat("doy head:", paste(head(clmT$doy, 5), collapse=", "), "\n")
cat("thresh NA count:", sum(is.na(clmT$thresh)), " range:",
    paste(round(range(clmT$thresh, na.rm=TRUE), 2), collapse=" ~ "), "\n")
cat("nrow == 366 ?", nrow(clmT) == 366, "\n\n")

# ---- 2. 用 clmOnly=TRUE 结果喂给 detect_event（脚本当前做法）----
cat("=== detect_event 使用 clmOnly=TRUE 结果（脚本当前做法）===\n")
r1 <- tryCatch({
  ev <- detect_event(df, seasClim = clmT$seas, threshClim = clmT$thresh)
  cat("成功: clim nrow =", nrow(ev$clim), " event nrow =", nrow(ev$event), "\n")
  cat("clim$thresh NA count:", sum(is.na(ev$clim$thresh)), "\n")
  cat("event:\n"); print(ev$event[, c("event_no","index_start","index_end","duration")])
  "OK"
}, error = function(e) paste("ERROR:", conditionMessage(e)))
cat(r1, "\n\n")

# ---- 3. 正确做法：clmOnly=FALSE -> 全长 clm，再喂 detect_event ----
cat("=== 正确做法：clmOnly=FALSE ===\n")
clmF <- ts2clm(df, climatologyPeriod = c("1983-01-01", "2012-12-31"),
               pctile = 90, smoothPercentile = FALSE)
cat("clmOnly=FALSE -> nrow:", nrow(clmF), " (应等于 n =", n, ")\n")
cat("thresh NA count:", sum(is.na(clmF$thresh)), "\n")
ev2 <- detect_event(clmF)
cat("detect_event(clmF) -> events:", nrow(ev2$event), "\n")
print(ev2$event[, c("event_no","index_start","index_end","duration")])
