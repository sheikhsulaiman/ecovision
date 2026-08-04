---
title: "EcoVision — reference sample interpretation: how to actually do it"
status: Working protocol — read before your first point
date: 2026-08-03
---

# How to interpret the reference sample

1,550 points, both authors, independently. **Roughly 30–60 hours each.**
This is the binding constraint on the thesis and the single most-skipped
step in the risk register. Nothing here can be compressed at the end, and
no amount of compute substitutes for it.

Read this before your first point. Most of κ is decided by whether the
two of you apply the same rules, not by how carefully either of you looks.

---

## 1. Setup, once

**Generate the KML** (already done, regenerate if the sample changes):

```bash
python src/export_kml.py
```

That writes `data/reference/interpret_{district}_{author}.kml` — every
point as a clickable placemark, grouped into folders by stratum.

**Open your own KML in Google Earth Pro.** File → Open. Points appear in
the sidebar. Click one and Earth Pro flies to it.

**Open `gee/06_point_inspector.js`** in the Earth Engine Code Editor in a
second window. You will need it constantly — see §3.

**Open your own CSV** in a spreadsheet:

```
data/reference/interpretation_{district}_{author}.csv
```

Fill `class_t0`, `class_t3`, `confidence`, `notes`. Leave every other
column alone — `point_id` is what joins your file to the other author's.

> **Do not open the other author's file.** Not once, not to check a hard
> point. The independence *is* κ; comparing notes first turns it into a
> measure of how well you negotiated.

---

## 2. The classes

From `docs/forest_definition.md` §4. Same four everywhere.

| Code | Class | What it is |
|---|---|---|
| 0 | Non-forest | Built-up, bare soil, cropland, actively cultivated or recently cleared jhum |
| 1 | Natural forest | ≥30% canopy, ≥0.5 ha, trees able to reach 5 m. Sal, hill forest, qualifying jhum fallow |
| 2 | Plantation / tea | Tea, rubber, teak, orchards, agroforestry woodlots |
| 3 | Water | Rivers, ponds, haors |

**The threshold is 30% canopy over 0.5 ha** — about a 70 × 70 m square,
roughly 6 Landsat pixels. Judge the *neighbourhood* of the point, not the
single pixel under the pin. A lone tree in a field is not forest.

**Record two dates:** `class_t0` is **1990**, `class_t3` is **2024**.

---

## 3. Why you cannot do this in Earth Pro alone

Earth Pro's historical imagery over rural Bangladesh usually does not
reach 1990. For most points there is simply nothing to look at for T0.

So: **T3 in Earth Pro, T0 in the point inspector.** Paste the point's
lat/lon into `gee/06_point_inspector.js`, and it gives you the 1990 and
2024 Landsat composites plus the annual NDVI and NBR series at that
pixel.

Reading the trajectory:

| Pattern | Meaning |
|---|---|
| High, flat, small seasonal wobble | Stable forest |
| Drop that **stays down** | Permanent loss |
| Drop that **recovers over ~5–7 years**, often repeating | **Cyclical jhum — not deforestation** (rule 9) |
| High but flatter and lower amplitude than natural forest; regular shallow dips | Plantation / tea (pruning cycles) |
| Gradual decline, no sharp step | Degradation |

A gap in the chart means no cloud-free observation that year. It does not
mean zero vegetation.

---

## 4. The three calls that will cost you κ

These are where two careful people disagree. Agree the rules now, not
after 200 points.

### Tea versus natural forest (Sylhet)

The thesis question, and the hardest call.

| Tea | Natural forest |
|---|---|
| Regular planted rows, visible at Earth Pro zoom | Structurally chaotic, no repeating pattern |
| Uniform canopy height and colour | Mottled, varied canopy |
| Pale service tracks cutting through in a grid | Tracks follow terrain, irregular |
| Hard geometric estate boundaries | Ragged, follows topography |
| Shade trees in a regular scatter | No pattern |

Many estates keep **natural forest patches on steep ground inside their
boundaries**. Those patches are class 1, not class 2. Judge the pixel,
not the estate.

Sylhet holds >10,000 ha of tea against 28,489 ha of Hansen ≥30% canopy —
so expect to be calling class 2 often in the `stable_forest` stratum.
**That disagreement with the stratum is a result, not an error.**

### Jhum: fallow or cleared (Bandarban)

