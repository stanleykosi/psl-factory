#!/bin/bash
# F-23: scores the 8 SCR-28 boards (4 desktop at 1440, 4 phone at 390). App on 4761 (production build), mock on 4762,
# frozen pages on 4763. Usage: run.sh <exceptions.json> <out-dir>
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-23/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-23/round-1/fidelity}
PW=/Users/Hunchoo/psl-factory-worktrees/f-23/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # suffix page width viewport-name
  local name="SCR-28-$4$1-$3"
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/SCR-28-$4$5.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=pm \
    --exceptions "$EXC" --wait-ms 500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  if [ $W = 1440 ]; then DEF="http://localhost:4763/frozen/default-1440.html"; else DEF="http://localhost:4761/work/W-2301"; fi
  run "" "$DEF" $W "$V" ""
  run "-suggesting" "http://localhost:4761/work/W-2302" $W "$V" "-suggesting"
  run "-drafted" "http://localhost:4761/work/W-2303" $W "$V" "-drafted"
  run "-review" "http://localhost:4761/work/W-2304" $W "$V" "-review"
done
cat "$OUT/scores.txt"
