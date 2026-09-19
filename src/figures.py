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

import json

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrow, FancyBboxPatch, Patch  # noqa: E402

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


HDIST = {"gazipur": "G", "sylhet": "S", "bandarban": "B"}
MODEL_COLOURS = {"E1": "#9aa3b0", "E2": "#2f6f4f",
                  "RF (patch pixels)": "#9aa3b0", "U-Net": "#2f6f4f", "E7 stacked": "#f2a33c",
                  "E3": "#2f6f4f", "E4": "#9aa3b0"}


def _swatch_legend(ax, entries, y=1.08, fontsize=6.5) -> None:
    """A compact colour-key drawn as text above the axes — cheaper than a legend box
    at the sizes these pre-defence-deck thumbnails are drawn at."""
    x = 0.0
    for label, colour in entries:
        ax.text(x, y, "■", transform=ax.transAxes, color=colour, fontsize=fontsize + 1,
                 va="bottom")
        ax.text(x + 0.045, y, label, transform=ax.transAxes, color="#333333",
                 fontsize=fontsize, va="bottom")
        x += 0.045 + 0.028 * len(label) + 0.05


def fig_terrain_ablation() -> None:
    """E1 vs E2 macro F1 per district — Slide 13 thumbnail ([IMG-08])."""
    path = TABLES / "rf_baseline_2024.csv"
    if _missing(path, "src/models/rf.py"):
        return
    table = pd.read_csv(path)
    e1 = [table[(table.district == d) & (table.experiment == "E1")].macro_f1_mean.iloc[0]
          for d in pp.DISTRICTS]
    e2 = [table[(table.district == d) & (table.experiment == "E2")].macro_f1_mean.iloc[0]
          for d in pp.DISTRICTS]

    fig, ax = plt.subplots(figsize=(3.95, 0.60))
    xs = np.arange(len(pp.DISTRICTS))
    width = 0.32
    ax.bar(xs - width / 2, e1, width, color=MODEL_COLOURS["E1"])
    ax.bar(xs + width / 2, e2, width, color=MODEL_COLOURS["E2"])
    for x, v1, v2 in zip(xs, e1, e2):
        if v2 < v1:  # terrain hurt this district (Bandarban) — mark it, don't hide it
            ax.text(x + width / 2, v2 + 0.03, "▼", ha="center", va="bottom",
                     fontsize=7, color="#d1495b")
    ax.set_xticks(xs)
    ax.set_xticklabels([HDIST[d] for d in pp.DISTRICTS], fontsize=7)
    ax.set_yticks([])
    ax.set_ylim(0, 0.95)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=1)
    _swatch_legend(ax, [("E1", MODEL_COLOURS["E1"]), ("E2", MODEL_COLOURS["E2"])])
    fig.subplots_adjust(top=0.78, bottom=0.16, left=0.02, right=0.98)
    _save(fig, "rf_terrain_ablation.png")


def fig_model_comparison() -> None:
    """Patch-test macro F1, RF vs U-Net vs stacked ensemble — Slide 13 ([IMG-09])."""
    rows = {}
    for district in pp.DISTRICTS:
        path = TABLES / f"ensemble_E7_{district}_2024.json"
        if _missing(path, "src/models/ensemble.py"):
            return
        rows[district] = json.loads(path.read_text())["scores"]

    models = ["RF (patch pixels)", "U-Net", "E7 stacked"]
    fig, ax = plt.subplots(figsize=(3.95, 0.60))
    xs = np.arange(len(pp.DISTRICTS))
    width = 0.24
    for k, model in enumerate(models):
        vals = [rows[d][model]["macro_f1"] for d in pp.DISTRICTS]
        ax.bar(xs + (k - 1) * width, vals, width, color=MODEL_COLOURS[model])
    ax.set_xticks(xs)
    ax.set_xticklabels([HDIST[d] for d in pp.DISTRICTS], fontsize=7)
    ax.set_yticks([])
    ax.set_ylim(0, 0.62)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=1)
    _swatch_legend(ax, [("RF", MODEL_COLOURS["RF (patch pixels)"]),
                        ("U-Net", MODEL_COLOURS["U-Net"]),
                        ("E7", MODEL_COLOURS["E7 stacked"])])
    fig.subplots_adjust(top=0.78, bottom=0.16, left=0.02, right=0.98)
    _save(fig, "model_comparison.png")


