# EcoVision — division of labour

Two authors need **separable, defensible contributions**. This file
records who owns what, so that the question "which parts were yours?"
has a written answer that both authors and the supervisor agreed to in
advance.

Based on the recommended split in `methodology_plan.md` §0.3, extended
for the third district. Revisit whenever responsibilities shift — an
inaccurate division-of-labour statement is worse than none, because it is
the document an examiner reads when asking what each author did.

- **Author A:** Sheikh Sulaiman Sony
- **Author B:** Jalal Uddin Mohammad Akbar

## Technical work

| Area | Owner | Status / notes |
|---|---|---|
| GEE project, AOI preparation | A | Complete — `src/prepare_aoi.py`, assets uploaded |
| Scene availability audit | A | Complete — `docs/phase2_audit.md`, START_YEAR = 1988 |
| Preprocessing pipeline, composites, indices | A | Primitives complete — `src/preprocess.py`, 23-band stack |
| Cross-sensor harmonisation | A | Complete — `docs/phase3_harmonisation.md`, locally fitted coefficients |
| Training label construction | A | `src/labels.py`; plantation class blocked on BFD |
| Model implementation (RF, U-Net, Siamese) | **B** | Phase 6, on Kaggle |
| Change detection methods (PCC, NDVI diff, Siamese, LandTrendr) | **B** | B implements each method; district owners apply them |
| Gazipur analysis | A | |
| Sylhet analysis | **B** | Includes the tea-plantation texture ablation (E4) |
| Bandarban analysis | A | Includes the LandTrendr cyclical-vs-permanent jhum split |
| Spatially disjoint splits | **B** | Phase 5, `torchgeo` samplers |
| Dashboard | A | Phase 10, 2-week cap |

## Joint work

| Area | Notes |
|---|---|
| **Reference sample interpretation** | **Both, independently, all 1,800 points each — 3,600 total.** See below |
| Accuracy assessment, area estimation | Both — `src/area_estimation.py` |
| Literature review | Both, split by topic area, cross-reviewing each other's sections. 30–40 references needed; currently 8 |
| Thesis writing | Both — see chapter table |
| Paper draft | Both |

## The reference sample is genuinely joint

Each author interprets **every** point independently: 600 per district,
1,800 each, 3,600 interpretations in total. Roughly 30–60 hours per
author at 1–2 minutes per point.

**Neither author looks at the other's file before `src/kappa.py` is
run.** The independence is the entire content of Cohen's κ; comparing
notes first turns it into a measure of how well you negotiated rather
than how reproducible the interpretation is.

Gate 4 requires κ ≥ 0.75. Below that, reconcile jointly and log what
changed and why — the reconciliation record is part of the audit trail.

This is the binding constraint on the whole thesis and the single
most-skipped step in the risk register. Start it in Month 3, in parallel
with Phase 3. It cannot be compressed at the end.

## Chapter authorship

Every number, figure, and table must come from a script in `src/`
(`docs/README.md` rule 2), whoever writes the prose around it.

| Chapter | Primary author | Reviewer |
|---|---|---|
| 1. Introduction | | |
| 2. Literature review | | |
| 3. Study area | | |
| 4. Data | | |
| 5. Methods | | |
| 6. Accuracy assessment | | |
| 7. Results | | |
| 8. Discussion | | |
| 9. Conclusion | | |

Fill these in before writing starts, not after. A sensible default is
that each author drafts the chapters covering the phases they owned, and
reviews the other's.

## Sign-off

Agree this before Phase 4 interpretation begins. Changing it later is
fine; discovering at submission that it was never accurate is not.

- Author A: Sheikh Sulaiman Sony ______________________  Date: __________
- Author B: Jalal Uddin Mohammad Akbar ______________________  Date: __________
- Supervisor acknowledged: ______________________  Date: __________
