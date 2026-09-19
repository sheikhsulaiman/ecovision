"""A0 conference posters, built from the same numbers as the thesis.

    python src/build_poster.py --layout overview
    python src/build_poster.py --layout focus
    python src/build_poster.py --layout overview --size a1

Output: outputs/thesis/EcoVision_poster_{layout}_{size}.pptx

TWO LAYOUTS, FOR TWO DIFFERENT ROOMS
------------------------------------
**overview** walks the whole project in the order it was run, numbered 1
to 9: problem, questions, study area, data, method, harmonisation,
experiments, results, contributions. Use it where the audience expects to
see the shape of the work -- a departmental poster session, an examiner
walking the hall with a mark sheet.

**focus** claims one thing and spends the whole sheet on it: most of what
looks like deforestation in Bandarban is not deforestation. Use it where
the audience is walking past and will give the poster ten seconds.

Neither is the better poster in the abstract. The overview risks being the
pre-defence deck printed at A0, which is dense and nobody reads end to
end; the focus risks under-selling RQ2 and RQ3, which are real
contributions. Pick by room.

TYPOGRAPHY
----------
Cambria and Calibri, matching docs/EcoVision_PreDefence.pptx, so the
poster and the deck read as one set of materials. Both ship with Office
on every machine a print shop is likely to use -- a poster that
substitutes its fonts at the printer is a poster with broken line breaks.

Sizes follow normal poster practice rather than screen practice: body
text at 26 pt is about the minimum that reads at 1.5 m, and the headline
figure is set large enough to carry across the hall.

NUMBERS
-------
Rule 8. Every figure here is read from outputs/tables/ or from the
chapters, and the small charts are rebuilt as native PowerPoint tables
rather than upscaled PNGs -- a 3.95-inch sparkline blown up to a 10-inch
poster column is a blurry sparkline.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "outputs" / "figures"
OUT_DIR = REPO / "outputs" / "thesis"

# ISO paper, portrait, in inches.
SIZES = {"a0": (33.11, 46.81), "a1": (23.39, 33.11)}

SERIF = "Cambria"
SANS = "Calibri"
MONO = "Consolas"

INK = RGBColor(0x11, 0x16, 0x1C)
INK_SOFT = RGBColor(0x48, 0x55, 0x5F)
INK_FAINT = RGBColor(0x75, 0x83, 0x8D)
PAPER = RGBColor(0xF4, 0xF6, 0xF8)
SURFACE = RGBColor(0xFF, 0xFF, 0xFF)
RULE = RGBColor(0xD5, 0xDD, 0xE4)
LOSS = RGBColor(0xC3, 0x3C, 0x54)
RECOVER = RGBColor(0x2F, 0x6F, 0x4F)
CAUTION = RGBColor(0xB8, 0x86, 0x0B)
CAUTION_SOFT = RGBColor(0xFB, 0xF3, 0xDE)

MARGIN = 1.3
GUTTER = 0.85

# Scan targets, as (url, label, caption). Empty list and the block is
# omitted rather than printed pointing nowhere -- a dead QR on a poster is
# worse than none, because people try it.
#
# One code. The Earth Engine app was the target until 2026-09-19 and is
# now reached from the site instead -- two codes on a poster make the
# visitor choose before they know what either is, and the site is the
# better first stop because it carries the findings themselves.
QR_TARGETS = [
    ("https://sheikhsulaiman.github.io/ecovision/",
     "Read the findings",
     "The numbers on this poster, with the figures, the district map, and "
     "a link through to the live Earth Engine app."),
]

# 2.75 in at A0. Rough rule for QR codes: readable scan distance is about
# ten times the code's width, so this reads from arm's length, which is
# what a poster session actually needs. Below about 1.5 in people have to
# lean in awkwardly and most give up.
QR_SIZE = 2.75


def qr_png(url: str, path: Path) -> Path:
    """Render `url` as a QR at high error correction.

    ERROR_CORRECT_H tolerates about 30% of the code being damaged, which on
    a printed poster covers scuffing, a thumb tack through a corner, and the
    glare that a phone camera gets off laminate.
    """
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H

    code = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=16,
                         border=2)
    code.add_data(url)
    code.make(fit=True)
    code.make_image(fill_color="black", back_color="white").save(path)
    return path


def _qr_slug(url: str) -> str:
    """Stable filename for a target's cached PNG."""
    keep = "".join(c if c.isalnum() else "_" for c in url.split("//", 1)[-1])
    return f"_qr_{keep[:60]}.png"


def _qr_beside(slide, x, y, w, size, url, label, caption):
    """One code with its text alongside. The footer column is wide and
    short, so a single code reads better beside its label than above it."""
    png = OUT_DIR / _qr_slug(url)
    if not png.exists():
        qr_png(url, png)
    slide.shapes.add_picture(str(png), Inches(x), Inches(y),
                             width=Inches(size), height=Inches(size))
    tf = textbox(slide, x + size + 0.45, y + 0.12, w - size - 0.45, size)
    para(tf, label, size=26, font=SERIF, colour=INK, bold=True, first=True,
         space_after=6)
    para(tf, caption, size=21, colour=INK_SOFT, line=1.2, space_after=6)
    para(tf, url.replace("https://", ""), size=17, font=MONO,
         colour=INK_FAINT, line=1.2)
    return y + size


def qr_block(slide, x, y, w, *, size=QR_SIZE, targets=None):
    """The scan targets, code above label. Returns the bottom edge.

    Laid out as columns rather than rows: the footer column is wide and
    short, so two stacked code-plus-paragraph rows would run off the
    bottom of the sheet, and the caption under a code is easier to tie to
    it than a caption beside it.
    """
    targets = QR_TARGETS if targets is None else targets
    if not targets:
        return y
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if len(targets) == 1:
        return _qr_beside(slide, x, y, w, size, *targets[0])

    gutter = 0.6
    col = (w - gutter * (len(targets) - 1)) / len(targets)
    bottom = y
    for i, (url, label, caption) in enumerate(targets):
        cx = x + i * (col + gutter)
        png = OUT_DIR / _qr_slug(url)
        if not png.exists():
            qr_png(url, png)
        slide.shapes.add_picture(str(png), Inches(cx), Inches(y),
                                 width=Inches(size), height=Inches(size))

        ty = y + size + 0.22
        lh = text_height(label, col, 26, font=SERIF, bold=True, line=1.15)
        ch = text_height(caption, col, 21, line=1.2)
        uh = text_height(url.replace("https://", ""), col, 17, font=MONO,
                         line=1.2)
        tf = textbox(slide, cx, ty, col, lh + ch + uh + 0.3)
        para(tf, label, size=26, font=SERIF, colour=INK, bold=True,
             first=True, space_after=6, line=1.15)
        para(tf, caption, size=21, colour=INK_SOFT, line=1.2, space_after=6)
        para(tf, url.replace("https://", ""), size=17, font=MONO,
             colour=INK_FAINT, line=1.2)
        bottom = max(bottom, ty + lh + ch + uh + 0.3)
    return bottom


