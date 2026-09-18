library(ncdf4)

nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
time_val <- ncvar_get(nc, 'time')
nc_close(nc)

cat('First 5 time values:', time_val[1:5], '\n')

# Try common origins
for (origin_str in c('1900-01-01', '1950-01-01', '1970-01-01')) {
  origin <- as.POSIXct(origin_str, tz='UTC')
  dates <- as.Date(origin + time_val[1:5])
  cat('Using origin', origin_str, ':', dates, '\n')
}

# Check time attrs
nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
cat('Time units:', nc$dim$time$units, '\n')
cat('Time calendar:', nc$dim$time$calendar, '\n')
nc_close(nc)
