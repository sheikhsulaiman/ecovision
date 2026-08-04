"""Turn the reference sample into KML you can click through in Google Earth Pro.

Interpreting 1,550 points from a CSV of coordinates means pasting a
lat/lon into the search box 1,550 times. This writes a KML instead: open
it, and every point is a placemark in the sidebar. Click one, Earth Pro
flies to it. Work down the list.

    python src/export_kml.py
    python src/export_kml.py --district sylhet --author author_b

Output: data/reference/interpret_{district}_{author}.kml

Placemarks are grouped into folders by stratum and named with the
point_id, so the KML sidebar and your interpretation CSV stay in step —
you always know which row you are filling in.

WHY THE CSV IS STILL WHERE YOU RECORD ANSWERS
---------------------------------------------
Earth Pro can edit placemark descriptions, but its KML is not a data
format anyone can reconcile or compute kappa from. Keep the CSV as the
record: the KML is a viewer, the CSV is the dataset.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
REF_DIR = REPO / "data" / "reference"

DISTRICTS = ["gazipur", "sylhet", "bandarban"]
AUTHORS = ["author_a", "author_b"]

# Distinct colours per stratum so a mis-sorted point is visible at a
# glance. KML colours are aabbggrr, not rrggbb.
STRATUM_STYLE = {
    "stable_non_forest": ("ff2020e1", "Stable non-forest"),
    "stable_forest": ("ff4fa159", "Stable natural forest"),
    "forest_loss": ("ff5957e1", "Forest loss"),
    "cyclical": ("ff02a2f0", "Cyclical jhum disturbance"),
    "plantation": ("ffb4783a", "Plantation"),
}

DESCRIPTION = """<![CDATA[
<b>{point_id}</b><br/>
stratum: {stratum}<br/>
lat, lon: {lat:.6f}, {lon:.6f}<br/>
<hr/>
Record your answer in:<br/>
<code>data/reference/interpretation_{district}_{author}.csv</code><br/><br/>
Fields: class_t0, class_t3, confidence, notes<br/>
Classes: 0 non-forest, 1 natural forest, 2 plantation/tea, 3 water
]]>"""


def build_kml(frame: pd.DataFrame, district: str, author: str) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        f"<name>EcoVision — {html.escape(district)} ({html.escape(author)})</name>",
    ]

    for stratum, (colour, _) in STRATUM_STYLE.items():
        parts.append(
            f'<Style id="{stratum}"><IconStyle><color>{colour}</color>'
            "<scale>0.9</scale><Icon><href>"
            "http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png"
            "</href></Icon></IconStyle>"
            "<LabelStyle><scale>0.7</scale></LabelStyle></Style>"
        )

    for stratum, group in frame.groupby("stratum", sort=False):
        label = STRATUM_STYLE.get(stratum, ("ffffffff", stratum))[1]
        parts.append(f"<Folder><name>{html.escape(label)} ({len(group)})</name>")
        for _, row in group.iterrows():
            desc = DESCRIPTION.format(
                point_id=row["point_id"], stratum=row["stratum"],
                lat=row["lat"], lon=row["lon"],
                district=district, author=author,
            )
            parts.append(
                f"<Placemark><name>{html.escape(str(row['point_id']))}</name>"
                f"<description>{desc}</description>"
                f'<styleUrl>#{stratum}</styleUrl>'
                f"<Point><coordinates>{row['lon']:.6f},{row['lat']:.6f},0</coordinates></Point>"
                "</Placemark>"
            )
        parts.append("</Folder>")

    parts.append("</Document></kml>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=DISTRICTS)
    parser.add_argument("--author", choices=AUTHORS)
    args = parser.parse_args()

    districts = [args.district] if args.district else DISTRICTS
    authors = [args.author] if args.author else AUTHORS

    total = 0
    for district in districts:
        source = REF_DIR / f"reference_sample_{district}.csv"
        if not source.exists():
            sys.exit(f"Missing {source.relative_to(REPO)} — run src/reference_sample.py --draw")
        frame = pd.read_csv(source)
        for author in authors:
            out = REF_DIR / f"interpret_{district}_{author}.kml"
            out.write_text(build_kml(frame, district, author), encoding="utf-8")
            print(f"  {out.relative_to(REPO)}  ({len(frame)} placemarks)")
            total += len(frame)

    print(f"\n  {total:,} placemarks written")
    print("\nOpen a .kml in Google Earth Pro. Points appear in the sidebar,")
    print("grouped by stratum. Click one to fly to it.")
    print("\nRecord answers in the interpretation CSV, not in Earth Pro —")
    print("its KML is a viewer format, not something kappa can be computed from.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
