#!/usr/bin/env bash
set -euo pipefail

CTID="${1:?Usage: reboot-test.sh <CTID> [IP] [PORT]}"
IP="${2:-}"
PORT="${3:-8080}"
APP_ID="fieldwatch"

pass() { echo "ok   $*"; }
bad()  { echo "FAIL $*"; exit 1; }

[[ "$(id -u)" == "0" ]] || bad "als root auf dem Proxmox-Host ausfuehren"

echo "== vor dem Reboot =="
pct status "$CTID" | grep -q running || pct start "$CTID"
pct exec "$CTID" -- systemctl is-active --quiet "$APP_ID" || bad "Dienst nicht aktiv"
pass "Dienst aktiv"
pct exec "$CTID" -- curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null || bad "healthz antwortet nicht"
pass "healthz antwortet"

echo "== Reboot =="
pct reboot "$CTID"
for _ in $(seq 1 90); do
  if pct exec "$CTID" -- systemctl is-active --quiet "$APP_ID" 2>/dev/null; then break; fi
  sleep 2
done

echo "== nach dem Reboot =="
pct exec "$CTID" -- systemctl is-active --quiet "$APP_ID" || bad "Dienst nach Reboot nicht aktiv"
pass "Dienst automatisch gestartet"
pct exec "$CTID" -- curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null || bad "healthz nach Reboot"
pass "healthz antwortet"
[[ "$(pct config "$CTID" | awk -F': ' '/^onboot:/{print $2}')" == "1" ]] || bad "onboot ist nicht 1"
pass "onboot=1"

if [[ -n "$IP" ]]; then
  curl -fsS "http://${IP}:${PORT}/healthz" >/dev/null || bad "Web-UI von aussen nicht erreichbar"
  pass "Web-UI erreichbar unter http://${IP}:${PORT}"
fi

echo "reboot-test: OK"
