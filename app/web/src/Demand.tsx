interface Props {
  payload: Record<string, unknown>;
}

export default function Demand({ payload }: Props) {
  const etc = (payload.etc_mm as Array<number | null> | undefined) ?? [];
  const weekMm = payload.week_mm as number | null | undefined;
  const weekM3 = payload.week_m3 as number | null | undefined;
  const status = (payload.status as string) ?? "unavailable";
  const flags = (payload.flags as string[] | undefined) ?? [];

  return (
    <section>
      <h3>Wasserbedarf 7 Tage</h3>
      {status === "unavailable" ? (
        <p className="muted">
          Keine belastbare Berechnung{payload.reason ? ` (${String(payload.reason)})` : ""}.
        </p>
      ) : (
        <>
          <div className="big">{weekMm?.toFixed(1)} mm</div>
          <div className="muted">{weekM3?.toFixed(0)} m³ · Kcb {String(payload.kcb ?? "–")}</div>
          <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 80, marginTop: 12 }}>
            {etc.map((v, i) => (
              <div
                key={i}
                title={`Tag ${i + 1}: ${v ?? "–"} mm`}
                style={{
                  flex: 1,
                  height: `${Math.min(100, ((v ?? 0) / Math.max(1, ...etc.map((x) => x ?? 0))) * 100)}%`,
                  background: v === null ? "#4a2f2f" : "var(--accent)",
                  borderRadius: 3,
                }}
              />
            ))}
          </div>
        </>
      )}
      <p className="muted">
        Bedarf, kein Verbrauch. Regen wird angezeigt, aber nicht abgezogen.
      </p>
      {flags.length > 0 && <p className="flag">Hinweise: {flags.join(", ")}</p>}
    </section>
  );
}
