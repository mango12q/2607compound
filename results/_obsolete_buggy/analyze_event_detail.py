import sys
sys.path.insert(0, r'D:\2607compound\python')
import xarray as xr
import numpy as np
import pandas as pd

# Load E-OBS
ds = xr.open_dataset(r'E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc')
t2m = ds['T2m']

# Grid point [29, 318]
li, lo = 29, 318
lat_val = float(t2m.lat[li].values)
lon_val = float(t2m.lon[lo].values)
print(f'Grid point [{li},{lo}] = ({lat_val:.2f}, {lon_val:.2f})')

# Get full time series
ts = t2m.isel(lat=li, lon=lo).to_pandas()
clim = t2m.isel(lat=li, lon=lo).groupby('time.dayofyear').quantile(0.9).reindex(ts.index.dayofyear).values

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

# Show a few events side by side
print('\n--- 1998 events ---')
print('Python:')
py_98 = py_events[py_events['event_start'].dt.year == 1998]
print(py_98[['event_start', 'event_end', 'duration']].to_string())
print('\nR:')
r_98 = r_events[r_events['date_start'].dt.year == 1998]
print(r_98[['date_start', 'date_end', 'duration']].to_string())

# Check the temperature around a Python-only event
if len(py_98) > 0:
    ev = py_98.iloc[0]
    start = ev['event_start'] - pd.Timedelta(days=5)
    end = ev['event_end'] + pd.Timedelta(days=5)
    subset = ts.loc[start:end]
    clim_subset = pd.Series(clim, index=ts.index).loc[start:end]
    print(f'\nTemperature around Python event {ev["event_start"].date()} - {ev["event_end"].date()}:')
    df = pd.DataFrame({'temp': subset, 'thresh': clim_subset, 'exceed': subset > clim_subset})
    print(df.to_string())

ds.close()
