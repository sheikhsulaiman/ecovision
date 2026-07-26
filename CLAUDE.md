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

Two deliberate exceptions, both recorded in `.gitignore`:

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

## Current phase status

Update this section as phases complete — Claude Code should read it
at the start of every session to know what's already done and what's
next, rather than re-deriving it from scratch each time.

- [x] Phase 0 — repo scaffolded, BFD request letter sent, GitHub repo
      created (private, `sheikhsulaiman/ecovision`)
- [~] Phase 1 — **partially done.** AOI boundaries built by
      `src/prepare_aoi.py`, verified against published areas, and
      uploaded as GEE assets under `projects/ecovision-503602/assets/`.
      Class scheme fixed. **Blocked on:** supervisor sign-off of
      `docs/forest_definition.md` §7. Do not start Phase 4 labelling
      until that is signed.
- [~] Phase 2 — **audit complete, 120/120 district-years, zero failures.**
      Results and Gate 2 decisions: `docs/phase2_audit.md`.
      **START_YEAR = 1988** (1985–87 have zero scenes in all three
      districts — an acquisition gap, not cloud). Epoch anchors
      **T0 = 1990, T1 = 2000, T2 = 2010, T3 = 2024**; T0 is 1990 rather
      than 1988 because 1988's observation depth is about half 1990's and
      T0 is one half of every bitemporal comparison. The annual series
      for LandTrendr still starts at 1988. Bandarban's LandTrendr
      condition is **met** (longest gap 1 year, 1991).
      **Blocked on:** supervisor confirmation of START_YEAR and anchors.
      Keep `START_YEAR` a named constant regardless — do not inline 1988.
      **Phase 3 constraint found:** the 2012 and 2013 dry seasons are
      100% Landsat 7 SLC-off in all three districts (L5 retired, L8 not
      yet delivering). Neither may be an epoch anchor, and residual gap
      fraction must be reported for both.
- [~] Phase 3 — preprocessing primitives written and verified
      (`src/preprocess.py`, 23-band stack, rule 6 check passing).
      Cross-sensor harmonisation resolved empirically: locally fitted
      coefficients replace Roy et al. on blue/red, Roy retained on green,
      local RMA on swir1, and **NIR and SWIR2 are left untransformed** —
      Roy's published values made both worse, and NBR is built from them.
      TM needs no transform (measured, not assumed). See
      `docs/phase3_harmonisation.md`. **Not done:** epoch composites, held
      until Gate 1 and Gate 2 are signed.
- [~] Phase 4 — machinery written, nothing drawn.
      `src/reference_sample.py` (`--dry-run` is the default and must stay
      so until the canopy threshold is signed) and `src/labels.py`.
      **Pre-2000 regime: Option B decided** — supervised post-2000,
      unsupervised before, with a 2000–2024 overlap comparison that makes
      the pre-2000 uncertainty a measured quantity. Note E5 (Siamese)
      therefore runs on post-2000 pairs only.
      **Gain stratum dropped** (Hansen `gain` is 2000–2012 only), its 50
      points moved to forest loss.
      **Blocked:** plantation stratum needs BFD/BFIS boundaries — now on
      the critical path, not a nice-to-have.
- [ ] Phase 5 — splits and experiment design
- [ ] Phase 6 — model development (Kaggle)
- [ ] Phase 7 — change detection and maps
- [ ] Phase 8 — accuracy assessment and area estimation
- [ ] Phase 9 — analysis
- [ ] Phase 10 — dashboard
- [ ] Phase 11 — writing

## Research questions (current)

1. How much forest cover has been lost in Gazipur, Sylhet, and
   Bandarban between [audited start year] and 2024, and how do loss
   patterns differ across the three districts?
2. Which model — U-Net, Siamese Network, or Random Forest — performs
   best in each district, and does the best model differ between them?
3. Does adding GLCM texture features resolve natural-forest vs
   tea-plantation confusion in Sylhet?
4. Which change detection method (PCC, NDVI differencing, direct
   Siamese comparison) is most accurate against the independent
   reference sample?
5. Do traditional ML methods reach comparable accuracy to deep
   learning at a fraction of the compute cost?
6. Can annual temporal segmentation (LandTrendr) separate cyclical jhum
   disturbance from permanent forest conversion in Bandarban, where
   bitemporal change detection cannot? *(Added with the Bandarban scope
   change, 2026-07-26. This is the question the third district exists
   to answer — without it, Bandarban is just more area for the same
   result.)*
7. How well do unsupervised change methods substitute for supervised
   deep learning in the years where no training labels exist? *(Added
   2026-07-26 with the Option B two-regime decision. Answered by running
   both regimes over the 2000–2024 overlap against the same reference
   sample — the measured gap is what the pre-2000 estimates' uncertainty
   rests on. If the RQ count becomes unwieldy, fold this into RQ4's
   discussion rather than dropping the overlap comparison itself.)*

## Working style for this project

- Prefer small, verifiable scripts over large notebooks — each script
  in `src/` should do one thing and be independently testable.
- When something depends on a Phase 2 audit result not yet known
  (e.g. the real study start year), write the code parametrised on a
  `START_YEAR` constant at the top of the file rather than
  hardcoding a guess.
- Flag any place where a design choice in the methodology plan was
  not followed, rather than silently deviating from it.
