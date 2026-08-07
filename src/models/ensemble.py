"""E7 — stacked Random Forest + U-Net ensemble.

    python src/models/ensemble.py --district sylhet --checkpoint outputs/checkpoints/unet_E3_sylhet_2024_s0.pt

Two models that fail differently are worth more than two that fail the
same way, and these do. Random Forest sees one pixel's 23 bands and no
context at all, so it is good on spectrally distinct classes and blind to
shape. U-Net sees a 3.84 km neighbourhood, so it gets boundaries and
patch geometry right and can be confidently wrong about an isolated
pixel. Stacking lets the meta-learner discover where each is reliable
instead of averaging that information away.

THE META-LEARNER IS FIT ON THE VALIDATION SPLIT
-----------------------------------------------
Not train, not test. Fitting it on train would mean fitting it to
predictions the base models have already memorised — the RF is near
perfect on its own training pixels, so the meta-learner would learn to
trust the RF unconditionally and then collapse on unseen ground. Fitting
it on test is straightforward leakage.

That leaves val, which is what val is for, and it costs nothing: the
blocks are spatially disjoint (rule 2), so val is genuinely unseen by
both base models.

WHAT THIS MEASURES
------------------
Hansen-derived training labels again, not the reference sample (rule 3).
E7 versus E1/E2/E3 here is a fair comparison because all four are scored
the same way on the same blocks. None of the four is a thesis accuracy
figure; Phase 8 is.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "src" / "models"))
import unet as un  # noqa: E402

PATCH_ROOT = REPO / "data" / "patches"
STATS = REPO / "outputs" / "tables" / "patch_norm_stats_2024.csv"
OUT_DIR = REPO / "outputs" / "tables"

IGNORE_INDEX = 255

# The RF is fed pixels, and a district's training split holds millions of
# them. Beyond a few hundred thousand the forest stops improving and
# starts costing minutes per fit, which matters when this runs three times
# per district.
MAX_RF_PIXELS = 400_000
MAX_META_PIXELS = 200_000

N_TREES = 300


def load_split(district: str, year: int, split: str,
               mean: np.ndarray, std: np.ndarray, keep: list[int],
               patch_root: Path) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Every patch in one split as (pixels, labels, per-patch arrays).

    The per-patch list is kept because the U-Net needs 2-D context; the
    flat pixel array is what the RF and the meta-learner consume. Both
    views index the same pixels in the same order.
    """
    directory = patch_root / f"{district}_{year}_{split}"
    files = sorted(directory.glob("*.npz"))
    if not files:
        sys.exit(f"no patches in {directory}")

    patches, pixels, labels = [], [], []
    for path in files:
        with np.load(path) as data:
            x = data["x"].astype(np.float32)
            y = data["y"].astype(np.int64)
        x = ((x - mean) / std)[..., keep]
        patches.append(x)
        pixels.append(x.reshape(-1, x.shape[-1]))
        labels.append(y.reshape(-1))
    return np.concatenate(pixels), np.concatenate(labels), patches


def unet_probabilities(model, patches: list[np.ndarray], device: str,
                       n_classes: int) -> np.ndarray:
    """Softmax probabilities per pixel, flattened to match load_split."""
    import torch

    model.eval()
    out = []
    with torch.no_grad():
        for start in range(0, len(patches), 8):
            batch = np.stack(patches[start:start + 8]).transpose(0, 3, 1, 2)
            tensor = torch.from_numpy(np.ascontiguousarray(batch)).to(device)
            probs = torch.softmax(model(tensor), dim=1).cpu().numpy()
            # (N, C, H, W) -> (N*H*W, C), matching the reshape in load_split.
            out.append(probs.transpose(0, 2, 3, 1).reshape(-1, n_classes))
    return np.concatenate(out)


def subsample(n: int, cap: int, seed: int) -> np.ndarray:
    if n <= cap:
        return np.arange(n)
    return np.random.default_rng(seed).choice(n, cap, replace=False)