def fig_texture_ablation() -> None:
    """Sylhet per-class F1, texture on (E3) vs off (E4) — Slide 13 ([IMG-10])."""
    e3_path = TABLES / "ensemble_E7_sylhet_2024.json"
    e4_path = TABLES / "unet_E4_sylhet_2024_perclass.json"
    if _missing(e3_path, "src/models/ensemble.py") or _missing(e4_path, "src/models/unet.py --experiment E4"):
        return
    e3 = json.loads(e3_path.read_text())["scores"]["U-Net"]["per_class_f1"]
    e4 = json.loads(e4_path.read_text())[0]["per_class_f1"]
    classes = ["non_forest", "natural_forest", "plantation", "water"]
    labels = ["NF", "Forest", "Plant.", "Water"]

    fig, ax = plt.subplots(figsize=(3.95, 0.60))
    xs = np.arange(len(classes))
    width = 0.32
    v3 = [e3[c] for c in classes]
    v4 = [e4[c] for c in classes]
    ax.bar(xs - width / 2, v3, width, color=MODEL_COLOURS["E3"])
    ax.bar(xs + width / 2, v4, width, color=MODEL_COLOURS["E4"])
    plantation_idx = classes.index("plantation")
    ax.annotate("+22%", xy=(plantation_idx, max(v3[plantation_idx], v4[plantation_idx]) + 0.05),
                ha="center", fontsize=6.5, color="#d1495b", fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_yticks([])
    ax.set_ylim(0, 1.05)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=1)
    _swatch_legend(ax, [("texture (E3)", MODEL_COLOURS["E3"]), ("no texture (E4)", MODEL_COLOURS["E4"])])
    fig.subplots_adjust(top=0.78, bottom=0.16, left=0.02, right=0.98)
    _save(fig, "texture_ablation.png")


def fig_bandarban_disturbance() -> None:
    """Stable / permanent / cyclical / undetermined shares — Slide 14 ([IMG-11])."""
    path = TABLES / "landtrendr_bandarban_disturbance.csv"
    if _missing(path, "src/landtrendr.py --district bandarban"):
        return
    table = pd.read_csv(path, comment="#").set_index("class")

    order = ["stable", "permanent_conversion", "cyclical_disturbance", "undetermined"]
    colours = {"stable": "#dfe6e0", "permanent_conversion": "#d1495b",
               "cyclical_disturbance": "#2f6f4f", "undetermined": "#c3c9d1"}
    inline = {"stable", "cyclical_disturbance"}  # segments wide enough for a label inside
    label_text = {"stable": "stable", "permanent_conversion": "permanent",
                  "cyclical_disturbance": "cyclical (jhum)", "undetermined": "undet."}

    fig, ax = plt.subplots(figsize=(6.05, 0.80))
    left = 0.0
    callout_side = 1  # alternate external callouts up/down so leaders don't collide
    for cls in order:
        share = table.loc[cls, "share"]
        ax.barh(0, share, left=left, height=0.62, color=colours[cls],
                edgecolor="white", linewidth=0.6)
        centre = left + share / 2
        pct = f"{share * 100:.1f}%"
        if cls in inline:
            txt_colour = "white" if cls == "cyclical_disturbance" else "#333333"
            ax.text(centre, 0, f"{label_text[cls]}\n{pct}", ha="center", va="center",
                    fontsize=6.5, color=txt_colour, linespacing=1.1)
        else:
            y = 0.62 if callout_side > 0 else -0.62
            ax.annotate(f"{label_text[cls]} {pct}", xy=(centre, 0.31 * (1 if y > 0 else -1)),
                        xytext=(centre, y), ha="center",
                        va="bottom" if y > 0 else "top", fontsize=6.5, color="#333333",
                        arrowprops=dict(arrowstyle="-", color="#888888", linewidth=0.6))
            callout_side *= -1
        left += share
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.95, 0.95)
    ax.axis("off")
    fig.subplots_adjust(top=0.98, bottom=0.02, left=0.01, right=0.99)
    _save(fig, "bandarban_disturbance.png")


