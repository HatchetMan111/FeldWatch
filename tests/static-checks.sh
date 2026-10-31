#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail=0
ok()   { echo "ok   $*"; }
bad()  { echo "FAIL $*"; fail=1; }

check_file() {
  [[ -f "$1" ]] && ok "$1" || bad "$1 fehlt"
}

for f in install/fieldwatch.sh install/fieldwatch-inner.sh systemd/fieldwatch.service \
         README.md NOTICE app/requirements.txt app/pyproject.toml data/states.json \
         app/web/dist/index.html; do
  check_file "$f"
done

for f in install/fieldwatch.sh install/fieldwatch-inner.sh; do
  [[ -f "$f" ]] || continue
  bash -n "$f" && ok "bash -n $f" || bad "bash -n $f"
  grep -q '^set -euo pipefail' "$f" && ok "strict mode $f" || bad "set -euo pipefail fehlt in $f"
  grep -q 'trap .*ERR' "$f" && ok "ERR-Trap $f" || bad "ERR-Trap fehlt in $f"
done

grep -q '^User=fieldwatch' systemd/fieldwatch.service && ok "unit User" || bad "unit User"
grep -q '@APP_DIR@' systemd/fieldwatch.service && ok "unit Platzhalter APP_DIR" || bad "unit Platzhalter APP_DIR"
grep -q 'Restart=always' systemd/fieldwatch.service && ok "unit Restart" || bad "unit Restart"

grep -q 'raw.githubusercontent.com/HatchetMan111/FeldWatch/main/install/fieldwatch.sh' README.md \
  && ok "README Einzeiler" || bad "README Einzeiler passt nicht"

if command -v python3 >/dev/null; then
  python3 -m compileall -q app/src >/dev/null && ok "python compileall" || bad "python compileall"
fi

if [[ -f data/states.json ]]; then
  count=$(python3 -c "import json;print(len(json.load(open('data/states.json'))['states']))")
  [[ "$count" == "16" ]] && ok "16 Bundeslaender" || bad "Bundeslaender: $count statt 16"
fi

if command -v shellcheck >/dev/null; then
  shellcheck -S warning install/*.sh tests/*.sh && ok "shellcheck" || bad "shellcheck"
fi

if [[ "$fail" == "1" ]]; then
  echo "static-checks: FEHLGESCHLAGEN"
  exit 1
fi
echo "static-checks: OK"
