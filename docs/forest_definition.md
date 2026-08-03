---
title: "EcoVision — Operational forest definition"
status: DRAFT — awaiting supervisor sign-off
version: 0.1
date_drafted: 2026-07-26
date_signed_off:
---

# Operational forest definition

**Status: DRAFT. Not yet signed off. Do not begin Phase 4 labelling
against this definition until the sign-off block at the foot of this
document is completed.**

This document fixes what "forest" means for every number this thesis
reports. It is written before any data is touched, deliberately — a
definition chosen after seeing results is not a definition, it is a
justification. The wording in §1 is quoted verbatim in the thesis
(Chapter 3, Study Area) and governs Phases 3 through 8.

---

## 1. The definition

> Forest is land with tree canopy cover of **at least 30%** over a
> minimum mapping unit of **0.5 ha** (approximately 6 Landsat pixels at
> 30 m resolution), with trees capable of reaching **5 m height in
> situ**, **excluding** tea plantations, rubber plantations, orchards,
> agroforestry woodlots, and homestead vegetation. Bare ground within a
> forest boundary arising from temporary disturbance is classified as
> forest where regrowth is evident within the observation period.
>
> Land under shifting cultivation (**jhum**) is classified by its canopy
> condition at the observation date, not by its land-use history: an
> actively cultivated or recently cleared jhum plot is non-forest, and a
> jhum fallow meeting the canopy, area, and height criteria above is
> forest. Canopy loss on land whose annual trajectory shows recovery
> within the observation period is reported as **cyclical disturbance**,
> separately from **permanent conversion**, and only permanent
> conversion enters headline deforestation totals.

---

## 2. Why each clause is there

| Clause | What it prevents |
|---|---|
| Canopy cover ≥30% | An arbitrary and unstated comparison with Hansen GFC, whose `treecover2000` band is a continuous percentage requiring the analyst to pick a threshold. Stating 30% makes our figures reproducible and directly comparable. |
| MMU 0.5 ha (≈6 pixels) | Single-pixel salt-and-pepper "loss" inflating area statistics. Implemented as a connected-component filter in Phase 7.2. |
| Trees capable of 5 m in situ | Scrub and shrubland registering as forest. "In situ" matters — young trees in a recently cut plot still qualify, which is what makes the temporary-disturbance clause coherent. |
| Excluding tea and rubber | **The Sylhet failure mode.** Tea estates are spectrally close to natural forest. If they count as forest, real hill-forest loss is masked by stable plantation canopy and the district's loss figure is understated. |
| Excluding orchards and agroforestry woodlots | Managed tree crops behaving as agriculture, not forest, in both districts. |
| Excluding homestead vegetation | Village tree cover in Gazipur — dense, tree-covered, and not forest by any policy-relevant sense. |
| Temporary-disturbance clause | A selectively logged or wind-damaged patch flickering forest → non-forest → forest across epochs, producing implausible trajectories. Cross-checked in Phase 7.3. |
| Jhum clause — canopy condition, not land-use history | An unanswerable question at the moment of labelling: "is this fallow plot forest?" Judged on canopy alone, it is answerable from imagery. Judged on land-use history, it requires knowledge the imagery does not contain, and two interpreters will disagree — directly threatening the κ ≥ 0.75 gate. |
| Jhum clause — cyclical vs permanent split | **The Bandarban failure mode.** Counting swidden fallow as deforestation would inflate Bandarban's loss figure by whatever fraction of the landscape happened to be mid-cycle at T3. That is an artefact of date selection, not a measurement. |

---

## 3. Relationship to other definitions

State this comparison explicitly in the thesis rather than leaving an
examiner to work out whether our numbers are commensurable with
published figures.

| Source | Their definition | Difference from ours |
|---|---|---|
| FAO FRA | ≥10% canopy, ≥0.5 ha, trees ≥5 m, excluding land predominantly under agricultural or urban use | Ours is stricter on canopy cover (30% vs 10%) and names the excluded plantation types explicitly rather than relying on the "predominantly agricultural use" clause |
| Hansen GFC | `treecover2000` is continuous canopy percentage; forest is whatever threshold the user applies. Includes plantations. | We threshold at 30% to match ours. **Hansen counts tea and rubber as tree cover — we do not.** This is the expected source of divergence in Phase 8.3 cross-validation, and it is a result to explain, not an error to hide. |
| BFD / national reporting | Reported at the 2026-07-27 supervisor meeting as **consistent with the definition in §1** | No material divergence identified. **Still to obtain: the written BFD definition itself**, so this row can quote it rather than paraphrase a meeting. |
| Siddik et al. (2025), *J. Agroforestry and Environment* 18(2):102–115 | Tea estates mapped from imagery; **18 estates in Sylhet district**, none in Gazipur or Bandarban | Independent evidence for the scale of the plantation problem. Sylhet holds >10,000 ha under tea against 28,489 ha of Hansen ≥30% "forest" — so a large share of what Hansen calls forest in Sylhet is plausibly tea. Confirms the plantation exclusion in §1 is load-bearing, not precautionary. |

