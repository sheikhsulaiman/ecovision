// EcoVision — public dashboard (Phase 10)
//
// Deforestation in Gazipur, Sylhet and Bandarban, 1988-2024, from Landsat
// via Google Earth Engine.
//
// HOW TO PUBLISH
//   1. Paste this whole file into the GEE Code Editor.
//   2. Run it once and check every layer draws.
//   3. Apps > Publish app. Name: ecovision. Restrict to "anyone with the
//      link" unless the supervisor asks otherwise.
//   4. Put the resulting URL in the thesis (Chapter 1) and the defence deck.
//
// WHAT THIS IS AND IS NOT
// -----------------------
// This renders composites and indices live from Landsat. It does NOT show
// the classified maps from src/models/, because those are trained against
// Hansen labels and a viewer cannot tell a model's opinion from a
// measurement by looking at it. The change layer here is NDVI differencing,
// which is reproducible from the imagery on screen and was the better of
// the two bitemporal methods tested (Chapter 6).
//
// EVERY REFERENCE-BASED NUMBER IN THE STATISTICS PANEL IS PROVISIONAL.
// Inter-interpreter agreement failed its threshold (kappa 0.157 Gazipur,
// 0.038 Sylhet, against 0.75), so the accuracy and area figures are
// reported as provisional pending reconciliation. The panel says so
// on screen. Do not remove that wording to make the app look tidier —
// it is the single most important caveat in the project.
//
// Scope deliberately excluded, per the Phase 10 effort cap: user-uploaded
// AOIs, on-the-fly reprocessing, mobile layout, and styling beyond default.

var PROJECT = 'projects/ecovision-503602/assets/';

// Named constants, mirroring src/preprocess.py. Do not inline these:
// START_YEAR is a Gate 2 decision, not a convenience.
var START_YEAR = 1988;
var END_YEAR = 2024;
var EPOCHS = {T0: 1990, T1: 2000, T2: 2010, T3: 2024};
var MAX_CLOUD = 40;
var SLC_ONLY_YEARS = [2012, 2013];

var DISTRICTS = ['gazipur', 'sylhet', 'bandarban'];

var MECHANISM = {
  gazipur: 'abrupt permanent conversion',
  sylhet: 'gradual degradation + plantation confusion',
  bandarban: 'cyclical clearing and regrowth (jhum)'
};

// Olofsson-adjusted, from outputs/tables/adjusted_{area,loss}_*.csv.
// PROVISIONAL — see the header note. Figures as of the reconciled
// 2026-08-07 run.
var STATS = {
  gazipur: {
    area_km2: '1,819',
    forest: '45,530 +/- 25,723 ha',
    nonforest: '134,252 +/- 25,723 ha',
    loss: '443 +/- 849 ha',
    loss_points: 2,
    significant: false
  },
  sylhet: {
    area_km2: '3,416',
    forest: '41,681 +/- 23,420 ha',
    nonforest: '254,993 +/- 31,210 ha',
    loss: '5,547 +/- 10,755 ha',
    loss_points: 7,
    significant: false
  },
  bandarban: {
    area_km2: '4,592',
    forest: '365,272 +/- 43,291 ha',
    nonforest: '73,620 +/- 41,822 ha',
    loss: '71,011 +/- 41,629 ha',
    loss_points: 18,
    significant: true
  }
};

// LandTrendr, annual NBR 1988-2024. outputs/tables/landtrendr_bandarban_disturbance.csv
var JHUM = {
  stable: '371,380 ha (80.8%)',
  permanent: '14,457 ha (3.15%)',
  cyclical: '56,235 ha (12.24%)',
  undetermined: '17,431 ha (3.79%)'
};

var SENSORS = {
  LT04: {id: 'LANDSAT/LT04/C02/T1_L2', optical: ['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']},
  LT05: {id: 'LANDSAT/LT05/C02/T1_L2', optical: ['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']},
  LE07: {id: 'LANDSAT/LE07/C02/T1_L2', optical: ['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']},
  LC08: {id: 'LANDSAT/LC08/C02/T1_L2', optical: ['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7']},
  LC09: {id: 'LANDSAT/LC09/C02/T1_L2', optical: ['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7']}
};
var COMMON = ['blue', 'green', 'red', 'nir', 'swir1', 'swir2'];

// Collection 2 Level-2 scale factors. CLAUDE.md rule 6 — applied before
// any index is computed, every time a collection is touched.
function maskAndScale(img, optical) {
  var qa = img.select('QA_PIXEL');
  var clear = qa.bitwiseAnd(1 << 1).eq(0)
    .and(qa.bitwiseAnd(1 << 2).eq(0))
    .and(qa.bitwiseAnd(1 << 3).eq(0))
    .and(qa.bitwiseAnd(1 << 4).eq(0));
  var sr = img.select(optical, COMMON).multiply(0.0000275).add(-0.2);
  return sr.updateMask(clear).copyProperties(img, ['system:time_start']);
}