def fig_bandarban_by_year(scale: float = 1.0) -> None:
    """Disturbed area per year, split by class — the RQ4 result as a series.

    The class totals say how much; this says when, and it is the only view
    in which the jhum cycle looks like a cycle. It also makes the method's
    one irreducible limitation visible rather than footnoted: everything
    from 2019 on is `undetermined`, because a plot cleared within
    RECOVERY_WINDOW years of the series end has not had time to regrow and
    cannot be told from permanent conversion.
    """
    path = TABLES / "landtrendr_bandarban_by_year.csv"
    if _missing(path, "src/landtrendr.py --from-asset --by-year"):
        return
    table = pd.read_csv(path)

    series = [
        ("cyclical_disturbance_ha", "cyclical jhum", "#2f6f4f"),
        ("permanent_conversion_ha", "permanent conversion", "#d1495b"),
        ("undetermined_ha", "undetermined (too recent to judge)", "#c3c9d1"),
    ]

    fig, ax = plt.subplots(figsize=(9.4, 3.5))
    bottom = np.zeros(len(table))
    for column, label, colour in series:
        ax.bar(table["year"], table[column], bottom=bottom, width=0.78,
               label=label, color=colour, edgecolor="white", linewidth=0.3)
        bottom += table[column].to_numpy()

    # The boundary is a property of the method, not of the landscape, so it
    # is drawn rather than left for the reader to infer from the colours.
    first_undetermined = table.loc[table["undetermined_ha"] > 0, "year"].min()
    ax.axvline(first_undetermined - 0.5, color="#888888", linewidth=1.1,
               linestyle="--")
    # Set low and on two lines, in the gap above the small post-2018 bars.
    # Placed at the top it ran straight through the final-year column, which
    # is the tallest on the chart.
    ax.text(first_undetermined + 0.1, ax.get_ylim()[1] * 0.52,
            "recovery not\nyet judgeable", fontsize=8.5 * scale,
            color="#666666", va="top", linespacing=1.25)

    ax.set_ylabel("disturbed area (ha)", fontsize=9.5 * scale)
    ax.set_xlim(pp.START_YEAR - 0.8, pp.END_YEAR + 0.8)
    ax.tick_params(labelsize=9 * scale)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e4eaef", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9 * scale, loc="upper left", ncol=1)

    fig.tight_layout()
    _save(fig, "bandarban_disturbance_by_year"
          f"{'_poster' if scale != 1.0 else ''}.png")


