# EcoVision — Claude Code project instructions

This file is project context for Claude Code. Read it in full before
making changes. It encodes decisions already made — don't relitigate
them without flagging it to the user first.

## Project summary

Undergraduate thesis: deep learning deforestation detection in
**Gazipur**, **Sylhet**, and **Bandarban** districts, Bangladesh,
using Landsat imagery via Google Earth Engine. Two authors, one
supervisor, department of Educational Technology and Engineering, UFTB.

Full phase-by-phase methodology: `docs/methodology_plan.md`.
Original proposal (superseded — the title's imagery source is corrected
from "Google Earth" to "Landsat via Google Earth Engine"):
`docs/thesis_proposal.md`.

### Scope change — 2026-07-26: Bandarban added

Study areas went from two to three. Recorded here because the previous
version of this file said scope had been *cut* to two districts; that is
no longer true and the reasoning should not have to be re-derived.

**What was added:** Bandarban district only (4,592 km²) — **not** the
whole Chittagong Hill Tracts. CHT is three districts totalling 13,205
km², which is 2.5× the original two-district study area and would have
required 1,800 extra reference points interpreted twice by hand.

**Why Bandarban of the three:** comparable in size to Sylhet so the
three areas stay balanced; single clean polygon; most intact forest and
the clearest jhum signal. Rangamati was rejected because Kaptai
reservoir dominates it and reservoir inundation reads as forest loss;
Khagrachhari because it is already the most degraded and has fragmented
geometry.

**What it buys:** a third distinct loss mechanism. Gazipur is abrupt
permanent conversion, Sylhet is gradual degradation plus plantation
confusion, Bandarban is **cyclical clearing and regrowth (jhum,
shifting cultivation)**. Three mechanisms make the headline finding —
that model choice matters more as landscape complexity rises — much
harder to argue with than two.

**What it costs:** +600 reference points (~3–4 weeks), ~1.9× total pixel
volume. The reference sample remains the binding constraint on this
thesis; if schedule slips, Bandarban is the first thing to cut, not the
accuracy assessment.

**New obligation it creates:** jhum breaks a plain bitemporal T0→T3
comparison — a fallow that regrows in 5–7 years is not deforestation,
but T0→T3 scores it as loss or as nothing depending purely on where in
the swidden cycle the two dates land. See rule 9 below and
`docs/forest_definition.md` §6.4.

## Compute environment: Kaggle

**All model training happens on Kaggle notebooks, not locally and not
in this VS Code workspace.** This changes how you should work:

- Do not write training loops assuming persistent local GPU state —
  Kaggle sessions are ephemeral (resets on restart) and capped at
  ~30 GPU-hours/week on the free tier.
- Write training scripts as **self-contained notebook cells or
  scripts** that can be copy-pasted into a Kaggle notebook, with all
  imports and paths at the top — don't assume they'll run via VS
  Code's local Python interpreter and reach the same result.
- Kaggle notebooks have **no persistent local disk** between
  sessions. Any checkpoint, model weight, or intermediate array must
  be saved to a Kaggle Dataset/Output or pulled back down — never
  assume a file written mid-notebook survives to the next session.
- Kaggle notebook internet access must be explicitly enabled in
  session settings; GEE exports should go to Google Drive, then be
  pulled into the Kaggle notebook via a downloaded/mounted copy, not
  fetched live from GEE inside Kaggle.
- Local VS Code work is for: GEE scripts (`gee/`), preprocessing and
  data-prep code intended to run locally or in Colab, evaluation and
  area-estimation scripts (`src/area_estimation.py`), analysis
  notebooks, and the thesis writing itself. Model training code
  should be written here, tested on a tiny synthetic/sample tensor
  locally, then handed off to Kaggle for the real run.
- When writing anything Kaggle-bound, include a short "Kaggle setup"
  comment block at the top of the file: internet on/off requirement,
  which accelerator (GPU T4 x2 typical on free tier), and where
  input data is expected to be mounted (`/kaggle/input/...`).

