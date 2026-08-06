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

# NO UPPER CAP, and that was a real bug. A 3,000 ha cap silently dropped a
# 14,053 ha block centred at 24.9485N 91.9321E — the north-east Sylhet
# canopy that contains Malnicherra, Lackatoorah and Khadim, merged with
# surrounding forest. The single most important candidate was excluded for
# being too big.
#
# Adjacent estates and nearby forest merge into one blob at 60 m, so large
# blocks are EXPECTED. They get reviewed and split, not discarded.
MAX_AREA_HA = None

# Homestead vegetation is the dominant false positive: village tree cover
# is real tree cover, so WorldCover classes it as such. Measured over
# TEA-C000, which a reviewer rejected on sight, against a known tea block:
#
#              tree   built-up  cropland  water
#   known tea  94.7%      0.2%      4.1%   1.0%
#   TEA-C000   52.5%     24.6%     15.1%   6.1%
#
# Built-up fraction separates them cleanly. This is a SETTLEMENT filter,
# not a tea filter — it says nothing about tea versus natural forest, which
# is the distinction that must stay with a human (RQ3).
MAX_BUILTUP_FRACTION = 0.08
MIN_TREE_FRACTION = 0.70
BUILTUP_CLASS = 50

# Morphological opening, in metres. Village tree cover connects to real
# canopy through thin corridors, so reduceToVectors merges whole
# settlements onto an estate — a reviewer looking at TEA-C000 in Earth Pro
# saw the polygon's ragged fingers running through Dhopagul, Mahishkher,
# Khadim Nagar and Atgaon.
#
# Eroding by 150 m severs anything narrower than ~300 m, then dilating
# back restores the cores at roughly their original size. Estates are over
# a kilometre across and survive; village corridors do not. Multipart
# results are then split, which is what breaks the 14,053 ha blob into
# reviewable pieces.
# Default 150 m. Measured consequence: Gowainghat fell from 4,942 ha of
# candidates to 640 ha and Jaintiapur to 1,399 ha, which is too little for
# the four and three estates the worklist expects there. Estates following
# narrow valleys are narrower than 300 m and did not survive. Override with
# --opening for those upazilas.
OPENING_M = 150

# Set from --opening at runtime; None means use OPENING_M.
OPENING_OVERRIDE = None

# Protected areas are natural forest by designation, so they cannot be
# tea. Khadimnagar National Park and Tilagar Eco Park both sit inside the
# largest candidate; subtracting them removes known non-tea rather than
# leaving a reviewer to work it out from the imagery.
WDPA = "WCMC/WDPA/current/polygons"

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
    frame = frame[frame["area_ha"] >= MIN_AREA_HA].copy()
    if MAX_AREA_HA is not None:
        frame = frame[frame["area_ha"] <= MAX_AREA_HA].copy()

    frame = subtract_protected(frame, region)
    frame = split_by_opening(frame, OPENING_OVERRIDE)

    frame["area_ha"] = (frame.to_crs(pp.NATIVE_CRS).area / 1e4).round(1)
    return frame[frame["area_ha"] >= MIN_AREA_HA].copy()


def subtract_protected(frame: gpd.GeoDataFrame, region: ee.Geometry) -> gpd.GeoDataFrame:
    """Remove gazetted protected areas — natural forest by designation."""
    try:
        parks = ee.FeatureCollection(WDPA).filterBounds(region).getInfo()
    except Exception as exc:
        print(f"  (protected-area subtraction skipped: {str(exc)[:60]})")
        return frame
    if not parks.get("features"):
        return frame
    pa = gpd.GeoDataFrame.from_features(parks["features"], crs="EPSG:4326")
    names = ", ".join(sorted({str(n) for n in pa.get("NAME", [])})[:4])
    print(f"  subtracting {len(pa)} protected areas: {names}")
    return frame.overlay(pa[["geometry"]], how="difference")