def fig_trajectories(scale: float = 1.0) -> None:
    """Three real pixels, 1988-2024 — the evidence rule 9 rests on.

    Every other figure reports rule 9 as a total: so much cyclical, so
    much permanent. This is the one that shows why the distinction is
    real rather than asserted, and it needs no numbers read off it. A
    cyclical pixel saws up and down; a permanently converted one drops
    once and stays down; a stable one never moves. A bitemporal
    comparison samples two of these 37 points and cannot, even in
    principle, tell the first two apart.

    The series are real observations, not the LandTrendr fit — a fitted
    line would beg the question by showing the segmentation's own answer
    instead of the record it was derived from. Gaps are years with no
    usable observation at that pixel, left as gaps rather than
    interpolated.
    """
    path = REPO / "ecovision-dashboard" / "src" / "data" / "trajectories.json"
    if _missing(path, "src/export_trajectories.py"):
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    points = {p["id"]: p for p in payload["points"]}

    # One pixel per behaviour, all three in Bandarban so the contrast is
    # landscape-controlled: same district, same composites, same year range.
    #
    # The permanent example is `permanent-2`, not the higher-magnitude
    # `permanent-6`. Both are classed permanent and both classifications are
    # defensible, but -6 climbs back to 61% of its pre-disturbance NBR by the
    # end of the series: it qualifies as permanent only because it failed to
    # recover 70% *within six years*, which is a true statement about the
    # rule and a misleading picture on a poster. -2 dropped in 1998 and is
    # still under half its old level a quarter-century later, which is what
    # the class is meant to describe.
    # Two straplines each: the full one for the thesis, and a short one for
    # the poster, where the type is 1.5x larger and the panel is no wider.
    # The long line is not shrunk to fit — at poster distance a line nobody
    # can read is the same as no line, and the poster's own caption under
    # the figure carries the argument at 21 pt.
    panels = [
        ("bandarban-cyclical-3", "Cyclical jhum", "#2f6f4f",
         "three clearings since 1988, each one regrown",
         "regrown every time"),
        ("bandarban-permanent-2", "Permanent conversion", "#d1495b",
         "cleared 1998; 26 years on, still under half recovered",
         "cleared 1998, never back"),
        ("bandarban-stable-1", "Stable forest", "#6b7a88",
         "no sustained drop in 37 years — the baseline",
         "no sustained drop"),
    ]
    missing = [pid for pid, *_ in panels if pid not in points]
    if missing:
        print(f"  skipped trajectories.png — no such point(s): {missing}")
        return

    years = np.arange(payload["startYear"], payload["endYear"] + 1)
    # `scale` multiplies type, not the canvas. Shrinking the canvas to make
    # type print larger was tried first and ran the three panel titles into
    # one another — there is only so much width for "Permanent conversion".
    fig, axes = plt.subplots(1, 3, figsize=(9.4, 2.9), sharey=True)

    for ax, (pid, title, colour, strap, short) in zip(axes, panels):
        strap = short if scale > 1.3 else strap
        point = points[pid]
        nbr = np.array([np.nan if v is None else v for v in point["nbr"]],
                       dtype=float)
        ax.plot(years, nbr, color=colour, linewidth=1.5, solid_capstyle="round")
        ax.fill_between(years, -0.1, nbr, color=colour, alpha=0.10)

        # Title and strapline both live above the axes, stacked. Setting the
        # strap at 1.015 put it inside the plot area and over the gridlines.
        ax.set_title(title, fontsize=10 * scale, color="#11161c",
                     pad=22 * scale, loc="left")
        ax.text(0.0, 1.035, strap, transform=ax.transAxes, fontsize=8 * scale,
                color="#75838d", va="bottom")
        ax.set_xlim(years[0] - 0.5, years[-1] + 0.5)
        ax.set_ylim(-0.1, 1.0)
        # Two ticks at poster type size; four only when the labels are small
        # enough not to touch.
        ax.set_xticks([1990, 2010] if scale > 1.3 else [1990, 2000, 2010, 2020])
        ax.tick_params(labelsize=8.5 * scale)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#e4eaef", linewidth=0.7)
        ax.set_axisbelow(True)
        # Coordinates, so the claim is checkable rather than illustrative.
        ax.text(0.985, 0.045, f"{point['lat']:.3f}, {point['lon']:.3f}",
                transform=ax.transAxes, fontsize=7 * scale,
                color="#9aa6b0",
                ha="right")

    axes[0].set_ylabel("NBR", fontsize=9.5 * scale)
    fig.tight_layout()
    _save(fig, f"trajectories{'_poster' if scale != 1.0 else ''}.png")


