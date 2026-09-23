import sys
sys.path.insert(0, 'python')
from coastal_buffer import build_coastal_buffer_mask

variants = {
    'A. fig1j 框（含黑海） lat30-47 lon5-42': {'lon': (5.0, 42.0), 'lat': (30.0, 47.0)},
    'B. 严格地中海（不含黑海） lat30-46 lon5-30': {'lon': (5.0, 30.0), 'lat': (30.0, 46.0)},
    'C. 含西班牙东岸 lat30-46 lon-6-36': {'lon': (-6.0, 36.0), 'lat': (30.0, 46.0)},
}

for name, reg in variants.items():
    m, d, info = build_coastal_buffer_mask(region=reg)
    n_land = info['land_cells_in_region']
    n_buf = info['cells_within_buffer']
    dmax = info['dist_km_max_within']
    print(f'{name}')
    print(f'   陆地格点 {n_land:5d}   缓冲内 {n_buf:5d}  ({100.0*n_buf/max(n_land,1):.1f}%)   缓冲内最大距海 {dmax:.1f} km')
    print()
