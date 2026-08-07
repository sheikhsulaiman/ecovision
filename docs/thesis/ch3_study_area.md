# Chapter 3 — Study Area

## 3.1 Rationale for a three-district design

This study examines forest cover change in three districts of
Bangladesh: **Gazipur**, **Sylhet**, and **Bandarban**. The districts
were not chosen for convenience or for coverage. Each was selected
because it presents a *different mechanism of forest loss*, and the
central question of this thesis — whether the choice of classification
method matters more as landscape complexity increases — cannot be
answered in a landscape with only one mechanism.

A study confined to a single district can demonstrate that a method
works. It cannot demonstrate *when* a method stops working, which is the
more useful finding for anyone deciding what to deploy over an unfamiliar
landscape.

| District | Area | Dominant loss mechanism |
|---|---|---|
| Gazipur | 1,819 km² | Abrupt permanent conversion |
| Sylhet | 3,416 km² | Gradual degradation with plantation confusion |
| Bandarban | 4,592 km² | Cyclical clearing and regrowth (*jhum*) |

Areas were computed from district boundaries in EPSG:32646 (UTM Zone
46N) by `src/prepare_aoi.py` and verified against published figures
before use. Figure 3.1 shows their location and relative extent.

## 3.2 Gazipur — abrupt permanent conversion

Gazipur lies immediately north of Dhaka and contains the remnants of the
Bhawal sal (*Shorea robusta*) forest. Its loss mechanism is the simplest
of the three and the one most classification methods are implicitly
designed for: forest is cleared and replaced by something that is
unambiguously not forest — factories, housing, roads, brickfields — and
it does not return.

Two properties make Gazipur analytically useful. First, change is
*abrupt and permanent*, so a comparison between two dates is in principle
sufficient to detect it. Second, forest is a small and shrinking minority
of the landscape: forest loss constitutes approximately 0.22% of pixels.
That extreme class imbalance is itself a methodological problem, and it
is one this thesis treats explicitly rather than averaging away
(see §5.6 and rule 5 in the project constraints).

Gazipur also presents a specific interpretation difficulty that recurs
throughout Chapter 7. Village homestead vegetation in Bangladesh is dense,
green, and structurally similar to forest at 30 m resolution, but it sits
over houses, ponds and a road grid and is not forest under the definition
adopted here. Distinguishing it requires attention to settlement pattern
rather than to greenness.

## 3.3 Sylhet — degradation and plantation confusion

Sylhet contributes the confusion this thesis was designed around. The
district contains both natural hill forest and a substantial tea
plantation industry, and at 30 m resolution the two are spectrally
similar: both are dense, evergreen, and green in every season.

This matters beyond Sylhet. Where plantation cannot be separated from
natural forest, a mapping exercise reports plantation expansion as forest
stability, or worse, reports natural forest cleared for tea as no change
at all. The distinction is therefore preserved throughout this study as a
separate class rather than collapsed into a binary forest/non-forest
scheme, and any point at which a collapse occurs is stated explicitly.

Sylhet's loss mechanism is correspondingly gradual. Rather than the clean
step change seen in Gazipur, forest here thins, fragments, and converts
by degrees — a pattern that a two-date comparison represents poorly and
that motivates the annual analysis described in §5.8.

The district is also dominated by *haors*, seasonally inundated wetland
basins. Their extent varies enormously between wet and dry season, which
creates a definitional problem for the water class that is documented in
Chapter 7.

## 3.4 Bandarban — cyclical disturbance

Bandarban is the largest of the three districts and the most forested. It
was added to the study specifically because its loss mechanism breaks the
assumption underlying every bitemporal method.

The dominant land use in the Chittagong Hill Tracts is *jhum*, shifting
cultivation: a plot is cleared, cropped for one or two seasons, abandoned,
and allowed to regrow over roughly five to seven years, after which the
cycle repeats. A fallow plot is not deforested land. It is a stage in a
rotation.

A comparison between two fixed dates cannot see this. The same plot of
ground will be scored as loss, as gain, or as no change at all, depending
entirely on where in the swidden cycle the two observation dates happen
to fall. This is not a limitation that better classification accuracy
resolves; it is a limitation of the temporal design.

Consequently, no deforestation figure for Bandarban is reported in this
thesis without first separating permanent conversion from cyclical
disturbance, and that separation is made from the annual trajectory
rather than from any pair of dates (§5.8, Chapter 6). Headline
deforestation totals count permanent conversion only.

### Why Bandarban rather than the whole Chittagong Hill Tracts

The Chittagong Hill Tracts comprise three districts totalling 13,205 km².
Including all three would have made the study area 2.5 times its original
size and required substantially more reference interpretation, which is
the binding constraint on this work (Chapter 4).

Bandarban was selected from the three for reasons that are worth stating,
because the alternatives fail in instructive ways:

- **Rangamati** is dominated by the Kaptai reservoir. Reservoir
  inundation reads spectrally as forest loss, which would have
  contaminated the loss signal with an artefact of impoundment.
- **Khagrachhari** is already the most degraded of the three and has
  fragmented geometry, giving both a weaker signal and a more awkward
  spatial sampling frame.
- **Bandarban** is comparable in size to Sylhet, keeping the three study
  areas balanced; forms a single clean polygon; and retains the most
  intact forest, giving the clearest *jhum* signal.

## 3.5 What the three districts jointly permit

Taken together the three districts span a gradient of landscape
complexity — from a landscape where change is abrupt, permanent and
spectrally obvious, through one where the classes themselves are
confusable, to one where the temporal structure of the change defeats the
standard bitemporal design.

That gradient is what allows the central claim of this thesis to be
tested rather than asserted. A method that performs well in Gazipur and
poorly in Bandarban has told us something specific about where it should
and should not be deployed, and that finding is considerably harder to
dispute across three mechanisms than it would be across one.