def split_by_opening(frame: gpd.GeoDataFrame, opening_m: float = None) -> gpd.GeoDataFrame:
    """Sever thin village corridors, then split what falls apart.

    Erode and dilate in a projected CRS — buffering in degrees would
    shrink differently by latitude and is meaningless in metres.
    """
    opening_m = OPENING_M if opening_m is None else opening_m
    metric = frame.to_crs(pp.NATIVE_CRS)
    opened = metric.buffer(-opening_m).buffer(opening_m)
    out = gpd.GeoDataFrame(geometry=opened, crs=pp.NATIVE_CRS)
    out = out[~out.geometry.is_empty & out.geometry.notna()]
    return out.explode(index_parts=False).reset_index(drop=True).to_crs("EPSG:4326")


def land_cover_mix(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Built-up and tree fractions per candidate, to drop settlements."""
    wc = ee.ImageCollection(WORLDCOVER).first().select("Map")
    features = [
        ee.Feature(ee.Geometry(geom.__geo_interface__), {"idx": int(i)})
        for i, geom in zip(frame.index, frame.geometry)
    ]

    built = wc.eq(BUILTUP_CLASS).rename("built")
    tree = wc.eq(TREE_CLASS).rename("tree")
    stats = (
        built.addBands(tree)
        .reduceRegions(
            collection=ee.FeatureCollection(features),
            reducer=ee.Reducer.mean(),
            scale=30,
            tileScale=4,
        )
        .getInfo()
    )
    lookup = {
        f["properties"]["idx"]: (
            f["properties"].get("built") or 0.0,
            f["properties"].get("tree") or 0.0,
        )
        for f in stats["features"]
    }
    frame = frame.copy()
    frame["built_frac"] = [round(lookup.get(i, (0, 0))[0], 3) for i in frame.index]
    frame["tree_frac"] = [round(lookup.get(i, (0, 0))[1], 3) for i in frame.index]
    return frame


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
    parser.add_argument("--opening", type=float,
                        help="erosion in metres; lower keeps narrow valley estates")
    parser.add_argument("--upazilas", nargs="+",
                        help="restrict to these upazilas")
    parser.add_argument("--out-suffix", default="",
                        help="suffix for output filenames, to avoid overwriting")
    args = parser.parse_args()

    zone_path = VECTOR_DIR / "sylhet_tea_search_zone.geojson"
    if not zone_path.exists():
        sys.exit(f"Missing {zone_path.relative_to(REPO)} — run src/tea_search_zone.py")

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    global OPENING_OVERRIDE
    OPENING_OVERRIDE = args.opening

    zone = gpd.read_file(zone_path)
    if args.upazilas:
        zone = zone[zone["shapeName"].isin(args.upazilas)].copy()
        if zone.empty:
            sys.exit(f"no upazilas matched {args.upazilas}")
        print(f"restricted to: {', '.join(sorted(zone.shapeName.unique()))}")
    print(f"search zone: {len(zone)} upazila parts, "
          f"{zone.to_crs(pp.NATIVE_CRS).area.sum() / 1e6:,.0f} km2")
    cap = f"up to {MAX_AREA_HA:,.0f} ha" if MAX_AREA_HA else "no upper cap"
    print(f"proposing canopy blocks from {args.min_area:,.0f} ha, {cap}, "
          f"opening {args.opening or OPENING_M:.0f} m")

    blocks = candidate_blocks(zone)
    if blocks.empty:
        print("no candidates found")
        return 1

    before = len(blocks)
    blocks = land_cover_mix(blocks)
    blocks = blocks[
        (blocks["built_frac"] <= MAX_BUILTUP_FRACTION)
        & (blocks["tree_frac"] >= MIN_TREE_FRACTION)
    ].copy()
    print(f"  {before} canopy blocks -> {len(blocks)} after removing settlements "
          f"(built-up > {MAX_BUILTUP_FRACTION:.0%} or tree < {MIN_TREE_FRACTION:.0%})")

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

    keep = ["review_order", "candidate_id", "upazila", "expected_in_upazila", "area_ha", "built_frac", "tree_frac", "is_tea", "estate_name", "notes", "geometry"]
    sfx = args.out_suffix
    blocks[keep].to_file(VECTOR_DIR / f"sylhet_tea_candidates{sfx}.geojson", driver="GeoJSON")
    write_kml(blocks, VECTOR_DIR / f"sylhet_tea_candidates{sfx}.kml")
    blocks[[c for c in keep if c != "geometry"]].to_csv(
        VECTOR_DIR / f"sylhet_tea_candidates{sfx}_review.csv", index=False
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
