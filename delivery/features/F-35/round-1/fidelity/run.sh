#!/bin/bash
# F-35: scores the 8 SCR-52 part-1 boards (drafting, review, tuesday, received; desktop at 1440, phone at 390) on the live pages.
# App on 4987 (production build, API_ORIGIN=http://127.0.0.1:4986 FRAME_FIXTURES=1), mock on 4986, persona ceo.
# Usage: run.sh <exceptions.json> <out-dir>
WT=/Users/Hunchoo/psl-factory-worktrees/f-35
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-35/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-35/round-1/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=$WT/design/canvas/project
mkdir -p "$OUT"
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board-suffix item width
  local V=desktop; [ $3 = 390 ] && V=mobile
  local board="SCR-52-$V$1"
  local name="$board-$3"
  curl -s -X POST http://127.0.0.1:4986/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$board.dc.html" --page "http://localhost:4987/work/$2" --width $3 --cookies psl_mock_persona=ceo \
    --exceptions "$EXC" --wait-ms 1500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  run "-drafting" W-3201 $W
  run "-review" W-3202 $W
  run "-tuesday" W-3203 $W
  run "-received" W-3204 $W
done
cat "$OUT/scores.txt"
