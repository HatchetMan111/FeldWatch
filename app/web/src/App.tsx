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
  const [frames, setFrames] = useState<Frame[]>([]);
  const [demand, setDemand] = useState<Record<string, unknown>>({ status: "unavailable" });
  const [index, setIndex] = useState(0);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);

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
      }
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const save = async () => {
    if (!draft) return;
    const name = window.prompt("Feldname", "Feld") ?? "Feld";
    try {
      const { id } = await api.create(name, draft);
      const list = await api.fields();
      setFields(list.fields);
      setSelected(list.fields.find((f) => f.id === id) ?? null);
    } catch (e) {
      setError(String(e));
    }
  };

  const select = async (f: FieldSummary) => {
    setSelected(f);
    setDraft(f.geometry as GeoJSON.Polygon);
    const [fr, dm] = await Promise.all([api.frames(f.id), api.demand(f.id)]);
    setFrames(fr.frames);
    setDemand(dm);
    setIndex(0);
    setT(0);
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
        <button onClick={save} disabled={!draft}>Feld speichern</button>
      </header>
      <main>
        <Map
          basemap={config.basemap}
          geometry={draft ?? (selected?.geometry as GeoJSON.Polygon | undefined) ?? null}
          onPoint={pick}
          onPolygon={setDraft}
        />
        <aside className="side">
          <h3>Felder</h3>
          {fields.length === 0 && <p className="muted">Noch kein Feld. Auf die Karte tippen oder zeichnen.</p>}
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
