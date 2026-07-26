// EcoVision — Phase 2: scene availability audit
//
// For each district, each year, counts usable dry-season Landsat scenes
// and measures how deeply they actually cover the district. Output fixes
// START_YEAR and the epoch anchors, and decides whether Bandarban can
// support LandTrendr at all (see Gate 2 in docs/methodology_plan.md).
//
// THIS SCRIPT CAN CHANGE THE THESIS TITLE. Run it before Phase 3.
//
// Run: paste into the Code Editor, hit Run, then start the three export
// tasks from the Tasks tab. Each takes a few minutes. Results land in
// Google Drive, then are read by src/audit_summary.py.
//
// Three deliberate differences from the snippet in methodology_plan.md
// section 2.1 — each is noted at the relevant line below:
//   1. Landsat 9 is included. The plan's snippet has L5/L7/L8 only, which
//      undercounts 2022-2024 — and 2024 is the T3 endpoint epoch.
//   2. Scene counts are supplemented by per-pixel observation depth. A
//      scene clipping the district corner counts the same as one covering
//      it fully under filterBounds() alone; that is the main way a scene
//      count lies to you.
//   3. Landsat 7 SLC-off scenes are counted separately, so we can see how
//      much of a year's total depends on scenes with ~22% missing data.

// --- configuration ---------------------------------------------------

var PROJECT = 'projects/ecovision-503602/assets/';

var DISTRICTS = {
  gazipur:   PROJECT + 'gazipur_shp',
  sylhet:    PROJECT + 'sylhet_shp',
  bandarban: PROJECT + 'bandarban_shp'
};

var START_YEAR = 1985;   // first year with a full Nov-Mar window after L5 launch
var END_YEAR   = 2024;

// Dry season, 1 November (previous year) to 31 March. Bangladesh's monsoon
// (June-October) makes optical imagery largely unusable, and mixed-season
// composites introduce phenological change that a model reads as forest
// loss (methodology_plan.md 2.1).
var SEASON_START_MONTH = 11;
var SEASON_END_MONTH   = 4;   // exclusive bound: April 1 includes all of March 31

var MAX_CLOUD = 40;   // scene-level CLOUD_COVER percent

// Observation depth is measured at 300 m, 10x the native Landsat scale.
// This is an audit, not an analysis: at 30 m the reduceRegion over 40
// years x 3 districts times out. The coverage fraction is insensitive to
// this; do not reuse this scale for anything in Phase 3 onward.
var AUDIT_SCALE = 300;

var SENSORS = {
  // Landsat 4 is included for the 1980s, where every scene counts.
  l4: 'LANDSAT/LT04/C02/T1_L2',
  l5: 'LANDSAT/LT05/C02/T1_L2',
  l7: 'LANDSAT/LE07/C02/T1_L2',
  l8: 'LANDSAT/LC08/C02/T1_L2',
  // (1) Landsat 9, operational since 2022. Absent from the plan's snippet.
  l9: 'LANDSAT/LC09/C02/T1_L2'
};

// Landsat 7's scan line corrector failed on this date; every ETM+ scene
// after it has wedge-shaped gaps covering ~22% of the frame.
var SLC_FAILURE = ee.Date('2003-05-31');
// First dry-season window that can contain post-failure ETM+ scenes.
var SLC_FIRST_AFFECTED_YEAR = 2004;

// --- helpers ---------------------------------------------------------

function seasonWindow(year) {
  return {
    start: ee.Date.fromYMD(year - 1, SEASON_START_MONTH, 1),
    end:   ee.Date.fromYMD(year, SEASON_END_MONTH, 1)
  };
}

function filtered(collectionId, aoi, win) {
  return ee.ImageCollection(collectionId)
    .filterBounds(aoi)
    .filterDate(win.start, win.end)
    .filter(ee.Filter.lt('CLOUD_COVER', MAX_CLOUD));
}

// Clear-pixel mask from QA_PIXEL. Scene-level CLOUD_COVER is not enough —
// it is a whole-frame average and says nothing about whether the cloud sat
// over the district (methodology_plan.md 3.2).
function clearObservation(img) {
  var qa = img.select('QA_PIXEL');
  var clear = qa.bitwiseAnd(1 << 1).eq(0)   // dilated cloud
    .and(qa.bitwiseAnd(1 << 2).eq(0))       // cirrus
    .and(qa.bitwiseAnd(1 << 3).eq(0))       // cloud
    .and(qa.bitwiseAnd(1 << 4).eq(0));      // cloud shadow
  return clear.rename('obs').updateMask(clear);
}

// (2) The number that actually answers "can I composite this year?".
// Returns mean clear observations per pixel, and the fraction of the
// district with at least one.
function observationDepth(merged, aoi) {
  var isEmpty = merged.size().eq(0);
  var depth = ee.Image(ee.Algorithms.If(
    isEmpty,
    ee.Image.constant(0).rename('obs'),
    merged.map(clearObservation).sum().unmask(0).rename('obs')
  ));
  return depth.addBands(depth.gte(1).rename('covered'))
    .reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: aoi,
      scale: AUDIT_SCALE,
      maxPixels: 1e9,
      bestEffort: true
    });
}

