library(ncdf4)

nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
t2m <- ncvar_get(nc, 'T2m')
nc_close(nc)

cat('t2m dimensions:', dim(t2m), '\n')
cat('length(t2m[,1,1]):', length(t2m[, 1, 1]), '\n')

# Check what ts2clm sees
dates <- seq(as.Date('1983-01-01'), by = 'day', length.out = length(t2m[, 1, 1]))
cat('Date range:', min(dates), 'to', max(dates), '\n')
cat('Number of dates:', length(dates), '\n')