## Hard rules — do not violate without flagging to the user

These come from mistakes already caught in planning. If a task seems
to require breaking one of these, stop and ask rather than silently
doing it.

1. **Never use Google Earth or Google Maps imagery as analysis
   input.** Only Landsat/Sentinel via Google Earth Engine
   (`LANDSAT/.../C02/T1_L2` collections). Google Earth Pro is allowed
   only for visual reference interpretation of the validation sample.
2. **Never train/test split randomly at the pixel or patch level.**
   Splits must be spatially disjoint (whole grid blocks assigned to
   train/val/test) — see `docs/methodology_plan.md` Phase 5.1. Random
   splitting on this data silently inflates accuracy and is the kind
   of bug that isn't caught until an examiner asks about it.
3. **Never conflate training labels and the reference/validation
   sample.** Hansen GFC + BFD shapefiles = training labels only. The
   ~600-point stratified reference sample, independently interpreted
   by both authors, is the only thing accuracy is measured against.
   If a script's variable names blur this distinction, rename them —
   clarity here prevents a circularity error in the results chapter.
4. **Never report area as raw pixel counts.** Always run the
   Olofsson et al. (2014) stratified area estimator
   (`src/area_estimation.py`) and report area with a 95% CI. A bare
   pixel count is not an acceptable deliverable at any stage.
5. **Never report overall accuracy as the headline metric** for
   change detection — the change class is a small minority of
   pixels. Headline metric is F1/IoU on the change class specifically.
6. **Apply the correct Landsat Collection 2 Level-2 scale factors**
   before computing any index: optical bands ×0.0000275 + (-0.2),
   thermal bands ×0.00341802 + 149.0. This is the most common silent
   error in student GEE work — verify reflectance values land in
   [0, 1] after scaling, every time a new collection is touched.
7. **Keep the "natural forest" vs "plantation/tea" class distinction
   everywhere** — don't silently collapse to binary forest/non-forest
   until the final reporting step, and say explicitly when a
   collapse happens. This is what prevents the Sylhet tea-garden
   confusion from hiding real forest loss.
8. **Don't fabricate or assume results.** If a script produces
   numbers, they come from actually running the pipeline on real
   data. Never write placeholder accuracy figures, area statistics,
   or example outputs into the thesis text or into code comments as
   if they were real results — mark anything illustrative as
   `# EXAMPLE — replace with real run output` and say so out loud.
9. **Never report cyclical jhum disturbance as deforestation.**
   Bandarban's dominant signal is shifting cultivation: clear, crop,
   abandon, regrow, repeat on a 5–7 year cycle. A bitemporal T0→T3
   comparison cannot tell that apart from permanent clearance — it
   scores a fallow plot as loss or as nothing purely according to where
   in the swidden cycle the two dates happen to fall. Any Bandarban
   loss figure must therefore be split into **permanent conversion**
   and **cyclical disturbance**, separated using the annual LandTrendr
   trajectory (a pixel that recovers within the series is cyclical),
   never by a single date pair. Headline deforestation totals count
   permanent conversion only. This is the Bandarban analogue of rule 7.

## Repo structure

```
gee/            Earth Engine JavaScript — AOI, scene audit, composites, exports
data/vector/    AOI boundaries, BFD shapefiles (once received)
data/reference/ Reference-sample interpretation CSVs (both authors, kept separate before reconciliation)
data/raw/       Gitignored — regenerate from gee/ scripts
data/patches/   Gitignored — regenerate from src/ scripts
src/            Python — dataset loading, models, training, evaluation
src/models/     Model architectures (RF wrapper, U-Net config, Siamese config)
src/area_estimation.py   Olofsson et al. (2014) adjusted-area estimator — see rule 4
notebooks/      Exploratory analysis only — no thesis figures generated here directly
outputs/        Maps, figures, tables — must be regenerable from src/, never hand-edited
docs/           Methodology plan, proposal, division of labour, this file
```

