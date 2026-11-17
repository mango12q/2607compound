# -*- coding: utf-8 -*-
"""Region-definition sensitivity for Fig. 4 (read-only diagnostic).

Motivation
----------
Fig. 4 currently uses the Mediterranean & Black Sea box (lat 30-47 / lon 5-42,
64 of the 206 CESM coastal pairs) and the `med_mean` column of the annual
compound-exposure tables.  AGENTS.md lists "coastal buffer / analysis domain" as
one of the two remaining cheap sensitivities.  This script tests whether the
already-concluded Fig. 4 match (15/15 paper anchors inside our bootstrap CI)
depends on that regional choice.

Two regions are compared, both with the *same* event tables (`_v12w50`):
  med   -- lat 30-47 / lon 5-42, compound column `med_mean`      (current main line)
  all   -- all 206 coastal pairs, compound column `eur_mean`     (Europe-wide)

Only the *series construction* differs; the statistical kernel is the production
one (`gev_return_period.analyse_return_periods_emp`, 1000x bootstrap).
Nothing is written except this script's stdout (tee'd to a log by the caller).

Usage:
    python logs/_diag_region_sens.py [_v12w50] [_v12w60]
"""
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "python"))

import phase6_cesm as P                     # noqa: E402
from phase6_cesm import _force_utf8_stdout  # noqa: E402
import gev_return_period as G               # noqa: E402

_force_utf8_stdout()

RPS = (5, 10, 20, 50, 100)   # note: json.dump turns these int keys into strings
PAPER = {
    "marine": [2.30, 3.80, 6.30, 13.4, 24.0],
    "terrestrial": [1.26, 1.46, 1.75, 2.44, 3.26],
    "compound": [1.96, 2.56, 3.50, 5.14, 7.85],
}
PAPER_LO = {
    "marine": [2.1, 3.3, 5.5, 11.5, 20.7],
    "terrestrial": [1.2, 1.3, 1.6, 2.1, 2.8],
    "compound": [1.6, 2.0, 2.6, 3.5, 5.0],
}
PAPER_HI = {
    "marine": [2.7, 4.5, 7.8, 17.3, 34.8],
    "terrestrial": [1.3, 1.5, 1.9, 2.8, 3.8],
    "compound": [2.4, 3.3, 4.8, 7.4, 12.1],
}

REGIONS = {
    "med": dict(compound_col="med_mean",
                mask=lambda df: (df.land_lat.between(30, 47) &
                                 df.land_lon.between(5, 42)).values),
    "all": dict(compound_col="eur_mean",
                mask=lambda df: np.ones(len(df), dtype=bool)),
}


def member_series(exp, member, tag, pairs_df, sub, compound_col):
    """Same construction as phase6_cesm._member_exposure_series, but the compound
    column and the pair subset are parameters (the production version hardcodes
    the Mediterranean box + `med_mean`)."""
    t2m_path = os.path.join(P.CESM_INT, f"{exp}_{member}_T2m.nc")
    with xr.open_dataset(t2m_path) as ds:
        time_da = ds["T2m"]
        nt = time_da.sizes["time"]
        years = time_da.time.dt.year.values
        t0 = pd.Timestamp(time_da.time.values[0]).normalize()

    mhw = pd.read_csv(os.path.join(P.CESM_INT, f"mhw{tag}_{exp}_{member}.csv"),
                      parse_dates=["event_start", "event_end"])
    thw = pd.read_csv(os.path.join(P.CESM_INT, f"thw{tag}_{exp}_{member}.csv"),
                      parse_dates=["event_start", "event_end"])

    ocean_keys = list({(int(a), int(b)) for a, b in
                       sub[["ocean_lat_idx", "ocean_lon_idx"]].itertuples(index=False)})
    land_keys = list({(int(a), int(b)) for a, b in
                      sub[["land_lat_idx", "land_lon_idx"]].itertuples(index=False)})

    mo = P._event_masks_by_key(mhw, set(ocean_keys), nt, t0)
    tl = P._event_masks_by_key(thw, set(land_keys), nt, t0)
    ann_o, uyears = P._annual_exposure_from_masks(mo, ocean_keys, years)
    ann_l, _ = P._annual_exposure_from_masks(tl, land_keys, years)

    ca = pd.read_csv(os.path.join(P.CESM_INT, f"annual{tag}_{exp}_{member}.csv"))
    comp = ca.set_index("year")[compound_col].reindex(uyears).values

    return {
        "marine": ann_o.mean(axis=1),
        "terrestrial": ann_l.mean(axis=1),
        "compound": comp,
    }


