# %% [markdown]
# # EcoVision — E3/E4 U-Net training on Kaggle
#
# **Kaggle setup**
#
# | setting | value |
# |---|---|
# | Accelerator | **GPU T4 x2** (free tier) |
# | Internet | **ON** — needed for the pip install and the ImageNet encoder weights |
# | Input | Dataset `ecovision-patches`, mounted at `/kaggle/input/ecovision-patches/` |
# | Output | `/kaggle/working/` — **download before the session ends, nothing persists** |
#
# Build the input dataset locally first:
#
# ```
# python src/patch_stats.py --year 2024
# python src/package_kaggle.py --year 2024
# ```
#
# then upload `outputs/kaggle/ecovision-patches.zip` as a Kaggle Dataset.
#
# ---
#
# **What this measures.** Accuracy here is against Hansen-derived training
# labels, not the reference sample (CLAUDE.md rule 3). These are pipeline
# checks and E3-vs-E4 comparisons. Real accuracy is Phase 8, against the
# independently interpreted points, and it will be lower.

# %%
# --- cell 1: environment -------------------------------------------------
!pip install -q segmentation-models-pytorch==0.3.4

import os
import shutil
import subprocess
import sys
from pathlib import Path

import torch

INPUT = Path("/kaggle/input/ecovision-patches")
WORK = Path("/kaggle/working")

print("torch", torch.__version__, "| cuda", torch.cuda.is_available(),
      "|", torch.cuda.device_count(), "device(s)")
if not torch.cuda.is_available():
    print("\nNo GPU. Settings -> Accelerator -> GPU T4 x2, then restart.")

# %%
# --- cell 2: stage the bundle -------------------------------------------
# /kaggle/input is read-only, and the training script writes alongside its
# inputs, so everything is copied to /kaggle/working first. This costs a
# minute and saves a confusing permission error twenty minutes in.
for name in ("patches", "tables", "src"):
    source = INPUT / name
    target = WORK / name
    if source.exists() and not target.exists():
        shutil.copytree(source, target)

sys.path.insert(0, str(WORK / "src"))

splits = sorted(p.name for p in (WORK / "patches").iterdir() if p.is_dir())
for split in splits:
    print(f"  {split:<24}{len(list((WORK / 'patches' / split).glob('*.npz'))):>5}")

# %%
# --- cell 3: smoke test on synthetic tensors -----------------------------
# Runs in seconds and catches the failures that otherwise appear after an
# hour of training: shape mismatch, all-nodata batch producing NaN loss,
# missing normalisation statistics.
subprocess.run([sys.executable, str(WORK / "src/models/unet.py"), "--smoke-test"],
               check=True)

# %%
# --- cell 4: E3 and E4 ---------------------------------------------------
# One seed, not three. Three seeds is the right answer and the reason is in
# methodology_plan.md 5.3 — single runs are not evidence. If the schedule
# allows only one, say so in the results chapter rather than presenting a
# single run as if it were a mean.
YEAR = 2024
SEEDS = 1
EPOCHS = 60

DISTRICTS = ["gazipur", "sylhet", "bandarban"]

# E4 (with GLCM texture) is the RQ3 experiment and only means anything in
# Sylhet, where the tea-versus-forest confusion lives.
JOBS = [("E3", d) for d in DISTRICTS] + [("E4", "sylhet")]

for experiment, district in JOBS:
    print(f"\n{'=' * 60}\n{experiment}  {district}\n{'=' * 60}", flush=True)
    subprocess.run([
        sys.executable, str(WORK / "src/models/unet.py"),
        "--experiment", experiment,
        "--district", district,
        "--year", str(YEAR),
        "--seeds", str(SEEDS),
        "--epochs", str(EPOCHS),
        "--patch-root", str(WORK / "patches"),
        "--stats", str(WORK / f"tables/patch_norm_stats_{YEAR}.csv"),
    ], check=False)

# %%
# --- cell 5: collect results --------------------------------------------
# Nothing in /kaggle/working survives the session. Download this zip before
# closing the notebook, unzip into outputs/tables/, and commit.
results = WORK / "results"
results.mkdir(exist_ok=True)
for pattern in ("*.csv", "*.json", "*.pt"):
    for path in (WORK / "outputs" / "tables").glob(pattern) if (
            WORK / "outputs" / "tables").exists() else []:
        shutil.copy(path, results / path.name)

shutil.make_archive(str(WORK / "ecovision-results"), "zip", results)
print("Download /kaggle/working/ecovision-results.zip before the session ends.")
for path in sorted(results.iterdir()):
    print(f"  {path.name}  ({path.stat().st_size / 1e3:.0f} KB)")
