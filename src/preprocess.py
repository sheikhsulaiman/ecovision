"""Landsat Collection 2 Level-2 preprocessing primitives.

Scaling, cloud masking, cross-sensor harmonisation, index computation,
texture, and terrain — everything needed to turn raw C2 L2 scenes into
the ~22-band feature stack the models consume.

Nothing in this module hardcodes a year. Composite years come from
START_YEAR and EPOCHS, both named constants, so a change to the Gate 2
decision is a one-line edit rather than a grep.

    python src/preprocess.py --verify           # rule 6 check, one tile
    python src/preprocess.py --verify --year 2024 --district sylhet

WHICH FILE IS AUTHORITATIVE: this one. gee/03_composites.js mirrors it
for Code Editor use; if they disagree, this produced the results.

--- COEFFICIENTS REQUIRING VERIFICATION ------------------------------
Two coefficient tables below were reproduced from memory and must be
checked against the published papers before any composite built with
them is used for results. Both are flagged again at their definitions.
A wrong harmonisation coefficient does not raise an error — it silently
biases every pre-2013 composite, which is exactly the class of mistake
that survives to the viva.
  * ROY_ETM_TO_OLI   — Roy et al. (2016) RSE 185:57-70, Table 2
  * TASSELLED_CAP    — Crist (1985) RSE 17:301-306
"""

from __future__ import annotations

import argparse
import sys

import ee

PROJECT = "ecovision-503602"
ASSET_ROOT = f"projects/{PROJECT}/assets/"
DISTRICTS = ["gazipur", "sylhet", "bandarban"]

# --- Gate 2 decisions, docs/phase2_audit.md ---------------------------

START_YEAR = 1988   # annual series start (LandTrendr)
END_YEAR = 2024

# Bitemporal anchors. T0 is 1990 rather than START_YEAR because 1988's
# observation depth is about half 1990's, and T0 is one half of every
# bitemporal comparison.
EPOCHS = {"T0": 1990, "T1": 2000, "T2": 2010, "T3": 2024}

# Dry season, 1 November (year-1) to 31 March (year).
SEASON_START_MONTH = 11
SEASON_END_MONTH = 4  # exclusive

MAX_CLOUD = 40

# 2012 and 2013 dry seasons are 100% Landsat 7 SLC-off in all three
# districts (docs/phase2_audit.md section 5). Not usable as anchors;
# residual gap fraction must be reported if either is composited.
SLC_ONLY_YEARS = (2012, 2013)

NATIVE_CRS = "EPSG:32646"  # UTM 46N
NATIVE_SCALE = 30

# --- band naming ------------------------------------------------------
# Unify before merging collections. TM/ETM+ and OLI/TIRS number their
# bands differently for the same wavelengths; merging without renaming
# silently compares blue against green.

COMMON_BANDS = ["blue", "green", "red", "nir", "swir1", "swir2"]

SENSORS = {
    "LT04": {"id": "LANDSAT/LT04/C02/T1_L2", "family": "TM",
             "optical": ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"],
             "thermal": "ST_B6"},
    "LT05": {"id": "LANDSAT/LT05/C02/T1_L2", "family": "TM",
             "optical": ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"],
             "thermal": "ST_B6"},
    "LE07": {"id": "LANDSAT/LE07/C02/T1_L2", "family": "ETM",
             "optical": ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7"],
             "thermal": "ST_B6"},
    "LC08": {"id": "LANDSAT/LC08/C02/T1_L2", "family": "OLI",
             "optical": ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"],
             "thermal": "ST_B10"},
    "LC09": {"id": "LANDSAT/LC09/C02/T1_L2", "family": "OLI",
             "optical": ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"],
             "thermal": "ST_B10"},
}

# --- scale factors ----------------------------------------------------
# CLAUDE.md rule 6. C2 L2 stores surface reflectance as scaled integers.
# Applying the wrong factor is the most common silent error in student
# GEE work, so verify_reflectance() below checks the result every time a
# new collection is touched.

