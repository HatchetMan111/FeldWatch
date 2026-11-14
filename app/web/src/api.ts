export interface FieldSummary {
  id: number;
  name: string;
  area_m2: number;
  state: string;
  last_obs: string | null;
  obs_count: number;
  geometry: { type: string; coordinates: unknown };
}

export interface DemandSummary {
  status?: string;
  reason?: string | null;
  week_mm?: number | null;
  balance_mm?: number | null;
  cover?: number | null;
  canopy_date?: string | null;
  canopy_age_days?: number | null;
  missing_days?: number | null;
}

export interface FieldOverview extends FieldSummary {
  last_ndvi: number | null;
  demand: DemandSummary | null;
}

export interface Anomaly {
  date: string;
  type: string;
  ndvi: number;
  baseline: number;
  delta: number;
  text?: string;
}

export interface SeriesPoint {
  date: string;
  median_ndvi: number | null;
  mean_ndvi: number | null;
  clear_pct: number;
  pixels: number;
  anomalies?: Anomaly[];
}

export interface DemandPayload {
  status: string;
  reason?: string;
  kcb?: number | null;
  etc_mm?: Array<number | null>;
  precip_mm?: Array<number | null>;
  dates?: string[];
  temp_max_c?: Array<number | null>;
  temp_min_c?: Array<number | null>;
  wind_max_kmh?: Array<number | null>;
  precip_prob_pct?: Array<number | null>;
  soil_temp_c?: Array<number | null>;
  week_mm?: number | null;
  week_m3?: number | null;
  balance_mm?: number | null;
  area_m2?: number;
  cover?: number | null;
  canopy_date?: string;
  canopy_age_days?: number;
  flags?: string[];
}

/** Deutsche, lesbare Meldung statt "[TypeError] Failed to fetch". */
export function errMsg(e: unknown): string {
  if (e instanceof Error) {
    const text = e.message.replace(/^Error:\s*/, "");
    if (/Failed to fetch|NetworkError|Load failed/i.test(text)) {
      return "Server nicht erreichbar. Läuft der FieldWatch-Dienst?";
    }
    if (/Server error|Bad Gateway|Gateway Time-?out|\b50[234]\b/.test(text)) {
      return "Sentinel-2- oder Wetterquelle kurz nicht erreichbar — bitte in wenigen Minuten erneut versuchen.";
    }
    return text || "Unbekannter Fehler";
  }
  return String(e);
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
  overview: () => json<{ fields: FieldOverview[] }>("/api/overview"),
  field: (id: number) => json<FieldSummary>(`/api/fields/${id}`),
  frames: (id: number) =>
    json<{ frames: Array<{ date: string; width: number; height: number; data: string }> }>(
      `/api/fields/${id}/frames`
    ),
  demand: (id: number) => json<DemandPayload>(`/api/fields/${id}/demand`),
  series: (id: number, months = 24) =>
    json<{ series: SeriesPoint[]; anomalies: Anomaly[] }>(
      `/api/fields/${id}/series?months=${months}`
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
  rename: (id: number, name: string) =>
    json<FieldSummary>(`/api/fields/${id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  remove: (id: number) => json<{ deleted: boolean }>(`/api/fields/${id}`, { method: "DELETE" }),
  refresh: (id: number) =>
    json<{ status: string }>(`/api/fields/${id}/refresh`, { method: "POST" }),
  status: (id: number) =>
    json<{ running: boolean; error: string | null; observations: number; done: number; total: number }>(
      `/api/fields/${id}/status`
    ),
  geocode: (q: string) =>
    json<{ found: boolean; label?: string; lon?: number; lat?: number }>(
      `/api/geocode?q=${encodeURIComponent(q)}`
    ),
};
