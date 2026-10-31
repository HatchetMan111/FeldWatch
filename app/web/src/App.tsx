import { useCallback, useEffect, useState } from "react";
import { api, FieldSummary } from "./api";
import Map from "./Map";
import Timeline from "./Timeline";
import Demand from "./Demand";
import Method from "./Method";
import Series from "./Series";
import { Frame } from "./frames";

interface SeriesPoint {
  date: string;
  median_ndvi: number | null;
}

export default function App() {
  const [config, setConfig] = useState({ basemap: "local", state: "none", attribution: [] as string[] });
  const [fields, setFields] = useState<FieldSummary[]>([]);
  const [selected, setSelected] = useState<FieldSummary | null>(null);
  const [draft, setDraft] = useState<GeoJSON.Polygon | null>(null);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [frames, setFrames] = useState<Frame[]>([]);
  const [series, setSeries] = useState<SeriesPoint[]>([]);
  const [demand, setDemand] = useState<Record<string, unknown>>({ status: "unavailable" });
  const [index, setIndex] = useState(0);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [jobError, setJobError] = useState("");
  const [query, setQuery] = useState("");
  const [place, setPlace] = useState("");
  const [focus, setFocus] = useState<{ lon: number; lat: number } | null>(null);

  useEffect(() => {
    api.config().then(setConfig).catch((e) => setError(String(e)));
    api.fields().then((r) => setFields(r.fields)).catch((e) => setError(String(e)));
  }, []);

  const pick = useCallback(async (lon: number, lat: number) => {
    setError("");
    try {
      const hit = await api.resolve(lat, lon);
      if (hit.found && hit.geometry) {
        setDraft(hit.geometry as GeoJSON.Polygon);
        setHint("");
      } else {
        setHint('Kein Feldblock gefunden. Nutze „Feld zeichnen" und setze mindestens 3 Punkte.');
      }
    } catch (e) {
      setError(String(e));
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
        setPlace("Nichts gefunden");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const loadResults = async (id: number) => {
    const [fr, dm, se] = await Promise.all([api.frames(id), api.demand(id), api.series(id)]);
    setFrames(fr.frames);
    setDemand(dm);
    setSeries(se.series);
    setIndex(0);
    setT(0);
  };

  const analyse = async (id: number) => {
    setJobError("");
    setProgress({ done: 0, total: 0 });
    setRunning(true);
    try {
      await api.refresh(id);
    } catch (e) {
      setJobError(String(e));
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
        setJobError(String(e));
      }
    }, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [running, selected]);

  const save = async () => {
    if (!draft) return;
    const name = window.prompt("Feldname", "Feld") ?? "Feld";
    try {
      const { id } = await api.create(name, draft);
      const list = await api.fields();
      setFields(list.fields);
      const created = list.fields.find((f) => f.id === id) ?? null;
      setSelected(created);
      if (created) {
        setFrames([]);
        setSeries([]);
        setDemand({ status: "unavailable" });
        await analyse(id);
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const select = async (f: FieldSummary) => {
    setSelected(f);
    setDraft(f.geometry as GeoJSON.Polygon);
    setJobError("");
    try {
      await loadResults(f.id);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    if (!playing || frames.length < 2) return;
    const timer = window.setInterval(() => {
      setIndex((i) => {
        const next = i + 1;
        if (next >= frames.length - 1) {
          setT(0);
          return frames.length - 1;
        }
        return next;
      });
      setT((v) => (v >= 0.95 ? 0 : v + 0.05));
    }, 120);
    return () => window.clearInterval(timer);
  }, [playing, frames.length]);

  return (
    <div className="app">
      <header>
        <strong>FieldWatch</strong>
        <form className="search" onSubmit={doSearch}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="PLZ, Ort oder Adresse"
            aria-label="PLZ, Ort oder Adresse"
          />
          <button type="submit">Suchen</button>
        </form>
        <span className="muted">{config.state === "none" ? "kein Bundesland" : config.state}</span>
        <button onClick={save} disabled={!draft} title={draft ? "Feld speichern" : "Zuerst ein Polygon zeichnen"}>
          Speichern
        </button>
      </header>
      <main>
        <Map
          basemap={config.basemap}
          geometry={draft ?? (selected?.geometry as GeoJSON.Polygon | undefined) ?? null}
          focus={focus}
          onPoint={pick}
          onPolygon={(g) => { setDraft(g); setHint(""); }}
        />
        <aside className="side">
          <h3>Felder</h3>
          {place && <p className="muted">{place}</p>}
          {fields.length === 0 && (
            <p className="muted">
              Noch kein Feld. Oben rechts „Feld zeichnen" waehlen, mindestens 3 Punkte
              auf die Karte setzen, dann „Speichern".
            </p>
          )}
          {hint && <p className="muted">{hint}</p>}
          <ul>
            {fields.map((f) => (
              <li key={f.id}>
                <button className="ghost" onClick={() => select(f)}>
                  {f.name}
                </button>
                <span className="muted"> {Math.round(f.area_m2 / 10000)} ha</span>
              </li>
            ))}
          </ul>

          {selected && (
            <section className="card">
              <h3>{selected.name}</h3>
              <button onClick={() => analyse(selected.id)} disabled={running}>
                {running ? "Analyse laeuft…" : "Satelliten-Analyse starten"}
              </button>
              {running && (
                <p className="muted">
                  {progress.total > 0
                    ? `Szenen ${progress.done}/${progress.total} gelesen`
                    : "Sentinel-2 wird gesucht…"}
                  {" · "}beim ersten Mal 2-6 Minuten
                </p>
              )}
              {jobError && <p className="flag">Analyse fehlgeschlagen: {jobError}</p>}
              {!running && frames.length === 0 && !jobError && (
                <p className="muted">Noch keine Aufnahmen: „Satelliten-Analyse starten" klicken.</p>
              )}
            </section>
          )}

          {selected && <Series series={series} />}
          {selected && <Demand payload={demand} />}
          <Method />
          {error && <p className="flag">{error}</p>}
        </aside>
      </main>
      <Timeline
        frames={frames}
        index={index}
        t={t}
        onChange={(i, tt) => { setIndex(i); setT(tt); }}
        playing={playing}
        onToggle={() => setPlaying((p) => !p)}
      />
      <footer>{config.attribution.join(" · ")}</footer>
    </div>
  );
}