# --------------------------------------------------------------- measuring
#
# Text height has to be measured, not estimated. python-pptx writes a box
# and PowerPoint reflows the text inside it at open time; it does not clip,
# so a paragraph that needs more room than its box simply draws over
# whatever sits below. Guessing "characters per line" from an average glyph
# width is close enough for one paragraph and wrong by a line or two after
# six, which is exactly how sections end up on top of each other.
#
# So: load the real font file, wrap greedily on measured word widths, and
# advance by the line count that comes out.

FONT_FILES = {
    (SANS, False): "calibri.ttf",
    (SANS, True): "calibrib.ttf",
    (SERIF, False): "cambria.ttc",
    (SERIF, True): "cambriab.ttf",
    (MONO, False): "consola.ttf",
    (MONO, True): "consolab.ttf",
}
FONT_DIR = Path("C:/Windows/Fonts")
_font_cache: dict = {}


def _font(name, bold, size_pt):
    """PIL font at the pixel size PowerPoint renders `size_pt` to at 96 dpi."""
    from PIL import ImageFont
    px = max(1, int(round(size_pt * 96 / 72)))
    key = (name, bold, px)
    if key not in _font_cache:
        path = FONT_DIR / FONT_FILES[(name, bold)]
        try:
            _font_cache[key] = ImageFont.truetype(str(path), px)
        except Exception:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def line_count(text, width_in, size_pt, *, font=SANS, bold=False):
    """Lines this text wraps to in a box `width_in` wide. Greedy, like Word.

    Manual breaks are honoured: a headline broken by hand into two lines
    occupies two lines even where it would have fitted on one.
    """
    fnt = _font(font, bold, size_pt)
    limit = width_in * 96
    lines = 0
    for segment in text.split("\n"):
        lines += 1
        current = ""
        for word in segment.split():
            trial = word if not current else current + " " + word
            if fnt.getlength(trial) <= limit or not current:
                current = trial
            else:
                lines += 1
                current = word
    return lines


def text_height(text, width_in, size_pt, *, font=SANS, bold=False, line=1.22):
    """Height in inches that `text` actually occupies."""
    return line_count(text, width_in, size_pt, font=font, bold=bold) * \
        size_pt * line / 72.0


def textbox(slide, x, y, w, h, *, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    tf.paragraphs[0].alignment = align
    return tf


def para(tf, text, *, size, font=SANS, colour=INK, bold=False, italic=False,
         space_after=0, space_before=0, line=None, first=False, align=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    if align is not None:
        p.alignment = align
    p.space_after = Pt(space_after)
    p.space_before = Pt(space_before)
    if line:
        p.line_spacing = line
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.name = font
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = colour
    return p


def block(slide, x, y, w, h, fill, line=None, line_w=1.0):
    from pptx.enum.shapes import MSO_SHAPE
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y),
                                    Inches(w), Inches(h))
    shape.shadow.inherit = False
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(line_w)
    shape.text_frame.word_wrap = True
    return shape


def rule(slide, x, y, w, colour=RULE, weight=1.5):
    block(slide, x, y, w, weight / 72.0, colour)


def heading(slide, x, y, w, eyebrow, title, *, accent=INK):
    tf = textbox(slide, x, y, w, 1.9)
    para(tf, eyebrow.upper(), size=22, font=MONO, colour=accent, first=True,
         space_after=6)
    para(tf, title, size=44, font=SERIF, colour=INK, bold=True, line=0.95)
    return y + 0.45 + 0.5 * (title.count("\n") + 1) + 1.15


def table(slide, x, y, w, rows, *, col_w, header=True, size=24, row_h=0.62):
    """Native PowerPoint table -- stays sharp at poster scale, unlike an
    upscaled PNG of the same chart."""
    n_rows, n_cols = len(rows), len(rows[0])
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y),
                                    Inches(w), Inches(row_h * n_rows))
    tbl = shape.table
    tbl.first_row = header
    tbl.horz_banding = False
    total = sum(col_w)
    for i, frac in enumerate(col_w):
        tbl.columns[i].width = Emu(int(Inches(w) * frac / total))
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = SURFACE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT if (c > 0 and r > 0) else PP_ALIGN.LEFT
            run = p.add_run()
            emphasis = value.startswith("*")
            run.text = value[1:] if emphasis else value
            run.font.size = Pt(size)
            run.font.name = MONO if (c > 0 and r > 0) else SANS
            run.font.bold = (r == 0 and header) or emphasis
            run.font.color.rgb = (
                INK_FAINT if (r == 0 and header)
                else RECOVER if emphasis
                else INK
            )
    return y + row_h * n_rows


def image_ratio(path) -> float:
    """height / width of an image, so a panel can be sized from its contents."""
    from PIL import Image
    with Image.open(path) as im:
        return im.height / im.width


def picture(slide, path, x, y, w):
    """Place scaled to width, returning the bottom edge."""
    from PIL import Image
    with Image.open(path) as im:
        ratio = im.height / im.width
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y),
                                    width=Inches(w))
    del pic
    return y + w * ratio


def caption(slide, x, y, w, text, *, size=19):
    h = text_height(text, w, size, line=1.15)
    tf = textbox(slide, x, y, w, h)
    para(tf, text, size=size, colour=INK_FAINT, first=True, line=1.15)
    return y + h


