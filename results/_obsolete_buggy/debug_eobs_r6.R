#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))

args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]

nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")
lat <- ncvar_get(nc, "lat")
lon <- ncvar_get(nc, "lon")
time_val <- ncvar_get(nc, "time")
nc_close(nc)

dates <- as.Date(time_val, origin = "1950-01-01")
clim_period <- c('1983-01-01', '2012-12-31')

# Test with known good point: [55,156] = (39.12, -1.38) Spain
li <- 55; lo <- 156
cat(sprintf('Testing [%d,%d] = (%.2f, %.2f)\n', li, lo, lat[li], lon[lo]))

# Correct indexing for (lon, lat, time) = (464, 201, 14975)
ts <- t2m[lo, li, ]
cat(sprintf('len=%d valid=%d range=%.1f-%.1f\n', length(ts), sum(!is.na(ts)), min(ts, na.rm=TRUE), max(ts, na.rm=TRUE)))

ts_df <- data.frame(t = dates, temp = ts)
clm <- tryCatch(ts2clm(ts_df, climatologyPeriod = clim_period, pctile = 90, smoothPercentile = FALSE, clmOnly = TRUE), error=function(e) e)
if (inherits(clm, 'error')) {
  cat('ts2clm FAILED:', clm$message, '\n')
} else {
  cat('ts2clm OK\n')
  ev <- tryCatch(detect_event(ts_df, seasClim = clm$seas, threshClim = clm$thresh), error=function(e) e)
  if (inherits(ev, 'error')) {
    cat('detect_event FAILED:', ev$message, '\n')
  } else {
    cat('detect_event OK, events:', nrow(ev$event), '\n')
    if (nrow(ev$event) > 0) print(head(ev$event[, c('date_start', 'date_end', 'duration')]))
  }
}
