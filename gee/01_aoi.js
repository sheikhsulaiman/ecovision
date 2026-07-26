// EcoVision — Phase 1: Area of Interest setup
//
// Loads the three district boundaries and confirms geometry before any
// data pull. Run this first in a fresh session; every other gee/ script
// assumes these asset IDs resolve.
//
// Assets were produced by src/prepare_aoi.py from geoBoundaries BGD ADM2
// (2020 vintage, CC BY 3.0 IGO — must be cited in Chapter 3) and uploaded
// via Code Editor > Assets > NEW > Shape files.

var PROJECT = 'projects/ecovision-503602/assets/';

var DISTRICTS = {
  gazipur:   {asset: PROJECT + 'gazipur_shp',   expected_km2: 1818.7, colour: 'e15759'},
  sylhet:    {asset: PROJECT + 'sylhet_shp',    expected_km2: 3416.1, colour: '4e79a7'},
  bandarban: {asset: PROJECT + 'bandarban_shp', expected_km2: 4592.1, colour: '59a14f'}
};

// Expected areas above are what src/prepare_aoi.py measured locally in
// EPSG:32646, NOT the published BBS figures. That is deliberate: this
// check is asking "did the asset survive the upload intact", not "is
// geoBoundaries correct". A mismatch here means the upload mangled the
// geometry or the wrong file was uploaded.
var TOLERANCE = 0.01;  // 1% — upload should be near-exact, not approximate

// Landsat native CRS for Bangladesh. Areas are computed in this
// projection; do not reproject for analysis (methodology_plan.md 1.1).
var UTM46N = 'EPSG:32646';

// --- load ------------------------------------------------------------

var aois = {};
Object.keys(DISTRICTS).forEach(function(name) {
  aois[name] = ee.FeatureCollection(DISTRICTS[name].asset);
});

// Combined boundary, used by later scripts that iterate all three.
var allDistricts = ee.FeatureCollection([
  aois.gazipur, aois.sylhet, aois.bandarban
]).flatten();

// --- display ---------------------------------------------------------

Map.centerObject(allDistricts, 7);
Object.keys(DISTRICTS).forEach(function(name) {
  Map.addLayer(
    aois[name].style({color: DISTRICTS[name].colour, fillColor: '00000000', width: 2}),
    {},
    name.charAt(0).toUpperCase() + name.slice(1)
  );
});

// --- verify ----------------------------------------------------------

Object.keys(DISTRICTS).forEach(function(name) {
  var cfg = DISTRICTS[name];
  var area = aois[name].geometry().area({maxError: 1, proj: UTM46N}).divide(1e6);
  var deviation = area.subtract(cfg.expected_km2).abs().divide(cfg.expected_km2);

  print(name + ' — area (km2)', area);
  print(name + ' — matches local build', deviation.lte(TOLERANCE));
  print(name + ' — features', aois[name].size());
});

print('Combined features (expect 3)', allDistricts.size());

// If "matches local build" prints false for any district, stop. Either the
// wrong shapefile was uploaded, or GEE simplified the geometry on ingest.
// Re-upload rather than proceeding — every downstream area statistic is
// measured against these boundaries.
//
// If "features" is anything other than 1 per district, the shapefile was
// not dissolved. Re-run src/prepare_aoi.py and re-upload.

// --- exports for other scripts ---------------------------------------
// The Code Editor has no module system for user scripts other than
// require() on a saved repo path. Until these are saved to a shared repo,
// copy the DISTRICTS block above into each script rather than duplicating
// asset ID strings by hand — a typo'd asset ID fails loudly, but a
// typo'd *expected area* fails silently.

exports.DISTRICTS = DISTRICTS;
exports.aois = aois;
exports.allDistricts = allDistricts;
exports.UTM46N = UTM46N;
