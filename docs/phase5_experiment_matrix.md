---
title: "EcoVision — Phase 5: patch size and the frozen experiment matrix"
status: Gate 5 — decided, to be copied into the methods chapter
date: 2026-07-27
---

# Phase 5 — experimental design

Two things are fixed here: the patch size, and the six experiments. Both
go into Chapter 5 verbatim. **Adding an experiment after this point
requires a written reason** — scope creep back to eight models is in the
risk register, and the cut list in §5 is pre-agreed.

---

## 1. Patch size: 128 × 128 — DECIDED

**Chosen:** 128 × 128 px = 3.84 × 3.84 km at 30 m.

**Rejected:** 256 × 256, which the original plan specified.

### Why the plan's own numbers do not fit together

The plan asks for 256 × 256 patches *and* 10 × 10 km split blocks *and*
32 px overlap between patches. Measured against the real blocks from
`src/splits.py`:

| Patch | Edge | Patches per 10 km block | Total across 3 districts |
|---|---|---|---|
| 256 px | 7.68 km | **1.70** | **~236** |
| 128 px | 3.84 km | 6.78 | ~943 |

A 7.68 km patch barely fits inside a 10 km block, so patches cannot tile
with overlap without crossing the block boundary — which would break the
spatial disjointness that is the entire point of the blocks (rule 2).

The dataset size is the sharper problem. 236 patches total means roughly
**165 training patches** for a ResNet-34 U-Net. Flips and 90° rotations
give at most 8× of highly correlated variants. That is not enough to
fine-tune an ImageNet encoder without severe overfitting, and the
resulting model would tell us more about the seed than about Bangladesh.

128 px gives ~660 training patches and tiles 6× over inside a block.

### What it costs, stated plainly

Less spatial context per patch: 3.84 km instead of 7.68 km. This matters
most for **gradual, diffuse degradation in Sylhet**, where the signal is
spread over a wider area than an abrupt clearing. If E3 underperforms in
Sylhet specifically, insufficient context is a candidate explanation and
should be named as such in the discussion rather than discovered later.

**Rejected alternative — keep 256 and enlarge blocks to 20 km.** Gazipur
is only 1,819 km²; at 20 km blocks it would hold about 7 blocks total,
leaving one block each for validation and test. A single-block test set
is not a test set.

---

## 2. The experiment matrix — FROZEN

Six runs, **three seeds each**, reporting mean ± standard deviation.
Single-run numbers are not evidence.

| ID | Model | Input | Epochs used | Purpose |
|---|---|---|---|---|
| **E1** | Random Forest | Per-pixel: spectral + indices + texture | any labelled year | Accuracy floor, pipeline debug |
| **E2** | Random Forest | E1 + terrain | any labelled year | Does terrain help? |
| **E3** | U-Net (ResNet-34, ImageNet) | Full 23-band stack, single date | 2000, 2010, 2024 | Segmentation |
| **E4** | U-Net | E3 **minus** the 3 GLCM texture bands | 2000, 2010, 2024 | **Ablation: does texture solve the tea problem?** |
| **E5** | Siamese U-Net (FC-Siam-diff) | Bitemporal pairs | **post-2000 pairs only** | Direct change detection |
| **E6** | Best of E3/E5, cross-district | Full stack | as parent | Generalisation |

### E1 and E2 are done

Run 2026-07-27 on the 2024 composite, three seeds, against Hansen-derived
training labels:

| District | E1 macro F1 | E2 macro F1 | Δ | Verdict |
|---|---|---|---|---|
| Gazipur | 0.7805 ± 0.0009 | 0.7979 ± 0.0009 | +0.0174 | terrain helps |
| Sylhet | 0.8265 ± 0.0010 | 0.8346 ± 0.0012 | +0.0081 | terrain helps |
| Bandarban | 0.7431 ± 0.0081 | 0.7359 ± 0.0013 | −0.0073 | within seed noise |

Terrain helps *least* in the most mountainous district. The likely reason
is that Bandarban is 84% forest, so elevation separates little; in
Gazipur it distinguishes the flat industrial belt from remnant sal.

**These are measured against training labels, not the reference sample.**
They state how faithfully the model reproduces Hansen. Phase 8 measures
real accuracy and it will be lower.

### E5 runs on post-2000 pairs only

A consequence of the Option B two-regime decision, not an oversight.
Direct bitemporal change detection needs change labels *for that specific
pair*, and none exist before Hansen's 2000 baseline. E3 can classify the
1990 composite using weights trained on later labels — transfer in time,
not in supervision — but E5 cannot.

**Say this in the methods chapter.** An examiner comparing E5's date
range against E3's will otherwise find it themselves.

### E4 is the ablation that matters most

Texture is the stated answer to the Sylhet natural-forest versus tea
problem. Early warning from E1/E2: **no GLCM band appears in any
district's top six feature importances.** Texture may simply matter less
to a per-pixel Random Forest than to a U-Net that can see spatial
context — which would itself be a finding — but do not assume E4 will
vindicate it. A null result here is publishable and must be reported
either way.

---

## 3. Class imbalance is not one problem, it is three

