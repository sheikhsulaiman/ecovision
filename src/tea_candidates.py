"""Propose candidate tea-estate polygons for human confirmation.

No open dataset maps Bangladesh's tea estates (docs/forest_definition.md
§6.5), so the polygons must be drawn. This does the finding and the
rough drawing; a human does the deciding.

    python src/tea_candidates.py

Outputs
    data/vector/sylhet_tea_candidates.geojson   candidate blocks
    data/vector/sylhet_tea_candidates.kml       open in Google Earth Pro
    data/vector/sylhet_tea_candidates_review.csv  one row per candidate

WHAT THIS DOES AND DOES NOT DECIDE
----------------------------------
It finds large contiguous canopy blocks inside the seven upazilas where
Siddik et al. (2025) report tea estates, and vectorises them. That is a
LOCATION prior: where to look.

It does NOT decide what is tea. At Sentinel-2's 10 m, tea and natural
hill forest are both dark, textured canopy — the planted rows that
actually distinguish them are not resolvable. Sub-metre imagery is
needed, which means Google Earth Pro, which means a person.

WHY THAT SEPARATION MATTERS MORE THAN CONVENIENCE
------------------------------------------------
If candidates were selected by texture and then accepted without real
checking, class 2 would be partly texture-defined — and E4, the ablation
that asks whether texture separates tea from forest, would be measuring
its own input. The selection here deliberately uses only canopy presence
and block size, never a texture or spectral tea signature.

**Every candidate must be confirmed at high zoom before use.** A block
this script proposes is a question, not a label.
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
import preprocess as pp  # noqa: E402

VECTOR_DIR = REPO / "data" / "vector"

# ESA WorldCover 10 m, class 10 = tree cover. Used only to find canopy,
# not to identify tea.
WORLDCOVER = "ESA/WorldCover/v200"
TREE_CLASS = 10

# Vectorising at 10 m over 2,229 km2 is needlessly expensive for a
# proposal step; 60 m keeps boundaries good enough to review and adjust.
VECTOR_SCALE = 60

# Sylhet estates run from roughly 100 ha to 610 ha (Malnicherra) and
# above. A first pass at 40 ha produced 147 candidates — more to review
# than the 19 estates you would otherwise just look up by name, which
# defeats the point. 100 ha is still well below the smallest estate.
MIN_AREA_HA = 100
MAX_AREA_HA = 3000

# Which estates the worklist expects in each upazila, so a reviewer knows
# what they are looking for before they open the imagery.
EXPECTED = {
    "Sylhet Sadar": ["Burjan", "Alibahar", "Daddnagar", "Dalia", "Khadim",
                     "Lackatoorah", "Malnicherra", "Star"],
    "Gowainghat": ["Fatehpur", "Habibnagar", "Jafflong", "Khan"],
    "Jaintiapur": ["Afifanagar", "Lallakhal", "Sreepore"],
    "Fenchuganj": ["Dallucherra", "Monipur", "Moomincherra"],
    "Kanaighat": ["Loobacherra"],
}


def candidate_blocks(zone: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    region = ee.Geometry(zone.to_crs("EPSG:4326").geometry.union_all().__geo_interface__)

    trees = (
        ee.ImageCollection(WORLDCOVER).first()
        .select("Map").eq(TREE_CLASS)
        .selfMask()
        .clip(region)
    )

    vectors = trees.reduceToVectors(
        geometry=region,
        scale=VECTOR_SCALE,
        geometryType="polygon",
        eightConnected=True,
        maxPixels=int(1e10),
        bestEffort=True,
    )
    info = vectors.getInfo()

    frame = gpd.GeoDataFrame.from_features(info["features"], crs="EPSG:4326")
    if frame.empty:
        return frame
    # Rounded: these boundaries come from a 60 m vectorisation, so quoting
    # area to 13 decimal places implies a precision that does not exist and
    # makes the review CSV hard to read.
    frame["area_ha"] = (frame.to_crs(pp.NATIVE_CRS).area / 1e4).round(1)
    return frame[(frame["area_ha"] >= MIN_AREA_HA) & (frame["area_ha"] <= MAX_AREA_HA)].copy()


def write_kml(frame: gpd.GeoDataFrame, path: Path) -> None:
    """KML so candidates can be reviewed in Earth Pro at high zoom."""
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        "<name>Sylhet tea estate candidates — CONFIRM EACH AT HIGH ZOOM</name>",
        '<Style id="cand"><LineStyle><color>ff00a5ff</color><width>2</width></LineStyle>'
        "<PolyStyle><color>4d00a5ff</color></PolyStyle></Style>",
    ]
    for _, row in frame.iterrows():
        expect = ", ".join(EXPECTED.get(row["upazila"], [])) or "unknown"
        desc = (
            f"<![CDATA[<b>{row['candidate_id']}</b><br/>"
            f"upazila: {row['upazila']}<br/>"
            f"area: {row['area_ha']:,.0f} ha<br/><hr/>"
            f"Estates expected in this upazila:<br/>{expect}<br/><br/>"
            "<b>Zoom in.</b> Tea shows regular planted rows, uniform canopy, "
            "pale service tracks in a grid, hard geometric edges. Natural "
            "forest is chaotic with ragged edges.<br/><br/>"
            "Record yes/no in sylhet_tea_candidates_review.csv]]>"
        )
        coords = []
        geom = row.geometry
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            ring = " ".join(f"{x:.6f},{y:.6f},0" for x, y in poly.exterior.coords)
            coords.append(
                "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
                f"{ring}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
            )
        parts.append(
            f"<Placemark><name>{row['candidate_id']} ({row['area_ha']:,.0f} ha)</name>"
            f"<description>{desc}</description><styleUrl>#cand</styleUrl>"
            f"<MultiGeometry>{''.join(coords)}</MultiGeometry></Placemark>"
        )
    parts.append("</Document></kml>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-area", type=float, default=MIN_AREA_HA)
    args = parser.parse_args()

    zone_path = VECTOR_DIR / "sylhet_tea_search_zone.geojson"
    if not zone_path.exists():
        sys.exit(f"Missing {zone_path.relative_to(REPO)} — run src/tea_search_zone.py")

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    zone = gpd.read_file(zone_path)
    print(f"search zone: {len(zone)} upazila parts, "
          f"{zone.to_crs(pp.NATIVE_CRS).area.sum() / 1e6:,.0f} km2")
    print(f"proposing canopy blocks between {args.min_area:,.0f} and "
          f"{MAX_AREA_HA:,.0f} ha\n")

    blocks = candidate_blocks(zone)
    if blocks.empty:
        print("no candidates found")
        return 1

    # Label each block with the upazila it mostly falls in, so a reviewer
    # knows which estate names to expect before opening the imagery.
    joined = gpd.sjoin(
        blocks, zone[["shapeName", "geometry"]], how="left", predicate="intersects"
    )
    joined = joined.drop_duplicates(subset=joined.index.name or "geometry", keep="first")
    blocks = blocks.copy()
    blocks["upazila"] = joined["shapeName"].to_numpy()[: len(blocks)]
    blocks["upazila"] = blocks["upazila"].fillna("unknown")

    # Review order matters more than the candidate list itself. Sort by how
    # many estates the worklist expects in that upazila, then by size, so
    # the reviewer meets the likely estates first and can stop once the
    # expected count is found rather than grinding through every block.
    #
    # Balaganj and Companiganj have no named estates in the worklist but are
    # kept, because Siddik et al. note estates "visible in southern upazilas
    # like Balaganj", indicating expansion the directory has not caught up
    # with. They simply sort last.
    blocks["expected_in_upazila"] = blocks["upazila"].map(
        lambda u: len(EXPECTED.get(u, []))
    )
    blocks = blocks.sort_values(
        ["expected_in_upazila", "area_ha"], ascending=[False, False]
    ).reset_index(drop=True)
    blocks["review_order"] = range(1, len(blocks) + 1)
    blocks["candidate_id"] = [f"TEA-C{i:03d}" for i in range(len(blocks))]
    blocks["is_tea"] = ""
    blocks["estate_name"] = ""
    blocks["notes"] = ""

    print(f"{len(blocks)} candidates, {blocks['area_ha'].sum():,.0f} ha total\n")
    print(f"{'upazila':<16}{'candidates':>12}{'area (ha)':>14}   expected estates")
    for upazila, group in blocks.groupby("upazila"):
        expect = len(EXPECTED.get(upazila, []))
        print(f"{upazila:<16}{len(group):>12}{group['area_ha'].sum():>14,.0f}   {expect}")

    keep = ["review_order", "candidate_id", "upazila", "expected_in_upazila", "area_ha", "is_tea", "estate_name", "notes", "geometry"]
    blocks[keep].to_file(VECTOR_DIR / "sylhet_tea_candidates.geojson", driver="GeoJSON")
    write_kml(blocks, VECTOR_DIR / "sylhet_tea_candidates.kml")
    blocks[[c for c in keep if c != "geometry"]].to_csv(
        VECTOR_DIR / "sylhet_tea_candidates_review.csv", index=False
    )

    total = blocks["area_ha"].sum()
    print(f"\nSiddik et al. report ~10,000 ha under tea in Sylhet.")
    print(f"These candidates total {total:,.0f} ha, so roughly "
          f"{10000 / total:.0%} of them should survive review if the "
          "reported figure is right.")
    print("\nWritten to data/vector/. Open the .kml in Google Earth Pro,")
    print("zoom in on each candidate, and mark is_tea yes/no in the review CSV.")
    print("\nA candidate is a QUESTION, not a label. Nothing here identifies")
    print("tea — only canopy in the right upazilas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
