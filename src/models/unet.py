"""E3 / E4 — U-Net land-cover segmentation.

E3  full 23-band stack
E4  E3 minus the 3 GLCM texture bands  ->  does texture solve the tea problem?

    python src/models/unet.py --smoke-test          # local, CPU, 2 patches
    python src/models/unet.py --experiment E3 --district sylhet --seed 0

E4 is a FLAG, not a separate script. An ablation that lives in a forked
copy drifts from its baseline the first time either is edited, and the
comparison silently stops being an ablation.

=====================================================================
KAGGLE SETUP
=====================================================================
    Accelerator : GPU T4 x2   (free tier; ~30 GPU-hours/week)
    Internet    : ON          (pip install + pretrained encoder weights)
    Input       : /kaggle/input/ecovision-patches/{district}_{year}_{split}/
                  /kaggle/input/ecovision-patches/patch_norm_stats_{year}.csv
    Output      : /kaggle/working/   -- copy anything you need OUT before
                  the session ends. Kaggle keeps no local disk between
                  sessions, so a checkpoint written mid-notebook and not
                  saved to Output or a Dataset is gone.

    !pip install -q segmentation-models-pytorch

Upload data/patches/ and outputs/tables/patch_norm_stats_2024.csv as a
Kaggle Dataset. Set PATCH_ROOT and STATS_PATH below, or pass --patch-root.
=====================================================================

WHAT THIS SCRIPT REFUSES TO DO
------------------------------
* Train on nodata. Patch labels use 255 for pixels outside the district
  (src/extract_patches.py); the loss ignores them. Folding them into
  class 0 would teach the model that the outside of the district is
  non-forest.
* Normalise with statistics it computed itself. Statistics are LOADED
  from patch_norm_stats, which src/patch_stats.py computes from the
  training split alone. Recomputing here over whatever happens to be in
  memory is how test information leaks in without anything erroring.
* Report overall accuracy as the headline (rule 5).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
except ImportError:  # pragma: no cover
    sys.exit("torch not installed. Locally: pip install torch --index-url "
             "https://download.pytorch.org/whl/cpu")

REPO = Path(__file__).resolve().parents[2]

# Overridden by --patch-root on Kaggle.
PATCH_ROOT = REPO / "data" / "patches"
STATS_PATH = REPO / "outputs" / "tables" / "patch_norm_stats_2024.csv"
OUT_DIR = REPO / "outputs" / "tables"

DISTRICTS = ["gazipur", "sylhet", "bandarban"]
CLASSES = {0: "non_forest", 1: "natural_forest", 2: "plantation", 3: "water"}
IGNORE_INDEX = 255

BAND_NAMES = [
    "blue", "green", "red", "nir", "swir1", "swir2", "thermal",
    "ndvi", "evi", "savi", "ndwi", "ndmi", "ndbi", "nbr",
    "brightness", "greenness", "wetness",
    "glcm_contrast", "glcm_entropy", "glcm_homogeneity",
    "elevation", "slope", "aspect",
]
TEXTURE_BANDS = ["glcm_contrast", "glcm_entropy", "glcm_homogeneity"]

EXPERIMENTS = {
    "E3": {"drop_bands": [], "note": "full 23-band stack"},
    "E4": {"drop_bands": TEXTURE_BANDS, "note": "no texture — tea ablation"},
}

# methodology_plan.md 6.2
ENCODER = "resnet34"
ENCODER_WEIGHTS = "imagenet"
LR = 1e-4
WEIGHT_DECAY = 1e-4
EPOCHS = 100
BATCH_SIZE = 16
PATIENCE = 15
DICE_WEIGHT = 0.5


# --- data ------------------------------------------------------------


class PatchDataset(Dataset):
    """Patches from disk, normalised with training-split statistics.

    Augmentation is flips and 90 degree rotations ONLY. Colour jitter
    destroys radiometric meaning: these are calibrated surface
    reflectance values, and shifting them makes the model learn from
    physically impossible spectra.
    """

    def __init__(self, directory: Path, mean: np.ndarray, std: np.ndarray,
                 keep: list[int], augment: bool = False):
        self.files = sorted(Path(directory).glob("*.npz"))
        self.mean, self.std, self.keep, self.augment = mean, std, keep, augment
        if not self.files:
            raise FileNotFoundError(f"no patches in {directory}")

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, i: int):
        with np.load(self.files[i]) as data:
            x = data["x"].astype(np.float32)
            y = data["y"].astype(np.int64)

        x = (x - self.mean) / self.std
        x = x[..., self.keep]

        if self.augment:
            k = np.random.randint(4)
            if k:
                x, y = np.rot90(x, k, (0, 1)), np.rot90(y, k, (0, 1))
            if np.random.rand() < 0.5:
                x, y = x[::-1], y[::-1]
            if np.random.rand() < 0.5:
                x, y = x[:, ::-1], y[:, ::-1]

        x = np.ascontiguousarray(x.transpose(2, 0, 1))
        return torch.from_numpy(x), torch.from_numpy(np.ascontiguousarray(y))


def load_stats(district: str, keep_names: list[str], path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Per-band mean/std, from the TRAINING split, for this district."""
    import pandas as pd

    if not path.exists():
        sys.exit(f"Missing {path}. Run: python src/patch_stats.py")
    frame = pd.read_csv(path)
    sub = frame[frame["district"] == district].set_index("band")
    missing = [b for b in BAND_NAMES if b not in sub.index]
    if missing:
        sys.exit(f"stats file missing bands: {missing}")
    mean = sub.loc[BAND_NAMES, "mean"].to_numpy(np.float32)
    std = sub.loc[BAND_NAMES, "std"].to_numpy(np.float32)
    # A zero-variance band would divide to inf and poison every gradient.
    std = np.where(std <= 0, 1.0, std)
    return mean, std


