import xarray as xr
import pandas as pd
import numpy as np
import os

base = r"D:\2607compound\results\intermediate"

print("="*60)
print("VALIDATION REPORT")
print("="*60)

# 1. Load all datasets
ann_comp = xr.open_dataset(os.path.join(base, 'annual_compound_days.nc'))
ann_std = xr.open_dataset(os.path.join(base, 'annual_standalone_days.nc'))
ann_thw = xr.open_dataset(os.path.join(base, 'annual_thw_days.nc'))
chr_ds = xr.open_dataset(os.path.join(base, 'CHR_annual.nc'))
cooc = xr.open_dataset(os.path.join(base, 'cooccurrence_prob_annual.nc'))
mhw = pd.read_csv(os.path.join(base, 'mhw_events.csv'))
thw = pd.read_csv(os.path.join(base, 'thw_events.csv'))
pairs = pd.read_csv(os.path.join(base, 'coastal_pairs.csv'))

print("\n--- Dataset shapes and variables ---")
for name, ds in [('annual_compound', ann_comp), ('annual_standalone', ann_std), 
                  ('annual_thw', ann_thw), ('CHR', chr_ds), ('cooccurrence', cooc)]:
    print(f"{name}: dims={dict(ds.dims)}, vars={list(ds.data_vars)}")
    for var in ds.data_vars:
        da = ds[var]
        print(f"  {var}: shape={da.shape}, time_range={da.time.values[0]} to {da.time.values[-1]}")
        print(f"    min={float(np.nanmin(da.values)):.3f}, max={float(np.nanmax(da.values)):.3f}, mean={float(np.nanmean(da.values)):.3f}")

print("\n--- Event counts ---")
print(f"MHW events: {len(mhw)}")
print(f"THW events: {len(thw)}")
print(f"Coastal pairs: {len(pairs)}")

if 'event_start' in mhw.columns:
    print(f"MHW year range: {pd.to_datetime(mhw['event_start']).dt.year.min()} - {pd.to_datetime(mhw['event_start']).dt.year.max()}")
if 'event_start' in thw.columns:
    print(f"THW year range: {pd.to_datetime(thw['event_start']).dt.year.min()} - {pd.to_datetime(thw['event_start']).dt.year.max()}")

print("\n--- Compound event statistics ---")
comp = ann_comp[list(ann_comp.data_vars)[0]]
print(f"Compound days per year (spatial mean):")
for y in [2003, 2006, 2010, 2012, 2018, 2019, 2020, 2022, 2023]:
    yr_data = comp.sel(time=y)
    mean_val = float(np.nanmean(yr_data.values))
    max_val = float(np.nanmax(yr_data.values))
    print(f"  {y}: spatial_mean={mean_val:.2f} days, max={max_val:.1f} days")

print("\n--- CHR statistics ---")
chr_var = chr_ds[list(chr_ds.data_vars)[0]]
print(f"CHR time range: {chr_var.time.values[0]} to {chr_var.time.values[-1]}")
print(f"CHR global stats: min={float(np.nanmin(chr_var.values)):.3f}, max={float(np.nanmax(chr_var.values)):.3f}")
print(f"CHR mean over Europe (lat 30-72, lon -15-45):")
for y in range(1983, 2024):
    yr_data = chr_var.sel(time=y)
    mean_val = float(np.nanmean(yr_data.values))
    print(f"  {y}: {mean_val:.3f}")

print("\n--- Co-occurrence probability ---")
cooc_var = cooc[list(cooc.data_vars)[0]]
prob_map = cooc_var.mean(dim='time')
print(f"Co-occurrence prob range: {float(np.nanmin(prob_map.values)):.3f} - {float(np.nanmax(prob_map.values)):.3f}")

# Mediterranean region stats
med = prob_map.sel(lat=slice(30, 47), lon=slice(5, 42))
print(f"Mediterranean co-occurrence mean: {float(np.nanmean(med.values)):.3f}")

print("\n--- Sanity checks ---")
# Check compound <= standalone (compound is subset of thw)
comp_ts = comp.sum(dim=['lat','lon'])
std_ts = ann_std[list(ann_std.data_vars)[0]].sum(dim=['lat','lon'])
print(f"Compound total days: {int(comp_ts.sum())}")
print(f"Standalone total days: {int(std_ts.sum())}")
print(f"Total THW days (compound+standalone): {int(comp_ts.sum() + std_ts.sum())}")

# Check CHR = compound / standalone
chr_check = comp_ts / std_ts
chr_check_mean = float(np.nanmean(chr_check.values))
print(f"CHR check (compound/standalone mean): {chr_check_mean:.3f}")

print("\n--- Paper reference values (for comparison) ---")
print("From paper Fig 1: Top compound years should include 2003, 2006, 2010, 2012, 2018, 2019, 2020, 2022, 2023")
print("From paper Fig 2: CHR > 1 in Mediterranean, especially 2003, 2010, 2019, 2022-2023")
print("From paper: Compound events peak in Mediterranean & Black Sea region")
