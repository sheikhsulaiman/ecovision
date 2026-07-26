"""Derive local cross-sensor harmonisation coefficients from our own data.

Roy et al. (2016) coefficients were derived on Landsat Collection 1 and,
measured on near-coincident pairs over Gazipur, do not reduce total
cross-sensor bias on the Collection 2 Level-2 data this project uses
(docs/phase3_harmonisation.md). This script fits replacements from
near-coincident scene pairs over the actual study areas.

    python src/derive_harmonisation.py
    python src/derive_harmonisation.py --samples 800 --max-pairs 8

Outputs
    outputs/tables/harmonisation_coefficients.csv   thesis table
    outputs/tables/harmonisation_validation.csv     held-out comparison
    outputs/tables/harmonisation_local.json         consumed by preprocess.py

TWO CHAINS, NOT ONE
-------------------
Everything is brought into the OLI reference, because T3 (2024) is OLI/L9
and the endpoint should not be the thing that gets adjusted.

    ETM+ -> OLI   fitted directly from L7/L8 pairs (2013-2021 overlap)
    TM   -> OLI   fitted as TM -> ETM+ -> OLI, composed

TM -> OLI cannot be fitted directly: Landsat 5 returned its last usable
data in 2011 and Landsat 8 launched in 2013, so TM and OLI never operated
concurrently and no near-coincident TM/OLI pair exists anywhere on Earth.
The composition through ETM+ is the only available route, and it must be
stated as such in Chapter 4 — the TM chain carries the error of two
regressions, not one.

VALIDATION SPLIT
----------------
Pairs are split into fit and held-out sets BY PAIR, never by pixel.
Pixels within one scene pair are spatially autocorrelated and share an
atmospheric state; splitting by pixel would put near-identical
observations on both sides and report an improvement that is not real.
This is the same failure that makes random patch splits invalid in
Phase 5, appearing one phase early.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import ee
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

TABLE_DIR = REPO / "outputs" / "tables"

# Sensor pairs to fit: (target, source, target_family, source_family, window)
CHAINS = [
    ("LC08", "LE07", "2013-04-01", "2021-12-31"),  # ETM+ -> OLI
    ("LE07", "LT05", "1999-07-01", "2011-11-30"),  # TM   -> ETM+
]

MAX_DAYS = 8          # one WRS-2 repeat cycle
MAX_CLOUD = 20        # stricter than the audit; residual cloud is the
                      # dominant confounder in a paired comparison
HOLDOUT_FRACTION = 0.30
RANDOM_SEED = 42


def scene_list(sensor: str, aoi: ee.Geometry, start: str, end: str) -> list[dict]:
    col = (
        ee.ImageCollection(pp.SENSORS[sensor]["id"])
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", MAX_CLOUD))
    )
    out = []
    for item in col.toList(col.size()).getInfo():
        props = item["properties"]
        out.append({
            "id": item["id"],
            "time": datetime.fromtimestamp(props["system:time_start"] / 1000, tz=timezone.utc),
            "path": props.get("WRS_PATH"),
            "row": props.get("WRS_ROW"),
        })
    return out


def find_pairs(target: list[dict], source: list[dict], max_days: int) -> list[tuple[dict, dict]]:
    """Same path/row, within max_days. Returns (target, source), argument order."""
    pairs = []
    for t in target:
        for s in source:
            if t["path"] != s["path"] or t["row"] != s["row"]:
                continue
            if abs((t["time"] - s["time"]).days) <= max_days:
                pairs.append((t, s))
    return pairs


def prepared(scene_id: str, sensor: str) -> ee.Image:
    """Masked, scaled, band-renamed. No harmonisation — that is what we fit."""
    return pp.rename_bands(pp.scale_l2(pp.mask_l2(ee.Image(scene_id))), sensor)


def sample_pair(
    target_id: str, target_sensor: str,
    source_id: str, source_sensor: str,
    aoi: ee.Geometry, n: int,
) -> pd.DataFrame | None:
    """Per-pixel paired reflectance where BOTH scenes are cloud-free."""
    tgt = prepared(target_id, target_sensor).select(
        pp.COMMON_BANDS, [f"y_{b}" for b in pp.COMMON_BANDS]
    )
    src = prepared(source_id, source_sensor).select(
        pp.COMMON_BANDS, [f"x_{b}" for b in pp.COMMON_BANDS]
    )
    # sample() drops any pixel masked in either image, so the intersection
    # of the two cloud masks is enforced automatically.
    try:
        feats = (
            tgt.addBands(src)
            .sample(region=aoi, scale=pp.NATIVE_SCALE, numPixels=n,
                    geometries=False, tileScale=4)
            .getInfo()
        )
    except Exception as exc:
        print(f"    sample failed: {str(exc)[:90]}")
        return None
    rows = [f["properties"] for f in feats.get("features", [])]
    if not rows:
        return None
    return pd.DataFrame(rows)


def fit_ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def fit_rma(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Reduced major axis: symmetric in x and y.

    Preferred over OLS for sensor-to-sensor calibration because both
    variables carry measurement error. OLS assumes x is error-free, which
    is false when x is another satellite's reflectance, and the resulting
    slope is attenuated toward zero.
    """
    sign = np.sign(np.cov(x, y)[0, 1])
    slope = float(sign * np.std(y, ddof=1) / np.std(x, ddof=1))
    return slope, float(np.mean(y) - slope * np.mean(x))


def mae(pred: np.ndarray, truth: np.ndarray) -> float:
    return float(np.mean(np.abs(pred - truth)))


