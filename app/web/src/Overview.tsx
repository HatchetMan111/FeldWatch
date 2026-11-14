import { FieldOverview } from "./api";
import { formatDateOnly, parseDateOnly } from "./dates";
import { formatDate, formatHa } from "./App";

interface Props {
  fields: FieldOverview[];
  selectedId: number | null;
  runningId: number | null;
  progress: { done: number; total: number };
  onOpen: (id: number) => void;
  onRerun: (id: number) => void;
  onDelete: (field: FieldOverview) => void;
}

const STALE_DAYS = 21;

function relativeDays(iso: string | null | undefined): string {
  const parsed = parseDateOnly(iso);
  if (!parsed) return "";
  const days = Math.floor((Date.now() - parsed.getTime()) / 86_400_000);
  if (days <= 0) return "heute";
  if (days === 1) return "gestern";
  return `vor ${days} Tagen`;
}

function ndviClass(ndvi: number): string {
  if (ndvi < 0.2) return "ndvi-low";
  if (ndvi < 0.45) return "ndvi-mid";
  if (ndvi < 0.7) return "ndvi-high";
  return "ndvi-full";
}

export default function Overview({
  fields,
  selectedId,
  runningId,
  progress,
  onOpen,
  onRerun,
  onDelete,
}: Props) {
  if (fields.length === 0) {
    return (
      <div className="overview">
        <div className="card overview-empty">
          <h3>Noch keine Felder</h3>
          <p className="muted">
            Wechsle zur Karte, zeichne dein Feld (mindestens 3 Punkte) oder tippe auf einen
            Feldblock, und speichere es. Danach erscheint es hier mit allen Werten.
          </p>
        </div>
      </div>
    );
  }

  const sorted = [...fields].sort((a, b) => a.name.localeCompare(b.name, "de"));

  return (
    <div className="overview">
      <div className="overview-head">
        <h2>Meine Felder ({fields.length})</h2>
        <span className="muted small">
          Analyse pro Feld: Satellitenbilder der letzten 24 Monate auswerten, danach Wasserbedarf
          und Wetter für die nächsten 7 Tage.
        </span>
      </div>
      <div className="ov-grid">
        {sorted.map((f) => {
          const running = runningId === f.id;
          const ndvi = f.last_ndvi;
          const demand = f.demand;
          const stale =
            demand?.canopy_age_days != null && demand.canopy_age_days > STALE_DAYS;
          return (
            <div key={f.id} className={`card ov-card${f.id === selectedId ? " active" : ""}`}>
              <div className="card-head">
                <h3>{f.name}</h3>
                <span className="muted">{formatHa(f.area_m2)}</span>
              </div>
              <p className="muted small ov-line">
                {f.last_obs ? (
                  <>
                    Letzte Aufnahme: {formatDate(f.last_obs)} ({relativeDays(f.last_obs)}) ·{" "}
                    {f.obs_count} Szenen
                  </>
                ) : (
                  "noch nicht analysiert"
                )}
              </p>
              <div className="ov-stats">
                {ndvi != null && (
                  <span className={`ov-chip ${ndviClass(ndvi)}`} title="NDVI der letzten Aufnahme">
                    NDVI {ndvi.toLocaleString("de-DE", { maximumFractionDigits: 2 })}
                  </span>
                )}
                {demand?.cover != null && (
                  <span className="ov-chip" title="Bewachsung aus letzter Aufnahme">
                    {(demand.cover * 100).toLocaleString("de-DE", { maximumFractionDigits: 0 })} %
                    Bewuchs
                  </span>
                )}
                {demand?.week_mm != null && (
                  <span className="ov-chip" title="Wasserbedarf der nächsten 7 Tage">
                    {demand.week_mm.toLocaleString("de-DE", { maximumFractionDigits: 1 })} mm
                    Bedarf/Woche
                  </span>
                )}
                {demand?.balance_mm != null && (
                  <span
                    className={`ov-chip${demand.balance_mm >= 0 ? " good" : " warn"}`}
                    title="Regen minus Bedarf (7 Tage)"
                  >
                    Bilanz {demand.balance_mm > 0 ? "+" : ""}
                    {demand.balance_mm.toLocaleString("de-DE", { maximumFractionDigits: 1 })} mm
                  </span>
                )}
                {stale && (
                  <span className="ov-chip warn" title="Letzte klare Aufnahme älter als 21 Tage">
                    veraltet ({demand?.canopy_age_days} Tage)
                  </span>
                )}
                {demand?.status === "partial" && (
                  <span className="ov-chip warn">Vorhersage unvollständig</span>
                )}
              </div>
              {running && (
                <div className="ov-running">
                  <div className="progress">
                    <div
                      className="progress-bar"
                      style={{
                        width:
                          progress.total > 0
                            ? `${(progress.done / progress.total) * 100}%`
                            : "12%",
                      }}
                    />
                  </div>
                  <span className="muted small">
                    {progress.total > 0
                      ? `Szenen ${progress.done}/${progress.total} gelesen`
                      : "Sentinel-2 wird gesucht…"}
                  </span>
                </div>
              )}
              <div className="ov-actions">
                <button onClick={() => onRerun(f.id)} disabled={running}>
                  {running ? "Analyse läuft…" : f.last_obs ? "↻ Analyse erneut" : "↻ Analyse starten"}
                </button>
                <button className="ghost" onClick={() => onOpen(f.id)}>
                  Auf Karte öffnen
                </button>
                <button
                  className="icon-btn danger ov-delete"
                  title={`${f.name} löschen`}
                  aria-label={`${f.name} löschen`}
                  onClick={() => onDelete(f)}
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <p className="muted small">
        „Analyse erneut" holt aktuelle Sentinel-2-Szenen und die frische Wetterprognose — bestehende
        Aufnahmen bleiben erhalten, Kartenansicht öffnet das Feld mit Verlauf und Zeitachse.
      </p>
    </div>
  );
}
