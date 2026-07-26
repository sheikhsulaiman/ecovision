---
title: "EcoVision — Phase 3: cross-sensor harmonisation, measured result and decision"
status: RESOLVED — Option B taken, coefficients wired into src/preprocess.py
date: 2026-07-26
---

# Decision taken

**Option B.** Local coefficients were fitted from near-coincident scene
pairs over all three districts and adopted per band, subject to a 5%
margin over doing nothing. The full reasoning that led here is preserved
below; this section records what was decided and what it rests on.

## What is applied

Transform into the OLI reference, ETM+ and TM alike:

| Band | Transform | Source | Held-out gain vs raw |
|---|---|---|---|
| blue | ×0.721504 + 0.006165 | local OLS | −33.9% |
| green | ×0.848300 + 0.008800 | Roy et al. (2016) | −12.0% |
| red | ×0.874212 + 0.005028 | local OLS | −15.6% |
| nir | **none** | — | −1.5%, under margin |
| swir1 | ×0.975336 + 0.001335 | local RMA | −5.8% |
| swir2 | **none** | — | raw was best |

Fitted on 45 near-coincident ETM+/OLI pairs across all three districts,
34,414 paired pixels, 13 pairs held out. Split by pair, never by pixel.

Held-out means: raw 0.01582, Roy 0.01680, **local OLS 0.01433** — the
published coefficients are worse than doing nothing on this data; the
locally fitted ones are about 9% better than doing nothing.

## Why NIR and SWIR2 are left alone

Not an oversight. **NBR is built from NIR and SWIR2**, and NBR is the
band LandTrendr segments to separate cyclical jhum disturbance from
permanent conversion (`docs/forest_definition.md` §6.4). Roy's published
coefficients degraded both bands (+8.5% and +69.8% on held-out pairs).
Adopting them would have propagated a known degradation directly into
the result the third district was added to produce.

The margin rule is what keeps this honest in the other direction too:
NIR's "local RMA wins" verdict was 0.0% in a 18-pair fit and 1.5% in a
45-pair fit. That is noise, and a selection rule without a margin would
have adopted it.

## Why TM gets the ETM+ transform — measured, not assumed

Applying ETM+ coefficients to TM is the standard simplification and is
usually asserted. Here it was tested: a separate TM→ETM+ fit on 45 pairs
(39,785 pixels) found **no transform beat identity on 5 of 6 bands**, and
the fitted RMA slopes came out at 0.97–1.01 with intercepts below 0.005 —
indistinguishable from identity.

TM and ETM+ have near-identical spectral response functions, so there is
little bias to correct and applying a transform would inject error rather
than remove it. **The TM chain therefore carries one regression's error,
not two** — which matters, because TM covers 1988–2011, most of the
study period.

This also resolves the concern raised below that TM→OLI cannot be fitted
directly (Landsat 5 and 8 never operated concurrently). The composition
is TM ≡ ETM+ → OLI, and the first step is empirically justified rather
than assumed.

## Remaining limitation

The reported gain comes from pairs held out of the *fit*, but all three
districts contributed to fitting, so these coefficients are tuned to
Bangladesh and should not be presented as generally applicable. That is
the intended scope — state it in Chapter 4 as a local calibration, not a
replacement for Roy et al.

---

# Original investigation

*(Kept as the record of how the decision was reached.)*

# Cross-sensor harmonisation — what we measured

## Why this matters more than it looks

The study runs 1988–2024. Landsat 4/5 TM covers the early years, ETM+ the
middle, OLI the end. TM, ETM+ and OLI have different spectral response
functions, so the *same ground* returns slightly different reflectance
depending on which sensor saw it. Compare an unharmonised 1990 TM
composite against a 2024 OLI composite and part of the difference is
sensor, not landscape. **A model reads that as forest loss.**

Nothing about this failure raises an error. It shows up as a plausible
looking change map with a systematic bias, and the only way to catch it
is to measure.

## Method

Landsat 7 and Landsat 8 fly the same WRS-2 orbit eight days apart, so a
scene pair from the same path/row within a few days sees very nearly the
same ground. Any systematic band difference between such a pair is
sensor difference rather than landscape change.

`src/check_harmonisation.py` finds those pairs and compares mean per-band
reflectance over the district, before and after harmonisation.