// Dry season only (1 Nov - 31 Mar), median reduced. Mixing seasons would
// render phenology as change.
function seasonComposite(year) {
  var start = ee.Date.fromYMD(year - 1, 11, 1);
  var end = ee.Date.fromYMD(year, 4, 1);
  var merged = ee.ImageCollection([]);
  Object.keys(SENSORS).forEach(function (k) {
    var col = ee.ImageCollection(SENSORS[k].id)
      .filterDate(start, end)
      .filter(ee.Filter.lt('CLOUD_COVER', MAX_CLOUD))
      .map(function (img) { return maskAndScale(img, SENSORS[k].optical); });
    merged = merged.merge(col);
  });
  return ee.ImageCollection(merged).median().set('year', year);
}

function withIndices(img) {
  return img
    .addBands(img.normalizedDifference(['nir', 'red']).rename('ndvi'))
    .addBands(img.normalizedDifference(['nir', 'swir2']).rename('nbr'));
}

function aoi(district) {
  return ee.FeatureCollection(PROJECT + district + '_shp');
}

// --- state -----------------------------------------------------------

var current = 'sylhet';

// --- UI scaffolding --------------------------------------------------

var panel = ui.Panel({style: {width: '430px', padding: '10px'}});
var statsHolder = ui.Panel();
var chartHolder = ui.Panel();

panel.add(ui.Label('EcoVision', {fontWeight: 'bold', fontSize: '22px', margin: '0 0 2px 0'}));
panel.add(ui.Label('Forest cover change, 1988-2024',
                   {fontSize: '14px', color: '555555', margin: '0 0 2px 0'}));
panel.add(ui.Label('Gazipur, Sylhet and Bandarban districts, Bangladesh',
                   {fontSize: '12px', color: '777777', margin: '0 0 10px 0'}));

var districtSelect = ui.Select({
  items: DISTRICTS.map(function (d) {
    return {label: d.charAt(0).toUpperCase() + d.slice(1), value: d};
  }),
  value: current,
  onChange: function (value) { current = value; draw(value); }
});
panel.add(ui.Label('District', {fontWeight: 'bold', margin: '4px 0 2px 0'}));
panel.add(districtSelect);

panel.add(ui.Label(
  'Tick layers in the top-right of the map to compare epochs. Click any ' +
  'pixel for its annual NDVI and NBR trajectory.',
  {fontSize: '11px', color: '777777', margin: '6px 0 4px 0'}));

panel.add(statsHolder);
panel.add(chartHolder);

// --- statistics panel ------------------------------------------------

function heading(text) {
  return ui.Label(text, {fontWeight: 'bold', fontSize: '13px', margin: '10px 0 2px 0'});
}

function row(label, value) {
  return ui.Panel(
    [ui.Label(label, {fontSize: '12px', color: '555555', margin: '1px 0', stretch: 'horizontal'}),
     ui.Label(value, {fontSize: '12px', margin: '1px 0'})],
    ui.Panel.Layout.flow('horizontal'));
}

function drawStats(district) {
  statsHolder.clear();
  var s = STATS[district];

  statsHolder.add(heading('Forest extent, 2024'));
  statsHolder.add(ui.Label('Olofsson stratified estimator, 95% CI. Never pixel counts.',
                           {fontSize: '10px', color: '888888', margin: '0 0 3px 0'}));
  statsHolder.add(row('District area', s.area_km2 + ' km2'));
  statsHolder.add(row('Natural forest', s.forest));
  statsHolder.add(row('Non-forest', s.nonforest));

  statsHolder.add(heading('Forest loss, 1990-2024'));
  statsHolder.add(row('Adjusted loss', s.loss));
  statsHolder.add(row('Reference change points', String(s.loss_points)));
  statsHolder.add(ui.Label(
    s.significant
      ? 'Interval excludes zero — loss is statistically detectable here.'
      : 'Interval includes zero — no statistically significant loss is ' +
        'detectable at 95% with this sample size.',
    {fontSize: '11px', color: s.significant ? '9a3412' : '555555', margin: '2px 0 0 0'}));

  statsHolder.add(heading('Dominant loss mechanism'));
  statsHolder.add(ui.Label(MECHANISM[district], {fontSize: '12px', margin: '1px 0'}));

  if (district === 'bandarban') {
    statsHolder.add(heading('Cyclical vs permanent disturbance'));
    statsHolder.add(ui.Label(
      'LandTrendr on the annual NBR series. A plot that recovers within ' +
      'the series is cyclical jhum, not deforestation.',
      {fontSize: '10px', color: '888888', margin: '0 0 3px 0'}));
    statsHolder.add(row('Stable', JHUM.stable));
    statsHolder.add(row('Permanent conversion', JHUM.permanent));
    statsHolder.add(row('Cyclical (jhum)', JHUM.cyclical));
    statsHolder.add(row('Undetermined', JHUM.undetermined));
    statsHolder.add(ui.Label(
      'Of 88,122 ha disturbed, only 16.4% is permanent. A two-date ' +
      'comparison would report roughly four times the actual ' +
      'deforestation. Headline totals count permanent conversion only.',
      {fontSize: '11px', color: '9a3412', margin: '3px 0 0 0'}));
  }
}

