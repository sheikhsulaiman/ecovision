# Chapter 2 — Literature Review (OUTLINE ONLY — you write this)

**This file is deliberately not drafted.** Chapter 2 needs citations to
papers you have actually read, and invented references are both the most
damaging thing that could go into this thesis and the easiest thing for
an examiner to check. What follows is the structure the rest of the
thesis needs Chapter 2 to establish, and the specific claims each section
has to support.

Every source named below is one this project already depends on
substantively — they appear in the code, the methodology, or the results
— so they are the minimum, not a suggested reading list.

---

## 2.1 Satellite-based forest monitoring

**What the rest of the thesis needs from this section:** that Landsat is
the standard instrument for multi-decadal forest monitoring, and that
global products exist and are widely used as labels.

Must cover:
- Landsat programme and the open-archive change after 2008
- **Hansen et al. (2013)**, Global Forest Change — used here as the
  training-label source. Ch. 4.4, 6.6
- Its known limitations, particularly commission error and the fact that
  its baseline is a single year (2000). Ch. 6.6 reports Gazipur drawing
  40 points from the Hansen loss stratum of which only 2 were judged
  genuine loss — that finding needs prior work to sit against.
- **JRC Global Surface Water** — used for the water class. Ch. 4.4

## 2.2 Forest definitions and why they matter

**What the thesis needs:** that "forest" is a definitional choice, not a
natural kind, and that the choice changes reported area.

Must cover:
- FAO forest definition and canopy-threshold conventions
- The land-use versus land-cover distinction — this thesis takes a
  **canopy-at-date** definition, which is what makes a regrown *jhum*
  fallow forest. Ch. 4.3
- Sensitivity of reported area to threshold choice (10% vs 30%)

## 2.3 Classification methods

**What the thesis needs:** that Random Forest is the established baseline
and U-Net the established deep-learning segmentation architecture, so
that comparing them is comparing standards rather than straw men.

Must cover:
- **Breiman (2001)**, Random Forest
- Random Forest in remote sensing land cover — its dominance as a
  baseline, and why
- **Ronneberger et al. (2015)**, U-Net
- Encoder pretraining and transfer learning for small labelled sets —
  directly relevant to RQ5 and to the Gazipur result at 55 training
  patches. Ch. 6.3
- Ensemble and stacking methods — needed for E7. Ch. 5.6, 8.2

## 2.4 Change detection

**What the thesis needs:** that post-classification comparison is known
to accumulate error from both dates, so that the PCC result in Ch. 6.6 is
confirmation rather than discovery.

Must cover:
- Taxonomy: post-classification comparison, image differencing, direct
  methods
- The error-accumulation argument for PCC — if each map is 90% accurate
  the change map is ~81%. Ch. 5.7 states this as the prediction; Ch. 6.6
  and 8.5 report it observed
- Index differencing and threshold selection, including why Otsu assumes
  bimodality that does not hold over a district 87% non-forest. Ch. 5.7
- **Daudt et al. (2018)**, FC-Siam-diff — the E5 architecture
- Benchmark change-detection datasets (LEVIR-CD, OSCD) and why they do
  not transfer directly to this problem

## 2.5 Temporal segmentation

**What the thesis needs:** that trajectory-based methods exist precisely
because date pairs cannot represent process, which is the entire basis of
RQ6.

Must cover:
- **Kennedy et al. (2010)**, LandTrendr; **Kennedy et al. (2018)**, the
  GEE implementation. Ch. 5.8
- Why NBR rather than NDVI for disturbance — sharper response to canopy
  removal, less saturation over dense canopy. Ch. 5.8
- Alternatives: BFAST, CCDC — and why LandTrendr was chosen here
- Shifting cultivation detection from time series — this is the closest
  prior work to Ch. 6.5 and the section where a genuine gap should be
  identifiable

## 2.6 Plantation discrimination

**The most important section, and the one with the least prior work.**

**What the thesis needs:** that separating plantation from natural forest
is a recognised open problem, so that Ch. 8.3's four independent failure
measurements read as contribution rather than as this study's shortcoming.

Must cover:
- Spectral similarity of evergreen plantation and natural forest
- Texture approaches, GLCM — **Haralick et al. (1973)** for the original
  features. Ch. 5.4
- Existing plantation datasets and their coverage. Note for Ch. 8.3: the
  Spatial Database of Planted Trees omits Bangladesh entirely, which is a
  checkable claim you should verify and cite properly
- Tea cultivation in Sylhet — area statistics, estate structure.
  **Siddik et al. (2025)** is cited in the code for the >10,000 ha
  district figure; verify it and cite it properly, since Ch. 4.6 and 8.8
  both depend on it

## 2.7 Accuracy assessment and area estimation

**What the thesis needs:** that pixel counting is a biased area estimator
and that the stratified estimator is the accepted correction. This is the
single most load-bearing methodological citation in the thesis.

Must cover:
- **Olofsson et al. (2013, 2014)** — good practices for accuracy
  assessment and area estimation. Ch. 5.9, 6.6
- Stratified sampling design and sample allocation to rare classes
- **Cohen (1960)**, kappa; and the literature criticising kappa as an
  agreement measure — Ch. 6.7 reports a failing kappa and Ch. 8.4
  interprets it, so the critique matters
- Why overall accuracy misleads for minority classes. Ch. 5.9

## 2.8 Cross-sensor harmonisation

**What the thesis needs:** that Roy et al. is the standard reference, so
that Ch. 5.3 departing from it on four of six bands reads as a measured
finding rather than as ignorance of the literature.

Must cover:
- **Roy et al. (2016)** — ETM+ to OLI transformation coefficients
- Sensor spectral response differences across TM, ETM+, OLI
- Landsat 7 SLC-off and its consequences for 2012–2013. Ch. 4.2
- Note: Ch. 5.3 reports Roy's coefficients performing worse than no
  correction on this data. Present the standard fairly and completely
  here so that departure is credible later.

## 2.9 Research gap

Pull together into a statement of what has not been done:

1. Method comparison across **multiple loss mechanisms** rather than
   within one landscape
2. Controlled ablation of texture for plantation discrimination
3. Explicit permanent-versus-cyclical separation before reporting
   deforestation totals in a shifting-cultivation landscape
4. Bangladesh-specific: no plantation reference data exists, which
   bounds what anyone can currently achieve

---

## Practical notes

**Length.** 3,000–5,000 words is typical for an undergraduate thesis
literature review. §2.6 and §2.7 deserve the most space — they carry the
most weight later.

**Do not cite anything you have not read.** Every claim above is one the
later chapters depend on; a wrong citation propagates into the results
discussion.

**Verify the two claims this project asserts from literature:** the
Sylhet tea area figure (>10,000 ha, attributed to Siddik et al. 2025) and
the absence of Bangladesh from global plantation databases. Both appear
in Ch. 4.6 and Ch. 8.3 and both are checkable.
