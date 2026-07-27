"""Sample labelled pixels from the feature stack, inside the block splits.

Feeds the Random Forest baseline (E1/E2). Pixels are drawn separately from
the train, val and test block sets defined by src/splits.py, so the
spatial disjointness established there survives into the model.

    python src/extract_pixels.py --year 2024
    python src/extract_pixels.py --year 2024 --district sylhet

Output: data/pixels/{district}_{year}_{split}.csv  (gitignored, regenerable)

WHY SAMPLING HAPPENS PER SPLIT, NOT ONCE
----------------------------------------
Drawing one big sample and splitting it afterwards would reintroduce
exactly the leakage src/splits.py exists to prevent (rule 2). The split
region is applied BEFORE sampling, so a train pixel and a test pixel can
never come from the same block.

Normalisation statistics, when they are computed, must likewise come from
the training split alone. Computing them over everything leaks test
information into the model — quietly, and in a way that inflates results
without ever failing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import labels as lb  # noqa: E402
import preprocess as pp  # noqa: E402

SPLIT_DIR = REPO / "data" / "splits"
OUT_DIR = REPO / "data" / "pixels"

SPLITS = ["train", "val", "test"]

# Pixels per class per split. Sampling is capped rather than proportional:
# forest loss is 0.22% of pixels in Gazipur and Sylhet, so a proportional
# draw would return a few dozen change pixels and the model would learn to
# predict "no change" everywhere at 99.8% accuracy.
PER_CLASS = {"train": 4000, "val": 1200, "test": 1200}

# Earth Engine aborts a getInfo once the result exceeds 5,000 elements.
# Classes are fetched one request at a time, each capped below that.
MAX_PER_REQUEST = 4500

SEED = 20260726


def split_region(district: str, split: str) -> ee.Geometry:
    """Dissolved geometry of the blocks belonging to one split."""
    path = SPLIT_DIR / f"{district}_blocks.geojson"
    if not path.exists():
        sys.exit(
            f"Missing {path.relative_to(REPO)}\n"
            "Run: python src/splits.py --write"
        )
    blocks = gpd.read_file(path)
    subset = blocks[blocks["split"] == split]
    if subset.empty:
        sys.exit(f"{district}: no blocks assigned to '{split}'")
    dissolved = subset.to_crs("EPSG:4326").geometry.union_all()
    return ee.Geometry(dissolved.__geo_interface__)


def sample_split(district: str, year: int, split: str) -> pd.DataFrame:
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    region = split_region(district, split)

    stack = pp.build_composite(aoi, year)
    label = lb.build_labels(aoi, year).rename("label")
    combined = stack.addBands(label)

    band_names = stack.bandNames().getInfo()
    n = PER_CLASS[split]

    # stratifiedSample, NOT sample(). sample() with numPixels draws across
    # the whole region and drops masked pixels afterwards, so each class
    # comes back in proportion to its abundance: masking to natural forest
    # (7% of Gazipur) and asking for 4,000 returned 259. stratifiedSample
    # takes a per-class quota and fills each independently.
    #
    # One request PER CLASS, because Earth Engine aborts a getInfo once the
    # result passes 5,000 elements — asking for 4,000 across three classes
    # at once fails outright with "Collection query aborted".
    frames = []
    for code, name in lb.CLASSES.items():
        fc = combined.stratifiedSample(
            numPoints=0,                   # ignored when classPoints is given
            classBand="label",
            region=region,
            scale=pp.NATIVE_SCALE,
            seed=SEED,
            classValues=[code],
            classPoints=[min(n, MAX_PER_REQUEST)],
            dropNulls=True,
            tileScale=4,
            geometries=False,
        )
        try:
            rows = [f["properties"] for f in fc.getInfo()["features"]]
        except Exception as exc:
            print(f"    {name}: sample failed — {str(exc)[:80]}")
            continue
        if not rows:
            # Expected for plantation (never assigned — blocked on BFD) and
            # for water in Bandarban, which has almost none.
            print(f"    {name}: none available")
            continue
        frame = pd.DataFrame(rows)
        frame["class_name"] = name
        frames.append(frame)
        short = "  (quota not met)" if len(frame) < min(n, MAX_PER_REQUEST) else ""
        print(f"    {name}: {len(frame):,} pixels{short}")

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    keep = [b for b in band_names if b in out.columns] + ["label", "class_name"]
    return out[keep]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=pp.EPOCHS["T3"])
    parser.add_argument("--district", choices=pp.DISTRICTS)
    args = parser.parse_args()

    if args.year < lb.HANSEN_BASELINE_YEAR:
        sys.exit(
            f"No training labels exist for {args.year}. Hansen's baseline is "
            f"{lb.HANSEN_BASELINE_YEAR}; pre-2000 years use the unsupervised "
            "regime (Option B, methodology_plan.md 4.1)."
        )

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    districts = [args.district] if args.district else pp.DISTRICTS

    print(f"year {args.year}   canopy threshold {lb.CANOPY_THRESHOLD}%   seed {SEED}")
    print("NOTE: plantation (class 2) is never assigned — blocked on BFD.\n")

    for district in districts:
        print(f"=== {district} ===")
        for split in SPLITS:
            print(f"  {split}:")
            frame = sample_split(district, args.year, split)
            if frame.empty:
                print("    nothing sampled")
                continue
            out = OUT_DIR / f"{district}_{args.year}_{split}.csv"
            frame.to_csv(out, index=False)
            print(f"    -> {out.relative_to(REPO)}  ({len(frame):,} rows)")
        print()

    print("Pixels are regenerable; data/pixels/ is gitignored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