// --- map -------------------------------------------------------------

function draw(district) {
  Map.layers().reset();
  chartHolder.clear();

  var region = aoi(district);
  var t0 = withIndices(seasonComposite(EPOCHS.T0)).clip(region.geometry());
  var t1 = withIndices(seasonComposite(EPOCHS.T1)).clip(region.geometry());
  var t2 = withIndices(seasonComposite(EPOCHS.T2)).clip(region.geometry());
  var t3 = withIndices(seasonComposite(EPOCHS.T3)).clip(region.geometry());

  // False colour (NIR/red/green): vegetation reads red. Natural forest is
  // mottled and irregular; tea is flatter, more uniform, rows sometimes
  // visible. This is the pairing the interpreters worked from.
  var fc = {bands: ['nir', 'red', 'green'], min: 0, max: 0.4};
  var ndviVis = {bands: ['ndvi'], min: 0, max: 0.9,
                 palette: ['ffffff', 'd9f0d3', '7fbf7b', '1b7837']};

  Map.addLayer(t0, fc, EPOCHS.T0 + ' false colour', false);
  Map.addLayer(t1, fc, EPOCHS.T1 + ' false colour', false);
  Map.addLayer(t2, fc, EPOCHS.T2 + ' false colour', false);
  Map.addLayer(t3, fc, EPOCHS.T3 + ' false colour', true);

  Map.addLayer(t0.select('ndvi'), ndviVis, EPOCHS.T0 + ' NDVI', false);
  Map.addLayer(t3.select('ndvi'), ndviVis, EPOCHS.T3 + ' NDVI', false);

  // Change: NDVI differencing T0 -> T3, the better of the two bitemporal
  // methods tested. Thresholded, not classified — a viewer can check it
  // against the two NDVI layers above.
  var dNDVI = t3.select('ndvi').subtract(t0.select('ndvi')).rename('dndvi');
  var lossMask = dNDVI.lte(-0.15);
  var gainMask = dNDVI.gte(0.15);
  Map.addLayer(dNDVI.updateMask(lossMask),
               {min: -0.6, max: -0.15, palette: ['7f0000', 'd7301f', 'fc8d59']},
               'NDVI decrease ' + EPOCHS.T0 + '-' + EPOCHS.T3, true);
  Map.addLayer(dNDVI.updateMask(gainMask),
               {min: 0.15, max: 0.6, palette: ['c7e9c0', '41ab5d', '005a32']},
               'NDVI increase ' + EPOCHS.T0 + '-' + EPOCHS.T3, false);

  Map.addLayer(region.style({color: '222222', fillColor: '00000000', width: 2}),
               {}, district + ' boundary');

  Map.centerObject(region, 10);
  drawStats(district);
}

// Click anywhere for that pixel's annual trajectory. This is the layer of
// evidence a single date cannot give you, and it is the whole argument for
// the Bandarban result.
Map.onClick(function (coords) {
  chartHolder.clear();
  var point = ee.Geometry.Point([coords.lon, coords.lat]);

  chartHolder.add(ui.Label('Annual trajectory at clicked pixel',
                           {fontWeight: 'bold', fontSize: '13px', margin: '10px 0 2px 0'}));
  chartHolder.add(ui.Label(
    coords.lat.toFixed(5) + ', ' + coords.lon.toFixed(5),
    {fontSize: '11px', color: '777777', margin: '0 0 4px 0'}));

  // Build the year list client-side. seasonComposite() does JS arithmetic
  // on the year (year - 1 for the November start), which silently produces
  // garbage if handed an ee.Number from ee.List.sequence().map().
  var yearList = [];
  for (var y = START_YEAR; y <= END_YEAR; y++) { yearList.push(y); }
  var series = ee.ImageCollection(yearList.map(function (yr) {
    return withIndices(seasonComposite(yr))
      .set('system:time_start', ee.Date.fromYMD(yr, 1, 1).millis());
  }));

  var chart = ui.Chart.image.series({
    imageCollection: series.select(['ndvi', 'nbr']),
    region: point,
    reducer: ee.Reducer.first(),
    scale: 30
  }).setOptions({
    hAxis: {title: 'year'},
    vAxis: {title: 'index', viewWindow: {min: -0.4, max: 1.0}},
    lineWidth: 2,
    pointSize: 3,
    series: {0: {color: '1b7837'}, 1: {color: 'd95f02'}},
    legend: {position: 'top'}
  });
  chartHolder.add(chart);

  chartHolder.add(ui.Label(
    'Reading it: stable forest is high and flat. Permanent loss drops and ' +
    'stays down. Cyclical jhum drops and recovers over about 5-7 years, ' +
    'often more than once — that is not deforestation. Tea is high but ' +
    'flatter than natural forest, with shallow regular dips from pruning.',
    {fontSize: '11px', color: '555555', margin: '2px 0 0 0'}));
});

