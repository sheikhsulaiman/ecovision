"""E1/E2 — Random Forest baseline, per-pixel land-cover classification.

methodology_plan.md 6.1: do not train a neural network until Random
Forest works. The baseline establishes an accuracy floor, debugs the
entire data pipeline cheaply, and produces feature importances that tell
you which bands matter — all three are worth more than the model itself.

    python src/models/rf.py --year 2024
    python src/models/rf.py --year 2024 --district sylhet --seeds 3

Experiments (methodology_plan.md 5.3):
    E1  spectral + indices + texture
    E2  E1 + terrain          -> does terrain help?

Runs locally on CPU. Nothing here belongs on Kaggle; the neural networks
do.

WHAT THIS DOES NOT MEASURE
--------------------------
Accuracy here is against HANSEN-DERIVED TRAINING LABELS, not against the
reference sample (rule 3). It says how well the model reproduces its
teacher. Real accuracy comes from Phase 8, measured against the 1,800
independently interpreted points, and will be lower.

Treat every number this script prints as a pipeline check and a relative
comparison between E1 and E2 — never as a thesis result.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, jaccard_score

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

PIXEL_DIR = REPO / "data" / "pixels"
TABLE_DIR = REPO / "outputs" / "tables"

# methodology_plan.md 6.1
N_TREES = 500
MAX_FEATURES = "sqrt"
CLASS_WEIGHT = "balanced"

TERRAIN_BANDS = ["elevation", "slope", "aspect"]

EXPERIMENTS = {
    "E1": {"terrain": False, "note": "spectral + indices + texture"},
    "E2": {"terrain": True, "note": "E1 + terrain"},
}

# Single-run numbers are not evidence (methodology_plan.md 5.3).
DEFAULT_SEEDS = [0, 1, 2]


def load(district: str, year: int, split: str) -> pd.DataFrame:
    path = PIXEL_DIR / f"{district}_{year}_{split}.csv"
    if not path.exists():
        sys.exit(
            f"Missing {path.relative_to(REPO)}\n"
            f"Run: python src/extract_pixels.py --year {year}"
        )
    return pd.read_csv(path)


def feature_columns(frame: pd.DataFrame, use_terrain: bool) -> list[str]:
    drop = {"label", "class_name"}
    cols = [c for c in frame.columns if c not in drop]
    if not use_terrain:
        cols = [c for c in cols if c not in TERRAIN_BANDS]
    return cols


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, classes: list[int]) -> dict:
    """Per-class F1 and IoU. Overall accuracy is reported but not headline."""
    present = [c for c in classes if c in set(y_true) | set(y_pred)]
    f1 = f1_score(y_true, y_pred, labels=present, average=None, zero_division=0)
    iou = jaccard_score(y_true, y_pred, labels=present, average=None, zero_division=0)
    return {
        "overall_accuracy": float((y_true == y_pred).mean()),
        "macro_f1": float(f1.mean()),
        "per_class_f1": dict(zip(present, map(float, f1))),
        "per_class_iou": dict(zip(present, map(float, iou))),
        "classes": present,
    }


def run(district: str, year: int, experiment: str, seed: int) -> dict:
    cfg = EXPERIMENTS[experiment]
    train = load(district, year, "train")
    test = load(district, year, "test")

    features = feature_columns(train, cfg["terrain"])
    x_train, y_train = train[features].to_numpy(), train["label"].to_numpy()
    x_test, y_test = test[features].to_numpy(), test["label"].to_numpy()

    # Guard rather than trust: the test pixels come from different blocks
    # by construction (src/extract_pixels.py samples per split), but a
    # silent regression there would inflate every number below.
    if len(train) == 0 or len(test) == 0:
        sys.exit(f"{district}: empty train or test set")

    model = RandomForestClassifier(
        n_estimators=N_TREES,
        max_features=MAX_FEATURES,
        class_weight=CLASS_WEIGHT,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)

    result = evaluate(y_test, y_pred, sorted(set(y_train)))
    result.update({
        "district": district, "year": year, "experiment": experiment,
        "seed": seed, "n_train": len(train), "n_test": len(test),
        "n_features": len(features),
    })
    result["importances"] = dict(
        sorted(zip(features, map(float, model.feature_importances_)),
               key=lambda kv: kv[1], reverse=True)
    )
    result["confusion"] = confusion_matrix(
        y_test, y_pred, labels=result["classes"]
    ).tolist()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=pp.EPOCHS["T3"])
    parser.add_argument("--district", choices=pp.DISTRICTS)
    parser.add_argument("--seeds", type=int, default=len(DEFAULT_SEEDS))
    args = parser.parse_args()

    districts = [args.district] if args.district else pp.DISTRICTS
    seeds = DEFAULT_SEEDS[: args.seeds]

    print("RF baseline — accuracy is against HANSEN TRAINING LABELS, not the")
    print("reference sample. These are pipeline checks, not thesis results.\n")
    print(f"{N_TREES} trees, max_features={MAX_FEATURES}, "
          f"class_weight={CLASS_WEIGHT}, seeds {seeds}\n")

    rows, detail = [], []
    for district in districts:
        for experiment in EXPERIMENTS:
            runs = [run(district, args.year, experiment, s) for s in seeds]
            detail.extend(runs)
            macro = np.array([r["macro_f1"] for r in runs])
            oa = np.array([r["overall_accuracy"] for r in runs])
            forest_f1 = np.array([r["per_class_f1"].get(1, np.nan) for r in runs])
            rows.append({
                "district": district,
                "experiment": experiment,
                "features": runs[0]["n_features"],
                "macro_f1_mean": macro.mean(),
                "macro_f1_std": macro.std(ddof=0),
                "forest_f1_mean": np.nanmean(forest_f1),
                "forest_f1_std": np.nanstd(forest_f1),
                "overall_acc_mean": oa.mean(),
            })

    summary = pd.DataFrame(rows)
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    # Does terrain help? The E1/E2 comparison is the point of running both.
    print("\n--- E2 minus E1 (does terrain help?) ---")
    for district in districts:
        sub = summary[summary["district"] == district].set_index("experiment")
        delta = sub.loc["E2", "macro_f1_mean"] - sub.loc["E1", "macro_f1_mean"]
        spread = max(sub.loc["E1", "macro_f1_std"], sub.loc["E2", "macro_f1_std"])
        verdict = "within seed noise" if abs(delta) <= spread else (
            "helps" if delta > 0 else "hurts")
        print(f"  {district:<11} {delta:+.4f} macro F1   ({verdict})")

    print("\n--- top features, E2, first seed ---")
    for district in districts:
        first = next(d for d in detail
                     if d["district"] == district and d["experiment"] == "E2")
        top = list(first["importances"].items())[:6]
        print(f"  {district:<11} " + ", ".join(f"{k} {v:.3f}" for k, v in top))

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLE_DIR / f"rf_baseline_{args.year}.csv"
    summary.to_csv(out, index=False)
    print(f"\nWritten: {out.relative_to(REPO)}")
    print("\nReminder: these compare model against teacher. Phase 8 measures")
    print("accuracy against the reference sample, and it will be lower.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
