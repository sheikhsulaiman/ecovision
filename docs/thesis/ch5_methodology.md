# Chapter 5 — Methodology

## 5.1 Overview

The pipeline proceeds in seven stages: compositing, cross-sensor
harmonisation, feature construction, spatial partitioning, classification,
change detection, and accuracy assessment. Each stage is implemented as an
independently testable script; nothing in the results chapter is produced
by an interactive session whose state cannot be reconstructed.

## 5.2 Compositing

For each district and year, all scenes from the dry-season window
(1 November – 31 March) with scene cloud cover below 40% are retrieved
across all contributing sensors, cloud- and shadow-masked using the
Collection 2 QA_PIXEL band, scaled to surface reflectance, harmonised to
a common radiometric basis (§5.3), and reduced by **median**.

Median rather than mean, because the median is robust to residual cloud
and shadow that survive masking; and rather than medoid, because medoid
is substantially more expensive over a 37-year annual series for a
difference that does not affect the classes at issue here.

## 5.3 Cross-sensor harmonisation

The study spans TM, ETM+ and OLI. These instruments have different
spectral response functions, so identical ground returns different
reflectance values, and uncorrected this produces apparent change at every
sensor transition — including at 2012–2013, in the middle of the series.

The standard correction is Roy et al. (2016), which provides published
ETM+ to OLI coefficients. Rather than adopt them on authority, they were
**tested against locally fitted alternatives** on this data.

Coefficients were fitted from **45 near-coincident ETM+/OLI scene pairs**
across all three districts, yielding 34,414 paired pixels. Thirteen pairs
were held out for validation. **The split was by scene pair, never by
pixel** — pixels from the same pair are not independent, and splitting by
pixel would have produced an optimistic validation with no warning.

### Result

Held-out mean residual: raw 0.01582, Roy 0.01680, local OLS **0.01433**.

**The published coefficients performed worse than applying no correction
at all on this data.** Locally fitted coefficients performed about 9%
better than no correction. A transform was therefore adopted per band
only where it beat doing nothing by more than a 5% margin:

| Band | Transform | Source | Gain vs raw |
|---|---|---|---|
| blue | ×0.721504 + 0.006165 | local OLS | −33.9% |
| green | ×0.848300 + 0.008800 | Roy et al. (2016) | −12.0% |
| red | ×0.874212 + 0.005028 | local OLS | −15.6% |
| nir | **none** | — | −1.5%, below margin |
| swir1 | ×0.975336 + 0.001335 | local RMA | −5.8% |
| swir2 | **none** | — | raw was best |

### Why NIR and SWIR2 are left untransformed

This is a decision, not an omission. **NBR is computed from NIR and
SWIR2**, and NBR is the index segmented to separate cyclical *jhum*
disturbance from permanent conversion (§5.8). Roy's coefficients degraded
both bands on held-out pairs — NIR by 8.5% and SWIR2 by 69.8% — so
adopting them would have propagated a measured degradation directly into
the index on which the Bandarban result depends.

TM requires no transform. This was measured, not assumed: for every band
the TM-to-ETM+ chain either selected `raw` or produced a gain below the
adoption margin.

The general point is worth stating. Published harmonisation coefficients
are fitted over particular landscapes and atmospheres, and their
transferability is an empirical question rather than a given. Testing them
cost one script; adopting them unexamined would have degraded the study's
central index.

## 5.4 Feature construction

Each composite is expanded into a **23-band feature stack**:

| Group | Bands |
|---|---|
| Spectral | blue, green, red, NIR, SWIR1, SWIR2, thermal |
| Vegetation indices | NDVI, EVI, SAVI |
| Moisture / built-up | NDWI, NDMI, NDBI |
| Burn / disturbance | NBR |
| Tasselled cap | brightness, greenness, wetness |
| Texture (GLCM on NIR) | contrast, entropy, homogeneity |
| Terrain (SRTM) | elevation, slope, aspect |

**GLCM texture is included specifically to test RQ3.** Tea plantation and
natural forest are spectrally similar but structurally different:
plantation has planted rows, uniform canopy height and geometric
boundaries, while natural forest is structurally chaotic. If that
difference is detectable at 30 m, it will appear in texture rather than in
reflectance. Texture is computed on the composite rather than per scene,
because per-scene texture is dominated by cloud-edge artefacts.

Terrain is included because tea estates in Sylhet sit on hill slopes and
*jhum* in Bandarban is a function of terrain; whether it helps is tested
as an ablation (§5.6) rather than assumed.

