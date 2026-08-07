# Chapter 8 — Discussion

## 8.1 Model choice matters more as landscape complexity rises

The central claim of this thesis is supported, and the mechanism by which
it holds is more specific than the claim itself.

No single model won across all three districts. The stacked ensemble won
in Gazipur and Bandarban; the U-Net won in Sylhet. Random Forest — the
cheapest model by a wide margin — beat the U-Net outright in Gazipur.

The determining variable is not district complexity in the abstract but
**the interaction between the structure of the class being detected and
the information the model can see**:

- Where classes are spectrally distinct and labelled data is scarce, a
  per-pixel model is sufficient and better. Gazipur, with 55 training
  patches, is that case.
- Where the confusion is **structural rather than spectral**, spatial
  context is decisive. Tea plantation is defined by planted rows, uniform
  canopy and geometric boundaries — none of which exist for a per-pixel
  model. Random Forest scored 0.0286 on plantation; the U-Net scored
  0.4520 on the same data.
- Where the difficulty is **temporal**, no bitemporal model of any
  architecture is adequate. Bandarban's answer came from LandTrendr, not
  from the best classifier.

The practical implication is that "which model is best" is the wrong
question. The useful question is which property of the target class is
carrying the signal — spectral, spatial, or temporal — and only the third
of these is invisible to every model considered here.

## 8.2 Ensembles inherit the coverage of their meta-training set

E7 scored 0.0000 on plantation while the U-Net inside it scored 0.4520.

This was not a failure of stacking as a technique. The meta-learner is
fitted on the validation split, and the spatial constraint that made RQ3
answerable at all — pinning both tea blocks to training and test — left
validation with no plantation examples. A class the meta-learner never
observes cannot appear in its output, regardless of how confidently a base
model argues for it.

The general lesson is worth carrying beyond this study. **A stacked
ensemble can be strictly worse than its own best member on a rare class
confined to few spatial blocks.** Where classes are spatially clustered
and the sampling unit is a block rather than a pixel, meta-learner class
coverage must be checked explicitly; it is not implied by the base models
having seen the class.

## 8.3 Plantation mapping is genuinely unsolved, and this study measured it four ways

RQ3 asked whether texture resolves the natural-forest/tea confusion. The
answer is that it helps materially — plantation F1 rising from 0.3696 to
0.4520 — but does not resolve it. Roughly 55% of plantation pixels remain
misclassified.

More significant than the number is the accumulated evidence that this
confusion is hard in a way that is not usually documented. Four
independent measurements point the same way:

**1. Sub-metre manual digitisation carries an 83% error.** A polygon
digitised as 1,906 ha of tea against sub-metre imagery was found on
independent review to be approximately 1,600 ha of hill forest, and was
corrected to 321 ha. It was caught only because it was checked.

**2. Open data does not exist.** A global plantation database omits
Bangladesh entirely. Rendered global forest-cover tiles return 0.00%
coverage over Sylhet while returning 83% over Sumatra and 19% over Assam.
OpenStreetMap contains one relevant polygon district-wide. Public
gazetteers resolve one estate in nineteen under strict name matching.
Global land-cover products have no plantation class at all.

**3. A purpose-built texture detector failed under validation.** An FFT
periodicity and Hough line detector, designed to find the planted-row
signature at sub-metre resolution, returned forest 4.36 against tea 4.27
with p = 0.55 — no separation. The negative result is reported because it
bounds what is achievable at that resolution over this landscape.

**4. Two trained interpreters agreed at chance level.** Cohen's κ of
0.038 in Sylhet and 0.157 in Gazipur, over 280 shared points, against a
0.75 target.

Taken together these place the classification results in context. A model
achieving 0.45 F1 on a class that expert human interpreters cannot agree
on, and for which no reference dataset exists anywhere, is a different
kind of result from one achieving 0.45 on a well-defined class. This is
also why the plantation problem persists in regional forest statistics:
the ground truth required to fix it has not been assembled.

## 8.4 What the κ result actually means

Two interpreters, working from the same written protocol over the same
points, disagreed on 101 of 180 Sylhet points, with 75 of those
disagreements running in a single direction.

Three readings are possible and they are not mutually exclusive.

**The protocol was underspecified.** The written definition — canopy ≥30%
at the observation date, excluding homestead gardens and village tree
cover — is unambiguous as prose and ambiguous in application. Bangladesh's
homestead vegetation is dense, evergreen and structurally forest-like at
30 m; deciding where it stops being "village tree cover" is a judgement
the protocol delegated without constraining.

**The scale of presentation influenced the judgement.** Reference chips
were 1.5 km wide while the judgement concerns a single 30 m pixel. In a
predominantly forested scene the eye reads the scene. This was observed
directly: an initial Bandarban pass returned natural forest for all 240
date-judgements, which is impossible in a district containing towns and
two major rivers, and required explicit zoom-level correction.

**The landscape is genuinely ambiguous.** A homestead grove, a young
plantation and a degraded natural forest patch can be near-identical at
30 m, and the true class may not be recoverable from imagery alone.

The methodological conclusion is that **inter-interpreter agreement should
be measured early and treated as a gate rather than as a reported
statistic**. Had κ been computed after the first hundred points, the
definitional divergence would have cost an afternoon. Computed at the end,
it invalidates the accuracy assessment until reconciliation.

That this study reports a failing κ rather than omitting it is a
deliberate choice. An unreported κ is indistinguishable from an
unmeasured one.

## 8.5 Bitemporal change detection is weak here, and the reason is structural

Change-class F1 did not exceed 0.36 for any bitemporal method in any
district. NDVI differencing beat post-classification comparison
everywhere, by a factor of 2.6 where the reference sample was large
enough to resolve it.