OPTICAL_SCALE, OPTICAL_OFFSET = 0.0000275, -0.2
THERMAL_SCALE, THERMAL_OFFSET = 0.00341802, 149.0

# --- harmonisation ----------------------------------------------------
# VERIFY BEFORE USE. Roy et al. (2016) Table 2, OLS coefficients mapping
# ETM+ surface reflectance onto the OLI reference:  OLI = slope*ETM + int.
#
# Direction matters: everything is brought INTO the OLI reference,
# because T3 (2024) is OLI/L9 and the endpoint should not be the thing
# that gets adjusted.
#
# TM (Landsat 4/5) is harmonised with the same coefficients. TM and ETM+
# spectral response functions are close but not identical; this is the
# standard simplification and must be stated as one in Chapter 4, not
# left implicit.
#
# MEASURED BEHAVIOUR ON OUR DATA — src/check_harmonisation.py, Gazipur,
# 12 near-coincident ETM+/OLI pairs (same path/row, <= 8 days apart):
#
#     band     raw      harmonised   change
#     blue     0.0167   0.0099       -40.6%   better
#     green    0.0100   0.0083       -16.5%   better
#     red      0.0095   0.0085        -9.9%   better
#     nir      0.0120   0.0130        +8.5%   worse
#     swir1    0.0084   0.0141       +68.5%   worse
#     swir2    0.0056   0.0096       +69.8%   worse
#     TOTAL    0.0622   0.0635        +2.1%   no material change
#
# The regression DIRECTION is confirmed correct: applying the inverse
# transform gives 0.0827, far worse than either. So these are ETM+ -> OLI
# coefficients, as used.
#
# The likely explanation for the infrared bands is that Roy et al. derived
# these on Collection 1, whose atmospheric correction differs from the
# Collection 2 LaSRC/LEDAPS products used here. Applying C1-derived
# coefficients to C2 data is a known imperfection, not a coding error.
#
# UNRESOLVED — do not treat harmonisation as validated. Tested on one
# district and one path/row (p137r43) only. Options are recorded in
# docs/phase3_harmonisation.md; the decision is pending.
ROY_ETM_TO_OLI = {
    "blue":  (0.8474, 0.0003),
    "green": (0.8483, 0.0088),
    "red":   (0.9047, 0.0061),
    "nir":   (0.8462, 0.0412),
    "swir1": (0.8937, 0.0254),
    "swir2": (0.9071, 0.0172),
}

# --- what is actually applied ----------------------------------------
# Per-band selection, chosen on held-out MAE from 45 near-coincident
# ETM+/OLI pairs across all three districts (34,414 paired pixels, 13
# pairs held out). Derived by src/derive_harmonisation.py; validation
# table at outputs/tables/harmonisation_validation.csv; reasoning and
# limitations in docs/phase3_harmonisation.md.
#
# A transform is adopted only if it beats leaving the band alone by more
# than ADOPT_MARGIN on held-out pairs. Without a margin the selection
# chases noise: NIR's local_rma "win" was 0.0% in a smaller fit and 1.5%
# here, which is not a real effect.
ADOPT_MARGIN = 0.05

IDENTITY = (1.0, 0.0)

HARMONISE_TO_OLI = {
    #  band       slope      intercept   source        held-out gain
    "blue":  (0.721504,  0.006165),   # local OLS      -33.9%
    "green": (0.848300,  0.008800),   # Roy et al.     -12.0%
    "red":   (0.874212,  0.005028),   # local OLS      -15.6%
    "nir":   IDENTITY,                # none            -1.5%, under margin
    "swir1": (0.975336,  0.001335),   # local RMA       -5.8%
    "swir2": IDENTITY,                # none             raw was best
}

