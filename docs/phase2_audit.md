---
title: "EcoVision — Phase 2 scene availability audit: results and Gate 2 decisions"
status: Gate 2 — CONFIRMED, decisions final
date: 2026-07-26
date_confirmed: 2026-09-17
---

# Phase 2 — scene availability audit

Produced by `src/scene_audit.py` (authoritative) against Landsat
Collection 2 Level-2 in Google Earth Engine, summarised by
`src/audit_summary.py`. 120 district-years evaluated, zero failures.

Raw output: `data/raw/audit/{district}_scene_audit.csv`
Tables: `outputs/tables/scene_audit_summary.csv`, `..._verdicts.csv`
Figure: `outputs/figures/scene_availability.png`

**Every number in this document came from running the pipeline. None is
illustrative.**

---

## 1. Headline result

| District | Years audited | Usable | Annual composite viable | Unusable | Proposed start |
|---|---|---|---|---|---|
| Gazipur | 40 | 37 | 37 | 3 | 1988 |
| Sylhet | 40 | 37 | 37 | 3 | 1988 |
| Bandarban | 40 | 36 | 36 | 4 | 1988 |

**START_YEAR = 1988**, common to all three districts. Every usable year
supports an annual composite outright; not one district-year fell into
the "3-year moving window" category the plan anticipated needing.

---

## 2. The Gate 2 justification paragraph

> The study period begins in 1988. A dry-season (1 November – 31 March)
> audit of Landsat 4, 5, 7, 8, and 9 Collection 2 Level-2 holdings over
> each district, filtered to scene cloud cover below 40%, returned zero
> usable scenes for 1985, 1986, and 1987 in all three districts —
> Bangladesh lay outside the reception footprint of the international
> ground station network during the mid-1980s, so the imagery was never
> acquired rather than being merely cloudy. From 1988 onward every year
> in Gazipur and Sylhet, and all but one in Bandarban, provides at least
> three usable scenes with complete spatial coverage of the district and
> a mean of at least one cloud-free observation per pixel. The single
> exception, Bandarban 1991, yields two scenes covering 83% of the
> district at 0.85 clear observations per pixel and is excluded. A start
> year of 1988 therefore gives a 37-year observation period in which
> 97–100% of years are independently usable, without relying on
> composites assembled from partial coverage.

---

## 3. Why 1985–1987 are empty

Not a cloud problem — an acquisition problem. The audit returns
`total_scenes = 0`, meaning no Collection 2 Level-2 scene of any sensor
intersects these districts in those dry seasons at any cloud level that
passed the filter. Landsat 5 was operating, but its data had to be
downlinked to a receiving station in range; Bangladesh was not covered
until later. This is the outcome the methodology plan predicted
("1984–1990 will be thin over Bangladesh") and it is the reason Phase 2
runs before anything is written.

The plan's fallback of moving to 1990 or 1995 turns out to be
unnecessary. **1988 is defensible and two years earlier than the plan's
own fallback.**

---

## 4. Epoch anchors

| Epoch | Year | Gazipur | Sylhet | Bandarban | Purpose |
|---|---|---|---|---|---|
| T0 | **1990** | 11 scenes, 5.9 obs/px | 19, 7.0 | 16, 8.1 | Baseline |
| T1 | 2000 | 16, 8.1 | 27, 10.0 | 31, 13.6 | Aligns with Hansen baseline |
| T2 | 2010 | 18, 8.1 | 35, 11.2 | 36, 15.6 | Mid-point |
| T3 | 2024 | 26, 13.0 | 43, 14.7 | 68, 25.7 | Endpoint |

All four anchors reach 100% spatial coverage in all three districts.

**T0 is 1990, not 1988, deliberately.** 1988 is usable — 100% coverage,
6/8/9 scenes — but its observation depth (3.0/2.5/4.2 clear observations
per pixel) is roughly half 1990's (5.9/7.0/8.1). T0 is one half of every
bitemporal comparison in the thesis, so a thin composite there degrades
every change product built on it. The annual series still starts at 1988
for LandTrendr; only the bitemporal anchor moves. This costs two years
of change-detection span and buys a materially more reliable baseline.