def rescale(slide, factor: float) -> None:
    """Scale every shape and every run on the slide by `factor`.

    The layout below is written in A0 inches throughout. Scaling the canvas
    without scaling its contents leaves A0 coordinates on a smaller sheet,
    which puts the footer four inches past the bottom edge -- and PowerPoint
    does not clip, so it looks like a layout choice rather than a bug.
    Doing it as one pass afterwards keeps a single set of coordinates to
    reason about instead of a scale factor threaded through sixty numbers.
    """
    for shape in slide.shapes:
        if shape.left is not None:
            shape.left = Emu(int(shape.left * factor))
            shape.top = Emu(int(shape.top * factor))
            shape.width = Emu(int(shape.width * factor))
            shape.height = Emu(int(shape.height * factor))
        if shape.has_text_frame:
            for p in shape.text_frame.paragraphs:
                for r in p.runs:
                    if r.font.size is not None:
                        r.font.size = Pt(r.font.size.pt * factor)
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                row.height = Emu(int(row.height * factor))
            for col in shape.table.columns:
                col.width = Emu(int(col.width * factor))
            for cell in [c for row in shape.table.rows for c in row.cells]:
                for p in cell.text_frame.paragraphs:
                    for r in p.runs:
                        if r.font.size is not None:
                            r.font.size = Pt(r.font.size.pt * factor)


