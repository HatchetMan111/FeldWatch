import { useCallback, useEffect, useMemo, useState } from "react";
import { Anomaly, api, DemandPayload, errMsg, FieldSummary, SeriesPoint } from "./api";
import Map from "./Map";
import Timeline from "./Timeline";
import Demand from "./Demand";
import Weather from "./Weather";
import Method from "./Method";
import Series from "./Series";
import FieldList from "./FieldList";
import Anomalies from "./Anomalies";
import { Frame } from "./frames";

export function formatHa(areaM2: number): string {
  const ha = areaM2 / 10000;
  return `${ha.toLocaleString("de-DE", { maximumFractionDigits: 2 })} ha`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("de-DE");
}

export default function App() {
  const [config, setConfig] = useState({ basemap: "local", state: "none", attribution: [] as string[] });
  const [fields, setFields] = useState<FieldSummary[]>([]);
  const [selected, setSelected] = useState<FieldSummary | null>(null);
  const [draft, setDraft] = useState<GeoJSON.Polygon | GeoJSON.MultiPolygon | null>(null);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [frames, setFrames] = useState<Frame[]>([]);
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [demand, setDemand] = useState<DemandPayload>({ status: "unavailable" });
  const [pos, setPos] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [jobError, setJobError] = useState("");
  const [query, setQuery] = useState("");
  const [place, setPlace] = useState("");
  const [focus, setFocus] = useState<{ lon: number; lat: number } | null>(null);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);

  const index = Math.floor(pos);
  const t = pos - index;

  useEffect(() => {
    api.config().then(setConfig).catch((e) => setError(errMsg(e)));
    api.fields()
      .then((r) => setFields(r.fields))
      .catch((e) => setError(errMsg(e)));
  }, []);

  const pick = useCallback(async (lon: number, lat: number) => {
    setError("");
    try {
      const hit = await api.resolve(lat, lon);
      if (hit.found && hit.geometry) {
        setDraft(hit.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon);
        setNewName("");
        setHint("");
      } else {
        setHint('Kein Feldblock gefunden. Nutze „Feld zeichnen" und setze mindestens 3 Punkte.');
      }
    } catch (e) {
      setError(errMsg(e));
    }
  }, []);

  const doSearch = async (event: React.FormEvent) => {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setError("");
    try {
      const hit = await api.geocode(query.trim());
      if (hit.found && hit.lon != null && hit.lat != null) {
        setFocus({ lon: hit.lon, lat: hit.lat });
        setPlace(hit.label ?? "");
      } else {
        setPlace("Nichts gefunden – Ort oder PLZ anders versuchen");
      }
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const loadResults = async (id: number) => {
    const [fr, dm, se] = await Promise.all([api.frames(id), api.demand(id), api.series(id)]);
    setFrames(fr.frames);
    setDemand(dm);
    setSeries(se.series);
    setAnomalies(se.anomalies);
    setPos(0);
    setPlaying(false);
  };

  const analyse = async (id: number) => {
    setJobError("");
    setProgress({ done: 0, total: 0 });
    setRunning(true);
    try {
      await api.refresh(id);
    } catch (e) {
      setJobError(errMsg(e));
      setRunning(false);
    }
  };

  useEffect(() => {
    if (!running || !selected) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const st = await api.status(selected.id);
        if (cancelled) return;
        setProgress({ done: st.done, total: st.total });
        if (st.running) return;
        window.clearInterval(timer);
        setRunning(false);
        if (st.error) {
          setJobError(st.error);
        } else {
          await loadResults(selected.id);
        }
      } catch (e) {
        setJobError(errMsg(e));
      }
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, selected]);

  const draftIsNew =
    draft != null &&
    (selected == null || JSON.stringify(draft) !== JSON.stringify(selected.geometry));

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!draft || saving) return;
    const name = newName.trim() || `Feld ${fields.length + 1}`;
    setSaving(true);
    setError("");
    try {
      const { id } = await api.create(name, draft);
      const list = await api.fields();
      setFields(list.fields);
      setDraft(null);
      setNewName("");
      setHint("");
      const created = list.fields.find((f) => f.id === id) ?? null;
      setSelected(created);
      setFrames([]);
      setSeries([]);
      setAnomalies([]);
      setDemand({ status: "unavailable" });
      if (created) await analyse(id);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  const select = async (f: FieldSummary) => {
    setSelected(f);
    setDraft(f.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon);
    setJobError("");
    setError("");
    try {
      const st = await api.status(f.id);
      if (st.running) {
        setRunning(true);
        setProgress({ done: st.done, total: st.total });
      } else {
        setRunning(false);
        await loadResults(f.id);
      }
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const rename = async (id: number, name: string) => {
    setError("");
    try {
      const updated = await api.rename(id, name);
      setFields((list) => list.map((f) => (f.id === id ? { ...f, ...updated } : f)));
      if (selected?.id === id) setSelected((s) => (s ? { ...s, ...updated } : s));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const remove = async (f: FieldSummary) => {
    if (!window.confirm(`„${f.name}" wirklich löschen? Alle Aufnahmen gehen verloren.`)) return;
    setError("");
    try {
      await api.remove(f.id);
      const list = await api.fields();
      setFields(list.fields);
      if (selected?.id === f.id) {
        setSelected(null);
        setDraft(null);
        setFrames([]);
        setSeries([]);
        setAnomalies([]);
        setDemand({ status: "unavailable" });
        setPlaying(false);
        setRunning(false);
      }
    } catch (e) {
      setError(errMsg(e));
    }
  };

  useEffect(() => {
    if (!playing || frames.length < 2) return;
    const timer = window.setInterval(() => {
      setPos((p) => (p + 0.05 >= frames.length - 1 ? 0 : p + 0.05));
    }, 120);
    return () => window.clearInterval(timer);
  }, [playing, frames.length]);

  const fieldsSorted = useMemo(
    () => [...fields].sort((a, b) => a.name.localeCompare(b.name, "de")),
    [fields]
  );

  return (
    <div className="app">
      <header>
        <div className="brand">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="7" fill="var(--accent)" />
            <path
              d="M16 25V13M16 13c0-4 3-6 7-6 0 4-3 6-7 6Zm0 0c0-4-3-6-7-6 0 4 3 6 7 6Z"
              stroke="#07120a"
              strokeWidth="2.4"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
          <strong>FieldWatch</strong>
        </div>
        <form className="search" onSubmit={doSearch}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="PLZ, Ort oder Adresse suchen…"
            aria-label="PLZ, Ort oder Adresse"
          />
          <button type="submit">Suchen</button>
        </form>
        <span className="chip">{config.state === "none" ? "kein Bundesland" : config.state}</span>
      </header>
      <main>
        <Map
          basemap={config.basemap}
          geometry={
            draft ??
            ((selected?.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon | undefined) ?? null)
          }
          focus={focus}
          onPoint={pick}
          onPolygon={(g) => {
            setDraft(g);
            setNewName("");
            setHint("");
          }}
        />
        <aside className="side">
          {error && (
            <p className="flag banner" role="alert">
              {error}
            </p>
          )}

          <section className="side-block">
            <h3>Meine Felder</h3>
            {place && <p className="muted">{place}</p>}
            {fields.length === 0 && !draft && (
              <p className="muted">
                Noch kein Feld angelegt. Auf der Karte <strong>„Feld zeichnen"</strong> wählen,
                mindestens 3 Punkte um dein Feld setzen, dann unten speichern.
              </p>
            )}
            {hint && <p className="muted">{hint}</p>}
            <FieldList
              fields={fieldsSorted}
              selectedId={selected?.id ?? null}
              onSelect={select}
              onRename={rename}
              onDelete={remove}
            />
          </section>

          {draft && draftIsNew && (
            <form className="card save-card" onSubmit={save}>
              <h3>Feld speichern</h3>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder={`Feld ${fields.length + 1}`}
                aria-label="Feldname"
                maxLength={120}
              />
              <button type="submit" disabled={saving}>
                {saving ? "Speichert…" : "Speichern & analysieren"}
              </button>
              <button type="button" className="ghost discard" onClick={() => setDraft(null)}>
                Verwerfen
              </button>
            </form>
          )}

          {selected && (
            <section className="card">
              <div className="card-head">
                <h3>{selected.name}</h3>
                <span className="muted">{formatHa(selected.area_m2)}</span>
              </div>
              {selected.last_obs && (
                <p className="muted small">
                  Letzte Aufnahme: {formatDate(selected.last_obs)} · {selected.obs_count} Szenen
                </p>
              )}
              <button onClick={() => analyse(selected.id)} disabled={running}>
                {running ? "Analyse läuft…" : "Satelliten-Analyse starten"}
              </button>
              {running && (
                <div className="progress">
                  <div
                    className="progress-bar"
                    style={{
                      width: progress.total > 0 ? `${(progress.done / progress.total) * 100}%` : "12%",
                    }}
                  />
                </div>
              )}
              {running && (
                <p className="muted small">
                  {progress.total > 0
                    ? `Szenen ${progress.done}/${progress.total} gelesen`
                    : "Sentinel-2 wird gesucht…"}
                  {" · "}beim ersten Mal 2–6 Minuten, bitte Fenster offen lassen
                </p>
              )}
              {jobError && <p className="flag">Analyse fehlgeschlagen: {jobError}</p>}
              {!running && frames.length === 0 && !jobError && (
                <p className="muted">Noch keine Aufnahmen: Analyse starten.</p>
              )}
            </section>
          )}

          {anomalies.length > 0 && <Anomalies items={anomalies} />}
          {selected && <Series series={series} />}
          {selected && <Demand payload={demand} />}
          {selected && <Weather payload={demand} />}
          <Method />
        </aside>
      </main>
      <Timeline
        frames={frames}
        index={Math.min(index, Math.max(frames.length - 1, 0))}
        t={t}
        onChange={(i, tt) => {
          setPos(i + tt);
          setPlaying(false);
        }}
        playing={playing}
        onToggle={() => setPlaying((p) => !p)}
      />
      <footer>{config.attribution.join(" · ")}</footer>
    </div>
  );
}
