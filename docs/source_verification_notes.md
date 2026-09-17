---
title: "EcoVision — source verification notes"
status: Working notes — NOT thesis prose, never include in a build
opened: 2026-08
last_reviewed: 2026-09-17
---

# Source verification notes

Working notes on citations and external datasets that did not survive
checking. **This file is not part of the thesis.** It lived as §2.10 of
`ch2_literature.md` until 2026-09-17, where it was being compiled into
Chapter 2 of the submittable document — a section addressed to the
authors, telling them what not to submit, inside the thing being
submitted. Moved here; the substantive corrections were folded into the
chapter prose where they belonged.

`src/build_latex.py` and `src/build_thesis.py` only read the files named
in their `CHAPTERS` lists, so nothing here can reach a build.

---

## 1. The "Siddik et al. (2025)" citation — UNRESOLVED, needs the authors

**Status: open.** Only the authors can close this one.

The figure of ">10,000 ha of tea in Sylhet district" is attributed to:

> Siddik, M.A., Al-Mamun, A., Siddiki, M.H., Chakraborty, B., et al.
> (2025), *Journal of Agroforestry and Environment* 18(2):102–115.

**Searches of the published literature did not locate this work.**
`docs/forest_definition.md` §307 records that a proof or preprint was
reviewed at some point — it notes "Tables 1–4 are cited in the text but
hold no data in the available proof; only district centroids appear
anywhere in the file" — so something was in hand. Whether the published
version exists and can be produced on demand is the open question.

### Where it still appears

Thesis prose no longer names Siddik. The claim survives unattributed:

- `ch4_data.md` — "a district total exceeding 10,000 ha reported in the
  literature"
- `ch7_discussion.md` §7.8 — "a reported district total exceeding
  10,000 ha"

An unsourced number is weaker than a sourced one. Either restore a
citation you can defend, or attribute the figure to a source you can
actually obtain.

The project code still names Siddik directly, in `src/tea_search_zone.py`,
`src/tea_candidates.py`, `src/labels.py`, `src/reference_sample.py`,
`gee/05_tea_digitising.js`, plus `docs/forest_definition.md` and
`docs/interpretation_protocol.md`. Code comments are not submitted, so
these are lower priority — but if the citation turns out to be
unusable, they are misleading to a future reader and should be reworded.

### The underlying claim is separately supportable

Bangladesh Tea Board and Bangladesh Tea Association figures give **167
commercial estates covering approximately 279,507 acres (≈113,100 ha)
nationally**, with Sylhet division dominant. That industry source is now
cited in `ch2_literature.md` §2.6.

**Care needed:** the BTB/BTA figure is *national*. The claim in ch4 and
§7.8 is a *Sylhet district* total. A national figure cannot be
substituted for a district figure without changing what is being
asserted. Resolve deliberately, not by find-and-replace.

---

## 2. SDPT version — RESOLVED 2026-09-17, one check still worth doing

The Spatial Database of Planted Trees was tested during this project and
found to carry no Bangladesh layer. That test ran against **SDPT v1.3**,
which carried 43 country layers. **Version 2.0 (2024) covers 158
countries.**

Chapter 7 §7.3 previously asserted, flatly, that "a global plantation
database omits Bangladesh entirely" — while Chapter 2 §2.6 stated that
v2.0 covers 158 countries. The thesis contradicted itself across two
chapters.

**What was done:** §7.3 now scopes the claim to the version actually
tested, rather than asserting something about a version nobody here has
checked. This is the honest option and it is what rule 8 requires.

**What is still worth doing (≈20 minutes, authors):** re-run the check
against SDPT v2.0 and report what it actually contains for Bangladesh.
Both outcomes are useful:

- v2.0 **does** carry Bangladeshi tea boundaries → the plantation-layer
  limitation changes materially, and a reference dataset may exist after
  all.
- v2.0 **does not** → the claim becomes considerably stronger for having
  been tested against the current version rather than a superseded one.

Until that check is run, do not restate the claim in unversioned form.