def build_focus(size_key: str) -> Path:
    """One-claim poster. See module docstring."""
    # Always laid out at A0, then scaled as one pass if a smaller sheet was
    # asked for. See rescale().
    W, H = SIZES["a0"]
    factor = SIZES[size_key][0] / SIZES["a0"][0]

    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    bg = block(slide, 0, 0, W, H, PAPER)
    bg.shadow.inherit = False

    col_w = (W - 2 * MARGIN - 2 * GUTTER) / 3
    col_x = [MARGIN + i * (col_w + GUTTER) for i in range(3)]

    # ---------------------------------------------------------------- header
    block(slide, 0, 0, W, 0.38, LOSS)

    y = 1.15
    claim = ("Most of what looks like deforestation\n"
             "in the Chittagong Hills is not deforestation.")
    claim_h = text_height(claim, W - 2 * MARGIN, 92, font=SERIF, bold=True,
                          line=0.92)
    tf = textbox(slide, MARGIN, y, W - 2 * MARGIN, claim_h)
    para(tf, claim, size=92, font=SERIF, colour=INK, bold=True, line=0.92,
         first=True)
    y += claim_h + 0.55

    tf = textbox(slide, MARGIN, y, W - 2 * MARGIN - 9.0, 2.2)
    para(tf, "Forest cover change in three districts of Bangladesh, 1988–2024, "
             "measured from Landsat — and what it takes to measure it correctly.",
         size=34, font=SERIF, colour=INK_SOFT, line=1.15, first=True)

    tf = textbox(slide, W - MARGIN - 8.6, y, 8.6, 2.4, align=PP_ALIGN.RIGHT)
    para(tf, "Sheikh Sulaiman Sony  ·  Jalal Uddin Mohammad Akbar",
         size=23, font=MONO, colour=INK, first=True, space_after=5,
         align=PP_ALIGN.RIGHT)
    para(tf, "Supervisor: Rubel Sheikh", size=21, font=MONO, colour=INK_SOFT,
         space_after=5, align=PP_ALIGN.RIGHT)
    para(tf, "Dept. of Educational Technology & Engineering", size=21,
         font=MONO, colour=INK_FAINT, space_after=5, align=PP_ALIGN.RIGHT)
    para(tf, "University of Frontier Technology, Bangladesh", size=21,
         font=MONO, colour=INK_FAINT, align=PP_ALIGN.RIGHT)

    y += 2.55
    rule(slide, MARGIN, y, W - 2 * MARGIN, INK, 3)
    y += 0.75

    # ------------------------------------------------------------ claim band
    band_h = 6.1
    block(slide, MARGIN, y, W - 2 * MARGIN, band_h, SURFACE, RULE, 1.5)
    block(slide, MARGIN, y, W - 2 * MARGIN, 0.13, LOSS)

    inner = y + 0.75
    tf = textbox(slide, MARGIN + 0.9, inner, 9.2, 4.6)
    para(tf, "16.4%", size=150, font=SERIF, colour=LOSS, bold=True, line=0.85,
         first=True)
    para(tf, "of disturbed land is\npermanent conversion",
         size=27, colour=INK_SOFT, line=1.15, space_before=8)

    tf = textbox(slide, MARGIN + 11.0, inner, W - 2 * MARGIN - 12.8, 4.6)
    # "The rest is jhum" would be wrong: 63.8% is cyclical and 19.8% is
    # undetermined. Splitting them here keeps the headline honest, and the
    # undetermined class is explained in full in the column below.
    para(tf, "Of 88,122 ha disturbed in Bandarban since 1988, only a sixth is "
             "permanent. Most of the rest — 63.8% — is shifting cultivation, "
             "jhum: cleared, cropped and left to regrow on a five-to-seven year "
             "cycle. A further 19.8% is too recent to judge either way.",
         size=30, colour=INK, line=1.25, first=True, space_after=13)
    para(tf, "A two-date comparison cannot tell those apart. It catches the cycle "
             "mid-swing and reports loss, gain, or nothing at all depending only "
             "on when the two dates fall. Read that way, this district shows "
             "roughly four times the deforestation that actually occurred.",
         size=30, colour=INK, line=1.25, space_after=13)
    para(tf, "Only the annual trajectory shows whether the canopy came back.",
         size=30, colour=LOSS, bold=True, line=1.25)

    y += band_h + 0.95

    # ------------------------------------------------- column 1 : the problem
    c1 = col_x[0]
    y1 = heading(slide, c1, y, col_w, "Why this is hard",
                 "Three districts, three\nways forest is lost", accent=LOSS)

    mechanisms = [
        ("Gazipur", "1,819 km²", "SPECTRAL", CAUTION,
         "Abrupt, permanent conversion as Dhaka expands north. Cleared land "
         "looks different from forest, and stays different. The easy case."),
        ("Sylhet", "3,416 km²", "SPATIAL", RECOVER,
         "Tea estates are as green and as dense as natural forest. What "
         "separates them is pattern — planted rows, uniform canopy, "
         "geometric edges — not colour."),
        ("Bandarban", "4,592 km²", "TEMPORAL", LOSS,
         "Jhum: clear, crop, abandon, regrow, repeat. The signal is in the "
         "sequence, and no single pair of dates contains it."),
    ]
    for name, area, signal, colour, text in mechanisms:
        h = 3.35
        block(slide, c1, y1, col_w, h, SURFACE, RULE, 1.2)
        block(slide, c1, y1, 0.14, h, colour)
        tfm = textbox(slide, c1 + 0.55, y1 + 0.35, col_w - 1.0, h - 0.6)
        para(tfm, f"{name}   {area}", size=30, font=SERIF, colour=INK,
             bold=True, first=True, space_after=3)
        para(tfm, signal, size=21, font=MONO, colour=colour, bold=True,
             space_after=9)
        para(tfm, text, size=24, colour=INK_SOFT, line=1.2)
        y1 += h + 0.42

    y1 += 0.35
    y1 = picture(slide, FIG / "study_area.png", c1, y1, col_w) + 0.28
    y1 = caption(slide, c1, y1, col_w,
                 "The three districts at a common scale. 9,827 km² in total, "
                 "about 10.9 million Landsat pixels at 30 m.") + 0.5

    tf = textbox(slide, c1, y1, col_w, 3.2)
    para(tf, "Most method comparisons hold the landscape constant and vary the "
             "model. This one varies both, which is what makes the interaction "
             "between a class's structure and a model's capability visible at all.",
         size=25, colour=INK, line=1.25, first=True)

    # ------------------------------------------------- column 2 : the finding
    c2 = col_x[1]
    y2 = heading(slide, c2, y, col_w, "The finding · RQ4",
                 "Separating jhum from\ndeforestation", accent=LOSS)

    y2 = picture(slide, FIG / "bandarban_jhum_map.png", c2, y2, col_w) + 0.3
    y2 = caption(slide, c2, y2, col_w,
                 "Bandarban, classified from the annual NBR trajectory, 1988–2024. "
                 "Green is cyclical jhum; red is permanent conversion. Shown at "
                 "100 m by majority class — areas are tabulated at the native 30 m.") + 0.55

    y2 = table(slide, c2, y2, col_w, [
        ["Class", "Area", "Share"],
        ["Stable", "371,380 ha", "80.8%"],
        ["Permanent conversion", "*14,457 ha", "*3.15%"],
        ["Cyclical jhum", "56,235 ha", "12.24%"],
        ["Undetermined", "17,431 ha", "3.79%"],
    ], col_w=[2.1, 1.25, 0.85], size=25, row_h=0.72) + 0.42

    # Kept to two lines. The chart below now carries the rest of this
    # argument, and says it better than the paragraph did: the grey block
    # is visibly the tail of the series, not a scatter of hard cases.
    y2 = body(slide, c2, y2, col_w,
              "Undetermined is disturbance too close to the end of the series "
              "to judge recovery — a plot cleared in 2022 has not had time to "
              "regrow, and calling it permanent would inflate the headline.",
              size=25, colour=INK_SOFT) + 0.2

    y2 = picture(slide, FIG / "bandarban_disturbance_by_year.png",
                 c2, y2, col_w) + 0.2
    caption(slide, c2, y2, col_w,
            "Disturbance per year. The final column is the tallest and the "
            "least informative — it is almost entirely undetermined.")

    # ------------------------------------------ column 3 : does the model matter
    c3 = col_x[2]
    y3 = heading(slide, c3, y, col_w, "Method comparison · RQ2, RQ3",
                 "The right model depends\non the signal", accent=LOSS)

    y3 = body(slide, c3, y3, col_w,
              "Random Forest, a U-Net and a stacked ensemble, scored on "
              "spatially disjoint test blocks. No model wins everywhere, and "
              "the ordering tracks training-set size exactly.", size=25) + 0.15

    y3 = table(slide, c3, y3, col_w, [
        ["District", "RF", "U-Net", "Ens.", "Patches"],
        ["Gazipur", "0.413", "0.316", "*0.444", "55"],
        ["Sylhet", "0.503", "*0.590", "0.519", "167"],
        ["Bandarban", "0.463", "0.461", "*0.475", "260"],
    ], col_w=[1.5, 0.85, 0.9, 0.85, 1.0], size=24, row_h=0.68) + 0.3
    y3 = caption(slide, c3, y3, col_w,
                 "Patch-test macro F1, against Hansen-derived training labels.") + 0.65

    y3 = body(slide, c3, y3, col_w,
              "Tea is a spatial pattern, not a spectral one. Switching only "
              "the GLCM texture bands in and out — architecture and data "
              "held constant — moves plantation F1 by 22%, and almost "
              "nothing else.", size=25) + 0.15

    y3 = table(slide, c3, y3, col_w, [
        ["Sylhet, plantation F1", "Score"],
        ["U-Net with texture", "*0.452"],
        ["U-Net without texture", "0.370"],
        ["Random Forest (per-pixel)", "0.029"],
    ], col_w=[2.6, 1.0], size=24, row_h=0.68) + 0.3
    y3 = caption(slide, c3, y3, col_w,
                 "A per-pixel model has no access to planted rows or canopy "
                 "uniformity — the properties that define a tea estate.") + 0.65

    y3 = body(slide, c3, y3, col_w,
              "Areas use the Olofsson stratified estimator with 95% confidence "
              "intervals, never raw pixel counts.", size=25) + 0.15

    y3 = table(slide, c3, y3, col_w, [
        ["Adjusted loss, 1990–2024", "Estimate", "Sig."],
        ["Gazipur", "443 ± 849 ha", "no"],
        ["Sylhet", "5,547 ± 10,755 ha", "no"],
        ["Bandarban", "*71,011 ± 41,629 ha", "*yes"],
    ], col_w=[1.5, 1.9, 0.6], size=24, row_h=0.68) + 0.3
    caption(slide, c3, y3, col_w,
            "Only Bandarban's interval excludes zero. In the other two, the "
            "reduced reference sample cannot resolve loss from no loss — "
            "reported as a result, not hidden.")

    # ---------------------------------------------------------------- footer
    fy = H - 7.6
    rule(slide, MARGIN, fy, W - 2 * MARGIN, INK, 3)
    fy += 0.55

    fcol = (W - 2 * MARGIN - 2 * GUTTER) / 3

    method = ("Landsat Collection 2 Level-2 surface reflectance via Google "
              "Earth Engine. Dry-season composites (1 Nov – 31 Mar), cloud and "
              "shadow masked, median reduced into a 23-band stack. Train, "
              "validation and test splits are whole disjoint 10 km blocks, "
              "never random pixels. LandTrendr segments the annual NBR series "
              "to separate cyclical disturbance from permanent conversion.")
    tf = textbox(slide, MARGIN, fy, fcol,
                 0.42 + text_height(method, fcol, 23, line=1.22))
    para(tf, "METHOD", size=21, font=MONO, colour=INK_FAINT, bold=True,
         first=True, space_after=9)
    para(tf, method, size=23, colour=INK_SOFT, line=1.22)

    tf = textbox(slide, MARGIN + fcol + GUTTER, fy, fcol, 5.6)
    para(tf, "MEASURED, NOT ASSUMED", size=21, font=MONO, colour=INK_FAINT,
         bold=True, first=True, space_after=9)
    para(tf, "Published cross-sensor harmonisation coefficients, fitted over the "
             "continental United States, performed worse here than applying no "
             "correction at all. They would have degraded NIR by 8.5% and SWIR2 "
             "by 69.8% — the two bands NBR is built from, and NBR is what the "
             "Bandarban result depends on. Locally fitted coefficients were "
             "adopted per band instead.",
         size=23, colour=INK_SOFT, line=1.22)

    lx = MARGIN + 2 * (fcol + GUTTER)
    block(slide, lx, fy - 0.3, fcol, 5.9, CAUTION_SOFT)
    block(slide, lx, fy - 0.3, fcol, 0.11, CAUTION)
    tf = textbox(slide, lx + 0.5, fy + 0.15, fcol - 1.0, 5.2)
    para(tf, "PROVISIONAL", size=21, font=MONO, colour=CAUTION, bold=True,
         first=True, space_after=9)
    para(tf, "Every figure here that rests on the reference sample is provisional. "
             "Two trained interpreters working from the same written protocol "
             "agreed at close to chance on where forest begins — Cohen's κ of "
             "0.157 and 0.038 against a 0.75 threshold. Until that is reconciled "
             "these numbers are indicative, not final.",
         size=23, colour=INK_SOFT, line=1.22, space_after=9)
    para(tf, "We report them anyway. An unreported κ is indistinguishable from "
             "an unmeasured one.",
         size=23, colour=INK, bold=True, line=1.22)

    # Under the METHOD column, which is the shortest of the three. Measured
    # rather than offset by eye: at fy + 4.6 the code ran off the bottom of
    # the sheet, which the checker catches but a glance would not.
    method_h = text_height(method, fcol, 23, line=1.22) + 0.42
    qr_block(slide, MARGIN, fy + method_h + 0.5, fcol)

    return finish(prs, slide, size_key, factor, "focus")


