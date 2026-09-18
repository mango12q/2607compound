#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(ncdf4))

args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]

nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")
lat <- ncvar_get(nc, "lat")
lon <- ncvar_get(nc, "lon")
nc_close(nc)

cat('t2m dim:', dim(t2m), '\n')
cat('lat[1:5]:', lat[1:5], '\n')
cat('lon[1:5]:', lon[1:5], '\n')

# Mediterranean region
li_start <- which.min(abs(lat - 30))
li_end <- which.min(abs(lat - 45))
lo_start <- which.min(abs(lon - 5))
lo_end <- which.min(abs(lon - 35))

cat(sprintf('lat[%d]=%.2f, lat[%d]=%.2f\n', li_start, lat[li_start], li_end, lat[li_end]))
cat(sprintf('lon[%d]=%.2f, lon[%d]=%.2f\n', lo_start, lon[lo_start], lo_end, lon[lo_end]))

# Check a few points
for (li in li_start:min(li_start+2, li_end)) {
  for (lo in lo_start:min(lo_start+2, lo_end)) {
    ts <- t2m[, li, lo]
    valid <- sum(!is.na(ts))
    cat(sprintf('  [%d,%d] valid=%d/%d, range=%.1f-%.1f\n', li, lo, valid, length(ts), min(ts, na.rm=TRUE), max(ts, na.rm=TRUE)))
  }
}
