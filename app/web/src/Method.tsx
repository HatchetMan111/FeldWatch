export default function Method() {
  return (
    <section>
      <h3>Methode</h3>
      <p className="muted">
        NDVI aus Sentinel-2 L2A (B04/B08, 10 m), Wolkenmaske über das SCL-Band.
        Frames zwischen Überflügen linear interpoliert.
      </p>
      <pre style={{ fontSize: 12, overflowX: "auto" }}>
{`CC   = clip(1.22 · NDVI − 0.21, 0, 0.8)
Kcb  = 1.13 · CC + 0.14
ETc  = Kcb · ETo
m³   = mm · Fläche / 1000`}
      </pre>
      <p className="muted">
        Kalibriert für grüne Blätter und CC ≤ 0,8 (Trout &amp; Johnson 2007).
        Unbewachsener Boden, Netze und Beschattung unterschätzen den Bedarf.
        Das Ergebnis ist keine Bewässerungsanweisung.
      </p>
      <p className="muted">
        Quellen: Copernicus Sentinel-2, Open-Meteo (CC BY 4.0).
      </p>
    </section>
  );
}
