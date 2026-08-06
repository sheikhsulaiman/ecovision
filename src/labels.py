"""Build TRAINING labels. These are not, and must never become, reference data.

CLAUDE.md rule 3. Two datasets exist in this project and conflating them
invalidates every accuracy figure:

    TRAINING LABELS (this file)      REFERENCE SAMPLE (reference_sample.py)
    purpose: teach the model         purpose: measure the model
    source:  Hansen GFC, BFD         source:  human interpretation
    volume:  millions of pixels      volume:  600 points per district
    quality: noisy is fine           quality: must be high
    overlap: none, ever

If a model is scored against labels derived here, it is being scored
against its own teacher and the resulting accuracy means nothing. The
guard in _assert_no_reference_access() makes that mistake loud rather
than silent.

    python src/labels.py --balance            # class balance at each epoch
    python src/labels.py --balance --year 2010

WHAT THIS CANNOT DO YET
-----------------------
* Plantation (class 2) needs BFD/BFIS tea and rubber boundaries, still
  outstanding. Without them the class cannot be built, and no spectral
  proxy is acceptable — separating plantation from natural forest
  spectrally is the thesis question, so a proxy would assume the answer.
* Nothing before 2000. Hansen's baseline IS 2000; it cannot say what was
  forest in 1990. The study starts in 1988, so labels exist for roughly
  two-thirds of the period. That gap is the subject of an open decision
  (methodology_plan.md 4.1, options A/B/C) that has not been made.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ee

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

HANSEN = "UMD/hansen/global_forest_change_2025_v1_13"
JRC_WATER = "JRC/GSW1_4/GlobalSurfaceWater"

# docs/forest_definition.md 1 and 4. Same value as reference_sample.py by
# necessity, not coincidence: labels and strata must express the same
# forest definition or the map and its assessment are measuring different
# things. Still awaiting sign-off.
CANOPY_THRESHOLD = 30
WATER_OCCURRENCE = 50

# Hansen's baseline. Before this, Hansen has nothing to say about forest
# extent, and no amount of band arithmetic changes that.
HANSEN_BASELINE_YEAR = 2000

CLASSES = {
    0: "non_forest",
    1: "natural_forest",
    2: "plantation",     # blocked on BFD
    3: "water",
}

# Hand-digitised tea estates, the ONLY source of class 2. No open dataset
# maps Bangladesh's tea (docs/forest_definition.md §6.5), so unlike classes
# 0/1 this cannot be regenerated — see src/ingest_tea.py.
TEA_ESTATES = REPO / "data" / "vector" / "sylhet_tea_estates.geojson"

# Sylhet only. Siddik et al. (2025) report no tea estates in Gazipur or
# Bandarban, so applying this layer elsewhere would be meaningless.
PLANTATION_DISTRICTS = {"sylhet"}

PLANTATION_PARTIAL = (
    "Class 2 covers the hand-digitised Sylhet tea estates only, and those "
    "are incomplete: about 1,300 ha are drawn against a district total of "
    ">10,000 ha reported by Siddik et al. (2025). Tea outside the drawn "
    "polygons still falls into class 1, so the Sylhet confusion is reduced "
    "rather than eliminated. Gazipur and Bandarban have no plantation "
    "class at all — no tea there, and no source for their teak or rubber."
)


def _assert_no_reference_access(path: Path) -> None:
    """Refuse to touch the reference sample from the training-label module.

    Rule 3 is a rule about intent, and intent decays under deadline. This
    turns it into something the interpreter enforces.
    """
    reference_dir = (REPO / "data" / "reference").resolve()
    if reference_dir in path.resolve().parents or path.resolve() == reference_dir:
        raise RuntimeError(
            f"labels.py attempted to access {path}, which is inside "
            "data/reference/. Training labels and the reference sample must "
            "never mix (CLAUDE.md rule 3). If you need reference data, you "
            "are in the wrong module."
        )


def plantation_mask(district: str) -> ee.Image | None:
    """Hand-digitised tea estates as a mask, or None where none exist."""
    if district not in PLANTATION_DISTRICTS or not TEA_ESTATES.exists():
        return None
    import geopandas as gpd

    # Features are constructed one at a time from shapely geometries.
    # Handing the raw GeoJSON dict to ee.FeatureCollection fails with
    # "Invalid GeoJSON geometry" — Earth Engine does not accept a
    # FeatureCollection mapping directly.
    frame = gpd.read_file(TEA_ESTATES).to_crs("EPSG:4326")
    feats = [
        ee.Feature(ee.Geometry(geom.__geo_interface__), {"tea": 1})
        for geom in frame.geometry
        if geom is not None and not geom.is_empty
    ]
    if not feats:
        return None
    return (
        ee.FeatureCollection(feats)
        .reduceToImage(["tea"], ee.Reducer.first())
        .gt(0)
        .unmask(0)
    )


def build_labels(aoi: ee.Geometry, year: int, district: str | None = None) -> ee.Image:
    """Four-class training label image for `year`.

    Forest at time t is the year-2000 canopy layer minus everything lost
    up to t, plus gain. Hansen's lossyear is 1-indexed from 2000.
    """
    if year < HANSEN_BASELINE_YEAR:
        raise ValueError(
            f"Cannot build labels for {year}: Hansen's baseline is "
            f"{HANSEN_BASELINE_YEAR} and it has no information before it.\n"
            "The study period starts in 1988, so the pre-2000 years need a "
            "different regime — see docs/methodology_plan.md 4.1, options "
            "A/B/C. That decision is still open; do not paper over it by "
            "extrapolating the 2000 baseline backwards."
        )

    hansen = ee.Image(HANSEN).clip(aoi)
    # unmask(0) is required: Hansen's lossyear is masked wherever no loss
    # occurred, so any expression using its complement silently evaluates
    # to masked rather than true. See the same note in reference_sample.py.
    tree2000 = hansen.select("treecover2000").unmask(0)
    lossyear = hansen.select("lossyear").unmask(0)
    gain = hansen.select("gain").unmask(0)

    forest2000 = tree2000.gte(CANOPY_THRESHOLD)
    lost_by_year = lossyear.gte(1).And(lossyear.lte(year - HANSEN_BASELINE_YEAR))

    forest_now = forest2000.And(lost_by_year.Not()).Or(
        gain.eq(1).And(lost_by_year.Not())
    )

    water = ee.Image(JRC_WATER).select("occurrence").unmask(0).gte(WATER_OCCURRENCE)

    labels = forest_now.multiply(1).rename("label").toInt()
    labels = labels.where(water, 3)

    # Plantation overrides forest, not water: a drawn estate boundary can
    # clip a pond, and a pond inside an estate is still water.
    tea = plantation_mask(district) if district else None
    if tea is not None:
        labels = labels.where(tea.And(water.Not()), 2)

    return labels.clip(aoi).set({"year": year, "canopy_threshold": CANOPY_THRESHOLD})


def class_balance(aoi: ee.Geometry, year: int, district: str | None = None) -> dict:
    """Area per class. Gate 4 requires this tabulated before training."""
    labels = build_labels(aoi, year, district)
    grouped = (
        ee.Image.pixelArea()
        .addBands(labels)
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="label"),
            geometry=aoi,
            scale=pp.NATIVE_SCALE,
            maxPixels=int(1e10),
            bestEffort=True,
        )
        .getInfo()
    )
    by_code = {int(g["label"]): float(g["sum"]) for g in grouped.get("groups", [])}
    total = sum(by_code.values()) or 1.0
    return {
        CLASSES[code]: {"area_ha": area / 1e4, "share": area / total}
        for code, area in sorted(by_code.items())
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--balance", action="store_true")
    parser.add_argument("--year", type=int, help="default: every epoch anchor")
    parser.add_argument("--district", choices=pp.DISTRICTS)
    args = parser.parse_args()

    if not args.balance:
        parser.print_help()
        return 0

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    _assert_no_reference_access(REPO / "data" / "raw")

    years = [args.year] if args.year else sorted(
        y for y in pp.EPOCHS.values() if y >= HANSEN_BASELINE_YEAR
    )
    skipped = sorted(y for y in pp.EPOCHS.values() if y < HANSEN_BASELINE_YEAR)
    districts = [args.district] if args.district else pp.DISTRICTS

    print(f"canopy threshold {CANOPY_THRESHOLD}%   Hansen {HANSEN.split('/')[-1]}")
    if skipped:
        print(f"\nSKIPPED epochs before Hansen's baseline: {skipped}")
        print("These need the pre-2000 regime decision (methodology_plan.md 4.1).")

    for district in districts:
        aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
        print(f"\n=== {district} ===")
        print(f"{'year':<8}{'class':<18}{'area (ha)':>14}{'share':>9}")
        for year in years:
            balance = class_balance(aoi, year, district)
            for name, stats in balance.items():
                print(f"{year:<8}{name:<18}{stats['area_ha']:>14,.1f}"
                      f"{stats['share']:>9.2%}")

    print("\nNOTE: " + PLANTATION_PARTIAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