function auditYear(aoi, year) {
  var win = seasonWindow(year);

  var cols = {};
  Object.keys(SENSORS).forEach(function(key) {
    cols[key] = filtered(SENSORS[key], aoi, win);
  });

  // (3) How much of this year leans on gap-affected ETM+ scenes.
  //
  // The date range is guarded because the season window ends on 1 April of
  // `year`; for year <= 2003 that is BEFORE the SLC failure, so filterDate()
  // receives an inverted range and GEE throws "Empty date ranges not
  // supported for the current operation" instead of returning zero. The
  // first window that can contain post-failure scenes is Nov 2003 - Mar 2004.
  var l7SlcOff = year >= SLC_FIRST_AFFECTED_YEAR
    ? cols.l7.filterDate(SLC_FAILURE, win.end).size()
    : ee.Number(0);

  // Merge on QA_PIXEL only — the sensors have different band names, and
  // merging full images would produce a ragged collection.
  var merged = ee.ImageCollection(
    cols.l4.select('QA_PIXEL')
      .merge(cols.l5.select('QA_PIXEL'))
      .merge(cols.l7.select('QA_PIXEL'))
      .merge(cols.l8.select('QA_PIXEL'))
      .merge(cols.l9.select('QA_PIXEL'))
  );

  var total = merged.size();
  var stats = observationDepth(merged, aoi);

  // Distinct WRS-2 path/rows. Three scenes from one path/row cover less of
  // a district than three from three — this distinguishes them.
  var pathRows = merged.aggregate_array('WRS_PATH')
    .zip(merged.aggregate_array('WRS_ROW'))
    .distinct().size();

  return ee.Feature(null, {
    year:          year,
    season_start:  win.start.format('YYYY-MM-dd'),
    season_end:    win.end.advance(-1, 'day').format('YYYY-MM-dd'),
    l4:            cols.l4.size(),
    l5:            cols.l5.size(),
    l7:            cols.l7.size(),
    l7_slc_off:    l7SlcOff,
    l8:            cols.l8.size(),
    l9:            cols.l9.size(),
    total_scenes:  total,
    path_rows:     pathRows,
    mean_cloud:    merged.aggregate_mean('CLOUD_COVER'),
    obs_per_pixel: stats.get('obs'),       // mean clear observations per pixel
    pct_covered:   ee.Number(stats.get('covered')).multiply(100)
  });
}

// --- run -------------------------------------------------------------

// Years are built client-side, NOT with ee.List.sequence. auditYear needs a
// real JavaScript number so the SLC-off date guard can branch before the
// filterDate call is ever constructed. ee.Algorithms.If would not work here:
// it evaluates both branches, so the inverted-range error would still fire.
var years = [];
for (var y = START_YEAR; y <= END_YEAR; y++) {
  years.push(y);
}

Object.keys(DISTRICTS).forEach(function(name) {
  var aoi = ee.FeatureCollection(DISTRICTS[name]).geometry();

  var audit = ee.FeatureCollection(
    years.map(function(yr) { return auditYear(aoi, yr); })
  );

  Export.table.toDrive({
    collection: audit,
    description: name + '_scene_audit',
    folder: 'ecovision_audit',
    fileNamePrefix: name + '_scene_audit',
    fileFormat: 'CSV',
    selectors: [
      'year', 'season_start', 'season_end',
      'l4', 'l5', 'l7', 'l7_slc_off', 'l8', 'l9',
      'total_scenes', 'path_rows', 'mean_cloud',
      'obs_per_pixel', 'pct_covered'
    ]
  });
});

// Print one district to the console as a smoke test before launching the
// exports — if this errors, the exports will too.
print('Gazipur, first 5 years (smoke test)',
  ee.FeatureCollection(
    years.slice(0, 5).map(function(yr) {
      return auditYear(ee.FeatureCollection(DISTRICTS.gazipur).geometry(), yr);
    })
  ));

// --- how to read the output ------------------------------------------
//
// Decision rule (methodology_plan.md 2.2) keyed on total_scenes:
//   >= 3   annual composite viable
//   1-2    use a 3-year moving window centred on the target year
//   0      year unusable — exclude and say so explicitly
//
// But prefer pct_covered where the two disagree. total_scenes counts a
// scene that clips the district corner the same as one covering it whole;
// pct_covered does not. A year with 4 scenes and pct_covered of 45 is not
// a usable year, whatever the decision rule says.
//
// For Bandarban specifically, Gate 2 also requires enough ANNUAL coverage
// to run LandTrendr, not just coverage at the epoch anchors. The
// permanent-versus-cyclical jhum split depends entirely on the annual
// trajectory (docs/forest_definition.md 6.4). If Bandarban has long runs
// of unusable years, that split is unsupportable and Bandarban cannot
// report a deforestation figure at all. Decide it here, not in Month 9.