A first attempt compared whole-season *medians* per sensor instead. That
does not work — the two sensors contribute different dates, so phenology
and atmospheric state are confounded with the sensor effect. It reported
harmonisation making things worse, which was uninterpretable. The paired
design replaced it.

## Result — Gazipur, 12 pairs, ≤ 8 days apart

Mean absolute ETM+ minus OLI difference:

| Band | Raw | Harmonised | Change | |
|---|---|---|---|---|
| blue | 0.0167 | 0.0099 | −40.6% | better |
| green | 0.0100 | 0.0083 | −16.5% | better |
| red | 0.0095 | 0.0085 | −9.9% | better |
| nir | 0.0120 | 0.0130 | +8.5% | worse |
| swir1 | 0.0084 | 0.0141 | +68.5% | worse |
| swir2 | 0.0056 | 0.0096 | +69.8% | worse |
| **TOTAL** | **0.0622** | **0.0635** | **+2.1%** | **no material change** |

Two things are established by this:

1. **The regression direction is correct.** Applying the inverse
   transform gives a total of 0.0827 — far worse than either raw or
   harmonised. The coefficients in `src/preprocess.py` are ETM+ → OLI,
   as used. This was worth checking: Roy et al. publish coefficients in
   both directions and the wrong one is a silent, plausible-looking error.
2. **Harmonisation as applied does not reduce total cross-sensor bias on
   this data.** It clearly helps the visible bands and clearly harms the
   infrared ones.

## Most likely explanation

Roy et al. (2016) derived these coefficients on **Landsat Collection 1**.
This project uses **Collection 2 Level-2**, whose atmospheric correction
differs. Applying C1-derived coefficients to C2 surface reflectance is a
known imperfection, not a coding mistake. The infrared bands are where
the two collections' atmospheric treatments diverge most.

## Limits of what was tested

- One district (Gazipur), one path/row (p137r43), 12 pairs.
- Scene-mean statistics, not per-pixel distributions.
- ETM+ against OLI only. **TM against ETM+ was not tested at all**, and
  TM covers 1988–2011 — the majority of the study period. The current
  code applies the ETM+ coefficients to TM as a standard simplification.

**Harmonisation is therefore not validated.** Nothing here should be
described as verified in Chapter 4 until the decision below is made.

## The decision

### Option A — keep Roy coefficients as-is, report the measurement

Cheapest. Defensible: it is the standard published approach and citable.
Report the +2.1% measurement honestly as a limitation. Cost: knowingly
applying a transform that worsens three of six bands, including SWIR1
and SWIR2, which drive NDMI and NBR — and **NBR is what LandTrendr
segments to separate cyclical jhum from permanent conversion.**

### Option B — derive local coefficients from our own paired scenes

Fit per-band OLS on near-coincident pairs sampled per-pixel across all
three districts. Guaranteed to reduce bias on this data by construction,
and it turns a wobble into a genuine methodological contribution:
*"published cross-sensor coefficients derived on Collection 1 transfer
poorly to Collection 2 over Bangladesh; we derive local ones."* Cost:
roughly a day, plus care not to overfit — needs per-pixel sampling
across many pairs, not 12 scene means, and a held-out set of pairs to
test on.

### Option C — skip harmonisation, document why

Simplest and honest given the measurement: raw is marginally better than
harmonised in total. Cost: gives up the visible-band improvement, which
is real and large for blue. Weakest of the three as a thesis argument —
"we did nothing" is harder to defend than either doing the standard
thing or doing better than it.

## Recommendation

**Option B**, with A as the fallback if the schedule tightens.

The reason is specific rather than general: SWIR2 is the band harmonisation
damages most (+69.8%), NBR is built from NIR and SWIR2, and NBR is the
input to the LandTrendr segmentation that the entire Bandarban
cyclical-versus-permanent jhum split depends on. Carrying a known
degradation into that band undermines the result the third district was
added to produce.

Option B also has the best failure mode: if locally-derived coefficients
turn out not to beat raw on held-out pairs, that is itself a reportable
finding, and Option C follows from it with evidence rather than by
default.

**Before either option is finalised, extend the test to Sylhet and
Bandarban and to TM–ETM+ pairs.** TM covers most of the study period and
is currently harmonised on an untested assumption.
