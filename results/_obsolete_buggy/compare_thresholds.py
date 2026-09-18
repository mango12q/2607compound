import sys
sys.path.insert(0, r'D:\2607compound\python')
import xarray as xr
import numpy as np
import pandas as pd
import subprocess

# Python threshold
ds = xr.open_dataset(r'E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc')
t2m = ds['T2m']
li, lo = 29, 318
ts = t2m.isel(lat=li, lon=lo).to_pandas()
t2m_full = t2m.values
clim_values = t2m_full[:, li, lo]
time_index = pd.DatetimeIndex(t2m.time.values)
clim_mask = (time_index.year >= 1983) & (time_index.year <= 2012)
clim_vals = t2m_full[clim_mask, li, lo]
clim_doy = time_index.dayofyear[clim_mask]
clim_thresh = np.zeros(366)
for d in range(1, 367):
    vals = clim_vals[clim_doy == d]
    if len(vals) > 0:
        clim_thresh[d-1] = np.percentile(vals, 90)
py_thresh = pd.Series(clim_thresh[ts.index.dayofyear - 1], index=ts.index)

# R threshold - run a small R script
r_script = '''
suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))
args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]
li <- as.integer(args[2])
lo <- as.integer(args[3])

nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")
lat <- ncvar_get(nc, "lat")
lon <- ncvar_get(nc, "lon")
time_val <- ncvar_get(nc, "time")
nc_close(nc)

dates <- as.Date(time_val, origin = "1950-01-01")
temp_ts <- t2m[lo, li, ]
ts_df <- data.frame(t = dates, temp = temp_ts)
clm <- ts2clm(ts_df, climatologyPeriod = c("1983-01-01", "2012-12-31"), pctile = 90, smoothPercentile = FALSE, clmOnly = TRUE)

# Output threshold for 1999
idx1999 <- which(format(dates, "%Y") == "1999")
for (i in idx1999) {
  cat(sprintf("%s %.4f\n", dates[i], clm$thresh[i]))
}
'''

script_path = r'D:\2607compound\results\get_r_thresh.R'
with open(script_path, 'w') as f:
    f.write(r_script)

res = subprocess.run(
    [r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe", script_path, r'E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc', str(li), str(lo)],
    capture_output=True, text=True
)

r_thresh_lines = res.stdout.strip().split('\n')
r_thresh = {}
for line in r_thresh_lines:
    parts = line.strip().split()
    if len(parts) == 2:
        r_thresh[pd.Timestamp(parts[0])] = float(parts[1])

r_thresh_series = pd.Series(r_thresh)

# Compare thresholds for 1999
print("=== Threshold comparison for 1999 ===")
comparison = pd.DataFrame({
    'py_thresh': py_thresh.loc['1999'].values,
    'r_thresh': r_thresh_series.reindex(py_thresh.loc['1999'].index).values,
    'diff': py_thresh.loc['1999'].values - r_thresh_series.reindex(py_thresh.loc['1999'].index).values
})
comparison.index = py_thresh.loc['1999'].index.strftime('%m-%d')
print(comparison.to_string())

print(f"\nMean diff (Python - R): {comparison['diff'].mean():.3f}")
print(f"Max diff: {comparison['diff'].abs().max():.3f}")

ds.close()