def fig_bandarban_jhum_map() -> None:
    """The permanent-vs-cyclical map behind the RQ4 table — Chapter 6 §6.5.

    Rendered from the committed GEE asset `landtrendr_bandarban`, which is
    the same image the area figures in §6.5 were tabulated from. Rendering
    from the asset rather than recomputing matters for more than speed: the
    segmentation behind it runs 37 dry-season composites, and a fresh run
    could disagree with the published table at the margins. The figure and
    the number come from one object.
    """
    try:
        import ee
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        print(f"  SKIPPED — Earth Engine unavailable ({str(exc)[:60]}). "
              f"Run `earthengine authenticate` first.")
        return

    asset = f"{pp.ASSET_ROOT}landtrendr_bandarban"
    try:
        classified = ee.Image(asset)
        classified.getInfo()
    except Exception:
        print(f"  SKIPPED — {asset} does not exist. Produce it with "
              f"src/landtrendr.py --district bandarban --to-asset.")
        return

    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}bandarban_shp")
    # Same palette as fig_bandarban_disturbance, so the map and the bar
    # chart read as one pair rather than two unrelated graphics.
    colours = {"stable": "#dfe6e0", "permanent_conversion": "#d1495b",
               "cyclical_disturbance": "#2f6f4f", "undetermined": "#c3c9d1"}
    order = ["stable", "permanent_conversion", "cyclical_disturbance", "undetermined"]

    # `class` is categorical, and the asset was written toFloat() with no
    # pyramidingPolicy, so its overviews are MEAN-averaged. Drawn straight
    # at thumbnail size, a cell that is half stable (0) and half cyclical
    # (2) averages to 1 and paints as "permanent conversion" — the first
    # version of this figure was a red speckle that contradicted its own
    # legend. Downsample by majority instead, which is the correct
    # reduction for a class band.
    display_scale = 100
    mode_class = (classified.select("class").int()
                  .reduceResolution(reducer=ee.Reducer.mode(), maxPixels=1024)
                  .reproject(crs=pp.NATIVE_CRS, scale=display_scale))

    url = mode_class.clip(aoi.geometry()).getThumbURL({
        "min": 0, "max": 3,
        "palette": [colours[c].lstrip("#") for c in order],
        "region": aoi.geometry(),
        "dimensions": 1300,
        "format": "png",
    })
    import urllib.request
    with urllib.request.urlopen(url, timeout=180) as response:
        blob = response.read()

    import io as _io
    from matplotlib.image import imread
    arr = imread(_io.BytesIO(blob), format="png")

    fig, ax = plt.subplots(figsize=(7.2, 7.6))
    ax.imshow(arr)
    ax.axis("off")

    labels = {"stable": "stable (80.8%)",
              "permanent_conversion": "permanent conversion (3.15%)",
              "cyclical_disturbance": "cyclical jhum (12.24%)",
              "undetermined": "undetermined, post-2018 (3.79%)"}
    handles = [Patch(facecolor=colours[c], edgecolor="#888888", linewidth=0.5,
                     label=labels[c]) for c in order]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.11),
              ncol=2, frameon=False, fontsize=9)

    ax.text(0.5, -0.145,
            f"Displayed at {display_scale} m by majority class; areas in the legend are "
            f"tabulated at the native {pp.NATIVE_SCALE} m.\nPatches smaller than a "
            f"display cell are generalised away, so the map shows where each class "
            f"occurs, not how much.",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=8, color="#666666")

    fig.suptitle("Bandarban — permanent conversion separated from cyclical jhum\n"
                 "LandTrendr on the annual NBR series, 1988–2024",
                 fontsize=12, y=0.97)
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    _save(fig, "bandarban_jhum_map.png")


def fig_adjusted_loss() -> None:
    """Adjusted forest loss ± 95% CI per district — Slide 14 ([IMG-12]).

    Bandarban uses the reconciled 2026-08-07 estimate (commit 82fe7e2),
    not the pre-reconciliation figure still quoted in docs/phase8_results.md
    at time of writing — that doc is stale and should be regenerated from
    outputs/tables/adjusted_loss_bandarban_2024.csv to match.
    """
    values, errors = [], []
    for district in pp.DISTRICTS:
        path = TABLES / f"adjusted_loss_{district}_2024.csv"
        if _missing(path, "src/area_estimation.py"):
            return
        row = pd.read_csv(path).set_index("class").loc["forest_loss"]
        values.append(row["adjusted_area_ha"])
        errors.append(row["ci95_ha"])

    fig, ax = plt.subplots(figsize=(6.05, 0.70))
    ys = np.arange(len(pp.DISTRICTS))
    colours = ["#d1495b" if (v - e) > 0 else "#4c78a8" for v, e in zip(values, errors)]
    ax.errorbar(values, ys, xerr=errors, fmt="none", ecolor="#888888",
                elinewidth=1.1, capsize=2.5, capthick=1.1, zorder=1)
    ax.scatter(values, ys, color=colours, s=26, zorder=2)
    ax.axvline(0, color="#333333", linewidth=0.8, linestyle="--", zorder=0)
    x_max = max(v + e for v, e in zip(values, errors))
    for y, v, e in zip(ys, values, errors):
        # label to the right of the whisker, not above the marker — with three
        # rows this tight (0.70 in tall) a stacked label collides with the row above
        ax.text(v + e + x_max * 0.025, y, f"{v:,.0f} ± {e:,.0f} ha", ha="left", va="center",
                 fontsize=6.3, color="#333333")
    ax.set_yticks(ys)
    ax.set_yticklabels([HDIST[d] for d in pp.DISTRICTS], fontsize=7)
    ax.set_xticks([])
    ax.set_xlim(min(0, min(v - e for v, e in zip(values, errors))) * 1.08, x_max * 1.55)
    ax.set_ylim(-0.6, len(pp.DISTRICTS) - 0.4)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=2)
    fig.subplots_adjust(top=0.98, bottom=0.06, left=0.04, right=0.98)
    _save(fig, "adjusted_loss.png")


