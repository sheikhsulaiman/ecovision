import { useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import { DISTRICTS, byId, type DistrictId } from "../data/findings";
import districtsRaw from "../data/districts.geojson?raw";

const districts = JSON.parse(districtsRaw) as FeatureCollection<
  Geometry,
  { district: DistrictId }
>;

/** Semantic colours, read off the stylesheet so the map follows the theme. */
function token(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name);
  return v.trim() || fallback;
}

/** Leaflet sizes itself on mount; a district switch has to fly it. */
function FlyTo({ id }: { id: DistrictId }) {
  const map = useMap();
  const d = byId(id);
  useEffect(() => {
    map.flyTo(d.centre, d.zoom, { duration: 0.8 });
  }, [id, map, d.centre, d.zoom]);
  return null;
}

export default function MapExplorer() {
  const [selected, setSelected] = useState<DistrictId>("bandarban");
  const district = byId(selected);

  // Recomputed on selection so the highlight follows, and keyed on the
  // theme so the colours survive a light/dark switch.
  const style = useMemo(
    () => (feature?: Feature<Geometry, { district: DistrictId }>) => {
      const isSelected = feature?.properties.district === selected;
      // Over imagery the outline has to carry itself: white for the
      // unselected districts, the loss red for the one in focus, and only
      // a whisper of fill so the forest underneath stays readable.
      return {
        color: isSelected ? token("--loss", "#c33c54") : "#ffffff",
        weight: isSelected ? 3 : 1.5,
        opacity: isSelected ? 1 : 0.75,
        fillColor: isSelected ? token("--loss", "#c33c54") : "#ffffff",
        fillOpacity: isSelected ? 0.12 : 0.03,
      };
    },
    [selected],
  );

  return (
    <>
      <div className="explorer">
        <div className="map-pane">
          <div className="district-tabs" role="group" aria-label="Select a district">
            {DISTRICTS.map((d) => (
              <button
                key={d.id}
                type="button"
                id={`tab-${d.id}`}
                aria-pressed={selected === d.id}
                onClick={() => setSelected(d.id)}
              >
                {d.name}
              </button>
            ))}
          </div>
          <MapContainer
            center={district.centre}
            zoom={district.zoom}
            scrollWheelZoom={false}
            style={{ height: "calc(100% - 3rem)", minHeight: "23rem" }}
          >
            {/* Satellite imagery rather than a street map: the subject is
                forest cover, and on a road basemap the district outlines
                enclose nothing a reader can see. Esri World Imagery needs
                no API key -- CARTO's basemaps now do, and silently serve
                "API KEY REQUIRED" tiles without erroring. */}
            <TileLayer
              attribution='Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={18}
            />
            <GeoJSON
              key={selected}
              data={districts}
              style={style}
              onEachFeature={(feature, layer) => {
                const id = (feature.properties as { district: DistrictId }).district;
                layer.on("click", () => setSelected(id));
                layer.bindTooltip(byId(id).name, { sticky: true });
              }}
            />
            <FlyTo id={selected} />
          </MapContainer>
        </div>

        <div className="stats-pane">
          <h3>{district.name}</h3>
          <p className={`mech-line signal-${district.signal}`}>
            {district.signal} signal
          </p>

          <dl>
            <div className="stat-row">
              <dt>District area</dt>
              <dd>{district.areaKm2.toLocaleString()} km²</dd>
            </div>
            <div className="stat-row">
              <dt>Natural forest, 2024</dt>
              <dd>{district.forest2024}</dd>
            </div>
            <div className="stat-row">
              <dt>Non-forest, 2024</dt>
              <dd>{district.nonForest2024}</dd>
            </div>
            <div className="stat-row">
              <dt>Adjusted loss, 1990–2024</dt>
              <dd>{district.adjustedLoss}</dd>
            </div>
            <div className="stat-row">
              <dt>Reference change points</dt>
              <dd>{district.referenceChangePoints}</dd>
            </div>
            <div className="stat-row">
              <dt>Map agreement at 2024</dt>
              <dd>{district.landCoverOverall.toFixed(3)}</dd>
            </div>
          </dl>

          <p
            className={`verdict ${
              district.lossExcludesZero ? "detectable" : "not-detectable"
            }`}
          >
            {district.lossExcludesZero
              ? "The confidence interval excludes zero. Loss is statistically detectable here — the only district where that is true."
              : "The confidence interval includes zero. No statistically significant loss is detectable at 95% with this sample size."}
          </p>

          <p style={{ fontSize: "var(--step--1)", color: "var(--ink-soft)", marginTop: "1rem" }}>
            {district.blurb}
          </p>
        </div>
      </div>
      <p className="figcaption" style={{ fontSize: "var(--step--1)", color: "var(--ink-faint)", marginTop: "0.8rem" }}>
        Boundaries from geoBoundaries ADM2, simplified for display. Areas and
        confidence intervals come from the Olofsson stratified estimator run at
        the native 30 m, not from these simplified outlines.
      </p>
    </>
  );
}
