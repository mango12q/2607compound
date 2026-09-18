import subprocess, os, sys
sys.path.insert(0, r'D:\2607compound\python')
import pandas as pd
import numpy as np

RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
SCRIPT = r"D:\2607compound\python\detect_thw_subset_top.R"
EOBS = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"
OUT = r"D:\2607compound\results\intermediate\thw_events_R_top500.csv"

# Load Python results and find top 500 grid points by event count
py_df = pd.read_csv(r"D:\2607compound\results\intermediate\thw_events.csv.bak")
py_df['event_start'] = pd.to_datetime(py_df['event_start'])
py_counts = py_df.groupby(['lat_idx', 'lon_idx']).size().reset_index(name='py_count')
top500 = py_counts.nlargest(500, 'py_count')
print(f"Top 500 grid points have {top500['py_count'].sum()} events ({len(py_df)} total)")

# Write grid points to a temp file for R to read
points_file = r"D:\2607compound\results\intermediate\top500_points.csv"
top500.to_csv(points_file, index=False)

# Create a modified R script that only processes these points
r_script = r'''
suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))

args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]
points_file <- args[2]
output_file <- args[3]
clim_start <- as.integer(args[4])
clim_end <- as.integer(args[5])

points <- read.csv(points_file)
cat(sprintf("Processing %d grid points...\n", nrow(points)))

nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")
lat <- ncvar_get(nc, "lat")
lon <- ncvar_get(nc, "lon")
time_val <- ncvar_get(nc, "time")
nc_close(nc)

dates <- as.Date(time_val, origin = "1950-01-01")
clim_period <- c(sprintf("%04d-01-01", clim_start), sprintf("%04d-12-31", clim_end))

all_events <- list()
for (i in 1:nrow(points)) {
  li <- points$lat_idx[i]
  lo <- points$lon_idx[i]
  temp_ts <- t2m[lo, li, ]
  valid <- sum(!is.na(temp_ts))
  if (valid < 730) next

  ts_df <- data.frame(t = dates, temp = temp_ts)
  result <- tryCatch({
    clm <- ts2clm(ts_df, climatologyPeriod = clim_period, pctile = 90, smoothPercentile = FALSE, clmOnly = TRUE)
    ev <- detect_event(ts_df, seasClim = clm$seas, threshClim = clm$thresh)
    ev$event
  }, error = function(e) NULL)

  if (!is.null(result) && nrow(result) > 0) {
    result$lat_idx <- li
    result$lon_idx <- lo
    result$lat <- lat[li]
    result$lon <- lon[lo]
    all_events[[length(all_events) + 1]] <- result
  }
}

if (length(all_events) > 0) {
  combined <- do.call(rbind, all_events)
} else {
  combined <- data.frame()
}

cat(sprintf("Total THW events detected: %d\n", nrow(combined)))
write.csv(combined, output_file, row.names = FALSE)
cat(sprintf("Saved to: %s\n", output_file))
'''

subset_script = r"D:\2607compound\python\detect_thw_subset_top.R"
with open(subset_script, 'w') as f:
    f.write(r_script)

cmd = [RSCRIPT, subset_script, EOBS, points_file, OUT, "1983", "2012"]
print("Running R heatwaveR on top 500 grid points...")
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout[-2000:] if len(res.stdout) > 2000 else res.stdout)
if res.stderr:
    print("STDERR:", res.stderr[-1000:])

r_df = pd.read_csv(OUT)
print(f"\nR THW events (top 500 points): {len(r_df)}")

# Compare
py_top500 = py_df[(py_df['lat_idx'].isin(top500['lat_idx'])) & (py_df['lon_idx'].isin(top500['lon_idx']))]
print(f"Python THW events (same points): {len(py_top500)}")
print(f"Ratio: {len(r_df) / max(len(py_top500), 1):.2f}")

if len(r_df) > 0 and len(py_top500) > 0:
    r_counts = r_df.groupby(['lat_idx', 'lon_idx']).size().reset_index(name='r_count')
    py_counts2 = py_top500.groupby(['lat_idx', 'lon_idx']).size().reset_index(name='py_count')
    merged = pd.merge(r_counts, py_counts2, on=['lat_idx', 'lon_idx'], how='outer').fillna(0)
    merged['ratio'] = merged['r_count'] / merged['py_count'].replace(0, np.nan)
    print(f"Median event count ratio (R/Python): {merged['ratio'].median():.2f}")
    print(f"Mean ratio: {merged['ratio'].mean():.2f}")
    print(f"Points where R > Python: {(merged['ratio'] > 1).sum()}")
    print(f"Points where R < Python: {(merged['ratio'] < 1).sum()}")
    print(f"Points where R == Python: {(merged['ratio'] == 1).sum()}")
