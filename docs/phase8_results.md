# Phase 8 — accuracy against the reference sample

**Numbers last verified against `outputs/tables/` on 2026-09-17.** Every
figure below was read out of the CSVs by script rather than transcribed,
after this document twice drifted out of step with them.

**Relationship to the thesis.** Chapter 6 §6.6–6.7 is the authoritative
statement of these results; where the two ever disagree, the chapter
wins and this file is the one to fix. What this file adds is the
land-cover accuracy table (§3 below), which the chapter does not carry,
and the interpretive notes in the second half.

Run on 400 interpreted points: Gazipur 100, Sylhet 180, Bandarban 120,
under the reduced design, plus a separate 40-point Sylhet plantation
stratum interpreted on 2026-09-17. Cohen's κ **is** measurable for
Gazipur, Sylhet and the plantation stratum — see §5. It is not measurable
for Bandarban, which has one interpreter.

These are the only accuracy figures in the thesis. Everything in
`src/models/` is scored against Hansen-derived training labels — model
against teacher — and is not comparable to anything here.

---

## 1. Forest extent 2024, Olofsson-adjusted (RQ1)

| district | natural forest | non-forest | water |
|---|---|---|---|
| Gazipur | 45,530 ± 25,723 ha | 134,252 ± 25,723 ha | — |
| Sylhet | 41,681 ± 23,420 ha | 254,993 ± 31,210 ha | 27,947 ± 23,145 ha |
| Bandarban | 365,272 ± 43,291 ha | 73,620 ± 41,822 ha | 20,518 ± 14,618 ha |

Bandarban's figures are from the reconciled third pass (commit
`82fe7e2`). Its non-forest estimate of 73,620 ha sits close to the map's
70,448 ha — an agreement at the aggregate level that neither of the
earlier interpretation passes achieved.

## 2. Forest loss 1990–2024

| district | adjusted loss | reference change points |
|---|---|---|
| Gazipur | 443 ± 849 ha | 2 |
| Sylhet | 5,547 ± 10,755 ha | 7 |
| Bandarban | 71,011 ± 41,629 ha | 18 |

**Gazipur and Sylhet are not statistically significant at the 95%
level** — a consequence of sample size meeting a rare class, and the
quantified cost of reducing the sample from 1,650 to 440. **Bandarban's
reconciled interval excludes zero** — the first loss estimate in this
thesis that does. Report each district as it stands, not narrowed by
choosing a friendlier interval.

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
| Sylhet | 0.533 | 0.651 | 0.388 |
| Bandarban | **0.317** | 0.268 | 0.383 |

Overall agreement is the diagonal of `confusion_{district}_2024.csv` over
its total: 57/100, 96/180 and 38/120 respectively.

Forest F1 near 0.40 in Gazipur and Sylhet is modest but coherent, and it
is what an honest assessment of a 30 m Hansen-derived map against
independent interpretation tends to look like. Bandarban is a different
case and is discussed in §4 below.

## 4. Change detection — F1 on the change class

| district | PCC | NDVI differencing | n reference loss |
|---|---|---|---|
| Gazipur | 0.000 | 0.000 | 2 |
| Sylhet | 0.000 | 0.148 | 7 |
| Bandarban | 0.138 | **0.357** | 18 |

**NDVI differencing equals or beats PCC in all three districts.** That is
the direction the literature predicts and the direction this thesis
argued for in advance: PCC accumulates error from both dates, so two maps
at roughly 0.53–0.57 overall agreement cannot produce a reliable change
map between them.

The caveat is severe and must travel with the number: with 2, 7 and 18
reference change points, these F1 values have large sampling uncertainty.
They support a **ranking**, weakly. They do not support a claim about
magnitude.

## 5. Inter-interpreter agreement (Cohen's κ at T3)

| sample | compared points | raw agreement | κ | passes Gate 4 (≥0.75) |
|---|---|---|---|---|
| Gazipur | 100 | 0.500 | 0.157 ± 0.084 | no |
| Sylhet | 180 | 0.439 | 0.038 ± 0.063 | no |
| Sylhet plantation stratum | 40 | 0.300 | 0.067 ± 0.097 | no |

