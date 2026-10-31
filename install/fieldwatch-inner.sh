#!/usr/bin/env bash
#
# fieldwatch-inner.sh - laeuft INNERHALB des LXC.
# Installiert FieldWatch, schreibt die systemd-Unit und startet den Dienst.
#
set -euo pipefail

APP_ID="fieldwatch"
APP_DIR="/opt/fieldwatch"
DATA_DIR="/var/lib/fieldwatch"
CONF_DIR="/etc/fieldwatch"
PORT="8080"
STATE_CODE="none"
BASEMAP="local"
REPO_URL="https://github.com/HatchetMan111/FeldWatch"
REPO_REF="main"
DEBUG=0
LOG_FILE="/var/log/fieldwatch-install.log"

msg_info()  { echo -e "\e[34m[INFO]\e[0m  $*"; }
msg_ok()    { echo -e "\e[32m[OK]\e[0m    $*"; }
msg_warn()  { echo -e "\e[33m[WARN]\e[0m  $*"; }
msg_error() { echo -e "\e[31m[ERROR]\e[0m $*" >&2; }
die()       { msg_error "$*"; exit 1; }

on_error() {
  local code=$1 line=$2 cmd=$3
  trap - ERR
  {
    echo
    msg_error "Abbruch (Exit ${code}) in Zeile ${line}: ${cmd}"
    echo "--- Install-Log (letzte 60 Zeilen) ---"
    tail -n 60 "$LOG_FILE" 2>/dev/null || true
    echo "--- systemctl status ---"
    systemctl status "$APP_ID" --no-pager -l 2>&1 | tail -n 40 || true
    echo "--- journalctl ---"
    journalctl -u "$APP_ID" -n 60 --no-pager 2>&1 || true
    echo "--- Ports ---"
    ss -tlnp 2>&1 | head -20 || true
    echo
    echo "Naechster Schritt: erneut mit --debug ausfuehren:"
    echo "  bash /root/fieldwatch-inner.sh --debug --port ${PORT}"
  } >&2
  exit "$code"
}
trap 'on_error $? $LINENO "$BASH_COMMAND"' ERR

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --state) STATE_CODE="$2"; shift 2;;
    --basemap) BASEMAP="$2"; shift 2;;
    --repo) REPO_URL="$2"; shift 2;;
    --ref) REPO_REF="$2"; shift 2;;
    --debug) DEBUG=1; shift;;
    *) die "Unbekannte Option: $1";;
  esac
done

if [[ "$DEBUG" == "1" ]]; then
  export PS4='+ $(date +%H:%M:%S) ${BASH_SOURCE##*/}:${LINENO}: '
  exec > >(tee -a "$LOG_FILE") 2>&1
  set -x
else
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

msg_info "FieldWatch Installation startet (Port ${PORT}, Land ${STATE_CODE})"

msg_info "Pakete aktualisieren"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git python3 python3-venv python3-dev \
  build-essential gdal-bin libgdal-dev sqlite3 ufw jq >/dev/null
msg_ok "Pakete installiert"

if ! id "$APP_ID" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_ID"
  msg_ok "Benutzer ${APP_ID} angelegt"
fi

mkdir -p "$APP_DIR" "$DATA_DIR" "$CONF_DIR"
chown -R "$APP_ID:$APP_ID" "$DATA_DIR"

msg_info "Code laden von ${REPO_URL} (${REPO_REF})"
TMP_DIR="$(mktemp -d)"
git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$TMP_DIR/src" \
  || die "git clone fehlgeschlagen: ${REPO_URL} (${REPO_REF})"
rm -rf "${APP_DIR:?}/"*
cp -a "$TMP_DIR/src/app/." "$APP_DIR/"
mkdir -p "$APP_DIR/data"
cp -a "$TMP_DIR/src/data/." "$APP_DIR/data/"
cp -a "$TMP_DIR/src/systemd" "$APP_DIR/systemd" 2>/dev/null || true
rm -rf "$TMP_DIR"
chown -R "$APP_ID:$APP_ID" "$APP_DIR"
msg_ok "Code in ${APP_DIR}"

msg_info "Python-Umgebung"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip wheel
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
"$APP_DIR/venv/bin/pip" install --quiet -e "$APP_DIR"
"$APP_DIR/venv/bin/python" -c "import fieldwatch, fastapi, rasterio, fiona"
msg_ok "Python-Abhaengigkeiten installiert"

msg_info "Konfiguration schreiben"
cat > "$CONF_DIR/config.env" <<EOF
FIELDWATCH_STATE=${STATE_CODE}
FIELDWATCH_PORT=${PORT}
FIELDWATCH_BASEMAP=${BASEMAP}
FIELDWATCH_DATA_DIR=${DATA_DIR}
FIELDWATCH_REPO_REF=${REPO_REF}
FIELDWATCH_SCHEDULER=1
EOF
chmod 600 "$CONF_DIR/config.env"
chown root:root "$CONF_DIR/config.env"
msg_ok "Konfiguration in ${CONF_DIR}/config.env"

msg_info "systemd-Unit installieren"
sed -e "s|@APP_DIR@|${APP_DIR}|g" -e "s|@APP_PORT@|${PORT}|g" \
  "$APP_DIR/systemd/fieldwatch.service" > "/etc/systemd/system/${APP_ID}.service"
systemctl daemon-reload
systemctl enable "$APP_ID" >/dev/null 2>&1
systemctl restart "$APP_ID"
msg_ok "Dienst ${APP_ID}.service aktiviert"

msg_info "Firewall (nur LAN)"
if ufw --force reset >/dev/null 2>&1 \
  && ufw default deny incoming >/dev/null 2>&1 \
  && ufw default allow outgoing >/dev/null 2>&1; then
  for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16; do
    ufw allow from "$net" to any port "$PORT" proto tcp >/dev/null 2>&1 || true
  done
  if ufw --force enable >/dev/null 2>&1; then
    msg_ok "ufw: Port ${PORT} nur aus RFC1918"
  else
    msg_warn "ufw konnte nicht aktiviert werden (LXC ohne CAP_NET_ADMIN) - Schutz erfolgt ueber die LAN-Grenze"
  fi
else
  msg_warn "ufw nicht verfuegbar (LXC) - Schutz erfolgt ueber die LAN-Grenze"
fi

msg_info "Healthcheck"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
if [[ "$ok" != "1" ]]; then
  die "Web-UI antwortet nicht auf http://127.0.0.1:${PORT}/healthz"
fi
systemctl is-active --quiet "$APP_ID" || die "Dienst ${APP_ID} laeuft nicht"
msg_ok "Dienst laeuft, /healthz antwortet"

echo
msg_ok "FieldWatch ist bereit."
