# FieldWatch auf Proxmox VE

Ein Einzeiler-Installer im Stil der Proxmox Community Scripts: Erstellt einen
Debian-12-LXC, installiert FieldWatch und richtet einen reboot-festen
`systemd`-Dienst ein. Die Web-UI ist nur im LAN erreichbar.

FieldWatch zeigt pro Feld eine Wachstumsanimation aus echten
Sentinel-2-Aufnahmen der letzten 12 Monate und den Wasserbedarf der naechsten
7 Tage (NDVI -> Cover -> Kcb x FAO-56 ETo).

## Was wird installiert?

| Komponente | Detail |
|---|---|
| Container | Debian 12, LXC, unprivileged, `onboot=1` |
| Ressourcen | 2 vCPU, 2048 MB RAM, 2048 MB Swap, 16 GB Disk |
| Dienst | `fieldwatch.service`, `Restart=always`, `After=network-online.target` |
| Stack | Python 3.11, FastAPI, rasterio, SQLite, React-Build (statisch) |
| Daten | `/var/lib/fieldwatch` (SQLite, COG-Cache, Feldbloecke) |
| Web-UI | `http://<CT-IP>:8080` |

## Voraussetzungen

- Proxmox VE 8.x, root-SSH auf dem Host
- Internetzugang des Containers (Sentinel-2, Open-Meteo)
- 20 GB freier Storage

## Schnellstart

Auf dem **Proxmox-Host** als root:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh)"
```

Das Script fragt Bundesland und Ressourcen ab, waehlt die naechste freie
CT-ID, erstellt den Container und installiert die App. Dauer: 5-10 Minuten.

Am Ende wird die URL ausgegeben:

```text
Web-UI: http://192.168.1.50:8080
```

## Optionen

```text
--ctid ID            CT-ID (Default: naechste freie)
--hostname NAME      Default: fieldwatch
--cores N            Default: 2
--ram MB             Default: 2048
--disk GB            Default: 16
--storage NAME       Default: automatisch
--bridge NAME        Default: vmbr0
--port N             Default: 8080
--bundesland CODE    BW,BY,BE,BB,HB,HH,HE,MV,NI,NW,RP,SL,SN,ST,SH,TH,none
--basemap local|osm  Default: local
--repo URL           Default: https://github.com/HatchetMan111/FeldWatch
--ref REF            Default: main
--password PW        root-Passwort im Container
--force              bestehende Installation ueberschreiben
--yes                nicht-interaktiv
--debug              bash -x + erweiterte Diagnose
```

Beispiel:

```bash
bash install/fieldwatch.sh --bundesland NW --ram 4096 --disk 32 --port 8080 --yes
```

## Nach der Installation

1. `http://<CT-IP>:8080` oeffnen.
2. Auf die Karte tippen (Feldblock, falls importiert) oder ein Polygon zeichnen.
3. Feld speichern, Analyse starten, Zeitachse abspielen.

### Feldbloecke

Fuer Laender mit `status: pending` in `data/states.json` gibt es noch keinen
Import. Bis dahin gilt der Zeichnen-Modus. Ein Feldblock-Datensatz kann
manuell importiert werden:

```bash
pct exec <CTID> -- /opt/fieldwatch/venv/bin/python -c \
  "from pathlib import Path; from fieldwatch.parcels import import_file; \
   print(import_file(Path('/root/felder.gpkg'), 'NW', Path('/var/lib/fieldwatch/parcels')))"
```

Danach den Dienst neu starten: `pct exec <CTID> -- systemctl restart fieldwatch`.

### Update

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh)" -- --ctid <CTID>
```

Daten in `/var/lib/fieldwatch` bleiben erhalten.

### Deinstallation

```bash
pct stop <CTID> && pct destroy <CTID> --purge
```

## Test und Diagnose

```bash
# ohne Proxmox
bash tests/static-checks.sh

# auf dem Proxmox-Host nach der Installation
bash tests/reboot-test.sh <CTID> <CT-IP> 8080

# Logs
pct exec <CTID> -- journalctl -u fieldwatch -f
pct exec <CTID> -- tail -n 200 /var/log/fieldwatch-install.log
```

Bei Fehlern zeigt der Installer Exit-Code, Zeile, Befehl, Host-Log,
Container-Log, `pct status` und `journalctl`. Fuer ein vollstaendiges Trace:

```bash
bash install/fieldwatch.sh --debug --ctid <CTID>
```

## Grenzen

- **Nur LAN.** Kein TLS, keine Domain, kein Login. Nicht ins Internet stellen.
- **Datenquelle Internet.** Die App laeuft lokal, Sentinel-2 und Open-Meteo
  werden aber online abgefragt.
- **Modell.** Kalibriert fuer gruene Blaetter und CC <= 0,8. Ergebnis ist
  Bedarf, keine Bewaesserungsanweisung.
- **Feldbloecke.** Nur Laender mit Status `available` loesen per Tap auf.
- **Kein Markenklon.** Name, Design und Texte sind eigenstaendig.

## Projektstruktur

```text
FeldWatch/
├── install/
│   ├── fieldwatch.sh          # Host: LXC, Whiptail, Verifikation
│   └── fieldwatch-inner.sh    # Container: Pakete, App, systemd, ufw
├── systemd/fieldwatch.service
├── app/
│   ├── src/fieldwatch/        # Pipeline + API
│   ├── tests/                 # pytest
│   └── web/                   # React + MapLibre, dist eingecheckt
├── data/states.json
├── tests/
│   ├── static-checks.sh
│   └── reboot-test.sh
├── NOTICE
└── README.md
```

## Credits

- Copernicus Sentinel-2 (ESA), AWS Earth Search (Element 84)
- Open-Meteo (CC BY 4.0)
- Trout & Johnson (2007), USDA-ARS
- Installer-Struktur inspiriert von den Proxmox Community Scripts