# --- model and loss --------------------------------------------------


def build_model(in_channels: int, n_classes: int):
    """U-Net with an ImageNet encoder adapted to N input channels.

    smp handles the first-conv surgery: it repeats and rescales the
    pretrained RGB weights across the extra channels, which preserves the
    pretrained statistics far better than random initialisation.
    """
    import segmentation_models_pytorch as smp

    return smp.Unet(
        encoder_name=ENCODER,
        encoder_weights=ENCODER_WEIGHTS,
        in_channels=in_channels,
        classes=n_classes,
    )


class DiceCELoss(nn.Module):
    """Dice + cross-entropy, both ignoring nodata.

    Cross-entropy alone handles the imbalance poorly: at 0.22% forest loss
    in Gazipur, predicting the majority class everywhere is already a very
    low loss. Dice is computed on class overlap and does not care how
    large the background is.
    """

    def __init__(self, n_classes: int, dice_weight: float = DICE_WEIGHT):
        super().__init__()
        self.ce = nn.CrossEntropyLoss(ignore_index=IGNORE_INDEX)
        self.n_classes, self.dice_weight = n_classes, dice_weight

    def forward(self, logits, target):
        valid = target != IGNORE_INDEX

        # A batch with no valid pixels at all makes CrossEntropyLoss average
        # over zero elements, which is NaN — and one NaN destroys every
        # weight on the backward pass. Returning ce here would propagate it.
        #
        # Patches below 70% valid are already dropped at extraction, so this
        # is defensive; but "should not happen" is exactly the condition
        # that shows up forty minutes into a GPU session. The multiply keeps
        # the tensor attached to the graph so the optimiser step is a no-op
        # rather than an error.
        if not valid.any():
            return logits.sum() * 0.0

        ce = self.ce(logits, target)
        probs = torch.softmax(logits, dim=1)
        safe = torch.where(valid, target, torch.zeros_like(target))
        onehot = torch.zeros_like(probs).scatter_(1, safe.unsqueeze(1), 1.0)
        mask = valid.unsqueeze(1).float()
        probs, onehot = probs * mask, onehot * mask

        dims = (0, 2, 3)
        inter = (probs * onehot).sum(dims)
        denom = probs.sum(dims) + onehot.sum(dims)
        dice = 1.0 - ((2 * inter + 1.0) / (denom + 1.0)).mean()
        return (1 - self.dice_weight) * ce + self.dice_weight * dice