---

## 5. Constraint discovered: the 2012–2013 Landsat 7 dependency

**Every scene available in the 2012 and 2013 dry seasons, in all three
districts, is a Landsat 7 SLC-off scene** — each carrying roughly 22%
missing data in wedge-shaped gaps.

| District | Year | L5 | L7 (all SLC-off) | L8 | Total | obs/px |
|---|---|---|---|---|---|---|
| Gazipur | 2012 | 0 | 13 | 0 | 13 | 4.9 |
| Gazipur | 2013 | 0 | 16 | 0 | 16 | 7.7 |
| Sylhet | 2012 | 1 | 22 | 0 | 23 | 8.0 |
| Sylhet | 2013 | 0 | 20 | 0 | 20 | **3.9** |
| Bandarban | 2012 | 3 | 25 | 0 | 28 | 10.0 |
| Bandarban | 2013 | 0 | 20 | 0 | 20 | 7.2 |

Landsat 5 was retired in 2012 and Landsat 8, launched February 2013, did
not deliver usable data until after the 2013 dry season closed. The
window is therefore genuinely ETM+-only, exactly as the plan's Phase 3.4
warned, but across **two** consecutive years rather than one.

Consequences, to be carried into Phase 3:

1. **Neither 2012 nor 2013 may be used as an epoch anchor.** They are
   not, under the anchors chosen above.
2. **Residual gap fraction must be reported per year** for 2012 and
   2013, per plan 3.4. With 13–20 scenes per district the median
   composite should fill most gaps, but "should" is not a result.
3. **Sylhet 2013 is the weakest year in the entire 37-year series** at
   3.9 clear observations per pixel, all from gap-affected scenes.
   Inspect its composite visually before trusting the LandTrendr segment
   that crosses it.

---

## 6. Bandarban: LandTrendr viability — the condition Gate 2 added

The jhum cyclical-versus-permanent split (`docs/forest_definition.md`
§6.4) depends on a near-continuous annual series; a long gap would let a
plot be cleared and recover unobserved, making the split unsupportable
and leaving Bandarban unable to report a deforestation figure at all.

**Result: viable.** From 1988, Bandarban's longest run of consecutive
unusable years is **one** (1991 alone), inside the 2-year tolerance. 36
of 37 years are usable. Bandarban's data is in fact the *deepest* of the
three districts in most years — 25.7 observations per pixel in 2024
against Gazipur's 13.0.

**This condition is met and Bandarban proceeds.** The one-year 1991 gap
should still be stated in Chapter 4.

---

## 7. Method notes for Chapter 4

- **Dry season 1 November – 31 March.** The monsoon (June–October) makes
  optical imagery largely unusable, and mixed-season composites
  introduce phenological change a model reads as forest loss.
- **Landsat 9 was included.** It contributes 12 of Gazipur's 26 scenes
  in 2024 — 46% of the endpoint epoch. An audit omitting it would have
  materially understated recent availability.
- **Coverage was measured per pixel, not per scene.** `filterBounds`
  counts a scene clipping a district corner the same as one covering it
  whole, so the audit also computes clear observations per pixel and the
  percentage of the district with at least one, from `QA_PIXEL`. Both
  criteria must pass for a year to count as usable.
- **Audit resolution 300 m**, ten times native, to keep 120 district-year
  reductions tractable. Used for the availability decision only; nothing
  in Phase 3 onward uses this scale.
- **WRS-2 path/row counts** are recorded per year, since three scenes
  from one path/row cover less of a district than three from three.

---

## 8. Gate 2 checklist

- [x] Audit table exported for all three districts
- [x] Start year fixed and justified in one written paragraph (§2)
- [x] Epoch anchors chosen (§4)
- [x] Bandarban annual-coverage condition tested and met (§6)
- [x] Supervisor confirmation of START_YEAR and epoch anchors
      (confirmed 2026-09-17)

**Gate 2 is closed.** START_YEAR = 1988 and the epoch anchors
T0 = 1990, T1 = 2000, T2 = 2010, T3 = 2024 are final.
