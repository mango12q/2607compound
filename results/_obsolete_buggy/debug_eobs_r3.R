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

# Original dims are (lon, lat, time) = (464, 201, 14975)
# To get time series at (lat_idx, lon_idx): t2m[lon_idx, lat_idx, ]

li_start <- which.min(abs(lat - 30))
li_end <- which.min(abs(lat - 45))
lo_start <- which.min(abs(lon - 5))
lo_end <- which.min(abs(lon - 35))

cat(sprintf('Testing lat[%d-%d]=%.2f-%.2f lon[%d-%d]=%.2f-%.2f\n',
  li_start, li_end, lat[li_start], lat[li_end], lo_start, lo_end, lon[lo_start], lon[lo_end]))
cat(sprintf('t2m dim: %s\n', paste(dim(t2m), collapse='x')))

for (li in li_start:min(li_start+2, li_end)) {
  for (lo in lo_start:min(lo_start+2, lo_end)) {
    ts <- t2m[lo, li, ]
    cat(sprintf('  [%d,%d] len=%d valid=%d min=%.1f max=%.1f\n', li, lo, length(ts), sum(!is.na(ts)), min(ts, na.rm=TRUE), max(ts, na.rm=TRUE)))
  }
}

# Also test ts2clm + detect_event on one point
li <- li_start
lo <- lo_start
ts <- t2m[lo, li, ]
ts_df <- data.frame(t = dates, temp = ts)
cat('\nTesting ts2clm+detect_event on [', li, ',', lo, ']...\n')
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