def run_chain(
    target: str, source: str, start: str, end: str,
    samples: int, max_pairs: int,
) -> dict | None:
    print(f"\n=== {source} -> {target}  ({start[:4]}-{end[:4]}) ===")

    collected: list[pd.DataFrame] = []
    for district in pp.DISTRICTS:
        aoi = ee.FeatureCollection(f"{pp.ASSET_ROOT}{district}_shp").geometry()
        tgt_scenes = scene_list(target, aoi, start, end)
        src_scenes = scene_list(source, aoi, start, end)
        pairs = find_pairs(tgt_scenes, src_scenes, MAX_DAYS)[:max_pairs]
        print(f"  {district}: {len(tgt_scenes)} {target}, {len(src_scenes)} {source}, "
              f"{len(pairs)} pairs")
        for i, (t, s) in enumerate(pairs):
            df = sample_pair(t["id"], target, s["id"], source, aoi, samples)
            if df is None or len(df) < 50:
                continue
            df["pair"] = f"{district}_p{t['path']}r{t['row']}_{t['time']:%Y%m%d}_{i}"
            collected.append(df)

    if not collected:
        print("  no usable pairs")
        return None

    data = pd.concat(collected, ignore_index=True).dropna()
    pair_ids = sorted(data["pair"].unique())
    rng = np.random.default_rng(RANDOM_SEED)
    rng.shuffle(pair_ids)
    n_hold = max(1, int(len(pair_ids) * HOLDOUT_FRACTION))
    holdout_ids = set(pair_ids[:n_hold])

    fit_set = data[~data["pair"].isin(holdout_ids)]
    hold_set = data[data["pair"].isin(holdout_ids)]
    print(f"  {len(data):,} paired pixels from {len(pair_ids)} pairs "
          f"({len(pair_ids) - n_hold} fit / {n_hold} held out)")

    coefficients, validation = {}, []
    for band in pp.COMMON_BANDS:
        xf, yf = fit_set[f"x_{band}"].to_numpy(), fit_set[f"y_{band}"].to_numpy()
        xh, yh = hold_set[f"x_{band}"].to_numpy(), hold_set[f"y_{band}"].to_numpy()
        if len(xf) < 50 or len(xh) < 20:
            continue

        ols_s, ols_i = fit_ols(xf, yf)
        rma_s, rma_i = fit_rma(xf, yf)
        roy_s, roy_i = pp.ROY_ETM_TO_OLI[band]

        scores = {
            "raw": mae(xh, yh),
            "roy": mae(roy_s * xh + roy_i, yh),
            "local_ols": mae(ols_s * xh + ols_i, yh),
            "local_rma": mae(rma_s * xh + rma_i, yh),
        }
        best = min(scores, key=scores.get)
        coefficients[band] = {
            "ols": [ols_s, ols_i],
            "rma": [rma_s, rma_i],
            "best": best,
            "n_fit": int(len(xf)),
        }
        validation.append({"band": band, **scores, "best": best,
                           "gain_vs_raw_pct": (scores[best] - scores["raw"]) / scores["raw"] * 100})

    frame = pd.DataFrame(validation)
    print()
    print(frame.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    return {"coefficients": coefficients, "validation": frame,
            "source": source, "target": target}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=600, help="pixels per pair")
    parser.add_argument("--max-pairs", type=int, default=6, help="pairs per district")
    args = parser.parse_args()

    try:
        ee.Initialize(project=pp.PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}")

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    results, all_validation, all_coeffs = [], [], {}

    for target, source, start, end in CHAINS:
        res = run_chain(target, source, start, end, args.samples, args.max_pairs)
        if res is None:
            continue
        results.append(res)
        key = f"{res['source']}_to_{res['target']}"
        all_coeffs[key] = res["coefficients"]
        v = res["validation"].copy()
        v.insert(0, "chain", key)
        all_validation.append(v)

    if not results:
        print("\nNo chain could be fitted. Nothing written.")
        return 1

    validation = pd.concat(all_validation, ignore_index=True)
    validation.to_csv(TABLE_DIR / "harmonisation_validation.csv", index=False)

    rows = []
    for chain, bands in all_coeffs.items():
        for band, c in bands.items():
            rows.append({
                "chain": chain, "band": band,
                "ols_slope": c["ols"][0], "ols_intercept": c["ols"][1],
                "rma_slope": c["rma"][0], "rma_intercept": c["rma"][1],
                "selected": c["best"], "n_fit_pixels": c["n_fit"],
            })
    pd.DataFrame(rows).to_csv(TABLE_DIR / "harmonisation_coefficients.csv", index=False)

    with (TABLE_DIR / "harmonisation_local.json").open("w", encoding="utf-8") as fh:
        json.dump(all_coeffs, fh, indent=2)

    print("\n=== summary, held-out pairs ===")
    for chain in validation["chain"].unique():
        sub = validation[validation["chain"] == chain]
        wins = (sub["best"].str.startswith("local")).sum()
        print(f"{chain}: local coefficients best on {wins}/{len(sub)} bands")
        print(f"  mean MAE  raw {sub['raw'].mean():.5f}  roy {sub['roy'].mean():.5f}  "
              f"local_ols {sub['local_ols'].mean():.5f}  local_rma {sub['local_rma'].mean():.5f}")

    print(f"\nWritten to {TABLE_DIR.relative_to(REPO)}/")
    print("Nothing in preprocess.py changes until these are wired in "
          "deliberately — review the validation table first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
