"""Read the Phase 2 scene-availability audit and decide START_YEAR.

Consumes the CSVs exported by gee/02_scene_audit.js (via Google Drive,
placed in data/raw/audit/), applies the decision rule from
docs/methodology_plan.md 2.2, and writes a per-district verdict table
plus an availability figure.

    python src/audit_summary.py

Inputs   data/raw/audit/{district}_scene_audit.csv
Outputs  outputs/tables/scene_audit_summary.csv
         outputs/tables/scene_audit_verdicts.csv
         outputs/figures/scene_availability.png

This script decides nothing on its own authority — it applies a written
rule to real numbers and prints what the rule says. The START_YEAR it
proposes still has to be justified in one written paragraph at Gate 2.

NOTHING HERE INVENTS DATA. If the CSVs are absent the script exits with
instructions rather than producing an illustrative result.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display on this machine; write straight to file
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
AUDIT_DIR = REPO / "data" / "raw" / "audit"
TABLE_DIR = REPO / "outputs" / "tables"
FIG_DIR = REPO / "outputs" / "figures"

DISTRICTS = ["gazipur", "sylhet", "bandarban"]

# --- the decision rule, stated once -----------------------------------
# methodology_plan.md 2.2. Scene counts alone overstate availability,
# because filterBounds() counts a scene clipping the district corner the
# same as one covering it whole. Both conditions must hold.

MIN_SCENES_ANNUAL = 3       # >= 3 scenes: annual composite viable
MIN_SCENES_WINDOW = 1       # 1-2 scenes: 3-year moving window
MIN_PCT_COVERED = 80.0      # below this, the year is not usable whatever
                            # the scene count says
MIN_OBS_PER_PIXEL = 1.0     # mean clear observations per pixel

# A start year is only defensible if the run from it to 2024 is mostly
# usable. One good year in 1987 surrounded by unusable ones is not a start.
MIN_USABLE_FRACTION = 0.80

# Bandarban's cyclical-vs-permanent jhum split needs an annual series, not
# just epoch anchors (docs/forest_definition.md 6.4). A long gap breaks it.
MAX_TOLERABLE_GAP_YEARS = 2


def verdict(row: pd.Series) -> str:
    """Apply the decision rule to one district-year."""
    if row["total_scenes"] == 0:
        return "unusable — no scenes"
    if row["pct_covered"] < MIN_PCT_COVERED:
        return f"unusable — only {row['pct_covered']:.0f}% covered"
    if row["obs_per_pixel"] < MIN_OBS_PER_PIXEL:
        return f"unusable — {row['obs_per_pixel']:.2f} obs/pixel"
    if row["total_scenes"] >= MIN_SCENES_ANNUAL:
        return "annual"
    if row["total_scenes"] >= MIN_SCENES_WINDOW:
        return "3-year window"
    return "unusable"


def is_usable(v: str) -> bool:
    return not v.startswith("unusable")


def load(district: str) -> pd.DataFrame:
    path = AUDIT_DIR / f"{district}_scene_audit.csv"
    if not path.exists():
        sys.exit(
            f"Missing {path.relative_to(REPO)}\n\n"
            "Run gee/02_scene_audit.js in the Earth Engine Code Editor, start\n"
            "the three export tasks, then download the CSVs from Google Drive\n"
            f"(folder 'ecovision_audit') into {AUDIT_DIR.relative_to(REPO)}/.\n\n"
            "This script will not run without them, and will not invent a\n"
            "placeholder audit."
        )
    df = pd.read_csv(path).sort_values("year").reset_index(drop=True)
    df["district"] = district
    df["verdict"] = df.apply(verdict, axis=1)
    df["usable"] = df["verdict"].map(is_usable)
    return df


def propose_start_year(df: pd.DataFrame) -> tuple[int | None, str]:
    """Earliest year whose run to the end is >= MIN_USABLE_FRACTION usable."""
    years = df["year"].to_numpy()
    usable = df["usable"].to_numpy()
    for i, year in enumerate(years):
        if not usable[i]:
            continue
        run = usable[i:]
        if run.mean() >= MIN_USABLE_FRACTION:
            return int(year), f"{run.mean():.0%} of {len(run)} years usable"
    return None, "no run meets the threshold"


def longest_gap(df: pd.DataFrame, from_year: int | None) -> int:
    """Longest consecutive run of unusable years at or after from_year."""
    if from_year is None:
        return len(df)
    sub = df[df["year"] >= from_year]
    longest = current = 0
    for ok in sub["usable"]:
        current = 0 if ok else current + 1
        longest = max(longest, current)
    return longest


def plot(frames: dict[str, pd.DataFrame], dest: Path) -> None:
    fig, axes = plt.subplots(
        len(frames), 1, figsize=(13, 2.4 * len(frames)), sharex=True
    )
    axes = np.atleast_1d(axes)
    for ax, (district, df) in zip(axes, frames.items()):
        colours = [
            "#59a14f" if v == "annual" else "#f0a202" if v == "3-year window" else "#e15759"
            for v in df["verdict"]
        ]
        ax.bar(df["year"], df["total_scenes"], color=colours, width=0.8)
        ax.set_ylabel("scenes")
        ax.set_title(district.capitalize(), loc="left", fontsize=10)
        ax2 = ax.twinx()
        ax2.plot(df["year"], df["pct_covered"], color="#333", lw=1, marker=".", ms=3)
        ax2.axhline(MIN_PCT_COVERED, color="#333", ls=":", lw=0.8)
        ax2.set_ylim(0, 105)
        ax2.set_ylabel("% covered")
    axes[-1].set_xlabel("year")
    fig.suptitle(
        "Dry-season Landsat availability (bars: scenes, line: % of district covered)",
        fontsize=11,
    )
    fig.tight_layout()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=150)
    plt.close(fig)


def main() -> int:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    frames = {d: load(d) for d in DISTRICTS}
    combined = pd.concat(frames.values(), ignore_index=True)

    combined.to_csv(TABLE_DIR / "scene_audit_verdicts.csv", index=False)

    rows = []
    for district, df in frames.items():
        start, why = propose_start_year(df)
        gap = longest_gap(df, start)
        rows.append(
            {
                "district": district,
                "years_audited": len(df),
                "usable_years": int(df["usable"].sum()),
                "annual_viable": int((df["verdict"] == "annual").sum()),
                "window_only": int((df["verdict"] == "3-year window").sum()),
                "unusable": int((~df["usable"]).sum()),
                "proposed_start_year": start,
                "basis": why,
                "longest_gap_from_start": gap,
            }
        )
    summary = pd.DataFrame(rows)
    summary.to_csv(TABLE_DIR / "scene_audit_summary.csv", index=False)

    print(summary.to_string(index=False))
    print()

    starts = [r["proposed_start_year"] for r in rows if r["proposed_start_year"]]
    if len(starts) == len(rows):
        common = max(starts)
        print(f"Common START_YEAR across all districts: {common}")
        print("(the latest of the per-district proposals — a shared start year is")
        print(" required for the cross-district comparison to be meaningful)")
    else:
        print("At least one district has no defensible start year. Do not proceed")
        print("to Phase 3 for that district until this is resolved.")

    # Gate 2's Bandarban-specific condition.
    bandarban = next(r for r in rows if r["district"] == "bandarban")
    print()
    if bandarban["proposed_start_year"] is None:
        print("BANDARBAN: no usable run at all. The jhum cyclical-vs-permanent")
        print("split cannot be supported. See docs/forest_definition.md 6.4.")
    elif bandarban["longest_gap_from_start"] > MAX_TOLERABLE_GAP_YEARS:
        print(
            f"BANDARBAN: longest unusable gap is "
            f"{bandarban['longest_gap_from_start']} years, over the "
            f"{MAX_TOLERABLE_GAP_YEARS}-year tolerance."
        )
        print("LandTrendr needs a near-continuous annual series to separate")
        print("cyclical jhum disturbance from permanent conversion. With a gap")
        print("this long, a plot could be cleared and recover unobserved.")
        print("Bandarban may not be able to report a deforestation figure —")
        print("decide this at Gate 2, not in Month 9.")
    else:
        print(
            f"BANDARBAN: annual series is near-continuous (longest gap "
            f"{bandarban['longest_gap_from_start']} years). LandTrendr is viable."
        )

    plot(frames, FIG_DIR / "scene_availability.png")
    print(f"\nWritten: {TABLE_DIR.relative_to(REPO)}/scene_audit_summary.csv")
    print(f"         {TABLE_DIR.relative_to(REPO)}/scene_audit_verdicts.csv")
    print(f"         {FIG_DIR.relative_to(REPO)}/scene_availability.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