# NIR and SWIR2 are left untransformed, and that is load-bearing rather
# than incidental: NBR is built from exactly those two bands, and NBR is
# what LandTrendr segments to separate cyclical jhum disturbance from
# permanent conversion (docs/forest_definition.md 6.4). Roy's published
# coefficients degraded both (+8.5% and +69.8% on held-out pairs), which
# would have propagated straight into the Bandarban result.
#
# TM (Landsat 4/5) is treated as ETM+ and given the same transform. This
# is not the usual hand-wave — it was measured. Fitting TM -> ETM+ on 45
# pairs (39,785 pixels) found NO transform beating identity on 5 of 6
# bands, and the fitted RMA slopes came out at 0.97-1.01 with intercepts
# under 0.005, i.e. indistinguishable from identity. TM and ETM+ have
# near-identical spectral response functions, so there is little bias to
# correct, and applying one would inject error rather than remove it.
# The TM chain therefore carries ONE regression's error, not two.

# VERIFY BEFORE USE. Crist (1985) tasselled cap coefficients for
# reflectance-space TM data, in COMMON_BANDS order. Applied after
# harmonisation, so one set is used for all sensors — state this.
TASSELLED_CAP = {
    "brightness": [0.2043, 0.4158, 0.5524, 0.5741, 0.3124, 0.2303],
    "greenness": [-0.1603, -0.2819, -0.4934, 0.7940, -0.0002, -0.1446],
    "wetness": [0.0315, 0.2021, 0.3102, 0.1594, -0.6806, -0.6109],
}

# GLCM window: size=2 gives a 5x5 neighbourhood. This is the band group
# that separates tea plantation and jhum fallow from natural forest —
# planted canopy is geometrically regular, natural hill forest is not.
GLCM_SIZE = 2
GLCM_MEASURES = {"nir_contrast": "contrast", "nir_ent": "entropy", "nir_idm": "homogeneity"}


# --- primitives -------------------------------------------------------


def scale_l2(img: ee.Image) -> ee.Image:
    """Apply Collection 2 Level-2 scale factors (CLAUDE.md rule 6)."""
    optical = img.select("SR_B.*").multiply(OPTICAL_SCALE).add(OPTICAL_OFFSET)
    thermal = img.select("ST_B.*").multiply(THERMAL_SCALE).add(THERMAL_OFFSET)
    return img.addBands(optical, None, True).addBands(thermal, None, True)


def mask_l2(img: ee.Image) -> ee.Image:
    """Mask cloud, shadow, cirrus, snow, and saturated pixels.

    Uses the QA_PIXEL bitmask rather than scene-level CLOUD_COVER, which
    is a whole-frame average and says nothing about this pixel.
    """
    qa = img.select("QA_PIXEL")
    clear = (
        qa.bitwiseAnd(1 << 1).eq(0)        # dilated cloud
        .And(qa.bitwiseAnd(1 << 2).eq(0))  # cirrus
        .And(qa.bitwiseAnd(1 << 3).eq(0))  # cloud
        .And(qa.bitwiseAnd(1 << 4).eq(0))  # cloud shadow
        .And(qa.bitwiseAnd(1 << 5).eq(0))  # snow
    )
    saturated = img.select("QA_RADSAT").eq(0)
    return img.updateMask(clear.And(saturated))


def rename_bands(img: ee.Image, sensor: str) -> ee.Image:
    """Rename to COMMON_BANDS + thermal, so sensors can be merged."""
    cfg = SENSORS[sensor]
    return img.select(cfg["optical"] + [cfg["thermal"]], COMMON_BANDS + ["thermal"])


def harmonise(img: ee.Image, family: str) -> ee.Image:
    """Bring TM/ETM+ into the OLI reference. OLI/TIRS passes through.

    Without this, an unharmonised 1990 TM composite compared against a
    2024 OLI composite produces a spurious change signal that a model
    reads as forest loss.

    Only the bands in HARMONISE_TO_OLI with a non-identity transform are
    touched. NIR and SWIR2 pass through unchanged — see the note there.
    """
    if family == "OLI":
        return img
    adjusted = []
    for band in COMMON_BANDS:
        slope, intercept = HARMONISE_TO_OLI[band]
        if (slope, intercept) == IDENTITY:
            continue
        adjusted.append(
            img.select(band).multiply(slope).add(intercept).rename(band)
        )
    if not adjusted:
        return img
    return img.addBands(ee.Image.cat(adjusted), None, True)


