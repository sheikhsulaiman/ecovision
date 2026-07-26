"""Phase 2 scene-availability audit, run headlessly against Earth Engine.

Python equivalent of gee/02_scene_audit.js. Same logic, same decision
inputs, but it writes CSVs straight to data/raw/audit/ instead of going
through a Drive export, and it can be run and re-run from the terminal.

    python src/scene_audit.py                 # all districts
    python src/scene_audit.py --district sylhet

Requires `earthengine authenticate` to have been run once.

WHICH FILE IS AUTHORITATIVE: this one. The numbers used in the thesis come
from here. gee/02_scene_audit.js is kept as the Code Editor reference — it
is useful for interactive inspection and for the Phase 10 dashboard, but
if the two ever disagree, this file is what produced the results. Any
change to the decision inputs must be made in both.

Resumable: years already present in the output CSV are skipped, so an
interrupted run can be restarted without losing work.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import ee

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "raw" / "audit"

PROJECT = "ecovision-503602"
ASSET_ROOT = f"projects/{PROJECT}/assets/"

DISTRICTS = ["gazipur", "sylhet", "bandarban"]

START_YEAR = 1985  # query range only — the real start year is the OUTPUT
END_YEAR = 2024

# Dry season: 1 November (previous year) to 31 March. The monsoon
# (June-October) makes optical imagery largely unusable, and mixed-season
# composites introduce phenological change a model reads as forest loss.
SEASON_START_MONTH = 11
SEASON_END_MONTH = 4  # exclusive: April 1 includes all of March 31

MAX_CLOUD = 40

# 300 m, 10x native. This is an audit, not an analysis — at 30 m the
# reduceRegion over 40 years x 3 districts times out. Do not reuse this
# scale anywhere in Phase 3 onward.
AUDIT_SCALE = 300

SENSORS = {
    "l4": "LANDSAT/LT04/C02/T1_L2",
    "l5": "LANDSAT/LT05/C02/T1_L2",
    "l7": "LANDSAT/LE07/C02/T1_L2",
    "l8": "LANDSAT/LC08/C02/T1_L2",
    # Operational since 2022. Absent from the methodology plan's snippet,
    # which would have undercounted 2022-2024 — and 2024 is the T3 epoch.
    "l9": "LANDSAT/LC09/C02/T1_L2",
}

SLC_FAILURE = "2003-05-31"  # Landsat 7 scan line corrector failure
# First dry-season window (Nov year-1 to Mar year) that can contain
# post-failure ETM+ scenes. See the guard in audit_year().
SLC_FIRST_AFFECTED_YEAR = 2004

FIELDS = [
    "year", "season_start", "season_end",
    "l4", "l5", "l7", "l7_slc_off", "l8", "l9",
    "total_scenes", "path_rows", "mean_cloud",
    "obs_per_pixel", "pct_covered",
]


def clear_observation(img: ee.Image) -> ee.Image:
    """1 where the pixel is a clear observation, masked elsewhere.

    Scene-level CLOUD_COVER is a whole-frame average and says nothing
    about whether the cloud sat over the district. QA_PIXEL does.
    """
    qa = img.select("QA_PIXEL")
    clear = (
        qa.bitwiseAnd(1 << 1).eq(0)        # dilated cloud
        .And(qa.bitwiseAnd(1 << 2).eq(0))  # cirrus
        .And(qa.bitwiseAnd(1 << 3).eq(0))  # cloud
        .And(qa.bitwiseAnd(1 << 4).eq(0))  # cloud shadow
    )
    return clear.rename("obs").updateMask(clear)


def audit_year(aoi: ee.Geometry, year: int) -> dict:
    start = ee.Date.fromYMD(year - 1, SEASON_START_MONTH, 1)
    end = ee.Date.fromYMD(year, SEASON_END_MONTH, 1)

    cols = {
        key: (
            ee.ImageCollection(cid)
            .filterBounds(aoi)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUD_COVER", MAX_CLOUD))
        )
        for key, cid in SENSORS.items()
    }

    # How much of this year leans on gap-affected ETM+ scenes (~22% missing).
    #
    # Guard the date range client-side. The season window ends on 1 April of
    # `year`, so for year <= 2003 that end is BEFORE the SLC failure date and
    # filterDate() gets an inverted range, which GEE rejects with
    # "Empty date ranges not supported for the current operation" rather than
    # returning zero. The first window that can contain post-SLC scenes is
    # Nov 2003 - Mar 2004, i.e. year 2004.
    if year >= SLC_FIRST_AFFECTED_YEAR:
        l7_slc_off = cols["l7"].filterDate(ee.Date(SLC_FAILURE), end).size()
    else:
        l7_slc_off = ee.Number(0)

    # Merge on QA_PIXEL only — the sensors have different band names.
    merged = cols["l4"].select("QA_PIXEL")
    for key in ("l5", "l7", "l8", "l9"):
        merged = merged.merge(cols[key].select("QA_PIXEL"))
    merged = ee.ImageCollection(merged)

    total = merged.size()

    depth = ee.Image(
        ee.Algorithms.If(
            total.eq(0),
            ee.Image.constant(0).rename("obs"),
            merged.map(clear_observation).sum().unmask(0).rename("obs"),
        )
    )
    stats = depth.addBands(depth.gte(1).rename("covered")).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=AUDIT_SCALE,
        maxPixels=int(1e9),
        bestEffort=True,
    )

    # Three scenes from one WRS-2 path/row cover less of a district than
    # three from three path/rows. This tells them apart.
    path_rows = (
        merged.aggregate_array("WRS_PATH")
        .zip(merged.aggregate_array("WRS_ROW"))
        .distinct()
        .size()
    )

    payload = ee.Dictionary({
        "year": year,
        "season_start": start.format("YYYY-MM-dd"),
        "season_end": end.advance(-1, "day").format("YYYY-MM-dd"),
        "l4": cols["l4"].size(),
        "l5": cols["l5"].size(),
        "l7": cols["l7"].size(),
        "l7_slc_off": l7_slc_off,
        "l8": cols["l8"].size(),
        "l9": cols["l9"].size(),
        "total_scenes": total,
        "path_rows": path_rows,
        # aggregate_mean over an empty collection raises rather than
        # returning null — and a year with no scenes at all is exactly the
        # result Phase 2 exists to find, so it must produce a row, not a crash.
        "mean_cloud": ee.Algorithms.If(
            total.gt(0), merged.aggregate_mean("CLOUD_COVER"), None
        ),
        "obs_per_pixel": stats.get("obs"),
        "pct_covered": ee.Number(stats.get("covered")).multiply(100),
    })
    return payload.getInfo()


def completed_years(path: Path) -> set[int]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as fh:
        return {int(row["year"]) for row in csv.DictReader(fh) if row.get("year")}


def run_district(name: str, retries: int = 3) -> None:
    aoi = ee.FeatureCollection(f"{ASSET_ROOT}{name}_shp").geometry()
    out = OUT_DIR / f"{name}_scene_audit.csv"
    done = completed_years(out)

    todo = [y for y in range(START_YEAR, END_YEAR + 1) if y not in done]
    if not todo:
        print(f"{name}: already complete ({len(done)} years)")
        return
    if done:
        print(f"{name}: resuming, {len(done)} years already done")

    new_file = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()

        for year in todo:
            for attempt in range(1, retries + 1):
                try:
                    row = audit_year(aoi, year)
                    break
                except Exception as exc:  # transient EE errors are common
                    if attempt == retries:
                        print(f"  {name} {year}: FAILED after {retries} tries — {exc}")
                        row = None
                        break
                    time.sleep(2 * attempt)
            if row is None:
                continue
            writer.writerow({k: row.get(k) for k in FIELDS})
            fh.flush()
            print(
                f"  {name} {year}: {row['total_scenes']:>3} scenes, "
                f"{row['path_rows']} path/row, "
                f"{row['obs_per_pixel'] or 0:.2f} obs/px, "
                f"{row['pct_covered'] or 0:.1f}% covered"
            )
    print(f"{name}: written to {out.relative_to(REPO)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=DISTRICTS, help="one district only")
    args = parser.parse_args()

    try:
        ee.Initialize(project=PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}\nRun `earthengine authenticate` first.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in [args.district] if args.district else DISTRICTS:
        print(f"\n=== {name} ({START_YEAR}-{END_YEAR}) ===")
        run_district(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