**Nothing derived is committed to git.** If a script can regenerate a
file, that file belongs in `.gitignore`, not in a commit.

Three deliberate exceptions, all recorded in `.gitignore`:

- `data/reference/*.csv` **is** committed. It is hand-interpreted by
  both authors over weeks and no script can regenerate it — it is the
  only non-derived data in the repo and the basis of every accuracy
  figure.
- `outputs/figures/` and `outputs/tables/` **are** committed, though
  derived. They are small, and versioning them gives an audit trail of
  how each reported number moved as the pipeline changed — useful when
  an examiner asks whether a result shifted after a bug fix.
  `outputs/maps/` stays ignored (GeoTIFFs, frequently over GitHub's
  100 MB per-file limit).
- `data/splits/*.geojson` **is** committed. The block assignment defines
  what "test set" means for every experiment. It is seed-reproducible but
  also depends on Hansen loss counts, so a Hansen version bump would
  silently reassign blocks and two models trained a month apart would be
  scored on different test sets while looking comparable. Regenerate
  deliberately with `src/splits.py --write`, never incidentally.

## Current phase status

Update this section as phases complete — Claude Code should read it
at the start of every session to know what's already done and what's
next, rather than re-deriving it from scratch each time.

**Audited against the repo on 2026-09-17** and substantially rewritten.
It had drifted badly: Phases 7 and 8 were marked not-started while their
results were already written into the thesis, and Phase 4 was marked
"nothing drawn" with 400 interpreted points sitting in
`data/reference/`. If this section and the files disagree again, the
files are right.

**The short version.** Phases 0–8 are done, and **Gates 1 and 2 were
signed off on 2026-09-17**. What actually remains:
1. RQ3 has no independent validation, deliberately. The 40-point Sylhet
   plantation stratum was interpreted by both authors on 2026-09-17 and
   the two agreed at chance (kappa 0.067), so it is reported as unusable
   for validation rather than used. Decided 2026-09-17; do not quietly
   revive it as a validation source.
2. κ fails Gate 4 in both districts measured (0.157, 0.038 against a
   0.75 threshold); reconciliation, then recompute everything
   reference-based downstream. **This is a measurement failure, not a
   paperwork one — signing it off is not available as an option.**
3. `outputs/maps/` is still empty (no GeoTIFF was pulled down), but the
   thesis now has its map: `bandarban_jhum_map.png`, rendered from the
   committed `landtrendr_bandarban` asset and placed in ch6 section 6.5.
4. **Two things are published, and they are not the same thing.**
   - The Earth Engine App, 2026-09-18:
     https://ecovision-503602.projects.earthengine.app/view/ecovision
     Live GEE compute — the annual trajectory at any pixel you click.
     This is the QR target on both posters.
   - The React dashboard, 2026-09-19:
     https://sheikhsulaiman.github.io/ecovision/
     Static, built from `ecovision-dashboard/` by
     `.github/workflows/deploy-dashboard.yml` and served from GitHub
     Pages (source: GitHub Actions, not a branch, so `dist/` stays
     ignored). It carries the findings, figures and district map, and
     links out to the GEE app for anything needing live compute — a
     static site cannot run Earth Engine for a visitor.

   The workflow is path-filtered to `ecovision-dashboard/**`, so a commit
   to `src/` or `docs/` does not redeploy. `vite.config.ts` sets
   `base: "./"`, which is what makes the build work from `/ecovision/`;
   an absolute base would 404 every asset there.

   Still to do: put both URLs in Chapter 1 and the deck.
5. The thesis has never been compiled to PDF. The authors compile the
   Overleaf zip themselves; no local LaTeX toolchain is installed and
   none is wanted.
6. Reference list is populated by `
ocite{*}` rather than real
   `\cite{}` commands, so there are no numbered in-text citations. Fine
   for an author-year thesis; revisit only if IEEE numbering is wanted.

