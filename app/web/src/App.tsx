import { useCallback, useEffect, useState } from "react";
import { api, FieldSummary } from "./api";
import Map from "./Map";
import Timeline from "./Timeline";
import Demand from "./Demand";
import Method from "./Method";
import { Frame } from "./frames";

export default function App() {
  const [config, setConfig] = useState({ basemap: "local", state: "none", attribution: [] as string[] });
  const [fields, setFields] = useState<FieldSummary[]>([]);
  const [selected, setSelected] = useState<FieldSummary | null>(null);
  const [draft, setDraft] = useState<GeoJSON.Polygon | null>(null);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");
  const [frames, setFrames] = useState<Frame[]>([]);
  const [demand, setDemand] = useState<Record<string, unknown>>({ status: "unavailable" });
  const [index, setIndex] = useState(0);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [running, setRunning] = useState(false);
  const [jobError, setJobError] = useState("");

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

  const loadResults = async (id: number) => {
    const [fr, dm] = await Promise.all([api.frames(id), api.demand(id)]);
    setFrames(fr.frames);
    setDemand(dm);
    setIndex(0);
    setT(0);
  };

  const analyse = async (id: number) => {
    setJobError("");
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
        if (cancelled || st.running) return;
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
    }, 3000);
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
        <span className="muted">{config.state === "none" ? "kein Bundesland" : config.state}</span>
        <button onClick={save} disabled={!draft} title={draft ? "Feld speichern" : "Zuerst ein Polygon zeichnen"}>
          Speichern
        </button>
      </header>
      <main>
        <Map
          basemap={config.basemap}
          geometry={draft ?? (selected?.geometry as GeoJSON.Polygon | undefined) ?? null}
          onPoint={pick}
          onPolygon={(g) => { setDraft(g); setHint(""); }}
        />
        <aside className="side">
          <h3>Felder</h3>
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
            <section>
              <button onClick={() => analyse(selected.id)} disabled={running}>
                {running ? "Analyse laeuft…" : "Satelliten-Analyse starten"}
              </button>
              {running && (
                <p className="muted">
                  Sentinel-2 der letzten 12 Monate wird geladen. Beim ersten Mal
                  2-6 Minuten, danach aus dem Cache.
                </p>
              )}
              {jobError && <p className="flag">Analyse fehlgeschlagen: {jobError}</p>}
              {!running && frames.length === 0 && !jobError && (
                <p className="muted">
                  Noch keine Aufnahmen: „Satelliten-Analyse starten" klicken.
                </p>
              )}
            </section>
          )}

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
