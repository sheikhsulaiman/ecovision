"""Separate permanent forest conversion from cyclical jhum disturbance.

    python src/landtrendr.py --district bandarban --scale 90     # quick look
    python src/landtrendr.py --district bandarban                # full, 30 m
    python src/landtrendr.py --district bandarban --export       # GeoTIFF to Drive

CLAUDE.md rule 9, and the reason Bandarban is in this thesis at all.

Shifting cultivation clears a plot, crops it for a season or two, then
abandons it to regrow over five to seven years. A bitemporal T0->T3
comparison cannot see that. It scores a fallow plot as loss or as nothing
purely according to where in the swidden cycle the two dates happen to
land — the same ground gives opposite answers depending on the calendar.
Only the annual trajectory distinguishes the two, because only the
trajectory shows whether the pixel came back.

THE RULE APPLIED HERE
---------------------
A pixel that drops and then recovers most of the way to its own
pre-disturbance level is cyclical. A pixel that drops and stays down is
permanent conversion. Headline deforestation totals count permanent
conversion only.

WHY NBR AND WHY INVERTED
------------------------
NBR responds to canopy removal more sharply than NDVI and saturates less
over dense tropical canopy. LandTrendr expects a series in which
disturbance is an INCREASE, so the series is negated on the way in and
the fitted values negated on the way back out. Feeding raw NBR in would
segment the series perfectly well and label every recovery a disturbance.

THE END-OF-SERIES PROBLEM, WHICH IS NOT SOLVABLE
------------------------------------------------
A pixel cleared in 2022 has not had time to regrow by 2024, so it looks
exactly like permanent conversion. Calling it permanent would inflate the
headline figure with fallows that simply have not come back yet.

So it is not called permanent. Pixels whose disturbance falls within
RECOVERY_WINDOW years of the series end get their own class,
`undetermined`, and its area is reported alongside the other two rather
than folded into either. That is a real limitation of a 1988-2024 series
and the honest response is to quantify it, not to pick a side.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ee

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

# Kennedy et al. (2010, 2018) defaults, which the GEE implementation ships
# with. Not tuned here: tuning them against the reference sample would
# make the reference sample part of the method it is supposed to measure.
LT_PARAMS = {
    "maxSegments": 6,
    "spikeThreshold": 0.9,
    "vertexCountOvershoot": 3,
    "preventOneYearRecovery": True,
    "recoveryThreshold": 0.25,
    "pvalThreshold": 0.05,
    "bestModelProportion": 0.75,
    "minObservationsNeeded": 6,
}

# Minimum drop in NBR to count as a disturbance at all. Below this the
# signal is indistinguishable from phenology and sensor noise across a
# series that spans four Landsat instruments.
MAGNITUDE_THRESHOLD = 0.20

# Fraction of the drop that must be regained to call the pixel recovered.
# 0.70 rather than 1.0: a regrown jhum fallow is younger secondary forest
# and its NBR sits below the mature canopy it replaced, so demanding full
# recovery would classify most genuine swidden as permanent.
RECOVERY_FRACTION = 0.70

# Years needed after a disturbance before recovery can be judged. Matches
# the 5-7 year swidden cycle in docs/forest_definition.md 6.4.
RECOVERY_WINDOW = 6

CLASSES = {0: "stable", 1: "permanent_conversion", 2: "cyclical_disturbance",
           3: "undetermined"}

VERY_NEGATIVE = -9999


def annual_nbr(aoi: ee.Geometry) -> ee.ImageCollection:
    """One inverted-NBR image per year, tagged with its year."""
    images = []
    for year in range(pp.START_YEAR, pp.END_YEAR + 1):
        composite = pp.build_composite(aoi, year, with_stack=False)
        nbr = composite.normalizedDifference(["nir", "swir2"]).rename("nbr")
        # Mid-year, not 1 January. LandTrendr derives its year row from
        # system:time_start, and a timestamp sitting exactly on the year
        # boundary came back one year early for the whole series — every
        # disturbance date off by one, silently. July is unambiguous.
        images.append(
            nbr.multiply(-1).toFloat()
            .set({"system:time_start": ee.Date.fromYMD(year, 7, 1).millis(),
                  "year": year})
        )
    return ee.ImageCollection(images)


def segmented(aoi: ee.Geometry) -> ee.Image:
    """The raw LandTrendr array: 4 rows (year, source, fitted, isVertex)."""
    result = ee.Algorithms.TemporalSegmentation.LandTrendr(
        timeSeries=annual_nbr(aoi), **LT_PARAMS)
    return result.select("LandTrendr")


def classify(array: ee.Image) -> ee.Image:
    """Per-pixel: stable, permanent conversion, cyclical, or undetermined.

    Everything here is array arithmetic on the segmented series, with no
    step that assumes how long that series is. The array does NOT have a
    fixed length: LandTrendr returns one column per observation the pixel
    actually had, so a cloud-prone hillside carries a shorter array than
    the valley beside it. Flattening to one band per year works on the
    pixels you look at first and fails on the district.

    The series was negated before segmentation, so throughout this
    function a disturbance is a MAXIMUM and recovery is a return downward.
    """
    fitted = array.arraySlice(0, 2, 3)     # 1 x N, inverted NBR
    years = array.arraySlice(0, 0, 1)      # 1 x N
    length = array.arrayLength(1)

    # Deepest disturbance in the series and where it sits.
    peak = fitted.arrayReduce(ee.Reducer.max(), [1]).arrayGet([0, 0])
    index = fitted.arrayArgmax().arrayGet([1])

    # Slices are clamped so neither can be empty. A peak in the first year
    # has no earlier reference, so `pre` collapses to the peak itself,
    # magnitude becomes zero and the pixel falls through to stable — which
    # is the right answer, because a disturbance with nothing before it
    # cannot be distinguished from a series that simply starts low.
    pre = fitted.arraySlice(1, 0, index.max(1))
    post = fitted.arraySlice(1, index.add(1).min(length.subtract(1)), length)

    pre_floor = pre.arrayReduce(ee.Reducer.min(), [1]).arrayGet([0, 0])
    post_floor = post.arrayReduce(ee.Reducer.min(), [1]).arrayGet([0, 0])

    trough_year = (
        years.arraySlice(1, index, index.add(1))
        .arrayReduce(ee.Reducer.first(), [1]).arrayGet([0, 0]).toInt()
    )

    magnitude = peak.subtract(pre_floor)
    disturbed = magnitude.gte(MAGNITUDE_THRESHOLD)

    # Share of the drop regained afterwards. max(1e-6) guards the division
    # only; where magnitude is that small the pixel is not disturbed and
    # the ratio is never consulted.
    regained = peak.subtract(post_floor).divide(magnitude.max(1e-6))
    recovered = regained.gte(RECOVERY_FRACTION)

    too_late = trough_year.gt(pp.END_YEAR - RECOVERY_WINDOW)

    labels = ee.Image.constant(0).toInt().rename("class")
    labels = labels.where(disturbed.And(recovered.Not()), 1)
    labels = labels.where(disturbed.And(recovered), 2)
    labels = labels.where(disturbed.And(too_late), 3)

    return (labels
            .addBands(magnitude.rename("magnitude"))
            .addBands(trough_year.rename("trough_year"))
            .addBands(regained.rename("recovered_fraction")))


def _grouped_area(image: ee.Image, aoi: ee.Geometry, scale: int):
    return (
        ee.Image.pixelArea()
        .addBands(image.select("class"))
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="class"),
            geometry=aoi, scale=scale, maxPixels=int(1e10), bestEffort=True)
    )


def disturbance_by_year(image: ee.Image, aoi: ee.Geometry, scale: int) -> dict:
    """Disturbed area per year per class, from the trough_year band.

    The classified map says how much of the district ended up in each class;
    this says *when* each pixel was disturbed, which is the only view that
    shows the jhum cycle as a cycle rather than as a total. Stable pixels
    have no disturbance year and are excluded.

    trough_year is stored float (the asset is written toFloat), so values
    come back as 2023.94 rather than 2024 and have to be rounded before
    grouping or every year lands in its own bucket.
    """
    year = image.select("trough_year").round().toInt()
    out: dict[str, dict[int, float]] = {}
    for code in (1, 2, 3):
        masked = year.updateMask(image.select("class").eq(code))
        grouped = (
            ee.Image.pixelArea()
            .addBands(masked)
            .reduceRegion(
                reducer=ee.Reducer.sum().group(groupField=1, groupName="year"),
                geometry=aoi, scale=scale, maxPixels=int(1e10),
                bestEffort=True)
            .getInfo()
        )
        out[CLASSES[code]] = {
            int(g["year"]): float(g["sum"]) / 1e4
            for g in grouped.get("groups", [])
            if pp.START_YEAR <= int(g["year"]) <= pp.END_YEAR
        }
    return out


def asset_id(district: str) -> str:
    return f"{pp.ASSET_ROOT}landtrendr_{district}"


def export_asset(image: ee.Image, aoi: ee.Geometry, district: str) -> None:
    """Materialise the classified map as a GEE asset.

    Tabulating areas at 30 m failed both interactively and as a batch
    task, and coarsening the scale was not the answer — the cost is not
    the reduction, it is that every tile of it re-runs 37 dry-season
    composites and the segmentation behind them. Earth Engine will not
    reuse that work across a reduceRegion.

    Writing the result to an asset computes it once. Everything
    afterwards — areas, the reference-point overlay in Phase 8, the loss
    year map — then reads a materialised image and costs almost nothing.
    """
    task = ee.batch.Export.image.toAsset(
        image=image.select(["class", "magnitude", "trough_year"]).toFloat(),
        description=f"landtrendr_asset_{district}",
        assetId=asset_id(district),
        region=aoi,
        scale=pp.NATIVE_SCALE,
        crs=pp.NATIVE_CRS,
        maxPixels=int(1e10),
        # `class` and `trough_year` are categorical. Without this, Earth
        # Engine builds their overviews by averaging, and every view below
        # native scale is then wrong in a way that looks like data: a cell
        # half stable (0) and half cyclical (2) averages to 1, which reads
        # as permanent conversion. The tabulated areas are unaffected
        # because they are computed at native scale, but any map drawn
        # from the averaged overviews contradicts them. Seen in practice —
        # see src/figures.py fig_bandarban_jhum_map.
        pyramidingPolicy={"class": "mode", "trough_year": "mode",
                          "magnitude": "mean"},
    )
    task.start()
    print(f"Asset export started: {asset_id(district)}")
    print("When it finishes, re-run with --from-asset to tabulate areas.")


def areas(image: ee.Image, aoi: ee.Geometry, scale: int) -> dict:
    grouped = _grouped_area(image, aoi, scale).getInfo()
    by_code = {int(g["class"]): float(g["sum"]) for g in grouped.get("groups", [])}
    total = sum(by_code.values()) or 1.0
    return {CLASSES[c]: {"area_ha": a / 1e4, "share": a / total}
            for c, a in sorted(by_code.items())}


def write_by_year(image: ee.Image, aoi: ee.Geometry, district: str,
                  scale: int) -> Path:
    """Write the per-year table `src/figures.py` reads.

    One row per year of the series, one column per class, zero-filled: a
    year with no disturbance is a real zero and has to plot as one, not as
    a gap. Columns stay in class order rather than the order Earth Engine
    happens to return them in.
    """
    import csv

    series = disturbance_by_year(image, aoi, scale)
    columns = [CLASSES[c] for c in (1, 2, 3)]
    out = REPO / "outputs" / "tables" / f"landtrendr_{district}_by_year.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["year"] + [f"{c}_ha" for c in columns])
        for year in range(pp.START_YEAR, pp.END_YEAR + 1):
            writer.writerow([year] + [
                round(series.get(c, {}).get(year, 0.0), 3) for c in columns])
    print(f"wrote {out.relative_to(REPO)}")
    return out


def combine_by_year() -> Path | None:
    """Merge whatever per-district by-year tables exist into one wide table.

    Written from the per-district files rather than recomputed, so the
    combined table cannot disagree with them. Districts with no table are
    left out entirely rather than written as zeros: a district that was
    never run and a district with no disturbance are different statements,
    and a column of zeros reads as the second.
    """
    import csv

    tables = REPO / "outputs" / "tables"
    present = [d for d in pp.DISTRICTS
               if (tables / f"landtrendr_{d}_by_year.csv").exists()]
    if not present:
        print("no per-district by-year tables yet")
        return None

    data: dict[str, dict[int, dict[str, float]]] = {}
    for district in present:
        rows = {}
        with (tables / f"landtrendr_{district}_by_year.csv").open(
                encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                rows[int(row["year"])] = {k: float(v)
                                          for k, v in row.items() if k != "year"}
        data[district] = rows

    columns = [f"{CLASSES[c]}_ha" for c in (1, 2, 3)]
    out = tables / "landtrendr_by_year_all.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["year"] + [f"{d}_{c}" for d in present
                                    for c in columns])
        for year in range(pp.START_YEAR, pp.END_YEAR + 1):
            line: list = [year]
            for district in present:
                row = data[district].get(year, {})
                line += [round(row.get(c, 0.0), 3) for c in columns]
            writer.writerow(line)
    print(f"wrote {out.relative_to(REPO)}  ({', '.join(present)})")
    missing = [d for d in pp.DISTRICTS if d not in present]
    if missing:
        print(f"  not included, never run: {', '.join(missing)}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", default="bandarban", choices=pp.DISTRICTS)
    parser.add_argument("--scale", type=int, default=pp.NATIVE_SCALE,
                        help="coarsen for a quick look; 90 is ~9x cheaper")
    parser.add_argument("--export", action="store_true",
                        help="start a Drive export of the classified image")
    parser.add_argument("--to-asset", action="store_true",
                        help="materialise the classified map as a GEE asset (do this first)")
    parser.add_argument("--from-asset", action="store_true",
                        help="tabulate from the materialised asset — cheap, and the only way at 30 m")
    parser.add_argument("--by-year", action="store_true",
                        help="also write disturbed area per year per class to outputs/tables/")
    parser.add_argument("--combine", action="store_true",
                        help="merge the per-district by-year tables into one; no Earth Engine call")
    args = parser.parse_args()

    if args.combine:
        combine_by_year()
        return 0

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{args.district}_shp").geometry()

    print(f"{args.district}  {pp.START_YEAR}-{pp.END_YEAR}  "
          f"({pp.END_YEAR - pp.START_YEAR + 1} annual composites)")
    print(f"magnitude >= {MAGNITUDE_THRESHOLD}, recovery >= "
          f"{RECOVERY_FRACTION:.0%} within {RECOVERY_WINDOW} years, "
          f"scale {args.scale} m\n")

    if args.from_asset:
        try:
            classified = ee.Image(asset_id(args.district))
            classified.bandNames().getInfo()
        except Exception as exc:
            sys.exit(f"Cannot read {asset_id(args.district)}: {str(exc)[:80]}\n"
                     "Run with --to-asset first and wait for the task to finish.")
        print(f"reading materialised asset {asset_id(args.district)}\n")
    else:
        classified = classify(segmented(aoi)).clip(aoi)

    if args.to_asset:
        export_asset(classified, aoi, args.district)
        return 0

    if args.by_year:
        write_by_year(classified, aoi, args.district, args.scale)

    if args.export:
        task = ee.batch.Export.image.toDrive(
            image=classified.select(["class", "magnitude", "trough_year"]).toFloat(),
            description=f"landtrendr_{args.district}",
            folder="ecovision",
            region=aoi,
            scale=pp.NATIVE_SCALE,
            crs=pp.NATIVE_CRS,
            maxPixels=int(1e10),
        )
        task.start()
        print(f"Export started: landtrendr_{args.district} -> Drive/ecovision")

    print("computing areas — this is 37 composites and it is slow\n")
    try:
        table = areas(classified, aoi, args.scale)
    except ee.ee_exception.EEException as exc:
        print(f"  interactive tabulation failed: {str(exc)[:70]}")
        print("  falling back to a batch task — at 30 m this is expected.\n")
        areas_batch(classified, aoi, args.district)
        print("Check Drive/ecovision when both tasks finish. For numbers now,")
        print("re-run with --scale 300; the class shares are stable at that")
        print("resolution even though the absolute areas are not.")
        return 0
    print(f"{'class':<24}{'area (ha)':>14}{'share':>9}")
    for name, stats in table.items():
        print(f"{name:<24}{stats['area_ha']:>14,.1f}{stats['share']:>9.2%}")

    permanent = table.get("permanent_conversion", {}).get("area_ha", 0.0)
    cyclical = table.get("cyclical_disturbance", {}).get("area_ha", 0.0)
    undetermined = table.get("undetermined", {}).get("area_ha", 0.0)
    disturbed = permanent + cyclical + undetermined

    print(f"\nOf {disturbed:,.0f} ha disturbed since {pp.START_YEAR}:")
    if disturbed:
        print(f"  {permanent / disturbed:.1%} permanent conversion  "
              f"({permanent:,.0f} ha)  <- the only part that is deforestation")
        # "jhum" only where jhum is what this class means. The rule is
        # district-neutral — disturbed, then recovered within the series —
        # but the mechanism is not: in Bandarban that is shifting
        # cultivation, in Sylhet it is far more likely tea replanting or
        # selective extraction with regrowth, and calling that jhum in a
        # printout is how a wrong word reaches a caption.
        label = ("cyclical jhum" if args.district == "bandarban"
                 else "cyclical disturbance (recovered within the series)")
        print(f"  {cyclical / disturbed:.1%} {label}  ({cyclical:,.0f} ha)")
        print(f"  {undetermined / disturbed:.1%} undetermined, disturbed after "
              f"{pp.END_YEAR - RECOVERY_WINDOW}  ({undetermined:,.0f} ha)")

    print("\nHeadline deforestation counts permanent conversion only (rule 9).")
    print("These areas are raw pixel sums and are NOT reportable as they")
    print("stand — Phase 8 runs them through the Olofsson estimator against")
    print("the reference sample and reports them with a 95% CI (rule 4).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
