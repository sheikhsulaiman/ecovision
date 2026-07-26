"""Extract Gazipur and Sylhet district boundaries for use as GEE assets.

Reads the geoBoundaries BGD ADM2 archive from data/raw/, selects the two
study districts, dissolves each to a single polygon, verifies the area
against published figures, and writes upload-ready files to data/vector/.

Run once. Re-run only if the boundary source changes.

    python src/prepare_aoi.py

Outputs, per district, in data/vector/:
    <district>.geojson          EPSG:4326 — inspection, web display
    <district>_utm46n.geojson   EPSG:32646 — native Landsat CRS
    <district>_shp.zip          zipped shapefile — upload this to GEE

Note on CRS: all area arithmetic happens in EPSG:32646 (UTM 46N), the
native Landsat CRS for Bangladesh. Computing area in EPSG:4326 gives
square degrees, which is meaningless. Per the methodology plan, nothing
is reprojected for analysis — only for display.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd

# --- configuration ----------------------------------------------------

REPO = Path(__file__).resolve().parents[1]
SRC_ZIP = REPO / "data" / "raw" / "geoboundaries" / "geoBoundaries-BGD-ADM2-all.zip"
OUT_DIR = REPO / "data" / "vector"

# Landsat native CRS for Bangladesh. Do not change without reading
# docs/methodology_plan.md Phase 1.1.
UTM46N = "EPSG:32646"

# Published district areas, for the sanity check. Sources differ slightly;
# a deviation inside the tolerance is expected, a large one means the
# boundary was uploaded wrong or is not dissolved.
# (methodology_plan.md Phase 1.1)
EXPECTED_AREA_KM2 = {
    "Gazipur": 1806.0,
    "Sylhet": 3490.0,
    # Added 2026-07-26. One CHT district, not all three — see the scope-change
    # note in CLAUDE.md. Bandarban was chosen over Rangamati (Kaptai reservoir
    # dominates, and reservoir inundation reads as forest loss) and over
    # Khagrachhari (smallest, already most degraded, fragmented geometry).
    "Bandarban": 4479.0,
}
AREA_TOLERANCE = 0.10  # 10% — boundary vintages genuinely differ this much

# geoBoundaries ADM2 name field
NAME_FIELD = "shapeName"


# --- helpers ----------------------------------------------------------


def load_adm2() -> gpd.GeoDataFrame:
    """Load the ADM2 layer straight out of the zip, no manual extraction."""
    if not SRC_ZIP.exists():
        sys.exit(
            f"Missing {SRC_ZIP.relative_to(REPO)}\n"
            "data/raw/ is gitignored by design. Re-download with:\n"
            "  curl -sSL -o data/raw/geoboundaries/geoBoundaries-BGD-ADM2-all.zip \\\n"
            "    https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
            "releaseData/gbOpen/BGD/ADM2/geoBoundaries-BGD-ADM2-all.zip"
        )
    gdf = gpd.read_file(f"zip://{SRC_ZIP}!geoBoundaries-BGD-ADM2.shp")
    if gdf.crs is None:
        sys.exit("Source has no CRS. Refusing to guess — inspect the .prj file.")
    return gdf


def select_district(gdf: gpd.GeoDataFrame, name: str) -> gpd.GeoDataFrame:
    """Select one district by name and dissolve it to a single feature."""
    match = gdf[gdf[NAME_FIELD].str.strip().str.casefold() == name.casefold()]
    if match.empty:
        available = sorted(gdf[NAME_FIELD].unique())
        sys.exit(
            f"District '{name}' not found in {NAME_FIELD}.\n"
            f"Available ({len(available)}): {', '.join(available)}"
        )
    # Dissolve guards against the district arriving as multiple records.
    # A multipart polygon (river islands, enclaves) survives this and is fine.
    dissolved = match.dissolve()
    dissolved[NAME_FIELD] = name
    return dissolved[[NAME_FIELD, "geometry"]].reset_index(drop=True)


def check_area(district: gpd.GeoDataFrame, name: str) -> tuple[float, bool]:
    """Return (area_km2, passed) measured in the native Landsat CRS."""
    area_km2 = float(district.to_crs(UTM46N).geometry.area.iloc[0] / 1e6)
    expected = EXPECTED_AREA_KM2[name]
    deviation = abs(area_km2 - expected) / expected
    return area_km2, deviation <= AREA_TOLERANCE


def write_shapefile_zip(district: gpd.GeoDataFrame, name: str, dest: Path) -> None:
    """Write a zipped shapefile — the format GEE's asset uploader accepts."""
    slug = name.lower()
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        district.to_file(tmpdir / f"{slug}.shp", driver="ESRI Shapefile")
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for part in sorted(tmpdir.glob(f"{slug}.*")):
                zf.write(part, part.name)


# --- main -------------------------------------------------------------


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gdf = load_adm2()

    print(f"Source : {SRC_ZIP.relative_to(REPO)}")
    print(f"CRS    : {gdf.crs.to_string()}")
    print(f"Records: {len(gdf)} ADM2 units\n")

    all_passed = True
    for name in EXPECTED_AREA_KM2:
        district = select_district(gdf, name)
        area_km2, passed = check_area(district, name)
        all_passed &= passed

        slug = name.lower()
        district.to_file(OUT_DIR / f"{slug}.geojson", driver="GeoJSON")
        district.to_crs(UTM46N).to_file(
            OUT_DIR / f"{slug}_utm46n.geojson", driver="GeoJSON"
        )
        write_shapefile_zip(district, name, OUT_DIR / f"{slug}_shp.zip")

        geom = district.geometry.iloc[0]
        flag = "OK" if passed else "CHECK"
        # ASCII only in console output: the default Windows console codepage
        # is cp1252 and raises UnicodeEncodeError on characters like -> or km2.
        print(f"{name}")
        print(f"  area (UTM 46N)  {area_km2:>10,.1f} km2")
        print(f"  expected        {EXPECTED_AREA_KM2[name]:>10,.1f} km2   [{flag}]")
        print(f"  geometry        {geom.geom_type}, {len(geom.geoms) if geom.geom_type == 'MultiPolygon' else 1} part(s)")
        print(f"  bounds (WGS84)  {', '.join(f'{v:.4f}' for v in geom.bounds)}")
        print(f"  written         {slug}.geojson, {slug}_utm46n.geojson, {slug}_shp.zip\n")

    if not all_passed:
        print(
            "At least one area is outside the "
            f"{AREA_TOLERANCE:.0%} tolerance. Before proceeding, check whether the\n"
            "boundary vintage genuinely differs from the published figure, or "
            "whether the\nwrong feature was selected. Do not upload to GEE until "
            "this is understood."
        )
        return 1

    print(f"All {len(EXPECTED_AREA_KM2)} districts verified. Next: upload the _shp.zip files as GEE assets")
    print("(Code Editor > Assets > NEW > Shape files), then set the asset IDs in")
    print("gee/01_aoi.js.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
