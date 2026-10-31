export default function App() {
  return (
    <div className="app">
      <header>
        <strong>FieldWatch</strong>
        <span className="muted">Oberfläche wird geladen…</span>
      </header>
      <main>
        <div className="map" />
        <aside className="side">
          <p className="muted">Feld auswählen oder zeichnen.</p>
        </aside>
      </main>
    </div>
  );
}
