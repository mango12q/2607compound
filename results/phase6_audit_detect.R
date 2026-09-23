#!/usr/bin/env Rscript
# =============================================================================
# phase6_audit_detect.R — D-2 检测语义审计（R 侧：heatwaveR 真实语义的权威证据）
#
# 本脚本**不采信**任何项目文档自述，直接从本机安装的 heatwaveR 提取函数体，
# 并用判别性实验测定其游程/桥接语义；随后在真实 CESM 序列上产出权威阈值与事件，
# 供 phase6_audit_detect.py 做跨语言对照。
#
# 输出目录: results/intermediate/audit/detect/
#   heatwaveR_source_evidence.txt   —— 决定性源码摘录（含行号）
#   synth_discriminative.csv        —— 合成判别性用例的 heatwaveR 结果
#   R_thr_w11_<tag>.csv             —— windowHalfWidth=5 阈值 (date + 点列)
#   R_thr_w01_<tag>.csv             —— windowHalfWidth=0 阈值 (单日分位, 抽样点)
#   R_ev_<tag>_w<NN>.csv            —— detect_event 事件表
#   R_counts_<tag>.csv              —— 逐点事件数/超标天数汇总 (w11 vs w01)
#
# 用法:
#   Rscript phase6_audit_detect.R [in_dir] [out_dir]
# in_dir 需含 python 侧导出的 series_<var>_<exp>_<mem>.csv (第 1 列为 date)。
# =============================================================================

suppressPackageStartupMessages(library(heatwaveR))

args <- commandArgs(trailingOnly = TRUE)
IN_DIR  <- if (length(args) >= 1) args[1] else "D:/2607compound/results/intermediate/audit/detect"
OUT_DIR <- if (length(args) >= 2) args[2] else IN_DIR
MODE    <- if (length(args) >= 3) args[3] else "all"   # all | fuzz | force
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

W11 <- 5L      # 11 天窗（windowHalfWidth=5）
W01 <- 0L      # 单日分位（windowHalfWidth=0）
MIN_DUR <- 5L
MAX_GAP <- 2L
CLIM <- c("2000-01-01", "2021-12-31")
N_SUB <- 24L   # windowHalfWidth=0 抽样点数

cat("== phase6_audit_detect.R ==\n")
cat("heatwaveR ", as.character(packageVersion("heatwaveR")),
    " @ ", system.file(package = "heatwaveR"), "\n", sep = "")
cat("R ", R.version.string, "\n", sep = "")
cat("IN_DIR  = ", IN_DIR, "\nOUT_DIR = ", OUT_DIR, "\n", sep = "")

# =============================================================================
# 1. 源码证据（决定性）
# =============================================================================
dump_src <- function(expr, label) {
  cat("\n----- ", label, " -----\n", sep = "")
  print(expr)
}

ev_path <- file.path(OUT_DIR, "heatwaveR_source_evidence.txt")
sink(ev_path)
cat("=================================================================\n")
cat("heatwaveR ", as.character(packageVersion("heatwaveR")),
    " 真实函数体摘录（本机安装包，非项目文档）\n", sep = "")
cat("pkg path: ", system.file(package = "heatwaveR"), "\n", sep = "")
cat("R: ", R.version.string, "\n", sep = "")
cat("生成时间: ", format(Sys.time()), "\n", sep = "")
cat("=================================================================\n")

cat("\n\n########## [证据 1] ts2clm：windowHalfWidth 与 smoothPercentile 的关系 ##########\n")
cat("# 关键: clim_spread(clim_start,clim_end,windowHalfWidth) 与 clim_calc/clim_calc_cpp\n")
cat("#       是**无条件**执行的；smoothPercentile 只控制是否再做 31 天滚动**均值**平滑。\n")
cat("#       因此 smoothPercentile=FALSE 时 11 天窗**仍然生效**。\n\n")
b <- get("ts2clm", envir = asNamespace("heatwaveR"))
src <- deparse(b)
for (i in grep("clim_spread|clim_calc|smoothPercentile|smooth_percentile|ts_clim <-",
               src)) cat(sprintf("%4d| %s\n", i, src[i]))

cat("\n\n########## [证据 2] clim_calc：11 天窗内**合并原始样本**后取分位 ##########\n")
b2 <- get("clim_calc", envir = asNamespace("heatwaveR"))
src2 <- deparse(b2)
for (i in grep("windowHalfWidth|quantile|for \\(i in", src2)) cat(sprintf("%4d| %s\n", i, src2[i]))

