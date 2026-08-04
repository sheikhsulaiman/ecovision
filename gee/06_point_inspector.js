// EcoVision — reference point inspector
//
// Google Earth Pro is the primary interpretation tool, but its historical
// imagery over rural Bangladesh rarely reaches 1990 — and class_t0 is a 1990
// judgement. This script fills that gap: click anywhere and get the T0 and T3
// Landsat composites side by side, plus the full annual NDVI and NBR series
// at that pixel.
//
// Use it for:
//   * every T0 (1990) call, since Earth Pro usually cannot show you 1990
//   * any point where T3 is ambiguous in Earth Pro
//   * every Bandarban point, because a jhum plot's trajectory is the whole
//     question and a single date cannot answer it
//
// HOW TO USE
//   1. Run. Paste a point's lat/lon into the boxes, or just click the map.
//   2. Read the chart. Then record your answer in the interpretation CSV.
//
// READING THE TRAJECTORY
//   stable forest      high NDVI/NBR, flat, small seasonal wobble
//   permanent loss     drop, then STAYS down for the rest of the series
//   cyclical (jhum)    drop, then recovers over ~5-7 years, often repeating.
//                      This is NOT deforestation (rule 9) — Bandarban loss
//                      figures count permanent conversion only
//   plantation/tea     high but flatter and lower-amplitude than natural
//                      forest; pruning cycles show as regular shallow dips
//   degradation        gradual decline without a sharp step

var PROJECT = 'projects/ecovision-503602/assets/';

var START_YEAR = 1988;   // docs/phase2_audit.md
var END_YEAR = 2024;
var EPOCHS = {T0: 1990, T1: 2000, T2: 2010, T3: 2024};

var SENSORS = {
  LT04: {id: 'LANDSAT/LT04/C02/T1_L2', optical: ['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']},
  LT05: {id: 'LANDSAT/LT05/C02/T1_L2', optical: ['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']},
  LE07: {id: 'LANDSAT/LE07/C02/T1_L2', optical: ['SR_B1','SR_B2','SR_B3','SR_B4','SR_B5','SR_B7']},
  LC08: {id: 'LANDSAT/LC08/C02/T1_L2', optical: ['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7']},
  LC09: {id: 'LANDSAT/LC09/C02/T1_L2', optical: ['SR_B2','SR_B3','SR_B4','SR_B5','SR_B6','SR_B7']}
};
var COMMON = ['blue','green','red','nir','swir1','swir2'];

function maskAndScale(img, optical) {
  var qa = img.select('QA_PIXEL');
  var clear = qa.bitwiseAnd(1 << 1).eq(0)
    .and(qa.bitwiseAnd(1 << 2).eq(0))
    .and(qa.bitwiseAnd(1 << 3).eq(0))
    .and(qa.bitwiseAnd(1 << 4).eq(0));
  var sr = img.select(optical, COMMON).multiply(0.0000275).add(-0.2);
  return sr.updateMask(clear).copyProperties(img, ['system:time_start']);
}

// Dry season only, matching the analysis window. Mixing seasons would show
// phenology as if it were change.
function seasonComposite(year) {
  var start = ee.Date.fromYMD(year - 1, 11, 1);
  var end = ee.Date.fromYMD(year, 4, 1);
  var merged = ee.ImageCollection([]);
  Object.keys(SENSORS).forEach(function (k) {
    var col = ee.ImageCollection(SENSORS[k].id)
      .filterDate(start, end)
      .filter(ee.Filter.lt('CLOUD_COVER', 40))
      .map(function (img) { return maskAndScale(img, SENSORS[k].optical); });
    merged = merged.merge(col);
  });
  return ee.ImageCollection(merged).median()
    .set('year', year);
}

function withIndices(img) {
  return img
    .addBands(img.normalizedDifference(['nir', 'red']).rename('ndvi'))
    .addBands(img.normalizedDifference(['nir', 'swir2']).rename('nbr'));
}

// --- UI --------------------------------------------------------------

