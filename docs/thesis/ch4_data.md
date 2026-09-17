# Chapter 4 — Data

## 4.1 Imagery source

All analysis imagery is **Landsat Collection 2 Level-2 surface
reflectance**, accessed through Google Earth Engine. Four sensor
generations contribute across the study period:

| Sensor | Collection |
|---|---|
| Landsat 4 TM | `LANDSAT/LT04/C02/T1_L2` |
| Landsat 5 TM | `LANDSAT/LT05/C02/T1_L2` |
| Landsat 7 ETM+ | `LANDSAT/LE07/C02/T1_L2` |
| Landsat 8 OLI | `LANDSAT/LC08/C02/T1_L2` |
| Landsat 9 OLI-2 | `LANDSAT/LC09/C02/T1_L2` |

Level-2 surface reflectance is used rather than Level-1 radiance because
the study spans 37 years and four sensors; without atmospheric correction
applied consistently, apparent change between epochs would be
indistinguishable from change in atmospheric condition.

**Google Earth and Google Maps imagery are used at no point as analysis
input.** High-resolution imagery is used only for visual reference
interpretation of the validation sample (§4.5), which is a distinct
purpose: it never enters a model, an index, or an area calculation.

### Scale factors

Collection 2 Level-2 products are distributed as scaled integers and must
be converted before any index is computed:

- optical bands: `DN × 0.0000275 − 0.2`
- thermal bands: `DN × 0.00341802 + 149.0`

Applying these correctly is verified after every change to the imagery
handling, by confirming that scaled reflectance falls within [0, 1]
(`src/preprocess.py`). Omitting or misapplying the offset is a silent
error: indices still compute, values still look plausible, and the
resulting map is wrong in a way that no downstream check catches.

## 4.2 Temporal design

### Compositing season

Composites are built from the **dry season**, 1 November to 31 March.
This avoids the monsoon, when cloud cover makes cloud-free observation
rare, and it fixes the phenological state so that between-epoch
differences reflect land cover rather than season.

### Study period

A full audit of scene availability was conducted before any compositing.
`src/scene_audit.py` evaluated **120 district-years** — 40 years across
three districts — with zero failures, recording per-year scene counts,
cloud cover, per-pixel observation depth, and spatial coverage.

**The study period begins in 1988.** The audit returned *zero usable
scenes* for 1985, 1986 and 1987 in all three districts. This is an
acquisition gap rather than a cloud problem: Bangladesh lay outside the
reception footprint of the international ground station network during
the mid-1980s, so the imagery was never collected. No amount of
processing recovers data that does not exist.

From 1988 onward, every year in Gazipur and Sylhet, and all but one in
Bandarban, supports an annual composite outright.

### Epoch anchors

| Epoch | Year | Rationale |
|---|---|---|
| T0 | 1990 | Historical baseline |
| T1 | 2000 | Aligns with the Hansen GFC baseline |
| T2 | 2010 | Midpoint |
| T3 | 2024 | Endpoint |

**T0 is 1990 rather than 1988**, despite 1988 being the first usable
year, because 1988's per-pixel observation depth is roughly half that of
1990. T0 forms one half of every bitemporal comparison in the study, and
a baseline built from thin observation propagates its noise into every
change figure derived from it. The annual series used for temporal
segmentation still begins in 1988; only the anchor moved.

### The 2012–2013 constraint

The 2012 and 2013 dry seasons are **100% Landsat 7 SLC-off** in all three
districts. Landsat 5 was retired in 2011 and Landsat 8 did not begin
delivering until 2013, leaving a two-year window served only by ETM+
after its scan line corrector failure, which loses approximately 22% of
each scene in wedge-shaped gaps.

Neither year may serve as an epoch anchor, and this constraint was
identified before the anchors were chosen rather than discovered
afterwards. Where these years appear in the annual series, residual gap
fraction is reported.

### Annual coverage for temporal segmentation

Separating cyclical from permanent disturbance in Bandarban (§3.4)
requires an unbroken annual series, not merely usable epoch anchors. The
audit confirmed this is available: Bandarban's longest gap from 1988
onward is **one year (1991)**. Had annual coverage been insufficient,
Bandarban could not have reported a deforestation figure at all, because
the permanent/cyclical separation would have been unsupportable.

## 4.3 Forest definition

Forest is defined as **≥ 30% canopy cover** at the observation date, over
a minimum mapping unit of one Landsat pixel (0.09 ha).

Two properties of this definition matter for interpretation:

1. It is a **canopy definition, not a land-use definition**. A *jhum*
   fallow that has regrown past 30% canopy is forest at that date,
   irrespective of its cultivation history. Whether the disturbance was
   cyclical or permanent is recorded separately and is *not* encoded in
   the class.
2. It is **date-specific**. A plot cleared in 2005 and regrown by 2024 is
   non-forest at T2 and forest at T3, and both statements are correct.

A 10% threshold sensitivity comparison is reported alongside the primary
30% results.

### Class scheme

