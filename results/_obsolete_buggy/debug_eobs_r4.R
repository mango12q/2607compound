#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(ncdf4))

args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]

nc <- nc_open(eobs_file)

# Try reading just one grid point directly
lat_target <- 30.0
lon_target <- 5.0

lat <- ncvar_get(nc, "lat")
lon <- ncvar_get(nc, "lon")
time_val <- ncvar_get(nc, "time")

li <- which.min(abs(lat - lat_target))
lo <- which.min(abs(lon - lon_target))
cat(sprintf('Closest to (%.1f, %.1f) -> [%d,%d] = (%.2f, %.2f)\n',
  lat_target, lon_target, li, lo, lat[li], lon[lo]))

# Method 1: read full variable
t2m_full <- ncvar_get(nc, "T2m")
cat(sprintf('Full var dim: %s\n', paste(dim(t2m_full), collapse='x')))
cat(sprintf('t2m_full[%d,%d,] valid=%d\n', lo, li, sum(!is.na(t2m_full[lo, li, ]))))

# Method 2: read with index
idx <- list(lo, li, TRUE)
t2m_idx <- ncvar_get(nc, "T2m", start = c(lo, li, 1), count = c(1, 1, -1))
cat(sprintf('t2m_idx len=%d valid=%d range=%.1f-%.1f\n',
  length(t2m_idx), sum(!is.na(t2m_idx)), min(t2m_idx, na.rm=TRUE), max(t2m_idx, na.rm=TRUE)))

nc_close(nc)
