#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))

args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]
output_file <- args[2]
clim_start <- as.integer(args[3])
clim_end <- as.integer(args[4])

nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")
lat <- ncvar_get(nc, "lat")
lon <- ncvar_get(nc, "lon")
time_val <- ncvar_get(nc, "time")
nc_close(nc)

t2m <- aperm(t2m, c(3, 2, 1))
dates <- as.Date(time_val, origin = "1950-01-01")
clim_period <- c(sprintf("%04d-01-01", clim_start), sprintf("%04d-12-31", clim_end))

li_start <- which.min(abs(lat - 30))
li_end <- which.min(abs(lat - 45))
lo_start <- which.min(abs(lon - 5))
lo_end <- which.min(abs(lon - 35))

cat(sprintf('Testing lat[%d-%d]=%.2f-%.2f lon[%d-%d]=%.2f-%.2f\n',
  li_start, li_end, lat[li_start], lat[li_end], lo_start, lo_end, lon[lo_start], lon[lo_end]))
cat(sprintf('t2m dim after aperm: %s\n', paste(dim(t2m), collapse='x')))

for (li in li_start:min(li_start+2, li_end)) {
  for (lo in lo_start:min(lo_start+2, lo_end)) {
    ts <- t2m[, li, lo]
    cat(sprintf('  [%d,%d] len=%d valid=%d min=%.1f max=%.1f\n', li, lo, length(ts), sum(!is.na(ts)), min(ts, na.rm=TRUE), max(ts, na.rm=TRUE)))
  }
}