## 5.5 Spatial partitioning

**Train, validation and test splits are spatially disjoint, assigned as
whole 10 km blocks.**

Random splitting at pixel or patch level is invalid on this data.
Neighbouring pixels are strongly spatially autocorrelated, so a random
split places near-identical samples on both sides of the evaluation and
inflates reported accuracy by a well-documented margin. The failure is
silent: nothing errors, and the resulting figures look better than the
correct ones.

Blocks are assigned greedily to whichever split is furthest below its
target share of **forest-loss pixels**, with total area as a secondary
criterion. Balancing on loss rather than area alone is necessary because
loss is 0.22% of pixels in Gazipur and Sylhet, and an area-balanced
assignment routinely produces a test split containing almost no change at
all — which cannot measure the headline metric.

Targets are 70/15/15. Achieved shares are reported per district.

### Plantation constraint

Sylhet's split carries an additional constraint. The hand-digitised tea
polygons fall within **4 of 48 blocks**, and two of those hold 99.8% of
the area. An initial assignment placed both in validation and test,
leaving the training split with 0.24% of the plantation area — and the
models, trained without a single tea example, scored **0.000 F1 on
plantation**, which was arithmetically guaranteed rather than informative.

Plantation blocks are therefore pinned before the greedy pass: the
largest to **training**, the second to **test**. Training, because a class
absent from training cannot be learned; test, because a class absent from
test cannot be measured. Validation loses, because its role is early
stopping and a class at 0.5% of pixels never drove checkpoint selection.

A proportional 70/15/15 split of plantation is not available at 10 km
blocks. With two meaningful blocks the only available choice is which two
splits receive tea. The consequence — that Sylhet's plantation test
estimate rests on a single 10 km block, and is therefore spatially
pseudo-replicated — is reported alongside the result.

## 5.6 Classification

### Experiments

| ID | Model | Purpose |
|---|---|---|
| E1 | Random Forest, spectral + indices + texture | Baseline |
| E2 | E1 + terrain | Does terrain help? |
| E3 | U-Net, full 23-band stack | Deep learning baseline |
| E4 | U-Net, 20 bands (texture removed) | **RQ3 ablation** |
| E7 | Stacked RF + U-Net ensemble | Does combining help? |

A sixth experiment, E5 — a Siamese network for direct bitemporal change
detection — was specified in the original experiment matrix but was not
run. It is documented here rather than omitted silently, because the
change-detection comparison in §5.7 is narrower as a result: two methods
are compared rather than three. Nothing reported in this thesis depends
on E5, and no research question requires it.

Random Forest is run first and deliberately. It establishes an accuracy
floor, debugs the entire data pipeline at negligible cost, and produces
feature importances — all three worth more than the model itself.

### Patch extraction

U-Net training uses **128 × 128 pixel patches** (3.84 km). The original
design specified 256 × 256, but a 256-pixel patch is 7.68 km and does not
tile inside a 10 km block, yielding roughly 165 training patches in total
— too few to fine-tune a pretrained encoder.

Patches are cut **inside** blocks, never across them, and partial tiles at
block edges are discarded. A patch spanning a training block and a test
block would place the same ground on both sides of the evaluation, and
would not surface as an error, only as an implausibly good test score.

### Class imbalance

Imbalance differs by two orders of magnitude across the districts — forest
loss is 0.22% of pixels in Gazipur and Sylhet but 24.3% in Bandarban.
Patch sampling is therefore weighted toward informative content in the
first two districts and left unweighted in Bandarban, where the classes
are already near-balanced.

**Test splits are never weighted, in any district.** A filtered test set
measures the sampler rather than the model.

Loss is a combination of Dice and cross-entropy, with nodata pixels
excluded by an ignore index rather than folded into the non-forest class.
Assigning nodata to class 0 would teach the model that the area outside
the district is non-forest, an error that surfaces only as slightly worse
edge predictions.

### The ensemble

E7 stacks Random Forest and U-Net predictions through a logistic
meta-learner. The two models fail differently, which is what makes
stacking worthwhile: Random Forest sees a single pixel's 23 bands and no
spatial context, so it is strong on spectrally distinct classes and blind
to shape; U-Net sees a 3.84 km neighbourhood and captures boundaries and
patch geometry but can be confidently wrong about an isolated pixel.

**The meta-learner is fitted on the validation split**, not on training or
test. Fitting on training would fit it to predictions the base models have
memorised, teaching it to trust Random Forest unconditionally and to
collapse on unseen ground; fitting on test is straightforward leakage.
Validation is genuinely unseen by both base models because the blocks are
spatially disjoint.

