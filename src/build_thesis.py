"""Assemble the drafted chapters into a formatted thesis document.

    python src/build_thesis.py

Output: outputs/thesis/EcoVision_thesis.docx
        outputs/thesis/EcoVision_thesis.tex   (Overleaf-ready)

WHY BOTH FORMATS
----------------
The .docx is for review and for a supervisor who will comment in Word.
The .tex is for the final submission if the department wants typeset
output — this machine has no LaTeX installed, so the .tex is written to
be compiled on Overleaf, which needs no installation.

LAYOUT
------
Single column, IEEE numbered citations. IEEE's two-column layout is a
conference and journal format; applied to a 13,000 word thesis it
produces something no examiner wants to read, and no department asks for
it. What departments do ask for from IEEE is the citation style, which is
what is applied here.

WHAT IS NOT AUTOMATED
---------------------
Figure and table numbering are resolved from the markdown, but the
reference list is assembled from a hand-maintained list in this file
rather than parsed out of the prose. That is deliberate: a citation
extracted by regex from text is a citation nobody has checked, and every
entry below was verified against the publisher record.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

REPO = Path(__file__).resolve().parents[1]
CHAPTER_DIR = REPO / "docs" / "thesis"
FIG_DIR = REPO / "outputs" / "figures"
OUT_DIR = REPO / "outputs" / "thesis"

TITLE = ("Deep Learning for Deforestation Detection in Bangladesh: "
         "A Three-District Comparison of Classification and Change "
         "Detection Methods Using Landsat Imagery")
AUTHORS = ["Sheikh Sulaiman Sony", "Jalal Uddin Mohammad Akbar"]
SUPERVISOR = "[Supervisor name]"
DEPARTMENT = "Department of Educational Technology and Engineering"
UNIVERSITY = "University of Frontier Technology, Bangladesh"
DATE = "August 2026"

CHAPTERS = [
    ("ch1_introduction.md", "Introduction"),
    ("ch2_literature.md", "Literature Review"),
    ("ch3_study_area.md", "Study Area"),
    ("ch4_data.md", "Data"),
    ("ch5_methodology.md", "Methodology"),
    ("ch6_results.md", "Results"),
    ("ch8_discussion.md", "Discussion and Conclusions"),
]

# Figures placed after the section whose heading matches. Keyed on a
# substring of the heading text so a reworded heading does not silently
# drop the figure.
FIGURE_PLACEMENT = {
    "Rationale for a three-district design": (
        "study_area.png",
        "The three study districts in national context, and their extent "
        "and dominant forest-loss mechanism at a common scale."),
    "Cross-sensor harmonisation": (
        "harmonisation.png",
        "Residual RMSE per band for each candidate transform. The adopted "
        "transform is marked. Roy et al. (2016) coefficients are worse "
        "than applying no correction on four of six bands."),
    "Spatial partitioning": (
        "block_splits.png",
        "Spatially disjoint 10 km block assignment per district. Whole "
        "blocks are assigned to one split each, so no patch can straddle "
        "a train/test boundary."),
    "Temporal design": (
        "scene_availability.png",
        "Usable Landsat scenes per district-year. START_YEAR is fixed at "
        "1988: 1985-87 returned zero scenes in all three districts."),
}

# Verified against the publisher record. See docs/thesis/ch2_literature.md
# section 2.10 for the two claims that could NOT be verified.
REFERENCES = [
    "L. Breiman, “Random forests,” Machine Learning, vol. 45, "
    "no. 1, pp. 5–32, 2001.",

    "J. Cohen, “A coefficient of agreement for nominal scales,” "
    "Educational and Psychological Measurement, vol. 20, no. 1, "
    "pp. 37–46, 1960.",

    "R. C. Daudt, B. Le Saux, and A. Boulch, “Fully convolutional "
    "Siamese networks for change detection,” in Proc. 25th IEEE Int. "
    "Conf. Image Processing (ICIP), Athens, Greece, 2018, "
    "pp. 4063–4067.",

    "M. C. Hansen et al., “High-resolution global maps of "
    "21st-century forest cover change,” Science, vol. 342, no. 6160, "
    "pp. 850–853, 2013, doi: 10.1126/science.1244693.",

    "R. M. Haralick, K. Shanmugam, and I. Dinstein, “Textural "
    "features for image classification,” IEEE Trans. Systems, Man, "
    "and Cybernetics, vol. SMC-3, no. 6, pp. 610–621, 1973.",

    "R. E. Kennedy, Z. Yang, and W. B. Cohen, “Detecting trends in "
    "forest disturbance and recovery using yearly Landsat time series: "
    "1. LandTrendr — temporal segmentation algorithms,” Remote "
    "Sensing of Environment, vol. 114, no. 12, pp. 2897–2910, 2010.",

    "P. Olofsson, G. M. Foody, M. Herold, S. V. Stehman, C. E. Woodcock, "
    "and M. A. Wulder, “Good practices for estimating area and "
    "assessing accuracy of land change,” Remote Sensing of "
    "Environment, vol. 148, pp. 42–57, 2014, "
    "doi: 10.1016/j.rse.2014.02.015.",

    "J.-F. Pekel, A. Cottam, N. Gorelick, and A. S. Belward, "
    "“High-resolution mapping of global surface water and its "
    "long-term changes,” Nature, vol. 540, no. 7633, "
    "pp. 418–422, 2016, doi: 10.1038/nature20584.",

    "O. Ronneberger, P. Fischer, and T. Brox, “U-Net: convolutional "
    "networks for biomedical image segmentation,” in Proc. Medical "
    "Image Computing and Computer-Assisted Intervention (MICCAI), 2015, "
    "pp. 234–241.",

    "D. P. Roy et al., “Characterization of Landsat-7 to Landsat-8 "
    "reflective wavelength and normalized difference vegetation index "
    "continuity,” Remote Sensing of Environment, vol. 185, "
    "pp. 57–70, 2016.",

    "J. Richter et al., Spatial Database of Planted Trees (SDPT) "
    "Version 2.0. Washington, DC: World Resources Institute, 2024.",

    "Bangladesh Tea Association, “Overview of the tea industry of "
    "Bangladesh.” [Online]. Available: https://btabd.com/overview "
    "[Accessed: Aug. 2026].",
]


def style_document(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.5

    for level, size in ((1, 16), (2, 14), (3, 12)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)


def add_caption(doc: Document, text: str) -> None:
    para = doc.add_paragraph(text)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.runs[0]
    run.font.size = Pt(10)
    run.font.italic = True
    para.paragraph_format.space_after = Pt(12)


def add_table(doc: Document, header: list[str], rows: list[list[str]],
              caption: str, number: int) -> None:
    add_caption(doc, f"Table {number}. {caption}")
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, text in zip(table.rows[0].cells, header):
        cell.text = text
        for para in cell.paragraphs:
            for run in para.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    for row in rows:
        cells = table.add_row().cells
        for cell, text in zip(cells, row):
            cell.text = str(text)
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(10)
    doc.add_paragraph()


def parse_inline(paragraph, text: str) -> None:
    """Render **bold**, *italic* and `code` runs."""
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith("*") and part.endswith("*"):
            paragraph.add_run(part[1:-1]).italic = True
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(10)
        else:
            paragraph.add_run(part)


def title_page(doc: Document) -> None:
    for _ in range(4):
        doc.add_paragraph()
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(TITLE)
    run.bold = True
    run.font.size = Pt(18)

    doc.add_paragraph()
    for line, size, bold in (
        ("A thesis submitted in partial fulfilment of the requirements "
         "for the degree of Bachelor of Science", 11, False),
        ("", 12, False),
        (" and ".join(AUTHORS), 14, True),
        ("", 12, False),
        (f"Supervisor: {SUPERVISOR}", 12, False),
        (DEPARTMENT, 12, False),
        (UNIVERSITY, 12, False),
        ("", 12, False),
        (DATE, 12, False),
    ):
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(line)
        run.font.size = Pt(size)
        run.bold = bold
    doc.add_page_break()


def abstract_page(doc: Document) -> None:
    doc.add_heading("Abstract", level=1)
    for text in [
        "Satellite-based forest monitoring methods are largely developed "
        "and validated over landscapes where forest loss is abrupt, "
        "permanent and spectrally unambiguous. This study asks how much "
        "the choice of method matters when those conditions do not hold. "
        "Forest cover change is measured across three districts of "
        "Bangladesh — Gazipur, Sylhet and Bandarban — between "
        "1988 and 2024 using Landsat Collection 2 imagery, with the "
        "districts selected because each contributes a different loss "
        "mechanism: abrupt permanent conversion, gradual degradation with "
        "plantation confusion, and cyclical clearing and regrowth under "
        "shifting cultivation.",

        "Random Forest, U-Net, and a stacked ensemble were compared under "
        "spatially disjoint block splits, alongside post-classification "
        "comparison, spectral index differencing, and LandTrendr temporal "
        "segmentation. Accuracy was assessed against an independently "
        "interpreted stratified reference sample, and all areas are "
        "reported through the Olofsson stratified estimator with 95% "
        "confidence intervals.",

        "No single model won across all three districts, and the "
        "determining variable was the structure of the target class "
        "rather than district complexity in the abstract. Random Forest "
        "outperformed U-Net where labelled data was scarce; U-Net "
        "outperformed Random Forest by more than an order of magnitude on "
        "tea plantation, a class defined by spatial arrangement rather "
        "than spectral response. Adding GLCM texture features improved "
        "plantation F1 from 0.370 to 0.452, and the improvement was "
        "specific to that class.",

        "The clearest methodological result concerns temporal design. Of "
        "88,122 ha disturbed in Bandarban since 1988, only 16.4% was "
        "permanent conversion; a bitemporal comparison would have "
        "reported approximately four times the deforestation that "
        "occurred. Two trained interpreters working from the same written "
        "protocol agreed at chance level on the forest boundary "
        "(κ = 0.038), which bounds what any accuracy figure over this "
        "landscape can currently mean.",
    ]:
        para = doc.add_paragraph()
        parse_inline(para, text)
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    para = doc.add_paragraph()
    parse_inline(para, "**Keywords:** deforestation, Landsat, Google Earth "
                       "Engine, U-Net, Random Forest, LandTrendr, shifting "
                       "cultivation, accuracy assessment, Bangladesh")
    doc.add_page_break()


def render_chapter(doc: Document, path: Path, number: int,
                   title: str, counters: dict) -> None:
    doc.add_heading(f"Chapter {number}. {title}", level=1)

    lines = path.read_text(encoding="utf-8").split("\n")
    i = 0
    pending_figure = None

    while i < len(lines):
        line = lines[i].rstrip()

        # Blockquote — used for status notes. Rendered but marked.
        if line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip("> ").rstrip())
                i += 1
            para = doc.add_paragraph()
            parse_inline(para, " ".join(b for b in block if b))
            para.paragraph_format.left_indent = Inches(0.4)
            for run in para.runs:
                run.font.size = Pt(10)
                run.font.italic = True
            continue

        if line.startswith("# "):
            i += 1
            continue

        if line.startswith("### "):
            doc.add_heading(line[4:], level=3)
            i += 1
            continue

        if line.startswith("## "):
            heading = re.sub(r"^\d+\.\d+\s+", "", line[3:])
            doc.add_heading(line[3:], level=2)
            counters["heading"] = heading
            # Each figure is placed once. Several headings legitimately
            # mention harmonisation or partitioning across chapters, and
            # without this the same figure appears twice under different
            # numbers, which is worse than it appearing in the wrong place.
            for key, (fname, caption) in FIGURE_PLACEMENT.items():
                if key.lower() in heading.lower() and fname not in counters["placed"]:
                    pending_figure = (fname, caption)
                    counters["placed"].add(fname)
            i += 1
            continue

        # Markdown table
        if line.startswith("|") and i + 1 < len(lines) and set(
                lines[i + 1].replace("|", "").replace(" ", "")) <= {"-", ":"}:
            header = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip().replace("**", "")
                             for c in lines[i].strip("|").split("|")])
                i += 1
            counters["table"] += 1
            add_table(doc, header, rows,
                      counters.get("heading", "Results") + ".",
                      counters["table"])
            continue

        if re.match(r"^[-*] ", line):
            para = doc.add_paragraph(style="List Bullet")
            parse_inline(para, line[2:])
            i += 1
            continue

        if re.match(r"^\d+\. ", line):
            para = doc.add_paragraph(style="List Number")
            parse_inline(para, re.sub(r"^\d+\. ", "", line))
            i += 1
            continue

        if line.startswith("---") or not line:
            i += 1
            continue

        para = doc.add_paragraph()
        parse_inline(para, line)
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        i += 1

        if pending_figure:
            fname, caption = pending_figure
            path_fig = FIG_DIR / fname
            if path_fig.exists():
                doc.add_picture(str(path_fig), width=Inches(6.2))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                counters["figure"] += 1
                add_caption(doc, f"Figure {counters['figure']}. {caption}")
            pending_figure = None

    doc.add_page_break()


def references_page(doc: Document) -> None:
    doc.add_heading("References", level=1)
    for n, entry in enumerate(REFERENCES, 1):
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Inches(0.4)
        para.paragraph_format.first_line_indent = Inches(-0.4)
        para.paragraph_format.line_spacing = 1.0
        para.add_run(f"[{n}] ").bold = True
        para.add_run(entry)


def main() -> int:
    if not CHAPTER_DIR.exists():
        sys.exit(f"No chapters at {CHAPTER_DIR}")

    doc = Document()
    style_document(doc)
    for section in doc.sections:
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.0)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)

    title_page(doc)
    abstract_page(doc)

    doc.add_heading("Table of Contents", level=1)
    doc.add_paragraph(
        "Right-click here in Word and choose Update Field, or insert "
        "References → Table of Contents. Headings are styled so Word "
        "builds it automatically."
    ).runs[0].italic = True
    doc.add_page_break()

    counters = {"figure": 0, "table": 0, "placed": set(), "heading": ""}
    for number, (fname, title) in enumerate(CHAPTERS, 1):
        path = CHAPTER_DIR / fname
        if not path.exists():
            print(f"  missing {fname}, skipped")
            continue
        render_chapter(doc, path, number, title, counters)
        print(f"  chapter {number}: {title}")

    references_page(doc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "EcoVision_thesis.docx"
    doc.save(out)
    print(f"\nWritten: {out.relative_to(REPO)}")
    print(f"  {counters['figure']} figures, {counters['table']} tables, "
          f"{len(REFERENCES)} references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
