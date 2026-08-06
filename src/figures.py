"""Thesis figures that depend on no model result.

Everything here is derivable from the AOI boundaries, the block splits,
the Phase 2 audit and the Phase 3 harmonisation — all of which are done.
That makes these figures writable now, in parallel with interpretation,
rather than at the end when nothing else is left.

    python src/figures.py --all
    python src/figures.py --splits

Output: outputs/figures/*.png (300 dpi, tracked in git — see CLAUDE.md)

NOTHING HERE IS ILLUSTRATIVE
----------------------------
Rule 8. Every number plotted comes from a table produced by an actual run
in outputs/tables/. If an input table is missing, the figure is skipped
with a message saying which script produces it — it is never drawn from
plausible-looking stand-in values.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

VECTOR = REPO / "data" / "vector"
SPLIT_DIR = REPO / "data" / "splits"
TABLES = REPO / "outputs" / "tables"
FIGURES = REPO / "outputs" / "figures"

DPI = 300
SPLIT_COLOURS = {"train": "#4c78a8", "val": "#f2a33c", "test": "#d1495b"}
BANGLADESH = VECTOR / "bangladesh.geojson"


def _save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {path.relative_to(REPO)}")


def _missing(path: Path, produced_by: str) -> bool:
    if path.exists():
        return False
    print(f"  SKIPPED — {path.relative_to(REPO)} does not exist. Produce it with {produced_by}.")
    return True


def bangladesh_outline() -> gpd.GeoDataFrame | None:
    """National boundary for context, cached after the first fetch.

    FAO GAUL via Earth Engine. Used for orientation only — no analysis
    depends on it, so a coarse boundary is fine and rule 1 is untouched.
    """
    if BANGLADESH.exists():
        return gpd.read_file(BANGLADESH)
    try:
        import ee

        ee.Initialize(project=pp.PROJECT)
        country = (
            ee.FeatureCollection("FAO/GAUL/2015/level0")
            .filter(ee.Filter.eq("ADM0_NAME", "Bangladesh"))
            .geometry()
            .simplify(1000)
            .getInfo()
        )
        frame = gpd.GeoDataFrame.from_features(
            [{"type": "Feature", "geometry": country, "properties": {}}], crs="EPSG:4326"
        )
        frame.to_file(BANGLADESH, driver="GeoJSON")
        return frame
    except Exception as exc:
        print(f"  national outline unavailable ({str(exc)[:60]}) — drawing districts alone")
        return None


def fig_study_area() -> None:
    """The three districts, in national context, with the loss mechanism each contributes."""
    mechanism = {
        "gazipur": "abrupt permanent\nconversion",
        "sylhet": "gradual degradation +\nplantation confusion",
        "bandarban": "cyclical clearing\nand regrowth (jhum)",
    }
    frames = {}
    for district in pp.DISTRICTS:
        path = VECTOR / f"{district}.geojson"
        if _missing(path, "src/prepare_aoi.py"):
            return
        frames[district] = gpd.read_file(path)

    fig, axes = plt.subplots(1, 4, figsize=(16, 5.6),
                             gridspec_kw={"width_ratios": [1.5, 1, 1, 1]})

    context = axes[0]
    outline = bangladesh_outline()
    if outline is not None:
        outline.plot(ax=context, color="#eef1f5", edgecolor="#8d95a3", linewidth=0.8)
    for district, frame in frames.items():
        frame.plot(ax=context, color="#2f6f4f", edgecolor="#1d4632", linewidth=0.8)
        centre = frame.geometry.union_all().centroid
        context.annotate(district.capitalize(), (centre.x, centre.y),
                         xytext=(6, 6), textcoords="offset points",
                         fontsize=9, fontweight="bold")
    context.set_title("Study districts, Bangladesh", fontsize=11)
    context.set_aspect("equal")
    context.axis("off")

    # One panel per district, each centred on its own centroid but sharing a
    # single metres-per-inch scale. Plotting all three on one axis puts them
    # at their true separation, which is 400 km — they end up as three
    # unreadable specks, and relative size, the thing worth seeing, is lost.
    metric_frames = {d: f.to_crs(pp.NATIVE_CRS) for d, f in frames.items()}
    half_span = max(
        max(f.total_bounds[2] - f.total_bounds[0],
            f.total_bounds[3] - f.total_bounds[1])
        for f in metric_frames.values()
    ) / 2 * 1.12

    for ax, (district, metric) in zip(axes[1:], metric_frames.items()):
        area_km2 = metric.area.sum() / 1e6
        metric.plot(ax=ax, facecolor="#2f6f4f", alpha=0.28,
                    edgecolor="#1d4632", linewidth=1.2)
        centre = metric.geometry.union_all().centroid
        ax.set_xlim(centre.x - half_span, centre.x + half_span)
        ax.set_ylim(centre.y - half_span, centre.y + half_span)
        ax.set_title(f"{district.capitalize()}  ·  {area_km2:,.0f} km$^2$", fontsize=10.5)
        ax.text(0.5, -0.04, mechanism[district], transform=ax.transAxes,
                ha="center", va="top", fontsize=9, color="#333")
        ax.set_aspect("equal")
        ax.axis("off")

    # Scale bar on the first district panel only; all three share the scale.
    bar_m = 20_000
    bar_ax = axes[1]
    x0 = bar_ax.get_xlim()[0] + half_span * 0.12
    y0 = bar_ax.get_ylim()[0] + half_span * 0.12
    bar_ax.plot([x0, x0 + bar_m], [y0, y0], color="#222", linewidth=2.2)
    bar_ax.text(x0 + bar_m / 2, y0 + half_span * 0.03, f"{bar_m // 1000} km",
                ha="center", fontsize=8.5)

    fig.suptitle(
        f"Three districts, three loss mechanisms  ·  study period "
        f"{pp.START_YEAR}–{pp.END_YEAR}",
        fontsize=12.5, y=0.99)
    _save(fig, "study_area.png")


def fig_splits() -> None:
    """Block assignment per district — the figure that answers rule 2 at a glance."""
    summary = pd.read_csv(TABLES / "splits_summary.csv") if (
        TABLES / "splits_summary.csv").exists() else None

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4))
    for ax, district in zip(axes, pp.DISTRICTS):
        path = SPLIT_DIR / f"{district}_blocks.geojson"
        if _missing(path, "src/splits.py --write"):
            plt.close(fig)
            return
        # Both layers must be reprojected explicitly. The blocks are written
        # in UTM metres and the AOI in degrees; drawn on one axis as-is, the
        # degree-scale geometry collapses to a dot beside coordinates six
        # orders of magnitude larger, and the autoscale hides it.
        blocks = gpd.read_file(path).to_crs(pp.NATIVE_CRS)
        aoi = gpd.read_file(VECTOR / f"{district}.geojson").to_crs(pp.NATIVE_CRS)
        aoi.plot(ax=ax, facecolor="none", edgecolor="#333", linewidth=1.1, zorder=3)
        for split, colour in SPLIT_COLOURS.items():
            subset = blocks[blocks["split"] == split]
            if not subset.empty:
                subset.plot(ax=ax, facecolor=colour, alpha=0.62,
                            edgecolor="white", linewidth=0.35)

        title = district.capitalize()
        if summary is not None:
            rows = summary[summary["district"] == district]
            if not rows.empty:
                shares = ", ".join(
                    f"{r.split} {r.loss_share:.0%}" for r in rows.itertuples())
                title += f"\nforest-loss share — {shares}"
        ax.set_title(title, fontsize=10)
        ax.set_aspect("equal")
        ax.axis("off")

    handles = [Patch(facecolor=c, alpha=0.62, label=f"{s} ({int(t * 100)}%)")
               for (s, c), t in zip(SPLIT_COLOURS.items(), [0.70, 0.15, 0.15])]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=10)
    fig.suptitle(
        "Spatially disjoint 10 km block splits — whole blocks, never pixels "
        "or patches (CLAUDE.md rule 2)", fontsize=12)
    fig.tight_layout(rect=[0, 0.06, 1, 0.94])
    _save(fig, "block_splits.png")


def fig_harmonisation() -> None:
    """Residual RMSE per band per candidate transform, with the adopted one marked.

    This is the figure that justifies departing from Roy et al. (2016) on
    four of six bands — the published coefficients made NIR and SWIR2
    worse here, and NBR is built from exactly those two.
    """
    path = TABLES / "harmonisation_validation.csv"
    if _missing(path, "src/derive_harmonisation.py"):
        return
    table = pd.read_csv(path)
    candidates = ["raw", "roy", "local_ols", "local_rma"]
    labels = {"raw": "no transform", "roy": "Roy et al. (2016)",
              "local_ols": "local OLS", "local_rma": "local RMA"}
    colours = {"raw": "#9aa3b0", "roy": "#4c78a8",
               "local_ols": "#2f6f4f", "local_rma": "#f2a33c"}

    chains = list(dict.fromkeys(table["chain"]))
    fig, axes = plt.subplots(len(chains), 1, figsize=(11, 4.2 * len(chains)),
                             squeeze=False)
    for ax, chain in zip(axes[:, 0], chains):
        subset = table[table["chain"] == chain]
        bands = list(subset["band"])
        width = 0.2
        for k, candidate in enumerate(candidates):
            offsets = [j + (k - 1.5) * width for j in range(len(bands))]
            ax.bar(offsets, subset[candidate], width,
                   label=labels[candidate], color=colours[candidate])
        for j, row in enumerate(subset.itertuples()):
            best = getattr(row, "best")
            k = candidates.index(best)
            ax.text(j + (k - 1.5) * width, subset[best].iloc[j],
                    "▼", ha="center", va="bottom", fontsize=9, color="#d1495b")
        ax.set_xticks(range(len(bands)))
        ax.set_xticklabels(bands)
        ax.set_ylabel("residual RMSE (reflectance)")
        ax.set_title(f"{chain.replace('_', ' ')}  —  ▼ adopted", fontsize=11)
        ax.legend(frameon=False, fontsize=9, ncol=4)
        ax.spines[["top", "right"]].set_visible(False)

    fig.suptitle("Cross-sensor harmonisation: measured, not assumed", fontsize=12.5)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    _save(fig, "harmonisation.png")


def fig_scene_availability() -> None:
    """Usable scenes per district-year — the evidence behind START_YEAR."""
    path = TABLES / "scene_audit_verdicts.csv"
    if _missing(path, "src/scene_audit.py"):
        return
    table = pd.read_csv(path)
    if not {"district", "year"}.issubset(table.columns):
        print(f"  SKIPPED — {path.name} lacks district/year columns")
        return
    count_col = next((c for c in ("total_scenes", "n_scenes", "scenes",
                                  "usable_scenes", "count")
                      if c in table.columns), None)
    if count_col is None:
        print(f"  SKIPPED — no scene-count column in {path.name}")
        return

    grid = table.pivot_table(index="district", columns="year",
                             values=count_col, aggfunc="sum")
    grid = grid.reindex(pp.DISTRICTS)
    fig, ax = plt.subplots(figsize=(14, 3.2))
    mesh = ax.pcolormesh(grid.columns, range(len(grid)), grid.values,
                         cmap="YlGnBu", edgecolors="white", linewidth=0.4)
    ax.set_yticks([i + 0.0 for i in range(len(grid))])
    ax.set_yticklabels([d.capitalize() for d in grid.index])
    ax.axvline(pp.START_YEAR - 0.5, color="#d1495b", linewidth=1.6)
    ax.text(pp.START_YEAR + 0.3, len(grid) - 0.4,
            f"START_YEAR = {pp.START_YEAR}", color="#d1495b", fontsize=9)
    for year in pp.SLC_ONLY_YEARS:
        ax.axvline(year, color="#f2a33c", linewidth=1.2, linestyle="--")
    ax.text(pp.SLC_ONLY_YEARS[0] + 0.3, -0.45,
            "100% SLC-off", color="#c08324", fontsize=8.5)
    fig.colorbar(mesh, ax=ax, label="usable scenes", pad=0.01)
    ax.set_title("Landsat scene availability by district-year "
                 "(dry season, cloud < %d%%)" % pp.MAX_CLOUD, fontsize=11)
    fig.tight_layout()
    _save(fig, "scene_availability.png")


FIGURES_AVAILABLE = {
    "study-area": fig_study_area,
    "splits": fig_splits,
    "harmonisation": fig_harmonisation,
    "scene-availability": fig_scene_availability,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in FIGURES_AVAILABLE:
        parser.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    chosen = [n for n in FIGURES_AVAILABLE
              if args.all or getattr(args, n.replace("-", "_"))]
    if not chosen:
        parser.print_help()
        return 0

    for name in chosen:
        print(f"{name}:")
        FIGURES_AVAILABLE[name]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
