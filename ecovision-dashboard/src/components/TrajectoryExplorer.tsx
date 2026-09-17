import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import Trajectory, { type TrajectoryPoint } from "./Trajectory";
import raw from "../data/trajectories.json";

interface Payload {
  startYear: number;
  endYear: number;
  scale: number;
  note: string;
  points: TrajectoryPoint[];
}
const data = raw as unknown as Payload;

const KIND_LABEL: Record<string, string> = {
  cyclical: "Cyclical jhum",
  permanent: "Permanent conversion",
  stable: "Stable forest",
  plantation: "Tea plantation",
  loss_gazipur: "Abrupt conversion",
};

const KIND_COLOUR: Record<string, string> = {
  cyclical: "var(--recover)",
  permanent: "var(--loss)",
  stable: "var(--ink-faint)",
  plantation: "var(--caution)",
  loss_gazipur: "var(--loss)",
};

/**
 * Two examples of each class ship, so the label alone repeats and the
 * buttons become indistinguishable. Number them only where a kind actually
 * occurs more than once — "Cyclical jhum 1 / 2", but a lone "Tea plantation".
 */
function labelsFor(points: TrajectoryPoint[]): Record<string, string> {
  const counts = points.reduce<Record<string, number>>((acc, p) => {
    acc[p.kind] = (acc[p.kind] ?? 0) + 1;
    return acc;
  }, {});
  const seen: Record<string, number> = {};
  return Object.fromEntries(
    points.map((p) => {
      const base = KIND_LABEL[p.kind];
      if (counts[p.kind] === 1) return [p.id, base];
      seen[p.kind] = (seen[p.kind] ?? 0) + 1;
      return [p.id, `${base} ${seen[p.kind]}`];
    }),
  );
}

export default function TrajectoryExplorer() {
  const [selectedId, setSelectedId] = useState(
    data.points.find((p) => p.kind === "cyclical")?.id ?? data.points[0].id,
  );
  const labels = useMemo(() => labelsFor(data.points), []);
  const selected = useMemo(
    () => data.points.find((p) => p.id === selectedId) ?? data.points[0],
    [selectedId],
  );

  return (
    <div className="traj-explorer">
      <div className="traj-map">
        <MapContainer
          center={[22.1, 92.0]}
          zoom={8}
          scrollWheelZoom={false}
          style={{ height: "100%", minHeight: "20rem" }}
        >
          <TileLayer
            attribution="Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            maxZoom={18}
          />
          {data.points.map((p) => {
            const active = p.id === selectedId;
            return (
              <CircleMarker
                key={p.id}
                center={[p.lat, p.lon]}
                radius={active ? 9 : 6}
                pathOptions={{
                  color: active ? "#ffffff" : KIND_COLOUR[p.kind],
                  weight: active ? 3 : 2,
                  fillColor: KIND_COLOUR[p.kind],
                  fillOpacity: active ? 1 : 0.75,
                }}
                eventHandlers={{ click: () => setSelectedId(p.id) }}
              >
                <Tooltip>{labels[p.id]}</Tooltip>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>

      <div className="traj-side">
        <div className="traj-picker" role="group" aria-label="Choose an example location">
          {data.points.map((p) => (
            <button
              key={p.id}
              type="button"
              id={`traj-${p.id}`}
              aria-pressed={p.id === selectedId}
              onClick={() => setSelectedId(p.id)}
            >
              <i style={{ background: KIND_COLOUR[p.kind] }} aria-hidden="true" />
              {labels[p.id]}
            </button>
          ))}
        </div>

        <h3>{labels[selected.id]}</h3>
        <Trajectory
          point={selected}
          startYear={data.startYear}
          endYear={data.endYear}
        />
      </div>
    </div>
  );
}
