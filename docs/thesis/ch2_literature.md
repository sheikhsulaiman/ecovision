# Chapter 2 — Literature Review

> **Read before submitting.** Every citation below was verified against
> the publisher record — journal, volume, pages, DOI — and none was
> written from memory. But a literature review should reflect what its
> authors have read, and you have not yet read all of these. Obtain each
> source, confirm that the claim attributed to it is the claim it makes,
> and adjust the wording where your reading differs from mine. Two
> specific corrections this drafting uncovered are recorded in §2.10 and
> **both change claims currently made in Chapters 4 and 8.**

---

## 2.1 Satellite-based forest monitoring

Landsat has been the primary instrument for multi-decadal forest
monitoring since the opening of the USGS archive in 2008 made systematic
time-series analysis practical at no cost. Its 30 m resolution and
continuous acquisition since 1972 give it a temporal depth no other
open sensor matches, which is the reason a study spanning 1988 to 2024
is possible at all.

The reference product for global forest change is the Global Forest
Change dataset of **Hansen et al. (2013)**, which mapped forest loss and
gain globally at 30 m from Landsat, reporting 2.3 million km² of loss and
0.8 million km² of gain over 2000–2012. It is updated annually and is
used in this study as the source of training labels (Ch. 4.4).

Two of its properties bear directly on how it is used here. First, its
baseline is the single year 2000; it makes no statement about forest
extent before that date, which is what necessitates the two-regime design
described in Chapter 4. Second, it is a global product calibrated
globally, and its performance in any particular landscape is an empirical
question rather than a given — a point returned to in Chapter 6, where
40 points drawn from the Hansen loss stratum in Gazipur yielded only 2
judged to be genuine forest-to-non-forest transitions.

Water is taken from the JRC Global Surface Water dataset of
**Pekel et al. (2016)**, which quantified monthly surface-water change
globally at 30 m from more than three million Landsat images over 32
years. Its `occurrence` band expresses the *frequency* with which a pixel
was water, which makes it a statement about permanence rather than about
any particular date — a distinction that turns out to matter for this
study's water class and is discussed in Chapter 7.

## 2.2 Forest definitions

"Forest" is a definitional choice rather than a natural kind, and the
choice materially changes reported area. The FAO definition combines a
canopy cover threshold, a minimum area, and a minimum tree height, and
crucially includes a **land-use** criterion: temporarily unstocked areas
expected to regenerate remain forest.

That land-use criterion is precisely what this study does *not* adopt.
The definition used here is canopy cover ≥30% **at the observation date**
(Ch. 4.3), which is a land-cover definition. The consequence is
deliberate: a shifting-cultivation plot cleared and cropped is non-forest
at that date, and the same plot regrown past 30% canopy is forest, and
both statements are true of the same land use. Encoding the rotation in
the class would make the class unmeasurable from imagery; recording it
separately, as this study does, keeps the two questions apart.

Reported forest area is sensitive to the threshold chosen, which is why a
10% sensitivity comparison accompanies the 30% results.

## 2.3 Classification methods

### Random Forest

**Breiman (2001)** introduced Random Forest as an ensemble of decision
trees trained on bootstrap samples with random feature subsetting at each
split. In remote sensing it has become the default baseline for land
cover classification: it handles high-dimensional, correlated feature
stacks without preprocessing, is insensitive to hyperparameter choice
over a wide range, and produces feature importances that are directly
interpretable.

Its limitation for this study is structural rather than statistical. A
Random Forest classifies each pixel from that pixel's own feature vector
and has no access to spatial context. Where a class is defined by its
*arrangement* — planted rows, uniform canopy, geometric boundaries —
that information is unavailable to it in principle. Chapter 6 reports
this directly: Random Forest scores 0.0286 on plantation where a
convolutional model scores 0.4520 on identical data.

### Convolutional segmentation

**Ronneberger et al. (2015)** introduced U-Net for biomedical image
segmentation: a symmetric encoder–decoder with skip connections that
preserve spatial detail lost in downsampling. It has since become the
standard architecture for semantic segmentation of remote sensing
imagery, where the same requirement — dense per-pixel prediction with
both local detail and wider context — applies.

Encoder pretraining is central to its use on small labelled datasets. An
encoder pretrained on ImageNet transfers low-level feature detectors that
would otherwise have to be learned from scratch, which matters acutely
here: the districts in this study yield 55, 167 and 260 training patches
respectively. The relationship between labelled-set size and the point at
which deep learning overtakes a classical baseline is the subject of RQ5.

### Ensemble and stacking

