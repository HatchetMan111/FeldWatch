export interface Frame {
  date: string;
  width: number;
  height: number;
  data: string;
}

export function decodeFrame(frame: Frame): Uint8Array {
  const binary = atob(frame.data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export function interpolate(a: Uint8Array, b: Uint8Array, t: number): Uint8Array {
  const out = new Uint8Array(a.length);
  const clamped = Math.min(Math.max(t, 0), 1);
  for (let i = 0; i < a.length; i += 1) {
    if (b[i] === 0) {
      out[i] = 0;
      continue;
    }
    out[i] = Math.round(a[i] + (b[i] - a[i]) * clamped);
  }
  return out;
}

const STOPS: Array<[number, [number, number, number, number]]> = [
  [0, [0, 0, 0, 0]],
  [1, [120, 90, 60, 255]],
  [64, [190, 120, 70, 255]],
  [128, [150, 190, 90, 255]],
  [192, [40, 140, 60, 255]],
  [255, [10, 80, 30, 255]],
];

export function ramp(value: number): [number, number, number, number] {
  for (let i = 1; i < STOPS.length; i += 1) {
    const [hi, high] = STOPS[i];
    const [lo, low] = STOPS[i - 1];
    if (value <= hi) {
      const f = (value - lo) / (hi - lo);
      return [
        Math.round(low[0] + (high[0] - low[0]) * f),
        Math.round(low[1] + (high[1] - low[1]) * f),
        Math.round(low[2] + (high[2] - low[2]) * f),
        Math.round(low[3] + (high[3] - low[3]) * f),
      ];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

export function positionFor(frames: Frame[], index: number, t: number): string {
  if (frames.length === 0) return "";
  const current = frames[Math.min(index, frames.length - 1)];
  if (index >= frames.length - 1) return current.date;
  const next = frames[index + 1];
  const start = Date.parse(current.date);
  const end = Date.parse(next.date);
  return new Date(start + (end - start) * Math.min(Math.max(t, 0), 1))
    .toISOString()
    .slice(0, 10);
}
