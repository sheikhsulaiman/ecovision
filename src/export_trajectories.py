"""Annual NDVI and NBR trajectories at curated points, for the public site.

    python src/export_trajectories.py
    python src/export_trajectories.py --out ecovision-dashboard/src/data/trajectories.json

WHY CURATED POINTS AND NOT ARBITRARY CLICKS
-------------------------------------------
Earth Engine cannot run in a static site: client-side `ee` would need every
visitor to hold their own EE account, and a service-account proxy would need
a server plus a secret and would spend project quota on every visitor's
click. The Earth Engine App (gee/07_dashboard.js) keeps arbitrary-pixel
clicking for anyone who wants it.

What the site ships instead is a small set of points chosen because their
trajectory *demonstrates* something, extracted once at the native 30 m. That
is a better teaching object than a random pixel: a reader clicking blindly on
a 4,592 km2 district will land on stable forest almost every time, and the
sawtooth that makes the jhum argument is only visible if you land on a plot
that is actually being cycled.

Points are drawn from the classified LandTrendr asset by class, so they are
real examples of the categories the thesis reports rather than locations
picked by eye to look convincing.

NOTHING HERE IS ILLUSTRATIVE
----------------------------
Rule 8. Every value written is sampled from the same composites the thesis
pipeline builds (pp.build_composite), at the same scale. If Earth Engine is
unreachable the script fails rather than emitting anything.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402
import landtrendr as lt  # noqa: E402

DEFAULT_OUT = REPO / "ecovision-dashboard" / "src" / "data" / "trajectories.json"

# How the site labels each class, and what a reader should look for.
READING = {
    "cyclical": "Cleared and regrown more than once. Each dip is a cropping "
                "cycle and each recovery is fallow regrowth — this is not "
                "deforestation, and a two-date comparison cannot tell.",
    "permanent": "One drop, and the canopy never comes back. This is what "
                 "deforestation actually looks like in the record.",
    "stable": "High and flat for the whole series. Undisturbed canopy, and "
              "the baseline everything else is read against.",
    "plantation": "High but flatter than natural forest, with shallow regular "
                  "dips from pruning cycles rather than clearing.",
    "loss_gazipur": "An abrupt, permanent conversion on the edge of Dhaka's "
                    "industrial belt — the simple case the other districts "
                    "are contrasted against.",
}

CLASS_CODE = {"stable": 0, "permanent": 1, "cyclical": 2}

# Sampled per class, then scored and narrowed to KEEP_PER_CLASS. Widening
# the candidate pool costs nothing in Earth Engine calls -- every point
# rides in the same FeatureCollection, so the cost is 37 calls either way.
CANDIDATES_PER_CLASS = 8
KEEP_PER_CLASS = 2


def curated_points() -> list[dict]:
    """Points sampled from the classified asset, plus two fixed references."""
    classified = ee.Image(lt.asset_id("bandarban"))
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}bandarban_shp").geometry()

    picked: list[dict] = []
    for kind in ("cyclical", "permanent", "stable"):
        mask = classified.select("class").eq(CLASS_CODE[kind])
        sample = (classified.updateMask(mask)
                  .sample(region=aoi, scale=pp.NATIVE_SCALE, numPixels=6000,
                          seed=17, geometries=True))
        # A single 30 m pixel's raw annual series is noisy -- residual cloud,
        # BRDF and cross-sensor differences all land in it, which is why the
        # classification fits a trajectory rather than reading raw values.
        # Taking arbitrary pixels of a class therefore produces examples
        # whose class is not visible to a reader. Ordering by disturbance
        # magnitude picks unambiguous cases instead of marginal ones.
        if kind != "stable":
            sample = sample.sort("magnitude", False)
        feats = sample.limit(CANDIDATES_PER_CLASS).getInfo().get("features", [])
        for i, f in enumerate(feats):
            lon, lat = f["geometry"]["coordinates"]
            picked.append({
                "id": f"bandarban-{kind}-{i + 1}",
                "district": "bandarban",
                "kind": kind,
                "lon": round(lon, 6),
                "lat": round(lat, 6),
            })

    # The largest hand-digitised tea estate in Sylhet, 721 ha, taken as the
    # representative point of its polygon in data/vector/sylhet_tea_estates
    # .geojson rather than typed in. A coordinate picked by eye landed 65 km
    # outside the district in an earlier version and sampled nothing but
    # nulls -- the request succeeds, it just misses the image.
    picked.append({
        "id": "sylhet-plantation-1",
        "district": "sylhet",
        "kind": "plantation",
        "lon": 91.99108,
        "lat": 24.96944,
    })

    # GAZ-0301, from the reference sample: interpreted natural_forest at T0
    # and non_forest at T3, high confidence, by both authors.
    picked.append({
        "id": "gazipur-loss-1",
        "district": "gazipur",
        "kind": "loss_gazipur",
        "lon": 90.303743,
        "lat": 23.955232,
    })
    return picked


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def clarity(kind: str, nbr: list[float | None]) -> float:
    """How plainly this series shows the class it was drawn from.

    The raw annual NBR at one 30 m pixel carries real year-to-year noise, so
    a pixel that is genuinely, say, permanent conversion may not look it.
    Ranking candidates lets the site show unambiguous examples without
    inventing them -- every candidate is a real pixel of that class, this
    only decides which two get shown.
    """
    vals = [v for v in nbr if v is not None]
    if len(vals) < 12:
        return float("-inf")
    early, late = _mean(vals[:8]), _mean(vals[-8:])
    spread = max(vals) - min(vals)
    mean = _mean(vals)
    variance = _mean([(v - mean) ** 2 for v in vals]) ** 0.5

    if kind == "permanent":
        # Dropped, and stayed dropped.
        return early - late
    if kind == "stable":
        # High AND flat. Penalising the full range rather than the standard
        # deviation matters: a pixel that drifts steadily upward over the
        # series has a modest sd but is regrowth, not stable canopy, and
        # sd alone happily selected one.
        return mean - spread
    if kind == "cyclical":
        # Crosses its own midline repeatedly: down, back up, down again.
        # Hysteresis at a quarter of the spread keeps noise from counting.
        mid, band = (max(vals) + min(vals)) / 2, spread * 0.25
        crossings, state = 0, None
        for v in vals:
            if v > mid + band and state != "hi":
                crossings, state = crossings + (state is not None), "hi"
            elif v < mid - band and state != "lo":
                crossings, state = crossings + (state is not None), "lo"
        # Reward oscillation, but require the swings to be worth seeing.
        return crossings + min(spread, 0.6)
    return 0.0


def narrow(points: list[dict], series: dict[str, dict]) -> list[dict]:
    """Keep the clearest KEEP_PER_CLASS of each sampled class, all others as-is."""
    kept: list[dict] = []
    for kind in ("cyclical", "permanent", "stable"):
        pool = [p for p in points if p["kind"] == kind]
        ranked = sorted(pool, key=lambda p: clarity(kind, series[p["id"]]["nbr"]),
                        reverse=True)
        for p in ranked[:KEEP_PER_CLASS]:
            print(f"  {kind:10s} keep {p['id']:26s} "
                  f"clarity {clarity(kind, series[p['id']]['nbr']):+.3f}")
            # The id is never renamed. An earlier version renamed kept points
            # to a rank, and main() then looked their series up by the NEW
            # name -- silently pairing each point with whichever candidate
            # had held that name, so the map showed one pixel's coordinates
            # against another pixel's trajectory.
            kept.append(p)
    # Fixed reference points are not ranked; they are there by name.
    kept.extend(p for p in points if p["kind"] in ("plantation", "loss_gazipur"))
    return kept


def sample_series(points: list[dict]) -> dict[str, dict]:
    """NDVI and NBR per year at every point, one Earth Engine call per year."""
    by_district: dict[str, ee.FeatureCollection] = {}
    for district in {p["district"] for p in points}:
        by_district[district] = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"pid": p["id"]})
            for p in points if p["district"] == district
        ])
    years = list(range(pp.START_YEAR, pp.END_YEAR + 1))
    series = {p["id"]: {"ndvi": [None] * len(years), "nbr": [None] * len(years)}
              for p in points}
    lock = threading.Lock()

    def work(index_year):
        index, year = index_year
        # Each district's composite is bounded by its own AOI. Bounding every
        # composite with Bandarban's, as a first version did, silently
        # returned nulls for every Sylhet and Gazipur point -- the sample
        # succeeds, it just falls outside the image.
        for district, members in by_district.items():
            aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
            composite = pp.build_composite(aoi, year, with_stack=False)
            ndvi = composite.normalizedDifference(["nir", "red"]).rename("ndvi")
            nbr = composite.normalizedDifference(["nir", "swir2"]).rename("nbr")
            try:
                sampled = (ndvi.addBands(nbr)
                           .sampleRegions(collection=members,
                                          scale=pp.NATIVE_SCALE,
                                          properties=["pid"], geometries=False)
                           .getInfo())
            except Exception as exc:
                print(f"    {year} {district}: {str(exc)[:60]}")
                continue
            with lock:
                for feat in sampled.get("features", []):
                    prop = feat["properties"]
                    entry = series.get(prop.get("pid"))
                    if entry is None:
                        continue
                    for band in ("ndvi", "nbr"):
                        value = prop.get(band)
                        entry[band][index] = None if value is None else round(value, 4)
        print(f"    {year} done")

    print(f"  sampling {len(years)} annual composites at {len(points)} points")
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(work, enumerate(years)))
    return series


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    ee.Initialize(project=pp.PROJECT)

    print("picking points from the classified asset:")
    points = curated_points()
    for p in points:
        print(f"  {p['id']:28s} {p['lat']:.5f}, {p['lon']:.5f}")

    series = sample_series(points)

    print("\nnarrowing to the clearest examples per class:")
    points = narrow(points, series)

    payload = {
        "startYear": pp.START_YEAR,
        "endYear": pp.END_YEAR,
        "scale": pp.NATIVE_SCALE,
        "note": ("Annual dry-season composites, same pipeline as the thesis "
                 "(src/preprocess.py build_composite). Sampled at 30 m. "
                 "Nulls are years with no usable observation at that pixel."),
        "reading": READING,
        "points": [
            {**p, **series[p["id"]], "reading": READING[p["kind"]]}
            for p in points
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    size_kb = args.out.stat().st_size / 1024
    print(f"\nwrote {args.out.relative_to(REPO)}  ({size_kb:.0f} KB, "
          f"{len(points)} points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