def collect(tag, pairs_df, region):
    mask = REGIONS[region]["mask"](pairs_df)
    sub = pairs_df[mask]
    col = REGIONS[region]["compound_col"]
    out = {"marine": {"ALL": [], "XGHG": []},
           "terrestrial": {"ALL": [], "XGHG": []},
           "compound": {"ALL": [], "XGHG": []}}
    for exp in ("ALL", "XGHG"):
        for m in P.C.CESM_ALL_MEMBERS:
            s = member_series(exp, m, tag, pairs_df, sub, col)
            for panel in out:
                out[panel][exp].append(np.asarray(s[panel], dtype=float))
    return out, len(sub)


def n_unique(sub, which):
    if which == "ocean":
        return len({(int(a), int(b)) for a, b in
                    sub[["ocean_lat_idx", "ocean_lon_idx"]].itertuples(index=False)})
    return len({(int(a), int(b)) for a, b in
                sub[["land_lat_idx", "land_lon_idx"]].itertuples(index=False)})


def main():
    tags = sys.argv[1:] or ["_v12w50"]
    pairs_df = pd.read_csv(P.PAIRS_CSV)
    print("pairs total =", len(pairs_df), " members =", len(P.C.CESM_ALL_MEMBERS))

    for tag in tags:
        print("\n" + "=" * 104)
        print(f"TAG {tag}   (event tables reused; only the region/aggregation column changes)")
        results = {}
        for region in ("med", "all"):
            series, n_sub = collect(tag, pairs_df, region)
            sub = pairs_df[REGIONS[region]["mask"](pairs_df)]
            print(f"\n  region={region:3s}  pairs={n_sub:3d}  "
                  f"unique_ocean={n_unique(sub, 'ocean'):3d} unique_land={n_unique(sub, 'land'):3d}"
                  f"  compound_col={REGIONS[region]['compound_col']}")
            results[region] = {}
            for panel in ("marine", "terrestrial", "compound"):
                a = np.concatenate(series[panel]["ALL"])
                f = np.concatenate(series[panel]["XGHG"])
                res = G.analyse_return_periods_emp(a, f, n_bootstrap=1000)
                results[region][panel] = res
                vals, ins = [], []
                for k, rp in enumerate(RPS):
                    node = res["all"][rp]
                    med_v = node["median"]
                    lo, hi = node["ci_lower"], node["ci_upper"]
                    vals.append(med_v)
                    ins.append("IN " if (lo <= PAPER[panel][k] <= hi) else "out")
                print("    %-12s mean_expo ALL=%6.2f XGHG=%6.2f | RP %s | %s"
                      % (panel, a.mean(), f.mean(),
                         "/".join("%7.1f" % v if np.isfinite(v) else "    inf" for v in vals),
                         " ".join(ins)))

        print("\n  vs paper:")
        for panel in ("marine", "terrestrial", "compound"):
            row_m = results["med"][panel]["all"]
            row_a = results["all"][panel]["all"]
            print("    %-12s paper %s" % (panel, "/".join("%5.2f" % v for v in PAPER[panel])))
            for region, row in (("med", row_m), ("all", row_a)):
                meds = [row[rp]["median"] for rp in RPS]
                print("    %-12s %-4s %s" % ("", region,
                      "/".join("%5.2f" % v if np.isfinite(v) else "  inf" for v in meds)))
            # count IN under each region
            for region, row in (("med", row_m), ("all", row_a)):
                n_in = sum(1 for k, rp in enumerate(RPS)
                           if row[rp]["ci_lower"] <= PAPER[panel][k] <= row[rp]["ci_upper"])
                print("    %-12s %-4s -> %d/5 paper anchors inside our CI" % ("", region, n_in))


if __name__ == "__main__":
    main()