- [x] Phase 0 — repo scaffolded, BFD request letter sent, GitHub repo
      created (private, `sheikhsulaiman/ecovision`)
- [x] Phase 1 — **done, Gate 1 signed off 2026-09-17.** AOI boundaries
      built by `src/prepare_aoi.py`, verified against published areas, and
      uploaded as GEE assets under `projects/ecovision-503602/assets/`.
      Class scheme fixed. `docs/forest_definition.md` is now
      `status: SIGNED OFF` at version 1.0.
      The definition is fixed from here: changing it invalidates the
      reference sample and every area estimate built on it, so any change
      needs a new version and a re-run, not an edit in place.
- [x] Phase 2 — **audit complete, 120/120 district-years, zero failures.**
      Results and Gate 2 decisions: `docs/phase2_audit.md`.
      **START_YEAR = 1988** (1985–87 have zero scenes in all three
      districts — an acquisition gap, not cloud). Epoch anchors
      **T0 = 1990, T1 = 2000, T2 = 2010, T3 = 2024**; T0 is 1990 rather
      than 1988 because 1988's observation depth is about half 1990's and
      T0 is one half of every bitemporal comparison. The annual series
      for LandTrendr still starts at 1988. Bandarban's LandTrendr
      condition is **met** (longest gap 1 year, 1991).
      **Gate 2 confirmed 2026-09-17** — START_YEAR and the epoch anchors
      are final; `docs/phase2_audit.md` is closed.
      Keep `START_YEAR` a named constant regardless — do not inline 1988.
      **Phase 3 constraint found:** the 2012 and 2013 dry seasons are
      100% Landsat 7 SLC-off in all three districts (L5 retired, L8 not
      yet delivering). Neither may be an epoch anchor, and residual gap
      fraction must be reported for both.
- [x] Phase 3 — **done.** Preprocessing primitives written and verified
      (`src/preprocess.py`, 23-band stack, rule 6 check passing).
      Cross-sensor harmonisation resolved empirically: locally fitted
      coefficients replace Roy et al. on blue/red, Roy retained on green,
      local RMA on swir1, and **NIR and SWIR2 are left untransformed** —
      Roy's published values made both worse, and NBR is built from them.
      TM needs no transform (measured, not assumed). See
      `docs/phase3_harmonisation.md`. Epoch composites are built in GEE
      and everything downstream runs on them; they were never exported as
      local rasters, which is by design — `data/raw/` holds only the audit
      and the boundaries.
- [x] Phase 4 — **done, with one stratum outstanding.** Reference sample
      drawn and interpreted: 400 points under the reduced design
      (Gazipur 100, Sylhet 180, Bandarban 120), in
      `data/reference/`. Bandarban went to a **third, reconciled pass**
      (commit `82fe7e2`) after the first returned natural_forest for all
      240 calls; that reconciliation moved every Bandarban figure in the
      thesis and is the single most common source of stale numbers in this
      repo — check dates before trusting any Bandarban value.
      **Pre-2000 regime: Option B decided** — supervised post-2000,
      unsupervised before.
      **Gain stratum dropped** (Hansen `gain` is 2000–2012 only), its 50
      points moved to forest loss.
      **Plantation stratum: interpreted, and not usable.** Both authors
      completed the 40-point Sylhet plantation top-up on 2026-09-17 and
      agreed on 12 of 40, kappa 0.067 — worse than either district. Author
      A called 25 plantation and 9 water; author B called 14 plantation and
      0 water. The stratum is reported as **not usable for validation**
      (option C, chosen 2026-09-17), which is a finding about how hard tea
      is to interpret rather than a gap in the work. It became a fifth line
      of evidence in ch7 section 7.3. The interpreted files are committed.
      If anyone revisits this, start with the water disagreement: the same
      A-over-B water divergence shows in the main sample (13 against 6), so
      it looks like one definitional difference rather than 40 judgements.
