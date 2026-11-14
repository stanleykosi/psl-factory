#!/usr/bin/env bash
# Runs every F-09 board against the dev server (app 4401, mock 4402). Usage: runall.sh <out dir> [board filter]
set -u
OUT="${1:?out dir}"; FILTER="${2:-}"
WT=/Users/Hunchoo/psl-factory-worktrees/f-09
HERE="$(cd "$(dirname "$0")" && pwd)"
BOARDS="$WT/design/canvas/project"
EXC="$HERE/../exception-requests.json"
APP=http://localhost:4401
run() { # board width url persona state
  local board=$1 width=$2 url=$3 persona=$4 state=$5
  [[ -n "$FILTER" && "$board" != *"$FILTER"* ]] && return
  curl -s -X POST http://127.0.0.1:4402/__mock/reset >/dev/null
  echo "== $board @ $width"
  FID_STATE=$state node "$HERE/fid-driver.mjs" --playwright "$WT/frontend/node_modules/playwright/index.mjs" \
    --board "$BOARDS/$board.dc.html" --page "$APP$url" --width "$width" --cookies "psl_mock_persona=$persona" \
    --exceptions "$EXC" --actions "$HERE/act.mjs" --out "$OUT/$board-$width" | grep -E '^(PASS|FAIL)'
}
R='/work/W-1601/respond?task=T-1601'
S='/work/W-1602/respond?task=T-1602'
run SCR-16-desktop 1440 "$R" pm default
run SCR-16-mobile 390 "$R" pm default
run SCR-16-desktop-validation 1440 "$R" pm validation
run SCR-16-mobile-validation 390 "$R" pm validation
run SCR-16-desktop-success 1440 "$R" pm success
run SCR-16-mobile-success 390 "$R" pm success
run SCR-16-desktop-sow-signed 1440 "$S" pm sow
run SCR-16-mobile-sow-signed 390 "$S" pm sow
run SCR-02-desktop-awaiting-reconciliation 1440 /work/W-1603 finance_lead reconcile
run SCR-02-mobile-awaiting-reconciliation 390 /work/W-1603 finance_lead reconcile
run SCR-02-desktop-waiting 1440 /work/W-1601 pm waiting
run SCR-02-mobile-waiting 390 /work/W-1601 pm waiting
