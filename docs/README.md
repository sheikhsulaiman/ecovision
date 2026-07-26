# EcoVision — repository guide

This repo holds all code for the EcoVision deforestation thesis
(Gazipur and Sylhet districts, Bangladesh). See
`docs/methodology_plan.md` for the full phase-by-phase plan.

## Rules

1. **Nothing derived is committed.** If a script in `src/` or `gee/`
   can regenerate a file, that file stays out of git (see `.gitignore`).
   Two exceptions, both justified in `.gitignore` and `CLAUDE.md`:
   `data/reference/*.csv` (hand-made, irreplaceable) and
   `outputs/figures/` + `outputs/tables/` (small, kept as an audit
   trail of how reported numbers changed). `outputs/maps/` is ignored.
2. **Every thesis figure must trace to a script.** If you hand-edited
   a figure in an image tool, redo it in code — reviewers and
   examiners may ask "how was this produced".
3. **Reference-sample interpretation is logged, not overwritten.**
   Keep both authors' independent interpretations in
   `data/reference/` before reconciliation; don't merge in place.

## Setup

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

You'll also need the Earth Engine Python API authenticated once:

```bash
earthengine authenticate
```

## Folder map

| Folder | Contents |
|---|---|
| `gee/` | Earth Engine JavaScript — AOI, scene audit, composites, exports |
| `data/vector/` | AOI boundaries, BFD shapefiles (once received) |
| `data/reference/` | Reference-sample interpretation CSVs (both authors) |
| `data/raw/`, `data/patches/` | Gitignored — regenerate from `gee/` scripts |
| `src/` | Python — dataset loading, models, training, evaluation |
| `src/area_estimation.py` | Olofsson et al. (2014) adjusted-area estimator |
| `notebooks/` | Exploratory analysis only — no thesis figures generated here directly |
| `outputs/` | Maps, figures, tables — regenerable from `src/` |
