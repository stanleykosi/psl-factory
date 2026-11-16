#!/bin/bash
# F-22: scores the 4 SCR-25 boards (returned and received, desktop at 1440, phone at 390). App on 4750 (production build), mock on 4751.
# Usage: run.sh <exceptions.json> <out-dir>
WT=/Users/Hunchoo/psl-factory-worktrees/f-22
EXC=${1:-$WT/delivery/features/F-22/fidelity-exceptions.json}
OUT=${2:-$WT/delivery/features/F-22/round-1/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # state item width
  local V=desktop; [ $3 = 390 ] && V=mobile
  local name="SCR-25-$V-$1-$3"
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/SCR-25-$V-$1.dc.html" --page "http://localhost:4750/work/$2" --width $3 --cookies psl_mock_persona=pm \
    --exceptions "$EXC" --wait-ms 500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  run returned W-2209 $W
  run received W-2211 $W
done
cat "$OUT/scores.txt"
