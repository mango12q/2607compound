import subprocess, os, sys
sys.path.insert(0, r'D:\2607compound\python')
import pandas as pd
import numpy as np

RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
SCRIPT = r"D:\2607compound\python\detect_thw.R"
EOBS = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"
OUT = r"D:\2607compound\results\intermediate\thw_events_R.csv"

# Backup old results
old_csv = r"D:\2607compound\results\intermediate\thw_events.csv"
if os.path.exists(old_csv):
    os.replace(old_csv, old_csv + '.bak')
    print(f'Backed up old results to {old_csv}.bak')

cmd = [RSCRIPT, SCRIPT, EOBS, OUT, "1983", "2012"]
print("Running R heatwaveR detection (this may take a few minutes)...")
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout[-2000:] if len(res.stdout) > 2000 else res.stdout)
if res.stderr:
    print("STDERR (last 1000 chars):", res.stderr[-1000:])

r_df = pd.read_csv(OUT)
print(f"\nR THW events: {len(r_df)}")
if len(r_df) > 0:
    print(r_df[['lat_idx','lon_idx','date_start','date_end','duration']].head(10))
    print(f"R year range: {pd.to_datetime(r_df['date_start']).dt.year.min()} - {pd.to_datetime(r_df['date_start']).dt.year.max()}")

# Load old Python results
py_df = pd.read_csv(old_csv + '.bak')
py_df['event_start'] = pd.to_datetime(py_df['event_start'])
py_df['event_end'] = pd.to_datetime(py_df['event_end'])
print(f"\nPython THW events: {len(py_df)}")
if len(py_df) > 0:
    print(py_df[['lat_idx','lon_idx','event_start','event_end','duration']].head(10))

# Compare
print(f"\n=== Comparison ===")
print(f"R events: {len(r_df)}")
print(f"Python events: {len(py_df)}")
print(f"Ratio: {len(r_df) / max(len(py_df), 1):.2f}")

if len(r_df) > 0 and len(py_df) > 0:
    # Compare by grid point
    r_counts = r_df.groupby(['lat_idx', 'lon_idx']).size().reset_index(name='r_count')
    py_counts = py_df.groupby(['lat_idx', 'lon_idx']).size().reset_index(name='py_count')
    merged = pd.merge(r_counts, py_counts, on=['lat_idx', 'lon_idx'], how='outer').fillna(0)
    merged['diff'] = merged['r_count'] - merged['py_count']
    merged['ratio'] = merged['r_count'] / merged['py_count'].replace(0, np.nan)
    print(f"\nGrid points with events: R={len(r_counts)}, Python={len(py_counts)}, overlap={len(merged.dropna())}")
    print(f"Mean event count ratio (R/Python): {merged['ratio'].median():.2f}")
    print(f"Diff stats: mean={merged['diff'].mean():.1f}, std={merged['diff'].std():.1f}")