| Code | Class | Definition |
|---|---|---|
| 0 | non-forest | Cropland, bare soil, built-up, roads, **and homestead gardens and village tree cover** |
| 1 | natural forest | Contiguous canopy ≥ 30%, no settlement structure |
| 2 | plantation | Tea or rubber estate: planted rows, uniform canopy, geometric boundary |
| 3 | water | Open water at the observation date |

Class 2 is retained as a distinct class throughout, and is collapsed into
a binary scheme only at the final reporting step, where the collapse is
stated explicitly. Collapsing earlier would hide precisely the confusion
this study set out to measure.

## 4.4 Training labels

Training labels derive from the **Hansen Global Forest Change** product
(`UMD/hansen/global_forest_change_2025_v1_13`), with water from the JRC
Global Surface Water dataset at ≥ 50% occurrence, and plantation from
hand-digitised tea estate boundaries (§4.6).

Forest at time *t* is constructed as the year-2000 canopy layer, minus
cumulative loss to *t*, plus gain. Hansen's `lossyear` band is masked
where no loss occurred, so it must be explicitly unmasked before its
complement is used; failing to do so causes stable-forest counts to
evaluate to zero, silently.

Hansen's baseline is the year 2000 and it can say nothing about forest
extent in 1990. The study period begins in 1988, so labels exist for
roughly two-thirds of it. This gap is addressed by a **two-regime
design**: supervised deep learning from 2000 onward, unsupervised
spectral and temporal-segmentation methods before it, with the two
regimes compared over the 2000–2024 overlap so that the pre-2000
uncertainty becomes a measured quantity rather than a caveat.

## 4.5 Reference sample

**Training labels and the reference sample are entirely separate, and
nothing derived from Hansen enters the reference sample.** A model scored
against labels derived from its own training source is being scored
against its teacher, and the resulting accuracy figure describes the
consistency of the pipeline rather than the accuracy of the map.

The reference sample is a **stratified random sample**, drawn
independently and interpreted by hand against high-resolution imagery and
the full annual spectral trajectory at each point.

### Stratification

Strata deliberately over-sample the rare change classes. A proportional
sample of Gazipur, where forest loss is 0.22% of the landscape, would
return a handful of change points and confidence intervals too wide to
support any statement.

| District | Strata | Total ha | Interpreted points |
|---|---|---|---|
| Gazipur | stable non-forest, stable forest, forest loss | 179,782 | 100 |
| Sylhet | + plantation | 326,039 | 180 |
| Bandarban | + cyclical | 459,409 | 120 |

Stratum weights are computed from **map pixel counts**, not from the
sample. This is what allows sample size to be reduced without
invalidating the area estimator: reducing points per stratum widens the
confidence interval and changes nothing else, provided the achieved
sample size per stratum is recorded, which it is.

### Reduced design and its consequences

The design as originally specified called for 1,650 points interpreted
independently by both authors — approximately 80 person-hours. Schedule
constraints required a reduction to **440 points**, with each point
interpreted once and a cross-stratum subset interpreted by both authors
so that inter-interpreter agreement remained measurable.

The consequences are quantified rather than described, and are reported
in §6.6. They are real: with a small number of reference change
points, several forest-loss confidence intervals include zero.

This trade was made deliberately and in one direction only. A smaller
sample produces wider intervals, which is a stated limitation. Omitting
the accuracy assessment entirely would remove the only independent
yardstick in the study and render every accuracy figure circular. The
first is a weaker result; the second is not a result.

### Interpretation protocol

Each point receives two independent judgements — its class at T0 and its
class at T3. **Change is derived from the pair and is never interpreted
directly.** An interpreter asked "did this change?" anchors on the answer
they expect; asked twice about single dates, they cannot.

Each point also carries a confidence level and free-text notes. For
Bandarban, whether an observed disturbance is cyclical or permanent is
recorded in the notes and never in the class, because the class is a
canopy statement and cannot express a trajectory.

## 4.6 Plantation boundaries

Class 2 rests on **hand-digitised tea estate boundaries**, totalling
1,303 ha across 12 polygons, drawn in Google Earth Pro against sub-metre
imagery.

They were drawn by hand because no alternative exists. Section 7.3
documents the automated routes that were attempted and measured to fail:
no open dataset maps Bangladesh's tea estates at a usable resolution; the
Spatial Database of Planted Trees carried no Bangladesh layer in the
version tested (v1.3); rendered global forest-cover tiles
return zero coverage over Sylhet while returning high coverage over
comparable tea landscapes elsewhere; public gazetteers resolve one estate
in nineteen under strict name matching; and a purpose-built row-texture
detector could not separate tea from forest at conventional significance.

The layer is **incomplete and the incompleteness is quantified**:
approximately 1,300 ha are drawn against a district total exceeding
10,000 ha reported in the literature. Tea outside the drawn polygons is
labelled natural forest, so the Sylhet confusion is *reduced rather than
eliminated*, and results involving class 2 are bounded accordingly.

Gazipur and Bandarban have no plantation class. There are no tea estates
in either, and no boundary source exists for their Forest Department teak
and rubber plantations.