def finish(prs, slide, size_key, factor, layout) -> Path:
    if factor != 1.0:
        rescale(slide, factor)
        prs.slide_width = Inches(SIZES[size_key][0])
        prs.slide_height = Inches(SIZES[size_key][1])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"EcoVision_poster_{layout}_{size_key.upper()}.pptx"
    prs.save(out)
    return out


def section(slide, x, y, w, number, title, *, accent=LOSS):
    """Numbered section head.

    The numbering is not decoration here: this poster walks the pipeline in
    the order it was actually run, so a reader wanting to know what happened
    before the models walks backwards from 6 to 5. The focus poster, whose
    sections are not a sequence, does not number them.
    """
    block(slide, x, y, 1.05, 1.05, accent)
    tfn = textbox(slide, x, y + 0.17, 1.05, 0.9, align=PP_ALIGN.CENTER)
    para(tfn, str(number), size=34, font=SERIF, colour=SURFACE, bold=True,
         first=True, align=PP_ALIGN.CENTER)
    tf = textbox(slide, x + 1.35, y + 0.05, w - 1.35, 1.3)
    para(tf, title, size=38, font=SERIF, colour=INK, bold=True, line=0.95,
         first=True)
    rule(slide, x, y + 1.32, w, RULE, 1.5)
    return y + 1.72


def body(slide, x, y, w, text, *, size=24, colour=INK):
    """Paragraph, returning its true bottom so the next element clears it."""
    h = text_height(text, w, size, line=1.22)
    tf = textbox(slide, x, y, w, h)
    para(tf, text, size=size, colour=colour, line=1.22, first=True)
    return y + h + 0.12


def bullets(slide, x, y, w, items, *, size=24, marker=RECOVER):
    for head, rest in items:
        block(slide, x, y + 0.22, 0.17, 0.17, marker)
        tf = textbox(slide, x + 0.45, y,
                     w - 0.45,
                     text_height(head + " " + rest, w - 0.45, size,
                                 bold=True, line=1.22))
        p = tf.paragraphs[0]
        p.line_spacing = 1.22
        run = p.add_run()
        run.text = head + " "
        run.font.size = Pt(size)
        run.font.name = SANS
        run.font.bold = True
        run.font.color.rgb = INK
        run2 = p.add_run()
        run2.text = rest
        run2.font.size = Pt(size)
        run2.font.name = SANS
        run2.font.color.rgb = INK_SOFT
        # The bold lead-in and the body wrap as one paragraph, so measure
        # them together at the wider of the two metrics.
        h = text_height(head + " " + rest, w - 0.45, size, bold=True, line=1.22)
        y += h + 0.3
    return y