cat("\n\n########## [证据 3] detect_event：判据 = 严格大于 且 非 NA ##########\n")
b3 <- get("detect_event", envir = asNamespace("heatwaveR"))
src3 <- deparse(b3)
for (i in grep("threshCriterion|is.na\\(ts_y\\)|proto_event\\(", src3)) cat(sprintf("%4d| %s\n", i, src3[i]))

cat("\n\n########## [证据 4] ★proto_event：先按原始游程 >= minDuration 过滤，再桥接空隙 ##########\n")
cat("# 这是 E3 的判决性证据：\n")
cat("#   (a) ex1 <- rle(criterion_column) 得到**原始**超标游程；\n")
cat("#   (b) proto_events[proto_events$duration >= minDuration, ] 先**过滤**；\n")
cat("#   (c) 之后才 joinAcrossGaps 把 <= maxGap 的空隙填 TRUE。\n")
cat("# => 不足 minDuration 的短游程**在桥接前就被丢弃**，永远无法被桥接成事件。\n\n")
b4 <- get("proto_event", envir = asNamespace("heatwaveR"))
print(b4)
sink()
cat("已写出源码证据 -> ", ev_path, "\n", sep = "")

# =============================================================================
# 2. 合成判别性实验
# =============================================================================
mk <- function(n, exc) {
  t <- as.Date("2001-01-01") + 0:(n - 1)
  temp <- rep(0, n); temp[exc] <- 1
  data.frame(t = t, temp = temp, seas = 0, thresh = 0.5)
}

run_case <- function(label, n, exc) {
  ev <- detect_event(mk(n, exc), minDuration = MIN_DUR, maxGap = MAX_GAP)$event
  # detect_event 在"无事件"时返回 1 行 event_no=NA 的占位行（detect_events.R 亦如此剔除）
  if (!is.null(ev) && nrow(ev) > 0L) ev <- ev[!is.na(ev$event_no), , drop = FALSE]
  if (is.null(ev) || nrow(ev) == 0L) {
    data.frame(case = label, n_exceed_days = length(exc), n_events = 0L,
               starts = "", ends = "", durations = "")
  } else {
    data.frame(case = label, n_exceed_days = length(exc), n_events = nrow(ev),
               starts = paste(as.character(ev$date_start), collapse = ";"),
               ends = paste(as.character(ev$date_end), collapse = ";"),
               durations = paste(ev$duration, collapse = ";"))
  }
}

cases <- list(
  list("3+2gap+3 (both runs <5)",        30, c(10:12, 15:17)),
  list("1+2gap+4 (both runs <5)",        30, c(10, 13:16)),
  list("4+2gap+4 (both runs <5)",        30, c(10:13, 16:19)),
  list("2+2gap+5 (short run at head)",   30, c(1:2, 5:9)),
  list("5+2gap+4 (2nd run <5)",          30, c(10:14, 17:20)),
  list("4+2gap+5 (1st run <5)",          30, c(10:13, 16:20)),
  list("5+2gap+3+2gap+5 (middle <5)",    40, c(10:14, 17:19, 22:26)),
  list("5+1gap+5 (gap=1)",               30, c(10:14, 16:20)),
  list("5+2gap+5 (gap=2, boundary)",     30, c(10:14, 17:21)),
  list("5+3gap+5 (gap=3 > maxGap)",      30, c(10:14, 18:22)),
  list("5+2gap+5+2gap+5 (chain)",        40, c(10:14, 17:21, 24:28)),
  list("6+2gap+6",                       40, c(10:15, 18:23)),
  list("10 contiguous (no gap)",         30, 10:19),
  list("4 contiguous (<5, single run)",  30, 10:13),
  list("5+2gap+2+2gap+5",                40, c(10:14, 17:18, 21:25)),
  # ★ 尾部空档吸收 / 头部空档不吸收（proto_event 判据 index_end > 首个种子起点）
  list("TAIL: 5 exc 20-24, n=26 (尾空档=2<=maxGap)", 26, 20:24),
  list("TAIL: 5 exc 25-29, n=30 (尾空档=1)",         30, 25:29),
  list("TAIL: 5 exc 22-26, n=30 (尾空档=4>maxGap)",  30, 22:26),
  list("HEAD: 5 exc 3-7, n=30 (头空档=2, 应不吸收)", 30, 3:7),
  list("HEAD: 5 exc 1-5, n=30 (无头空档)",           30, 1:5),
  list("TAIL+HEAD: 5 exc 3-7, n=9 (尾空档=2)",       9,  3:7)
)
synth <- do.call(rbind, lapply(cases, function(cs) run_case(cs[[1]], cs[[2]], cs[[3]])))
synth_path <- file.path(OUT_DIR, "synth_discriminative.csv")
write.csv(synth, synth_path, row.names = FALSE)
cat("\n== 合成判别性实验 (heatwaveR", as.character(packageVersion("heatwaveR")), ") ==\n")
print(synth, row.names = FALSE)
cat("-> ", synth_path, "\n", sep = "")

