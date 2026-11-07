import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { draftData, fieldData } from "./draft";

type LayerKind = "satellite" | "osm" | "dark";

const LAYER_STORAGE_KEY = "fieldwatch.layer";

interface Props {
  basemap: string;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
  focus: { lon: number; lat: number } | null;
  onPoint: (lon: number, lat: number) => void;
  onPolygon: (geometry: GeoJSON.Polygon) => void;
}

function styleFor(layer: LayerKind): StyleSpecification {
  if (layer === "osm") {
    return {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap-Mitwirkende",
        },
      },
      layers: [{ id: "osm", type: "raster", source: "osm" }],
    };
  }
  if (layer === "satellite") {
    return {
      version: 8,
      sources: {
        esri: {
          type: "raster",
          tiles: [
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          ],
          tileSize: 256,
          maxzoom: 19,
          attribution: "Luftbilder © Esri, Maxar, Earthstar Geographics",
        },
      },
      layers: [{ id: "esri", type: "raster", source: "esri" }],
    };
  }
  return {
    version: 8,
    sources: {},
    layers: [{ id: "bg", type: "background", paint: { "background-color": "#141a17" } }],
  };
}

/** Umriss eines Polygons/MultiPolygons für fitBounds. */
function boundsOf(
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
): maplibregl.LngLatBoundsLike | null {
  if (!geometry) return null;
  const rings =
    geometry.type === "MultiPolygon" ? geometry.coordinates.flat() : geometry.coordinates;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const ring of rings) {
    for (const [x, y] of ring) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  if (!Number.isFinite(minX)) return null;
  return [
    [minX, minY],
    [maxX, maxY],
  ];
}

