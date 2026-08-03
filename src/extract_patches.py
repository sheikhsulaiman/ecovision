"""Extract 128x128 training patches from the feature stack.

Feeds E3, E4 and E5. Patches are cut INSIDE split blocks and never across
them, so the spatial disjointness from src/splits.py survives into the
neural networks (rule 2).

    python src/extract_patches.py --year 2024 --district gazipur --dry-run
    python src/extract_patches.py --year 2024

Output: data/patches/{district}_{year}_{split}/{block_id}_{r}_{c}.npz
        each holding `x` (128,128,23) float32 and `y` (128,128) uint8

PATCHES NEVER CROSS A BLOCK BOUNDARY
------------------------------------
Each block is tiled independently and partial tiles at the block edge are
discarded. A patch spanning a train block and a test block would put the
same ground on both sides of the evaluation, which is the exact failure
the block splits exist to prevent — and it would not show up as an error,
only as an implausibly good test score.

WHY NOT EXPORT TO DRIVE
-----------------------
ee.data.computePixels returns arrays directly, one request per patch, so
there is no Drive round trip and no manual download step. Each patch is
128*128*23*4 bytes = 1.5 MB, far below the request ceiling.

SAMPLING DIFFERS BY DISTRICT, DELIBERATELY
------------------------------------------
Forest loss is 0.22% of pixels in Gazipur and Sylhet but 24.3% in
Bandarban (docs/phase5_experiment_matrix.md §3). Patches are therefore
filtered toward informative content in the first two districts and kept
whole in Bandarban, where the classes are already near-balanced.

**Test splits are never filtered, in any district.** A filtered test set
measures the sampler rather than the model.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import labels as lb  # noqa: E402
import preprocess as pp  # noqa: E402

SPLIT_DIR = REPO / "data" / "splits"
OUT_DIR = REPO / "data" / "patches"

PATCH_PX = 128            # docs/phase5_experiment_matrix.md §1
OVERLAP_PX = 32           # reduces edge artefacts on reassembly
STRIDE_PX = PATCH_PX - OVERLAP_PX

SPLITS = ["train", "val", "test"]

# A training patch that is 100% one class teaches nothing and costs a full
# forward pass. Applied only where the classes are wildly imbalanced.
MIN_MINORITY_FRACTION = 0.02
FILTERED_DISTRICTS = {"gazipur", "sylhet"}

# Label value for pixels with no data. Blocks are clipped to the district,
# so patches on the boundary contain pixels outside it; computePixels
# returns those as -inf in every band sourced from the composite. (Terrain
# comes from SRTM, which is global and unmasked, so it stays finite — which
# is how these were identified.)
#
# They must be IGNORED by the loss, not folded into class 0. Writing them
# as non-forest would teach the model that the outside of the district is
# non-forest, and the error would never surface as anything but slightly
# worse edge predictions.
IGNORE_INDEX = 255

# A patch mostly outside the district costs a full forward pass to learn
# almost nothing.
MIN_VALID_FRACTION = 0.70


def patch_origins(bounds: tuple[float, float, float, float]) -> list[tuple[float, float]]:
    """Top-left corners of whole patches fitting inside one block.

    Partial tiles are dropped: a patch must lie entirely within the block
    or it could straddle a split boundary.
    """
    minx, miny, maxx, maxy = bounds
    span_m = PATCH_PX * pp.NATIVE_SCALE
    stride_m = STRIDE_PX * pp.NATIVE_SCALE
    xs, ys = [], []
    x = minx
    while x + span_m <= maxx:
        xs.append(x)
        x += stride_m
    y = miny
    while y + span_m <= maxy:
        ys.append(y)
        y += stride_m
    return [(px, py) for px in xs for py in ys]


def fetch_patch(image: ee.Image, x: float, y: float, band_names: list[str]) -> np.ndarray | None:
    """One patch as a numpy array, via computePixels."""
    span_m = PATCH_PX * pp.NATIVE_SCALE
    request = {
        "expression": image,
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": PATCH_PX, "height": PATCH_PX},
            "affineTransform": {
                "scaleX": pp.NATIVE_SCALE, "shearX": 0, "translateX": x,
                "shearY": 0, "scaleY": -pp.NATIVE_SCALE, "translateY": y + span_m,
            },
            "crsCode": pp.NATIVE_CRS,
        },
    }
    try:
        return ee.data.computePixels(request)
    except Exception as exc:
        print(f"      fetch failed: {str(exc)[:70]}")
        return None


def informative(label: np.ndarray, district: str, split: str) -> bool:
    """Should this patch be kept?

    Test splits are always kept — filtering them would make the metric
    describe the sampler. Bandarban is kept whole because its classes are
    already near-balanced.
    """
    if split == "test" or district not in FILTERED_DISTRICTS:
        return True
    valid = label[label != IGNORE_INDEX]
    if valid.size == 0:
        return False
    counts = np.bincount(valid, minlength=len(lb.CLASSES))
    present = counts[counts > 0]
    if present.size < 2:
        return False                       # single-class patch
    return present.min() / valid.size >= MIN_MINORITY_FRACTION


def run_split(district: str, year: int, split: str, dry_run: bool, limit: int | None) -> dict:
    blocks = gpd.read_file(SPLIT_DIR / f"{district}_blocks.geojson")
    blocks = blocks[blocks["split"] == split]

    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    stack = pp.build_composite(aoi, year)
    label = lb.build_labels(aoi, year).rename("label")
    combined = stack.addBands(label).toFloat()
    band_names = combined.bandNames().getInfo()

    out_dir = OUT_DIR / f"{district}_{year}_{split}"
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    planned = kept = skipped = failed = 0
    for _, block in blocks.iterrows():
        origins = patch_origins(block.geometry.bounds)
        planned += len(origins)
        if dry_run:
            continue
        for i, (x, y) in enumerate(origins):
            if limit and kept >= limit:
                break
            arr = fetch_patch(combined, x, y, band_names)
            if arr is None:
                failed += 1
                continue
            stacked = np.stack([arr[b] for b in band_names], axis=-1)
            raw_features = stacked[..., :-1]
            raw_label = stacked[..., -1]

            # Validity is judged on the composite bands, NOT on terrain:
            # SRTM is global and stays finite even outside the district, so
            # a terrain-based check would call every edge pixel valid.
            valid = np.isfinite(raw_features[..., :-3]).all(axis=-1) & np.isfinite(raw_label)
            valid_fraction = float(valid.mean())
            if valid_fraction < MIN_VALID_FRACTION:
                skipped += 1
                continue

            features = np.nan_to_num(
                raw_features, nan=0.0, posinf=0.0, neginf=0.0
            ).astype(np.float32)
            lab = np.where(valid, np.nan_to_num(raw_label, nan=0.0), IGNORE_INDEX)
            lab = lab.astype(np.uint8)

            if not informative(lab, district, split):
                skipped += 1
                continue
            np.savez_compressed(
                out_dir / f"{block.block_id}_{i:02d}.npz",
                x=features, y=lab, valid=valid,
            )
            kept += 1
        if limit and kept >= limit:
            break

    return {"blocks": len(blocks), "planned": planned, "kept": kept,
            "skipped": skipped, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=pp.EPOCHS["T3"])
    parser.add_argument("--district", choices=pp.DISTRICTS)
    parser.add_argument("--split", choices=SPLITS)
    parser.add_argument("--dry-run", action="store_true", help="count patches only")
    parser.add_argument("--limit", type=int, help="stop after N patches per split")
    args = parser.parse_args()

    if args.year < lb.HANSEN_BASELINE_YEAR:
        sys.exit(
            f"No labels exist for {args.year}. Hansen's baseline is "
            f"{lb.HANSEN_BASELINE_YEAR}; earlier years use the unsupervised "
            "regime (Option B)."
        )

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    districts = [args.district] if args.district else pp.DISTRICTS
    splits = [args.split] if args.split else SPLITS

    mb = PATCH_PX * PATCH_PX * 23 * 4 / 1e6
    print(f"patch {PATCH_PX}px ({PATCH_PX * pp.NATIVE_SCALE / 1000:.2f} km), "
          f"overlap {OVERLAP_PX}px, stride {STRIDE_PX}px, ~{mb:.1f} MB each uncompressed")
    print(f"year {args.year}   filtered districts: {', '.join(sorted(FILTERED_DISTRICTS))}\n")

    total = 0
    for district in districts:
        for split in splits:
            stats = run_split(district, args.year, split, args.dry_run, args.limit)
            total += stats["planned"]
            if args.dry_run:
                print(f"  {district:<11} {split:<6} {stats['blocks']:>3} blocks -> "
                      f"{stats['planned']:>4} whole patches")
            else:
                print(f"  {district:<11} {split:<6} kept {stats['kept']:>4}, "
                      f"skipped {stats['skipped']:>4}, failed {stats['failed']:>3}")

    if args.dry_run:
        print(f"\n  total planned: {total:,} patches  (~{total * mb / 1000:.1f} GB uncompressed)")
        print("  re-run without --dry-run to fetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