---

## 4. Class scheme

Four classes, not two. Binary forest/non-forest cannot express the
plantation problem, which is the central technical risk in Sylhet.

| Code | Class | Contents |
|---|---|---|
| 0 | Non-forest | Built-up, bare soil, cropland, actively cultivated or recently cleared jhum |
| 1 | Natural forest | Sal forest (Gazipur), remnant hill forest (Sylhet), mixed evergreen and semi-evergreen hill forest plus qualifying jhum fallow (Bandarban) |
| 2 | Plantation / tea | Tea estates and rubber (Sylhet); teak and rubber plantations (Bandarban); orchards, agroforestry woodlots |
| 3 | Water | Rivers, ponds, haors (Sylhet), Sangu and Matamuhuri river systems (Bandarban) |

**Class 2 is trained, mapped, and reported separately throughout.**
Collapse to binary forest/non-forest happens only at the final reporting
step, and every table that presents collapsed figures must say so in its
caption.

**Jhum is not a class.** It is handled as a trajectory property on top
of these four classes — see §6.4. A jhum plot occupies class 0 or
class 1 depending on its canopy at the observation date; whether its
canopy loss is cyclical or permanent is decided from the annual series,
not from the class map.

---

## 5. Consequences for the pipeline

Downstream code depends on this document. If any clause changes after
sign-off, these must be revisited:

| Clause | Enforced where |
|---|---|
| 30% canopy threshold | Phase 4.1 — Hansen `treecover2000` thresholding. Parametrised as `CANOPY_THRESHOLD`, never hardcoded, so §6.1's sensitivity run is a one-line change |
| 10% sensitivity run | Phase 8 — rerun area estimation at `CANOPY_THRESHOLD = 10`, report alongside the 30% figure |
| 0.5 ha MMU | Phase 7.2 — connected-component filter on change maps |
| Plantation exclusion | Phase 4.1 label construction; Phase 7.2 plantation mask; all Phase 8 reporting |
| Four-class scheme | Phase 4 labels, Phase 5 experiment design, Phase 6 model output channels |
| Degradation via magnitude, not class | Phase 7 LandTrendr NBR magnitude; Phase 9 Gazipur/Sylhet magnitude-distribution comparison |
| Temporary-disturbance clause | Phase 7.3 temporal consistency check |
| Jhum: cyclical vs permanent split | Phase 2 Gate — confirm annual coverage over Bandarban supports LandTrendr; Phase 4.2 cyclical-disturbance stratum; Phase 7 trajectory classification; Phase 8 separate columns in every Bandarban loss table |

---

## 6. Decisions taken, and the one still open

Decisions 1 and 2 were taken by the authors on 2026-07-26 and are
recorded here for supervisor confirmation at sign-off. They are not
silent defaults — each was an explicit choice with a rejected
alternative, and each is to be stated in Chapter 3.

### 6.1 Canopy threshold: 30%, with a stated caveat — CONFIRMED BY SUPERVISOR

**Confirmed at the supervisor meeting, 2026-07-27.** The threshold is
fixed at 30% and the reference-sample strata may be drawn against it.

**Chosen:** 30% canopy cover, as in §1.

**Rejected:** 10%, the FAO FRA threshold.

**Why:** 30% separates closed forest from scattered tree cover far more
cleanly, and scattered cover is exactly what produces the Gazipur
homestead-vegetation and Sylhet plantation confusion this thesis has to
survive. A 10% threshold would pull both into the forest class.

**Cost, stated plainly:** our loss totals are **not directly comparable
to FAO FRA Bangladesh figures**, which use 10%. Chapter 8 (Discussion)
must say this where the comparison is made. Not stating it would make
our numbers look like they contradict national reporting when in fact
they are measuring a different thing.

**Mitigation — the 10% sensitivity run.** Repeat the area estimation
with the Hansen threshold set to 10%, holding everything else fixed, and
report both figures in a single table. This converts the limitation into
a result: it quantifies how much of the divergence from national
reporting is definitional rather than substantive. Scheduled in Phase 8;
first item on the cut list if Phase 8 runs short, since the 30% figure
stands on its own.

### 6.2 No degraded-forest class — DECIDED

**Chosen:** four classes as in §4. Degradation is captured through
LandTrendr change magnitude on the annual NBR series, not through a
label class.

**Rejected:** a fifth "degraded forest" class.

**Why:** Sylhet loss is expected to be gradual and partial rather than
abrupt clearance, so degradation genuinely matters. But a fifth class
needs its own reference stratum, and Phase 4.2 is already 600 points per
district interpreted twice, by hand — the single most-skipped step in
the risk register. Adding a stratum risks the whole accuracy assessment
to improve one sub-result.