- [x] Phase 5 — **done.** Spatially disjoint 10 km block splits written
      and verified (`src/splits.py`, `data/splits/*.geojson`, committed so
      the test set cannot drift). Balanced on forest loss as well as area,
      because loss is 0.22% of pixels in Gazipur and Sylhet and an
      area-only split leaves the test set with no positives.
      **Patch size revised 256 → 128 px** — 256 does not tile inside a
      10 km block and yields only ~165 training patches. Experiment matrix
      frozen. See `docs/phase5_experiment_matrix.md`.
- [x] Phase 6 — **done for every experiment still in scope.**
      E1/E2 (`src/models/rf.py`, 3 seeds): terrain helps in Gazipur
      (+0.017 macro F1) and Sylhet (+0.021), within seed noise in
      Bandarban. E3/E4 (U-Net) and E7 (stacked ensemble) all run —
      results in `outputs/tables/unet_*` and `ensemble_E7_*`. Patches
      were extracted (706 at 128 px, `data/patches/`, 2024 only).
      All of these are scored against Hansen training labels, not the
      reference sample — pipeline checks, not accuracy results.
      **E5 (Siamese) and E6 (cross-district transfer) were never built
      and are now out of scope**, dropped with the RQ trim of 2026-09-17.
      **Class imbalance differs by two orders of magnitude across
      districts** (0.22% loss in Gazipur/Sylhet vs 24.3% in Bandarban), so
      patch sampling is weighted in the first two and unweighted in
      Bandarban. Test splits are never weighted.
- [~] Phase 7 — **change detection done, map rasters not exported.**
      PCC and NDVI differencing run for all three districts
      (`change_accuracy_*.csv`); LandTrendr permanent-vs-cyclical
      separation done for Bandarban, satisfying rule 9.
      **Map figure done 2026-09-17:** `bandarban_jhum_map.png` renders the
      classified LandTrendr asset and is placed in ch6 section 6.5.
      **Still not done:** `outputs/maps/` is empty — no GeoTIFF was pulled
      down, so there is no raster deliverable, only the figure. Also
      `change_areas_*` exists for Gazipur and Bandarban but **not
      Sylhet**.
      **Bug found and fixed while making that figure:** `landtrendr.py`
      exported the asset `.toFloat()` with no `pyramidingPolicy`, so Earth
      Engine built MEAN overviews of a categorical band. Any view below
      native scale averaged the class codes — a cell half stable (0) and
      half cyclical (2) averaged to 1 and rendered as permanent
      conversion. The tabulated areas were never affected (they are
      computed at native 30 m, and reproduce the published table exactly),
      but the first draft of the map was a red speckle contradicting its
      own legend. `export_asset` now sets
      `pyramidingPolicy={'class': 'mode', ...}`; **the existing asset
      predates that fix**, so anything drawn from it must downsample by
      majority, as `fig_bandarban_jhum_map` does.
- [x] Phase 8 — **done.** Olofsson adjusted areas, confusion matrices,
      change-detection accuracy, and Cohen's κ for Gazipur and Sylhet.
      Numbers in `outputs/tables/`, written up in Chapter 6 §6.6–6.7
      (authoritative) and `docs/phase8_results.md` (phase record).
      **κ fails Gate 4 in both districts measured** (0.157, 0.038), so
      every reference-based figure is provisional pending reconciliation.
      κ is not measurable for Bandarban — one interpreter.
- [~] Phase 9 — analysis is written rather than held separately: the
      cross-district synthesis lives in Chapter 6 and Chapter 7. No
      separate analysis artifact exists and probably none is needed.
- [~] Phase 10 — dashboard. **In scope and mandatory** (decided
      2026-09-17). Written: `gee/07_dashboard.js`, a GEE App built to the
      Phase 10 spec — per-epoch layer toggle, NDVI change layer with
      legend, click-a-pixel annual NDVI/NBR trajectory, per-district
      statistics panel, and a methods-and-limitations block carrying the
      forest definition. AOI assets verified to resolve; JS syntax
      checked. **Published 2026-09-18** at
      https://ecovision-503602.projects.earthengine.app/view/ecovision
      (verified HTTP 200). Wired into the React site and encoded as the QR
      target on both posters. Still to do: cite the URL in Chapter 1 and
      the pre-defence deck.
      Every reference-based number in its panel is labelled provisional
      on screen, for the κ reason. Do not remove that wording.