def run(district: str, year: int, checkpoint: Path, seed: int, device: str,
        patch_root: Path, stats_path: Path) -> dict:
    import torch
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression

    blob = torch.load(checkpoint, map_location=device, weights_only=False)
    keep_names = blob["keep_names"]
    n_classes = blob["n_classes"]
    if blob["district"] != district:
        sys.exit(f"checkpoint is for {blob['district']}, not {district}")

    keep = [un.BAND_NAMES.index(b) for b in keep_names]
    mean, std = un.load_stats(district, keep_names, stats_path)

    model = un.build_model(len(keep), n_classes).to(device)
    model.load_state_dict(blob["state_dict"])

    data = {split: load_split(district, year, split, mean, std, keep, patch_root)
            for split in ("train", "val", "test")}

    # --- base model 1: RF on training pixels --------------------------
    x_train, y_train, _ = data["train"]
    valid = y_train != IGNORE_INDEX
    index = subsample(int(valid.sum()), MAX_RF_PIXELS, seed)
    forest = RandomForestClassifier(
        n_estimators=N_TREES, max_features="sqrt", class_weight="balanced",
        random_state=seed, n_jobs=-1)
    forest.fit(x_train[valid][index], y_train[valid][index])

    # RF may not have seen every class — plantation exists only in Sylhet,
    # and a district with no class 2 gives predict_proba three columns, not
    # four. Expanding to the full width keeps the meta-features aligned
    # across districts instead of silently shifting by one column.
    def rf_probs(x: np.ndarray) -> np.ndarray:
        partial = forest.predict_proba(x)
        full = np.zeros((len(x), n_classes), dtype=np.float32)
        for column, label in enumerate(forest.classes_):
            full[:, int(label)] = partial[:, column]
        return full

    # --- meta-learner, fit on VAL -------------------------------------
    x_val, y_val, patches_val = data["val"]
    valid_val = y_val != IGNORE_INDEX
    meta_x = np.hstack([rf_probs(x_val),
                        unet_probabilities(model, patches_val, device, n_classes)])
    index = subsample(int(valid_val.sum()), MAX_META_PIXELS, seed)
    # No multi_class argument: it was removed in scikit-learn 1.7, and
    # multinomial is the default for a solver that supports it anyway.
    meta = LogisticRegression(max_iter=1000)
    meta.fit(meta_x[valid_val][index], y_val[valid_val][index])

    # A class the meta-learner never sees, it can never output — no matter
    # how confidently a base model predicts it. In Sylhet the plantation
    # blocks are pinned to train and test, so val holds no class 2, and the
    # stack scored 0.0000 on plantation while the U-Net underneath it
    # scored 0.4520. Stacking discarded the one thing that was working.
    #
    # This is a property of where the meta-learner is fitted, not a flaw in
    # stacking, and it is silent unless something says so.
    absent = sorted(set(range(n_classes)) - set(int(c) for c in meta.classes_))
    if absent:
        print("  WARNING: classes absent from the validation split and therefore")
        print(f"  unpredictable by the stack: {[un.CLASSES[c] for c in absent]}")
        print("  Compare per-class F1 against the base models before reporting E7")
        print("  as best — on those classes the stack cannot win by construction.")

    # --- score all three on TEST --------------------------------------
    x_test, y_test, patches_test = data["test"]
    valid_test = y_test != IGNORE_INDEX
    truth = y_test[valid_test]

    rf_test = rf_probs(x_test)
    unet_test = unet_probabilities(model, patches_test, device, n_classes)
    stacked = meta.predict(np.hstack([rf_test, unet_test])[valid_test])

    classes = sorted(set(truth.tolist()))
    results = {
        "RF (patch pixels)": rf_test[valid_test].argmax(1),
        "U-Net": unet_test[valid_test].argmax(1),
        # Reported alongside the stack because if plain averaging matches
        # it, the meta-learner is adding complexity and nothing else, and
        # that is worth knowing rather than hiding.
        "soft vote": ((rf_test + unet_test) / 2)[valid_test].argmax(1),
        "E7 stacked": stacked,
    }

    from sklearn.metrics import f1_score, jaccard_score

    scored = {}
    for name, prediction in results.items():
        f1 = f1_score(truth, prediction, labels=classes, average=None, zero_division=0)
        iou = jaccard_score(truth, prediction, labels=classes, average=None, zero_division=0)
        scored[name] = {
            "macro_f1": float(f1.mean()),
            "mean_iou": float(iou.mean()),
            "per_class_f1": {un.CLASSES[c]: float(v) for c, v in zip(classes, f1)},
            "overall_accuracy": float((truth == prediction).mean()),
        }
    return {"district": district, "year": year, "seed": seed,
            "experiment": blob["experiment"], "n_test_pixels": int(valid_test.sum()),
            "scores": scored}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=un.DISTRICTS, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True,
                        help="from unet.py --checkpoint-dir")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--patch-root", type=Path, default=PATCH_ROOT)
    parser.add_argument("--stats", type=Path, default=STATS)
    args = parser.parse_args()

    if not args.checkpoint.exists():
        sys.exit(
            f"Missing {args.checkpoint}\n"
            "Train the U-Net with --checkpoint-dir first — E7 stacks a trained\n"
            "model, it does not train one."
        )

    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = run(args.district, args.year, args.checkpoint, args.seed, device,
                 args.patch_root, args.stats)

    print(f"\nE7 — {args.district} {args.year}, "
          f"{result['n_test_pixels']:,} test pixels\n")
    print(f"{'model':<20}{'macro F1':>10}{'mean IoU':>10}{'overall':>10}")
    for name, scores in result["scores"].items():
        print(f"{name:<20}{scores['macro_f1']:>10.4f}{scores['mean_iou']:>10.4f}"
              f"{scores['overall_accuracy']:>10.4f}")

    print("\nper-class F1")
    names = list(next(iter(result["scores"].values()))["per_class_f1"])
    print(f"{'model':<20}" + "".join(f"{n:>18}" for n in names))
    for name, scores in result["scores"].items():
        print(f"{name:<20}" + "".join(
            f"{scores['per_class_f1'][n]:>18.4f}" for n in names))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"ensemble_E7_{args.district}_{args.year}.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"\nWritten: {out.relative_to(REPO)}")
    print("\nAgainst Hansen training labels, not the reference sample (rule 3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