# =============================================================================
# 3. 模糊测试：真实 heatwaveR proto_event 语义 vs Python 实现
#    （用例由 Python 生成于 fuzz_cases.csv，保证两侧输入逐位一致；
#      阈值与事件逻辑解耦: 自建 seas=0 / thresh=0.5 的气候态数据框）
# =============================================================================
fuzz_in <- file.path(IN_DIR, "fuzz_cases.csv")
if (file.exists(fuzz_in)) {
  fc <- read.csv(fuzz_in, stringsAsFactors = FALSE,
                 colClasses = c(case = "character", pattern = "character"))
  cat("\n== 模糊测试: ", nrow(fc), " 条随机 0/1 序列 ==\n", sep = "")
  out <- list()
  k <- 0
  for (md in c(5L, 3L, 7L)) {
    for (mg in c(2L, 1L, 3L)) {
      for (i in seq_len(nrow(fc))) {
        pat <- fc$pattern[i]
        n <- nchar(pat)
        x <- as.integer(strsplit(pat, "")[[1]])
        d <- data.frame(t = as.Date("2001-01-01") + 0:(n - 1),
                        temp = x, seas = 0, thresh = 0.5)
        ev <- detect_event(d, minDuration = md, maxGap = mg)$event
        if (!is.null(ev) && nrow(ev) > 0L) ev <- ev[!is.na(ev$event_no), , drop = FALSE]
        k <- k + 1
        if (is.null(ev) || nrow(ev) == 0L) {
          out[[k]] <- data.frame(case = fc$case[i], min_dur = md, max_gap = mg,
                                 n_events = 0L, starts = "", ends = "",
                                 durations = "")
        } else {
          out[[k]] <- data.frame(
            case = fc$case[i], min_dur = md, max_gap = mg, n_events = nrow(ev),
            starts = paste(as.integer(ev$date_start - as.Date("2001-01-01")) + 1L,
                           collapse = ";"),
            ends = paste(as.integer(ev$date_end - as.Date("2001-01-01")) + 1L,
                         collapse = ";"),
            durations = paste(ev$duration, collapse = ";"))
        }
      }
    }
  }
  fz <- do.call(rbind, out)
  write.csv(fz, file.path(OUT_DIR, "fuzz_R.csv"), row.names = FALSE)
  cat("fuzz 结果 -> fuzz_R.csv (", nrow(fz), " 行 / 9 组参数 )\n", sep = "")
} else {
  cat("\n[提示] 无 fuzz_cases.csv；先运行 python results/phase6_audit_detect.py --only fuzz\n")
}

# =============================================================================
# 4. 真实 CESM 序列：权威阈值 + 事件
# =============================================================================
# 逐点跑 heatwaveR；返回 thresh 向量(对齐原始日期)、事件表、超标天数
process_point <- function(dates, vals, win) {
  df <- data.frame(t = dates, temp = vals)
  clm <- ts2clm(df, climatologyPeriod = CLIM, pctile = 90,
                windowHalfWidth = win, smoothPercentile = FALSE)
  thr_full <- clm$thresh
  m <- match(as.character(dates), as.character(clm$t))
  thr <- thr_full[m]
  ev <- detect_event(clm, minDuration = MIN_DUR, maxGap = MAX_GAP)$event
  if (!is.null(ev) && nrow(ev) > 0L) ev <- ev[!is.na(ev$event_no), , drop = FALSE]
  n_ev <- if (is.null(ev) || nrow(ev) == 0L) 0L else nrow(ev)
  exceed <- sum(!is.na(vals) & !is.na(thr) & vals > thr)
  list(thresh = thr, events = ev, n_ev = n_ev, exceed = exceed)
}

