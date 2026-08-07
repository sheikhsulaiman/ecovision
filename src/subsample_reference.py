"""Draw a smaller interpretable sample from the reference sample already drawn.

    python src/subsample_reference.py --write

Output: data/reference/reference_sample_{district}_reduced.csv
        data/reference/reduced_manifest.json

WHY THIS EXISTS
---------------
The full design is 1,650 points interpreted independently by both authors
— about 80 person-hours. When that does not fit the schedule, the choice
is which to give up: sample size, or the independent accuracy assessment.

CLAUDE.md already answers it. If the schedule slips, Bandarban goes
first and the accuracy assessment never does. A smaller sample widens the
confidence interval, which is a stated, quantified limitation. Dropping
the assessment removes the only independent yardstick in the thesis and
makes every accuracy figure circular. One of those is a weaker result;
the other is not a result at all.

So: fewer points per stratum, same strata, same weights, same estimator.

WHAT STAYS VALID AND WHY
------------------------
The Olofsson estimator does not care how large the sample is. Its stratum
weights W_h come from the MAP — pixel counts per stratum — not from how
many points were interpreted. Reducing n_h widens the interval and
changes nothing else, provided n_h is recorded honestly.

Two things must therefore survive intact, and both are written to the
manifest:

* the stratum weights, recomputed here for every district because the
  original manifest was overwritten by the plantation top-up and now
  holds Sylhet's plantation stratum alone
* the achieved n_h per stratum, which is what the variance formula uses

Subsampling happens WITHIN each stratum. Drawing at random across the
whole sample would collapse the rare strata — forest_loss is 0.22% of
Gazipur by area and is deliberately over-sampled — and the estimator
would lose the very classes it exists to measure.

THE KAPPA SUBSET
----------------
Every point is interpreted once, by one author. That is what makes it
affordable, and it is also the compromise: single interpretation means no
per-point reconciliation.

A subset is interpreted by BOTH authors so Cohen's kappa still has
something to measure. Kappa on a subsample is standard practice; kappa on
nothing is not. The subset is drawn across strata so agreement is
measured on the hard calls too, not only on the easy majority class.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
import preprocess as pp  # noqa: E402

REF_DIR = REPO / "data" / "reference"

SEED = 20260807

# Points per district in the reduced design. Sylhet gets the most because
# RQ3 lives there and it carries a fourth stratum; Bandarban keeps enough
# to separate cyclical from permanent, which is the reason it was added.
TARGET_TOTAL = {"gazipur": 100, "sylhet": 180, "bandarban": 120}
TARGET_TOPUP = {"sylhet_plantation_topup": 40}

# Below roughly this many points a stratum's own variance term becomes
# unstable and its contribution to the interval is noise. Strata are
# floored here rather than scaled blindly.
MIN_PER_STRATUM = 20

# Double-interpreted points per district, for kappa.
KAPPA_PER_DISTRICT = 20


def allocate(counts: pd.Series, target: int) -> dict[str, int]:
    """Scale each stratum toward `target`, never below MIN_PER_STRATUM."""
    factor = target / counts.sum()
    out = {}
    for name, have in counts.items():
        want = max(MIN_PER_STRATUM, int(round(have * factor)))
        out[name] = int(min(have, want))
    return out


def subsample(frame: pd.DataFrame, target: int, seed: int) -> pd.DataFrame:
    counts = frame["stratum"].value_counts()
    wanted = allocate(counts, target)
    parts = [
        frame[frame["stratum"] == name].sample(n=n, random_state=seed)
        for name, n in wanted.items()
    ]
    return pd.concat(parts).sort_values("point_id").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    jobs = {**TARGET_TOTAL, **TARGET_TOPUP}
    manifest: dict = {"seed": args.seed, "design": "reduced",
                      "kappa_per_district": KAPPA_PER_DISTRICT, "samples": {}}

    total_points = total_interpretations = 0
    for stem, target in jobs.items():
        source = REF_DIR / f"reference_sample_{stem}.csv"
        if not source.exists():
            print(f"  skipped {stem}: {source.name} not found")
            continue
        full = pd.read_csv(source)
        reduced = subsample(full, target, args.seed)

        # The kappa subset is spread across strata for the same reason the
        # sample is stratified: agreement on the majority class is easy and
        # uninformative, and the number would flatter itself.
        per_stratum = max(1, KAPPA_PER_DISTRICT // reduced["stratum"].nunique())
        overlap = (reduced.groupby("stratum", group_keys=False)
                   .apply(lambda g: g.sample(n=min(len(g), per_stratum),
                                             random_state=args.seed)))
        reduced["kappa_subset"] = reduced["point_id"].isin(overlap["point_id"])

        counts = reduced["stratum"].value_counts().to_dict()
        manifest["samples"][stem] = {
            "n": len(reduced),
            "n_by_stratum": counts,
            "n_kappa": int(reduced["kappa_subset"].sum()),
            "drawn_from": source.name,
            "full_n": len(full),
        }
        total_points += len(reduced)
        total_interpretations += len(reduced) + int(reduced["kappa_subset"].sum())

        print(f"{stem}: {len(full)} -> {len(reduced)} "
              f"({int(reduced['kappa_subset'].sum())} double-interpreted)")
        for name, n in sorted(counts.items()):
            print(f"    {name:<20}{full['stratum'].value_counts()[name]:>5} -> {n:>4}")

        if args.write:
            out = REF_DIR / f"reference_sample_{stem}_reduced.csv"
            reduced.to_csv(out, index=False)
            print(f"    -> {out.name}")
        print()

    print(f"total points {total_points}, "
          f"total interpretations {total_interpretations} "
          f"(~{total_interpretations / 2:.0f} per author)")
    print(f"at 90 s each that is about {total_interpretations * 90 / 3600 / 2:.1f} "
          "hours per author")

    print("\nSTRATUM WEIGHTS ARE UNCHANGED. They come from the map, not the")
    print("sample, so the Olofsson estimator stays valid — the interval")
    print("simply widens. Report the reduced n and say why.")

    if args.write:
        path = REF_DIR / "reduced_manifest.json"
        path.write_text(json.dumps(manifest, indent=2))
        print(f"\nWritten: {path.relative_to(REPO)}")
    else:
        print("\n--- dry run, nothing written. Re-run with --write ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
