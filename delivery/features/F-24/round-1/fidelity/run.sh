#!/bin/bash
# F-24: scores the 8 SCR-05 boards (4 desktop at 1440, 4 phone at 390). The mock is reset before each board.
# Usage: run.sh [exceptions.json] [out-dir]   (app on 4770, mock on 4771, serve-frozen.mjs on 4772)
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-24/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-24/round-1/fidelity}
PW=/Users/Hunchoo/psl-factory-worktrees/f-24/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
ASSETS=/Users/Hunchoo/psl-factory/design/mascots/canvas-assets.json
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board-suffix page width viewport-name
  local name="SCR-05-$4$1-$3"
  curl -s -X POST http://127.0.0.1:4771/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/SCR-05-$4$1.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=pm \
    --assets "$ASSETS" --exceptions "$EXC" --wait-ms 500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  run "" "http://localhost:4770/assistant" $W "$V"
  run "-working" "http://localhost:4770/assistant/CV-2405" $W "$V"
  run "-thread" "http://localhost:4770/assistant/CV-2401" $W "$V"
  run "-draft-started" "http://localhost:4772/frozen/draft-started-$W.html" $W "$V"
done
cat "$OUT/scores.txt"
