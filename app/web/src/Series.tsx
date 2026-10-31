interface Point {
  date: string;
  median_ndvi: number | null;
}

interface Props {
  series: Point[];
}

export default function Series({ series }: Props) {
  const points = series.filter((p) => p.median_ndvi != null);
  if (points.length < 2) return null;
  const w = 300;
  const h = 80;
  const pad = 6;
  const x = (i: number) => pad + (i / (points.length - 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - ((v + 0.2) / 1.2) * (h - 2 * pad);
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.median_ndvi as number).toFixed(1)}`)
    .join(" ");

  return (
    <section className="card">
      <h3>NDVI-Verlauf</h3>
      <svg viewBox={`0 0 ${w} ${h}`} className="spark" role="img" aria-label="NDVI-Zeitreihe">
        <path d={d} fill="none" stroke="var(--accent)" strokeWidth="2" />
        {points.map((p, i) => (
          <circle
            key={p.date}
            cx={x(i)}
            cy={y(p.median_ndvi as number)}
            r="2.5"
            fill="var(--accent)"
          />
        ))}
      </svg>
      <p className="muted small">
        {points[0].date} bis {points[points.length - 1].date} · {points.length} Aufnahmen
      </p>
    </section>
  );
}
