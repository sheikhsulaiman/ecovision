"""Phase 8 — accuracy assessment and adjusted area against the reference sample.

    python src/accuracy.py --district sylhet
    python src/accuracy.py            # all districts with an interpretation

Output: outputs/tables/accuracy_{district}_{year}.csv
        outputs/tables/adjusted_area_{district}_{year}.csv
        outputs/tables/confusion_{district}_{year}.csv

THIS IS THE ONLY PLACE ACCURACY IS MEASURED
-------------------------------------------
Everything in src/models/ is scored against Hansen-derived training
labels — model against teacher, useful for comparing E1 to E7 and for
nothing else. Here the maps meet an independently interpreted sample for
the first time, and these numbers will be lower. That is the point.

WHAT "MAP" MEANS HERE
---------------------
Two different things are scored, and they answer different questions.

* the LAND COVER map at T3 (src/labels.py) against class_t3 — RQ1's
  extent figures
* the CHANGE maps (src/change_detection.py, PCC and NDVI differencing)
  against change derived from the pair class_t0 -> class_t3 — RQ4

Change is derived from the two dates, never interpreted directly. An
interpreter asked "did this change" anchors on the answer they expect;
asked twice about single dates, they cannot.

AREAS COME FROM OLOFSSON, NEVER FROM PIXEL COUNTS
-------------------------------------------------
Rule 4. A pixel count is a biased estimate of area whenever the map has
any error at all, and the bias does not shrink with more pixels — only
the stratified estimator with its sampling variance can put an honest
interval on it. src/area_estimation.py implements it and passes 15/15
consistency checks.

WHAT THIS RUN CANNOT DO
-----------------------
No Cohen's kappa. Each district was interpreted once, by one author, in
the reduced design. Inter-interpreter agreement is therefore unmeasured
and must be reported as unmeasured — an assumed kappa is worse than a
missing one.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import area_estimation as ae  # noqa: E402
import labels as lb  # noqa: E402
import preprocess as pp  # noqa: E402

REF_DIR = REPO / "data" / "reference"
TABLE_DIR = REPO / "outputs" / "tables"
WEIGHTS = REF_DIR / "stratum_weights.json"

CLASS_ORDER = ["non_forest", "natural_forest", "plantation", "water"]
CLASS_CODE = {name: code for code, name in lb.CLASSES.items()}

# Reference change, derived from the pair rather than asked directly.
CHANGE_ORDER = ["no_loss", "forest_loss"]


def interpretation(district: str) -> pd.DataFrame | None:
    """The completed interpretation for a district, whichever author did it."""
    found = sorted(REF_DIR.glob(f"interpretation_{district}_author_*.csv"))
    frames = []
    for path in found:
        frame = pd.read_csv(path)
        if frame["class_t3"].notna().sum() == 0:
            continue
        frame["author"] = path.stem.split("author_")[-1]
        frames.append(frame[frame["class_t3"].notna()])
    if not frames:
        return None
    # One author per district in the reduced design. If both are present
    # the first is used and the second is reported separately, never
    # averaged — averaging two interpretations invents a third.
    if len(frames) > 1:
        print(f"  {district}: {len(frames)} authors present, using "
              f"'{frames[0]['author'].iloc[0]}' (kappa is a separate step)")
    return frames[0]


def sample_map(district: str, frame: pd.DataFrame, year: int) -> pd.Series:
    """Land-cover map class at each reference point."""
    aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
    labels = lb.build_labels(aoi, year, district).rename("map")
    features = [
        ee.Feature(ee.Geometry.Point([row.lon, row.lat]), {"pid": row.point_id})
        for row in frame.itertuples()
    ]
    sampled = labels.sampleRegions(
        collection=ee.FeatureCollection(features),
        scale=pp.NATIVE_SCALE, properties=["pid"], geometries=False).getInfo()
    got = {f["properties"]["pid"]: int(f["properties"]["map"])
           for f in sampled.get("features", [])}
    return frame["point_id"].map(got)


def sample_change(district: str, frame: pd.DataFrame, method: str) -> pd.Series | None:
    """Change-map class at each reference point, from the materialised asset."""
    asset = f"{pp.ASSET_ROOT}change_{method}_{district}"
    try:
        image = ee.Image(asset).select("change").rename("chg")
        image.bandNames().getInfo()
    except Exception:
        print(f"  {district}/{method}: asset not ready, skipped")
        return None
    features = [
        ee.Feature(ee.Geometry.Point([row.lon, row.lat]), {"pid": row.point_id})
        for row in frame.itertuples()
    ]
    sampled = image.sampleRegions(
        collection=ee.FeatureCollection(features),
        scale=pp.NATIVE_SCALE, properties=["pid"], geometries=False).getInfo()
    got = {f["properties"]["pid"]: int(f["properties"]["chg"])
           for f in sampled.get("features", [])}
    return frame["point_id"].map(got)


def confusion(reference: pd.Series, mapped: pd.Series, order: list[str]) -> pd.DataFrame:
    """Rows = map class, columns = reference class. Olofsson's orientation."""
    table = pd.DataFrame(0, index=order, columns=order, dtype=int)
    for m, r in zip(mapped, reference):
        if m in table.index and r in table.columns:
            table.loc[m, r] += 1
    return table