Stacked generalisation combines base learners through a meta-learner
trained on their outputs. The approach is most effective where base
models make *uncorrelated* errors, which is the situation here: a
per-pixel model and a convolutional model fail on different things.

The literature is less explicit about a constraint this study encountered
and reports in Chapter 7 — that a stacked ensemble inherits the class
coverage of its meta-training partition, and can therefore be strictly
worse than its own best member on a class absent from that partition.

## 2.4 Change detection

The standard taxonomy separates **post-classification comparison**,
**image differencing**, and **direct** methods.

**Post-classification comparison** classifies each date independently and
differences the resulting maps. Its appeal is that it requires no
radiometric consistency between dates and yields a labelled from–to
transition. Its defect is well established: it accumulates error from
both classifications, so two maps at 90% accuracy produce a change map of
approximately 81%, and errors at either date appear as spurious change.
This is the standard argument for direct methods, and Chapter 6 reports
it observed rather than argued — PCC's apparent 21.8% and 27.2% "forest
gain" in two districts is the accumulated error made visible.

**Index differencing** thresholds the change in a spectral index between
dates. Threshold selection is the operative question. Otsu's method is
commonly used but assumes a bimodal histogram; over a district that is
87% non-forest that assumption does not hold, which is why this study
sets its threshold at 2σ from the stable-forest distribution instead
(Ch. 5.7).

**Direct methods** compare the two dates within a single model rather
than comparing two independent outputs. **Daudt et al. (2018)** proposed
three fully convolutional architectures for this — early fusion, and two
Siamese variants that difference or concatenate features extracted by
shared-weight encoders. FC-Siam-diff is the basis of the E5 configuration
in this study.

Benchmark datasets for direct change detection (LEVIR-CD, OSCD) are
predominantly urban and very-high-resolution, which limits their direct
transfer to 30 m forest change. Their principal value here is as
pretraining sources rather than as evaluation sets.

## 2.5 Temporal segmentation

Bitemporal methods of every architecture share an assumption: that two
dates are sufficient to characterise change. Trajectory-based methods
exist because that assumption fails whenever the process is cyclical,
gradual, or ongoing.

**Kennedy et al. (2010)** introduced LandTrendr, which fits piecewise
linear segments to a yearly Landsat spectral time series, capturing both
abrupt events such as harvest and slow processes such as regrowth in a
single representation. Its implementation in Google Earth Engine has made
whole-landscape application routine.

The index choice matters. LandTrendr is commonly applied to NBR, which
responds more sharply to canopy removal than NDVI and saturates less over
dense closed canopy — both properties that matter over tropical forest.
The algorithm expects disturbance to appear as an *increase*, so an index
where disturbance decreases must be inverted before segmentation; failing
to do so produces a segmentation that runs perfectly well and labels
every recovery as a disturbance.

Alternative trajectory methods include BFAST, which decomposes a series
into trend and seasonal components and detects breakpoints, and CCDC,
which fits harmonic models continuously and flags departures. LandTrendr
was selected here for its explicit segment-level representation of
disturbance magnitude and recovery, which is exactly the quantity needed
to separate cyclical from permanent change.

Detection of shifting cultivation from time series is the closest prior
work to this study's Bandarban analysis, and it is the area where the
literature is thinnest relative to the size of the phenomenon.

## 2.6 Plantation discrimination

This is the section with the least established prior work and the most
direct bearing on RQ3.

Evergreen plantation and natural forest are spectrally similar at 30 m:
both are dense, both are green in all seasons, and both have high NIR and
low SWIR reflectance. Separating them from spectral information alone is
therefore poorly posed, and the discriminating information — if it exists
at Landsat resolution — is structural.

**Haralick et al. (1973)** introduced grey-level co-occurrence matrix
(GLCM) texture features, which quantify the spatial arrangement of pixel
values through measures such as contrast, entropy and homogeneity. The
premise for their use here is direct: plantation has planted rows,
uniform canopy height and geometric boundaries, while natural forest is
structurally chaotic, and that difference should appear in texture even
where it does not appear in reflectance. RQ3 tests this as a controlled
ablation.

On reference data, the **Spatial Database of Planted Trees (SDPT)** of
Richter et al. is the principal global source. **Version 2.0 (2024)
covers 158 countries**, a substantial expansion over version 1.3, which
carried 43 country layers. The distinction matters for this study: the
plantation-data check reported in §7.3 was run against v1.3, and its
finding is scoped to that version accordingly.