run_series <- function(tag, csv, do_w01 = FALSE) {
  cat("\n---- 真实序列: ", tag, " (", basename(csv), ") ----\n", sep = "")
  d <- read.csv(csv, check.names = FALSE)
  dates <- as.Date(d[[1]])
  cols <- setdiff(names(d), names(d)[1])
  cat("点数: ", length(cols), "  天数: ", length(dates), "\n", sep = "")

  thr11 <- matrix(NA_real_, nrow = length(dates), ncol = length(cols))
  thr01 <- matrix(NA_real_, nrow = length(dates), ncol = length(cols))
  counts <- vector("list", length(cols))
  ev_all <- vector("list", length(cols))

  t0 <- Sys.time()
  for (k in seq_along(cols)) {
    vals <- as.numeric(d[[cols[k]]])
    r11 <- process_point(dates, vals, W11)
    thr11[, k] <- r11$thresh
    if (do_w01) {
      r01 <- process_point(dates, vals, W01)
      thr01[, k] <- r01$thresh
    } else {
      r01 <- list(n_ev = NA_integer_, exceed = NA_integer_)
    }
    counts[[k]] <- data.frame(point = cols[k],
                              n_ev_w11 = r11$n_ev, n_exceed_w11 = r11$exceed,
                              n_ev_w01 = r01$n_ev, n_exceed_w01 = r01$exceed,
                              thr_mean_w11 = mean(r11$thresh, na.rm = TRUE),
                              thr_mean_w01 = if (do_w01) mean(thr01[, k], na.rm = TRUE) else NA_real_)
    if (!is.null(r11$events) && nrow(r11$events) > 0L) {
      ev_all[[k]] <- data.frame(
        point = cols[k],
        event_start = as.character(r11$events$date_start),
        event_end = as.character(r11$events$date_end),
        duration = r11$events$duration,
        stringsAsFactors = FALSE)
    }
  }
  cat("耗时 ", round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 1), " s\n", sep = "")

  out11 <- data.frame(date = dates, thr11, check.names = FALSE)
  names(out11) <- c("date", cols)
  cnt <- do.call(rbind, counts)
  evs <- if (length(ev_all)) do.call(rbind, ev_all) else
    data.frame(point = character(), event_start = character(),
               event_end = character(), duration = integer())

  write.csv(out11, file.path(OUT_DIR, paste0("R_thr_w11_", tag, ".csv")), row.names = FALSE)
  if (do_w01) {
    out01 <- data.frame(date = dates, thr01, check.names = FALSE)
    names(out01) <- c("date", cols)
    write.csv(out01, file.path(OUT_DIR, paste0("R_thr_w01_", tag, ".csv")), row.names = FALSE)
  }
  write.csv(evs, file.path(OUT_DIR, paste0("R_ev_", tag, "_w11.csv")), row.names = FALSE)
  write.csv(cnt, file.path(OUT_DIR, paste0("R_counts_", tag, ".csv")), row.names = FALSE)

  cat(sprintf("  heatwaveR(11d窗): 总事件 %d, 总超标日 %d\n",
              sum(cnt$n_ev_w11), sum(cnt$n_exceed_w11)))
  if (do_w01) {
    cat(sprintf("  heatwaveR(单日):   总事件 %d, 总超标日 %d\n",
                sum(cnt$n_ev_w01), sum(cnt$n_exceed_w01)))
  }
  cat("  -> R_thr_w11_", tag, ".csv / R_counts_", tag, ".csv\n", sep = "")
  invisible(NULL)
}

files <- list.files(IN_DIR, pattern = "^series_.*\\.csv$", full.names = TRUE)
if (MODE == "fuzz") {
  cat("\n[MODE=fuzz] 跳过真实序列环节。\n")
} else if (length(files) == 0L) {
  cat("\n[警告] 未找到 series_*.csv，跳过真实序列环节。\n")
} else {
  for (f in files) {                                    # 全点, 仅 11 天窗
    tag <- sub("^series_", "", sub("\\.csv$", "", basename(f)))
    if (MODE != "force" && file.exists(file.path(OUT_DIR, paste0("R_thr_w11_", tag, ".csv")))) {
      cat("\n[跳过] 已有 R_thr_w11_", tag, ".csv\n", sep = ""); next
    }
    run_series(tag, f, do_w01 = FALSE)
  }
  for (f in files) {                                    # 抽样点, 11 天窗 + 单日
    tag <- sub("^series_", "", sub("\\.csv$", "", basename(f)))
    tag2 <- paste0(tag, "_sub", N_SUB)
    if (MODE != "force" && file.exists(file.path(OUT_DIR, paste0("R_thr_w01_", tag2, ".csv")))) {
      cat("\n[跳过] 已有 R_thr_w01_", tag2, ".csv\n", sep = ""); next
    }
    d <- read.csv(f, check.names = FALSE)
    cols <- setdiff(names(d), names(d)[1])
    idx <- unique(round(seq(1, length(cols), length.out = N_SUB)))
    sub <- d[, c(1, 1 + idx)]
    sp <- file.path(OUT_DIR, paste0("_sub_series_", tag, ".csv"))
    write.csv(sub, sp, row.names = FALSE)
    run_series(tag2, sp, do_w01 = TRUE)
    file.remove(sp)
  }
}

cat("\n== phase6_audit_detect.R 完成 ==\n")
