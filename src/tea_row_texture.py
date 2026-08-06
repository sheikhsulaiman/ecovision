"""Detect planted-row texture inside a candidate, at the scale rows exist.

Samples sub-metre imagery on a grid inside a candidate polygon and scores
each sample for the periodic pattern tea rows make. Output is a per-point
score, so a large mixed candidate can be split into its tea and non-tea
parts rather than accepted or rejected whole.

    python src/tea_row_texture.py --candidate TEA-C000
    python src/tea_row_texture.py --candidate TEA-C000 --samples 400

Outputs
    outputs/tables/row_texture_{candidate}.csv
    data/vector/row_texture_{candidate}.geojson

WHY AN EARLIER ATTEMPT FOUND NOTHING
------------------------------------
tearesults/sylhet_tea_cv_pipeline.ipynb scored whole-candidate chips with
an FFT ring at radius 5-40 px. On a 7424 px chip that is a wavelength of
185-1485 px; at zoom 18 (0.54 m/px) it means 111-890 METRES. Tea rows are
spaced about 1-1.5 m, so the ring was measuring landscape patterning and
could not have seen rows at any threshold. Its Hough test asked for
straight runs of height/6 -- about 540 m -- and returned 0.00 on every
candidate, which is a broken detector rather than an absence of lines.

Scale here is set from the physics instead. At zoom 19 (0.27 m/px) a
1.0-1.5 m row spacing is 3.7-5.6 px, so in a 256 px window the signal sits
at FFT radius 46-69. That is the band this measures.

It also samples INSIDE the polygon rather than its bounding box. C000's
bbox is 21 x 9 km and contains the airport, part of Sylhet city and the
Khadimnagar forest; texture averaged over that says nothing about tea.

WHAT THE SCORE IS AND IS NOT
----------------------------
Row periodicity is evidence of planting, not proof of tea — rubber, teak
and orchards are planted too. In Sylhet, inside these upazilas, tea is the
overwhelmingly likely planted crop, but a high score is a place to look,
not a label.

This must not be used to build class 2 labels wholesale: E4 asks whether
GLCM texture separates tea from forest, and labels built from a texture
detector would make that ablation circular. Use it to target visual
confirmation.
"""

from __future__ import annotations

import argparse
import io
import math
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from PIL import Image
from shapely.geometry import Point

REPO = Path(__file__).resolve().parents[1]
VECTOR_DIR = REPO / "data" / "vector"
TABLE_DIR = REPO / "outputs" / "tables"

ESRI = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}")

# Zoom 19 is 0.27 m/px at this latitude and is the finest with real
# coverage here — zoom 20 returns near-blank tiles (2.5 KB, std 5.4).
ZOOM = 19
TILE_PX = 256

# Row spacing in metres. Bangladeshi tea is typically planted at about
# 1.0-1.5 m between rows.
ROW_SPACING_M = (1.0, 1.5)

# A tile that is mostly water, cloud or deep shadow has no texture to
# measure and produces a meaningless ratio.
MIN_TILE_STD = 8.0

SEED = 20260806


def deg2tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    return (int((lon + 180) / 360 * n),
            int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n))


def metres_per_px(lat: float, z: int) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


def fetch_tile(lon: float, lat: float, z: int) -> np.ndarray | None:
    x, y = deg2tile(lon, lat, z)
    try:
        req = urllib.request.Request(
            ESRI.format(z=z, x=x, y=y), headers={"User-Agent": "Mozilla/5.0"}
        )
        raw = urllib.request.urlopen(req, timeout=45).read()
    except Exception:
        return None
    if len(raw) < 4000:            # blank/placeholder tile
        return None
    try:
        return np.array(Image.open(io.BytesIO(raw)).convert("L"), dtype=float)
    except Exception:
        return None


