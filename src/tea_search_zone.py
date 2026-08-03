"""Narrow the area in which Sylhet's 18 tea estates must be digitised.

Tea plantations are excluded from forest by docs/forest_definition.md §1,
so class 2 and the plantation reference stratum both need polygons. None
are available: BFD/BFIS geometry has not arrived, and OpenStreetMap holds
exactly one tea estate polygon for the whole district.

Digitising by hand is therefore the realistic path. This script makes
that tractable by cutting the search area from the whole district to the
canopy inside the upazilas where Siddik et al. (2025) report estates.

    python src/tea_search_zone.py

Output: data/vector/sylhet_tea_search_zone.geojson

THIS IS A LOCATION PRIOR, NOT A CLASSIFIER
------------------------------------------
The zone says where to LOOK. A human decides what is tea. That
distinction matters: using spectral similarity to define the plantation
class would assume the answer to the very question the thesis asks
(RQ3). Narrowing by administrative unit and canopy presence, from an
independent published source, does not.

Nothing here labels anything. The zone is a work aid and is never used as
a mask, a feature, or a class.

Source: Siddik, M.A., Al-Mamun, A., Siddiki, M.H., Chakraborty, B., &
Zohora, K.F.T. (2025). Geospatial Distribution of Tea Estates in
Bangladesh: A Cartographic Gestalt. Journal of Agroforestry and
Environment 18(2), 102-115.
"""

from __future__ import annotations

import sys
from pathlib import Path

import ee
import geopandas as gpd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402
import reference_sample as rs  # noqa: E402

ADM3_ZIP = REPO / "data" / "raw" / "geoboundaries" / "geoBoundaries-BGD-ADM3-all.zip"
VECTOR_DIR = REPO / "data" / "vector"

# Upazilas reported to contain tea estates in Sylhet district, Siddik et
# al. (2025) p.108. The paper names five as principal and two more where
# estates are "visible", indicating expansion into new zones.
TEA_UPAZILAS = [
    "Gowainghat", "Kanaighat", "Sylhet Sadar", "Jaintiapur", "Companiganj",
    "Balaganj", "Fenchuganj",
]

# Siddik et al. report 18 estates and >10,000 ha under tea in Sylhet.
# Both are checks on the digitising, not inputs to it.
EXPECTED_ESTATES = 18
EXPECTED_AREA_HA = 10_000


def main() -> int:
    if not ADM3_ZIP.exists():
        sys.exit(
            f"Missing {ADM3_ZIP.relative_to(REPO)}. Download with:\n"
            "  curl -sSL -o data/raw/geoboundaries/geoBoundaries-BGD-ADM3-all.zip \\\n"
            "    https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
            "releaseData/gbOpen/BGD/ADM3/geoBoundaries-BGD-ADM3-all.zip"
        )

    sylhet = gpd.read_file(VECTOR_DIR / "sylhet.geojson")
    adm3 = gpd.read_file(f"zip://{ADM3_ZIP}!geoBoundaries-BGD-ADM3.shp")

    named = adm3[adm3["shapeName"].isin(TEA_UPAZILAS)].copy()
    # Two upazilas named Companiganj exist nationally (Sylhet and
    # Noakhali). Clipping to the district removes the wrong one without
    # having to special-case it by name.
    zone = gpd.overlay(
        named.to_crs(sylhet.crs), sylhet[["geometry"]], how="intersection"
    )
    zone = zone[~zone.geometry.is_empty].copy()
    zone["area_km2"] = zone.to_crs(pp.NATIVE_CRS).area / 1e6
    zone = zone[zone["area_km2"] > 1].copy()

    district_km2 = float(sylhet.to_crs(pp.NATIVE_CRS).area.iloc[0] / 1e6)
    zone_km2 = float(zone["area_km2"].sum())

    print("Sylhet tea-estate search zone\n")
    print(f"{'upazila':<18}{'km2':>10}")
    for _, row in zone.sort_values("area_km2", ascending=False).iterrows():
        print(f"{row['shapeName']:<18}{row['area_km2']:>10,.0f}")
    print(f"{'TOTAL':<18}{zone_km2:>10,.0f}")
    print(f"\ndistrict area      {district_km2:>10,.0f} km2")
    print(f"search zone        {zone_km2 / district_km2:>10.1%} of district")

    # Narrow again by canopy: tea has a closed canopy, so estates sit
    # inside the >=30% cover layer. This is presence of canopy, not
    # spectral similarity to tea.
    try:
        ee.Initialize(project=pp.PROJECT)
        aoi = ee.Geometry(zone.to_crs("EPSG:4326").geometry.union_all().__geo_interface__)
        hansen = ee.Image(rs.HANSEN)
        canopy = hansen.select("treecover2000").unmask(0).gte(rs.CANOPY_THRESHOLD)
        canopy_m2 = (
            ee.Image.pixelArea().updateMask(canopy)
            .reduceRegion(ee.Reducer.sum(), aoi, pp.NATIVE_SCALE,
                          maxPixels=int(1e10), bestEffort=True)
            .getInfo()["area"]
        )
        canopy_ha = canopy_m2 / 1e4
        print(f"canopy >={rs.CANOPY_THRESHOLD}% in zone {canopy_ha:>10,.0f} ha")
        print(f"  as % of district   {canopy_ha / (district_km2 * 100):>8.1%}")
        print(f"\nSiddik et al. report ~{EXPECTED_AREA_HA:,} ha under tea in Sylhet.")
        if canopy_ha:
            print(f"That is {EXPECTED_AREA_HA / canopy_ha:.0%} of the canopy in this zone —")
            print("so a large share of what Hansen calls forest here is likely tea.")
    except Exception as exc:
        print(f"\n(canopy narrowing skipped: {str(exc)[:70]})")

    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    out = VECTOR_DIR / "sylhet_tea_search_zone.geojson"
    zone[["shapeName", "area_km2", "geometry"]].to_file(out, driver="GeoJSON")
    print(f"\nWritten: {out.relative_to(REPO)}")
    print(f"\nNext: digitise the ~{EXPECTED_ESTATES} estates inside this zone using")
    print("gee/05_tea_digitising.js, then run src/tea_estates.py to ingest them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
