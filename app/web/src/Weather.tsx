import { DemandPayload } from "./api";
import { formatDateOnly, weekdayOf } from "./dates";

interface Props {
  payload: DemandPayload;
}

/** Faustregeln — keine Handlungsanweisung, Grenzwerte je Kultur/Mittel anders. */
const SPRAY_WIND_KMH = 20;
const SPRAY_PROB_PCT = 30;
const SOWING_WARM_C = 10;
const SOWING_COOL_C = 5;
const FROST_C = 0;

function num(v: number | null | undefined, digits = 0): string {
  return v == null ? "–" : v.toLocaleString("de-DE", { maximumFractionDigits: digits });
}

export default function Weather({ payload }: Props) {
  const dates = payload.dates ?? [];
  const tMin = payload.temp_min_c ?? [];
  const tMax = payload.temp_max_c ?? [];
  const wind = payload.wind_max_kmh ?? [];
  const prob = payload.precip_prob_pct ?? [];
  const soil = payload.soil_temp_c ?? [];

  const hasWeather =
    tMin.length + tMax.length + wind.length + prob.length + soil.length > 0 &&
    dates.length > 0;
  if (!hasWeather) return null;

  const sprayOk = (i: number): boolean | null => {
    const w = wind[i];
    const p = prob[i];
    if (w == null && p == null) return null;
    if (w == null || p == null) return null;
    return w < SPRAY_WIND_KMH && p <= SPRAY_PROB_PCT;
  };

  const frostDays = dates.filter((_, i) => tMin[i] != null && (tMin[i] as number) <= FROST_C);
  const sprayDays = dates.filter((_, i) => sprayOk(i) === true);

  return (
    <section className="card weather-card">
      <h3>Wetter &amp; Feldarbeit – {dates.length} Tage</h3>
      <div className="weather-grid" role="table" aria-label="Tagesüberblick Wetter und Feldarbeit">
        <div className="w-row w-days">
          <span className="w-label" />
          {dates.map((d, i) => (
            <span key={`day-${i}`} className="w-day">
              {weekdayOf(d)}
              <em className="muted small">{formatDateOnly(d)}</em>
            </span>
          ))}
        </div>
        <div className="w-row" role="row" title="Tiefst- und Höchsttemperatur (°C)">
          <span className="w-label" title="Tiefst-/Höchsttemperatur">🌡 °C</span>
          {dates.map((_, i) => (
            <span
              key={`t-${i}`}
              className={`w-val${tMin[i] != null && (tMin[i] as number) <= FROST_C ? " frost" : ""}`}
            >
              {num(tMin[i])}/{num(tMax[i])}
            </span>
          ))}
        </div>
        <div className="w-row" role="row" title="Maximale Windgeschwindigkeit (km/h)">
          <span className="w-label" title="Maximaler Wind">💨 km/h</span>
          {dates.map((_, i) => (
            <span
              key={`w-${i}`}
              className={`w-val${wind[i] != null && (wind[i] as number) >= SPRAY_WIND_KMH ? " warn" : ""}`}
            >
              {num(wind[i])}
            </span>
          ))}
        </div>
        <div className="w-row" role="row" title="Maximales Regenrisiko (%)">
          <span className="w-label" title="Regenrisiko">💧 %</span>
          {dates.map((_, i) => (
            <span key={`p-${i}`} className="w-val">
              {num(prob[i])}
            </span>
          ))}
        </div>
        <div className="w-row" role="row" title="Bodentemperatur 0–7 cm (°C)">
          <span className="w-label" title="Bodentemperatur 0–7 cm">🌱 °C</span>
          {dates.map((_, i) => (
            <span
              key={`s-${i}`}
              className={`w-val${
                soil[i] == null
                  ? ""
                  : (soil[i] as number) >= SOWING_WARM_C
                    ? " good"
                    : (soil[i] as number) >= SOWING_COOL_C
                      ? " mid"
                      : ""
              }`}
            >
              {num(soil[i], 1)}
            </span>
          ))}
        </div>
        <div className="w-row w-spray" title="Spritzen möglich bei Wind < 20 km/h und Regenrisiko ≤ 30 %">
          <span className="w-label" title="Spritzen möglich?">🚜</span>
          {dates.map((_, i) => {
            const ok = sprayOk(i);
            return (
              <span key={`sp-${i}`} className={`w-val${ok === true ? " good" : ok === false ? " warn" : ""}`}>
                {ok === true ? "✓" : ok === false ? "✗" : "–"}
              </span>
            );
          })}
        </div>
      </div>

      <p className="muted small weather-summary">
        {sprayDays.length > 0
          ? `Spritzen-Fenster: ${sprayDays.map((d) => weekdayOf(d)).join(", ")}`
          : "Spritzen-Fenster: diese Woche ungünstig (Wind/Regenrisiko)"}
        {frostDays.length > 0 && (
          <> · ⚠ Frost: {frostDays.map((d) => weekdayOf(d)).join(", ")}</>
        )}
      </p>
      <p className="muted small">
        Faustregeln: Spritzen bei Wind &lt; {SPRAY_WIND_KMH} km/h und Regenrisiko ≤ {SPRAY_PROB_PCT} %.
        Aussaat: viele Kulturen ab ~{SOWING_COOL_C}–{SOWING_WARM_C} °C Bodentemperatur (0–7 cm).
        Grenzwerte je Kultur und Mittel unterschiedlich — bitte Prüfungen vor Ort beachten.
      </p>
    </section>
  );
}
