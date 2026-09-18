library(ncdf4)

nc <- nc_open('E:/2607compound/data/E-OBS/EOBS_tg_1983_2023.nc')
cat('Variables:', names(nc$var), '\n')
cat('Dimensions:', names(nc$dim), '\n')
for (d in names(nc$dim)) {
  cat(' ', d, ':', nc$dim[[d]]$len, '\n')
}
nc_close(nc)
