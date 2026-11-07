import { Anomaly } from "./api";
import { formatDate } from "./App";

const TYPE_LABEL: Record<string, string> = {
  sudden_drop: "Einbruch",
  seasonal_deficit: "Schwächer als Vorjahre",
};

export default function Anomalies({ items }: { items: Anomaly[] }) {
  return (
    <section className="card warn-card">
      <h3>⚠ Auffälligkeiten</h3>
      <ul className="anomaly-list">
        {items.slice(0, 6).map((a, i) => (
          <li key={`${a.date}-${a.type}-${i}`}>
            <span className="anomaly-date">
              {formatDate(a.date)}
              {a.type in TYPE_LABEL ? ` · ${TYPE_LABEL[a.type]}` : ""}
            </span>
            <span className="anomaly-detail">
              NDVI {a.ndvi.toLocaleString("de-DE", { maximumFractionDigits: 2 })} statt{" "}
              {a.baseline.toLocaleString("de-DE", { maximumFractionDigits: 2 })} erwartet
            </span>
          </li>
        ))}
      </ul>
      <p className="muted small">
        Gemeldet wird nur, wenn der Unterschied klar über der Messunsicherheit liegt.
        Bitte vor ortseigenen Entscheidungen vor Ort prüfen (z.&nbsp;B. Hagel, Mahd, Wasser).
      </p>
    </section>
  );
}