# --- metrics ---------------------------------------------------------


@torch.no_grad()
def evaluate(model, loader, device, n_classes: int) -> dict:
    """Per-class IoU and F1. Nodata excluded from every count."""
    model.eval()
    inter = np.zeros(n_classes)
    union = np.zeros(n_classes)
    tp = np.zeros(n_classes)
    pred_n = np.zeros(n_classes)
    true_n = np.zeros(n_classes)

    for x, y in loader:
        x, y = x.to(device), y.to(device)
        pred = model(x).argmax(1)
        valid = y != IGNORE_INDEX
        for c in range(n_classes):
            p = (pred == c) & valid
            t = (y == c) & valid
            inter[c] += (p & t).sum().item()
            union[c] += (p | t).sum().item()
            tp[c] += (p & t).sum().item()
            pred_n[c] += p.sum().item()
            true_n[c] += t.sum().item()

    with np.errstate(divide="ignore", invalid="ignore"):
        iou = np.where(union > 0, inter / union, np.nan)
        precision = np.where(pred_n > 0, tp / pred_n, 0.0)
        recall = np.where(true_n > 0, tp / true_n, 0.0)
        f1 = np.where((precision + recall) > 0,
                      2 * precision * recall / (precision + recall), 0.0)
    present = true_n > 0
    return {
        "per_class_iou": {CLASSES[c]: float(iou[c]) for c in range(n_classes)},
        "per_class_f1": {CLASSES[c]: float(f1[c]) for c in range(n_classes)},
        "macro_f1": float(np.nanmean(f1[present])) if present.any() else float("nan"),
        "mean_iou": float(np.nanmean(iou[present])) if present.any() else float("nan"),
        "forest_f1": float(f1[1]),
        "forest_iou": float(iou[1]),
    }


# --- training --------------------------------------------------------


def train(district: str, experiment: str, seed: int, year: int,
          patch_root: Path, stats_path: Path, epochs: int, device: str) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)

    keep_names = [b for b in BAND_NAMES if b not in EXPERIMENTS[experiment]["drop_bands"]]
    keep = [BAND_NAMES.index(b) for b in keep_names]
    mean, std = load_stats(district, keep_names, stats_path)

    loaders = {}
    for split in ("train", "val", "test"):
        ds = PatchDataset(patch_root / f"{district}_{year}_{split}",
                          mean, std, keep, augment=(split == "train"))
        loaders[split] = DataLoader(
            ds, batch_size=BATCH_SIZE, shuffle=(split == "train"),
            num_workers=0, drop_last=False,
        )

    n_classes = len(CLASSES)
    model = build_model(len(keep), n_classes).to(device)
    criterion = DiceCELoss(n_classes)
    optimiser = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)

    best, best_state, since = -np.inf, None, 0
    for epoch in range(epochs):
        model.train()
        running = 0.0
        for x, y in loaders["train"]:
            x, y = x.to(device), y.to(device)
            optimiser.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimiser.step()
            running += loss.item()
        schedule.step()

        val = evaluate(model, loaders["val"], device, n_classes)
        if val["mean_iou"] > best:
            best, since = val["mean_iou"], 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            since += 1
            if since >= PATIENCE:
                print(f"      early stop at epoch {epoch} (patience {PATIENCE})")
                break
        if epoch % 10 == 0:
            print(f"      epoch {epoch:>3}  loss {running / max(len(loaders['train']), 1):.4f}"
                  f"  val mIoU {val['mean_iou']:.4f}")

    if best_state is not None:
        model.load_state_dict(best_state)
    test = evaluate(model, loaders["test"], device, n_classes)
    test.update({"district": district, "experiment": experiment, "seed": seed,
                 "year": year, "n_bands": len(keep), "best_val_miou": best})
    return test


