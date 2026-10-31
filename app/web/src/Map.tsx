import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { draftData, fieldData } from "./draft";

interface Props {
  basemap: string;
  geometry: GeoJSON.Polygon | null;
  focus: { lon: number; lat: number } | null;
  onPoint: (lon: number, lat: number) => void;
  onPolygon: (geometry: GeoJSON.Polygon) => void;
}

export default function Map({ basemap, geometry, focus, onPoint, onPolygon }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [points, setPoints] = useState<[number, number][]>([]);
  const drawingRef = useRef(false);
  const pointsRef = useRef<[number, number][]>([]);
  const geometryRef = useRef<GeoJSON.Polygon | null>(geometry);
  const onPointRef = useRef(onPoint);
  const onPolygonRef = useRef(onPolygon);

  drawingRef.current = drawing;
  pointsRef.current = points;
  geometryRef.current = geometry;
  onPointRef.current = onPoint;
  onPolygonRef.current = onPolygon;

  useEffect(() => {
    if (!container.current || map.current) return;
    const style: StyleSpecification =
      basemap === "osm"
        ? {
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
          }
        : {
            version: 8,
            sources: {},
            layers: [
              { id: "bg", type: "background", paint: { "background-color": "#141a17" } },
            ],
          };

    const instance = new maplibregl.Map({
      container: container.current,
      style,
      center: [10.0, 51.2],
      zoom: 5.4,
    });
    instance.addControl(new maplibregl.NavigationControl(), "top-left");
    instance.on("load", () => {
      instance.addSource("field", { type: "geojson", data: fieldData(geometryRef.current) });
      instance.addLayer({
        id: "field-fill",
        type: "fill",
        source: "field",
        paint: { "fill-color": "#7fd48b", "fill-opacity": 0.18 },
      });
      instance.addLayer({
        id: "field-line",
        type: "line",
        source: "field",
        paint: { "line-color": "#7fd48b", "line-width": 2 },
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

    map.current = instance;
    return () => {
      instance.off("click", click);
      instance.remove();
      map.current = null;
    };
  }, [basemap]);

  useEffect(() => {
    const instance = map.current;
    const source = instance?.getSource("field") as maplibregl.GeoJSONSource | undefined;
    source?.setData(fieldData(geometry));
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

      {!drawing ? (
        <button
          className="draw-btn"
          onClick={() => {
            setPoints([]);
            setDrawing(true);
          }}
        >
          Feld zeichnen
        </button>
      ) : (
        <div className="draw-panel">
          <div className="hint">
            Punkte: <strong>{points.length}</strong>
            <br />
            Auf die Karte klicken, mindestens 3 Punkte setzen, dann „Fertig".
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
            Abbrechen
          </button>
        </div>
      )}

      {basemap !== "osm" && !drawing && (
        <div className="map-note">
          Leere Basiskarte. Feld mit „Feld zeichnen" aufsetzen oder die App mit
          {" "}<code>--basemap osm</code> neu installieren.
        </div>
      )}
    </div>
  );
}