**How degradation is still addressed:** LandTrendr outputs a continuous
change magnitude per pixel. Partial canopy loss appears as a
low-magnitude disturbance segment rather than a class transition.
Phase 9 discusses the magnitude distribution for Sylhet against Gazipur;
a fatter low-magnitude tail in Sylhet is itself evidence of degradation-
dominated loss.

**Honest limitation for Chapter 8:** degradation below the 30% canopy
transition is detected as a *signal*, not *classified* and not
*area-estimated*. We do not report a degraded-forest area figure,
because we have no reference sample to support one.

### 6.4 Jhum handled by trajectory, not by class — DECIDED

Taken 2026-07-26 alongside the Bandarban scope change.

**Chosen:** jhum is classified by canopy condition at the observation
date (§1, second paragraph), and the cyclical-vs-permanent distinction
is made from the **annual LandTrendr trajectory** — a pixel whose NBR
recovers within the observation period is cyclical disturbance, one that
does not is permanent conversion.

**Rejected — a fifth "jhum" land-cover class.** Shifting cultivation is
not a land cover, it is a land-use *process*. At any single date a jhum
plot looks like bare soil, cropland, scrub, or young forest depending
only on its position in the cycle. No interpreter can label "jhum" from
a single image, so a jhum class would fail the reference-interpretation
protocol and drag down κ.

**Rejected — excluding jhum land wholesale, as we exclude tea.** Tea
estates have fixed, mappable boundaries; jhum has no stable footprint,
it migrates across the landscape between cycles. There is nothing to
draw a mask around.

**What this requires that the two-district design did not:**

1. **The annual series is now load-bearing for Bandarban**, not just a
   trend extra. Phase 2's audit must confirm enough annual coverage over
   Bandarban to run LandTrendr; if it cannot, the cyclical/permanent
   split is unsupportable and Bandarban's loss figure cannot be reported
   as deforestation at all. **Check this at Gate 2, before Phase 3.**
2. **A "cyclical disturbance" stratum in the Bandarban reference
   sample** (Phase 4.2), so the split is validated rather than asserted.
   Without it we have no accuracy figure for the one thing the third
   district was added to demonstrate.
3. **Loss tables gain a column.** Bandarban reports permanent conversion
   and cyclical disturbance separately, always. Gazipur and Sylhet
   report a single loss figure. Never sum a Bandarban total across both
   columns and compare it to the other two districts.

**Honest limitation for Chapter 8:** a jhum cycle longer than the
observation period is indistinguishable from permanent conversion in our
data. Cycles in CHT are commonly reported at 5–7 years but have been
lengthening; a plot cleared near the end of the series and not yet
recovered will be counted as permanent loss. State this, and state the
direction of the resulting bias — it **overestimates** permanent
conversion in Bandarban.

### 6.5 Plantation boundaries — STILL BLOCKED (definition resolved)

Two separate things were conflated under "BFD" and they have now come
apart:

**Resolved — the definition.** BFD's operational forest definition was
reported at the 2026-07-27 meeting as consistent with §1. §3 records
this. Still worth obtaining the written definition so that row quotes a
document rather than a meeting.

**Still blocked — the geometry.** The plantation class (class 2) and the
plantation reference stratum both need *polygons*, and none are in hand.

Siddik et al. (2025) was reviewed as a candidate source. It establishes
that Sylhet holds 18 tea estates concentrated in Gowainghat, Kanaighat,
Sylhet Sadar, Jaintiapur and Companiganj, with some in Balaganj and
Fenchuganj, and that neither Gazipur nor Bandarban has tea estates. But
its Tables 1–4, which the text says carry per-estate coordinates, contain
no data in the available proof — only district centroids appear anywhere
in the file. **It is a citable source for scale and location context, not
a source of geometry.**

Consequences that follow from it, and which stand regardless:

- **The tea problem is Sylhet-only.** Gazipur needs no tea stratum.
  Bandarban has teak and rubber, which that paper does not cover and
  which need their own source.
- **18 estates is tractable to digitise by hand**, unlike the 152
  nationally. This is the realistic fallback if BFD/BFIS geometry never
  arrives, and it is now a decision with a known cost rather than an
  open-ended one.

Do not substitute a spectral proxy for the plantation stratum. Separating
plantation from natural forest spectrally is the thesis question; using
spectral similarity to define the stratum would assume the answer. A
*location* proxy from an independent published source does not have that
problem and is acceptable.
not guess the row's contents in the meantime.

---

## 7. Sign-off

This definition is fixed once signed. Changing it afterwards invalidates
every label, map, and area estimate produced against it.

| Role | Name | Signature / typed name | Date |
|---|---|---|---|
| Author A | Sheikh Sulaiman Sony | | |
| Author B | Jalal Uddin Mohammad Akbar | | |
| Supervisor | | | |

**On sign-off:** change `status` in the front matter to `SIGNED OFF`,
fill `date_signed_off`, and tick Phase 1 in `CLAUDE.md`.
