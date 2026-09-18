import xarray as xr
import os

oisst_path = r"E:\2607compound\data\OISST\oisst_v2.1_1982_2023.nc"
eobs_path = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"

print("=== OISST merged ===")
oisst = xr.open_dataset(oisst_path)
print(f"Variables: {list(oisst.data_vars)}")
print(f"Dims: {dict(oisst.dims)}")
print(f"Time range: {oisst.time.values[0]} to {oisst.time.values[-1]}")
print(f"Lat range: {float(oisst.lat.min()):.2f} to {float(oisst.lat.max()):.2f}")
print(f"Lon range: {float(oisst.lon.min()):.2f} to {float(oisst.lon.max()):.2f}")
print(f"File size: {os.path.getsize(oisst_path)/1e9:.2f} GB")
oisst.close()

print("\n=== E-OBS merged ===")
eobs = xr.open_dataset(eobs_path)
print(f"Variables: {list(eobs.data_vars)}")
print(f"Dims: {dict(eobs.dims)}")
print(f"Time range: {eobs.time.values[0]} to {eobs.time.values[-1]}")
print(f"Lat range: {float(eobs.lat.min()):.2f} to {float(eobs.lat.max()):.2f}")
print(f"Lon range: {float(eobs.lon.min()):.2f} to {float(eobs.lon.max()):.2f}")
print(f"File size: {os.path.getsize(eobs_path)/1e6:.1f} MB")
print(f"Version attr: {eobs.attrs.get('eobs_version_note', 'N/A')}")
eobs.close()

print("\n=== ERA5 files ===")
era5_dir = r"E:\2607compound\data\ERA5"
for root, dirs, files in os.walk(era5_dir):
    for f in sorted(files):
        fp = os.path.join(root, f)
        print(f"  {fp.replace(era5_dir, '').lstrip(os.sep)}: {os.path.getsize(fp)/1e6:.1f} MB")
