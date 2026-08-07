"""Convert the drafted chapters into an Overleaf-ready LaTeX project.

    python src/build_latex.py

Output: outputs/thesis/latex/            (the project tree)
        outputs/thesis/EcoVision_thesis_overleaf.zip

Upload the zip to Overleaf: New Project -> Upload Project. It compiles
with pdfLaTeX and needs nothing installed locally, which matters because
this machine has no TeX distribution.

WHY report AND NOT IEEEtran
---------------------------
IEEEtran is a two-column conference and journal class. A 13,000 word
thesis set in it is unreadable, and no department asks for it. What
departments ask for from IEEE is the citation style, so the class here is
`report` — single column, 12pt, 1.5 spaced, bound margin — with
IEEEtran.bst for numbered references.

CHARACTER HANDLING
------------------
The chapters are written in Markdown with real typographic characters:
en dashes, kappa, sigma, greater-or-equal, multiplication signs. pdfLaTeX
does not accept most of these as literal UTF-8, and the failure mode is a
compile error a hundred lines from the actual character. Every one is
therefore substituted for its LaTeX command before anything else happens,
and LaTeX's own special characters are escaped first so the substitutions
are not themselves mangled.
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHAPTER_DIR = REPO / "docs" / "thesis"
FIG_DIR = REPO / "outputs" / "figures"
OUT_DIR = REPO / "outputs" / "thesis"
TEX_DIR = OUT_DIR / "latex"

TITLE = ("Deep Learning for Deforestation Detection in Bangladesh: "
         "A Three-District Comparison of Classification and Change "
         "Detection Methods Using Landsat Imagery")
AUTHORS = ["Sheikh Sulaiman Sony", "Jalal Uddin Mohammad Akbar"]
SUPERVISOR = "[Supervisor name]"
DEPARTMENT = "Department of Educational Technology and Engineering"
UNIVERSITY = "University of Frontier Technology, Bangladesh"
DATE = "August 2026"

CHAPTERS = [
    ("ch1_introduction.md", "Introduction", "ch1"),
    ("ch2_literature.md", "Literature Review", "ch2"),
    ("ch3_study_area.md", "Study Area", "ch3"),
    ("ch4_data.md", "Data", "ch4"),
    ("ch5_methodology.md", "Methodology", "ch5"),
    ("ch6_results.md", "Results", "ch6"),
    ("ch8_discussion.md", "Discussion and Conclusions", "ch7"),
]

# Keyed on (chapter, heading cue). Chapter matters: "Cross-sensor
# harmonisation" is a heading in BOTH the literature review and the
# methodology, and keying on the heading alone put the results figure in
# Chapter 2 where the method has not yet been described.
FIGURES = {
    ("ch3", "Rationale for a three-district design"): (
        "study_area.png", "fig:studyarea",
        "The three study districts in national context, and their extent "
        "and dominant forest-loss mechanism at a common scale."),
    ("ch5", "Cross-sensor harmonisation"): (
        "harmonisation.png", "fig:harmonisation",
        "Residual RMSE per band for each candidate transform, with the "
        "adopted transform marked."),
    ("ch5", "Spatial partitioning"): (
        "block_splits.png", "fig:splits",
        "Spatially disjoint 10\\,km block assignment per district."),
    ("ch4", "Temporal design"): (
        "scene_availability.png", "fig:scenes",
        "Usable Landsat scenes per district-year."),
}

# LaTeX specials escaped FIRST, then typography substituted. Order
# matters: escaping after substitution would turn \kappa into
# \textbackslash kappa.
ESCAPES = [
    ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
    ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
    ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
]

UNICODE = [
    ("\u2014", "---"), ("\u2013", "--"),
    ("\u2018", "`"), ("\u2019", "'"),
    ("\u201c", "``"), ("\u201d", "''"),
    ("\u2265", r"$\geq$"), ("\u2264", r"$\leq$"),
    ("\u00b1", r"$\pm$"), ("\u00d7", r"$\times$"),
    ("\u2248", r"$\approx$"), ("\u2192", r"$\rightarrow$"),
    ("\u03ba", r"$\kappa$"), ("\u03c3", r"$\sigma$"),
    ("\u00b2", r"$^{2}$"), ("\u00b3", r"$^{3}$"),
    ("\u2713", r"$\checkmark$"), ("\u00b7", r"$\cdot$"),
    ("\u00a0", "~"), ("\u2026", r"\dots{}"),
    ("\u00e9", r"\'e"), ("\u2011", "-"),
    ("\u00a7", r"\S{}"), ("\u2212", r"$-$"),
    ("\u00b0", r"\textdegree{}"), ("\u00ad", ""),
]


def report_leftovers(text: str, where: str) -> str:
    """Substitute anything still non-ASCII and say what it was.

    pdfLaTeX fails on an unmapped character with an error pointing
    somewhere other than the character, so a silent pass-through costs
    more time than it saves. Two rounds of this found the section sign and
    U+2212 MINUS, neither of which is the ASCII hyphen they resemble.
    """
    leftovers = sorted({ch for ch in text if ord(ch) > 127})
    if leftovers:
        import unicodedata

        for ch in leftovers:
            print(f"    {where}: unmapped U+{ord(ch):04X} "
                  f"{unicodedata.name(ch, '?')} \u2014 replaced with '?'")
            text = text.replace(ch, "?")
    return text

REFERENCES = r"""
@article{breiman2001,
  author  = {Breiman, Leo},
  title   = {Random Forests},
  journal = {Machine Learning}, volume = {45}, number = {1},
  pages   = {5--32}, year = {2001}
}
@article{cohen1960,
  author  = {Cohen, Jacob},
  title   = {A Coefficient of Agreement for Nominal Scales},
  journal = {Educational and Psychological Measurement},
  volume  = {20}, number = {1}, pages = {37--46}, year = {1960}
}
@inproceedings{daudt2018,
  author    = {Daudt, Rodrigo Caye and Le Saux, Bertrand and Boulch, Alexandre},
  title     = {Fully Convolutional Siamese Networks for Change Detection},
  booktitle = {Proc. 25th IEEE Int. Conf. Image Processing (ICIP)},
  address   = {Athens, Greece}, pages = {4063--4067}, year = {2018}
}
@article{hansen2013,
  author  = {Hansen, M. C. and Potapov, P. V. and Moore, R. and Hancher, M.
             and Turubanova, S. A. and Tyukavina, A. and others},
  title   = {High-Resolution Global Maps of 21st-Century Forest Cover Change},
  journal = {Science}, volume = {342}, number = {6160},
  pages   = {850--853}, year = {2013}, doi = {10.1126/science.1244693}
}
@article{haralick1973,
  author  = {Haralick, Robert M. and Shanmugam, K. and Dinstein, Its'Hak},
  title   = {Textural Features for Image Classification},
  journal = {IEEE Trans. Systems, Man, and Cybernetics},
  volume  = {SMC-3}, number = {6}, pages = {610--621}, year = {1973}
}
@article{kennedy2010,
  author  = {Kennedy, Robert E. and Yang, Zhiqiang and Cohen, Warren B.},
  title   = {Detecting Trends in Forest Disturbance and Recovery Using
             Yearly Landsat Time Series: 1. LandTrendr --- Temporal
             Segmentation Algorithms},
  journal = {Remote Sensing of Environment}, volume = {114}, number = {12},
  pages   = {2897--2910}, year = {2010}
}
@article{olofsson2014,
  author  = {Olofsson, Pontus and Foody, Giles M. and Herold, Martin and
             Stehman, Stephen V. and Woodcock, Curtis E. and Wulder, Michael A.},
  title   = {Good Practices for Estimating Area and Assessing Accuracy of
             Land Change},
  journal = {Remote Sensing of Environment}, volume = {148},
  pages   = {42--57}, year = {2014}, doi = {10.1016/j.rse.2014.02.015}
}
@article{pekel2016,
  author  = {Pekel, Jean-Fran\c{c}ois and Cottam, Andrew and Gorelick, Noel
             and Belward, Alan S.},
  title   = {High-Resolution Mapping of Global Surface Water and Its
             Long-Term Changes},
  journal = {Nature}, volume = {540}, number = {7633},
  pages   = {418--422}, year = {2016}, doi = {10.1038/nature20584}
}
@inproceedings{ronneberger2015,
  author    = {Ronneberger, Olaf and Fischer, Philipp and Brox, Thomas},
  title     = {U-Net: Convolutional Networks for Biomedical Image Segmentation},
  booktitle = {Medical Image Computing and Computer-Assisted Intervention
               (MICCAI)}, pages = {234--241}, year = {2015}
}
@article{roy2016,
  author  = {Roy, D. P. and Kovalskyy, V. and Zhang, H. K. and Vermote, E. F.
             and Yan, L. and Kumar, S. S. and Egorov, A.},
  title   = {Characterization of Landsat-7 to Landsat-8 Reflective Wavelength
             and Normalized Difference Vegetation Index Continuity},
  journal = {Remote Sensing of Environment}, volume = {185},
  pages   = {57--70}, year = {2016}
}
@techreport{sdpt2024,
  author      = {Richter, Jessica and Goldman, Elizabeth and Harris, Nancy
                 and Gibbs, David and others},
  title       = {Spatial Database of Planted Trees (SDPT) Version 2.0},
  institution = {World Resources Institute}, address = {Washington, DC},
  year        = {2024}
}
@misc{bta,
  author = {{Bangladesh Tea Association}},
  title  = {Overview of the Tea Industry of Bangladesh},
  howpublished = {\url{https://btabd.com/overview}},
  note   = {Accessed: Aug. 2026}
}
"""


def escape(text: str) -> str:
    for old, new in ESCAPES:
        text = text.replace(old, new)
    for old, new in UNICODE:
        text = text.replace(old, new)
    return text


def inline(text: str) -> str:
    """Markdown emphasis to LaTeX, applied after escaping."""
    text = escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\\textit{\1}", text)
    text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)
    return text


def convert(path: Path, title: str, key: str, placed: set[str]) -> str:
    lines = path.read_text(encoding="utf-8").split("\n")
    out = [f"\\chapter{{{escape(title)}}}", f"\\label{{ch:{key}}}", ""]
    i = 0
    pending = None

    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith("> "):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip("> ").rstrip())
                i += 1
            body = inline(" ".join(b for b in block if b))
            out += [r"\begin{quote}\small\itshape", body, r"\end{quote}", ""]
            continue

        if line.startswith("# "):
            i += 1
            continue

        if line.startswith("### "):
            out += [f"\\subsection{{{inline(line[4:])}}}", ""]
            i += 1
            continue

        if line.startswith("## "):
            heading = re.sub(r"^\d+\.\d+\s+", "", line[3:])
            out += [f"\\section{{{inline(heading)}}}", ""]
            for (chap, cue), spec in FIGURES.items():
                if (chap == key and cue.lower() in heading.lower()
                        and spec[0] not in placed):
                    pending = spec
                    placed.add(spec[0])
            i += 1
            continue

        # table
        if line.startswith("|") and i + 1 < len(lines) and set(
                lines[i + 1].replace("|", "").replace(" ", "")) <= {"-", ":"}:
            header = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            ncol = len(header)
            # First column left, remainder right: these tables are almost
            # all a label followed by numbers.
            spec = "l" + "r" * (ncol - 1)
            out += [r"\begin{table}[htbp]", r"\centering", r"\small",
                    f"\\begin{{tabular}}{{{spec}}}", r"\toprule",
                    " & ".join(inline(h) for h in header) + r" \\",
                    r"\midrule"]
            for row in rows:
                cells = (row + [""] * ncol)[:ncol]
                out.append(" & ".join(inline(c) for c in cells) + r" \\")
            out += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
            continue

        if re.match(r"^[-*] ", line):
            items = []
            while i < len(lines) and re.match(r"^[-*] ", lines[i].rstrip()):
                items.append(inline(lines[i].rstrip()[2:]))
                i += 1
            out += [r"\begin{itemize}"] + [f"  \\item {t}" for t in items] + \
                   [r"\end{itemize}", ""]
            continue

        if re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i].rstrip()):
                items.append(inline(re.sub(r"^\d+\. ", "", lines[i].rstrip())))
                i += 1
            out += [r"\begin{enumerate}"] + [f"  \\item {t}" for t in items] + \
                   [r"\end{enumerate}", ""]
            continue

        if line.startswith("---") or not line:
            i += 1
            continue

        out += [inline(line), ""]
        i += 1

        if pending:
            fname, label, caption = pending
            if (FIG_DIR / fname).exists():
                out += [r"\begin{figure}[htbp]", r"\centering",
                        f"\\includegraphics[width=\\textwidth]{{figures/{fname}}}",
                        f"\\caption{{{caption}}}", f"\\label{{{label}}}",
                        r"\end{figure}", ""]
            pending = None

    return "\n".join(out)


MAIN = r"""%% EcoVision -- undergraduate thesis
%% Compile on Overleaf with pdfLaTeX. Menu > Compiler > pdfLaTeX.
%% Run twice, or let Overleaf handle it, so the contents and the
%% bibliography resolve.

\documentclass[12pt,a4paper,oneside]{report}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{times}
\usepackage[a4paper,left=3.2cm,right=2.5cm,top=2.5cm,bottom=2.5cm]{geometry}
\usepackage{setspace}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{amsmath,amssymb}
\usepackage{url}
\usepackage[hidelinks]{hyperref}
\usepackage{titlesec}
\usepackage{caption}

\onehalfspacing
\setlength{\parskip}{6pt}
\setlength{\parindent}{0pt}
\captionsetup{font=small,labelfont=bf}

\titleformat{\chapter}[hang]{\normalfont\Large\bfseries}{\thechapter.}{10pt}{\Large}
\titlespacing*{\chapter}{0pt}{0pt}{20pt}

\begin{document}

%% ---------- title page ----------
\begin{titlepage}
\centering
\vspace*{2cm}
{\LARGE\bfseries __TITLE__\par}
\vspace{2cm}
{\normalsize A thesis submitted in partial fulfilment of the requirements\\
for the degree of Bachelor of Science\par}
\vspace{1.5cm}
{\large\bfseries __AUTHORS__\par}
\vspace{1.5cm}
{\normalsize Supervisor: __SUPERVISOR__\par}
\vspace{0.5cm}
{\normalsize __DEPARTMENT__\par}
{\normalsize __UNIVERSITY__\par}
\vfill
{\normalsize __DATE__\par}
\end{titlepage}

%% ---------- abstract ----------
\chapter*{Abstract}
\addcontentsline{toc}{chapter}{Abstract}

Satellite-based forest monitoring methods are largely developed and
validated over landscapes where forest loss is abrupt, permanent and
spectrally unambiguous. This study asks how much the choice of method
matters when those conditions do not hold. Forest cover change is
measured across three districts of Bangladesh --- Gazipur, Sylhet and
Bandarban --- between 1988 and 2024 using Landsat Collection~2 imagery,
with the districts selected because each contributes a different loss
mechanism: abrupt permanent conversion, gradual degradation with
plantation confusion, and cyclical clearing and regrowth under shifting
cultivation.

Random Forest, U-Net, and a stacked ensemble were compared under
spatially disjoint block splits, alongside post-classification
comparison, spectral index differencing, and LandTrendr temporal
segmentation. Accuracy was assessed against an independently interpreted
stratified reference sample, and all areas are reported through the
Olofsson stratified estimator with 95\% confidence intervals.

No single model won across all three districts, and the determining
variable was the structure of the target class rather than district
complexity in the abstract. Random Forest outperformed U-Net where
labelled data was scarce; U-Net outperformed Random Forest by more than
an order of magnitude on tea plantation, a class defined by spatial
arrangement rather than spectral response. Adding GLCM texture features
improved plantation F1 from 0.370 to 0.452, and the improvement was
specific to that class.

The clearest methodological result concerns temporal design. Of
88,122\,ha disturbed in Bandarban since 1988, only 16.4\% was permanent
conversion; a bitemporal comparison would have reported approximately
four times the deforestation that occurred. Two trained interpreters
working from the same written protocol agreed at chance level on the
forest boundary ($\kappa = 0.038$), which bounds what any accuracy figure
over this landscape can currently mean.

\vspace{1em}
\noindent\textbf{Keywords:} deforestation, Landsat, Google Earth Engine,
U-Net, Random Forest, LandTrendr, shifting cultivation, accuracy
assessment, Bangladesh

%% ---------- front matter ----------
\tableofcontents
\listoffigures
\listoftables

%% ---------- chapters ----------
__INPUTS__

%% ---------- references ----------
\bibliographystyle{IEEEtran}
\bibliography{refs}
\addcontentsline{toc}{chapter}{References}

\end{document}
"""

README = """EcoVision thesis — Overleaf project
===================================

1. Go to overleaf.com -> New Project -> Upload Project
2. Upload this zip
3. Menu -> Compiler -> pdfLaTeX
4. Recompile

If the references show as [?], compile once more. BibTeX needs a second
pass to resolve, and Overleaf sometimes stops after the first.

Files
-----
main.tex        title page, abstract, front matter, chapter inputs
chapters/*.tex  one file per chapter, generated from docs/thesis/*.md
figures/*.png   generated by src/figures.py
refs.bib        verified references

Do not edit chapters/*.tex by hand if you intend to regenerate: they are
built from the Markdown in docs/thesis/ by src/build_latex.py, and a
rebuild overwrites them. Edit the Markdown, or stop regenerating and take
the .tex as the source of truth from here on.

Two things still to fix
-----------------------
* The supervisor name on the title page is a placeholder.
* Chapter 2 section 2.10 records two claims that could not be verified
  and that appear in Chapters 4 and 8. Resolve before submission.
"""


def main() -> int:
    if TEX_DIR.exists():
        shutil.rmtree(TEX_DIR)
    (TEX_DIR / "chapters").mkdir(parents=True)
    (TEX_DIR / "figures").mkdir(parents=True)

    inputs = []
    placed: set[str] = set()
    for fname, title, key in CHAPTERS:
        path = CHAPTER_DIR / fname
        if not path.exists():
            print(f"  missing {fname}, skipped")
            continue
        body = report_leftovers(convert(path, title, key, placed),
                                f"{key}.tex")
        (TEX_DIR / "chapters" / f"{key}.tex").write_text(body, encoding="utf-8")
        inputs.append(f"\\input{{chapters/{key}}}")
        print(f"  {key}.tex  <- {fname}")

    for fig in FIG_DIR.glob("*.png"):
        shutil.copy(fig, TEX_DIR / "figures" / fig.name)

    main_tex = (MAIN
                .replace("__TITLE__", TITLE)
                .replace("__AUTHORS__", r" \\ ".join(AUTHORS))
                .replace("__SUPERVISOR__", SUPERVISOR)
                .replace("__DEPARTMENT__", DEPARTMENT)
                .replace("__UNIVERSITY__", UNIVERSITY)
                .replace("__DATE__", DATE)
                .replace("__INPUTS__", "\n".join(inputs)))
    (TEX_DIR / "main.tex").write_text(main_tex, encoding="utf-8")
    (TEX_DIR / "refs.bib").write_text(REFERENCES.strip() + "\n", encoding="utf-8")
    (TEX_DIR / "README.txt").write_text(README, encoding="utf-8")

    out = OUT_DIR / "EcoVision_thesis_overleaf.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(TEX_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(TEX_DIR))

    print(f"\nWritten: {out.relative_to(REPO)}  "
          f"({out.stat().st_size / 1e6:.1f} MB)")
    print("Overleaf: New Project -> Upload Project -> this zip, then "
          "compile with pdfLaTeX.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
