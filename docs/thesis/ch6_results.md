# Chapter 6 — Results

> **Status note.** Figures in §6.5 and §6.6 depend on the reference
> sample, for which inter-interpreter agreement currently falls below the
> Gate 4 threshold (§6.7). They are reported here as **provisional** and
> must be recomputed after reconciliation. Sections 6.1–6.4 depend on no
> reference data and are final.

## 6.1 Data availability and spatial partitioning

The scene audit evaluated 120 district-years with zero failures. From
1988 onward, every year in Gazipur and Sylhet and all but one in
Bandarban supports an annual composite. Bandarban's longest gap is a
single year (1991), which is what makes temporal segmentation viable
there (§6.4).

Block assignment achieved the following shares:

| District | Split | Blocks | Area share | Forest-loss share |
|---|---|---|---|---|
| Gazipur | train | 21 | 0.706 | 0.650 |
| | val | 3 | 0.136 | 0.185 |
| | test | 3 | 0.159 | 0.165 |
| Sylhet | train | 31 | 0.732 | 0.631 |
| | val | 10 | 0.135 | 0.224 |
| | test | 7 | 0.133 | 0.145 |
| Bandarban | train | 45 | 0.697 | 0.696 |
| | val | 11 | 0.149 | 0.153 |
| | test | 8 | 0.154 | 0.151 |

Bandarban's shares track the 70/15/15 target closely. Gazipur and Sylhet
deviate more on the loss dimension, which is expected: with loss at 0.22%
of pixels, it is concentrated in few blocks and cannot be divided finely.
Sylhet deviates furthest (train 0.631 against 0.700) because two blocks
are pinned by the plantation constraint (§5.5) and are therefore not
available to the balancing pass. That is the accepted cost of making RQ3
answerable.

Patch extraction yielded 706 patches at 128 × 128 pixels, with zero
fetch failures.

## 6.2 Random Forest baseline and the value of terrain (E1/E2)

Three seeds per configuration. Accuracy here is against **Hansen-derived
training labels**, so these are pipeline comparisons rather than accuracy
measurements; the comparison between E1 and E2 is the point.

| District | Exp | Features | Macro F1 | Forest F1 | Plantation F1 |
|---|---|---|---|---|---|
| Gazipur | E1 | 20 | 0.7805 ± 0.0009 | 0.7154 | — |
| | E2 | 23 | **0.7979** ± 0.0009 | 0.7309 | — |
| Sylhet | E1 | 20 | 0.7676 ± 0.0020 | 0.6430 | 0.7932 |
| | E2 | 23 | **0.7883** ± 0.0019 | 0.6622 | **0.8103** |
| Bandarban | E1 | 20 | 0.7431 ± 0.0081 | 0.6775 | — |
| | E2 | 23 | 0.7359 ± 0.0013 | 0.6798 | — |

**Terrain helps where terrain carries information.** Gazipur gains
+0.0174 macro F1 and Sylhet +0.0207, both an order of magnitude larger
than the seed spread. Bandarban shows −0.0073, within seed noise.

The pattern is interpretable rather than incidental. In Sylhet,
`elevation` is the single most important feature (0.158) — tea estates
occupy hill slopes, so elevation is a genuine discriminator between
plantation and the surrounding floodplain. In Bandarban, where
essentially the whole district is hilly, terrain carries no discriminating
information and adding it does nothing.

Sylhet's plantation F1 of 0.79–0.81 confirms that tea **is** spectrally
separable when a model is given balanced examples of it. Note that this
figure comes from a stratified pixel draw of 4,000 per class and is not
comparable to the patch-based figures in §6.3, where class 2 appears at
its true 0.108% prevalence.

## 6.3 Deep learning and the ensemble (E3/E4/E7)

Single seed, 60 epochs, GPU. Scored against training labels.

| District | RF | U-Net (E3) | Soft vote | E7 stacked |
|---|---|---|---|---|
| Gazipur | 0.4125 | 0.3157 | 0.3224 | **0.4443** |
| Sylhet | 0.5028 | **0.5895** | 0.5450 | 0.5187 |
| Bandarban | 0.4632 | 0.4607 | 0.4688 | **0.4754** |

*Macro F1 on patch test pixels.*

**The best model differs by district**, which is the answer to RQ2. The
ensemble wins in Gazipur and Bandarban; the U-Net wins in Sylhet.

### Why Random Forest beats U-Net in Gazipur

Gazipur has **55 training patches**. Sylhet has 167 and Bandarban 260.
The ordering of RF against U-Net follows the training-set size exactly:
RF wins decisively at 55 patches (0.4125 against 0.3157), loses at 167
(0.5028 against 0.5895), and ties at 260 where the classes are already
near-balanced.

