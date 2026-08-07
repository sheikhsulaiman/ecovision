# Phase 8 — accuracy against the reference sample

Run 2026-08-07 on 400 interpreted points: Gazipur 100, Sylhet 180,
Bandarban 120. Reduced design, **one interpreter per district**, so there
is no Cohen's kappa and none may be assumed.

These are the only accuracy figures in the thesis. Everything in
`src/models/` is scored against Hansen-derived training labels — model
against teacher — and is not comparable to anything here.

---

## 1. Forest extent 2024, Olofsson-adjusted (RQ1)

| district | natural forest | non-forest | water |
|---|---|---|---|
| Gazipur | 45,530 ± 25,723 ha | 134,252 ha | — |
| Sylhet | 41,681 ± 23,420 ha | 254,993 ha | 27,947 ha |
| Bandarban | 417,542 ± 31,747 ha | 12,950 ha | 28,918 ha |

## 2. Forest loss 1990–2024 — every interval includes zero

| district | adjusted loss | reference change points |
|---|---|---|
| Gazipur | 443 ± 849 ha | 2 |
| Sylhet | 5,547 ± 10,755 ha | 7 |
| Bandarban | 70 ± 96 ha | 2 |

**No statistically significant forest loss is detectable at the 95% level
in any district.** That is a consequence of sample size meeting a rare
class, and it is the quantified cost of reducing the sample from 1,650 to
440. It must be reported as it stands, not narrowed by choosing a
friendlier interval.

The over-sampled `forest_loss` stratum existed precisely to avoid this.
It did not fail: Gazipur drew 40 points from that stratum and the
interpreter judged only 2 of them to be genuine forest→non-forest, which
is a statement about **Hansen commission error**, not about the sample.
That finding is independently reportable and probably more interesting
than the loss figure would have been.

## 3. Land-cover map accuracy at T3

| district | overall | non-forest F1 | natural forest F1 |
|---|---|---|---|
| Gazipur | 0.570 | 0.661 | 0.411 |
| Sylhet | 0.565 | 0.651 | 0.388 |
| Bandarban | **0.233** | 0.062 | 0.370 |

Forest F1 near 0.40 in Gazipur and Sylhet is modest but coherent, and it
is what an honest assessment of a 30 m Hansen-derived map against
independent interpretation tends to look like.

## 4. Change detection (RQ4) — F1 on the change class

| district | PCC | NDVI differencing | n reference loss |
|---|---|---|---|
| Gazipur | 0.000 | 0.000 | 2 |
| Sylhet | 0.000 | 0.148 | 7 |
| Bandarban | 0.154 | 0.167 | 2 |

**NDVI differencing equals or beats PCC in all three districts.** That is
the direction the literature predicts and the direction this thesis
argued for in advance: PCC accumulates error from both dates, so two maps
at ~0.55 overall agreement cannot produce a reliable change map between
them.

The caveat is severe and must travel with the number: with 2, 7 and 2
reference change points, these F1 values have enormous sampling
uncertainty. They support a **ranking**, weakly. They do not support a
claim about magnitude.

---

## Three findings that are about definitions, not models

### Water F1 is 0.000 everywhere, and the map is not wrong

The map's water class is JRC occurrence ≥ 50%, i.e. **permanent** water.
Interpreters called seasonal river channels and haor margins water at the
observation date, which the class definition asks for. Sylhet's reference
found 6 water points and Bandarban's 8; the map has none at those
locations.

This is a definitional mismatch between a permanence-based map class and
a date-based reference class, not a detection failure. Either reconcile
the definitions or report water as unassessed — but do not present 0.000
as a measure of the map's ability to find water.

### Bandarban's map and reference disagree almost completely

The map calls 93 of 120 points non-forest; the reference calls 108 of 120
natural forest. User's accuracy for non-forest is 0.032 and overall
agreement is 0.233 — worse than chance for a two-class problem.

Two readings, and this run cannot separate them:

1. **The reference over-calls forest.** The first Bandarban pass returned
   natural_forest for all 240 calls, which is impossible in a district
   containing towns and two major rivers. Re-review at full zoom moved it
   only to 108/120. Chips are 1.5 km wide and Bandarban is overwhelmingly
   green, so scene-level reading inflates forest.
2. **Hansen under-maps forest in Bandarban.** In a swidden landscape the
   2000 canopy baseline catches recently cleared plots that have since
   regrown, so `stable_non_forest` genuinely contains regrown forest at
   2024.

Reading 2 is real and is part of the RQ6 story. Reading 1 is also
plausible. **Report Bandarban's land-cover accuracy as unresolved** and
do not use it to claim Hansen is wrong.

### Plantation is unassessed

Sylhet's map predicts plantation at 7 reference points; the reference
found none, giving user's accuracy 0.000. But the 40-point **plantation
stratum top-up was never interpreted**, and plantation is 0.4% of the
district, so the main sample was never going to contain tea.

RQ3 therefore has a model-side answer — E3 with texture 0.4520 against E4
without 0.3696 — and **no independent validation**. Interpreting the 40
top-up points is the single highest-value hour left in the project.

---

## What is missing, and must be stated as missing

- **Cohen's kappa.** One interpreter per district. Unmeasured.
- **Plantation accuracy.** Stratum not interpreted.
- **Bandarban land-cover accuracy.** Present but not interpretable.
- **Significant loss estimates.** Intervals include zero everywhere.