Measured from `src/labels.py`, forest loss as a share of district area,
2000→2024:

| District | Loss share | Regime |
|---|---|---|
| Gazipur | 0.23% | Extreme imbalance |
| Sylhet | 0.22% | Extreme imbalance |
| Bandarban | 24.30% | Near-balanced |

The plan's Phase 6.4 assumes change pixels are 1–5%. **Gazipur and Sylhet
are five to twenty times rarer than that; Bandarban is five times more
common.** A single training recipe cannot fit both regimes.

Consequences, decided:

1. **Patch sampling is weighted toward change-containing patches in
   Gazipur and Sylhet, and left unweighted in Bandarban.** Weighting a
   near-balanced district distorts it for no gain.
2. **The test split is never weighted**, in any district. Weighting the
   test set makes the metric describe the sampler rather than the model.
3. **Dice + BCE at 0.5/0.5** as the default loss. Focal (γ=2) is the
   fallback if Dice underperforms in the two rare-change districts only.
4. **Overall accuracy is never the headline** (rule 5). At 0.22% positive
   rate, predicting "no change" everywhere scores 99.8%.

---

## 4. Cross-district transfer (E6)

Train on one district, test on another, using the best of E3/E5. Six
ordered pairs exist; run the three that answer something:

| Train → test | Question |
|---|---|
| Gazipur → Sylhet | Does a model learned on abrupt conversion detect gradual degradation? |
| Sylhet → Bandarban | Does plantation-aware training transfer to swidden? |
| Bandarban → Gazipur | Does the data-rich district generalise to the sparse one? |

This is the result most likely to be publishable, and it is also the
first thing to cut if the schedule slips.

---

## 5. Cut list, pre-agreed

If behind schedule, cut in this order:

1. E6 cross-district transfer
2. Bandarban (the whole district — it was the last added)
3. The 10% canopy sensitivity run
4. Dashboard

**Protect E1, E3, E4, E5 and the entire accuracy assessment.** A
single-district study with confidence-bounded area estimates is a good
thesis; a three-district study with pixel-counted areas is not.

---

## 6. Gate 5 checklist

- [x] Splits generated and verified spatially disjoint (`src/splits.py`)
- [x] Patch size fixed with a written reason (§1)
- [x] Experiment matrix frozen (§2)
- [x] Class-imbalance strategy decided per district (§3)
- [ ] Matrix copied into the thesis methods chapter
- [ ] Patch extraction run — blocked on the canopy threshold sign-off,
      since labels depend on it

---

## Sylhet block split regenerated, 2026-08-07

Recorded here because `data/splits/*.geojson` is committed precisely so
the test set cannot drift, and this is a deliberate exception to that.
**Gazipur and Bandarban were not touched** — their splits, patches and
results from the first Kaggle run remain valid.

### What was wrong

The first Kaggle sweep returned **plantation F1 = 0.0000 in Sylhet for
every architecture** — RF, U-Net, soft vote and the E7 stack alike.

The cause was not the models. Sylhet's training split contained **zero
plantation pixels**, and the models were then evaluated on 11,071 of
them. F1 of zero was arithmetically guaranteed.

The splits were built before the tea polygons existed and were balanced
on Hansen loss and area; plantation was never a criterion. All 1,303 ha
of hand-digitised tea falls in **4 of 48 blocks**, and two of those hold
99.8% of it — one landed in val, the other in test, leaving train with
3.1 ha (0.24%).

The consequence was worse than a bad number. **The E3/E4 texture
ablation was meaningless**: it compared two models neither of which had
ever seen the class the ablation is about. RQ3 was unanswerable and
nothing in the pipeline said so.

### What changed

`src/splits.py` now pins plantation blocks before the greedy pass:
the largest goes to **train**, the second to **test**.

Train because a class absent from training cannot be learned. Test
because a class absent from test cannot be measured. Val loses, because
its job is early stopping and a class at 0.5% of pixels was never what
selected the checkpoint.

A proportional 70/15/15 split of plantation is **not available** at 10 km
blocks — with two meaningful blocks the only choice is which two splits
get tea.

| | before | after |
|---|---|---|
| train class 2 | 0 px | 2,906 px (0.108%) |
| val class 2 | 2,906 px | 0 px |
| test class 2 | 11,071 px | 11,071 px |
| train loss share | 0.696 | 0.631 |

Balance on Hansen loss got worse — train fell from 0.696 to 0.631 against
a 0.70 target — because two blocks are now pinned rather than free. That
is the price of making RQ3 answerable, and it is the right trade: loss is
still well represented in every split, whereas plantation was not
represented at all.

### Two limitations this creates, both reportable

**The plantation test estimate rests on one 10 km block.** 581 ha of a
single estate complex is not a sample of Bangladesh's tea. This is
spatial pseudo-replication and the interval will understate true
uncertainty. State it next to the RQ3 result.

**Training still sees only 2,906 tea pixels against 11,071 at test.** The
class is under-represented in training by a factor of four, so a weak
plantation F1 after this fix is evidence about *data scarcity*, not about
whether GLCM texture separates tea from forest. Distinguish the two when
writing the RQ3 discussion.
