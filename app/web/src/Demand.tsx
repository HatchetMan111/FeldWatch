import { DemandPayload } from "./api";

const FLAG_TEXT: Record<string, string> = {
  stale_canopy: "Letzte klare Aufnahme ist älter als 21 Tage.",
  insufficient_pixels: "Feld zu klein für eine belastbare Statistik.",
  no_clear_observation: "Keine wolkenfreie Aufnahme im Zeitraum.",
};

const WEEKDAYS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

interface Props {
  payload: DemandPayload;
}

function weekdayOf(date: string | null | undefined, fallbackIndex: number): string {
  if (!date) return `Tag ${fallbackIndex + 1}`;
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return `Tag ${fallbackIndex + 1}`;
  return WEEKDAYS[parsed.getDay()];
}

export default function Demand({ payload }: Props) {
  const etc = payload.etc_mm ?? [];
  const rain = payload.precip_mm ?? [];
  const dates = payload.dates ?? [];
  const weekMm = payload.week_mm;
  const weekM3 = payload.week_m3;
  const status = payload.status ?? "unavailable";
  const flags = (payload.flags ?? []).filter(Boolean);
  const cover = payload.cover;
  const kcb = payload.kcb;
  const canopyDate = payload.canopy_date;
  const age = payload.canopy_age_days;
  const maxEtc = Math.max(1, ...etc.map((v) => v ?? 0));
  const maxRain = Math.max(1, ...rain.map((v) => v ?? 0));

  return (
    <section className="card">
      <h3>Wasserbedarf – nächste 7 Tage</h3>
      {status === "unavailable" ? (
        <p className="muted">
          Keine belastbare Berechnung{payload.reason ? ` (${payload.reason})` : ""}.
        </p>
      ) : (
        <>
          <div className="metrics">
            <div className="metric">
              <span className="metric-value">
                {weekMm != null ? weekMm.toLocaleString("de-DE", { maximumFractionDigits: 1 }) : "–"}
              </span>
              <span className="metric-unit">mm</span>
              <span className="metric-label">Bedarf / Woche</span>
            </div>
            <div className="metric">
              <span className="metric-value">
                {weekM3 != null ? Math.round(weekM3).toLocaleString("de-DE") : "–"}
              </span>
              <span className="metric-unit">m³</span>
              <span className="metric-label">auf der Fläche</span>
            </div>
            <div className="metric">
              <span className="metric-value">
                {cover == null ? "–" : (cover * 100).toLocaleString("de-DE", { maximumFractionDigits: 0 })}
              </span>
              <span className="metric-unit">%</span>
              <span className="metric-label">Bewachsung</span>
            </div>
          </div>

          <div className="bar-group">
            <div className="bars" title="Täglicher Wasserbedarf (ETc)">
              {etc.map((v, i) => (
                <div
                  key={`etc-${i}`}
                  className="bar"
                  title={`${weekdayOf(dates[i], i)}: ${v != null ? `${v.toLocaleString("de-DE")} mm Bedarf` : "keine Daten"}`}
                  style={{
                    height: `${Math.min(100, ((v ?? 0) / maxEtc) * 100)}%`,
                    background: v === null ? "var(--danger-soft)" : "var(--accent)",
                  }}
                />
              ))}
            </div>
            <div className="bars rain" title="Erwarteter Regen">
              {rain.map((v, i) => (
                <div
                  key={`rain-${i}`}
                  className="bar"
                  title={`${weekdayOf(dates[i], i)}: ${v != null ? `${v.toLocaleString("de-DE")} mm Regen` : "keine Daten"}`}
                  style={{ height: `${Math.min(100, ((v ?? 0) / maxRain) * 100)}%` }}
                />
              ))}
            </div>
            <div className="bar-days">
              {etc.map((_, i) => (
                <span key={`day-${i}`} className="muted small">
                  {weekdayOf(dates[i], i)}
                </span>
              ))}
            </div>
          </div>
          <div className="bar-legend">
            <span><i className="swatch" style={{ background: "var(--accent)" }} /> Bedarf (mm/Tag)</span>
            <span><i className="swatch rain-swatch" /> Regen (mm/Tag)</span>
          </div>

          <p className="muted small">
            Kcb {kcb != null ? kcb.toLocaleString("de-DE") : "–"} · Stand {canopyDate ?? "–"}
            {age != null ? ` (${age} Tage alt)` : ""}
            {status === "partial" ? " · Vorhersage unvollständig" : ""}
          </p>
        </>
      )}
      {flags.length > 0 && (
        <ul className="flags">
          {flags.map((flag) => (
            <li key={flag} className="flag">
              {FLAG_TEXT[flag] ?? flag}
            </li>
          ))}
        </ul>
      )}
      <p className="muted small">
        Bedarf, kein Verbrauch. Der Regen wird angezeigt, aber nicht vom Bedarf abgezogen.
      </p>
    </section>
  );
}