def row_score(gray: np.ndarray, mpp: float) -> tuple[float, float]:
    """Directional periodicity in the row-spacing band.

    Returns (score, dominant_wavelength_m). The score is the ratio of the
    strongest single frequency in the band to the band's mean — a planted
    block concentrates energy at one spacing and one direction; forest
    canopy spreads it.
    """
    g = gray - gray.mean()
    # Hann window: without it, the image edges act as a step and smear
    # energy across every frequency, swamping the signal being measured.
    w = np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1]))
    spec = np.abs(np.fft.fftshift(np.fft.fft2(g * w)))

    h, wd = spec.shape
    cy, cx = h // 2, wd // 2
    spec[cy - 2:cy + 3, cx - 2:cx + 3] = 0

    yy, xx = np.ogrid[:h, :wd]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)

    # Radius for a given wavelength in pixels: r = N / wavelength_px
    lo_px, hi_px = ROW_SPACING_M[0] / mpp, ROW_SPACING_M[1] / mpp
    r_hi, r_lo = h / lo_px, h / hi_px
    band = (r >= r_lo) & (r <= r_hi)
    if not band.any():
        return 0.0, float("nan")

    vals = spec[band]
    peak = float(vals.max())
    mean = float(vals.mean())
    score = peak / (mean + 1e-9)

    idx = np.argmax(np.where(band, spec, -np.inf))
    py, px = np.unravel_index(idx, spec.shape)
    radius = math.hypot(py - cy, px - cx)
    wavelength_m = (h / radius) * mpp if radius else float("nan")
    return score, wavelength_m


def sample_points(poly, n: int, rng) -> list[Point]:
    minx, miny, maxx, maxy = poly.bounds
    pts, tries = [], 0
    while len(pts) < n and tries < n * 60:
        tries += 1
        p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if poly.contains(p):
            pts.append(p)
    return pts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default="TEA-C000")
    parser.add_argument("--samples", type=int, default=250)
    args = parser.parse_args()

    path = VECTOR_DIR / "sylhet_tea_candidates.geojson"
    if not path.exists():
        sys.exit(f"Missing {path.relative_to(REPO)} — run src/tea_candidates.py")
    cands = gpd.read_file(path)
    row = cands[cands["candidate_id"] == args.candidate]
    if row.empty:
        sys.exit(f"{args.candidate} not found. Have: {', '.join(cands.candidate_id[:5])}...")
    poly = row.geometry.iloc[0]

    rng = np.random.default_rng(SEED)
    pts = sample_points(poly, args.samples, rng)
    mpp = metres_per_px(poly.centroid.y, ZOOM)

    print(f"{args.candidate}: {row.area_ha.iloc[0]:,.0f} ha, {len(pts)} sample points")
    print(f"zoom {ZOOM} = {mpp:.2f} m/px; rows at {ROW_SPACING_M[0]}-{ROW_SPACING_M[1]} m "
          f"= {ROW_SPACING_M[0]/mpp:.1f}-{ROW_SPACING_M[1]/mpp:.1f} px\n")

    records = []
    for i, p in enumerate(pts):
        gray = fetch_tile(p.x, p.y, ZOOM)
        if gray is None or gray.std() < MIN_TILE_STD:
            continue
        score, wl = row_score(gray, mpp)
        records.append({"candidate_id": args.candidate, "lon": round(p.x, 6),
                        "lat": round(p.y, 6), "row_score": round(score, 2),
                        "wavelength_m": round(wl, 2) if np.isfinite(wl) else None,
                        "tile_std": round(float(gray.std()), 1)})
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(pts)} sampled, {len(records)} usable")

    if not records:
        print("no usable tiles")
        return 1

    frame = pd.DataFrame(records)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLE_DIR / f"row_texture_{args.candidate}.csv", index=False)

    gdf = gpd.GeoDataFrame(
        frame, geometry=gpd.points_from_xy(frame.lon, frame.lat), crs="EPSG:4326"
    )
    gdf.to_file(VECTOR_DIR / f"row_texture_{args.candidate}.geojson", driver="GeoJSON")

    q = frame["row_score"].quantile([0.1, 0.5, 0.9])
    print(f"\n{len(frame)} usable tiles")
    print(f"  row_score   p10 {q[0.1]:.2f}   median {q[0.5]:.2f}   p90 {q[0.9]:.2f}")
    print(f"  wavelength  median {frame['wavelength_m'].median():.2f} m")
    print(f"\nWritten: outputs/tables/row_texture_{args.candidate}.csv")
    print("         data/vector/row_texture_" + args.candidate + ".geojson")
    print("\nHigh scores mark where to LOOK, not what it is. Rubber, teak and")
    print("orchards are planted too — confirm visually before labelling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
