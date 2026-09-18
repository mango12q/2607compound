import subprocess, os, pandas as pd

RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
SCRIPT = r"D:\2607compound\python\detect_thw_subset_med.R"
EOBS = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"
OUT = r"D:\2607compound\results\intermediate\thw_events_subset_med.csv"

cmd = [RSCRIPT, SCRIPT, EOBS, OUT, "1983", "2012"]
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("STDERR:", res.stderr)

df = pd.read_csv(OUT)
print(f"R subset events: {len(df)}")
if len(df) > 0:
    print(df[['lat_idx','lon_idx','date_start','date_end','duration']].head(10))

# Compare with Python subset for same region
from python.detect_thw import detect_thw_all_points
from python.load_data import load_eobs
eobs = load_eobs()
t2m = eobs['T2m']
import numpy as np
land_mask = t2m.notnull().any(dim='time').values
sub_points = [(li, lo) for li in range(20, 31) for lo in range(40, 51) if land_mask[li, lo]]
print(f"Python subset points: {len(sub_points)}")
py_df = detect_thw_all_points(t2m, t2m.time.to_pandas().index, land_mask, clim_start=1983, clim_end=2012)
sub_py = py_df[(py_df['lat_idx'] >= 20) & (py_df['lat_idx'] <= 30) & (py_df['lon_idx'] >= 40) & (py_df['lon_idx'] <= 50)]
print(f"Python subset events: {len(sub_py)}")
if len(sub_py) > 0:
    print(sub_py[['lat_idx','lon_idx','event_start','event_end','duration']].head(10))
