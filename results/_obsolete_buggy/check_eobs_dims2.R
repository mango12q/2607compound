library(ncdf4)

nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
cat('t2m dimensions:', dim(nc$var$T2m), '\n')
cat('time length:', nc$dim$time$len, '\n')
cat('lat length:', nc$dim$lat$len, '\n')
cat('lon length:', nc$dim$lon$len, '\n')
nc_close(nc)
