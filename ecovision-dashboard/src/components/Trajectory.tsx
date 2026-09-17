import { useId } from "react";

export interface TrajectoryPoint {
  id: string;
  district: string;
  kind: string;
  lat: number;
  lon: number;
  ndvi: (number | null)[];
  nbr: (number | null)[];
  reading: string;
}

const W = 720;
const H = 260;
const PAD = { top: 16, right: 16, bottom: 34, left: 44 };

const SERIES = [
  { key: "nbr" as const, label: "NBR", colour: "var(--recover)" },
  { key: "ndvi" as const, label: "NDVI", colour: "var(--caution)" },
];

/**
 * Annual dry-season NDVI and NBR at one 30 m pixel.
 *
 * Drawn as a real chart rather than a sparkline because the shape is the
 * argument: a sawtooth is jhum, a step down that never returns is
 * deforestation, and the difference is invisible in any single pair of
 * dates. Nulls break the line rather than interpolating across them — a
 * year with no usable observation is not a year with an average value.
 */
export default function Trajectory({
  point,
  startYear,
  endYear,
}: {
  point: TrajectoryPoint;
  startYear: number;
  endYear: number;
}) {
  const clipId = useId();
  const years = endYear - startYear;

  const lo = -0.2;
  const hi = 1.0;
  const x = (i: number) => PAD.left + (i / years) * (W - PAD.left - PAD.right);
  const y = (v: number) =>
    PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);

  /** Split into runs of consecutive non-null values so gaps stay gaps. */
  const runs = (vals: (number | null)[]) => {
    const out: string[] = [];
    let current: string[] = [];
    vals.forEach((v, i) => {
      if (v === null) {
        if (current.length > 1) out.push(current.join(" "));
        current = [];
        return;
      }
      current.push(`${current.length ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    });
    if (current.length > 1) out.push(current.join(" "));
    return out;
  };

  const ticks = [1990, 2000, 2010, 2020];
  const vTicks = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <figure className="trajectory">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Annual NDVI and NBR from ${startYear} to ${endYear} at ${point.lat.toFixed(4)}, ${point.lon.toFixed(4)}. ${point.reading}`}
      >
        <defs>
          <clipPath id={clipId}>
            <rect
              x={PAD.left}
              y={PAD.top}
              width={W - PAD.left - PAD.right}
              height={H - PAD.top - PAD.bottom}
            />
          </clipPath>
        </defs>

        {vTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(v)}
              y2={y(v)}
              stroke="var(--rule-soft)"
              strokeWidth="1"
            />
            <text
              x={PAD.left - 8}
              y={y(v) + 3.5}
              textAnchor="end"
              fontSize="10"
              fill="var(--ink-faint)"
              fontFamily="var(--mono)"
            >
              {v.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Zero is the meaningful reference for a normalised index. */}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={y(0)}
          y2={y(0)}
          stroke="var(--ink-faint)"
          strokeWidth="1"
        />

        {ticks.map((t) => (
          <text
            key={t}
            x={x(t - startYear)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            fontSize="10"
            fill="var(--ink-faint)"
            fontFamily="var(--mono)"
          >
            {t}
          </text>
        ))}

        <g clipPath={`url(#${clipId})`}>
          {SERIES.map((s) =>
            runs(point[s.key]).map((d, i) => (
              <path
                key={`${s.key}-${i}`}
                d={d}
                fill="none"
                stroke={s.colour}
                strokeWidth="1.8"
                strokeLinejoin="round"
              />
            )),
          )}
          {SERIES.map((s) =>
            point[s.key].map((v, i) =>
              v === null ? null : (
                <circle
                  key={`${s.key}-p-${i}`}
                  cx={x(i)}
                  cy={y(v)}
                  r="2"
                  fill={s.colour}
                />
              ),
            ),
          )}
        </g>

        <text
          x={PAD.left}
          y={H - 4}
          fontSize="10"
          fill="var(--ink-faint)"
          fontFamily="var(--mono)"
        >
          year
        </text>
      </svg>

      <div className="traj-key">
        {SERIES.map((s) => (
          <span key={s.key}>
            <i style={{ background: s.colour }} aria-hidden="true" />
            {s.label}
          </span>
        ))}
        <span className="coords">
          {point.lat.toFixed(4)}, {point.lon.toFixed(4)} · 30 m pixel
        </span>
      </div>

      <figcaption>{point.reading}</figcaption>
    </figure>
  );
}