def weights_for(district: str, frame: pd.DataFrame,
                stratum_weights: dict) -> tuple[np.ndarray, np.ndarray]:
    """Stratum weights and achieved n_h, aligned.

    The weights come from the MAP — pixel counts per stratum — and not
    from the sample. That is what keeps the estimator valid after the
    sample was reduced: n_h changes, W_h does not.
    """
    strata = [s for s in stratum_weights if (frame["stratum"] == s).any()]
    w = np.array([stratum_weights[s]["weight"] for s in strata], dtype=float)
    n = np.array([(frame["stratum"] == s).sum() for s in strata], dtype=int)
    return w / w.sum(), n


def stratified_estimate(frame: pd.DataFrame, _unused,
                        stratum_weights: dict, order: list[str],
                        total_ha: float, reference_col: str) -> pd.DataFrame:
    """Olofsson adjusted area per class, from a stratified sample.

    The map here is the STRATIFICATION, which is how the design was drawn,
    so the estimator is applied stratum by stratum: within each stratum the
    sampled reference classes estimate that stratum's true composition, and
    the strata are combined by their map weights.
    """
    strata = [s for s in stratum_weights if (frame["stratum"] == s).any()]
    rows = []
    for cls in order:
        p = 0.0
        var = 0.0
        for s in strata:
            w = stratum_weights[s]["weight"]
            sub = frame[frame["stratum"] == s]
            n = len(sub)
            if n == 0:
                continue
            phat = float((sub[reference_col] == cls).mean())
            p += w * phat
            if n > 1:
                var += w ** 2 * phat * (1 - phat) / (n - 1)
        se = float(np.sqrt(var))
        rows.append({
            "class": cls,
            "proportion": p,
            "adjusted_area_ha": p * total_ha,
            "se_ha": se * total_ha,
            "ci95_ha": 1.96 * se * total_ha,
            "n_reference": int((frame[reference_col] == cls).sum()),
        })
    return pd.DataFrame(rows)


