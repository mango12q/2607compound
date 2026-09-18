import subprocess, os, sys
sys.path.insert(0, r'D:\2607compound')
import pandas as pd
import numpy as np

RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
SCRIPT = r"D:\2607compound\python\detect_thw_subset_med.R"
EOBS = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"
OUT = r"D:\2607compound\results\intermediate\thw_events_subset_med.csv"

cmd = [RSCRIPT, SCRIPT, EOBS, OUT, "1983", "2012"]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("STDERR:", res.stderr)

r_df = pd.read_csv(OUT)
print(f"\nR subset events: {len(r_df)}")
if len(r_df) > 0:
    print(r_df[['lat_idx','lon_idx','date_start','date_end','duration']].head(10))

# Python subset for same lat/lon ranges
from python.detect_thw import detect_thw_all_points
from python.load_data import load_eobs
eobs = load_eobs()
t2m = eobs['T2m']
land_mask = t2m.notnull().any(dim='time').values

lat_vals = t2m.lat.values
lon_vals = t2m.lon.values
li_start = int(np.argmin(np.abs(lat_vals - 30)))
li_end = int(np.argmin(np.abs(lat_vals - 45)))
lo_start = int(np.argmin(np.abs(lon_vals - 5)))
lo_end = int(np.argmin(np.abs(lon_vals - 35)))

sub_points = [(li, lo) for li in range(li_start, li_end+1) for lo in range(lo_start, lo_end+1) if land_mask[li, lo]]
print(f"\nPython subset points: {len(sub_points)} (lat {li_start}-{li_end}, lon {lo_start}-{lo_end})")

py_df = detect_thw_all_points(t2m, t2m.time.to_pandas().index, land_mask, clim_start=1983, clim_end=2012)
sub_py = py_df[(py_df['lat_idx'] >= li_start) & (py_df['lat_idx'] <= li_end) & (py_df['lon_idx'] >= lo_start) & (py_df['lon_idx'] <= lo_end)]
print(f"Python subset events: {len(sub_py)}")
if len(sub_py) > 0:
    print(sub_py[['lat_idx','lon_idx','event_start','event_end','duration']].head(10))