From `outputs/tables/kappa_class_t3.csv`; the ± here is one standard
error, not the 95% interval. All three fail. The plantation stratum is
the worst of them and is reported separately because it measures
agreement *on tea* rather than on the district — see the plantation note
below.

Every reference-based figure above is therefore **provisional pending
reconciliation**, and that caveat belongs with each of them rather than
in a footnote.

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

### Bandarban's map and reference disagree substantially

The map calls 93 of 120 points non-forest; the reference calls 93 of 120
natural forest. User's accuracy for non-forest is 0.161 and overall
agreement is 0.317 — below chance for a two-class problem.

Two readings, and this run still cannot fully separate them:

1. **The reference over-calls forest.** The first Bandarban pass returned
   natural_forest for all 240 calls, which is impossible in a district
   containing towns and two major rivers. Re-review at full zoom moved it
   to 108/120, and the reconciled third pass to 93/120. Chips are 1.5 km
   wide and Bandarban is overwhelmingly green, so scene-level reading
   inflates forest.
2. **Hansen under-maps forest in Bandarban.** In a swidden landscape the
   2000 canopy baseline catches recently cleared plots that have since
   regrown, so `stable_non_forest` genuinely contains regrown forest at
   2024.

Reading 2 is real and is part of the RQ4 *jhum* story. Reading 1 is also
plausible, though the third pass narrowed it considerably — the aggregate
non-forest estimate now agrees with the map to within about 5% (§1).
**Report Bandarban's per-point land-cover accuracy as unresolved** and do
not use it to claim Hansen is wrong.

### Plantation is unassessable, not merely unassessed

Sylhet's map predicts plantation at 7 reference points; the reference
found none, giving user's accuracy 0.000. Plantation is 0.4% of the
district, so the main 180-point sample was never going to contain tea.

The 40-point plantation top-up was drawn to fix exactly that, and **it
was interpreted by both authors on 2026-09-17** — 40/40 complete, in
`data/reference/interpretation_sylhet_plantation_topup_author_*.csv`.
The result is that they agreed on 12 of 40 points, **κ = 0.067 ± 0.189**
(§5). Author A called 25 of the 40 plantation; author B called 14, and
called 20 of them natural forest. Nine points A called water, B called
none.

**The stratum is therefore not used for validation.** That decision is
deliberate and it is not the same as leaving the work undone: a reference
sample whose interpreters agree at chance is not an independent yardstick,
and computing an accuracy figure against it would present a disagreement
as a measurement.

RQ3's answer stands as a model-side comparison — E3 with texture 0.4520
against E4 without 0.3696, architecture and data held constant — with
**no independent validation**, stated as such. The stratum's failure is
reported in Chapter 7 §7.3 as a fifth line of evidence that plantation
mapping is genuinely unsolved, which is a more useful result than a
validation number would have been.

**If this is ever revisited,** the water disagreement is the place to
start: A called 9 of these 40 water and B called none, and the same
divergence shows in the main sample (13 water against 6). That looks like
one definitional difference rather than 40 independent judgements, and
settling it may lift agreement across the whole Sylhet sample.

---

## What is missing, and must be stated as missing

- **Plantation accuracy.** Stratum interpreted 2026-09-17 but not
  usable: the two interpreters agreed at chance on it (kappa 0.067).
  Reported as unvalidated, deliberately.
- **Bandarban per-point land-cover accuracy.** Present but not
  interpretable; the aggregate area estimate is sound, the point-by-point
  agreement is not.
- **κ for Bandarban.** Only one interpreter. Unmeasured and unassumable.
- **κ above threshold anywhere.** Measured in two districts, failing in
  both. Reconciliation, then recomputation of everything downstream.
- **Significant loss estimates in Gazipur and Sylhet.** Both intervals
  include zero. Bandarban's does not.