A consequence of this choice is documented in Chapter 6: a class absent
from the validation split cannot be emitted by the stack, however
confidently a base model predicts it.

## 5.7 Bitemporal change detection

Two bitemporal methods are compared:

| Method | Type |
|---|---|
| Post-classification comparison (PCC) | Indirect — classify both dates, difference |
| NDVI differencing | Spectral — threshold the index change |

A third, a direct Siamese comparison, was specified but not run (E5,
§5.6). The comparison below is therefore between an indirect and a
spectral method only.

**PCC is expected to be the method to beat rather than to trust.** It
accumulates error from both dates: if each map is 90% accurate, the change
map is approximately 81% accurate, because an error at either date becomes
a spurious change. This is the standard argument for direct methods.
With E5 not run, that argument is not tested against a direct method
here; what can be tested is whether PCC's accumulated error is visible in
its own output, and Chapter 6 reports that it is.

The classifier used for PCC is trained on 2024 labels and applied to the
1990 composite. This is deliberate and follows from the two-regime design
(§4.4): Hansen's baseline is 2000, no 1990 label exists, and none can be
manufactured. The model transfers in time across composites harmonised to
a common radiometric basis. That transfer is an assumption, and its
magnitude is what the 2000–2024 overlap comparison measures.

The NDVI differencing threshold is set at **2σ below the mean NDVI change
of stable forest**, calibrated on Hansen-labelled stable-forest pixels
inside the training blocks. Two standard deviations rather than Otsu,
because Otsu assumes a bimodal histogram and over a district that is 87%
non-forest the histogram is not bimodal. Calibrating on the reference
sample instead would tune the method on the data intended to judge it.

Change is reported in four classes — no change, forest loss,
forest-to-plantation, and gain — rather than as a binary mask. Collapsing
forest-to-plantation into "no change" would conceal exactly the conversion
that RQ3 exists to expose.

## 5.8 Temporal segmentation

Bandarban requires a method that a pair of dates cannot provide.
**LandTrendr** temporal segmentation is applied to the annual NBR series,
1988–2024.

NBR responds more sharply to canopy removal than NDVI and saturates less
over dense tropical canopy. The series is **negated before segmentation
and the fitted values negated afterwards**, because LandTrendr expects
disturbance to appear as an increase; fed the raw series it segments
perfectly well and labels every recovery as a disturbance.

Each pixel is then classified from its fitted trajectory:

- **Permanent conversion** — a drop of at least 0.20 NBR that does not
  recover
- **Cyclical disturbance** — a drop that regains at least 70% of its
  magnitude
- **Undetermined** — a drop occurring within 6 years of the series end

The 70% recovery threshold rather than full recovery: a regrown *jhum*
fallow is younger secondary forest whose NBR sits below the mature canopy
it replaced, so requiring complete recovery would classify most genuine
swidden as permanent.

The **undetermined** class exists because the alternative is dishonest. A
plot cleared in 2022 has not had time to regrow by 2024 and looks
identical to permanent conversion; folding it into the permanent class
would inflate the headline deforestation figure with fallows that have
simply not returned yet. This is an irreducible limitation of a series
ending in 2024, and the appropriate response is to quantify it rather than
to choose a side.

## 5.9 Accuracy assessment and area estimation

### Adjusted area

**Area is never reported as a pixel count.** A pixel count is a biased
estimator of area whenever the map contains any error, and the bias does
not diminish with more pixels. All areas are reported through the
**Olofsson et al. (2014) stratified estimator** with 95% confidence
intervals.

The estimator combines each stratum's reference composition by that
stratum's map weight, where weights derive from map pixel counts. This is
what permits sample reduction without invalidating the estimate: reducing
points per stratum widens the interval and changes nothing else.

The implementation passes 15 internal consistency checks, including
agreement with hand-computed values on a synthetic confusion matrix.

### Metrics

**Overall accuracy is not the headline metric for change detection.** The
change class is a small minority — 0.22% of pixels in two districts — so a
model predicting "no change" everywhere achieves 99.8% overall accuracy
while detecting nothing. The headline metric is **F1 on the change class**;
overall accuracy is reported for completeness and interpreted accordingly.

### Inter-interpreter agreement

Cohen's κ is computed between authors on the doubly interpreted points,
against a target of 0.75. Where κ falls below that threshold,
reconciliation is conducted jointly on the disagreements only, both
original interpretations are retained, and the pre-reconciliation κ is
reported alongside the reconciled sample.
