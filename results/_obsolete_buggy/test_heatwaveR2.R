library(heatwaveR)
library(ncdf4)

cat("Testing heatwaveR with proper Date handling...\n")

nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
t2m <- ncvar_get(nc, 'T2m')
nc_close(nc)

temp_ts <- t2m[, 1, 1]
dates <- seq(as.Date('1983-01-01'), by = 'day', length.out = length(temp_ts))
ts_df <- data.frame(t = dates, temp = temp_ts)

cat('Data range:', min(ts_df$t), 'to', max(ts_df$t), '\n')

# Try with character dates
clm <- tryCatch(
  ts2clm(ts_df, climatologyPeriod = c('1983-01-01', '2012-12-31'), pctile = 90, smoothPercentile = FALSE),
  error = function(e) e
)
if (inherits(clm, 'error')) {
  cat('ts2clm FAILED:', clm$message, '\n')
  # Try with Date objects
  clm2 <- tryCatch(
    ts2clm(ts_df, climatologyPeriod = as.Date(c('1983-01-01', '2012-12-31')), pctile = 90, smoothPercentile = FALSE),
    error = function(e) e
  )
  if (inherits(clm2, 'error')) {
    cat('ts2clm Date FAILED:', clm2$message, '\n')
  } else {
    cat('ts2clm with Date OK!\n')
    ev <- detect_event(ts_df, seasClim = clm2$seas, threshClim = clm2$thresh)
    cat('detect_event OK, events:', nrow(ev$event), '\n')
  }
} else {
  cat('ts2clm OK!\n')
  ev <- detect_event(ts_df, seasClim = clm$seas, threshClim = clm$thresh)
  cat('detect_event OK, events:', nrow(ev$event), '\n')
}
