#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(ncdf4))

args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]

nc <- nc_open(eobs_file)

# Read just first time step
t2m_t0 <- ncvar_get(nc, "T2m", start = c(1, 1, 1), count = c(-1, -1, 1))
cat('t2m_t0 dim:', paste(dim(t2m_t0), collapse='x'), '\n')
cat('t2m_t0[182,19] =', t2m_t0[182, 19], '\n')
cat('t2m_t0[1,1] =', t2m_t0[1, 1], '\n')
cat('t2m_t0[464,201] =', t2m_t0[464, 201], '\n')

# Read full var and check same points
t2m_full <- ncvar_get(nc, "T2m")
cat('t2m_full[182,19,1] =', t2m_full[182, 19, 1], '\n')
cat('t2m_full[1,1,1] =', t2m_full[1, 1, 1], '\n')

# Check a transect
cat('\nFirst 5 lat at lon=182:\n')
print(t2m_t0[182, 1:5])

nc_close(nc)
