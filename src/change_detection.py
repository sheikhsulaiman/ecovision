"""Phase 7 — bitemporal change detection, T0 to T3.

    python src/change_detection.py --district gazipur --to-asset
    python src/change_detection.py --district gazipur --from-asset

Answers RQ4: which change detection method is most accurate. Two methods
run here; the third and fourth live elsewhere.

    PCC            classify both dates, difference the maps  (this file)
    NDVI diff      threshold the index difference            (this file)
    Siamese        direct, E5                                (src/models/)
    LandTrendr     temporal segmentation                     (src/landtrendr.py)

PCC AND WHY IT IS THE ONE TO BEAT, NOT THE ONE TO TRUST
-------------------------------------------------------
Post-classification comparison accumulates error from both dates. Two
maps at 90% accuracy give a change map near 81%, because an error at
either date becomes a spurious change. That is the standard argument for
direct methods, and the Siamese result either supports it or does not —
either way it belongs in the discussion rather than in a footnote.

THE CLASSIFIER IS TRAINED ON 2024 AND APPLIED TO 1990
-----------------------------------------------------
Deliberate, and it is the Option B design (methodology_plan.md 4.1).
Hansen's baseline is 2000, so no training label exists for 1990 and none
can be manufactured. The model transfers in time: it learns what forest
looks like from labelled 2024 data and is asked the same question of a
1990 composite that has been harmonised to the same sensor basis
(docs/phase3_harmonisation.md).

That transfer is an assumption, not a free lunch, and RQ7 is what
measures it — running both regimes over the 2000-2024 overlap turns the
pre-2000 uncertainty into a number instead of a caveat.

TRAINING SAMPLES COME FROM TRAIN BLOCKS ONLY
--------------------------------------------
Rule 2. The classifier is fitted on pixels drawn inside the training
blocks and never sees val or test ground. Sampling across the district
and splitting afterwards would leak, silently, and would inflate every
change figure that follows.

WHAT THIS DOES NOT PRODUCE
--------------------------
Reportable areas. Everything below is a raw pixel count. Rule 4 requires
the Olofsson estimator against the reference sample, which is Phase 8.
The numbers here exist to compare methods against each other and to make
the maps.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ee
import geopandas as gpd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import labels as lb  # noqa: E402
import preprocess as pp  # noqa: E402

SPLIT_DIR = REPO / "data" / "splits"
TABLE_DIR = REPO / "outputs" / "tables"

TRAIN_SAMPLES_PER_CLASS = 3000
N_TREES = 300
SEED = 20260726

# Standard deviations below the stable-forest mean at which an NDVI
# decline counts as change. 2 sigma is the convention in the differencing
# literature and, unlike Otsu, it does not assume the histogram is
# bimodal — over a district that is 87% non-forest it is not.
NDVI_SIGMA = 2.0

# Change classes. Forest-to-non-forest is the only one that is
# deforestation; the others exist so the map does not silently fold
# plantation conversion or regrowth into it (rules 5 and 7).
CHANGE = {
    0: "no_change",
    1: "forest_loss",          # natural forest -> non-forest
    2: "forest_to_plantation",  # natural forest -> plantation
    3: "gain",                 # non-forest -> forest
}


def split_region(district: str, split: str) -> ee.Geometry:
    path = SPLIT_DIR / f"{district}_blocks.geojson"
    if not path.exists():
        sys.exit(f"Missing {path.relative_to(REPO)} — run src/splits.py --write")
    blocks = gpd.read_file(path)
    subset = blocks[blocks["split"] == split]
    if subset.empty:
        sys.exit(f"{district}: no blocks assigned to '{split}'")
    return ee.Geometry(subset.to_crs("EPSG:4326").geometry.union_all().__geo_interface__)


def train_classifier(district: str, aoi: ee.Geometry, year: int) -> ee.Classifier:
    """Random Forest fitted inside the training blocks of `year`."""
    stack = pp.build_composite(aoi, year)
    label = lb.build_labels(aoi, year, district).rename("label")
    bands = stack.bandNames()

    samples = stack.addBands(label).stratifiedSample(
        numPoints=TRAIN_SAMPLES_PER_CLASS,
        classBand="label",
        region=split_region(district, "train"),
        scale=pp.NATIVE_SCALE,
        seed=SEED,
        dropNulls=True,
        tileScale=4,
        geometries=False,
    )
    return ee.Classifier.smileRandomForest(N_TREES, seed=SEED).train(
        features=samples, classProperty="label", inputProperties=bands)


def pcc(district: str, aoi: ee.Geometry) -> ee.Image:
    """Classify T0 and T3 independently, then difference the maps."""
    classifier = train_classifier(district, aoi, pp.EPOCHS["T3"])

    def classify(year: int) -> ee.Image:
        return pp.build_composite(aoi, year).classify(classifier).rename("class")

    early = classify(pp.EPOCHS["T0"])
    late = classify(pp.EPOCHS["T3"])

    forest_early = early.eq(1)
    forest_late = late.eq(1)

    change = ee.Image.constant(0).toInt().rename("change")
    change = change.where(forest_early.And(late.eq(0)), 1)
    change = change.where(forest_early.And(late.eq(2)), 2)
    change = change.where(early.eq(0).And(forest_late), 3)

    return (change
            .addBands(early.rename("class_t0"))
            .addBands(late.rename("class_t3")))


def ndvi_difference(district: str, aoi: ee.Geometry) -> ee.Image:
    """Threshold the NDVI decline, calibrated on stable forest.

    The threshold is derived from pixels Hansen calls forest at both
    dates: their NDVI difference is what "no change" looks like for this
    sensor pair over this terrain, so a decline far outside that
    distribution is the signal. Calibrating on the reference sample
    instead would tune the method on the data meant to judge it.
    """
    early = pp.build_composite(aoi, pp.EPOCHS["T0"])
    late = pp.build_composite(aoi, pp.EPOCHS["T3"])
    delta = late.select("ndvi").subtract(early.select("ndvi")).rename("dndvi")

    stable_forest = (
        lb.build_labels(aoi, pp.EPOCHS["T3"], district).eq(1)
        .And(ee.Image(lb.HANSEN).select("lossyear").unmask(0).eq(0))
    )

    stats = delta.updateMask(stable_forest).reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
        geometry=split_region(district, "train"),
        scale=pp.NATIVE_SCALE * 3,   # the threshold does not need 30 m
        maxPixels=int(1e10),
        bestEffort=True,
    )
    mean = ee.Number(stats.get("dndvi_mean"))
    sigma = ee.Number(stats.get("dndvi_stdDev"))
    threshold = mean.subtract(sigma.multiply(NDVI_SIGMA))

    change = delta.lt(ee.Image.constant(threshold)).toInt().rename("change")
    return (change
            .addBands(delta)
            .set({"threshold": threshold, "stable_mean": mean, "stable_sd": sigma}))


def asset_id(district: str, method: str) -> str:
    return f"{pp.ASSET_ROOT}change_{method}_{district}"


def export_asset(image: ee.Image, aoi: ee.Geometry, district: str, method: str) -> None:
    """Materialise the change map. Same reason as src/landtrendr.py.

    A change map is two full feature stacks and a Random Forest behind
    every pixel, and Earth Engine reruns all of it for each tile of a
    reduceRegion rather than reusing the work. Written to an asset once,
    every downstream use — areas, the Phase 8 overlay, the figures — reads
    a materialised image.
    """
    task = ee.batch.Export.image.toAsset(
        image=image.toFloat(),
        description=f"change_{method}_{district}",
        assetId=asset_id(district, method),
        region=aoi,
        scale=pp.NATIVE_SCALE,
        crs=pp.NATIVE_CRS,
        maxPixels=int(1e10),
    )
    task.start()
    print(f"  export started -> {asset_id(district, method)}")


def areas(image: ee.Image, aoi: ee.Geometry, band: str, names: dict) -> dict:
    grouped = (
        ee.Image.pixelArea().addBands(image.select(band).toInt())
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="code"),
            geometry=aoi, scale=pp.NATIVE_SCALE, maxPixels=int(1e10),
            bestEffort=True)
        .getInfo()
    )
    by_code = {int(g["code"]): float(g["sum"]) for g in grouped.get("groups", [])}
    total = sum(by_code.values()) or 1.0
    return {names.get(c, str(c)): {"area_ha": a / 1e4, "share": a / total}
            for c, a in sorted(by_code.items())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=pp.DISTRICTS, required=True)
    parser.add_argument("--to-asset", action="store_true",
                        help="materialise both change maps (do this first)")
    parser.add_argument("--from-asset", action="store_true",
                        help="tabulate areas from the materialised assets")
    args = parser.parse_args()

    if not (args.to_asset or args.from_asset):
        parser.print_help()
        return 0

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{args.district}_shp").geometry()
    t0, t3 = pp.EPOCHS["T0"], pp.EPOCHS["T3"]
    print(f"{args.district}   T0 {t0} -> T3 {t3}\n")

    if args.to_asset:
        print("PCC:")
        export_asset(pcc(args.district, aoi).clip(aoi), aoi, args.district, "pcc")
        print("NDVI differencing:")
        export_asset(ndvi_difference(args.district, aoi).clip(aoi),
                     aoi, args.district, "ndvi")
        print("\nBoth are batch tasks and survive this machine shutting down.")
        print("Re-run with --from-asset once they finish.")
        return 0

    rows = []
    for method, names in (("pcc", CHANGE), ("ndvi", {0: "no_change", 1: "change"})):
        try:
            image = ee.Image(asset_id(args.district, method))
            image.bandNames().getInfo()
        except Exception:
            print(f"{method}: asset not ready — run --to-asset and wait\n")
            continue
        table = areas(image, aoi, "change", names)
        print(f"{method.upper()}")
        print(f"  {'class':<24}{'area (ha)':>14}{'share':>9}")
        for name, stats in table.items():
            print(f"  {name:<24}{stats['area_ha']:>14,.1f}{stats['share']:>9.2%}")
            rows.append({"district": args.district, "method": method,
                         "class": name, "area_ha": stats["area_ha"],
                         "share": stats["share"]})
        print()

    if rows:
        import pandas as pd

        TABLE_DIR.mkdir(parents=True, exist_ok=True)
        out = TABLE_DIR / f"change_areas_{args.district}_{t0}_{t3}.csv"
        pd.DataFrame(rows).to_csv(out, index=False)
        print(f"Written: {out.relative_to(REPO)}\n")

        # PCC's gain class is the honest warning sign in this table. The
        # classifier is trained on 2024 and applied to 1990 (Option B), so
        # any systematic under-calling of forest at T0 reappears as gain at
        # T3. Implausibly large gain therefore measures classifier drift
        # across time, not regrowth — and it is exactly the error
        # accumulation that makes PCC the method to beat rather than trust.
        gain = next((r["share"] for r in rows
                     if r["method"] == "pcc" and r["class"] == "gain"), 0.0)
        if gain > 0.10:
            print(f"WARNING: PCC reports {gain:.1%} forest GAIN. Treat as")
            print("classifier drift between 1990 and 2024, not as regrowth,")
            print("until the reference sample says otherwise (Phase 8).")

    print("Raw pixel counts. NOT reportable — Phase 8 runs these through the")
    print("Olofsson estimator against the reference sample and attaches a")
    print("95% CI (rule 4).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
