"""Spatially disjoint train/validation/test splits.

CLAUDE.md rule 2. Random splitting at pixel or patch level is INVALID on
this data: neighbouring pixels are spatially autocorrelated, so a random
split puts near-identical patches in train and test and inflates accuracy
by 5-15 percentage points. Examiners who know remote sensing ask about
this first.

Whole blocks are assigned to one split each, so no patch can straddle the
boundary between train and test.

    python src/splits.py --report        # block counts, no files written
    python src/splits.py --write         # write block assignments

WHY BLOCKS ARE BALANCED ON LOSS, NOT AREA
-----------------------------------------
Forest loss is 0.22% of pixels in Gazipur and Sylhet (src/labels.py).
Assigning blocks at random by area would routinely produce a test split
containing almost no loss at all — and a test set with no positives
cannot measure F1 on the change class, which is the headline metric
(rule 5).

So blocks are assigned greedily to whichever split is furthest below its
target share of LOSS pixels, with total area as the tiebreak. The split
is still spatially disjoint; it is simply not blind to the thing being
measured. Report the achieved loss share per split — it is evidence the
test set can actually test something.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402
import reference_sample as rs  # noqa: E402

VECTOR_DIR = REPO / "data" / "vector"
SPLIT_DIR = REPO / "data" / "splits"
TABLE_DIR = REPO / "outputs" / "tables"

# Block edge length in metres. 10 km follows methodology_plan.md 5.1.
# See the patch-capacity warning in report() — this interacts with patch
# size and the interaction is not obvious.
BLOCK_M = 10_000

TARGETS = {"train": 0.70, "val": 0.15, "test": 0.15}

# Blocks clipped by the district edge can be slivers. A block holding less
# than this fraction of a full block is merged into its split by area but
# contributes little; below it we drop the block entirely rather than let
# a 2% sliver count as a spatial unit.
MIN_BLOCK_FRACTION = 0.05

# Relative importance when balancing blocks across splits. Loss is
# weighted higher because it is the scarce quantity — 0.22% of pixels in
# Gazipur and Sylhet — and a test split short of loss cannot measure the
# headline metric at all. Area still matters: a training split with 45% of
# the landscape has thrown away a third of its data.
LOSS_WEIGHT = 2.0
AREA_WEIGHT = 1.0

SEED = 20260726


def build_grid(district: str) -> gpd.GeoDataFrame:
    """Regular BLOCK_M grid over the district, clipped to its boundary.

    Built in EPSG:32646 so blocks are square in metres, not degrees. A
    grid built in geographic coordinates would produce blocks that shrink
    toward the poles and are not comparable in area.
    """
    path = VECTOR_DIR / f"{district}_utm46n.geojson"
    if not path.exists():
        sys.exit(f"Missing {path.relative_to(REPO)} — run src/prepare_aoi.py first")

    aoi = gpd.read_file(path)
    minx, miny, maxx, maxy = aoi.total_bounds
    xs = np.arange(minx, maxx + BLOCK_M, BLOCK_M)
    ys = np.arange(miny, maxy + BLOCK_M, BLOCK_M)

    cells = [box(x, y, x + BLOCK_M, y + BLOCK_M) for x in xs for y in ys]
    grid = gpd.GeoDataFrame(geometry=cells, crs=aoi.crs)

    clipped = gpd.overlay(grid, aoi[["geometry"]], how="intersection")
    clipped = clipped[~clipped.geometry.is_empty].copy()
    clipped["area_km2"] = clipped.geometry.area / 1e6

    full = (BLOCK_M / 1000) ** 2
    clipped = clipped[clipped["area_km2"] >= full * MIN_BLOCK_FRACTION].copy()
    clipped = clipped.reset_index(drop=True)
    clipped["block_id"] = [f"{district[:3].upper()}-B{i:03d}" for i in range(len(clipped))]
    return clipped


def loss_pixels_per_block(grid: gpd.GeoDataFrame, district: str) -> pd.Series:
    """Count Hansen loss pixels inside each block, via Earth Engine.

    Uses the same loss definition as the reference-sample stratification,
    so the balancing and the assessment agree about what change is.
    """
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    hansen = ee.Image(rs.HANSEN).clip(aoi)
    lossyear = hansen.select("lossyear").unmask(0)
    tree2000 = hansen.select("treecover2000").unmask(0)

    lo = max(pp.START_YEAR, 2001) - 2000
    hi = pp.END_YEAR - 2000
    loss = (
        tree2000.gte(rs.CANOPY_THRESHOLD)
        .And(lossyear.gte(lo))
        .And(lossyear.lte(hi))
        .rename("loss")
    )

    wgs = grid.to_crs("EPSG:4326")
    features = [
        ee.Feature(ee.Geometry(json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"]),
                   {"block_id": bid})
        for geom, bid in zip(wgs.geometry, wgs["block_id"])
    ]
    fc = ee.FeatureCollection(features)

    reduced = loss.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.sum(),
        scale=pp.NATIVE_SCALE,
        tileScale=4,
    ).getInfo()

    counts = {
        f["properties"]["block_id"]: float(f["properties"].get("sum") or 0.0)
        for f in reduced["features"]
    }
    return pd.Series(counts, name="loss_pixels")


def assign(grid: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Greedy assignment balancing loss pixels, then area.

    Blocks are processed largest-loss-first. Each goes to whichever split
    is furthest below its target share. Processing the rare stuff first
    matters: leaving the high-loss blocks until last would force them
    wherever there happens to be room.
    """
    grid = grid.copy()
    total_loss = grid["loss_pixels"].sum()
    total_area = grid["area_km2"].sum()

    order = grid.sort_values(
        ["loss_pixels", "area_km2"], ascending=False
    ).index.tolist()

    # Deterministic tie-break for the many zero-loss blocks, so the result
    # is reproducible rather than dependent on row order.
    rng = np.random.default_rng(SEED)
    zero = [i for i in order if grid.loc[i, "loss_pixels"] == 0]
    nonzero = [i for i in order if grid.loc[i, "loss_pixels"] > 0]
    rng.shuffle(zero)
    order = nonzero + zero

    got = {s: {"loss": 0.0, "area": 0.0} for s in TARGETS}
    assignment = {}

    for idx in order:
        block_loss = grid.loc[idx, "loss_pixels"]
        block_area = grid.loc[idx, "area_km2"]

        def need(split: str) -> float:
            """How much of this split's own quota is still unfilled, 0-1.

            Normalising by each split's quota is what makes this work. Two
            earlier attempts did not:

            - A lexicographic (loss, area) key let loss dominate absolutely.
              Area only broke exact ties, which never happen on a continuous
              quantity, so train took 70% of the loss and 45% of the area.
            - Minimising the worst ABSOLUTE deviation was worse still. With
              nothing assigned, train's deviation is 0.70 and test's 0.15,
              so train's gap dominates every comparison and fills first —
              Bandarban's test split came out with a single block.

            Proportional need has no such bias: a split holding half its
            quota reads as equally hungry whether that quota is 70% or 15%.
            """
            quota_loss = TARGETS[split] * total_loss
            quota_area = TARGETS[split] * total_area
            loss_need = max(quota_loss - got[split]["loss"], 0) / quota_loss if quota_loss else 0
            area_need = max(quota_area - got[split]["area"], 0) / quota_area if quota_area else 0
            return LOSS_WEIGHT * loss_need + AREA_WEIGHT * area_need

        chosen = max(TARGETS, key=need)
        assignment[idx] = chosen
        got[chosen]["loss"] += block_loss
        got[chosen]["area"] += block_area

    grid["split"] = pd.Series(assignment)
    return grid