This sharpens the RQ2 model-choice finding into a cost trade-off: deep
learning is not uniformly superior; it is superior where there is enough
labelled data to fit it. Below that threshold the cheaper model is not
merely competitive — it is better, and it costs a fraction of the
compute.

### Why the ensemble loses in Sylhet

E7 scores **0.0000 on plantation** while the U-Net inside it scores
0.4520. The stack discarded the one component that was working.

The cause is structural, not a defect of stacking. The meta-learner is
fitted on the validation split (§5.6), and pinning both tea blocks to
training and test leaves validation with **no class 2 at all**. A class
the meta-learner has never observed cannot be emitted, however
confidently a base model argues for it.

This is a general property worth stating: **stacked ensembles inherit the
class coverage of their meta-training set.** On a rare class confined to
few spatial blocks, a stack can be strictly worse than its own best
member.

## 6.4 Texture and the plantation confusion (RQ3)

The E3/E4 ablation removes the three GLCM texture bands, holding
everything else constant.

| Run | non-forest | natural forest | **plantation** | water | Macro F1 |
|---|---|---|---|---|---|
| E3, with texture (23 bands) | 0.9389 | 0.3163 | **0.4520** | 0.6508 | 0.5895 |
| E4, no texture (20 bands) | 0.9368 | 0.3172 | **0.3696** | 0.6244 | 0.5620 |

**Texture improves plantation F1 from 0.3696 to 0.4520 — a gain of
0.0824, or 22% relative.**

The specificity of the effect is what makes it credible. The macro
improvement is +0.0275, and almost all of it is the plantation class: the
other three classes move by less than 0.03, and natural forest moves by
0.001 in the *opposite* direction. That is precisely the shape the
hypothesis predicted — texture should help where the confusion is
structural rather than spectral, and it does, there and essentially
nowhere else.

The comparison is only possible because of the split correction described
in §5.5. Run against the original assignment, both configurations returned
plantation F1 of exactly 0.0000, and the ablation compared two models
neither of which had ever seen the class in question.

### Random Forest on plantation

Random Forest scores **0.0286** on plantation in the patch-based
comparison against the U-Net's 0.4520 — a reversal of the overall
ordering. Tea is a *spatial* pattern: planted rows, uniform canopy,
geometric boundaries. A per-pixel model has no access to any of it. This
is the clearest single demonstration in the study that the appropriate
model depends on the structure of the class being detected.

### What RQ3's answer does not rest on

Both figures above are scored against Hansen-derived training labels.
A 40-point stratum was drawn inside the tea-growing upazilas specifically
to validate them against independent interpretation, and both authors
interpreted it. They agreed on 12 of 40 points, κ = 0.067 (§6.7).

**That stratum is therefore not used here.** A reference sample whose two
interpreters agree at chance cannot act as an independent yardstick, and
reporting an accuracy figure against it would dress a disagreement up as
a measurement. RQ3's answer is a controlled model-side comparison — E3
against E4, architecture and data held constant — and it is reported as
exactly that, with no independent validation behind it. The stratum's
failure is not a gap in the experiment; it is reported in §7.3 as
evidence about the class itself.

## 6.5 Cyclical versus permanent disturbance (RQ4)

LandTrendr segmentation of the annual NBR series, 1988–2024, at 30 m over
Bandarban:

| Class | Area | Share of district |
|---|---|---|
| Stable | 371,380 ha | 80.8% |
| Permanent conversion | **14,457 ha** | 3.15% |
| Cyclical disturbance | **56,235 ha** | 12.24% |
| Undetermined (post-2018) | 17,431 ha | 3.79% |

Of 88,122 ha disturbed since 1988, **16.4% is permanent conversion and
63.8% is cyclical *jhum***, with 19.8% undetermined because it occurred
too near the series end to judge recovery.

**A bitemporal comparison would have reported roughly four times the
deforestation that actually occurred.** This is the finding the third
district was added to produce, and it is the empirical content of the
rule that no Bandarban loss figure may be reported without this split.

A 300 m preliminary run gave 25%/67%/8% over 31,468 ha. Resolution
changes the magnitudes substantially — coarse pixels miss small clearings
and blur the recovery signal — so the 30 m figures supersede it. What
survives both is the conclusion.

### Reference agreement

The independently interpreted sample attributes **95.3%** of tagged
disturbance to cyclical processes, against LandTrendr's 79.5%. Same
direction, same conclusion, different magnitude.

This is **directional support rather than validation**: 76 of 120
Bandarban points carry no cyclical/permanent tag and 4 carry both.

## 6.6 Accuracy against the reference sample — provisional

*400 interpreted points. See §6.7 before using these figures.*

### Adjusted area, 2024

