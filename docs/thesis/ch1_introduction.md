# Chapter 1 — Introduction

## 1.1 Background

Bangladesh has one of the lowest per-capita forest areas in the world and
one of the highest population densities. The pressure this places on
remaining forest is not uniform. It arrives as urban and industrial
expansion around Dhaka, as agricultural encroachment and plantation
conversion in the northeast, and as shifting cultivation in the hill
tracts of the southeast — three processes that differ not only in cause
but in their *observable structure*.

That difference matters for measurement. Satellite-based forest
monitoring has become the standard instrument for national and
sub-national forest reporting, and the methods in common use were largely
developed and validated over landscapes where forest loss is abrupt,
permanent, and spectrally unambiguous. Where those conditions hold, the
methods work well. Where they do not, the failure is often silent: a map
is produced, an area is reported, and nothing in the output indicates
that the method was answering a different question from the one asked.

This thesis is concerned with those silent failures, and with the
conditions under which the choice of method stops being a matter of
marginal accuracy and starts determining whether the result is meaningful
at all.

## 1.2 The problem

Three specific difficulties motivate this study, each of which is present
in Bangladesh and each of which defeats a standard assumption.

**Spectral ambiguity between forest and plantation.** Tea plantation and
natural forest are both dense and evergreen, and at 30 m resolution they
are spectrally similar. A classifier that cannot separate them reports
plantation expansion as forest stability, and reports natural forest
cleared for tea as no change. Regional forest statistics inherit that
error without any indication in the output that it occurred.

**Village tree cover that is not forest.** Homestead gardens, betel and
areca in Bangladesh are dense, green, and structurally forest-like at
Landsat resolution, but they sit over settlement and are not forest under
any canopy-plus-land-cover definition. The distinction depends on reading
settlement pattern rather than greenness.

**Cyclical disturbance that is not deforestation.** In shifting
cultivation, land is cleared, cropped, abandoned, and allowed to regrow
over roughly five to seven years. A comparison between two fixed dates
cannot distinguish a fallow plot mid-rotation from permanently converted
land. The same ground yields "loss", "gain", or "no change" depending
only on where the two observation dates fall in the cycle — and no
improvement in classification accuracy corrects this, because the error
lies in the temporal design rather than in the classifier.

Each of these is well known in isolation. What is less established is how
much the *choice of method* matters as they accumulate, and whether the
methods that perform best on simple landscapes remain the right choice on
complex ones.

## 1.3 Aim

This study measures forest cover change in three districts of Bangladesh
between 1988 and 2024 using Landsat imagery, and compares traditional
machine learning, deep learning, and temporal segmentation approaches
across landscapes chosen to differ in exactly the ways described above.

The districts — Gazipur, Sylhet and Bandarban — were selected because
each contributes a different loss mechanism: abrupt permanent conversion,
gradual degradation with plantation confusion, and cyclical clearing with
regrowth. A finding that holds across three mechanisms is considerably
harder to dispute than one established on a single landscape, and a
method that succeeds on one and fails on another has told us something
specific about where it should be deployed.

## 1.4 Research questions

1. **To what extent, and in what spatial patterns, has forest cover
   changed** across Gazipur, Sylhet and Bandarban between 1988 and 2024
   — and what does this variation reveal about the relationship between
   landscape type and dominant loss mechanism?

2. **How does the comparative performance of Random Forest and U-Net
   vary** across landscapes of differing spectral and spatial
   complexity, and what does this reveal about the relationship between
   a target class's discriminating signal and the model architecture
   needed to detect it?

3. **To what extent does incorporating GLCM texture features improve
   discrimination** between natural forest and tea plantation in Sylhet,
   and what does the isolated contribution of texture reveal about the
   spatial versus spectral nature of the confusion?

4. **To what extent can annual temporal segmentation distinguish
   cyclical *jhum* disturbance from permanent forest conversion** in
   Bandarban, in a setting where bitemporal comparison structurally
   cannot?

RQ4 is the question the third district exists to answer. Without it,
Bandarban contributes additional area to the same result rather than a
distinct test.

Two further comparisons are reported in Chapter 6 as supporting findings
rather than standalone research questions: change-detection method
choice (post-classification comparison versus NDVI differencing), and
the accuracy/cost trade-off between traditional machine learning and
deep learning. Both were originally scoped as separate research
questions alongside a direct Siamese-network comparison; the
Siamese-network run was not completed, so a fair three-way comparison
was never possible, and the two questions were folded into the
discussion of RQ2 rather than left as numbered questions with an
incomplete answer.

## 1.5 Scope and boundaries

**Imagery.** Analysis uses Landsat Collection 2 Level-2 surface
reflectance accessed through Google Earth Engine. High-resolution
commercial imagery is used only for visual interpretation of the
validation sample and never as model input.

**Period.** 1988 to 2024, with epoch anchors at 1990, 2000, 2010 and
2024. The start year follows from an audit of scene availability rather
than from convenience: no usable imagery exists over Bangladesh before
1988.

**Definition.** Forest is ≥30% canopy cover at the observation date. This
is a canopy definition, not a land-use definition, which has direct
consequences for how *jhum* fallow is classified.

**Not addressed.** This study does not model drivers of deforestation,
does not produce projections, and does not assess carbon stocks or
biodiversity. It is a measurement and methods-comparison study.

## 1.6 Contribution

The intended contributions are four.

**A three-mechanism comparison.** Most method comparisons in this domain
hold the landscape constant and vary the model. This study varies both,
which is what allows the interaction between class structure and model
capability to become visible.

**A measured answer on texture and plantation.** RQ3 is tested as a
controlled ablation — the same architecture with and without GLCM
features, everything else held constant — rather than as a comparison
between differently configured models.

**An explicit treatment of cyclical disturbance.** Deforestation figures
for the study's hill district are separated into permanent conversion and
cyclical disturbance before any headline total is reported, using the
annual trajectory rather than a date pair.

**Honest uncertainty.** Areas are reported through a stratified
estimator with confidence intervals rather than as pixel counts;
inter-interpreter agreement is measured and reported whatever its value;
and negative results — approaches that were tried and did not work — are
reported alongside positive ones, because they bound what is achievable
with the data available.

## 1.7 Thesis structure

**Chapter 2** reviews prior work on satellite forest monitoring, deep
learning for change detection, plantation discrimination, and temporal
segmentation.

**Chapter 3** describes the three study districts and the loss mechanism
each contributes.

**Chapter 4** documents the imagery, the temporal design, the forest
definition, and the construction of both the training labels and the
independent reference sample.

**Chapter 5** sets out the methodology: compositing, cross-sensor
harmonisation, feature construction, spatial partitioning, the experiment
matrix, change detection, temporal segmentation, and the accuracy and
area estimation framework.

**Chapter 6** presents results, distinguishing throughout between figures
scored against training labels and figures scored against the independent
reference sample. The accuracy assessment and adjusted area estimates are
presented there in full, in §6.6 and §6.7, rather than as a separate
chapter.

**Chapter 7** discusses what the results mean, what they do not support,
and the limitations that bound them.

## 1.8 A note on terminology

Two distinctions are maintained throughout and are easy to blur.

**Training labels versus reference sample.** Training labels derive from
existing global products and are used to fit models. The reference sample
is independently interpreted by hand and is the only basis on which
accuracy is measured. Accuracy figures computed against training labels
describe a model's agreement with its own teacher and are reported as
such, never as accuracy.

**Disturbance versus deforestation.** Disturbance is any detected loss of
canopy. Deforestation is permanent conversion. In a shifting-cultivation
landscape these differ by a factor of several, and conflating them is the
specific error this study was designed to avoid.
