export default function Method() {
  return (
    <details className="card method">
      <summary>Methode &amp; Grenzen</summary>
      <p className="muted">
        NDVI aus Sentinel-2 L2A (B04/B08, 10 m), Wolkenmaske über das SCL-Band.
        Frames zwischen Überflügen linear interpoliert. Auffälligkeiten werden gegen den
        gleichen Zeitraum früherer Jahre und die vorherige Aufnahme geprüft.
      </p>
      <pre>
        {`CC   = clip(1.22 · NDVI − 0.21, 0, 0.8)
Kcb  = 1.13 · CC + 0.14
ETc  = Kcb · ETo
m³   = mm · Fläche / 1000`}
      </pre>
      <p className="muted">
        Kalibriert für grüne Blätter und CC ≤ 0,8 (Trout &amp; Johnson 2007).
        Unbewachsener Boden, Netze und Beschattung unterschätzen den Bedarf.
        Das Ergebnis ist eine Orientierung, keine Bewässerungsanweisung.
      </p>
      <p className="muted">
        Wetter &amp; Feldarbeit: tägliche Tmin/Tmax, Wind, Regenrisiko und Bodentemperatur
        (0–7 cm) aus demselben Open-Meteo-Modell wie ETo. Spritzfenster (Wind &lt; 20 km/h,
        Regenrisiko ≤ 30 %) und Frosthinweis (Tmin ≤ 0 °C) sind grobe Faustregeln —
        keine Fachberatung; Grenzwerte je Kultur, Mittel und Witterung anders.
        Bodentemperatur ist modellderiviert und ersetzt keine Messung im Feld.
      </p>
      <p className="muted">
        Quellen: Copernicus Sentinel-2, Open-Meteo (CC BY 4.0), Luftbilder von Esri.
      </p>
    </details>
  );
}