For Bangladesh specifically, national statistics are available from the
Bangladesh Tea Board and Bangladesh Tea Association: **167 commercial tea
estates covering approximately 279,507 acres (≈113,100 ha) nationally**,
with Sylhet division the dominant producing region. These industry
figures are area statistics, not spatial boundaries, and the distinction
matters — knowing that a district contains a given area of tea does not
locate it, and a classifier cannot be trained or assessed on an
aggregate.

## 2.7 Accuracy assessment and area estimation

This is the most load-bearing methodological literature in the thesis.

**Olofsson et al. (2014)**, building on Olofsson et al. (2013), set out
good-practice recommendations for accuracy assessment and area estimation
from land change maps. The central result is that **counting map pixels
is a biased estimator of area whenever the map contains classification
error**, and that the bias does not diminish as the map grows. The
correction is a stratified estimator that combines each stratum's
reference class composition by that stratum's map-derived weight, with an
analytically derived variance permitting confidence intervals.

Three consequences shape this study's design directly:

- Areas are reported as adjusted estimates with 95% confidence
  intervals, never as pixel counts (Ch. 5.9).
- Stratum weights derive from map pixel counts rather than from the
  sample, which is what allows sample size to be reduced without
  invalidating the estimator — reducing points per stratum widens the
  interval and changes nothing else.
- Rare change classes must be deliberately over-sampled. A proportional
  sample of a landscape where change is 0.22% of pixels returns too few
  change points to support any interval worth reporting.

**Cohen (1960)** introduced κ as a chance-corrected measure of agreement
between two raters. Its use as an accuracy measure for maps has been
substantially criticised — it is sensitive to marginal distributions, its
correction for chance agreement is arguably inappropriate for map
accuracy, and Olofsson et al. explicitly recommend against reporting it
as a map accuracy statistic. That critique does not apply to the use made
of it here, which is its original one: agreement between two human
interpreters. Chapter 6 reports a failing κ and Chapter 7 interprets it.

Finally, **overall accuracy is inappropriate as a headline metric for a
minority class**. Where change is 0.22% of pixels, a map predicting "no
change" everywhere achieves 99.8% overall accuracy while detecting
nothing. Per-class F1 on the change class is reported instead.

## 2.8 Cross-sensor harmonisation

A 1988–2024 Landsat series spans TM, ETM+ and OLI. These instruments have
different spectral response functions, so identical ground returns
different reflectance, and uncorrected this produces apparent change at
every sensor transition.

**Roy et al. (2016)** is the standard reference. Using approximately 59
million corresponding 30 m observations from 6,317 ETM+ and OLI images
over the conterminous United States, they derived ordinary-least-squares
transformation functions between the sensors, reporting a mean relative
difference of about 4.73% in top-of-atmosphere reflectance — smallest in
green (0.11%) and largest in SWIR2 (13.59%).

Two features of that derivation matter for its transferability, and this
thesis tests rather than assumes it. The coefficients were fitted over
CONUS land cover and atmosphere, and the largest sensor difference falls
in SWIR2 — a band from which NBR is computed, and NBR is the index on
which this study's Bandarban result depends. Chapter 5 reports that the
published coefficients performed *worse than applying no correction at
all* on this data, and that NIR and SWIR2 were consequently left
untransformed. That departure is only defensible because the standard was
tested rather than ignored.

Separately, the Landsat 7 scan line corrector failed in May 2003,
removing roughly 22% of each subsequent ETM+ scene in wedge-shaped gaps.
With Landsat 5 retired in 2011 and Landsat 8 not delivering until 2013,
the 2012 and 2013 dry seasons over Bangladesh are served by SLC-off ETM+
alone — a constraint that determines which years can serve as epoch
anchors (Ch. 4.2).

## 2.9 Research gap

Four gaps follow from the above and define this study's contribution.

**Method comparison across loss mechanisms rather than within one
landscape.** Comparative studies typically hold the landscape constant
and vary the model. Varying both is what allows the interaction between
class structure and model capability to become visible — and it is that
interaction, rather than any single model's superiority, that this study
reports.

**Controlled ablation of texture for plantation discrimination.** Texture
features are widely included in classification stacks; their specific
contribution to the plantation/natural-forest confusion is rarely
isolated by holding architecture and all other features constant.

**Explicit permanent-versus-cyclical separation before reporting
deforestation.** Shifting cultivation is widespread and its
misattribution as deforestation is acknowledged in the literature, but
loss totals for such landscapes are routinely published from date-pair
comparison without the separation being made.

**Bangladesh-specific reference data does not exist.** National tea area
statistics exist; spatial boundaries suitable for training or assessment
do not. This bounds what any study of the region can currently achieve
and is the principal limitation reported in Chapter 7.