def clamp_reflectance(img: ee.Image) -> ee.Image:
    """Clamp optical bands to [0, 1]; values outside indicate bad pixels."""
    optical = img.select(COMMON_BANDS).clamp(0.0, 1.0)
    return img.addBands(optical, None, True)


def add_indices(img: ee.Image) -> ee.Image:
    """Vegetation, moisture, and built-up indices."""
    b = {name: img.select(name) for name in COMMON_BANDS}
    ndvi = img.normalizedDifference(["nir", "red"]).rename("ndvi")
    ndwi = img.normalizedDifference(["green", "nir"]).rename("ndwi")
    ndmi = img.normalizedDifference(["nir", "swir1"]).rename("ndmi")
    ndbi = img.normalizedDifference(["swir1", "nir"]).rename("ndbi")
    # NBR drives the LandTrendr segmentation that separates cyclical jhum
    # disturbance from permanent conversion (forest_definition.md 6.4).
    nbr = img.normalizedDifference(["nir", "swir2"]).rename("nbr")
    evi = img.expression(
        "2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)",
        {"nir": b["nir"], "red": b["red"], "blue": b["blue"]},
    ).rename("evi")
    savi = img.expression(
        "1.5 * (nir - red) / (nir + red + 0.5)",
        {"nir": b["nir"], "red": b["red"]},
    ).rename("savi")
    return img.addBands([ndvi, evi, savi, ndwi, ndmi, ndbi, nbr])


def add_tasselled_cap(img: ee.Image) -> ee.Image:
    """Brightness, greenness, wetness. Wetness discriminates forest well."""
    base = img.select(COMMON_BANDS)
    bands = [
        base.multiply(ee.Image.constant(coeffs)).reduce(ee.Reducer.sum()).rename(name)
        for name, coeffs in TASSELLED_CAP.items()
    ]
    return img.addBands(bands)


def add_texture(img: ee.Image) -> ee.Image:
    """GLCM texture on NIR — the tea-plantation and jhum-fallow answer.

    glcmTexture requires integer input, so NIR reflectance is quantised
    to 0-10000. Texture is computed on the composite, not per scene:
    per-scene texture would be dominated by cloud-edge artefacts.
    """
    nir_int = img.select("nir").multiply(10000).toInt32().rename("nir")
    glcm = nir_int.glcmTexture(size=GLCM_SIZE)
    selected = glcm.select(list(GLCM_MEASURES), [f"glcm_{v}" for v in GLCM_MEASURES.values()])
    return img.addBands(selected)


def add_terrain(img: ee.Image) -> ee.Image:
    """SRTM elevation, slope, aspect. Matters most in Sylhet and Bandarban."""
    srtm = ee.Image("USGS/SRTMGL1_003")
    terrain = ee.Algorithms.Terrain(srtm)
    return img.addBands(
        terrain.select(["elevation", "slope", "aspect"]).toFloat()
    )


# --- composite --------------------------------------------------------


def season_window(year: int) -> tuple[ee.Date, ee.Date]:
    return (
        ee.Date.fromYMD(year - 1, SEASON_START_MONTH, 1),
        ee.Date.fromYMD(year, SEASON_END_MONTH, 1),
    )


def sensor_collection(sensor: str, aoi: ee.Geometry, year: int) -> ee.ImageCollection:
    """One sensor, cleaned, harmonised, band-renamed, ready to merge."""
    cfg = SENSORS[sensor]
    start, end = season_window(year)
    col = (
        ee.ImageCollection(cfg["id"])
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", MAX_CLOUD))
    )

    def prepare(img: ee.Image) -> ee.Image:
        img = mask_l2(img)
        img = scale_l2(img)
        img = rename_bands(img, sensor)
        img = harmonise(img, cfg["family"])
        return clamp_reflectance(img)

    return col.map(prepare)


