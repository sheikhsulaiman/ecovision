"""Merge the hand-drawn tea polygons into one class-2 layer.

Reads data/vector/tea*.kml — one polygon per file, drawn in Google Earth
Pro against sub-metre imagery — and writes a single dissolved layer used
as the plantation class and the plantation reference stratum.

    python src/ingest_tea.py

Output: data/vector/sylhet_tea_estates.geojson

PROVENANCE MATTERS HERE MORE THAN USUAL
---------------------------------------
These polygons are the only source of class 2. No open dataset maps
Bangladesh's tea estates (docs/forest_definition.md §6.5), so unlike
classes 0/1 — which come from Hansen and can be regenerated — this layer
exists only because someone drew it. It is committed to git for the same
reason data/reference/ is.

Chapter 5 must say how they were made: drawn by hand in Google Earth Pro
on sub-metre imagery, inside candidate blocks proposed from WorldCover
canopy, verified against the estate directory. Not derived from any
spectral or texture classifier — that separation is what keeps E4
independent (see src/tea_candidates.py).
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

VECTOR_DIR = REPO / "data" / "vector"
OUT = VECTOR_DIR / "sylhet_tea_estates.geojson"

# Polygons still awaiting confirmation. tea10 spans the neighbourhood of
# Khadimnagar National Park; WDPA maps only the gazetted 700 ha core, and
# the surrounding reserve forest is larger and unmapped, so part of tea10
# may be natural forest rather than tea.
# tea10 was flagged provisional after its 1,906 ha extent was found to
# span the Khadimnagar reserve forest, which WDPA does not map beyond the
# gazetted 700 ha core. Visual check at 24.953N 91.945E confirmed it, and
# it was trimmed to 321 ha — an 83% cut. Nothing is provisional now.
PROVISIONAL: set[str] = set()

# Sanity bounds. Sylhet estates run from about 100 ha to 650 ha; anything
# far outside that is either a plot-level fragment or has swallowed
# something that is not an estate.
TYPICAL_MIN_HA, TYPICAL_MAX_HA = 40, 2500


def main() -> int:
    files = sorted(glob.glob(str(VECTOR_DIR / "tea*.kml")))
    if not files:
        sys.exit("No data/vector/tea*.kml found — draw them in Google Earth Pro first")

    rows = []
    for path in files:
        for _, r in gpd.read_file(path).iterrows():
            rows.append({"name": r.get("Name") or Path(path).stem,
                         "geometry": r.geometry})
    frame = gpd.GeoDataFrame(rows, crs="EPSG:4326")

    # Earth Pro writes every vertex as lon,lat,altitude — 3D geometry with
    # a meaningless z of 0. Earth Engine rejects it outright with "Invalid
    # GeoJSON geometry", so it must be flattened here rather than worked
    # around at each use site.
    if frame.geometry.has_z.any():
        from shapely import force_2d

        print(f"  flattened {int(frame.geometry.has_z.sum())} 3D geometries to 2D")
        frame["geometry"] = frame.geometry.apply(force_2d)

    # Earth Pro can emit self-intersecting rings when vertices are dragged;
    # buffer(0) repairs them. An invalid polygon silently breaks every
    # later overlay and area computation.
    invalid = (~frame.geometry.is_valid).sum()
    if invalid:
        print(f"  repaired {invalid} invalid geometries")
        frame["geometry"] = frame.geometry.buffer(0)

    metric = frame.to_crs(pp.NATIVE_CRS)
    frame["area_ha"] = (metric.area / 1e4).round(1)
    frame["provisional"] = frame["name"].isin(PROVISIONAL)

    print(f"{len(frame)} polygons from {len(files)} files\n")
    print(f"{'name':<8}{'area_ha':>10}  status")
    for _, r in frame.sort_values("area_ha", ascending=False).iterrows():
        flag = "PROVISIONAL — verify" if r["provisional"] else ""
        size = "" if TYPICAL_MIN_HA <= r["area_ha"] <= TYPICAL_MAX_HA else "  (outside typical estate size)"
        print(f"{r['name']:<8}{r['area_ha']:>10,.1f}  {flag}{size}")

    # Dissolve so overlapping polygons are not double-counted in area.
    union = metric.union_all()
    dissolved_ha = union.area / 1e4
    print(f"\n  sum {frame['area_ha'].sum():,.1f} ha   dissolved {dissolved_ha:,.1f} ha "
          f"(overlap {frame['area_ha'].sum() - dissolved_ha:,.1f} ha)")

    confirmed = frame[~frame["provisional"]]["area_ha"].sum()
    print(f"  confirmed {confirmed:,.1f} ha   provisional "
          f"{frame[frame['provisional']]['area_ha'].sum():,.1f} ha")

    frame["source"] = "hand-digitised, Google Earth Pro sub-metre imagery"
    frame["digitised"] = "2026-08-06"
    frame[["name", "area_ha", "provisional", "source", "digitised", "geometry"]].to_file(
        OUT, driver="GeoJSON"
    )
    print(f"\nWritten: {OUT.relative_to(REPO)}")
    print("\nThis layer is the ONLY source of class 2 and cannot be regenerated")
    print("by any script. It is committed to git for the same reason the")
    print("reference sample is.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