def summarise(grid: gpd.GeoDataFrame, district: str) -> pd.DataFrame:
    total_loss = grid["loss_pixels"].sum()
    total_area = grid["area_km2"].sum()
    rows = []
    for split in TARGETS:
        sub = grid[grid["split"] == split]
        rows.append({
            "district": district,
            "split": split,
            "blocks": len(sub),
            "area_km2": sub["area_km2"].sum(),
            "area_share": sub["area_km2"].sum() / total_area if total_area else 0,
            "target_share": TARGETS[split],
            "loss_pixels": sub["loss_pixels"].sum(),
            "loss_share": sub["loss_pixels"].sum() / total_loss if total_loss else 0,
        })
    return pd.DataFrame(rows)


def check_disjoint(grid: gpd.GeoDataFrame) -> list[str]:
    """Blocks must belong to exactly one split and not overlap each other."""
    problems = []
    if grid["block_id"].duplicated().any():
        problems.append("duplicate block_id")
    if grid["split"].isna().any():
        problems.append("unassigned blocks")

    # Grid cells are disjoint by construction; verify rather than assume,
    # because overlay() can produce multipart slivers.
    joined = gpd.sjoin(grid, grid, how="inner", predicate="overlaps")
    crossing = joined[joined["split_left"] != joined["split_right"]]
    if len(crossing):
        problems.append(f"{len(crossing)} block pairs overlap across splits")
    return problems