export default function Map({ basemap, geometry, focus, onPoint, onPolygon }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [layer, setLayer] = useState<LayerKind>(() => {
    const stored = window.localStorage.getItem(LAYER_STORAGE_KEY);
    if (stored === "satellite" || stored === "osm" || stored === "dark") return stored;
    return basemap === "osm" ? "osm" : "satellite";
  });
  const [drawing, setDrawing] = useState(false);
  const [points, setPoints] = useState<[number, number][]>([]);
  const drawingRef = useRef(false);
  const pointsRef = useRef<[number, number][]>([]);
  const geometryRef = useRef<GeoJSON.Polygon | GeoJSON.MultiPolygon | null>(geometry);
  const onPointRef = useRef(onPoint);
  const onPolygonRef = useRef(onPolygon);

  drawingRef.current = drawing;
  pointsRef.current = points;
  geometryRef.current = geometry;
  onPointRef.current = onPoint;
  onPolygonRef.current = onPolygon;

  useEffect(() => {
    // Installer-Default (osm) respektieren, solange der Nutzer nicht gewählt hat.
    if (basemap === "osm" && !window.localStorage.getItem(LAYER_STORAGE_KEY)) {
      setLayer("osm");
    }
  }, [basemap]);

  const chooseLayer = (kind: LayerKind) => {
    setLayer(kind);
    window.localStorage.setItem(LAYER_STORAGE_KEY, kind);
  };

  useEffect(() => {
    if (!container.current || map.current) return;
    const style = styleFor(layer);

    const instance = new maplibregl.Map({
      container: container.current,
      style,
      center: [10.0, 51.2],
      zoom: 5.4,
    });
    instance.addControl(new maplibregl.NavigationControl(), "top-left");
    instance.on("load", () => {
      instance.resize();
      instance.addSource("field", { type: "geojson", data: fieldData(geometryRef.current) });
      instance.addLayer({
        id: "field-fill",
        type: "fill",
        source: "field",
        paint: { "fill-color": "#7fd48b", "fill-opacity": 0.25 },
      });
      instance.addLayer({
        id: "field-line",
        type: "line",
        source: "field",
        paint: { "line-color": "#aef0b4", "line-width": 2.5 },
      });
      instance.addSource("draft", { type: "geojson", data: draftData(pointsRef.current) });
      instance.addLayer({
        id: "draft-line",
        type: "line",
        source: "draft",
        filter: ["==", "$type", "LineString"],
        paint: { "line-color": "#f0b45a", "line-width": 2.5, "line-dasharray": [2, 1.2] },
      });
      instance.addLayer({
        id: "draft-points",
        type: "circle",
        source: "draft",
        filter: ["==", "$type", "Point"],
        paint: {
          "circle-radius": 6,
          "circle-color": "#f0b45a",
          "circle-stroke-color": "#0f1210",
          "circle-stroke-width": 2,
        },
      });
    });

    const click = (event: maplibregl.MapMouseEvent) => {
      if (!drawingRef.current) {
        onPointRef.current(event.lngLat.lng, event.lngLat.lat);
        return;
      }
      setPoints([...pointsRef.current, [event.lngLat.lng, event.lngLat.lat]]);
    };
    instance.on("click", click);

    // MapLibres eingebautes trackResize basiert auf ResizeObserver und läuft
    // nicht überall (z. B. eingebettete Panes ohne RO-Feuer). Ohne Nachziehen
    // bleibt die Canvas auf ihrer Konstruktionsgröße stehen.
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(container.current);

    // Fallback: Größe per window-resize und Polling gegenziehen, falls der
    // ResizeObserver still bleibt. resize() kostet nichts, solange die
    // Containergröße unverändert ist.
    let lastW = container.current.clientWidth;
    let lastH = container.current.clientHeight;
    const syncSize = () => {
      const el = container.current;
      if (!el) return;
      if (el.clientWidth !== lastW || el.clientHeight !== lastH) {
        lastW = el.clientWidth;
        lastH = el.clientHeight;
        instance.resize();
      }
    };
    window.addEventListener("resize", syncSize);
    const sizePoll = window.setInterval(syncSize, 400);

    map.current = instance;
    return () => {
      window.clearInterval(sizePoll);
      window.removeEventListener("resize", syncSize);
      observer.disconnect();
      instance.off("click", click);
      instance.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layer]);

  useEffect(() => {
    const instance = map.current;
    const source = instance?.getSource("field") as maplibregl.GeoJSONSource | undefined;
    source?.setData(fieldData(geometry));
  }, [geometry]);

  // Bei jeder neuen Geometrie aufs Feld zoomen (Auswahl, Import, Zeichnen fertig).
  useEffect(() => {
    const instance = map.current;
    const bounds = boundsOf(geometry);
    if (!instance || !bounds) return;
    const fit = () => {
      try {
        instance.fitBounds(bounds, { padding: 60, maxZoom: 16, duration: 800 });
      } catch {
        /* Karte noch nicht bereit */
      }
    };
    if (instance.isStyleLoaded()) fit();
    else instance.once("load", fit);
  }, [geometry]);

  useEffect(() => {
    if (!focus || !map.current) return;
    map.current.flyTo({ center: [focus.lon, focus.lat], zoom: 14, duration: 900 });
  }, [focus]);

  useEffect(() => {
    const instance = map.current;
    const source = instance?.getSource("draft") as maplibregl.GeoJSONSource | undefined;
    source?.setData(draftData(points));
    instance?.getCanvas().style.setProperty("cursor", drawing ? "crosshair" : "");
  }, [points, drawing]);

  useEffect(() => {
    if (!drawing) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPoints([]);
        setDrawing(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawing]);

  const finish = () => {
    const ring = pointsRef.current;
    if (ring.length < 3) return;
    onPolygonRef.current({ type: "Polygon", coordinates: [[...ring, ring[0]]] });
    setPoints([]);
    setDrawing(false);
  };

  return (
    <div className="map">
      <div ref={container} style={{ position: "absolute", inset: 0 }} />

      <div className="map-layers" role="group" aria-label="Kartenhintergrund">
        {(
          [
            ["satellite", "Luftbild"],
            ["osm", "Karte"],
            ["dark", "Nacht"],
          ] as Array<[LayerKind, string]>
        ).map(([kind, label]) => (
          <button
            key={kind}
            className={layer === kind ? "layer-btn active" : "layer-btn"}
            onClick={() => chooseLayer(kind)}
          >
            {label}
          </button>
        ))}
      </div>

      {!drawing ? (
        <button
          className="draw-btn"
          onClick={() => {
            setPoints([]);
            setDrawing(true);
          }}
        >
          + Feld zeichnen
        </button>
      ) : (
        <div className="draw-panel">
          <div className="hint">
            Punkte: <strong>{points.length}</strong>
            <br />
            Auf die Karte klicken, mindestens 3 Punkte um das Feld setzen. Ein Klick auf den
            letzten Punkt beendet nicht – „Fertig" drücken.
          </div>
          <div className="row">
            <button onClick={finish} disabled={points.length < 3}>
              Fertig
            </button>
            <button
              className="ghost"
              onClick={() => setPoints((p) => p.slice(0, -1))}
              disabled={points.length === 0}
            >
              Zurück
            </button>
          </div>
          <button
            className="ghost"
            onClick={() => {
              setPoints([]);
              setDrawing(false);
            }}
          >
            Abbrechen (Esc)
          </button>
        </div>
      )}

      {layer === "dark" && !drawing && (
        <div className="map-note">
          Nacht-Ansicht ohne Kartenbild. Über „Luftbild" oben rechts siehst du echte
          Luftbilder deines Landes.
        </div>
      )}
    </div>
  );
}