def build_overview(size_key: str) -> Path:
    """The whole project, section by section, in the order it was run."""
    W, H = SIZES["a0"]
    factor = SIZES[size_key][0] / SIZES["a0"][0]

    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    block(slide, 0, 0, W, H, PAPER).shadow.inherit = False

    col_w = (W - 2 * MARGIN - 2 * GUTTER) / 3
    cx = [MARGIN + i * (col_w + GUTTER) for i in range(3)]

    # ------------------------------------------------------------- header
    block(slide, 0, 0, W, 0.38, LOSS)
    title = "Deep Learning for Deforestation Detection in Bangladesh"
    sub = ("A three-district comparison of classification and change "
           "detection methods using Landsat imagery, 1988–2024")
    tw = W - 2 * MARGIN - 9.2
    th = text_height(title, tw, 72, font=SERIF, bold=True, line=0.95)
    tf = textbox(slide, MARGIN, 1.1, tw, th)
    para(tf, title, size=72, font=SERIF, colour=INK, bold=True, line=0.95,
         first=True)
    sy = 1.1 + th + 0.3
    tf = textbox(slide, MARGIN, sy, tw,
                 text_height(sub, tw, 31, font=SERIF, line=1.15))
    para(tf, sub, size=31, font=SERIF, colour=INK_SOFT, line=1.15, first=True)

    tf = textbox(slide, W - MARGIN - 8.8, 1.25, 8.8, 3.4, align=PP_ALIGN.RIGHT)
    para(tf, "Sheikh Sulaiman Sony", size=25, font=MONO, colour=INK,
         first=True, space_after=4, align=PP_ALIGN.RIGHT)
    para(tf, "Jalal Uddin Mohammad Akbar", size=25, font=MONO, colour=INK,
         space_after=10, align=PP_ALIGN.RIGHT)
    para(tf, "Supervisor: Rubel Sheikh", size=22, font=MONO, colour=INK_SOFT,
         space_after=4, align=PP_ALIGN.RIGHT)
    para(tf, "Dept. of Educational Technology & Engineering", size=22,
         font=MONO, colour=INK_FAINT, space_after=4, align=PP_ALIGN.RIGHT)
    para(tf, "University of Frontier Technology, Bangladesh", size=22,
         font=MONO, colour=INK_FAINT, align=PP_ALIGN.RIGHT)

    y0 = 5.95
    rule(slide, MARGIN, y0, W - 2 * MARGIN, INK, 3)
    y0 += 0.7

    # ============================================= column 1 : setup and data
    y = section(slide, cx[0], y0, col_w, 1, "The problem")
    y = body(slide, cx[0], y, col_w,
             "Satellite forest monitoring was developed and validated where "
             "loss is abrupt, permanent and spectrally unambiguous. Where "
             "that does not hold the failure is silent: a map and a number "
             "are still produced, and nothing in the output says they are "
             "wrong.")
    y = body(slide, cx[0], y + 0.15, col_w,
             "Bangladesh breaks all three assumptions, in three different "
             "places. This study measures how much the choice of method "
             "matters as they fail one by one.") + 0.5

    y = section(slide, cx[0], y, col_w, 2, "Research questions")
    y = bullets(slide, cx[0], y, col_w, [
        ("RQ1", "To what extent, and in what spatial patterns, has forest "
                "cover changed across the three districts?"),
        ("RQ2", "How does Random Forest compare with U-Net across landscapes "
                "of differing spectral and spatial complexity?"),
        ("RQ3", "To what extent does GLCM texture improve discrimination of "
                "natural forest from tea plantation?"),
        ("RQ4", "Can annual temporal segmentation separate cyclical jhum from "
                "permanent conversion, where bitemporal comparison cannot?"),
    ], marker=LOSS) + 0.3

    y = section(slide, cx[0], y, col_w, 3, "Study area")
    y = picture(slide, FIG / "study_area.png", cx[0], y,
            col_w * 0.70) + 0.25
    y = caption(slide, cx[0], y, col_w,
                "Three districts, 9,827 km² in total — about 10.9 million "
                "Landsat pixels at 30 m.") + 0.35
    y = table(slide, cx[0], y, col_w, [
        ["District", "Area", "Loss mechanism"],
        ["Gazipur", "1,819 km²", "Abrupt conversion"],
        ["Sylhet", "3,416 km²", "Plantation confusion"],
        ["Bandarban", "4,592 km²", "Cyclical jhum"],
    ], col_w=[1.25, 1.0, 2.0], size=23, row_h=0.66) + 0.55

    y = section(slide, cx[0], y, col_w, 4, "Data")
    y = body(slide, cx[0], y, col_w,
             "Landsat Collection 2 Level-2 surface reflectance via Google "
             "Earth Engine — L4/L5 TM, L7 ETM+, L8/L9 OLI. 120 district-years "
             "audited, zero failures. Epoch anchors T0 1990, T1 2000, T2 2010, "
             "T3 2024; the annual series for segmentation runs from 1988.")
    y = picture(slide, FIG / "scene_availability.png", cx[0], y + 0.2,
                col_w * 0.86) + 0.25
    y = caption(slide, cx[0], y, col_w,
                "Usable scenes per district-year. The study starts at 1988 "
                "because 1985–87 returned none at all — an acquisition gap, "
                "not cloud. 2012 and 2013 are entirely Landsat 7 SLC-off.") + 0.5

    # The reference sample is data, and it is the only non-derived data in
    # the project. Leaving it to the footer would imply the accuracy
    # assessment rests on something the poster never introduces.
    y = body(slide, cx[0], y, col_w,
             "Accuracy is measured against a stratified reference sample, "
             "interpreted independently by both authors. The Hansen-derived "
             "labels are training data and never score a result.")
    table(slide, cx[0], y + 0.2, col_w, [
        ["Reference sample", "Points"],
        ["Gazipur", "100"],
        ["Sylhet", "180"],
        ["Bandarban", "120"],
        ["Sylhet plantation stratum", "40"],
    ], col_w=[2.6, 1.0], size=23, row_h=0.56)

    # ====================================== column 2 : method and experiments
    y = section(slide, cx[1], y0, col_w, 5, "Method")
    y = picture(slide, FIG / "pipeline_overview.png", cx[1], y,
                col_w * 0.50) + 0.3
    y = caption(slide, cx[1], y, col_w,
                "Each stage feeds the next. The accuracy assessment at the end "
                "is the only thing measured against independent data.") + 0.45
    y = body(slide, cx[1], y, col_w,
             "Dry-season composites (1 Nov – 31 Mar), cloud and shadow masked "
             "on QA_PIXEL, median reduced into a 23-band stack: spectral bands, "
             "vegetation and moisture indices, NBR, tasselled cap, GLCM texture "
             "and terrain.") + 0.45

    y = section(slide, cx[1], y, col_w, 6, "Measured, not assumed")
    y = body(slide, cx[1], y, col_w,
             "Published cross-sensor harmonisation coefficients, fitted over "
             "the continental United States, performed worse here than "
             "applying no correction at all.")
    y = table(slide, cx[1], y + 0.2, col_w, [
        ["Transform", "Held-out residual"],
        ["No correction", "0.01582"],
        ["Roy et al. (2016)", "0.01680"],
        ["Locally fitted (OLS)", "*0.01433"],
    ], col_w=[2.1, 1.5], size=23, row_h=0.66) + 0.3
    y = body(slide, cx[1], y, col_w,
             "Roy's values would have degraded NIR by 8.5% and SWIR2 by 69.8% "
             "— the two bands NBR is built from, and NBR is what the Bandarban "
             "result depends on. Local coefficients were adopted per band; NIR "
             "and SWIR2 are left untransformed.", colour=INK_SOFT) + 0.2
    y = picture(slide, FIG / "harmonisation.png", cx[1], y,
            col_w * 0.58) + 0.25
    y = caption(slide, cx[1], y, col_w,
                "Residual RMSE per band for each candidate transform, adopted "
                "choice marked. The published coefficients are beaten by the "
                "raw data on four of six bands.") + 0.5

    y = section(slide, cx[1], y, col_w, 7, "Experiments")
    y = body(slide, cx[1], y, col_w,
             "Train, validation and test splits are whole disjoint 10 km "
             "blocks, never random pixels — random splitting on spatially "
             "autocorrelated data inflates accuracy silently. 706 patches at "
             "128 px, balanced on forest-loss share.") + 0.2
    y = table(slide, cx[1], y, col_w, [
        ["ID", "Model", "Question"],
        ["E1", "Random Forest", "Baseline"],
        ["E2", "E1 + terrain", "Does terrain help?"],
        ["E3", "U-Net, 23 bands", "Deep learning baseline"],
        ["E4", "U-Net, no texture", "RQ3 ablation"],
        ["E7", "Stacked RF + U-Net", "Does combining help?"],
    ], col_w=[0.6, 2.0, 2.3], size=23, row_h=0.64) + 0.3
    caption(slide, cx[1], y, col_w,
            "Scored against Hansen-derived training labels — model against "
            "teacher, so these are pipeline comparisons, not accuracy.")

    # ========================================= column 3 : results and closing
    y = section(slide, cx[2], y0, col_w, 8, "Results")

    y = body(slide, cx[2], y, col_w,
             "RQ2 — no model wins everywhere, and the ordering tracks "
             "training-set size exactly.") + 0.05
    y = table(slide, cx[2], y, col_w, [
        ["District", "RF", "U-Net", "Ens.", "Patches"],
        ["Gazipur", "0.413", "0.316", "*0.444", "55"],
        ["Sylhet", "0.503", "*0.590", "0.519", "167"],
        ["Bandarban", "0.463", "0.461", "*0.475", "260"],
    ], col_w=[1.5, 0.85, 0.9, 0.85, 1.0], size=23, row_h=0.64) + 0.45

    y = body(slide, cx[2], y, col_w,
             "RQ3 — texture moves plantation F1 by 22%, and almost nothing "
             "else. Tea is a spatial pattern, not a spectral one.") + 0.05
    y = table(slide, cx[2], y, col_w, [
        ["Sylhet, plantation F1", "Score"],
        ["U-Net with texture", "*0.452"],
        ["U-Net without texture", "0.370"],
        ["Random Forest (per-pixel)", "0.029"],
    ], col_w=[2.6, 1.0], size=23, row_h=0.64) + 0.45

    y = body(slide, cx[2], y, col_w,
             "RQ1 — areas use the Olofsson stratified estimator with 95% "
             "confidence intervals, never raw pixel counts.") + 0.05
    y = table(slide, cx[2], y, col_w, [
        ["Adjusted loss, 1990–2024", "Estimate", "Sig."],
        ["Gazipur", "443 ± 849 ha", "no"],
        ["Sylhet", "5,547 ± 10,755 ha", "no"],
        ["Bandarban", "*71,011 ± 41,629 ha", "*yes"],
    ], col_w=[1.5, 1.9, 0.6], size=23, row_h=0.64) + 0.5

    # RQ4 carries the visual weight: it is the finding the third district
    # exists to produce, and on a poster this dense it would otherwise read
    # as one result among four.
    #
    # The panel height is derived from its contents rather than set by hand.
    # A hand-set 9.4 in held a map that is 9.1 in tall on its own, so the
    # caption beneath it drew straight over the next section -- and nothing
    # in python-pptx complains, because PowerPoint reflows on open.
    pad = 0.5
    inner_w = col_w - 2 * pad
    map_w = inner_w * 0.82
    map_h = map_w * image_ratio(FIG / "bandarban_jhum_map.png")
    lead = ("Only 16.4% of the 88,122 ha disturbed in Bandarban is permanent "
            "conversion. 63.8% is cyclical jhum that regrows; 19.8% is too "
            "recent to judge.")
    tail = ("Green is cyclical jhum, red is permanent conversion. A bitemporal "
            "comparison would have reported roughly four times the "
            "deforestation that occurred — only the annual trajectory shows "
            "whether the canopy came back.")
    ts_w = inner_w
    ts_h = ts_w * image_ratio(FIG / "bandarban_disturbance_by_year.png")
    ts_cap = ("When it happened. Green is cyclical jhum, red permanent "
              "conversion; grey is disturbance too close to the series end "
              "to judge, which is why the final year is the tallest column "
              "and the least informative.")
    lead_h = text_height(lead, inner_w, 25, line=1.22)
    tail_h = text_height(tail, inner_w, 23, line=1.22)
    ts_cap_h = text_height(ts_cap, inner_w, 21, line=1.22)
    bh = (pad + 0.45 + lead_h + 0.35 + map_h + 0.25 + tail_h
          + 0.45 + ts_h + 0.2 + ts_cap_h + pad)

    block(slide, cx[2], y, col_w, bh, SURFACE, RULE, 1.5)
    block(slide, cx[2], y, col_w, 0.13, LOSS)
    iy = y + pad
    tfr = textbox(slide, cx[2] + pad, iy, inner_w, 0.45 + lead_h)
    para(tfr, "RQ4 — THE FINDING", size=21, font=MONO, colour=LOSS,
         bold=True, first=True, space_after=8)
    para(tfr, lead, size=25, colour=INK, line=1.22)
    iy += 0.45 + lead_h + 0.35
    iy = picture(slide, FIG / "bandarban_jhum_map.png",
                 cx[2] + pad + (inner_w - map_w) / 2, iy, map_w) + 0.25
    tfr2 = textbox(slide, cx[2] + pad, iy, inner_w, tail_h)
    para(tfr2, tail, size=23, colour=INK_SOFT, line=1.22, first=True)

    iy += tail_h + 0.45
    iy = picture(slide, FIG / "bandarban_disturbance_by_year.png",
                 cx[2] + pad, iy, ts_w) + 0.2
    tfr3 = textbox(slide, cx[2] + pad, iy, inner_w, ts_cap_h)
    para(tfr3, ts_cap, size=21, colour=INK_FAINT, line=1.22, first=True)
    y += bh + 0.55

    # ------------------------------------------------------------- footer
    #
    # Contributions live here rather than at the foot of column 3. With the
    # RQ4 panel sized to its real contents, column 3 has no room left, and
    # the contributions read perfectly well beside the caveats they are
    # qualified by.
    # 7.4 rather than 7.7: the columns clear the rule by only a couple of
    # millimetres at A0, and PowerPoint's reflow need not agree with the
    # measurement here to the last point. The footer needs about 6.5 in,
    # so the extra third of an inch comes out of slack, not content.
    fy = H - 7.4
    rule(slide, MARGIN, fy, W - 2 * MARGIN, INK, 3)
    fy += 0.5
    fcol = (W - 2 * MARGIN - 2 * GUTTER) / 3

    tf = textbox(slide, MARGIN, fy, fcol, 6.4)
    para(tf, "CONTRIBUTIONS", size=21, font=MONO, colour=INK_FAINT, bold=True,
         first=True, space_after=8)
    for head, rest in [
        ("Three mechanisms, not one landscape.",
         " Varying model and landscape together is what makes the "
         "class-structure / model-capability interaction visible."),
        ("A controlled texture ablation.",
         " Same architecture, texture in and out, everything else held."),
        ("Permanent separated from cyclical, before any total is reported.",
         " Using the annual trajectory rather than a date pair."),
        ("Honest uncertainty.",
         " Confidence intervals rather than pixel counts, a failing kappa "
         "reported as measured, negative results alongside positive ones."),
    ]:
        pa = tf.add_paragraph()
        pa.line_spacing = 1.2
        pa.space_after = Pt(7)
        r1 = pa.add_run(); r1.text = head
        r1.font.size = Pt(22); r1.font.name = SANS; r1.font.bold = True
        r1.font.color.rgb = INK
        r2 = pa.add_run(); r2.text = rest
        r2.font.size = Pt(22); r2.font.name = SANS
        r2.font.color.rgb = INK_SOFT

    px = MARGIN + fcol + GUTTER
    block(slide, px, fy - 0.28, fcol, 6.4, CAUTION_SOFT)
    block(slide, px, fy - 0.28, fcol, 0.11, CAUTION)
    tf = textbox(slide, px + 0.5, fy + 0.15, fcol - 1.0, 5.6)
    para(tf, "PROVISIONAL — READ BEFORE CITING ANY NUMBER", size=21,
         font=MONO, colour=CAUTION, bold=True, first=True, space_after=8)
    para(tf, "Every figure resting on the reference sample is provisional. Two "
             "trained interpreters working from the same written protocol "
             "agreed at close to chance on where forest begins: Cohen's κ of "
             "0.157 in Gazipur and 0.038 in Sylhet, against a 0.75 threshold. "
             "On a 40-point stratum drawn inside the tea-growing upazilas it "
             "was 0.067, so that stratum is reported as unusable for "
             "validation rather than used.",
         size=22, colour=INK_SOFT, line=1.2, space_after=7)
    para(tf, "We report them anyway. An unreported κ is indistinguishable "
             "from an unmeasured one.",
         size=22, colour=INK, bold=True, line=1.2)

    lx = MARGIN + 2 * (fcol + GUTTER)
    lim = ("Reference sample reduced to 400 points from a planned 1,650, so "
           "loss intervals are wide and two of three districts cannot resolve "
           "loss from zero. Tea plantation mapping is unsolved on five "
           "converging lines of evidence. Deep-learning runs are single-seed, "
           "and applying a 2024-trained classifier to 1990 imagery is an "
           "untested assumption.")
    credit = ("Landsat Collection 2 via Google Earth Engine, courtesy of the "
              "U.S. Geological Survey. Areas after Olofsson et al. (2014); "
              "segmentation after Kennedy et al. (2010).")
    lim_h = (0.42 + text_height(lim, fcol, 22, line=1.2) + 0.13
             + text_height(credit, fcol, 20, line=1.2))
    tf = textbox(slide, lx, fy, fcol, lim_h)
    para(tf, "LIMITATIONS", size=21, font=MONO, colour=INK_FAINT, bold=True,
         first=True, space_after=8)
    para(tf, lim, size=22, colour=INK_SOFT, line=1.2, space_after=9)
    para(tf, credit, size=20, colour=INK_FAINT, line=1.2)

    # The QR goes bottom-right, where a reader's eye ends up and where they
    # can stand close enough to scan without blocking the poster.
    qr_block(slide, lx, fy + lim_h + 0.45, fcol)

    return finish(prs, slide, size_key, factor, "overview")


LAYOUTS = {"focus": build_focus, "overview": build_overview}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=sorted(SIZES), default="a0")
    parser.add_argument("--layout", choices=sorted(LAYOUTS), default="focus",
                        help="focus: one claim, read across a hall. "
                             "overview: the whole project, section by section.")
    args = parser.parse_args()
    out = LAYOUTS[args.layout](args.size)
    W, H = SIZES[args.size]
    print(f"wrote {out.relative_to(REPO)}")
    print(f"  {args.layout}, {args.size.upper()} portrait, {W:.2f} x {H:.2f} in "
          f"({W * 25.4:.0f} x {H * 25.4:.0f} mm)")
    print("  Print at 100%. Do not let the shop 'fit to page' -- that rescales "
          "the type and the 26 pt body text stops being 26 pt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
