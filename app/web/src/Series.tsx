import { useState } from "react";
import { SeriesPoint } from "./api";

interface Props {
  series: SeriesPoint[];
}

export default function Series({ series }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const points = series.filter((p) => p.median_ndvi != null);
  if (points.length < 2) return null;

  const w = 300;
  const h = 96;
  const pad = 8;
  const x = (i: number) => pad + (i / (points.length - 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - ((v + 0.2) / 1.2) * (h - 2 * pad);
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.median_ndvi as number).toFixed(1)}`)
    .join(" ");
  const hovered = hover != null ? points[hover] : null;

  return (
    <section className="card">
      <div className="card-head">
        <h3>NDVI-Verlauf</h3>
        <span className="muted small">
          {points[0].date.slice(0, 4)}–{points[points.length - 1].date.slice(0, 4)}
        </span>
      </div>
      <div className="spark-wrap">
        <svg viewBox={`0 0 ${w} ${h}`} className="spark" role="img" aria-label="NDVI-Zeitreihe">
          <line x1={pad} y1={y(0)} x2={w - pad} y2={y(0)} className="spark-zero" />
          <path d={d} fill="none" stroke="var(--accent)" strokeWidth="2" />
          {points.map((p, i) => {
            const isAnomaly = (p.anomalies ?? []).length > 0;
            return (
              <circle
                key={p.date}
                cx={x(i)}
                cy={y(p.median_ndvi as number)}
                r={hover === i ? 4.5 : isAnomaly ? 3.5 : 2.5}
                className={isAnomaly ? "spark-dot anomaly" : "spark-dot"}
                fill={isAnomaly ? "var(--danger)" : "var(--accent)"}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
            );
          })}
          {hover != null && (
            <line
              x1={x(hover)}
              y1={pad}
              x2={x(hover)}
              y2={h - pad}
              className="spark-guide"
            />
          )}
        </svg>
        {hovered && (
          <div className="spark-tip">
            <strong>{new Date(hovered.date).toLocaleDateString("de-DE")}</strong>
            <span>
              NDVI{" "}
              {(hovered.median_ndvi as number).toLocaleString("de-DE", {
                maximumFractionDigits: 2,
              })}
            </span>
            {(hovered.anomalies ?? []).map((a) => (
              <span key={a.type} className="tip-warn">
                ⚠ {a.type === "sudden_drop" ? "Einbruch" : "unter Vorjahre"}
              </span>
            ))}
          </div>
        )}
      </div>
      <p className="muted small">
        {points[0].date} bis {points[points.length - 1].date} · {points.length} Aufnahmen · rote
        Punkte = Auffälligkeit
      </p>
    </section>
  );
}
