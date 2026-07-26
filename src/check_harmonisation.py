"""Test whether the Roy et al. (2016) coefficients actually reduce
cross-sensor bias on OUR data, using near-coincident ETM+/OLI pairs.

    python src/check_harmonisation.py
    python src/check_harmonisation.py --district bandarban --max-days 4

WHY THIS EXISTS
---------------
src/preprocess.py harmonises TM/ETM+ into the OLI reference before any
index is computed. If those coefficients are wrong, nothing raises: every
composite before 2013 is quietly shifted, and the shift appears in the
change maps as forest loss that did not happen. The coefficient table in
preprocess.py was reproduced from memory and is flagged there as needing
verification against the published paper. This script is the empirical
half of that verification.

METHOD
------
Landsat 7 and Landsat 8 fly the same WRS-2 orbit eight days apart. A
scene pair from the same path/row within a few days sees very nearly the
same ground, so any systematic band difference between them is sensor
difference, not landscape change. For each such pair this script
computes the mean per-band reflectance over the district, before and
after harmonisation, and reports whether harmonisation moves ETM+ closer
to OLI or further away.

Comparing whole-season medians instead — the obvious quick version —
does NOT work: the two sensors contribute different dates, so phenology
and atmospheric state are confounded with the sensor effect. That test
reported harmonisation making things worse, which is uninterpretable
rather than informative.

READING THE RESULT
------------------
A negative "change" means harmonisation reduced the gap and the
coefficients are doing their job on this data. A positive change on a
band means they are not — check the direction of the regression (Roy
gives coefficients both ways) and the exact table values before using
any composite for results.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import ee
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import preprocess as pp  # noqa: E402

L7, L8 = "LE07", "LC08"

# Landsat 7 imaging degraded badly toward decommissioning; restrict to the
# clean overlap window where both sensors were fully operational.
OVERLAP_START, OVERLAP_END = 2014, 2021

MAX_DAYS_DEFAULT = 8   # one WRS-2 repeat cycle
MAX_CLOUD_PAIR = 20    # stricter than the audit: residual cloud is the
                       # main confounder in a paired comparison
COMPARE_SCALE = 300


def scene_list(sensor: str, aoi: ee.Geometry, start: str, end: str) -> list[dict]:
    """Scene id, timestamp, and path/row for one sensor."""
    col = (
        ee.ImageCollection(pp.SENSORS[sensor]["id"])
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", MAX_CLOUD_PAIR))
    )
    info = col.toList(col.size()).getInfo()
    out = []
    for item in info:
        props = item["properties"]
        out.append(
            {
                "id": item["id"],
                "time": datetime.fromtimestamp(
                    props["system:time_start"] / 1000, tz=timezone.utc
                ),
                "path": props.get("WRS_PATH"),
                "row": props.get("WRS_ROW"),
            }
        )
    return out


def find_pairs(
    oli_scenes: list[dict], etm_scenes: list[dict], max_days: int
) -> list[tuple[dict, dict]]:
    """Pair OLI and ETM+ scenes from the same path/row within max_days.

    Returns (oli, etm) tuples — same order as the arguments. Both lists
    are dicts of the same shape, so swapping them silently produces pairs
    with the sensors reversed, which then fails deep inside a band select
    with a confusing "SR_B6 did not match any bands". Hence the explicit
    names and the matching return order.
    """
    pairs = []
    for oli in oli_scenes:
        for etm in etm_scenes:
            if oli["path"] != etm["path"] or oli["row"] != etm["row"]:
                continue
            if abs((oli["time"] - etm["time"]).days) <= max_days:
                pairs.append((oli, etm))
    return pairs


def band_means(scene_id: str, sensor: str, aoi: ee.Geometry, harmonise: bool) -> dict:
    img = ee.Image(scene_id)
    img = pp.rename_bands(pp.scale_l2(pp.mask_l2(img)), sensor)
    if harmonise:
        img = pp.harmonise(img, pp.SENSORS[sensor]["family"])
    return (
        img.select(pp.COMMON_BANDS)
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=COMPARE_SCALE,
            maxPixels=int(1e9),
            bestEffort=True,
        )
        .getInfo()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", default="gazipur", choices=pp.DISTRICTS)
    parser.add_argument("--max-days", type=int, default=MAX_DAYS_DEFAULT)
    parser.add_argument("--max-pairs", type=int, default=12)
    args = parser.parse_args()

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{args.district}_shp").geometry()
    start, end = f"{OVERLAP_START}-01-01", f"{OVERLAP_END}-12-31"

    print(f"district {args.district}, {OVERLAP_START}-{OVERLAP_END}, "
          f"pairs within {args.max_days} days, cloud < {MAX_CLOUD_PAIR}%")

    l7 = scene_list(L7, aoi, start, end)
    l8 = scene_list(L8, aoi, start, end)
    pairs = find_pairs(l8, l7, args.max_days)[: args.max_pairs]
    print(f"L7 scenes {len(l7)}, L8 scenes {len(l8)}, usable pairs {len(pairs)}\n")

    if not pairs:
        print("No near-coincident pairs found. Widen --max-days or relax cloud.")
        return 1

    raw_diff = {b: [] for b in pp.COMMON_BANDS}
    harm_diff = {b: [] for b in pp.COMMON_BANDS}

    for i, (oli, etm) in enumerate(pairs, 1):
        gap = abs((oli["time"] - etm["time"]).days)
        try:
            o = band_means(oli["id"], L8, aoi, harmonise=False)
            r = band_means(etm["id"], L7, aoi, harmonise=False)
            h = band_means(etm["id"], L7, aoi, harmonise=True)
        except Exception as exc:
            print(f"  pair {i}: skipped ({exc})")
            continue
        if any(o.get(b) is None or r.get(b) is None for b in pp.COMMON_BANDS):
            print(f"  pair {i}: skipped (masked out over AOI)")
            continue
        for b in pp.COMMON_BANDS:
            raw_diff[b].append(r[b] - o[b])
            harm_diff[b].append(h[b] - o[b])
        print(f"  pair {i}: p{oli['path']}r{oli['row']}, {gap}d apart")

    n = len(raw_diff[pp.COMMON_BANDS[0]])
    if n == 0:
        print("\nNo pair produced usable statistics.")
        return 1

    print(f"\nmean absolute ETM+ minus OLI difference over {n} pairs\n")
    print(f"{'band':<7}{'raw':>10}{'harmonised':>13}{'change':>10}  verdict")
    total_raw = total_harm = 0.0
    for b in pp.COMMON_BANDS:
        mr = float(np.mean(np.abs(raw_diff[b])))
        mh = float(np.mean(np.abs(harm_diff[b])))
        total_raw += mr
        total_harm += mh
        change = (mh - mr) / mr * 100 if mr else 0.0
        # Bands left at identity produce exactly zero change; calling that
        # "WORSE" is misleading in a table headed for the thesis.
        if abs(change) < 1e-9:
            verdict = "unchanged (identity)"
        elif mh < mr:
            verdict = "better"
        else:
            verdict = "WORSE"
        print(f"{b:<7}{mr:>10.4f}{mh:>13.4f}{change:>9.1f}%  {verdict}")

    overall = (total_harm - total_raw) / total_raw * 100 if total_raw else 0.0
    print(f"{'TOTAL':<7}{total_raw:>10.4f}{total_harm:>13.4f}{overall:>9.1f}%")
    print()

    if overall < -5:
        print("Harmonisation reduces cross-sensor bias on this data. The")
        print("coefficients in preprocess.py behave as intended.")
        return 0
    if overall > 5:
        print("Harmonisation INCREASES cross-sensor bias. Do not build")
        print("composites until this is resolved: check the regression")
        print("direction (Roy gives both) and the exact Table 2 values.")
        return 1
    print("No material difference either way. Worth reporting as such —")
    print("a null result on harmonisation is still a Chapter 4 finding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
