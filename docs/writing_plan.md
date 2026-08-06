# Writing plan — what can be written now, and from what

Written 2026-08-06, at the point where the whole computational pipeline
through Phase 6 exists and the reference interpretation has not started.

The purpose of this file is narrow. Roughly 60% of the thesis depends on
no model result whatsoever, and that 60% is writable in parallel with the
interpretation rather than after it. What follows says, section by
section, which existing artefact each part is written *from*, so nobody
has to re-derive a decision that was already made and recorded.

**Division of labour while this holds:** one author interprets, the other
writes. Both interpreting is the wrong allocation — writing is the longer
pole and it has no dependency at all.

---

## Chapters that need no results

### Chapter 1 — Introduction

Nothing in the repo to draw on except the framing. Write from the
research questions in `CLAUDE.md` and the original proposal
`docs/thesis_proposal.md`.

One correction to carry through: the proposal's title says "Google
Earth"; the imagery is Landsat via Google Earth Engine. The proposal is
superseded on that point.

The Bandarban scope change (2026-07-26) belongs here as motivation, not
as an apology. Three districts were chosen because they contribute three
*distinct loss mechanisms* — abrupt conversion, gradual degradation with
plantation confusion, and cyclical jhum. The argument that model choice
matters more as landscape complexity rises is much harder to dispute
across three mechanisms than two.

### Chapter 2 — Literature review

No repo artefact. This is the one section that is pure writing.

Three threads the rest of the thesis actually needs:
- deep learning for change detection (U-Net, Siamese architectures)
- the plantation-versus-natural-forest discrimination problem — this is
  what RQ3 is about, and §6.5 of `docs/forest_definition.md` documents
  that no open dataset maps Bangladesh's tea
- temporal segmentation (LandTrendr) and why bitemporal comparison
  cannot separate cyclical from permanent change

### Chapter 3 — Study area

| Content | Source |
|---|---|
| District map, areas, loss mechanisms | `outputs/figures/study_area.png` |
| Areas verified against published figures | `src/prepare_aoi.py` |
| Why Bandarban and not Rangamati or Khagrachhari | `CLAUDE.md`, scope change section |

Gazipur 1,819 km², Sylhet 3,416 km², Bandarban 4,592 km².

### Chapter 4 — Data

| Content | Source |
|---|---|
| Scene availability, 120 district-years | `outputs/figures/scene_availability.png`, `outputs/tables/scene_audit_summary.csv` |
| START_YEAR = 1988 and why | `docs/phase2_audit.md` |
| Epoch anchors T0 1990, T1 2000, T2 2010, T3 2024 | same |
| 2012–13 fully SLC-off, excluded as anchors | same |
| Forest definition, 30% canopy threshold | `docs/forest_definition.md` |

Two things to state plainly rather than bury. 1985–87 have **zero**
scenes in all three districts — an acquisition gap, not cloud, which is
why the series starts at 1988. And T0 is 1990 rather than 1988 because
1988's observation depth is about half 1990's, and T0 is one half of
every bitemporal comparison.

**Still unsigned:** supervisor confirmation of START_YEAR and the epoch
anchors. Chapter 4 states them as settled. Get the confirmation now — it
is a one-line email and it blocks nothing else.

### Chapter 5 — Methodology

| Content | Source |
|---|---|
| Preprocessing, 23-band stack, scale factors | `src/preprocess.py` |
| Cross-sensor harmonisation, incl. departing from Roy et al. | `docs/phase3_harmonisation.md`, `outputs/figures/harmonisation.png` |
| Spatially disjoint block splits | `outputs/figures/block_splits.png`, `src/splits.py` |
| Patch size 128, and why not 256 | `docs/phase5_experiment_matrix.md` |
| Experiment matrix E1–E7 | same, plus `src/models/ensemble.py` for E7 |
| Reference sample design, strata, allocation | `src/reference_sample.py` |
| Interpretation protocol and the three calls that cost κ | `docs/interpretation_protocol.md` |
| Area estimator | `src/area_estimation.py` |

The harmonisation section is worth writing carefully. Roy et al. (2016)
is the standard citation and this thesis *departs from it on four of six
bands* because the published coefficients measurably made things worse
here — NIR and SWIR2 were left untransformed, and NBR is built from
exactly those two. That is a defensible, measured decision and the figure
shows the evidence. Presenting it as a considered result rather than a
deviation is the difference between a strength and a wobble.

---

## Chapters that need results

### Chapter 6 — Results
### Chapter 7 — Accuracy assessment
### Chapter 8 — Discussion

Blocked on interpretation and the Kaggle runs. But three items for
Chapter 8 are already established and can be drafted now, because they
are findings about method rather than about forest:

1. **The tea10 episode.** A careful human working with sub-metre imagery
   digitised 1,906 ha of "tea" of which roughly 1,600 ha was hill forest
   — an 83% error, caught only because it was independently checked. That
   is direct evidence for the premise RQ3 rests on. `docs/forest_definition.md` §6.5.

2. **Automation of the plantation layer failed, in four measured ways.**
   SDPT v1.3 has no Bangladesh layer; GFW rendered tiles gave 0.00%
   coverage over Sylhet against 83% over Sumatra; a purpose-built FFT and
   Hough row-texture detector could not separate tea from forest
   (forest 4.36 vs tea 4.27, p = 0.55, `src/tea_row_texture.py`); public
   gazetteers matched 1 estate in 19 under strict name matching. These
   negatives explain why the plantation problem persists in regional
   forest statistics, and they turn RQ3 from a rhetorical question into a
   real one.

3. **Class 2 is incomplete and the thesis must say so.** 1,303 ha drawn
   against >10,000 ha reported by Siddik et al. (2025). Tea outside the
   drawn polygons is still labelled natural forest, so the Sylhet
   confusion is *reduced, not eliminated*. Stating the bound is what
   makes the RQ3 result interpretable.

---

## What must not be written yet

Rule 8. No accuracy figure, area estimate, or confusion matrix goes into
the text until it comes out of an actual run. Anything illustrative used
while drafting must be marked `EXAMPLE — replace with real run output`
and removed before submission.

Two specific traps, both easy to fall into under deadline:

- **Do not report overall accuracy as a headline.** The change class is a
  small minority — 0.22% of pixels in Gazipur and Sylhet. A model that
  predicts "no change" everywhere scores 99.8%. Headline metric is F1/IoU
  on the change class (rule 5).
- **Do not report a Bandarban deforestation total without splitting it.**
  Jhum is cyclical; a T0→T3 pair scores a fallow plot as loss or as
  nothing purely according to where in the swidden cycle the dates land.
  Permanent conversion and cyclical disturbance must be separated using
  the annual LandTrendr trajectory, and the headline counts permanent
  conversion only (rule 9).
