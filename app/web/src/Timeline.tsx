import { useEffect, useRef } from "react";
import { Frame, decodeFrame, interpolate, positionFor, ramp } from "./frames";

interface Props {
  frames: Frame[];
  index: number;
  t: number;
  onChange: (index: number, t: number) => void;
  playing: boolean;
  onToggle: () => void;
}

export default function Timeline({ frames, index, t, onChange, playing, onToggle }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    if (!el || frames.length === 0) return;
    const current = frames[Math.min(index, frames.length - 1)];
    const next = frames[Math.min(index + 1, frames.length - 1)];
    const a = decodeFrame(current);
    const b = decodeFrame(next);
    const pixels = interpolate(a, b, t);
    const ctx = el.getContext("2d");
    if (!ctx) return;
    el.width = current.width;
    el.height = current.height;
    const image = ctx.createImageData(current.width, current.height);
    for (let i = 0; i < pixels.length; i += 1) {
      const [r, g, bl, al] = ramp(pixels[i]);
      image.data[i * 4] = r;
      image.data[i * 4 + 1] = g;
      image.data[i * 4 + 2] = bl;
      image.data[i * 4 + 3] = al;
    }
    ctx.putImageData(image, 0, 0);
  }, [frames, index, t]);

  if (frames.length === 0) {
    return (
      <div className="timeline empty">
        <span className="muted">
          Noch keine Aufnahmen. Erst ein Feld speichern, dann „Satelliten-Analyse starten".
        </span>
      </div>
    );
  }

  const current = frames[Math.min(index, frames.length - 1)];
  const shownDate = index < frames.length - 1 && t > 0 ? positionFor(frames, index, t) : current.date;

  return (
    <div className="timeline">
      <canvas ref={canvas} className="timeline-canvas" />
      <div className="timeline-info">
        <div className="big">{shownDate}</div>
        <div className="muted">
          {frames.length} Aufnahmen · {index + 1}/{frames.length}
        </div>
        <div className="legend" aria-hidden="true">
          <span className="muted small">karg</span>
          <span className="legend-scale" />
          <span className="muted small">dicht</span>
        </div>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(frames.length - 1, 0)}
        step={0.05}
        value={index + t}
        className="timeline-slider"
        aria-label="Zeitachse"
        onChange={(e) => {
          const v = Number(e.target.value);
          onChange(Math.floor(v), v - Math.floor(v));
        }}
      />
      <button className="play-btn" onClick={onToggle} aria-label={playing ? "Pause" : "Abspielen"}>
        {playing ? "❚❚" : "▶"}
      </button>
    </div>
  );
}