- [~] Phase 11 — **substantially drafted.** Seven chapters in
      `docs/thesis/`, assembled by `src/build_thesis.py` (docx) and
      `src/build_latex.py` (Overleaf zip). Title page, abstract, figures,
      tables and references all present. **Never compiled to PDF** — no
      LaTeX toolchain locally, so the Overleaf compile is still an
      unrun check.

## Research questions (current)

**Shrunk from 7 to 4 on 2026-09-17**, at the user's explicit direction,
because two of the original seven had no complete result behind them:
old RQ4 depended on a Siamese-network run (E5) that was never built, and
old RQ7 (unsupervised-vs-supervised substitution) was never attempted at
all. Keeping either as a numbered question with zero results behind it
was a worse look than dropping it. The renumbering:

- old RQ1 → RQ1 (unchanged)
- old RQ2 → RQ2, **with "Siamese Network" removed from the option list**
  — same reason as above, it was never built, so it can't be compared
- old RQ3 → RQ3 (unchanged)
- old RQ6 → **RQ4** (the Bandarban/LandTrendr question — this one was
  never a candidate for cutting; it's why the third district exists)
- old RQ4 (change-detection method: PCC/NDVI/Siamese) → **dropped as a
  standalone RQ.** The PCC-vs-NDVI comparison still stands and is still
  reported in Chapter 6 — it's now a supporting finding under RQ2's
  discussion, not its own numbered question, since the Siamese third of
  the comparison never happened.
- old RQ5 (traditional ML vs. DL cost/accuracy trade-off) → **dropped as
  a standalone RQ**, folded into RQ2's discussion (it falls directly out
  of the RQ2 results — RF wins at 55 patches, loses at 167).
- old RQ7 → **dropped entirely.** No experiment was ever run for it.

**Reworded 2026-09-17 to higher-order Bloom's verbs.** The measurements
behind each question are unchanged — only the framing verb and a closing
"what does this reveal" clause were added, moving each question from
descriptive (*how much*, *which*, *does X*) to analytical/evaluative.
The clause is not decoration: it is the bridge each question takes into
the discussion chapter.

1. To what extent, and in what spatial patterns, has forest cover
   changed across Gazipur, Sylhet, and Bandarban between [audited start
   year] and 2024 — and what does this variation reveal about the
   relationship between landscape type and dominant loss mechanism?
2. How does the comparative performance of Random Forest and U-Net vary
   across landscapes of differing spectral and spatial complexity, and
   what does this reveal about the relationship between a target class's
   discriminating signal and the model architecture needed to detect it?
3. To what extent does incorporating GLCM texture features improve
   discrimination between natural forest and tea plantation in Sylhet,
   and what does the isolated contribution of texture reveal about the
   spatial versus spectral nature of the confusion?
4. To what extent can annual temporal segmentation (LandTrendr)
   distinguish cyclical jhum disturbance from permanent forest
   conversion in Bandarban, in a setting where bitemporal comparison
   structurally cannot? *(Added with the Bandarban scope change,
   2026-07-26. This is the question the third district exists to answer
   — without it, Bandarban is just more area for the same result.)*

## Working style for this project

- Prefer small, verifiable scripts over large notebooks — each script
  in `src/` should do one thing and be independently testable.
- When something depends on a Phase 2 audit result not yet known
  (e.g. the real study start year), write the code parametrised on a
  `START_YEAR` constant at the top of the file rather than
  hardcoding a guess.
- Flag any place where a design choice in the methodology plan was
  not followed, rather than silently deviating from it.
