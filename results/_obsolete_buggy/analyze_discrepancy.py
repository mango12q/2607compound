import subprocess, os, sys
sys.path.insert(0, r'D:\2607compound\python')
import pandas as pd
import numpy as np

# Load both results
py_df = pd.read_csv(r"D:\2607compound\results\intermediate\thw_events.csv.bak")
py_df['event_start'] = pd.to_datetime(py_df['event_start'])
py_df['event_end'] = pd.to_datetime(py_df['event_end'])

r_df = pd.read_csv(r"D:\2607compound\results\intermediate\thw_events_R_top500.csv")
r_df['date_start'] = pd.to_datetime(r_df['date_start'])
r_df['date_end'] = pd.to_datetime(r_df['date_end'])

# Find a grid point with many Python events but few R events
py_counts = py_df.groupby(['lat_idx', 'lon_idx']).size().reset_index(name='py_count')
r_counts = r_df.groupby(['lat_idx', 'lon_idx']).size().reset_index(name='r_count')
merged = pd.merge(py_counts, r_counts, on=['lat_idx', 'lon_idx'], how='inner')
merged['ratio'] = merged['r_count'] / merged['py_count']
merged['diff'] = merged['py_count'] - merged['r_count']

# Pick a point with high Python count and some R events (not zero)
candidates = merged[(merged['py_count'] > 10) & (merged['r_count'] > 0)].nsmallest(5, 'ratio')
print("Candidates for detailed comparison:")
print(candidates)

if len(candidates) > 0:
    li, lo = candidates.iloc[0]['lat_idx'], candidates.iloc[0]['lon_idx']
    print(f"\n=== Detailed comparison for grid point [{li},{lo}] ===")
    
    py_events = py_df[(py_df['lat_idx'] == li) & (py_df['lon_idx'] == lo)].sort_values('event_start')
    r_events = r_df[(r_df['lat_idx'] == li) & (r_df['lon_idx'] == lo)].sort_values('date_start')
    
    print(f"\nPython events: {len(py_events)}")
    print(py_events[['event_start', 'event_end', 'duration']].head(10).to_string())
    
    print(f"\nR events: {len(r_events)}")
    print(r_events[['date_start', 'date_end', 'duration']].head(10).to_string())
    
    # Check if R events are contained in Python events
    print(f"\n--- Overlap analysis ---")
    py_starts = set(py_events['event_start'].dt.date)
    py_ends = set(py_events['event_end'].dt.date)
    r_starts = set(r_events['date_start'].dt.date)
    r_ends = set(r_events['date_end'].dt.date)
    
    print(f"Python event starts: {len(py_starts)} unique")
    print(f"R event starts: {len(r_starts)} unique")
    print(f"R starts in Python starts: {len(r_starts & py_starts)}")
    print(f"R starts NOT in Python: {len(r_starts - py_starts)}")
