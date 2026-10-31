const FLAG_TEXT: Record<string, string> = {
  stale_canopy: "Letzte klare Aufnahme ist aelter als 21 Tage.",
  insufficient_pixels: "Feld zu klein fuer eine belastbare Statistik.",
  no_clear_observation: "Keine wolkenfreie Aufnahme im Zeitraum.",
};

interface Props {
  payload: Record<string, unknown>;
}

export default function Demand({ payload }: Props) {
  const etc = (payload.etc_mm as Array<number | null> | undefined) ?? [];
  const weekMm = payload.week_mm as number | null | undefined;
  const weekM3 = payload.week_m3 as number | null | undefined;
  const status = (payload.status as string) ?? "unavailable";
  const flags = ((payload.flags as string[] | undefined) ?? []).filter(Boolean);
  const cover = payload.cover as number | null | undefined;
  const kcb = payload.kcb as number | null | undefined;
  const canopyDate = payload.canopy_date as string | undefined;
  const age = payload.canopy_age_days as number | undefined;
  const max = Math.max(1, ...etc.map((v) => v ?? 0));

  return (
    <section className="card">
      <h3>Wasserbedarf 7 Tage</h3>
      {status === "unavailable" ? (
        <p className="muted">
          Keine belastbare Berechnung{payload.reason ? ` (${String(payload.reason)})` : ""}.
        </p>
      ) : (
        <>
          <div className="metrics">
            <div className="metric">
              <span className="metric-value">{weekMm?.toFixed(1) ?? "–"}</span>
              <span className="metric-unit">mm</span>
              <span className="metric-label">pro Woche</span>
            </div>
            <div className="metric">
              <span className="metric-value">{weekM3?.toFixed(0) ?? "–"}</span>
              <span className="metric-unit">m³</span>
              <span className="metric-label">auf der Flaeche</span>
            </div>
            <div className="metric">
              <span className="metric-value">{cover == null ? "–" : (cover * 100).toFixed(0)}</span>
              <span className="metric-unit">%</span>
              <span className="metric-label">Bodenbedeckung</span>
            </div>
          </div>

          <div className="bars">
            {etc.map((v, i) => (
              <div
                key={i}
                title={`Tag ${i + 1}: ${v ?? "–"} mm`}
                style={{
                  flex: 1,
                  height: `${Math.min(100, ((v ?? 0) / max) * 100)}%`,
                  background: v === null ? "#4a2f2f" : "var(--accent)",
                  borderRadius: 3,
                }}
              />
            ))}
          </div>

          <p className="muted">
            Kcb {kcb ?? "–"} · Stand {canopyDate ?? "–"}
            {age != null ? ` (${age} T. alt)` : ""}
            {status === "partial" ? " · Vorhersage unvollstaendig" : ""}
          </p>
        </>
      )}
      {flags.length > 0 && (
        <ul className="flags">
          {flags.map((flag) => (
            <li key={flag} className="flag">{FLAG_TEXT[flag] ?? flag}</li>
          ))}
        </ul>
      )}
      <p className="muted small">
        Bedarf, kein Verbrauch. Regen wird angezeigt, aber nicht abgezogen.
      </p>
    </section>
  );
}
