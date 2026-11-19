#!/bin/bash
# F-43: scores the 8 SCR-56 part-1 boards (investigating, review, uncertain, verified; desktop at 1440, phone at 390) on the live pages.
# App on 4895 (production build, API_ORIGIN=http://127.0.0.1:4894 FRAME_FIXTURES=1), mock on 4894 reset before each board, persona finance_lead.
# Usage: run.sh <exceptions.json> <out-dir>
WT=/Users/Hunchoo/psl-factory-worktrees/f-43
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-43/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-43/round-1/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=$WT/design/canvas/finance/project
mkdir -p "$OUT"
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board-suffix item width
  local V=desktop; [ $3 = 390 ] && V=mobile
  local board="SCR-56-$V$1"
  local name="$board-$3"
  curl -s -X POST http://127.0.0.1:4894/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$board.dc.html" --page "http://localhost:4895/work/$2" --width $3 --cookies psl_mock_persona=finance_lead \
    --exceptions "$EXC" --wait-ms 1500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  run "-investigating" W-4001 $W
  run "-review" W-4002 $W
  run "-uncertain" W-4003 $W
  run "-verified" W-4004 $W
done
cat "$OUT/scores.txt"