def smoke_test() -> int:
    """Prove the whole path runs, on real patches, on CPU.

    Not a result. It checks that shapes line up, the loss is finite, the
    ignore index is respected and a gradient actually flows — the things
    that otherwise fail forty minutes into a GPU session.
    """
    print("smoke test: CPU, real patches, 2 steps\n")

    district = next(
        (d for d in DISTRICTS
         if (PATCH_ROOT / f"{d}_2024_train").exists()
         and any((PATCH_ROOT / f"{d}_2024_train").glob("*.npz"))),
        None,
    )
    if district is None:
        sys.exit("no patches found — run src/extract_patches.py first")
    print(f"  district: {district}")

    files = sorted((PATCH_ROOT / f"{district}_2024_train").glob("*.npz"))[:2]
    xs, ys = [], []
    for f in files:
        with np.load(f) as d:
            xs.append(d["x"].astype(np.float32))
            ys.append(d["y"].astype(np.int64))
    x = np.stack(xs)
    y = np.stack(ys)
    print(f"  x {x.shape}  y {y.shape}")
    print(f"  label values: {sorted(np.unique(y).tolist())}")
    assert np.isfinite(x).all(), "non-finite values in features"

    mean, std = x.reshape(-1, x.shape[-1]).mean(0), x.reshape(-1, x.shape[-1]).std(0)
    std = np.where(std <= 0, 1.0, std)
    print("  (smoke test normalises from these 2 patches only — the real run")
    print("   loads training-split statistics from patch_norm_stats)")
    xn = ((x - mean) / std).transpose(0, 3, 1, 2)

    for experiment, cfg in EXPERIMENTS.items():
        keep = [i for i, b in enumerate(BAND_NAMES) if b not in cfg["drop_bands"]]
        xt = torch.from_numpy(np.ascontiguousarray(xn[:, keep]))
        yt = torch.from_numpy(y)
        model = build_model(len(keep), len(CLASSES))
        criterion = DiceCELoss(len(CLASSES))

        logits = model(xt)
        loss = criterion(logits, yt)
        loss.backward()
        grad = sum(p.grad.abs().sum().item() for p in model.parameters() if p.grad is not None)

        print(f"  {experiment} ({len(keep)} bands, {cfg['note']}):")
        print(f"     logits {tuple(logits.shape)}  loss {loss.item():.4f}"
              f"  finite={np.isfinite(loss.item())}  grad_sum {grad:.1f}")
        assert np.isfinite(loss.item()), f"{experiment}: non-finite loss"
        assert grad > 0, f"{experiment}: no gradient flowed"

    # The ignore index must actually be ignored, not merely tolerated.
    all_ignored = torch.full_like(torch.from_numpy(y), IGNORE_INDEX)
    loss_ignored = DiceCELoss(len(CLASSES))(model(xt), all_ignored)
    print(f"\n  all-nodata batch -> loss {loss_ignored.item():.4f} "
          f"(finite={np.isfinite(loss_ignored.item())})")
    assert np.isfinite(loss_ignored.item()), "nodata-only batch produced non-finite loss"

    print("\nsmoke test PASSED — safe to hand to Kaggle")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--experiment", choices=list(EXPERIMENTS), default="E3")
    parser.add_argument("--district", choices=DISTRICTS)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--seeds", type=int, default=3, help="run seeds 0..n-1")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--patch-root", type=Path, default=PATCH_ROOT)
    parser.add_argument("--stats", type=Path, default=STATS_PATH)
    args = parser.parse_args()

    if args.smoke_test:
        return smoke_test()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("WARNING: no GPU. Full training on CPU is not practical —")
        print("this is meant for Kaggle (GPU T4 x2). Continuing anyway.\n")

    districts = [args.district] if args.district else DISTRICTS
    seeds = [args.seed] if args.seed is not None else list(range(args.seeds))

    results = []
    for district in districts:
        for seed in seeds:
            print(f"  {district} / {args.experiment} / seed {seed}")
            results.append(train(district, args.experiment, seed, args.year,
                                 args.patch_root, args.stats, args.epochs, device))

    import pandas as pd

    frame = pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)}
                          for r in results])
    print("\n" + frame.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"unet_{args.experiment}_{args.year}.csv"
    frame.to_csv(out, index=False)
    with (OUT_DIR / f"unet_{args.experiment}_{args.year}_perclass.json").open("w") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nWritten: {out.name}")
    print("\nAccuracy here is against Hansen-derived TRAINING labels, not the")
    print("reference sample. Phase 8 measures the real thing (rule 3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
