// EcoVision — digitising Sylhet's tea estates
//
// Tea is excluded from forest (docs/forest_definition.md section 1), so
// class 2 and the plantation reference stratum both need polygons. BFD/BFIS
// geometry has not arrived and OpenStreetMap holds one tea estate polygon
// for the whole district, so these are digitised by hand.
//
// Siddik et al. (2025) report 18 estates in Sylhet. src/tea_search_zone.py
// narrows where they are: 18,467 ha of canopy inside seven upazilas, about
// 5% of the district. That is what makes this a few hours rather than a week.
//
// YOU DO NOT NEED TO SEARCH. There is a named worklist.
//
// data/vector/sylhet_tea_estates_worklist.csv lists 19 estates with their
// addresses. Search each name in Google Earth Pro or the GEE search box,
// go straight to it, and draw. That turns "scan 185 km2 of canopy" into
// "visit 19 known places", which is the difference between a week and an
// afternoon.
//
//   Sylhet Sadar  Burjan, Alibahar, Daddnagar, Dalia, Khadim,
//                 Lackatoorah, Malnicherra, Star
//   Gowainghat    Fatehpur, Habibnagar, Jafflong, Khan
//   Jaintiapur    Afifanagar, Lallakhal, Sreepore
//   Fenchuganj    Dallucherra, Monipur, Moomincherra
//   Kanaighat     Loobacherra
//
// Tick each off in the worklist CSV as you go, with a confidence value.
// Two independent counts exist -- Siddik et al. (2025) say 18, the estate
// directory lists 19 -- so finding 18 or 19 is the expected outcome. If
// you find substantially fewer, estates are being missed; substantially
// more, natural forest is probably being included.
//
// HOW TO USE
//   1. Run this script. Three layers appear: search zone, canopy, imagery.
//   2. Use the Geometry Imports tool to create a FeatureCollection named
//      `tea` with a property `name` (string) and `confidence` (high/medium/low).
//   3. Draw one polygon per estate. Tea is visually distinctive at 10 m:
//      regular planted rows, uniform canopy height, pale service tracks
//      cutting through, hard geometric boundaries. Natural hill forest is
//      structurally chaotic with no repeating pattern and ragged edges.
//   4. When done, run the export task at the bottom.
//   5. Pull the GeoJSON into data/vector/ and run src/tea_estates.py.
//
// WHAT COUNTS
//   Include: mature tea, young tea, and the nursery blocks inside an estate
//            boundary. Estates are contiguous management units.
//   Exclude: estate housing, factories, roads outside the planted area, and
//            the natural forest patches many estates retain on steep ground.
//            Those patches ARE forest and misdrawing them as tea would
//            manufacture the very confusion the thesis measures.
//   Uncertain: mark confidence 'low' and move on. Do not agonise — the
//            reference sample, not this layer, decides accuracy. These
//            polygons define a training class and a sampling stratum.

var PROJECT = 'projects/ecovision-503602/assets/';

var sylhet = ee.FeatureCollection(PROJECT + 'sylhet_shp');

// Upload data/vector/sylhet_tea_search_zone.geojson as an asset first, or
// paste its geometry here. Falls back to the whole district if absent.
var SEARCH_ZONE_ASSET = PROJECT + 'sylhet_tea_search_zone';

var zone;
try {
  zone = ee.FeatureCollection(SEARCH_ZONE_ASSET);
} catch (e) {
  zone = sylhet;
  print('Search zone asset not found — showing the whole district.');
}

// --- canopy layer ----------------------------------------------------
// Same threshold as everything else. Estates sit inside this.
var CANOPY_THRESHOLD = 30;
var hansen = ee.Image('UMD/hansen/global_forest_change_2025_v1_13');
var canopy = hansen.select('treecover2000').unmask(0)
  .gte(CANOPY_THRESHOLD)
  .selfMask()
  .clip(zone);

// --- imagery ---------------------------------------------------------
// Sentinel-2 at 10 m, NOT Landsat. This layer is for a human eye deciding
// where an estate boundary runs; it is never analysis input, so the 30 m
// constraint that governs the rest of the thesis does not apply here.
// Dry season, matching the analysis window, so the scene looks like the
// composites the model will see.
var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(zone)
  .filterDate('2023-11-01', '2024-03-31')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 15))
  .median()
  .clip(zone);

Map.centerObject(zone, 10);

Map.addLayer(s2, {bands: ['B4', 'B3', 'B2'], min: 0, max: 2500}, 'Sentinel-2 true colour');
Map.addLayer(s2, {bands: ['B8', 'B4', 'B3'], min: 0, max: 4000}, 'Sentinel-2 false colour (NIR)', false);
Map.addLayer(canopy, {palette: ['1b7837']}, 'Canopy >= 30%', true, 0.45);
Map.addLayer(zone.style({color: 'ff7f00', fillColor: '00000000', width: 2}), {}, 'Search zone');
Map.addLayer(sylhet.style({color: '000000', fillColor: '00000000', width: 1}), {}, 'Sylhet district');

print('Search zone upazilas:', zone.aggregate_array('shapeName'));
print('Expected estates (Siddik et al. 2025): 18');
print('Expected area under tea: ~10,000 ha');

// False colour helps: tea reads as a flatter, more uniform red than natural
// forest, and the planted rows show as fine regular texture. Toggle it on
// when a boundary is ambiguous in true colour.

// --- export ----------------------------------------------------------
// Uncomment once `tea` exists in Geometry Imports.
//
// Export.table.toDrive({
//   collection: tea,
//   description: 'sylhet_tea_estates',
//   folder: 'ecovision_vector',
//   fileFormat: 'GeoJSON'
// });

// --- sanity check while drawing --------------------------------------
// Re-run after each few polygons. If total area drifts far above 10,000 ha
// you are probably including natural forest inside estate boundaries; far
// below and you are missing estates or drawing only their cores.
//
// print('Estates drawn:', tea.size());
// print('Total area (ha):', tea.geometry().area(30).divide(1e4));