A jhum plot is class 0 or class 1 depending on its canopy **at the
observation date**, never on its land-use history
(`forest_definition.md` §1):

- Actively cultivated or recently cleared → **0**
- Fallow that has regrown to ≥30% canopy → **1**

Whether the loss is cyclical or permanent is decided from the trajectory
in the point inspector, and recorded in `notes`, not in the class. Write
`cyclical` or `permanent` there for every Bandarban point showing loss.

### Homestead vegetation (Gazipur)

Village tree cover is dense and green and is **not forest**. If you can
see houses, ponds and a road pattern under the canopy, it is class 0.
Bhawal sal forest is contiguous and has no settlement grid inside it.

---

## 5. Confidence, and when to use it

| Value | Use when |
|---|---|
| `high` | You would defend this call in a viva |
| `medium` | Fairly sure; imagery adequate but not ideal |
| `low` | Genuinely uncertain, or imagery poor at one date |

**Use `low` freely.** Points that both authors mark `low` and disagree on
can be excluded with justification (`methodology_plan.md` §4.2 step 5).
Forcing a confident-looking answer you do not believe is worse than
admitting uncertainty — it turns a known limitation into a hidden error.

Put the *reason* in `notes`, not just the class. "Cloud at T0",
"boundary case, ~30% canopy", "tea or young sal, cannot tell". Those
notes are what makes reconciliation possible.

---

## 6. Pace, and the check that saves you weeks

Aim for **1–2 minutes per point**. At that rate a district is 8–20 hours.
Do not do all 1,550 in one sitting; fatigue produces systematic error,
and systematic error is exactly what κ cannot detect.

**After your first ~100 points each, stop and run:**

```bash
python src/kappa.py --field class_t3
```

Gate 4 needs **κ ≥ 0.75**. If it is already low at 100 points, the class
definitions are ambiguous at the boundaries and you must fix that now.
Discovering it at 1,550 costs both of you the whole exercise; discovering
it at 100 costs an afternoon.

Then run it again every few hundred points.

---

## 7. When you disagree

Reconcile **jointly, after κ is computed** — never before.

1. Compute κ and keep the number. It goes in the thesis.
2. Look only at the disagreements.
3. Agree a final class, or mark the point uncertain and exclude it with a
   written reason.
4. **Log what changed and why.** The reconciliation record is part of the
   audit trail; silently overwriting disagreements destroys the evidence
   that the sample was independently interpreted at all.

Keep both original files. They are committed to git, and they are the
only non-derived data in the repo.

---

## 8. The other task: digitising 19 tea estates

Separate job, an afternoon rather than weeks, and it unblocks class 2,
the plantation stratum and RQ3.

No open dataset maps Bangladesh's tea estates — SDPT, OSM, GFW and
WorldCover were all checked and all fail (`forest_definition.md` §6.5).
But you do not have to search, because there is a named list:
`data/vector/sylhet_tea_estates_worklist.csv`.

1. Open `gee/05_tea_digitising.js`. Sentinel-2 at 10 m, search zone and
   canopy overlaid.
2. Work down the worklist by name — search each estate in Earth Pro or
   the GEE search box and go straight to it.
3. Draw one polygon per estate into a `tea` FeatureCollection with `name`
   and `confidence` properties.
4. Include mature tea, young tea and nursery blocks. **Exclude** estate
   housing, factories, and the natural forest patches on steep ground.
5. Tick each off in the worklist CSV.
6. Export, then tell Claude to ingest them.

**Stopping condition:** two independent counts exist — Siddik et al.
(2025) say 18, the estate directory lists 19. Finding 18–19 is expected.
Substantially fewer means estates are being missed; substantially more
means natural forest is being included. Total area should land near
10,000 ha.

---

## 9. Quick reference

```bash
python src/export_kml.py                 # regenerate the clickable points
python src/kappa.py --field class_t3     # agreement so far — run early
python src/kappa.py --field class_t0     # the 1990 call
```

| File | Purpose |
|---|---|
| `data/reference/interpret_{d}_{author}.kml` | Open in Earth Pro |
| `data/reference/interpretation_{d}_{author}.csv` | **Where you record answers** |
| `gee/06_point_inspector.js` | T0 imagery + trajectory |
| `gee/05_tea_digitising.js` | Tea estate drawing |
| `data/vector/sylhet_tea_estates_worklist.csv` | The 19 named estates |
