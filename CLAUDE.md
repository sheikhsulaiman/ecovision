# EcoVision — Claude Code project instructions

This file is project context for Claude Code. Read it in full before
making changes. It encodes decisions already made — don't relitigate
them without flagging it to the user first.

## Project summary

Undergraduate thesis: deep learning deforestation detection in
**Gazipur** and **Sylhet** districts, Bangladesh, using Landsat
imagery via Google Earth Engine. Two authors, one supervisor,
department of Educational Technology and Engineering, UFTB.

Full phase-by-phase methodology: `docs/methodology_plan.md`.
Original proposal (superseded in scope — now 2 districts not 3, and
title imagery source is corrected from "Google Earth" to "Landsat via
Google Earth Engine"): `docs/thesis_proposal.md`.

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

- [x] Phase 0 — repo scaffolded, BFD request letter sent
- [ ] Phase 1 — AOI boundaries uploaded, forest definition signed off
- [ ] Phase 2 — scene availability audit (determines real start year)
- [ ] Phase 3 — preprocessing pipeline
- [ ] Phase 4 — labels and reference sample
- [ ] Phase 5 — splits and experiment design
- [ ] Phase 6 — model development (Kaggle)
- [ ] Phase 7 — change detection and maps
- [ ] Phase 8 — accuracy assessment and area estimation
- [ ] Phase 9 — analysis
- [ ] Phase 10 — dashboard
- [ ] Phase 11 — writing

## Research questions (current)

1. How much forest cover has been lost in Gazipur and Sylhet between
   [audited start year] and 2024, and how do loss patterns differ
   between the two districts?
2. Which model — U-Net, Siamese Network, or Random Forest — performs
   best in each district, and does the best model differ between them?
3. Does adding GLCM texture features resolve natural-forest vs
   tea-plantation confusion in Sylhet?
4. Which change detection method (PCC, NDVI differencing, direct
   Siamese comparison) is most accurate against the independent
   reference sample?
5. Do traditional ML methods reach comparable accuracy to deep
   learning at a fraction of the compute cost?

## Working style for this project

- Prefer small, verifiable scripts over large notebooks — each script
  in `src/` should do one thing and be independently testable.
- When something depends on a Phase 2 audit result not yet known
  (e.g. the real study start year), write the code parametrised on a
  `START_YEAR` constant at the top of the file rather than
  hardcoding a guess.
- Flag any place where a design choice in the methodology plan was
  not followed, rather than silently deviating from it.
