"""
verify_data.py — 数据完整性校验
检查合并后的 OISST 和 E-OBS 文件是否存在且维度正确。
"""
import os
import xarray as xr

from config import (
    BASE_DIR,
    OISST_MERGED_FILE, EOBS_MERGED_FILE,
    SST_CLIM_FILE, T2M_CLIM_FILE,
    MHW_EVENTS_CSV, THW_EVENTS_CSV,
    COASTAL_PAIRS_CSV,
    COMPOUND_NC, STANDALONE_NC,
    CLIM_PERIOD,
)


def check_file(path, label, min_size_mb=1.0):
    if not os.path.exists(path):
        print(f"  MISSING: {label}")
        print(f"    Path: {path}")
        return False

    size_mb = os.path.getsize(path) / 1e6
    if size_mb < min_size_mb:
        print(f"  TOO SMALL: {label} ({size_mb:.1f} MB, expected >= {min_size_mb:.1f} MB)")
        return False

    print(f"  OK: {label} ({size_mb:.1f} MB)")
    return True


def check_nc_file(path, label, expected_dims=None, min_size_mb=1.0):
    if not os.path.exists(path):
        print(f"  MISSING: {label}")
        return False

    size_mb = os.path.getsize(path) / 1e6
    if size_mb < min_size_mb:
        print(f"  TOO SMALL: {label} ({size_mb:.1f} MB, expected >= {min_size_mb:.1f} MB)")
        return False

    try:
        ds = xr.open_dataset(path)
        dims = dict(ds.sizes)
        ds.close()

        print(f"  OK: {label} ({size_mb:.1f} MB)")
        print(f"    Dims: {dims}")

        if expected_dims:
            for dim, expected_size in expected_dims.items():
                actual_size = dims.get(dim)
                if actual_size is None:
                    print(f"    WARNING: dimension '{dim}' not found")
                elif abs(actual_size - expected_size) > 10:
                    print(f"    WARNING: dim '{dim}' = {actual_size}, expected ~{expected_size}")

        return True
    except Exception as e:
        print(f"  ERROR opening {label} with open_dataset, trying open_dataarray: {e}")
        try:
            da = xr.open_dataarray(path)
            dims = dict(da.sizes)
            da.close()
            print(f"  OK: {label} ({size_mb:.1f} MB, as DataArray)")
            print(f"    Dims: {dims}")
            return True
        except Exception as e2:
            print(f"  ERROR opening {label} as DataArray: {e2}")
            return False


def verify_all():
    print("=" * 60)
    print("Data Verification Report")
    print("=" * 60)

    all_ok = True

    print("\n[1] Preprocessed data files:")
    all_ok &= check_nc_file(
        OISST_MERGED_FILE, "OISST merged",
        expected_dims={'time': 15340, 'lat': 720, 'lon': 1440}
    )
    all_ok &= check_nc_file(
        EOBS_MERGED_FILE, "E-OBS merged",
        expected_dims={'time': 14245, 'lat': 201, 'lon': 464}
    )

    print("\n[2] Climatology files:")
    all_ok &= check_nc_file(SST_CLIM_FILE, "SST climatology", min_size_mb=10)
    all_ok &= check_nc_file(T2M_CLIM_FILE, "T2m climatology", min_size_mb=1)

    print("\n[3] Detection results:")
    all_ok &= check_file(MHW_EVENTS_CSV, "MHW events CSV", min_size_mb=0.1)
    all_ok &= check_file(THW_EVENTS_CSV, "THW events CSV", min_size_mb=0.1)

    print("\n[4] Coastal pairs:")
    all_ok &= check_file(COASTAL_PAIRS_CSV, "Coastal pairs CSV", min_size_mb=0.1)

    print("\n[5] Compound events:")
    all_ok &= check_nc_file(COMPOUND_NC, "Compound events NC", min_size_mb=1)
    all_ok &= check_nc_file(STANDALONE_NC, "Standalone days NC", min_size_mb=1)

    print("\n" + "=" * 60)
    if all_ok:
        print("All data files present and valid.")
    else:
        print("Some data files are missing or invalid. Check the output above.")
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    verify_all()
