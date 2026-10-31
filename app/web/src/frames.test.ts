import { describe, expect, it } from "vitest";
import { decodeFrame, interpolate, positionFor, ramp } from "./frames";

function frame(width: number, height: number, values: number[]) {
  return { date: "2026-01-01", width, height, data: btoa(String.fromCharCode(...values)) };
}

describe("frames", () => {
  it("decodes base64 into bytes", () => {
    const bytes = decodeFrame(frame(2, 1, [0, 128]));
    expect(Array.from(bytes)).toEqual([0, 128]);
  });

  it("interpolates linearly and keeps nodata", () => {
    const a = new Uint8Array([0, 100, 200]);
    const b = new Uint8Array([100, 200, 0]);
    expect(Array.from(interpolate(a, b, 0.5))).toEqual([50, 150, 0]);
    expect(Array.from(interpolate(a, b, 0))).toEqual([0, 100, 0]);
    expect(Array.from(interpolate(a, b, 1))).toEqual([100, 200, 0]);
  });

  it("maps values to a green ramp", () => {
    expect(ramp(0)[3]).toBe(0);
    expect(ramp(64)[1]).toBeLessThan(ramp(200)[1]);
  });

  it("positions a date between two frames", () => {
    const frames = [
      { date: "2026-01-01", width: 1, height: 1, data: "" },
      { date: "2026-03-01", width: 1, height: 1, data: "" },
    ];
    expect(positionFor(frames, 0, 0.5)).toBe("2026-01-30");
    expect(positionFor(frames, 1, 0)).toBe("2026-03-01");
  });
});