// --- methods and limitations -----------------------------------------

panel.add(heading('Forest definition'));
panel.add(ui.Label(
  'Tree canopy cover of at least 30% over a minimum mapping unit of 0.5 ha ' +
  '(about 6 Landsat pixels at 30 m), trees capable of reaching 5 m in situ, ' +
  'EXCLUDING tea and rubber plantations, orchards, agroforestry woodlots ' +
  'and homestead vegetation.',
  {fontSize: '11px', color: '555555', margin: '1px 0'}));
panel.add(ui.Label(
  'Jhum land is classified by canopy condition at the observation date, not ' +
  'by land-use history: an actively cleared plot is non-forest, a fallow ' +
  'meeting the criteria is forest.',
  {fontSize: '11px', color: '555555', margin: '3px 0 0 0'}));

panel.add(heading('Methods'));
panel.add(ui.Label(
  'Landsat Collection 2 Level-2 surface reflectance (L4/L5 TM, L7 ETM+, ' +
  'L8/L9 OLI) via Earth Engine. Dry-season composites (1 Nov - 31 Mar), ' +
  'cloud and shadow masked on QA_PIXEL, median reduced. Cross-sensor ' +
  'harmonisation coefficients were fitted locally after published ' +
  'coefficients were tested and found to perform worse than no correction ' +
  'on this landscape. Areas use the Olofsson (2014) stratified estimator ' +
  'with 95% confidence intervals, never raw pixel counts.',
  {fontSize: '11px', color: '555555', margin: '1px 0'}));

panel.add(heading('Limitations — read before citing any number'));
panel.add(ui.Label(
  'ALL reference-based figures here are PROVISIONAL. Two trained ' +
  'interpreters working from the same written protocol agreed at close to ' +
  'chance on the forest boundary (Cohen kappa 0.157 in Gazipur, 0.038 in ' +
  'Sylhet, against a 0.75 threshold). Until that is reconciled, these ' +
  'accuracy and area figures should be read as indicative, not final.',
  {fontSize: '11px', color: '9a3412', margin: '1px 0'}));
panel.add(ui.Label(
  'The tea plantation layer is incomplete: about 1,300 ha digitised by hand ' +
  'against a district total reported in excess of 10,000 ha, so tea outside ' +
  'the drawn polygons is labelled natural forest and the Sylhet confusion is ' +
  'reduced rather than eliminated. No open spatial dataset of Bangladesh ' +
  'tea estates exists.',
  {fontSize: '11px', color: '555555', margin: '3px 0 0 0'}));
panel.add(ui.Label(
  'The change layer is NDVI differencing between two dates and inherits ' +
  'that method\'s weaknesses. In Bandarban it should not be read as ' +
  'deforestation at all: most canopy loss there is cyclical jhum that ' +
  'recovers, which is why the annual trajectory, not the date pair, ' +
  'produces the headline figure.',
  {fontSize: '11px', color: '555555', margin: '3px 0 0 0'}));
panel.add(ui.Label(
  'Landsat 7 SLC-off affects 2012 and 2013 entirely; neither is an epoch ' +
  'anchor. No usable imagery exists over Bangladesh before ' + START_YEAR + '.',
  {fontSize: '11px', color: '555555', margin: '3px 0 0 0'}));

panel.add(ui.Label(
  'Sheikh Sulaiman Sony and Jalal Uddin Mohammad Akbar — ' +
  'Department of Educational Technology and Engineering, ' +
  'University of Frontier Technology, Bangladesh',
  {fontSize: '10px', color: '888888', margin: '12px 0 0 0'}));

ui.root.insert(0, panel);
Map.setOptions('SATELLITE');
draw(current);
