#!/bin/bash
# F-21: scores the 8 SCR-25 boards (4 desktop at 1440, 4 phone at 390). Usage: run.sh <exceptions.json> <out-dir>
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-21/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-21/round-1/fidelity}
PW=/Users/Hunchoo/psl-factory-worktrees/f-21/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # suffix page width viewport-name
  local name="SCR-25-$4$1-$3"
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/SCR-25-$4$5.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=pm \
    --exceptions "$EXC" --wait-ms 500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  run "" "http://localhost:4743/frozen/default-$W.html" $W "$V" ""
  run "-invalid" "http://localhost:4743/frozen/invalid-$W.html" $W "$V" "-invalid"
  run "-assembling" "http://localhost:4741/work/W-2203" $W "$V" "-assembling"
  run "-review" "http://localhost:4741/work/W-2204" $W "$V" "-review"
done
cat "$OUT/scores.txt"
