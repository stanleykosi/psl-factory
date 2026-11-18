#!/bin/bash
# F-42: scores the 8 SCR-55 part-1 boards (investigating, register review, date review, calculating; desktop at 1440, phone at 390) on the live pages.
# App on 4969 (production build, API_ORIGIN=http://127.0.0.1:4968 FRAME_FIXTURES=1), mock on 4968, persona finance_lead.
# Usage: run.sh <exceptions.json> <out-dir>
WT=/Users/Hunchoo/psl-factory-worktrees/f-42
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-42/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-42/round-1/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=$WT/design/canvas/finance/project
mkdir -p "$OUT"
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board-suffix item width
  local V=desktop; [ $3 = 390 ] && V=mobile
  local board="SCR-55-$V$1"
  local name="$board-$3"
  curl -s -X POST http://127.0.0.1:4968/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$board.dc.html" --page "http://localhost:4969/work/$2" --width $3 --cookies psl_mock_persona=finance_lead \
    --exceptions "$EXC" --wait-ms 1500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  run "-investigating" W-3901 $W
  run "-register-review" W-3902 $W
  run "-date-review" W-3903 $W
  run "-calculating" W-3904 $W
done
cat "$OUT/scores.txt"
