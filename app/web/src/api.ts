export interface FieldSummary {
  id: number;
  name: string;
  area_m2: number;
  state: string;
  geometry: { type: string; coordinates: unknown };
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => json<{ basemap: string; state: string; attribution: string[] }>("/api/config"),
  states: () => json<{ states: Array<{ code: string; name: string; status: string }> }>("/api/states"),
  fields: () => json<{ fields: FieldSummary[] }>("/api/fields"),
  field: (id: number) => json<FieldSummary>(`/api/fields/${id}`),
  frames: (id: number) =>
    json<{ frames: Array<{ date: string; width: number; height: number; data: string }> }>(
      `/api/fields/${id}/frames`
    ),
  demand: (id: number) => json<Record<string, unknown>>(`/api/fields/${id}/demand`),
  series: (id: number) =>
    json<{ series: Array<{ date: string; median_ndvi: number | null; clear_pct: number }> }>(
      `/api/fields/${id}/series`
    ),
  resolve: (lat: number, lon: number) =>
    json<{ found: boolean; geometry?: unknown; name?: string }>(
      `/api/resolve?lat=${lat}&lon=${lon}`
    ),
  create: (name: string, geometry: unknown) =>
    json<{ id: number }>("/api/fields", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, geometry }),
    }),
  refresh: (id: number) =>
    json<{ status: string }>(`/api/fields/${id}/refresh`, { method: "POST" }),
  status: (id: number) =>
    json<{ running: boolean; error: string | null; observations: number }>(
      `/api/fields/${id}/status`
    ),
};
