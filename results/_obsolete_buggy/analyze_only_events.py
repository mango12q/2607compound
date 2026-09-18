import sys
sys.path.insert(0, r'D:\2607compound\python')
import xarray as xr
import numpy as np
import pandas as pd

ds = xr.open_dataset(r'E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc')
t2m = ds['T2m']
li, lo = 29, 318
ts = t2m.isel(lat=li, lon=lo).to_pandas()

# Python climatology
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
clim_series = pd.Series(clim_thresh[ts.index.dayofyear - 1], index=ts.index)

py_df = pd.read_csv(r"D:\2607compound\results\intermediate\thw_events.csv.bak")
py_events = py_df[(py_df['lat_idx'] == li) & (py_df['lon_idx'] == lo)].copy()
py_events['event_start'] = pd.to_datetime(py_events['event_start'])
py_events['event_end'] = pd.to_datetime(py_events['event_end'])

r_df = pd.read_csv(r"D:\2607compound\results\intermediate\thw_events_R_top500.csv")
r_events = r_df[(r_df['lat_idx'] == li) & (r_df['lon_idx'] == lo)].copy()
r_events['date_start'] = pd.to_datetime(r_events['date_start'])
r_events['date_end'] = pd.to_datetime(r_events['date_end'])

# Find Python-only events (not overlapped by any R event)
py_only = []
for _, pe in py_events.iterrows():
    overlap = False
    for _, re in r_events.iterrows():
        if not (pe['event_end'] < re['date_start'] or pe['event_start'] > re['date_end']):
            overlap = True
            break
    if not overlap:
        py_only.append(pe)

print(f"Python-only events: {len(py_only)} out of {len(py_events)}")

if len(py_only) > 0:
    ev = py_only[0]
    print(f"\nExample Python-only event: {ev['event_start'].date()} to {ev['event_end'].date()} ({ev['duration']} days)")
    start = ev['event_start'] - pd.Timedelta(days=3)
    end = ev['event_end'] + pd.Timedelta(days=3)
    subset = ts.loc[start:end]
    clim_subset = clim_series.loc[start:end]
    df = pd.DataFrame({'temp': subset, 'thresh': clim_subset, 'exceed': subset > clim_subset})
    print(df.to_string())

# Find R-only events
r_only = []
for _, re in r_events.iterrows():
    overlap = False
    for _, pe in py_events.iterrows():
        if not (re['date_end'] < pe['event_start'] or re['date_start'] > pe['event_end']):
            overlap = True
            break
    if not overlap:
        r_only.append(re)

print(f"\nR-only events: {len(r_only)} out of {len(r_events)}")
if len(r_only) > 0:
    ev = r_only[0]
    print(f"\nExample R-only event: {ev['date_start'].date()} to {ev['date_end'].date()} ({ev['duration']} days)")
    start = ev['date_start'] - pd.Timedelta(days=3)
    end = ev['date_end'] + pd.Timedelta(days=3)
    subset = ts.loc[start:end]
    clim_subset = clim_series.loc[start:end]
    df = pd.DataFrame({'temp': subset, 'thresh': clim_subset, 'exceed': subset > clim_subset})
    print(df.to_string())

ds.close()
