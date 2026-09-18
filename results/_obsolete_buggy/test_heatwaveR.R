library(heatwaveR)
library(ncdf4)

cat("Testing heatwaveR with data.frame input...\n")

nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
t2m <- ncvar_get(nc, 'T2m')
lat <- ncvar_get(nc, 'lat')
lon <- ncvar_get(nc, 'lon')
time_val <- ncvar_get(nc, 'time')
nc_close(nc)

cat('Data shape:', length(time_val), 'x', length(lat), 'x', length(lon), '\n')

temp_ts <- t2m[, 1, 1]
start_date <- as.Date('1983-01-01')
dates <- seq(start_date, by = 'day', length.out = length(temp_ts))

# Create data.frame like heatwaveR expects
ts_df <- data.frame(t = dates, temp = temp_ts)

cat('Testing ts2clm + detect_event on one grid point...\n')
clm <- tryCatch(
  ts2clm(ts_df, climatologyPeriod = c(1983, 2012), pctile = 90, smoothPercentile = FALSE),
  error = function(e) e
)
if (inherits(clm, 'error')) {
  cat('ts2clm FAILED:', clm$message, '\n')
} else {
  cat('ts2clm OK, rows:', nrow(clm), '\n')
  ev <- tryCatch(
    detect_event(ts_df, seasClim = clm$seas, threshClim = clm$thresh),
    error = function(e) e
  )
  if (inherits(ev, 'error')) {
    cat('detect_event FAILED:', ev$message, '\n')
  } else {
    cat('detect_event OK, events:', nrow(ev$event), '\n')
    if (nrow(ev$event) > 0) {
      print(head(ev$event[, c('event_start', 'event_end', 'duration')]))
    }
  }
}