| District | Natural forest | Non-forest | Water |
|---|---|---|---|
| Gazipur | 45,530 ± 25,723 ha | 134,252 ha | — |
| Sylhet | 41,681 ± 23,420 ha | 254,993 ha | 27,947 ha |
| Bandarban | 365,272 ± 43,291 ha | 73,620 ha | 20,518 ha |

Bandarban's non-forest estimate of 73,620 ha sits close to the map's
70,448 ha, an agreement at the aggregate level that the earlier
interpretation passes did not achieve.

### Forest loss, 1990–2024

| District | Adjusted loss | Reference change points |
|---|---|---|
| Gazipur | 443 ± 849 ha | 2 |
| Sylhet | 5,547 ± 10,755 ha | 7 |
| Bandarban | **71,011 ± 41,629 ha** | 18 |

**Only Bandarban's interval excludes zero.** Gazipur and Sylhet rest on 2
and 7 reference change points respectively, and at that sample size no
statistically significant loss is detectable at the 95% level.

This is the quantified cost of the reduced design, and it must be reported
as it stands. A related observation is independently informative: Gazipur
drew 40 points from the over-sampled forest-loss stratum, and the
interpreter judged only 2 to be genuine forest-to-non-forest transitions.
That is a statement about **Hansen commission error**, and it is arguably
more interesting than the loss figure would have been.

### Change detection accuracy (supporting finding, not a standalone RQ — see §1.4)

F1 on the change class — the headline metric, since overall accuracy is
uninformative for a minority class:

| District | PCC | NDVI differencing | n reference loss |
|---|---|---|---|
| Gazipur | 0.000 | 0.000 | 2 |
| Sylhet | 0.000 | 0.148 | 7 |
| Bandarban | 0.138 | **0.357** | 18 |

**NDVI differencing equals or beats PCC in every district**, and by a
factor of 2.6 in Bandarban where the reference sample is large enough to
resolve the difference. This is the direction predicted in §5.7 and for
the stated reason: PCC accumulates error from both dates, and two maps
agreeing with the reference at approximately 0.55 overall cannot yield a
reliable change map between them.

PCC's raw output makes the mechanism visible. It reports **21.8% forest
gain in Gazipur and 27.2% in Bandarban** — implausible as regrowth, and
attributable to systematic under-classification of forest on the 1990
composite by a model trained on 2024, reappearing as apparent gain.

The caveat is severe and travels with the result: at 2, 7 and 18 change
points these values carry very large sampling uncertainty. They support a
**ranking**, weakly. They do not support claims about magnitude.

## 6.7 Inter-interpreter agreement

Cohen's κ on class at T3, against a Gate 4 threshold of 0.75:

| Sample | Compared points | Raw agreement | κ |
|---|---|---|---|
| Gazipur | 100 | 0.500 | **0.157 ± 0.165** |
| Sylhet | 180 | 0.439 | **0.038 ± 0.124** |
| Sylhet plantation stratum | 40 | 0.300 | **0.067 ± 0.189** |

All three fall far below the threshold, and the two Sylhet figures are
indistinguishable from chance.

The plantation stratum is reported separately rather than folded into
Sylhet because it is a different sample with a different prevalence: its
40 points were drawn deliberately inside the tea-growing upazilas, so
agreement there measures agreement *on tea* rather than on the district
as a whole. It is the lowest of the three. One interpreter called 25 of
the 40 points plantation; the other called 14, and called 20 of them
natural forest. **The stratum is therefore not used to validate RQ3** —
a reference sample the interpreters cannot agree on cannot serve as an
independent yardstick, and using it anyway would put a number on RQ3 that
looks like validation without being one. The consequence is stated in
§6.4: RQ3's result is a model-side comparison only.

The disagreement is systematic rather than random, and its structure is
informative. Of Sylhet's 101 disagreements, **75 run in a single
direction** — one interpreter reads natural forest where the other reads
non-forest.

Critically, **the direction reverses between districts**:

| | Interpreter A | Interpreter B | Map |
|---|---|---|---|
| Gazipur natural forest | 45,530 ha | 117,795 ha | 12,988 ha |
| Sylhet natural forest | 245,979 ha | 41,681 ha | 27,597 ha |

Neither interpreter carries a consistent bias. The forest/non-forest
boundary is being resolved independently at each point rather than from a
fixed rule, and in each district one of the two readings makes a densely
populated agricultural landscape two-thirds natural forest.

The immediate consequence is that §6.6 is provisional. The wider
significance is discussed in Chapter 7: two trained interpreters working
from the same written protocol over the same 280 points agreed at
essentially chance level on where forest begins, which is a measurement
of how hard this landscape is to interpret rather than a procedural
failure.
