# Lead 独立复核：heatwaveR 0.5.5 的真实"桥接/过滤顺序"判别实验
# 用法: Rscript results\phase6_audit_lead_check.R
suppressPackageStartupMessages(library(heatwaveR))
cat("heatwaveR version:", as.character(packageVersion("heatwaveR")), "\n\n")

# 构造一个自带 thresh 列的"气候态"数据框，直接喂 detect_event，
# 以此把"事件逻辑"与"阈值计算"完全解耦。
mk <- function(o) {
  n <- length(o)
  data.frame(
    t     = as.Date("2000-01-01") + seq_len(n) - 1L,
    temp  = ifelse(o == 1, 1, 0),   # 超标=1, 未超标=0
    seas  = 0,
    thresh = 0.5,                    # 阈值 0.5 ⇒ temp>thresh 即 o==1
    stringsAsFactors = FALSE
  )
}

cases <- list(
  "3超+2空+3超 (跨度8)" = c(1,1,1,0,0,1,1,1),
  "1超+2空+4超 (跨度7)" = c(1,0,0,1,1,1,1),
  "2超+2空+2超 (跨度6)" = c(1,1,0,0,1,1),
  "1超+1空+3超 (跨度5)" = c(1,0,1,1,1),
  "4超+3空+4超 (间隙>2)" = c(1,1,1,1,0,0,0,1,1,1,1),
  "5超 单段"            = c(1,1,1,1,1),
  "4超 单段(<5)"        = c(1,1,1,1),
  "1超+2空+1超 (跨度4)" = c(1,0,0,1),
  "6超+2空+6超 (跨度14)" = c(1,1,1,1,1,1,0,0,1,1,1,1,1,1)
)

cat(sprintf("%-24s %-28s %s\n", "用例", "heatwaveR 事件(duration)", "事件数"))
for (nm in names(cases)) {
  o <- cases[[nm]]
  ev <- detect_event(mk(o), minDuration = 5, maxGap = 2)
  e <- ev$event
  if (!is.null(e) && nrow(e) > 0) e <- e[!is.na(e$event_no), , drop = FALSE]
  desc <- if (is.null(e) || nrow(e) == 0) "无" else
    paste(sprintf("%d天", e$duration), collapse = ", ")
  cat(sprintf("%-24s %-28s %d\n", nm, desc,
              if (is.null(e)) 0L else nrow(e)))
}

cat("\n---- 事件表列名 ----\n"); print(names(detect_event(mk(cases[[1]]), 5, 2)$event))
cat("\n---- 用 ts2clm 实证 windowHalfWidth 在 smoothPercentile=FALSE 下是否仍生效 ----\n")
set.seed(1)
d <- data.frame(t = as.Date("1983-01-01") + 0:(40*365 - 1))
d$temp <- 10 + 10*sin(2*pi*(as.numeric(format(d$t, "%j")))/365) + rnorm(nrow(d))
c1 <- ts2clm(d, climatologyPeriod = c("1983-01-01", "2012-12-31"),
             pctile = 90, windowHalfWidth = 5L, smoothPercentile = FALSE)
c2 <- ts2clm(d, climatologyPeriod = c("1983-01-01", "2012-12-31"),
             pctile = 90, windowHalfWidth = 0L, smoothPercentile = FALSE)
m <- merge(c1[, c("t", "thresh")], c2[, c("t", "thresh")], by = "t",
           suffixes = c("_w5", "_w0"))
cat(sprintf("11天窗 vs 0天窗 阈值差: mean=%.4f  max|d|=%.4f °C (n=%d)\n",
            mean(m$thresh_w5 - m$thresh_w0), max(abs(m$thresh_w5 - m$thresh_w0)),
            nrow(m)))
cat("⇒ 若差值显著非 0，则 smoothPercentile=FALSE 并不关闭 11 天窗合并。\n")