def patch_capacity(grid: gpd.GeoDataFrame, patch_px: int) -> float:
    """How many non-overlapping patches of this size fit per block."""
    patch_km = patch_px * pp.NATIVE_SCALE / 1000
    return (BLOCK_M / 1000 / patch_km) ** 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write split files")
    parser.add_argument("--report", action="store_true", default=True)
    parser.add_argument("--district", choices=pp.DISTRICTS)
    args = parser.parse_args()

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    districts = [args.district] if args.district else pp.DISTRICTS
    print(f"block size {BLOCK_M / 1000:.0f} km   targets "
          f"{'/'.join(f'{int(v * 100)}' for v in TARGETS.values())}   seed {SEED}\n")

    summaries, grids = [], {}
    for district in districts:
        grid = build_grid(district)
        grid["loss_pixels"] = loss_pixels_per_block(grid, district).reindex(
            grid["block_id"]
        ).to_numpy()
        grid = assign(grid)
        grids[district] = grid

        summary = summarise(grid, district)
        summaries.append(summary)

        print(f"=== {district} — {len(grid)} blocks ===")
        print(summary.to_string(
            index=False,
            columns=["split", "blocks", "area_km2", "area_share",
                     "loss_pixels", "loss_share"],
            float_format=lambda v: f"{v:,.3f}",
        ))
        problems = check_disjoint(grid)
        print("  disjoint check:", "PASS" if not problems else "; ".join(problems))
        print()

    combined = pd.concat(summaries, ignore_index=True)

    # The patch-size interaction, surfaced rather than discovered later.
    print("--- patch capacity per block ---")
    for patch_px in (128, 256):
        per_block = patch_capacity(grids[districts[0]], patch_px)
        total_blocks = sum(len(g) for g in grids.values())
        print(f"  {patch_px}x{patch_px} px "
              f"({patch_px * pp.NATIVE_SCALE / 1000:.2f} km): "
              f"{per_block:.2f} patches per {BLOCK_M / 1000:.0f} km block, "
              f"~{per_block * total_blocks:,.0f} patches across all districts")
    print()

    if not args.write:
        print("--- report only, nothing written. Re-run with --write ---")
        return 0

    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    for district, grid in grids.items():
        out = SPLIT_DIR / f"{district}_blocks.geojson"
        grid.to_file(out, driver="GeoJSON")
        print(f"{district}: {len(grid)} blocks -> {out.relative_to(REPO)}")
    combined.to_csv(TABLE_DIR / "splits_summary.csv", index=False)
    print(f"\nSummary -> outputs/tables/splits_summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
