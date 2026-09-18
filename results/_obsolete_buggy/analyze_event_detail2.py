import sys
sys.path.insert(0, r'D:\2607compound\python')
import xarray as xr
import numpy as np
import pandas as pd

ds = xr.open_dataset(r'E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc')
t2m = ds['T2m']

li, lo = 29, 318
lat_val = float(t2m.lat[li].values)
lon_val = float(t2m.lon[lo].values)
print(f'Grid point [{li},{lo}] = ({lat_val:.2f}, {lon_val:.2f})')

ts = t2m.isel(lat=li, lon=lo).to_pandas()

# Compute 90th percentile climatology using Python (same as detect_thw.py)
t2m_full = t2m.values
clim_values = t2m_full[:, li, lo]
time_index = pd.DatetimeIndex(t2m.time.values)
doy = time_index.dayofyear.values

# Compute 90th percentile per DOY over 1983-2012
clim_mask = (time_index.year >= 1983) & (time_index.year <= 2012)
clim_vals = t2m_full[clim_mask, li, lo]
clim_doy = doy[clim_mask]

clim_thresh = np.zeros(366)
for d in range(1, 367):
    vals = clim_vals[clim_doy == d]
    if len(vals) > 0:
        clim_thresh[d-1] = np.percentile(vals, 90)
    else:
        clim_thresh[d-1] = np.nan

clim_series = pd.Series(clim_thresh[ts.index.dayofyear - 1], index=ts.index)

# Python events
py_df = pd.read_csv(r"D:\2607compound\results\intermediate\thw_events.csv.bak")
py_events = py_df[(py_df['lat_idx'] == li) & (py_df['lon_idx'] == lo)].copy()
py_events['event_start'] = pd.to_datetime(py_events['event_start'])
py_events['event_end'] = pd.to_datetime(py_events['event_end'])

# R events
r_df = pd.read_csv(r"D:\2607compound\results\intermediate\thw_events_R_top500.csv")
r_events = r_df[(r_df['lat_idx'] == li) & (r_df['lon_idx'] == lo)].copy()
r_events['date_start'] = pd.to_datetime(r_events['date_start'])
r_events['date_end'] = pd.to_datetime(r_events['date_end'])

print(f'\nPython events: {len(py_events)}')
print(f'R events: {len(r_events)}')

# Show 1998 events
print('\n--- 1998 events ---')
print('Python:')
py_98 = py_events[py_events['event_start'].dt.year == 1998]
if len(py_98) > 0:
    print(py_98[['event_start', 'event_end', 'duration']].to_string())
else:
    print('None')

print('\nR:')
r_98 = r_events[r_events['date_start'].dt.year == 1998]
if len(r_98) > 0:
    print(r_98[['date_start', 'date_end', 'duration']].to_string())
else:
    print('None')

# Show a Python-only event with temperature context
if len(py_98) > 0:
    ev = py_98.iloc[0]
    start = ev['event_start'] - pd.Timedelta(days=5)
    end = ev['event_end'] + pd.Timedelta(days=5)
    subset = ts.loc[start:end]
    clim_subset = clim_series.loc[start:end]
    print(f'\nTemperature around Python event {ev["event_start"].date()} - {ev["event_end"].date()}:')
    df = pd.DataFrame({'temp': subset, 'thresh': clim_subset, 'exceed': subset > clim_subset})
    print(df.to_string())

ds.close()
