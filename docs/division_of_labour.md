# EcoVision — division of labour

**Revised 2026-07-26.** The original plan split the technical work
between two authors. It no longer does: Author A carries the analysis,
Author B carries the written report and the reference-sample overlap.

This file records what will actually happen, not what was originally
intended. Keep it accurate — an inaccurate division-of-labour statement
is worse than none, because it is the document an examiner reads when
asking what each author contributed.

| Area | Owner | Notes |
|---|---|---|
| GEE scripting, AOI preparation | Author A | |
| Scene availability audit | Author A | Complete — `docs/phase2_audit.md` |
| Preprocessing pipeline, composites, indices | Author A | |
| Cross-sensor harmonisation | Author A | Complete — `docs/phase3_harmonisation.md` |
| Model implementation (RF, U-Net, Siamese) | Author A | |
| Gazipur analysis | Author A | |
| Sylhet analysis | Author A | |
| Bandarban analysis | Author A | Includes the LandTrendr cyclical-vs-permanent jhum split |
| Change detection method comparison | Author A | |
| Accuracy assessment, area estimation | Author A | |
| Dashboard | Author A | |
| **Reference sample — full interpretation** | **Author A** | 600 points × 3 districts = 1,800 |
| **Reference sample — overlap interpretation** | **Author B** | 150 points × 3 districts = 450, independent, for Cohen's κ |
| **Thesis document — all chapters** | **Author B** | Drafting from Author A's methods records and results |
| Literature review | Author B | 30–40 references needed; currently 8 |
| Paper draft | Both | |

## The reference-sample overlap is not optional

Gate 4 requires Cohen's κ between two independent interpreters. With a
single interpreter it cannot be computed, and the thesis cannot state
that dual independent interpretation occurred if it did not.

Author B's 450 points are what keeps that deliverable real. They must be
interpreted **without seeing Author A's answers** — the independence is
the entire content of the number. Compute with `src/kappa.py`, which
reads the two files separately and never merges them.

## Chapter authorship (for the record)

Author B drafts all chapters; Author A reviews for technical accuracy and
supplies every number, figure, and table. No figure or statistic enters
the document except from a script in `src/` (`docs/README.md` rule 2).

| Chapter | Primary author | Technical reviewer |
|---|---|---|
| 1. Introduction | Author B | Author A |
| 2. Literature review | Author B | Author A |
| 3. Study area | Author B | Author A |
| 4. Data | Author B | Author A |
| 5. Methods | Author B | Author A |
| 6. Accuracy assessment | Author B | Author A |
| 7. Results | Author B | Author A |
| 8. Discussion | Author B | Author A |
| 9. Conclusion | Author B | Author A |

## Sign-off

Both authors and the supervisor should agree this reflects reality before
Phase 4 interpretation begins. Changing it later is fine; discovering at
submission that it was never accurate is not.

- Author A: Sheikh Sulaiman Sony ______________________  Date: __________
- Author B: Jalal Uddin Mohammad Akbar ______________________  Date: __________
- Supervisor acknowledged: ______________________  Date: __________
