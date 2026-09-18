library(heatwaveR)

cat("=== heatwaveR API smoke test ===\n")

# Make a 10-year synthetic daily temperature series with a clear heatwave
set.seed(1)
dates <- seq(as.Date('2000-01-01'), as.Date('2009-12-31'), by = 'day')
n <- length(dates)
temp <- 15 + 5 * sin(2 * pi * (1:n) / 365) + rnorm(n, 0, 1)
# Inject a 7-day heatwave in summer 2003
idx <- which(dates >= as.Date('2003-08-01') & dates <= as.Date('2003-08-07'))
temp[idx] <- temp[idx] + 8

ts_df <- data.frame(t = dates, temp = temp)
cat('Series length:', nrow(ts_df), '\n')

clm <- ts2clm(ts_df, climatologyPeriod = c('2000-01-01', '2009-12-31'), pctile = 90, smoothPercentile = FALSE)
cat('ts2clm OK, threshold range:', round(range(clm$thresh, na.rm=TRUE), 2), '\n')

ev <- detect_event(ts_df, seasClim = clm$seas, threshClim = clm$thresh)
cat('detect_event OK, events:', nrow(ev$event), '\n')
if (nrow(ev$event) > 0) {
  print(ev$event[, c('event_start', 'event_end', 'duration')])
}
cat('=== smoke test passed ===\n')
