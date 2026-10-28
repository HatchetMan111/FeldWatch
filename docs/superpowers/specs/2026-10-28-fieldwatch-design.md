# FieldWatch — lokale Feld-/Bewässerungs-App auf Proxmox – Design

- **Datum:** 2026-10-28
- **Status:** Entwurf zur Freigabe
- **Projektordner:** `fieldwatch-proxmox/`
- **Arbeitstitel:** `fieldwatch` (Name noch nicht final, Repo folgt)

## 1. Kontext und Ziel

Es soll eine selbst gehostete Anwendung entstehen, die pro Feldgrenze

1. eine **Wachstumsanimation** aus echten Sentinel-2-Aufnahmen der letzten
   12 Monate rendert (NDVI-gefärbt, zwischen den Überflügen interpoliert),
2. den **Wasserbedarf der nächsten 7 Tage** berechnet
   (`NDVI → Cover → Kcb × FAO-56 ETo`),
3. die Werte als Tiefe (mm) und Volumen (m³) zeigt,
4. alle Datenquellen korrekt attributiert.

Installation und Betrieb erfolgen vollständig im eigenen Proxmox-Homelab, im
Stil der [Proxmox VE Community Scripts](https://community-scripts.github.io/ProxmoxVE):
ein Einzeiler erzeugt einen LXC, installiert die App und richtet einen
reboot-festen systemd-Dienst ein. Die App ist **nur im LAN** erreichbar.

Vorbild der Funktion ist [epicfields.app](https://epicfields.app). Übernommen
wird ausschließlich die dort offen dokumentierte **Methode**, nicht Name,
Design, Texte oder Code des Produkts.

### 1.1 Entscheidungen aus der Klärung

| Thema | Entscheidung |
|---|---|
| Zielplattform | Proxmox VE 8.x, **LXC** (kein Docker im Container) |
| Installation | Einzeiler, Community-Scripts-Konvention, Whiptail-Abfragen |
| Erreichbarkeit | **nur LAN**, keine Domain, kein TLS, kein Port-Forwarding |
| Region | **alle 16 Bundesländer** werden angeboten, mit Fallback „Polygon zeichnen" |
| Umfang erster Wurf | **gestaffelt**: Installer + lauffähiger MVP zuerst, Feldblöcke danach |
| App-Name | `fieldwatch` (Arbeitstitel), CT-Hostname + Service leiten sich davon ab |
| Web-Port | `8080` (per `--port` änderbar) |
| Daten | Sentinel-2 (AWS Earth Search), Open-Meteo; gridMET/SILO optional |
| Kosten | 0 €, keine kostenpflichtigen Keys im privaten Betrieb |

### 1.2 Nicht-Ziele (v1)

- Globales „jedes Feld der Erde" — Feldgrenzen-Auflösung nur dort, wo freie
  Daten vorliegen, sonst manuelles Polygon
- iOS-/Android-App, Mehrbenutzerkonten, Login, Multi-Tenant
- Bodenfeuchte, Stressfaktor (Ke), Bewässerungsempfehlung, Ernteprognose
- Aussaat-/Erntedaten, Kulturart-spezifische Kcb-Kurven (v1.1)
- Selfhosting von Open-Meteo oder eines Tile-Servers
- Kommerzieller Betrieb (Open-Meteo-Free-Lizenz)
- VM-Variante (der LXC braucht < 1 GB RAM im Idle; VM erst relevant, wenn
  Open-Meteo selbst gehostet wird)

## 2. Annahmen (in Phase 0 zu verifizieren)

1. `earth-search.aws.element84.com/v1` liefert Sentinel-2-L2A-COGs anonym,
   ohne AWS-Account, mit stabilen Asset-Keys (`red`, `nir`, `scl`).
2. COG-Window-Reads über `/vsicurl` sind für ~1 km² schnell genug
   (< 2 s pro Szene, 8–16 parallel), ohne lokalen Voll-Download.
3. `api.open-meteo.com` liefert `et0_fao_evapotranspiration` als Tageswert
   ohne Key; Rate-Limit reicht für den privaten Betrieb.
4. Das SCL-Band (20 m) ist für die Wolkenmaskierung ausreichend; bei kleinen
   Feldern (< 2 ha) ist die Maske unscharf, aber brauchbar.
5. Für mindestens einige Bundesländer existieren offene InVeKoS-Feldblöcke in
   maschinenlesbarem Format (WFS/Shapefile/GeoPackage) mit Lizenz
   DL-DE-BY-2.0. Welche, wird in Phase 0 bzw. Phase 6 geprüft — nicht
   angenommen.
6. Ein Proxmox-Host mit ≥ 20 GB freiem Storage und Internetzugang steht bereit.
7. Die Formeln `CC = 1.22·NDVI − 0.21` und `Kcb = 1.13·CC + 0.14`
   (Trout & Johnson 2007, USDA-ARS) sind frei verfügbar und nachrechenbar.

## 3. Architektur

```
Proxmox VE 8.x Host
└── LXC „fieldwatch"  (Debian 12, unprivileged, onboot=1)
    ├── 2 vCPU / 2048 MB RAM / 16 GB Disk / 2 GB Swap
    ├── fieldwatch.service  (uvicorn, 0.0.0.0:8080, Restart=always)
    │     ├── FastAPI: REST-API + statisch gebautes Frontend
    │     ├── APScheduler im Prozess: Sentinel-1×/Tag, Wetter-1×/Stunde
    │     ├── Pipeline: STAC → COG-Window → NDVI/SCL → Zonal → CC/Kcb → ETo
    │     └── SQLite (WAL) + COG-Window-Cache (LRU, 4 GB Cap)
    └── /var/lib/fieldwatch/
          ├── app.sqlite
          ├── cache/cog/            (nur Fenster, keine Vollbilder)
          ├── parcels/<land>.fgb    (Feldblöcke, FlatGeobuf)
          └── basemap/states.geojson
```

Bewusst **ein** Prozess statt API + Worker + Proxy:

- Ein systemd-Dienst ist weniger Angriffs- und Fehlerfläche.
- Kein Caddy nötig, weil LAN-only ohne TLS.
- Kein Docker, weil Docker im LXC `nesting`, `keyctl`, `fuse` und
  overlayfs-Sonderfälle auf ZFS bedeutet — für drei Aufgaben zu viel.
- Refresh-Läufe sind kurz und idempotent, ein In-Process-Scheduler genügt.

### 3.1 Datenfluss pro Feld

```
Tap (lat, lon)
  → Punkt-in-Polygon gegen parcels/*.fgb (FlatGeobuf-Index, DuckDB spatial)
  → STAC-Suche (12 Monate, intersects=Feld, eo:cloud_cover < 80)
  → COG-Fenster lesen (red, nir, scl; BBox + 10 % Puffer)
  → NDVI = (nir − red) / (nir + red)
  → SCL-Maske (gültig = 4,5,7), Pass verwerfen bei < 70 % klaren Pixeln
  → Zonalstatistik im Polygon (Median NDVI, Mittel, Clear-%, Pixelzahl)
  → Frames: auf ≤ 256×256 skaliert, uint8, pro Pass + Datum
  → CC = clip(1.22·NDVI − 0.21, 0, 0.8)
  → Kcb = 1.13·CC + 0.14
  → ETo(7 d) von Open-Meteo (et0_fao_evapotranspiration, Tageswert)
  → ETc_d = Kcb · ETo_d ; Woche = Σ ; Volumen = Tiefe · Fläche
  → SQLite + HTTP
```

**Kein Video-Encoding:** Der Client bekommt pro Überflug ein kleines
`uint8`-Raster (~65 KB bei 256×256) plus Datum und interpoliert zwischen den
Frames. Ergebnis: flüssige, scrub-bare Animation bei wenigen hundert KB
Transfer und ohne FFmpeg im Container.

## 4. Datenquellen, Keys und Attribution

| Quelle | Liefert | Abdeckung | Auflösung | Key nötig | Privatperson |
|---|---|---|---|---|---|
| Sentinel-2 L2A | Bilder + NDVI | global | 10 m | nein (AWS Earth Search, anonym) | ja |
| Open-Meteo | ETo-Forecast, Regen | global | 11 km | nein (< 10k Calls/Tag, nicht-kommerziell) | ja |
| gridMET | Regen, ETo, Temperatur (Historie) | Kalifornien | 4 km | nein (THREDDS/OPeNDAP) | ja |
| SILO | Regen, ETo, Temperatur (Historie) | Australien | 5 km | ja, kostenlos per E-Mail-Registrierung | ja |
| InVeKoS-Feldblöcke | Feldgrenzen | je Bundesland | vektor | nein (WFS/Download) | ja |

**Attribution (Footer + Methodenseite, nicht entfernbar):**

- „Contains modified Copernicus Sentinel data 2025/2026"
- „Weather data by Open-Meteo.com (CC BY 4.0)"
- „gridMET — Abatzoglou 2013"
- „SILO © State of Queensland (CC BY 4.0)"
- „© GeoBasis-DE / <Land> (DL-DE-BY-2.0)" je importiertem Bundesland

**Rechtlicher Rahmen:** Methode und Formeln sind veröffentlicht und frei
nachrechenbar. Name, Logo, Hero-Bild, Texte und Quellcode von
epicfields.app sind geschützt und werden nicht übernommen. Deren Backend
wird nicht abgefragt.

## 5. Bundesländer-Strategie

Der Installer fragt das Bundesland ab und speichert es in
`/etc/fieldwatch/config.env`. Alle 16 Länder sind auswählbar; die
Feldblock-Auflösung hängt vom Datenstand ab:

| Status | Bedeutung im Betrieb |
|---|---|
| `available` | Feldblöcke importiert, Tap löst Parzelle auf |
| `pending` | Land wählbar, aber nur „Polygon zeichnen" |
| `fallback` | bewusst nur Zeichnen-Modus (Stadtstaaten) |

Die Status-Tabelle liegt als `data/states.json` im Repo und wird beim
Install in die App kopiert. Phase 6 füllt sie mit echten Quellen; bis dahin
steht jedes Land auf `pending` außer denen, die in Phase 6 verifiziert
wurden. Der Installer zeigt den Status im Auswahlmenü an, damit niemand eine
Funktion erwartet, die es noch nicht gibt.

InVeKoS-Import (Phase 6) pro Land:

1. Quelle und Lizenz in `data/states.json` eintragen (URL, Lizenz, Stand).
2. `python -m fieldwatch.import_parcels --state <CODE>` lädt, normalisiert
   auf EPSG:25832 → WGS84, schreibt `<land>.fgb` + Metadaten
   (`FLIK`, Nutzungscode, Fläche).
3. Import ist idempotent (Hash über Quelldatei), alter Stand bleibt bis zum
   erfolgreichen neuen Import erhalten.

## 6. Installer

### 6.1 Aufruf

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh)"
```

Lokal identisch: `git clone … && sudo bash install/fieldwatch.sh`.

### 6.2 Struktur (Community-Scripts-Konvention)

```text
install/fieldwatch.sh        # Host: Vorprüfung, Whiptail, LXC, Aufruf innen
install/fieldwatch-inner.sh  # Container: Pakete, App, systemd, Healthcheck
systemd/fieldwatch.service   # Unit mit @APP_PORT@/@APP_DIR@/@DATA_DIR@
tests/static-checks.sh       # ohne Proxmox ausführbar
tests/reboot-test.sh         # echter Reboot-Test auf dem Host
```

Host-Script: `set -euo pipefail`, `trap … ERR`, Log nach
`/var/log/fieldwatch-install.log`, farbige `msg_info/msg_ok/msg_warn/
msg_error/die`-Helfer, `--debug` → `set -x` mit `PS4`-Timestamps.

### 6.3 Ablauf

1. **Vorprüfung** — root, `pct`/`pveam`/`pvesh` vorhanden, `/etc/pve`
   existiert, `pvesm status` erreichbar, Internet-Check (STAC + Open-Meteo
   HEAD), Storage-Platz ≥ 20 GB.
2. **Whiptail** (nur wenn TTY und kein `--yes`):
   - Bundesland (16 Einträge + „Kein Bundesland / nur eigene Polygone")
   - CT-ID (Default: nächste freie)
   - Ressourcen (Default 2 vCPU / 2048 MB / 16 GB)
   - Basemap (offline Staaten-Grenzen / online OSM)
3. **Template** — `pveam update`, `debian-12-standard` suchen, bei Bedarf
   herunterladen.
4. **Container** — `pct create` mit `--unprivileged 1 --onboot 1
   --features nesting=0 --hostname fieldwatch`, Disk, Net0 `vmbr0,dhcp`,
   `--cores`, `--memory`, `--swap 2048`, DNS.
5. **Warten** — `pct exec` bis `cloud-init`/Netz bereit (max. 120 s),
   sonst vollständige Fehlerkette.
6. **Innen-Installation** — Inner-Script per `pct push` + `pct exec`,
   Ausgabe live, Log unter `/var/log/fieldwatch-install.log` im CT.
7. **Verifikation** — 30 s Retry auf `http://127.0.0.1:8080/healthz`,
   `systemctl is-active fieldwatch`, Port-Check.
8. **Abschluss** — IP ermitteln (`pct exec … hostname -I`), Banner mit
   `http://<IP>:8080`, CT-ID, Update-Befehl, Deinstall-Befehl.

### 6.4 Flags

```text
--ctid ID            CT-ID (Default: nächste freie ab 100)
--hostname NAME      Default: fieldwatch
--cores N            Default: 2
--ram MB             Default: 2048
--disk GB            Default: 16
--storage NAME       Default: automatisch
--bridge NAME        Default: vmbr0
--port N             Default: 8080
--bundesland CODE|none|ask   Default: ask
--basemap local|osm  Default: local
--repo URL           Default: im Script hinterlegt
--ref REF            Default: main
--force              Update/Reinstall erzwingen
--yes                nicht-interaktiv, Defaults verwenden
--debug              bash -x + erweiterte Diagnose
```

### 6.5 Idempotenz

- Existiert bereits ein CT mit `--ctid` **und** Hostname `fieldwatch`, wird
  er aktualisiert (Inner-Script erneut ausführen), nicht neu erstellt.
- Existiert die ID mit fremdem Hostnamen → Abbruch mit klarer Meldung, keine
  Änderung.
- Ohne `--ctid` wird `pvesh get /cluster/nextid` benutzt (nächste freie ID).
- Inner-Script ist auf Wiederholbarkeit ausgelegt: Pakete nur bei Bedarf,
  `git fetch && git reset --hard <ref>`, Unit neu schreiben,
  `daemon-reload`, `restart`.

### 6.6 Fehlerkette (verbindlich)

Bei jedem Abbruch gibt das Script aus:

1. Exit-Code und fehlgeschlagenen Befehl (`$BASH_COMMAND`) mit Zeilennummer
2. letzten 60 Zeilen des Host-Logs
3. falls vorhanden: letzten 60 Zeilen des Container-Logs
4. Container-Status (`pct status`), letzte `journalctl -u fieldwatch`-Zeilen
5. konkreten nächsten Schritt (z. B. „erneut mit `--debug`", „`pct enter <ID>`")

Niemals nur die letzte Fehlerzeile. `--debug` erzeugt zusätzlich ein
`bash -x`-Tracefile unter `/tmp/fieldwatch-install-<timestamp>.trace`.

## 7. Container-Inneninstallation

1. `apt-get update`, `debian-archive-keyring`, `curl`, `ca-certificates`,
   `python3`, `python3-venv`, `python3-dev`, `build-essential`, `gdal-bin`,
   `libgdal-dev`, `sqlite3`, `git`, `ufw`, `jq`.
2. Systemuser `fieldwatch` (nologin), Verzeichnisse
   `/opt/fieldwatch` (Code) und `/var/lib/fieldwatch` (Daten).
3. Code aus Repo/Release, `python3 -m venv /opt/fieldwatch/venv`,
   `pip install -r requirements.txt` (Rasterio/GDAL als Wheel oder gegen
   `libgdal-dev` gebaut).
4. Frontend: fertig gebautes `dist/` aus dem Repo (kein Node im Container).
5. `config.env` schreiben (`FIELDWATCH_STATE`, `FIELDWATCH_PORT`,
   `FIELDWATCH_BASEMAP`, `FIELDWATCH_REPO_REF`), Modus `600`,
   Besitzer `fieldwatch`.
6. Unit `fieldwatch.service` installieren, `enable --now`.
7. `ufw` nur für RFC1918 auf den Port freigeben:
   `ufw allow from 10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 to any port <PORT>`.
8. Healthcheck, Abschlussmeldung.

## 8. API

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/healthz` | Status, Version, DB, Cache-Größe, Quellen-Erreichbarkeit |
| GET | `/api/states` | 16 Länder mit Status (`available`/`pending`/`fallback`) |
| GET | `/api/resolve?lat=&lon=` | Parzelle per Punkt-in-Polygon oder `{found:false}` |
| POST | `/api/fields` | Feld anlegen (GeoJSON-Polygon + Name) |
| GET | `/api/fields` | Liste |
| GET | `/api/fields/{id}` | Feld + Fläche + Metadaten |
| DELETE | `/api/fields/{id}` | löschen |
| GET | `/api/fields/{id}/series?months=12` | NDVI-Serie je Pass (Datum, Median, Clear-%) |
| GET | `/api/fields/{id}/frames` | `uint8`-Raster je Pass + Datum + Bounds |
| GET | `/api/fields/{id}/demand` | 7-Tage-ETo, Kcb, ETc, Woche, Volumen, Flags |
| POST | `/api/fields/{id}/refresh` | Neuberechnung anstoßen (Rate-Limit) |

Antworten sind JSON, Fehler `{"error": {"code": "...", "message": "...",
"detail": "..."}}` mit passendem HTTP-Status. `/healthz` antwortet auch bei
Teilausfällen mit `200` und `"degraded": true`, damit der Installer nicht
falsch negativ prüft.

## 9. Datenmodell (SQLite, WAL)

| Tabelle | Inhalt |
|---|---|
| `fields` | id, name, geometry (GeoJSON), area_m2, state, created_at |
| `observations` | field_id, date, median_ndvi, mean_ndvi, clear_pct, pixels, frame (BLOB), wkb_hash |
| `demand` | field_id, computed_at, kcb, eto_json, etc_json, week_mm, week_m3, stale_canopy |
| `source_log` | ts, source, url, status, bytes, duration_ms, license |

GeoJSON-Polygone bleiben in SQLite, weil Felder klein sind (< 100 ha).
Feldblöcke liegen als FlatGeobuf außerhalb (Millionen Polygone).

## 10. Modell

```
NDVI   = (nir − red) / (nir + red)          # -1 … 1, 0 bei Division durch 0
CC     = clip(1.22 · NDVI − 0.21, 0, 0.8)   # Trout & Johnson 2007
Kcb    = 1.13 · CC + 0.14                   # 0.14 … 1.044
ETc_d  = Kcb · ETo_d                        # mm/Tag
Woche  = Σ ETc_d über 7 Tage
m³     = week_mm · area_m2 / 1000
```

- ETo kommt als `et0_fao_evapotranspiration` (Tageswert, `timezone=auto`).
- Regen wird **angezeigt, aber nie abgezogen** („demand, not use").
- Kcb stammt aus dem jüngsten Pass mit Clear-% ≥ 70. Ist er älter als
  21 Tage, wird `stale_canopy: true` gesetzt und in der UI gewarnt.
- Gültigkeitsgrenzen werden auf der Methodenseite genannt: kalibriert für
  grüne Blätter, CC ≤ 0,8; unbewachsener Boden und Netze unterschätzen den
  Bedarf; Ergebnis ist keine Bewässerungsanweisung.

## 11. Frontend

- React + TypeScript + Vite, MapLibre GL, Build-Artefakt im Repo.
- **Basemap:** Default ist eine neutrale, leere Karte (kein externer Request,
  `--basemap local`); Feldgrenze, gezeichnete Entwürfe und die NDVI-Zeitachse
  liegen darüber. Optional `--basemap osm` für Online-Rasterkacheln.
  Bundesland-Grenzen als Offline-Hintergrund (`states.geojson`) sind eine
  P1-Erweiterung, nicht Teil des MVP.
- Ansichten: Karte mit Feldauswahl/Zeichnen → Zeitachse mit Play/Scrub →
  Wasser-Panel (7 Balken, mm und m³) → Methodenseite mit Formeln und
  Attribution.
- Keine Tracker, keine CDN-Abhängigkeiten, keine Accounts.
- Mobil zuerst bedienbar (Tap auf Feld, große Scrub-Fläche).

## 12. Fehlerbehandlung und Degradation

| Fall | Verhalten |
|---|---|
| STAC/COG nicht erreichbar | Serie aus Cache; Banner „Quelle offline", Demand bleibt nutzbar |
| Open-Meteo nicht erreichbar | Demand `unavailable` statt 500; letzter bekannter Wert mit Zeitstempel |
| Kein klarer Pass in 21 Tagen | `stale_canopy`, Warnung, kein erfundener Wert |
| Feld < 0,5 ha | Hinweis „Maske zu grob", Ergebnis mit Unsicherheitsflag |
| Disk > 80 % | Cache-LRU räumen, Warnung in `/healthz` |
| Rate-Limit (429) | exponentieller Backoff, Batch-Requests, Job verschieben |

## 13. Tests

- `tests/static-checks.sh` (ohne Proxmox lauffähig): `bash -n` beider
  Scripts, `shellcheck` falls vorhanden, Unit-Platzhalter, README-Einzeiler
  passt zum Pfad, `python -m compileall`, `pytest -q`.
- `tests/reboot-test.sh`: Dienst + HTTP prüfen, `pct reboot`, erneut prüfen,
  Logausgabe.
- `pytest`: Formeln (CC/Kcb/ETc/Grenzen), SCL-Maske, Zonalstatistik,
  Volumenberechnung, GeoJSON-Validierung, API-Fehlerfälle, Idempotenz des
  Parcel-Imports.
- Abnahmekriterium MVP: frischer LXC → Installation < 10 min → Feld anlegen
  → Animation läuft → Demand erscheint → `pct reboot` → alles wieder da.

## 14. Phasen

| Phase | Inhalt | Aufwand |
|---|---|---|
| P0 | Spike: echte Requests an STAC/COG/Open-Meteo, Formeln prüfen, Bundesland-Datenlage sichten | 0,5–1 d |
| P1 | Repo-Gerüst, Installer (Host+Inner), systemd, `/healthz`, Tests, README | 1,5 d |
| P2 | Pipeline-CLI: STAC, COG-Window, NDVI/SCL, Zonal, Frames, ETo, Demand + Unit-Tests | 2–3 d |
| P3 | API + SQLite + statisches Frontend servieren | 1–2 d |
| P4 | Frontend: Karte, Zeichnen, Zeitachse, Wasser-Panel, Methodenseite | 2–3 d |
| P5 | Härtung: Cache-LRU, Retries, Disk-Guard, Degradation, Reboot-Test | 1 d |
| P6 | Feldblöcke: 16 Länder gelistet, verifizierte importieren (FlatGeobuf) | 2–4 d |
| P7 | Doku, Attribution, Release, finaler Einzeiler-Test | 0,5 d |

MVP = P0–P5 (≈ 7–10 Entwicklertage). P6 ist der zweite, unabhängige Wurf.

## 15. Risiken

- **HOCH:** „jedes Feld" ist ohne globalen Parzellendatensatz nicht
  erreichbar. → Region + Fallback sind explizit; Erwartung im README.
- **HOCH:** Trout-&-Johnson-Modell ist für San-Joaquin-Valley kalibriert.
  Mais/Spargel im Rheinland können systematisch abweichen. → Grenzen
  dokumentieren, Ergebnis nie als Anweisung darstellen.
- **MITTEL:** Feldblock-Daten sind pro Land heterogen (Format, Lizenz,
  Endpoint). → Nur verifizierte Länder auf `available`, Rest `pending`.
- **MITTEL:** „vollständig lokal" gilt nur für die App, nicht für
  Sentinel-2/Open-Meteo. → Im README und auf der Methodenseite klarstellen.
- **MITTEL:** Open-Meteo-Free ist nicht-kommerziell. → Bei öffentlichem
  Betrieb Selfhosting nötig; v1 ist LAN-only.
- **MITTEL:** Marken-/Urheberrecht an epicfields.app. → eigener Name,
  eigenes Design, eigene Texte, kein Scraping.
- **NIEDRIG:** SCL nur 20 m, kleine Felder ungenau. → Mindest-Clear-Anteil,
  Unsicherheitsflag.
- **NIEDRIG:** Einheiten (mm/m³, UTC/lokal). → intern SI, Umrechnung nur in
  der UI, Tests.

## 16. Offene Punkte

1. Finaler App-Name und GitHub-Repo (`HatchetMan111/FeldWatch`)
   im Script-Header und README.
2. Welche Bundesländer in Phase 6 tatsächlich `available` werden — abhängig
   vom Spike-Ergebnis.
3. Ob die Basemap offline (Default) oder online besser ankommt — nach P4
   entscheiden.