PCC's failure mode is visible in its raw output: 21.8% apparent forest
gain in Gazipur and 27.2% in Bandarban. Regrowth on that scale did not
occur. The classifier was trained on 2024 and applied to 1990, and its
systematic under-classification of forest on the older composite
reappeared as spurious gain — precisely the error accumulation that makes
PCC theoretically inferior, observed directly rather than argued.

Two considerations qualify these numbers. First, sample size: with 2, 7
and 18 reference change points, the F1 values support a ranking and not a
magnitude. Second, and more fundamentally, **change-class F1 may be the
wrong metric for a landscape where the change class is itself contested**.
Where two interpreters cannot agree on the state of a pixel at a single
date, the derived change label inherits both disagreements.

## 8.6 Cyclical disturbance and the limits of two dates

The Bandarban result is the clearest methodological finding in the study.

Of 88,122 ha disturbed since 1988, only 16.4% is permanent conversion.
**A bitemporal comparison would have reported approximately four times
the deforestation that occurred**, because a fallow plot in a swidden
rotation is scored as loss, as gain, or as no change depending only on
where the two observation dates fall in the cycle.

No improvement in classification accuracy addresses this. The error is in
the temporal design, and it is corrected only by observing the trajectory.
The independently interpreted sample attributes 95.3% of tagged
disturbance to cyclical processes against LandTrendr's 79.5% — the same
conclusion at a different magnitude, which is directional support rather
than validation given that 76 of 120 points carry no tag.

The finding has consequences beyond this thesis. Deforestation statistics
for shifting-cultivation landscapes derived from date-pair comparison
should be treated as upper bounds, and the *jhum* fraction is large enough
that the distinction is not a rounding correction.

### The undetermined class

Pixels disturbed within six years of the series end are reported
separately rather than assigned. A plot cleared in 2022 has not had time
to regrow and is indistinguishable from permanent conversion; assigning it
would inflate the headline figure with fallows that have not yet returned.
It amounts to 19.8% of disturbance — too large to absorb silently, and an
irreducible property of a series ending in 2024.

## 8.7 Published harmonisation coefficients did not transfer

Roy et al. (2016) ETM+-to-OLI coefficients performed **worse than applying
no correction at all** on this data: held-out residual 0.01680 against
0.01582 raw. Locally fitted coefficients achieved 0.01433.

Two bands were left untransformed as a direct consequence. NIR and SWIR2
were degraded by 8.5% and 69.8% respectively by the published
coefficients, and NBR — the index on which the entire Bandarban result
rests — is computed from exactly those two bands.

The general point is that harmonisation coefficients are fitted over
particular landscapes and atmospheres and their transferability is an
empirical question. Testing them cost one script. Adopting them on
authority would have propagated a measured degradation into the study's
most important index, invisibly.

## 8.8 Limitations

**Reference sample size.** The reduced design produced forest-loss
intervals that include zero in two of three districts. Only Bandarban's
estimate is statistically distinguishable from no change.

**Inter-interpreter agreement below threshold.** κ of 0.038 and 0.157.
All reference-based accuracy figures are provisional pending
reconciliation.

**Plantation layer incomplete.** Approximately 1,300 ha digitised against
a reported district total exceeding 10,000 ha. Tea outside the drawn
polygons is labelled natural forest, so the Sylhet confusion is reduced
rather than eliminated, and plantation results are bounded accordingly.

**Plantation test estimate spatially pseudo-replicated.** Sylhet's tea
falls in 4 of 48 blocks, two holding 99.8%. The test estimate rests on a
single 10 km block; 581 ha of one estate complex is not a sample of
Bangladesh's tea, and the interval understates true uncertainty.

**Single seed for deep models.** E3, E4 and E7 were run once. Single runs
are not evidence of a mean, and the district-level differences in §6.3
should be read with that in mind — although the E3/E4 texture difference
is supported by its specificity to the plantation class rather than by
replication.

**Water class definitional mismatch.** Water F1 is 0.000 in every
district. The map's water class is JRC occurrence ≥50%, meaning permanent
water, while interpreters recorded seasonal river channels and haor
margins as water at the observation date, which the class definition asks
of them. This is a mismatch between a permanence-based map class and a
date-based reference class, not a detection failure, and it should not be
reported as one.

**Bandarban land-cover accuracy unresolved.** The map classifies 93 of
120 reference points as non-forest where the reference records 108 as
natural forest, giving overall agreement of 0.233. Two explanations fit —
residual over-calling of forest by the interpreter, or genuine
under-mapping by Hansen in a swidden landscape where the 2000 baseline
catches plots that have since regrown — and this study cannot separate
them.

**Pre-2000 transfer unquantified.** The two-regime design assumes a
classifier trained on 2024 transfers to 1990. The overlap comparison that
would quantify this was not completed.

## 8.9 Future work

The single highest-value next step is **not** a better model. It is a
reference dataset for Bangladeshi tea plantation. Every plantation result
in this study is bounded by a hand-digitised layer covering roughly an
eighth of the district's tea, and no open alternative exists. That
boundary set would unblock work well beyond this thesis.

Second: **reconciliation and re-measurement of κ**, followed by
recomputation of all reference-based figures. The disagreement structure
identified in §6.7 is a single-axis definitional divergence and is
correctable.

Third: extension of the LandTrendr separation to Sylhet, where gradual
degradation is likely to be as poorly served by date-pair comparison as
cyclical disturbance was in Bandarban, for different reasons.

Fourth: multi-seed replication of the deep-learning experiments, and the
2000–2024 overlap comparison that would convert the pre-2000 uncertainty
from a stated assumption into a measured quantity.
