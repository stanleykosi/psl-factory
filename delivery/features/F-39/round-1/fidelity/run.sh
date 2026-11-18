#!/bin/bash
# F-39: scores the 8 SCR-51 part-1 boards (investigating, decide, not-escalated, draft; desktop at 1440, phone at 390) on the live pages.
# App on 4937 (production build, API_ORIGIN=http://127.0.0.1:4936 FRAME_FIXTURES=1), mock on 4936, persona pm.
WT=/Users/Hunchoo/psl-factory-worktrees/f-39
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-39/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-39/round-1/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=$WT/design/canvas/project
mkdir -p "$OUT"
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board-suffix item width
  local V=desktop; [ $3 = 390 ] && V=mobile
  local board="SCR-51-$V$1"
  local name="$board-$3"
  curl -s -X POST http://127.0.0.1:4936/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$board.dc.html" --page "http://localhost:4937/work/$2" --width $3 --cookies psl_mock_persona=pm \
    --exceptions "$EXC" --wait-ms 1500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  run "-investigating" W-3601 $W
  run "-decide" W-3602 $W
  run "-not-escalated" W-3603 $W
  run "-draft" W-3604 $W
done
cat "$OUT/scores.txt"
