"""Per-band normalisation statistics, computed from the TRAINING split only.

    python src/patch_stats.py --year 2024

Output: outputs/tables/patch_norm_stats_{year}.csv  (per district, per band)

WHY TRAINING ONLY
-----------------
methodology_plan.md §4.3: "Per-band z-score using training-set statistics
only. Computing stats over all data leaks test information."

The leak is quiet. Standardising with a mean and standard deviation that
saw the test split hands the model information about the test
distribution — every input is shifted and scaled by numbers derived
partly from data it is meant never to have seen. Accuracy rises, nothing
errors, and the result is not reproducible on genuinely unseen ground.
This script reads only `*_train` directories, and refuses to read others.

WHY IT MATTERS MORE THAN USUAL HERE
-----------------------------------
The 23 bands are not on comparable scales. Reflectance sits in [0, 1],
thermal near 300 K, and glcm_contrast reaches 1.27 million. Unnormalised,
the texture bands dominate every gradient and the spectral bands — which
carry most of the signal — contribute almost nothing.

Nodata pixels are excluded from the statistics using the `valid` mask
stored with each patch. Including them would drag every mean toward zero
in proportion to how much of a district's edge happens to be sampled.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

PATCH_DIR = REPO / "data" / "patches"
TABLE_DIR = REPO / "outputs" / "tables"

BAND_NAMES = pp.COMMON_BANDS + [
    "thermal", "ndvi", "evi", "savi", "ndwi", "ndmi", "ndbi", "nbr",
    "brightness", "greenness", "wetness",
    "glcm_contrast", "glcm_entropy", "glcm_homogeneity",
    "elevation", "slope", "aspect",
]


def accumulate(directory: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Streaming sum, sum-of-squares and count per band.

    Streaming rather than loading everything: 644 training patches at
    1.5 MB each is about 1 GB, which does not need to be resident to
    compute a mean.
    """
    total = sq_total = count = None
    n_patches = 0
    for path in sorted(directory.glob("*.npz")):
        with np.load(path) as data:
            x = data["x"].astype(np.float64)
            valid = data["valid"] if "valid" in data else np.ones(x.shape[:2], bool)
        flat = x[valid]                       # (n_valid_pixels, n_bands)
        if flat.size == 0:
            continue
        if total is None:
            total = np.zeros(flat.shape[1])
            sq_total = np.zeros(flat.shape[1])
            count = 0
        total += flat.sum(axis=0)
        sq_total += (flat ** 2).sum(axis=0)
        count += flat.shape[0]
        n_patches += 1
    return total, sq_total, count, n_patches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=pp.EPOCHS["T3"])
    args = parser.parse_args()

    rows = []
    for district in pp.DISTRICTS:
        directory = PATCH_DIR / f"{district}_{args.year}_train"
        if not directory.exists():
            print(f"  {district}: no training patches — run src/extract_patches.py")
            continue
        # Guard rather than trust. If this ever reads a val or test
        # directory the statistics are contaminated and nothing will say so.
        assert directory.name.endswith("_train"), "refusing to read a non-train split"

        total, sq_total, count, n_patches = accumulate(directory)
        if total is None:
            print(f"  {district}: no valid pixels")
            continue

        mean = total / count
        var = np.maximum(sq_total / count - mean ** 2, 0.0)
        std = np.sqrt(var)

        print(f"  {district}: {n_patches} training patches, {count:,} valid pixels")
        for i, band in enumerate(BAND_NAMES[: len(mean)]):
            rows.append({
                "district": district, "year": args.year, "band": band,
                "mean": mean[i], "std": std[i],
                "n_pixels": count, "n_patches": n_patches,
            })

    if not rows:
        print("\nNothing computed.")
        return 1

    frame = pd.DataFrame(rows)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLE_DIR / f"patch_norm_stats_{args.year}.csv"
    frame.to_csv(out, index=False)

    print(f"\n--- scale spread, {pp.DISTRICTS[0]} ---")
    sub = frame[frame["district"] == pp.DISTRICTS[0]].sort_values("mean", key=abs)
    for _, r in pd.concat([sub.head(3), sub.tail(3)]).iterrows():
        print(f"  {r['band']:<18} mean {r['mean']:>14,.4f}   std {r['std']:>14,.4f}")
    print("\nThis spread is why normalisation is not optional: unnormalised,")
    print("the texture bands dominate every gradient and the spectral bands")
    print("contribute almost nothing.")

    # A zero-variance band is constant across the whole training split and
    # cannot inform anything; dividing by it produces inf.
    dead = frame[frame["std"] <= 0]
    if len(dead):
        print(f"\nWARNING: {len(dead)} band(s) have zero variance in training:")
        for _, r in dead.iterrows():
            print(f"  {r['district']}/{r['band']}")
        print("Drop them or the z-score divides by zero.")

    print(f"\nWritten: {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
