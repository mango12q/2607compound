import xarray as xr
import numpy as np
import os

base = r"D:\2607compound\results\intermediate"

ann_comp = xr.open_dataset(os.path.join(base, 'annual_compound_days.nc'))
ann_std = xr.open_dataset(os.path.join(base, 'annual_standalone_days.nc'))
ann_thw = xr.open_dataset(os.path.join(base, 'annual_thw_days.nc'))
chr_ds = xr.open_dataset(os.path.join(base, 'CHR_annual.nc'))
cooc = xr.open_dataset(os.path.join(base, 'cooccurrence_prob_annual.nc'))

comp = ann_comp['compound_mhw_thw']
std = ann_std['standalone_thw']
thw = ann_thw['compound_mhw_thw']
chr_var = chr_ds['__xarray_dataarray_variable__']
cooc_var = cooc['compound_mhw_thw']

print("="*60)
print("CROSS-CONSISTENCY VALIDATION")
print("="*60)

# 1. THW decomposition: annual_thw == compound + standalone
recon = comp + std
diff = thw - recon
n_diff = int(np.sum(diff != 0))
print(f"\n[1] annual_thw == compound + standalone (per-grid-cell check)")
print(f"    Mismatched cells: {n_diff} / {diff.size}")
print(f"    Max absolute diff: {float(np.nanmax(np.abs(diff.values))):.6f}")
if n_diff == 0:
    print("    PASS: Decomposition is exact.")
else:
    print("    FAIL: Decomposition mismatch detected.")

# 2. CHR definition check: is CHR = compound / standalone?
chr_recon = comp / std
chr_recon = xr.where(np.isfinite(chr_recon), chr_recon, np.nan)
chr_diff = chr_var - chr_recon
n_chr_diff = int(np.sum(~np.isclose(chr_var.values, chr_recon.values, equal_nan=True)))
print(f"\n[2] CHR == compound / standalone (per-grid-cell check)")
print(f"    Mismatched cells: {n_chr_diff} / {chr_diff.size}")
print(f"    Max absolute diff: {float(np.nanmax(np.abs(chr_diff.values))):.6f}")
if n_chr_diff == 0:
    print("    PASS: CHR formula matches compound/standalone.")
else:
    print("    FAIL: CHR formula mismatch or NaN handling difference.")

# 3. CHR global extreme values
print(f"\n[3] CHR extreme value audit")
print(f"    CHR max (global): {float(np.nanmax(chr_var.values)):.3f}")
print(f"    CHR min (global): {float(np.nanmin(chr_var.values)):.3f}")
over_10 = float(np.sum(chr_var.values > 10)) / chr_var.size * 100
over_50 = float(np.sum(chr_var.values > 50)) / chr_var.size * 100
print(f"    Cells with CHR > 10: {over_10:.4f}%")
print(f"    Cells with CHR > 50: {over_50:.4f}%")

# Show grid cells with very high CHR
high_chr = chr_var.where(chr_var > 20, drop=True)
if high_chr.size > 0:
    print(f"    Grid cells with CHR > 20:")
    times, lats, lons = np.where(chr_var.values > 20)
    for i in range(min(10, len(times))):
        t, la, lo = times[i], lats[i], lons[i]
        print(f"      year={int(chr_var.time.values[t])}, lat={float(chr_var.lat.values[la]):.2f}, lon={float(chr_var.lon.values[lo]):.2f}, CHR={float(chr_var.values[t,la,lo]):.2f}, comp={int(comp.values[t,la,lo])}, std={int(std.values[t,la,lo])}")

# 4. Co-occurrence probability bounds
print(f"\n[4] Co-occurrence probability bounds")
print(f"    Min: {float(np.nanmin(cooc_var.values)):.3f}")
print(f"    Max: {float(np.nanmax(cooc_var.values)):.3f}")
if float(np.nanmin(cooc_var.values)) >= 0 and float(np.nanmax(cooc_var.values)) <= 1:
    print("    PASS: Values within [0, 1].")
else:
    print("    FAIL: Values out of bounds [0, 1].")

# 5. Spatial coverage check
print(f"\n[5] Spatial coverage check (non-zero cells over time)")
comp_nonzero = float(np.sum(comp.values > 0)) / comp.size * 100
std_nonzero = float(np.sum(std.values > 0)) / std.size * 100
thw_nonzero = float(np.sum(thw.values > 0)) / thw.size * 100
print(f"    Compound non-zero: {comp_nonzero:.3f}%")
print(f"    Standalone non-zero: {std_nonzero:.3f}%")
print(f"    THW non-zero: {thw_nonzero:.3f}%")

# 6. Temporal consistency
print(f"\n[6] Temporal consistency")
for y in range(1983, 2024):
    yr_comp = int(comp.sel(time=y).sum())
    yr_std = int(std.sel(time=y).sum())
    yr_thw = int(thw.sel(time=y).sum())
    match = "OK" if yr_comp + yr_std == yr_thw else "MISMATCH"
    print(f"    {y}: compound={yr_comp}, standalone={yr_std}, thw={yr_thw} [{match}]")

# 7. Annual THW days range
print(f"\n[7] annual_thw variable naming note")
print(f"    Variable name in annual_thw_days.nc: 'compound_mhw_thw'")
print(f"    This is identical to annual_compound_days.nc variable name.")
print(f"    Content check: annual_thw should equal compound + standalone.")
print(f"    Global annual_thw sum: {int(thw.sum())}")
print(f"    compound + standalone sum: {int(comp.sum() + std.sum())}")