def per_class_accuracy(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cls in table.index:
        tp = table.loc[cls, cls]
        mapped = table.loc[cls].sum()
        ref = table[cls].sum()
        ua = tp / mapped if mapped else np.nan
        pa = tp / ref if ref else np.nan
        f1 = 2 * ua * pa / (ua + pa) if ua and pa and (ua + pa) else 0.0
        rows.append({"class": cls, "n_map": int(mapped), "n_reference": int(ref),
                     "users_acc": ua, "producers_acc": pa, "f1": f1})
    return pd.DataFrame(rows)


def run(district: str, year: int, stratum_weights: dict, online: bool = True) -> None:
    frame = interpretation(district)
    if frame is None:
        print(f"  {district}: no completed interpretation, skipped")
        return

    total_ha = sum(v["area_ha"] for v in stratum_weights.values())
    print(f"\n=== {district} — {len(frame)} interpreted points, "
          f"{total_ha:,.0f} ha ===")

    # The area estimate is computed FIRST and needs no map and no network.
    # Olofsson combines the reference composition of each stratum by that
    # stratum's map weight, so the map enters only through W_h, which is
    # already on disk. Accuracy needs the map at each point; area does not,
    # and separating them means an outage costs the confusion matrix rather
    # than the headline figure.
    area = stratified_estimate(frame, None, stratum_weights,
                               CLASS_ORDER, total_ha, "class_t3")
    print("\nOlofsson adjusted area at T3 (reference-based, 95% CI)")
    print(area.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    ref_change = np.where(
        (frame["class_t0"] == "natural_forest") & (frame["class_t3"] != "natural_forest"),
        "forest_loss", "no_loss")
    frame = frame.assign(ref_change=ref_change)
    loss = stratified_estimate(frame, None, stratum_weights, CHANGE_ORDER,
                               total_ha, "ref_change")
    row = loss[loss["class"] == "forest_loss"].iloc[0]
    print(f"\nforest loss {pp.EPOCHS['T0']}–{year}: "
          f"{row['adjusted_area_ha']:,.0f} ± {row['ci95_ha']:,.0f} ha "
          f"({row['proportion']:.2%}), from {int(row['n_reference'])} reference points")

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    area.to_csv(TABLE_DIR / f"adjusted_area_{district}_{year}.csv", index=False)
    loss.to_csv(TABLE_DIR / f"adjusted_loss_{district}_{year}.csv", index=False)

    if not online:
        print("  (offline: confusion matrix and change-map accuracy skipped)")
        return

    # --- land cover at T3 ------------------------------------------
    codes = sample_map(district, frame, year)
    frame = frame.assign(map_class=codes.map(lb.CLASSES))
    usable = frame[frame["map_class"].notna()]

    table = confusion(usable["class_t3"], usable["map_class"], CLASS_ORDER)
    acc = per_class_accuracy(table)
    overall = np.trace(table.to_numpy()) / max(table.to_numpy().sum(), 1)

    print("\nconfusion (rows = map, cols = reference)")
    print(table.to_string())
    print(f"\nunweighted overall agreement {overall:.3f}  "
          "— NOT the headline metric (rule 5)")
    print(acc.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    area = stratified_estimate(frame, frame["map_class"], stratum_weights,
                               CLASS_ORDER, total_ha, "class_t3")
    print("\nOlofsson adjusted area, T3")
    print(area.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(TABLE_DIR / f"confusion_{district}_{year}.csv")
    acc.to_csv(TABLE_DIR / f"accuracy_{district}_{year}.csv", index=False)
    area.to_csv(TABLE_DIR / f"adjusted_area_{district}_{year}.csv", index=False)

    # --- change, T0 -> T3 ------------------------------------------
    # Derived from the pair. Forest to anything-but-forest is loss; the
    # plantation case is deliberately counted as loss of NATURAL forest,
    # because a tea estate replacing hill forest is exactly the conversion
    # rule 7 exists to keep visible.
    ref_change = np.where(
        (frame["class_t0"] == "natural_forest") & (frame["class_t3"] != "natural_forest"),
        "forest_loss", "no_loss")
    frame = frame.assign(ref_change=ref_change)

    change_rows = []
    for method in ("pcc", "ndvi"):
        got = sample_change(district, frame, method)
        if got is None:
            continue
        # PCC codes 1 as forest_loss; NDVI differencing is binary change.
        mapped = np.where(got == 1, "forest_loss", "no_loss")
        sub = frame.assign(map_change=mapped)
        ct = confusion(sub["ref_change"], sub["map_change"], CHANGE_ORDER)
        ca = per_class_accuracy(ct)
        loss = ca[ca["class"] == "forest_loss"].iloc[0]
        change_rows.append({"district": district, "method": method,
                            "users_acc": loss["users_acc"],
                            "producers_acc": loss["producers_acc"],
                            "f1": loss["f1"],
                            "n_reference_loss": int(loss["n_reference"])})
        print(f"\nchange — {method.upper()}  (F1 on the CHANGE class is the "
              "headline, rule 5)")
        print(ct.to_string())
        print(ca.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    if change_rows:
        out = pd.DataFrame(change_rows)
        out.to_csv(TABLE_DIR / f"change_accuracy_{district}_{year}.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=pp.DISTRICTS)
    parser.add_argument("--year", type=int, default=pp.EPOCHS["T3"])
    parser.add_argument("--offline", action="store_true",
                        help="areas only — skips everything needing Earth Engine")
    args = parser.parse_args()

    if not WEIGHTS.exists():
        sys.exit(f"Missing {WEIGHTS.relative_to(REPO)} — stratum weights come "
                 "from the map and must be computed before any area estimate.")
    weights = json.loads(WEIGHTS.read_text())

    online = not args.offline
    if online:
        try:
            ee.Initialize(project=pp.PROJECT)
        except Exception as exc:
            print(f"Earth Engine unavailable ({str(exc)[:60]}) — areas only.")
            online = False

    print("Accuracy against the INDEPENDENT reference sample (rule 3).")
    print("These are the thesis numbers. Everything in src/models/ was scored")
    print("against training labels and is not comparable to them.\n")
    print("Single interpretation per district in the reduced design, so there")
    print("is no Cohen's kappa. Report that as unmeasured, never as assumed.")

    for district in ([args.district] if args.district else pp.DISTRICTS):
        run(district, args.year, weights[district], online)

    print("\nAreas are Olofsson-adjusted with 95% CIs (rule 4). Never report")
    print("the raw pixel counts from src/change_detection.py in their place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