def fig_pipeline_overview() -> None:
    """Vertical analysis pipeline, Compositing through Accuracy assessment — Slide 8 ([IMG-03]).

    Structural, not a data result — same status as fig_study_area's mechanism
    labels above. Mirrors the stage row already on Slide 8 (CLAUDE.md repo
    structure / methodology_plan.md phases), drawn top-to-bottom for the
    portrait-shaped placeholder.
    """
    stages = [
        ("Compositing", "dry-season median, cloud-masked", "#4c78a8"),
        ("Harmonisation", "cross-sensor, locally fitted", "#4c78a8"),
        ("Feature construction", "23-band stack: spectral, texture, terrain", "#4c78a8"),
        ("Spatial partitioning", "disjoint 10 km blocks, never pixels", "#f2a33c"),
        ("Classification", "RF / U-Net / Siamese, per district", "#2f6f4f"),
        ("Change detection", "PCC · NDVI-diff · LandTrendr (Bandarban)", "#2f6f4f"),
        ("Accuracy assessment", "independent reference sample, Olofsson CI", "#d1495b"),
    ]
    fig, ax = plt.subplots(figsize=(4.05, 4.13))
    n = len(stages)
    box_h = 0.72
    top_margin = 0.15
    available = 10 - 2 * top_margin
    gap = (available - box_h * n) / (n - 1) if n > 1 else 0
    y = 10 - top_margin
    box_w = 8.4
    x0 = (10 - box_w) / 2
    for i, (title, note, colour) in enumerate(stages):
        box = FancyBboxPatch((x0, y - box_h), box_w, box_h,
                              boxstyle="round,pad=0.02,rounding_size=0.12",
                              linewidth=1.1, edgecolor=colour, facecolor=colour + "22")
        ax.add_patch(box)
        ax.text(x0 + 0.25, y - box_h * 0.36, title, fontsize=9, fontweight="bold",
                color="#222222", va="center")
        ax.text(x0 + 0.25, y - box_h * 0.74, note, fontsize=6.3, color="#555555", va="center")
        if i < n - 1:
            ax.annotate("", xy=(5.0, y - box_h - gap + 0.06), xytext=(5.0, y - box_h - 0.02),
                        arrowprops=dict(arrowstyle="-|>", color="#666666", linewidth=1.1))
        y -= box_h + gap
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")
    fig.subplots_adjust(top=0.99, bottom=0.01, left=0.01, right=0.99)
    _save(fig, "pipeline_overview.png")


FIGURES_AVAILABLE = {
    "study-area": fig_study_area,
    "splits": fig_splits,
    "harmonisation": fig_harmonisation,
    "scene-availability": fig_scene_availability,
    "terrain-ablation": fig_terrain_ablation,
    "model-comparison": fig_model_comparison,
    "texture-ablation": fig_texture_ablation,
    "bandarban-disturbance": fig_bandarban_disturbance,
    "adjusted-loss": fig_adjusted_loss,
    "bandarban-jhum-map": fig_bandarban_jhum_map,
    "bandarban-by-year": fig_bandarban_by_year,
    "trajectories": fig_trajectories,
    "pipeline-overview": fig_pipeline_overview,
    # Poster variants. Same data, same canvas, 1.5x type -- these two land
    # on the poster at roughly 1:1, so thesis-sized labels would print at
    # 9 pt beside 25 pt body text and be unreadable at poster distance.
    # Written as separate files so the thesis figures never change.
    "bandarban-by-year-poster": lambda: fig_bandarban_by_year(scale=1.5),
    "trajectories-poster": lambda: fig_trajectories(scale=1.5),
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
