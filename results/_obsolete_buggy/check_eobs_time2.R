library(ncdf4)

nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
time_val <- ncvar_get(nc, 'time')
nc_close(nc)

cat('First 5 time values:', time_val[1:5], '\n')
dates <- as.Date(time_val[1:5], origin = '1950-01-01')
cat('First 5 dates:', dates, '\n')
cat('Last date:', as.Date(tail(time_val, 1), origin = '1950-01-01'), '\n')
