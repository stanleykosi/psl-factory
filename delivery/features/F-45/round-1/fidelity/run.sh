#!/bin/bash
# F-45: scores the 8 SCR-58 part-1 boards (investigating, observe, review, verified; desktop at 1440, phone at 390) on a
# production build (the e2e build, FRAME_FIXTURES=1, API_ORIGIN=http://127.0.0.1:4954), persona finance_lead.
# live: app on 4955, mock on 4954; the six live boards (each run starts with POST /__mock/reset).
# frozen: drive-states.mjs has frozen the two observe boards; serve-frozen.mjs serves them on 4956 (assets from the app on 4955).
# Usage: run.sh <live|frozen> [exceptions.json] [out-dir]
MODE=$1
WT=/Users/Hunchoo/psl-factory-worktrees/f-45
EXC=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-45/fidelity-exceptions.json}
OUT=${3:-/Users/Hunchoo/psl-factory/delivery/features/F-45/round-1/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=$WT/design/canvas/finance/project
mkdir -p "$OUT"
[ -f "$OUT/scores.txt" ] || printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board page width
  local name="$1-$3"
  [ "$MODE" = live ] && curl -s -X POST http://127.0.0.1:4954/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$1.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=finance_lead \
    --exceptions "$EXC" --wait-ms 1500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  if [ "$MODE" = live ]; then
    run "SCR-58-$V-investigating" "http://localhost:4955/work/W-4201" $W
    run "SCR-58-$V-review" "http://localhost:4955/work/W-4203" $W
    run "SCR-58-$V-verified" "http://localhost:4955/work/W-4204" $W
  else
    run "SCR-58-$V-observe" "http://localhost:4956/frozen/SCR-58-$V-observe-$W.html" $W
  fi
done
cat "$OUT/scores.txt"
