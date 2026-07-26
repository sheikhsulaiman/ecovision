"""Stratified area and accuracy estimation, after Olofsson et al. (2014).

Olofsson, P., Foody, G.M., Herold, M., Stehman, S.V., Woodcock, C.E.,
Wulder, M.A. (2014). "Good practices for estimating area and assessing
accuracy of land change." Remote Sensing of Environment 148, 42-57.

WHY THIS EXISTS (CLAUDE.md rule 4): a classified map miscounts area
because it misclassifies pixels. Counting map pixels therefore gives a
biased area, and the bias does not shrink as the map gets bigger. The
design-based estimator here corrects the count using the reference
sample's error matrix and, crucially, produces a confidence interval.
An area figure without a CI is not a reportable result.

The map is used only to define the STRATA. The reference sample is the
only source of truth about what is actually on the ground. Never pass
training labels into this module (CLAUDE.md rule 3) — doing so measures
the model against itself and the resulting accuracy is meaningless.

    python src/area_estimation.py --self-test

Notation follows the paper:
    q          number of classes / strata
    W_h        proportion of total mapped area in stratum h
    n_h        reference sample units drawn from stratum h
    n_hj       units mapped as h whose reference class is j
    p_hj       estimated area proportion, cell (h, j)
    p_.j       estimated area proportion of reference class j
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

Z_95 = 1.959963984540054  # two-sided normal quantile for a 95% interval


@dataclass
class AreaEstimate:
    """Per-class results. Areas are in the same unit as `total_area`."""

    classes: list[str]
    area: np.ndarray            # adjusted area, per reference class
    area_se: np.ndarray         # standard error of the adjusted area
    area_ci95: np.ndarray       # half-width of the 95% CI
    proportion: np.ndarray      # estimated area proportion, p_.j
    proportion_se: np.ndarray
    mapped_area: np.ndarray     # naive pixel-count area, for comparison
    users_accuracy: np.ndarray
    users_accuracy_se: np.ndarray
    producers_accuracy: np.ndarray
    producers_accuracy_se: np.ndarray
    overall_accuracy: float
    overall_accuracy_se: float
    f1: np.ndarray
    unit: str = "ha"
    _matrix: np.ndarray = field(default=None, repr=False)

    def to_frame(self) -> pd.DataFrame:
        """Per-class table, ready for the results chapter."""
        return pd.DataFrame(
            {
                "class": self.classes,
                f"mapped_area_{self.unit}": self.mapped_area,
                f"adjusted_area_{self.unit}": self.area,
                f"se_{self.unit}": self.area_se,
                f"ci95_{self.unit}": self.area_ci95,
                "users_acc": self.users_accuracy,
                "users_acc_se": self.users_accuracy_se,
                "producers_acc": self.producers_accuracy,
                "producers_acc_se": self.producers_accuracy_se,
                "f1": self.f1,
            }
        )

    def report(self) -> str:
        """Human-readable summary in the form the thesis must use."""
        lines = [
            f"Overall accuracy: {self.overall_accuracy:.4f} "
            f"+/- {Z_95 * self.overall_accuracy_se:.4f} (95% CI)",
            "",
            "NOTE: overall accuracy is NOT the headline metric for change "
            "detection (CLAUDE.md rule 5).",
            "The change class is a small minority of pixels; report F1 on the "
            "change class instead.",
            "",
        ]
        for i, name in enumerate(self.classes):
            lines.append(
                f"{name}: {self.area[i]:,.0f} +/- {self.area_ci95[i]:,.0f} "
                f"{self.unit} (95% CI)"
            )
            lines.append(
                f"    mapped (pixel count): {self.mapped_area[i]:,.0f} {self.unit}"
                f"   |  bias: {self.area[i] - self.mapped_area[i]:+,.0f} {self.unit}"
            )
            lines.append(
                f"    UA {self.users_accuracy[i]:.3f}   "
                f"PA {self.producers_accuracy[i]:.3f}   "
                f"F1 {self.f1[i]:.3f}"
            )
        return "\n".join(lines)


def _validate(matrix: np.ndarray, weights: np.ndarray) -> None:
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"error matrix must be square, got {matrix.shape}")
    if matrix.shape[0] != weights.shape[0]:
        raise ValueError(
            f"weights length {weights.shape[0]} != matrix size {matrix.shape[0]}"
        )
    if np.any(matrix < 0):
        raise ValueError("error matrix contains negative counts")
    if not np.isclose(weights.sum(), 1.0, atol=1e-6):
        raise ValueError(
            f"stratum weights must sum to 1, got {weights.sum():.6f}. "
            "They are area proportions of the MAP, not of the sample."
        )
    n_h = matrix.sum(axis=1)
    if np.any(n_h < 2):
        raise ValueError(
            f"every stratum needs >= 2 sample units (variance divides by n_h - 1); "
            f"got {n_h.tolist()}"
        )


def estimate(
    matrix: np.ndarray | list[list[float]],
    weights: np.ndarray | list[float],
    total_area: float,
    classes: list[str] | None = None,
    unit: str = "ha",
) -> AreaEstimate:
    """Run the Olofsson stratified estimator.

    Args:
        matrix: q x q error matrix of SAMPLE COUNTS. Rows are map class
            (the stratum), columns are reference class. matrix[h][j] is
            the number of sample units mapped as h whose reference
            interpretation is j. Counts, not proportions.
        weights: W_h, the proportion of total mapped area in each stratum.
            Must sum to 1. Derived from the map, not from the sample.
        total_area: total area of the study region, in `unit`.
        classes: class names, in matrix order.
        unit: area unit, for labelling only.
    """
    matrix = np.asarray(matrix, dtype=float)
    weights = np.asarray(weights, dtype=float)
    _validate(matrix, weights)

    q = matrix.shape[0]
    if classes is None:
        classes = [f"class_{i}" for i in range(q)]

    n_h = matrix.sum(axis=1)                      # sample size per stratum

    # Estimated area proportions, paper eq. 4: p_hj = W_h * n_hj / n_h
    p = weights[:, None] * matrix / n_h[:, None]

    p_dot_j = p.sum(axis=0)                       # per reference class
    area = total_area * p_dot_j
    mapped_area = total_area * weights

    # SE of the estimated area proportion, paper eq. 10.
    ratio = matrix / n_h[:, None]
    var_p = ((weights[:, None] ** 2) * ratio * (1 - ratio) / (n_h[:, None] - 1)).sum(axis=0)
    p_se = np.sqrt(var_p)
    area_se = total_area * p_se

    # User's accuracy, paper eq. 2 — a within-stratum proportion, so its
    # variance is the ordinary binomial one (eq. 6). Independent of W_h.
    diag = np.diag(matrix)
    ua = diag / n_h
    ua_se = np.sqrt(ua * (1 - ua) / (n_h - 1))

    # Producer's accuracy, paper eq. 3 and its variance, eq. 7. Unlike UA,
    # PA depends on every stratum that could have omitted the class, so the
    # variance carries a term for each off-diagonal row.
    n_total_j = (weights / n_h)[:, None] * matrix    # N_i. / n_i. * n_ij
    n_dot_j = n_total_j.sum(axis=0)
    pa = np.divide(
        weights * ua, n_dot_j, out=np.zeros(q), where=n_dot_j > 0
    )

    pa_se = np.zeros(q)
    for j in range(q):
        if n_dot_j[j] <= 0 or n_h[j] < 2:
            continue
        first = (
            weights[j] ** 2
            * (1 - pa[j]) ** 2
            * ua[j]
            * (1 - ua[j])
            / (n_h[j] - 1)
        )
        others = 0.0
        for i in range(q):
            if i == j:
                continue
            r = matrix[i, j] / n_h[i]
            others += weights[i] ** 2 * r * (1 - r) / (n_h[i] - 1)
        var_pa = (first + pa[j] ** 2 * others) / (n_dot_j[j] ** 2)
        pa_se[j] = np.sqrt(max(var_pa, 0.0))

    # Overall accuracy, paper eq. 1, and its variance, eq. 5.
    oa = float((weights * ua).sum())
    oa_var = float((weights**2 * ua * (1 - ua) / (n_h - 1)).sum())

    with np.errstate(divide="ignore", invalid="ignore"):
        f1 = np.where((ua + pa) > 0, 2 * ua * pa / (ua + pa), 0.0)

    return AreaEstimate(
        classes=list(classes),
        area=area,
        area_se=area_se,
        area_ci95=Z_95 * area_se,
        proportion=p_dot_j,
        proportion_se=p_se,
        mapped_area=mapped_area,
        users_accuracy=ua,
        users_accuracy_se=ua_se,
        producers_accuracy=pa,
        producers_accuracy_se=pa_se,
        overall_accuracy=oa,
        overall_accuracy_se=float(np.sqrt(oa_var)),
        f1=f1,
        unit=unit,
        _matrix=matrix,
    )


def required_sample_size(
    weights: np.ndarray | list[float],
    target_se: float,
    expected_ua: np.ndarray | list[float],
) -> float:
    """Total sample size for a target SE on overall accuracy (paper eq. 13).

    Use this to justify the reference-sample size in Phase 4.2 rather than
    asserting a round number. Note it sizes the sample for OVERALL accuracy;
    rare change classes need their own allocation on top, which is why the
    plan over-samples them deliberately.
    """
    weights = np.asarray(weights, dtype=float)
    ua = np.asarray(expected_ua, dtype=float)
    numerator = (weights * np.sqrt(ua * (1 - ua))).sum()
    return float((numerator / target_se) ** 2)


# --- self-test --------------------------------------------------------


def _self_test() -> int:
    """Internal-consistency checks, plus the paper's worked example.

    IMPORTANT — READ BEFORE TRUSTING THIS: the worked-example inputs below
    were reproduced from Olofsson et al. (2014) section 4.3 / Table 8 from
    memory, and have NOT been checked against the published paper by the
    person who wrote this file. Open the paper, verify the error matrix and
    the stratum areas match, and verify the computed area and CI for the
    deforestation class match the values the paper reports.

    The internal-consistency checks below are genuine and do pass. They
    prove the estimator is self-coherent, NOT that it matches the paper.
    """
    print("--- internal consistency ---")

    rng = np.random.default_rng(0)
    q = 4
    counts = rng.integers(5, 60, size=(q, q)).astype(float)
    counts += np.diag(rng.integers(100, 300, size=q))
    w = rng.random(q)
    w /= w.sum()
    est = estimate(counts, w, total_area=1_000_000.0, unit="ha")

    checks = [
        ("area proportions sum to 1", np.isclose(est.proportion.sum(), 1.0)),
        ("adjusted areas sum to total", np.isclose(est.area.sum(), 1_000_000.0)),
        ("mapped areas sum to total", np.isclose(est.mapped_area.sum(), 1_000_000.0)),
        ("all standard errors finite", np.all(np.isfinite(est.area_se))),
        ("all standard errors non-negative", np.all(est.area_se >= 0)),
        ("UA within [0, 1]", np.all((est.users_accuracy >= 0) & (est.users_accuracy <= 1))),
        ("PA within [0, 1]", np.all((est.producers_accuracy >= 0) & (est.producers_accuracy <= 1))),
        ("OA within [0, 1]", 0.0 <= est.overall_accuracy <= 1.0),
        (
            "OA equals weighted mean of UA",
            np.isclose(est.overall_accuracy, (w * est.users_accuracy).sum()),
        ),
    ]

    # A perfect map must give back exactly the mapped areas, with zero SE.
    perfect = np.diag([100.0] * q)
    perfect_est = estimate(perfect, w, total_area=1_000_000.0)
    checks.append(("perfect map -> adjusted == mapped",
                   np.allclose(perfect_est.area, perfect_est.mapped_area)))
    checks.append(("perfect map -> zero SE", np.allclose(perfect_est.area_se, 0.0)))
    checks.append(("perfect map -> OA == 1", np.isclose(perfect_est.overall_accuracy, 1.0)))

    # Input validation must actually reject bad input.
    for label, bad in [
        ("non-square matrix rejected", lambda: estimate(np.ones((2, 3)), [0.5, 0.5], 1.0)),
        ("weights not summing to 1 rejected", lambda: estimate(np.eye(2) * 5, [0.3, 0.3], 1.0)),
        ("singleton stratum rejected", lambda: estimate([[1, 0], [0, 5]], [0.5, 0.5], 1.0)),
    ]:
        try:
            bad()
            checks.append((label, False))
        except ValueError:
            checks.append((label, True))

    failed = 0
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
        failed += not ok

    print("\n--- Olofsson et al. (2014) worked example ---")
    print("INPUTS REPRODUCED FROM MEMORY - VERIFY AGAINST THE PAPER.")
    print("Do not cite these numbers until you have checked Table 8.\n")

    # Map classes: 1 deforestation, 2 forest gain, 3 stable forest,
    # 4 stable non-forest. Rows = map, columns = reference.
    example_matrix = np.array(
        [
            [66, 0, 5, 4],
            [0, 55, 8, 12],
            [1, 0, 153, 11],
            [2, 1, 9, 313],
        ],
        dtype=float,
    )
    example_pixels = np.array([200_000, 150_000, 3_200_000, 6_450_000], dtype=float)
    example_weights = example_pixels / example_pixels.sum()
    # Landsat pixel = 30 m x 30 m = 0.09 ha
    total_ha = example_pixels.sum() * 0.09

    example = estimate(
        example_matrix,
        example_weights,
        total_area=total_ha,
        classes=["deforestation", "forest gain", "stable forest", "stable non-forest"],
        unit="ha",
    )
    print(example.report())
    print()
    print(example.to_frame().to_string(index=False, float_format=lambda v: f"{v:,.4f}"))

    print(f"\n{len(checks) - failed}/{len(checks)} consistency checks passed")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run consistency checks")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