def build_composite(aoi: ee.Geometry, year: int, with_stack: bool = True) -> ee.Image:
    """Median dry-season composite for one year, as the full feature stack.

    Median rather than mean: more robust to residual cloud, and cheaper
    than medoid. Texture and terrain are added after compositing.
    """
    merged = None
    for sensor in SENSORS:
        col = sensor_collection(sensor, aoi, year)
        merged = col if merged is None else merged.merge(col)

    composite = ee.ImageCollection(merged).median().clip(aoi)
    if not with_stack:
        return composite

    composite = add_indices(composite)
    composite = add_tasselled_cap(composite)
    composite = add_texture(composite)
    composite = add_terrain(composite)
    return composite.set({"year": year, "slc_only": year in SLC_ONLY_YEARS})


# --- verification (CLAUDE.md rule 6) ----------------------------------


def verify_reflectance(aoi: ee.Geometry, year: int, scale: int = 300) -> dict:
    """Check scaled reflectance lands in [0, 1] before clamping.

    Rule 6 requires this every time a new collection is touched. Run on
    the UNCLAMPED composite — clamping would hide exactly the error this
    is looking for.
    """
    merged = None
    for sensor in SENSORS:
        cfg = SENSORS[sensor]
        start, end = season_window(year)
        col = (
            ee.ImageCollection(cfg["id"])
            .filterBounds(aoi)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUD_COVER", MAX_CLOUD))
            .map(lambda i, s=sensor: rename_bands(scale_l2(mask_l2(i)), s))
        )
        merged = col if merged is None else merged.merge(col)

    unclamped = ee.ImageCollection(merged).median().select(COMMON_BANDS)
    stats = unclamped.reduceRegion(
        reducer=ee.Reducer.min().combine(ee.Reducer.max(), sharedInputs=True),
        geometry=aoi,
        scale=scale,
        maxPixels=int(1e9),
        bestEffort=True,
    )
    return stats.getInfo()


def _verify(district: str, year: int) -> int:
    aoi = ee.FeatureCollection(f"{ASSET_ROOT}{district}_shp").geometry()

    print(f"=== reflectance range check: {district} {year} ===")
    print("(unclamped, post-scaling — rule 6)\n")
    stats = verify_reflectance(aoi, year)

    failed = 0
    for band in COMMON_BANDS:
        lo, hi = stats.get(f"{band}_min"), stats.get(f"{band}_max")
        if lo is None or hi is None:
            print(f"  {band:<6} no data")
            failed += 1
            continue
        ok = -0.05 <= lo and hi <= 1.05  # small tolerance: real SR can sit
        flag = "OK" if ok else "OUT OF RANGE"      # marginally outside [0,1]
        print(f"  {band:<6} [{lo:>8.4f}, {hi:>8.4f}]   {flag}")
        failed += not ok

    print()
    if failed:
        print("FAIL: reflectance outside the expected range means the scale")
        print("factors are wrong, or a sensor's bands were renamed incorrectly.")
        print("Do not build composites until this passes.")
        return 1

    print("PASS: scale factors correct for every band.\n")

    stack = build_composite(aoi, year)
    names = stack.bandNames().getInfo()
    print(f"Feature stack: {len(names)} bands")
    print("  " + ", ".join(names))
    if year in SLC_ONLY_YEARS:
        print(f"\nNOTE: {year} is a Landsat 7 SLC-off-only year. Report the")
        print("residual gap fraction for this composite (phase2_audit.md 5).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="run the rule 6 check")
    parser.add_argument("--district", default="gazipur", choices=DISTRICTS)
    parser.add_argument("--year", type=int, default=EPOCHS["T3"])
    args = parser.parse_args()

    if not args.verify:
        parser.print_help()
        return 0

    try:
        ee.Initialize(project=PROJECT)
    except Exception as exc:
        sys.exit(f"Earth Engine init failed: {exc}\nRun `earthengine authenticate` first.")

    return _verify(args.district, args.year)


if __name__ == "__main__":
    raise SystemExit(main())
