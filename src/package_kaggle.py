"""Bundle everything the Kaggle notebook needs into one uploadable zip.

    python src/package_kaggle.py --year 2024

Output: outputs/kaggle/ecovision-patches.zip

Upload it as a Kaggle Dataset named `ecovision-patches`; the notebook in
notebooks/kaggle_train.py expects it mounted at
/kaggle/input/ecovision-patches/.

WHY A ZIP AND NOT A LIVE PULL
-----------------------------
CLAUDE.md, compute environment: Kaggle notebooks have no persistent disk
and their internet access is off by default. Fetching patches from Earth
Engine inside the notebook would mean re-authenticating GEE every session
and re-downloading 900-odd patches each time a session resets. The
bundle is built once here and mounted read-only there.

WHAT GOES IN
------------
The patches, the normalisation statistics, and the model source — nothing
else. In particular data/reference/ is never bundled: the training run
must not be able to see the reference sample even by accident (rule 3),
and the simplest way to guarantee that is for it not to be there.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

PATCH_ROOT = REPO / "data" / "patches"
OUT_DIR = REPO / "outputs" / "kaggle"

# Source files the notebook imports. Kept explicit rather than globbing
# src/, so nothing that touches the reference sample can drift into the
# bundle later without someone editing this list.
SOURCE_FILES = ["models/unet.py", "models/ensemble.py"]

FORBIDDEN = ("data/reference", "interpret_cache")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=pp.EPOCHS["T3"])
    parser.add_argument("--district", choices=pp.DISTRICTS,
                        help="bundle one district only — for re-running after a "
                             "split change without re-uploading the other two")
    args = parser.parse_args()

    stats = REPO / "outputs" / "tables" / f"patch_norm_stats_{args.year}.csv"
    if not stats.exists():
        sys.exit(
            f"Missing {stats.relative_to(REPO)}\n"
            f"Run: python src/patch_stats.py --year {args.year}\n"
            "Normalisation statistics must come from the TRAIN split only — "
            "computing them over all patches leaks test-set statistics into "
            "training and quietly inflates every score."
        )

    pattern = (f"{args.district}_{args.year}_*" if args.district
               else f"*_{args.year}_*")
    members: list[tuple[Path, str]] = []
    for directory in sorted(PATCH_ROOT.glob(pattern)):
        for patch in sorted(directory.glob("*.npz")):
            members.append((patch, f"patches/{directory.name}/{patch.name}"))
    if not members:
        sys.exit(f"No patches for {args.year} under {PATCH_ROOT.relative_to(REPO)}")

    members.append((stats, f"tables/{stats.name}"))
    for relative in SOURCE_FILES:
        path = REPO / "src" / relative
        if path.exists():
            members.append((path, f"src/{relative}"))

    for path, arcname in members:
        if any(f in path.as_posix() for f in FORBIDDEN):
            sys.exit(f"Refusing to bundle {arcname} — rule 3")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"-{args.district}" if args.district else ""
    out = OUT_DIR / f"ecovision-patches{suffix}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, arcname in members:
            archive.write(path, arcname)

    # The code goes out a SECOND time, on its own, in a bundle small enough
    # to re-upload in seconds. Code changes and 840 MB of patches do not,
    # and pairing them means every one-line fix costs a full re-upload over
    # a slow connection. The notebook prefers this copy when it is mounted.
    source_out = OUT_DIR / "ecovision-src.zip"
    with zipfile.ZipFile(source_out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in SOURCE_FILES:
            path = REPO / "src" / relative
            if path.exists():
                archive.write(path, f"src/{relative}")

    by_split: dict[str, int] = {}
    for _, arcname in members:
        if arcname.startswith("patches/"):
            by_split[arcname.split("/")[1]] = by_split.get(arcname.split("/")[1], 0) + 1
    for name in sorted(by_split):
        print(f"  {name:<24}{by_split[name]:>5} patches")

    print(f"\nWritten: {out.relative_to(REPO)}  ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"Written: {source_out.relative_to(REPO)}  "
          f"({source_out.stat().st_size / 1e3:.0f} KB)")
    print("\nUpload BOTH as Kaggle Datasets, named `ecovision-patches` and")
    print("`ecovision-src`, and add both to the notebook. After a code change")
    print("only ecovision-src needs re-uploading — it takes seconds, and the")
    print("notebook loads it in preference to the copy inside the big bundle.")
    print("\nThen run notebooks/kaggle_train.py with GPU T4 x2 and internet ON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
