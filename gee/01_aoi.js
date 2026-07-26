// EcoVision — Stage 0: Area of Interest setup
// Loads district boundaries and confirms geometry before any data pull.
//
// Prerequisite: upload your district boundary shapefile (from HDX or
// geoBoundaries) as a GEE asset first, then point this script at it.

var gazipur = ee.FeatureCollection('projects/YOUR_PROJECT/assets/gazipur_boundary');
var sylhet  = ee.FeatureCollection('projects/YOUR_PROJECT/assets/sylhet_boundary');

Map.centerObject(gazipur, 10);
Map.addLayer(gazipur, {color: 'FF0000'}, 'Gazipur AOI');
Map.addLayer(sylhet, {color: '0000FF'}, 'Sylhet AOI');

print('Gazipur area (sq km):', gazipur.geometry().area().divide(1e6));
print('Sylhet area (sq km):', sylhet.geometry().area().divide(1e6));

// Sanity check against known values (~1806 sq km Gazipur, ~3490 sq km Sylhet).
// If these numbers are far off, the boundary asset was uploaded with the
// wrong CRS or is not dissolved to a single district polygon.
