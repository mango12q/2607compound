import sys
sys.path.insert(0, r'D:\2607compound\python')
import xarray as xr
import numpy as np
import pandas as pd
import subprocess

ds = xr.open_dataset(r'E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc')
t2m = ds['T2m']
t2m_full = t2m.values
time_index = pd.DatetimeIndex(t2m.time.values)

# Find a grid point with high valid count in 1983-2012
clim_mask = (time_index.year >= 1983) & (time_index.year <= 2012)
valid_counts = np.nansum(~np.isnan(t2m_full[clim_mask, :, :]), axis=0)
best_li, best_lo = np.unravel_index(np.argmax(valid_counts), valid_counts.shape)
print(f"Best grid point: [{best_li},{best_lo}] ({t2m.lat[best_li].values:.2f}, {t2m.lon[best_lo].values:.2f})")
print(f"Valid days in 1983-2012: {valid_counts[best_li, best_lo]}")

li, lo = best_li, best_lo
ts = t2m.isel(lat=li, lon=lo).to_pandas()

# Python threshold
clim_vals = t2m_full[clim_mask, li, lo]
clim_doy = time_index.dayofyear[clim_mask]
clim_thresh = np.zeros(366)
for d in range(1, 367):
    vals = clim_vals[clim_doy == d]
    if len(vals) > 0:
        clim_thresh[d-1] = np.percentile(vals, 90)
py_thresh = pd.Series(clim_thresh[ts.index.dayofyear - 1], index=ts.index)

# R threshold
r_script = '''
suppressPackageStartupMessages(library(heatwaveR))
suppressPackageStartupMessages(library(ncdf4))
args <- commandArgs(trailingOnly = TRUE)
eobs_file <- args[1]
li <- as.integer(args[2])
lo <- as.integer(args[3])

nc <- nc_open(eobs_file)
t2m <- ncvar_get(nc, "T2m")
time_val <- ncvar_get(nc, "time")
nc_close(nc)

dates <- as.Date(time_val, origin = "1950-01-01")
temp_ts <- t2m[lo, li, ]
ts_df <- data.frame(t = dates, temp = temp_ts)
clm <- ts2clm(ts_df, climatologyPeriod = c("1983-01-01", "2012-12-31"), pctile = 90, smoothPercentile = FALSE, clmOnly = TRUE)

idx1999 <- which(format(dates, "%Y") == "1999")
for (i in idx1999) {
  val <- clm$thresh[i]
  if (is.na(val)) {
    cat(sprintf("%s NA\n", dates[i]))
  } else {
    cat(sprintf("%s %.4f\n", dates[i], val))
  }
}
'''

script_path = r'D:\2607compound\results\get_r_thresh2.R'
with open(script_path, 'w') as f:
    f.write(r_script)

res = subprocess.run(
    [r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe", script_path, r'E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc', str(li), str(lo)],
    capture_output=True, text=True
)

r_thresh = {}
for line in res.stdout.strip().split('\n'):
    parts = line.strip().split()
    if len(parts) == 2:
        r_thresh[pd.Timestamp(parts[0])] = float(parts[1]) if parts[1] != 'NA' else np.nan

r_thresh_series = pd.Series(r_thresh)

# Compare thresholds for 1999
print("\n=== Threshold comparison for 1999 ===")
comparison = pd.DataFrame({
    'py_thresh': py_thresh.loc['1999'].values,
    'r_thresh': r_thresh_series.reindex(py_thresh.loc['1999'].index).values,
})
comparison.index = py_thresh.loc['1999'].index.strftime('%m-%d')
comparison['diff'] = comparison['py_thresh'] - comparison['r_thresh']
print(comparison.to_string())

valid_diff = comparison['diff'].dropna()
print(f"\nMean diff (Python - R): {valid_diff.mean():.3f}")
print(f"Max abs diff: {valid_diff.abs().max():.3f}")
print(f"Days compared: {len(valid_diff)}")

ds.close()
