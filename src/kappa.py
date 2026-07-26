"""Inter-interpreter agreement on the reference sample.

Gate 4 requires Cohen's kappa between the two interpreters, reported in
the thesis. Both authors interpret every point independently — 600 per
district, 1,800 each — and kappa is computed on the full sample.

The comparison is a join on point_id, so it works on whatever both
authors have completed so far. Running it mid-way is useful: a kappa
that is already low after 200 points means the class definitions are
ambiguous at the boundaries, and it is far cheaper to fix that then than
after 1,800.

    python src/kappa.py
    python src/kappa.py --district sylhet --field class_t3

Gate 4 threshold is kappa >= 0.75. Below that, do not proceed to accuracy
assessment — reconcile the disagreements first and record what was
changed and why. A low kappa is information, not an obstacle to be
rounded away: it usually means the class definitions are ambiguous at the
boundaries, and that ambiguity will reappear as classification error.

WHAT KAPPA IS AND IS NOT
------------------------
It measures whether two trained people, looking at the same location
independently, assign the same class. It says nothing about whether
either of them is right. It is evidence that the reference data is
reproducible, which is what makes it usable as ground truth.

Pontius & Millones (2011) argue kappa is uninformative for MAP accuracy,
and this project accepts that (see docs/methodology_plan.md 8.1 — kappa
is not reported as a map accuracy metric). Its use HERE is different and
uncontroversial: agreement between raters is the purpose kappa was
designed for.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
REF_DIR = REPO / "data" / "reference"
TABLE_DIR = REPO / "outputs" / "tables"

DISTRICTS = ["gazipur", "sylhet", "bandarban"]
# Must match AUTHORS in src/reference_sample.py — these are the filenames
# that script writes.
AUTHOR_A, AUTHOR_B = "author_a", "author_b"

GATE_4_THRESHOLD = 0.75

# Interpretation fields that carry a class and can be compared.
COMPARABLE_FIELDS = ["class_t0", "class_t3"]


def cohens_kappa(a: pd.Series, b: pd.Series) -> tuple[float, float, int]:
    """Cohen's kappa with its standard error, for nominal classes.

    Returns (kappa, se, n). The SE is the large-sample approximation for
    the null case; it is adequate for reporting an interval alongside
    kappa and should be described as approximate.
    """
    classes = sorted(set(a) | set(b))
    index = {c: i for i, c in enumerate(classes)}
    k = len(classes)
    matrix = np.zeros((k, k))
    for x, y in zip(a, b):
        matrix[index[x], index[y]] += 1

    n = matrix.sum()
    if n == 0:
        return float("nan"), float("nan"), 0

    observed = np.trace(matrix) / n
    row, col = matrix.sum(axis=1) / n, matrix.sum(axis=0) / n
    expected = float((row * col).sum())

    if np.isclose(expected, 1.0):
        # Both raters used a single class for everything. Agreement is
        # perfect and kappa is undefined rather than 1.0 — chance agreement
        # is already total, so there is no room to do better than chance.
        return float("nan"), float("nan"), int(n)

    kappa = (observed - expected) / (1 - expected)
    se = float(np.sqrt(observed * (1 - observed) / (n * (1 - expected) ** 2)))
    return float(kappa), se, int(n)


def per_class_agreement(a: pd.Series, b: pd.Series) -> pd.DataFrame:
    """Where the two interpreters diverge, class by class."""
    rows = []
    for cls in sorted(set(a) | set(b)):
        both = ((a == cls) & (b == cls)).sum()
        either = ((a == cls) | (b == cls)).sum()
        rows.append({
            "class": cls,
            "author_a_n": int((a == cls).sum()),
            "author_b_n": int((b == cls).sum()),
            "agreed": int(both),
            "jaccard": float(both / either) if either else float("nan"),
        })
    return pd.DataFrame(rows)


def load_pair(district: str, field: str) -> pd.DataFrame | None:
    paths = {
        author: REF_DIR / f"interpretation_{district}_{author}.csv"
        for author in (AUTHOR_A, AUTHOR_B)
    }
    missing = [str(p.relative_to(REPO)) for p in paths.values() if not p.exists()]
    if missing:
        print(f"  {district}: missing {', '.join(missing)}")
        return None

    a = pd.read_csv(paths[AUTHOR_A])
    b = pd.read_csv(paths[AUTHOR_B])
    merged = a.merge(b, on="point_id", suffixes=("_a", "_b"))
    merged = merged[
        merged[f"{field}_a"].notna() & merged[f"{field}_b"].notna()
    ]
    merged = merged[
        (merged[f"{field}_a"].astype(str).str.strip() != "")
        & (merged[f"{field}_b"].astype(str).str.strip() != "")
    ]
    if merged.empty:
        print(f"  {district}: no completed interpretations for {field} yet")
        return None
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--district", choices=DISTRICTS)
    parser.add_argument("--field", choices=COMPARABLE_FIELDS, default="class_t3")
    args = parser.parse_args()

    districts = [args.district] if args.district else DISTRICTS
    results, any_data = [], False

    print(f"Cohen's kappa on {args.field}, Gate 4 threshold {GATE_4_THRESHOLD}\n")

    for district in districts:
        merged = load_pair(district, args.field)
        if merged is None:
            continue
        any_data = True
        a, b = merged[f"{args.field}_a"], merged[f"{args.field}_b"]
        kappa, se, n = cohens_kappa(a, b)
        raw = float((a == b).mean())

        verdict = "PASS" if kappa >= GATE_4_THRESHOLD else "BELOW GATE 4"
        print(f"=== {district} ===")
        print(f"  compared points     {n}")
        print(f"  raw agreement       {raw:.3f}")
        print(f"  Cohen's kappa       {kappa:.3f} +/- {1.96 * se:.3f}   {verdict}")
        print(per_class_agreement(a, b).to_string(index=False))
        print()

        results.append({"district": district, "field": args.field, "n": n,
                        "raw_agreement": raw, "kappa": kappa, "kappa_se": se,
                        "passes_gate_4": kappa >= GATE_4_THRESHOLD})

    if not any_data:
        print("No interpretations to compare yet.")
        print("Draw the sample with src/reference_sample.py --draw, then both")
        print("authors fill their interpretation CSVs independently. Do not")
        print("look at each other's files before this script is run — the")
        print("independence is the whole point of the number.")
        return 1

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    out = TABLE_DIR / f"kappa_{args.field}.csv"
    pd.DataFrame(results).to_csv(out, index=False)
    print(f"Written: {out.relative_to(REPO)}")

    failed = [r["district"] for r in results if not r["passes_gate_4"]]
    if failed:
        print(f"\nBELOW GATE 4 in: {', '.join(failed)}")
        print("Reconcile jointly before proceeding. Log what changed and why —")
        print("the reconciliation record is part of the audit trail, and")
        print("silently overwriting the disagreements destroys the evidence")
        print("that the sample was independently interpreted at all.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
