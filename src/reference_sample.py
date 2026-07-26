"""Draw the stratified reference sample for accuracy assessment.

THIS IS NOT TRAINING DATA. CLAUDE.md rule 3.

The reference sample is the only thing accuracy is measured against. Its
class labels come from independent visual interpretation by both authors
— never from Hansen, never from a model, never from this file. What this
script produces is a list of LOCATIONS and empty interpretation columns.
Nothing in this module writes a reference class.

    python src/reference_sample.py --dry-run      # inspect strata, draw nothing
    python src/reference_sample.py --draw         # draw and write CSVs

--dry-run is the default and is where you should stay until the canopy
threshold is signed off (docs/forest_definition.md §6.1). Drawing a
sample at 30% and then having the threshold changed to 10% wastes the
scarcest resource in the project: 3,600 human interpretations that cannot
be compressed at the end.

STRATIFICATION IS NOT CIRCULARITY
---------------------------------
The strata below are derived from Hansen GFC, which is also a training
label source. That looks like it violates rule 3 and does not, for a
specific reason: stratification determines only which locations get
LOOKED AT, not what they are. The reference class comes from a human
looking at imagery. Sampling probabilities are known and unequal, and
the Olofsson estimator corrects for exactly that.

What this DOES mean for Phase 8: the strata used for sampling are Hansen
strata, not our map's classes. The error matrix rows are therefore
strata, and W_h must be the mapped area proportions of THESE strata —
not of our classified map. Stehman (2014) covers the case where the
stratification differs from the map being assessed. The stratum areas
are written to disk at draw time for precisely this reason; without them
the sample cannot be used for area estimation at all.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

OUT_DIR = REPO / "data" / "reference"

HANSEN = "UMD/hansen/global_forest_change_2025_v1_13"
JRC_WATER = "JRC/GSW1_4/GlobalSurfaceWater"

# Canopy threshold from docs/forest_definition.md §1. NOT yet signed off.
# The 10% sensitivity run (§6.1) reuses this module with the value changed.
CANOPY_THRESHOLD = 30

# Water: JRC occurrence percentage above which a pixel is treated as water
# for stratification. Deliberately high — seasonal haor flooding in Sylhet
# should not pull cropland into the water stratum.
WATER_OCCURRENCE = 50

# Fixed so the draw is reproducible. Changing it draws a DIFFERENT sample;
# if interpretation has started, do not change it.
SEED = 20260726

# Sample allocation, docs/methodology_plan.md §4.2. Rare change classes
# are deliberately over-sampled: a proportional sample would give ~15 loss
# points and useless confidence intervals.
# The gain stratum was dropped on 2026-07-26 and its 50 points moved to
# forest_loss. Hansen's `gain` band covers 2000-2012 only, which left 624
# gain pixels in Gazipur and 451 in Sylhet — 50 points from 451 pixels is
# 11% of the stratum, breaking the large-population assumption behind the
# variance formulae, and the stratum could not honestly be described as
# covering 1988-2024 anyway. Regrowth is instead reported from the
# LandTrendr annual series, which spans the whole period.
#
# The points went to forest_loss rather than being spread evenly: loss is
# the change class, F1 on it is the headline metric (rule 5), and the
# width of its confidence interval is the number an examiner will press on.
ALLOCATION = {
    "gazipur":   {"stable_non_forest": 150, "stable_forest": 150,
                  "forest_loss": 200, "plantation": 100},
    "sylhet":    {"stable_non_forest": 150, "stable_forest": 150,
                  "forest_loss": 200, "plantation": 100},
    # Bandarban trades stable-class points and half the plantation stratum
    # for a cyclical-disturbance stratum. Without it the permanent-versus-
    # cyclical jhum split is asserted rather than measured, and that split
    # is the reason the district was added.
    "bandarban": {"stable_non_forest": 125, "stable_forest": 125,
                  "forest_loss": 150, "cyclical": 150, "plantation": 50},
}

STRATUM_CODES = {
    "stable_non_forest": 0,
    "stable_forest": 1,
    "forest_loss": 2,
    "gain": 3,
    "plantation": 4,
    "cyclical": 5,
}

# Strata whose inputs do not exist yet. See build_strata().
BLOCKED_STRATA = {
    "plantation": (
        "needs tea/rubber estate boundaries from BFD/BFIS, still outstanding "
        "(Phase 0.1). No defensible spectral proxy — that is the whole "
        "Sylhet problem this thesis exists to solve, so a proxy would beg "
        "the question."
    ),
}

# Above this share of a stratum's pixels, the sample stops behaving like a
# draw from a large population and the variance formulae get conservative.
MAX_SAMPLING_FRACTION = 0.05

# HANSEN GAIN IS NOT THE FULL PERIOD. The `gain` band covers 2000-2012
# only; it was never extended annually the way `lossyear` was. The gain
# stratum is therefore blind to any regrowth after 2012, which is most of
# the study period. Measured consequence: 624 gain pixels in Gazipur and
# 451 in Sylhet — 40 ha across the whole of Sylhet, which is not credible
# as a true regrowth total, only as the 2000-2012 slice of one.
#
# This is a stratification limitation, not a measurement error: points in
# the stratum are still interpreted honestly, and regrowth outside it can
# still be found in other strata. But the gain stratum cannot be described
# as covering 1988-2024, and Chapter 6 must say so.
GAIN_BAND_PERIOD = "2000-2012"

AUTHORS = ["author_a", "author_b"]

INTERPRETATION_COLUMNS = [
    "point_id", "district", "stratum", "lon", "lat",
    "class_t0", "class_t3", "confidence", "notes",
]


def build_strata(aoi: ee.Geometry, district: str) -> tuple[ee.Image, list[str]]:
    """Stratification image. Returns (image, strata actually available).

    Hansen bands used:
      treecover2000  canopy percentage in 2000
      lossyear       1-24, year of loss (1 = 2001)
      gain           1 where gain 2000-2012
    """
    hansen = ee.Image(HANSEN).clip(aoi)

    # unmask(0) is NOT cosmetic. Hansen's `lossyear` band is masked
    # everywhere there was no loss — in Sylhet only 14,666 of 4,203,102
    # pixels are unmasked. Without this, `loss.Not()` is masked rather than
    # true across the whole district, every stratum defined through it
    # collapses to zero pixels, and the sample comes out with NO stable
    # forest stratum at all. It fails silently: the reduceRegion returns 0
    # and nothing raises.
    tree2000 = hansen.select("treecover2000").unmask(0)
    lossyear = hansen.select("lossyear").unmask(0)
    gain = hansen.select("gain").unmask(0)

    forest2000 = tree2000.gte(CANOPY_THRESHOLD)

    # Loss inside the study period. lossyear is offset from 2000.
    lo = max(pp.START_YEAR, 2001) - 2000
    hi = pp.END_YEAR - 2000
    loss = lossyear.gte(lo).And(lossyear.lte(hi))

    water = ee.Image(JRC_WATER).select("occurrence").gte(WATER_OCCURRENCE).unmask(0)

    # Base the strata image on a Hansen band rather than ee.Image.constant.
    # A constant image carries a default projection of roughly 111 km per
    # pixel; .where() against it produces a result at that scale, so the
    # 30 m reduceRegion below would be sampling a near-empty grid. Deriving
    # from tree2000 inherits Hansen's 30 m projection and footprint.
    strata = tree2000.multiply(0).add(STRATUM_CODES["stable_non_forest"]).rename("stratum")
    available = ["stable_non_forest"]

    strata = strata.where(
        forest2000.And(loss.Not()), STRATUM_CODES["stable_forest"]
    )
    available.append("stable_forest")

    strata = strata.where(forest2000.And(loss), STRATUM_CODES["forest_loss"])
    available.append("forest_loss")

    # No gain stratum: see the note on ALLOCATION. The Hansen gain band is
    # still read above because the cyclical stratum below needs it.
    if district == "bandarban":
        # Cyclical-disturbance stratum: pixels showing BOTH loss and gain.
        # A stratification proxy, not a label — a swidden plot cleared and
        # regrown within the record is what this is reaching for, and the
        # interpreter decides whether it actually is one. Getting the proxy
        # partly wrong costs efficiency, not validity: inclusion
        # probabilities stay known and the estimator still corrects.
        strata = strata.where(loss.And(gain), STRATUM_CODES["cyclical"])
        available.append("cyclical")
    # Water is excluded from sampling rather than given a stratum: open
    # water is not in dispute and spending interpretation hours on it
    # buys nothing.
    strata = strata.updateMask(water.Not()).rename("stratum").toInt()
    return strata, available


def stratum_areas(strata: ee.Image, aoi: ee.Geometry, available: list[str]) -> dict:
    """Area and pixel count per stratum — the areas become W_h in Phase 8.

    Area is summed from ee.Image.pixelArea(), NOT computed as
    pixel_count x 0.09 ha. Hansen's native grid is 1/4000 degree, about
    27.8 m at this latitude, not 30 m — assuming 30 m overstates area by
    roughly 16% and that error would flow straight into every adjusted
    area estimate through W_h. pixelArea() is projection-correct by
    construction.

    Without these numbers the sample cannot produce an area estimate at
    all. Recorded at draw time, because a later Hansen version changes them.
    """
    grouped = (
        ee.Image.pixelArea()
        .addBands(strata)
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="stratum"),
            geometry=aoi,
            scale=pp.NATIVE_SCALE,
            maxPixels=int(1e10),
            bestEffort=True,
        )
        .getInfo()
    )
    by_code = {int(g["stratum"]): float(g["sum"]) for g in grouped.get("groups", [])}

    counts = strata.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=aoi,
        scale=pp.NATIVE_SCALE,
        maxPixels=int(1e10),
        bestEffort=True,
    ).getInfo()
    hist = counts.get("stratum", {}) or {}

    total_m2 = sum(by_code.values()) or 1.0
    out = {}
    for name in available:
        code = STRATUM_CODES[name]
        area_m2 = by_code.get(code, 0.0)
        out[name] = {
            "code": code,
            "pixels": float(hist.get(str(code), 0)),
            "area_ha": area_m2 / 1e4,
            "weight": area_m2 / total_m2,
        }
    return out


def draw(district: str, samples: int | None = None) -> pd.DataFrame:
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    strata, available = build_strata(aoi, district)

    wanted = ALLOCATION[district]
    usable = {k: v for k, v in wanted.items() if k in available}

    class_values = [STRATUM_CODES[k] for k in usable]
    class_points = [samples or usable[k] for k in usable]

    fc = strata.stratifiedSample(
        numPoints=0,
        classBand="stratum",
        region=aoi,
        scale=pp.NATIVE_SCALE,
        seed=SEED,
        classValues=class_values,
        classPoints=class_points,
        geometries=True,
        tileScale=4,
    )
    info = fc.getInfo()

    inverse = {v: k for k, v in STRATUM_CODES.items()}
    rows = []
    for i, feat in enumerate(info["features"], 1):
        lon, lat = feat["geometry"]["coordinates"]
        code = feat["properties"]["stratum"]
        rows.append({
            "point_id": f"{district[:3].upper()}-{i:04d}",
            "district": district,
            "stratum": inverse[code],
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "class_t0": "", "class_t3": "", "confidence": "", "notes": "",
        })
    return pd.DataFrame(rows, columns=INTERPRETATION_COLUMNS)


def report(district: str) -> dict:
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    strata, available = build_strata(aoi, district)
    areas = stratum_areas(strata, aoi, available)

    wanted = ALLOCATION[district]
    blocked = [k for k in wanted if k not in available]

    print(f"\n=== {district} ===")
    print(f"{'stratum':<20}{'pixels':>12}{'area (ha)':>14}{'weight':>9}{'wanted n':>10}")
    for name, stats in areas.items():
        print(f"{name:<20}{stats['pixels']:>12,.0f}{stats['area_ha']:>14,.1f}"
              f"{stats['weight']:>9.4f}{wanted.get(name, 0):>10}")

    for name in blocked:
        why = BLOCKED_STRATA.get(name, "input not available")
        print(f"{name:<20}{'BLOCKED':>12}   {why}")

    # Flag strata where the sample would be a large fraction of the whole
    # population. The variance formulae in src/area_estimation.py assume
    # sampling from a large population; at a high sampling fraction they
    # overstate the standard error, and past ~20% the "random sample"
    # framing stops being meaningful at all.
    for name, stats in areas.items():
        n = wanted.get(name, 0)
        if not n or not stats["pixels"]:
            continue
        fraction = n / stats["pixels"]
        if fraction > MAX_SAMPLING_FRACTION:
            print(f"\n  WARNING: {name} — {n} points from only "
                  f"{stats['pixels']:,.0f} pixels ({fraction:.1%} of the stratum).")
            print("  Reduce n, merge the stratum, or accept that its interval "
                  "is conservative.")
    return {"areas": areas, "blocked": blocked, "available": available}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw", action="store_true",
                        help="actually draw and write the sample")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--district", choices=pp.DISTRICTS)
    args = parser.parse_args()

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    districts = [args.district] if args.district else pp.DISTRICTS

    print(f"canopy threshold {CANOPY_THRESHOLD}%   "
          f"study period {pp.START_YEAR}-{pp.END_YEAR}   seed {SEED}")

    summary = {d: report(d) for d in districts}

    blocked_any = {d: s["blocked"] for d, s in summary.items() if s["blocked"]}

    if not args.draw:
        print("\n--- dry run, nothing written ---")
        if blocked_any:
            print("\nBlocked strata:")
            for d, names in blocked_any.items():
                print(f"  {d}: {', '.join(names)}")
        print("\nBefore drawing for real, confirm:")
        print("  1. docs/forest_definition.md §7 is signed — the canopy")
        print("     threshold determines every stratum boundary above.")
        print("  2. The blocked strata are resolved, or you accept drawing")
        print("     without them and topping up later as a separate sample.")
        print("\nThen re-run with --draw.")
        return 0

    if blocked_any:
        print("\nDrawing with strata missing. The sample will be incomplete;")
        print("any top-up later is a SEPARATE sample with its own inclusion")
        print("probabilities and must be recorded as such, not merged silently.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {"canopy_threshold": CANOPY_THRESHOLD, "seed": SEED,
                "hansen": HANSEN, "start_year": pp.START_YEAR,
                "end_year": pp.END_YEAR, "districts": {}}

    for district in districts:
        frame = draw(district)
        master = OUT_DIR / f"reference_sample_{district}.csv"
        frame.to_csv(master, index=False)
        # One blank copy per author. Rule 3 and docs/README.md rule 3: both
        # interpretations are logged separately and reconciled afterwards,
        # never merged in place.
        for author in AUTHORS:
            frame.to_csv(OUT_DIR / f"interpretation_{district}_{author}.csv", index=False)
        counts = frame["stratum"].value_counts().to_dict()
        manifest["districts"][district] = {
            "n": len(frame),
            "by_stratum": counts,
            "stratum_areas": summary[district]["areas"],
        }
        print(f"{district}: {len(frame)} points -> {master.relative_to(REPO)}")

    with (OUT_DIR / "sample_manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"\nManifest written. It records the stratum areas that become W_h")
    print("in the Olofsson estimator — without it the sample cannot produce")
    print("an area estimate. Commit it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