var panel = ui.Panel({style: {width: '420px', padding: '8px'}});
var latBox = ui.Textbox({placeholder: 'lat', style: {width: '120px'}});
var lonBox = ui.Textbox({placeholder: 'lon', style: {width: '120px'}});
var idBox = ui.Textbox({placeholder: 'point_id (optional)', style: {width: '160px'}});
var chartHolder = ui.Panel();

panel.add(ui.Label('EcoVision point inspector', {fontWeight: 'bold', fontSize: '16px'}));
panel.add(ui.Label('Paste a point from the reference CSV, or click the map.'));
panel.add(ui.Panel([latBox, lonBox], ui.Panel.Layout.flow('horizontal')));
panel.add(idBox);

function inspect(point, label) {
  chartHolder.clear();
  Map.layers().reset();

  var t0 = withIndices(seasonComposite(EPOCHS.T0));
  var t3 = withIndices(seasonComposite(EPOCHS.T3));

  // False colour: vegetation reads red. Natural forest is a mottled,
  // irregular red; tea is flatter and more uniform with visible rows.
  var vis = {bands: ['nir', 'red', 'green'], min: 0, max: 0.4};
  Map.addLayer(t0, vis, 'T0 ' + EPOCHS.T0 + ' (false colour)');
  Map.addLayer(t3, vis, 'T3 ' + EPOCHS.T3 + ' (false colour)', false);
  Map.addLayer(t3, {bands: ['red', 'green', 'blue'], min: 0, max: 0.25},
               'T3 ' + EPOCHS.T3 + ' (true colour)', false);
  Map.addLayer(ee.FeatureCollection([ee.Feature(point)]).style(
    {color: 'ffff00', pointSize: 10}), {}, 'point');
  Map.centerObject(point, 14);

  // Annual series, one dry-season composite per year.
  var years = ee.List.sequence(START_YEAR, END_YEAR);
  var series = ee.ImageCollection(years.map(function (y) {
    var img = withIndices(seasonComposite(ee.Number(y).getInfo ? y : y));
    return img.set('system:time_start',
                   ee.Date.fromYMD(ee.Number(y), 1, 1).millis());
  }));

  var chart = ui.Chart.image.series({
    imageCollection: series.select(['ndvi', 'nbr']),
    region: point,
    reducer: ee.Reducer.first(),
    scale: 30
  }).setOptions({
    title: 'Annual dry-season NDVI and NBR — ' + label,
    hAxis: {title: 'year'},
    vAxis: {title: 'index', viewWindow: {min: -0.4, max: 1.0}},
    lineWidth: 2,
    pointSize: 4,
    series: {0: {color: '1b7837'}, 1: {color: 'd95f02'}}
  });
  chartHolder.add(chart);
  chartHolder.add(ui.Label(
    'Gaps mean no cloud-free observation that year — not zero vegetation.',
    {fontSize: '11px', color: '666666'}));
}

panel.add(ui.Button('Inspect coordinates', function () {
  var lat = parseFloat(latBox.getValue());
  var lon = parseFloat(lonBox.getValue());
  if (isNaN(lat) || isNaN(lon)) {
    chartHolder.clear();
    chartHolder.add(ui.Label('Enter a valid lat and lon.', {color: 'red'}));
    return;
  }
  inspect(ee.Geometry.Point([lon, lat]), idBox.getValue() || (lat + ', ' + lon));
}));

panel.add(chartHolder);
ui.root.insert(0, panel);

Map.style().set('cursor', 'crosshair');
Map.onClick(function (coords) {
  latBox.setValue(coords.lat.toFixed(6));
  lonBox.setValue(coords.lon.toFixed(6));
  inspect(ee.Geometry.Point([coords.lon, coords.lat]),
          coords.lat.toFixed(4) + ', ' + coords.lon.toFixed(4));
});

Object.keys(PROJECT ? {gazipur: 1, sylhet: 1, bandarban: 1} : {}).forEach(function (d) {
  Map.addLayer(ee.FeatureCollection(PROJECT + d + '_shp')
    .style({color: '000000', fillColor: '00000000', width: 1}), {}, d, false);
});
