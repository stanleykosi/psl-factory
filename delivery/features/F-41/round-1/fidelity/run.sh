#!/bin/bash
# F-41: scores the four boards on the production build (app on 4951, mock on 4950), live URLs, each after POST /__mock/reset.
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-41/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-41/round-1/fidelity}
PW=/Users/Hunchoo/psl-factory-worktrees/f-41/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory-worktrees/f-41/design/canvas/finance/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board page width
  local name="$1-$3"
  curl -s -X POST http://127.0.0.1:4950/__mock/reset
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$1.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=finance_lead \
    --exceptions "$EXC" --wait-ms 800 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
run SCR-20-desktop "http://localhost:4951/finance/payments?status=issued" 1440
run SCR-20-mobile "http://localhost:4951/finance/payments?status=issued" 390
run SCR-32-desktop "http://localhost:4951/work/W-3801" 1440
run SCR-32-mobile "http://localhost:4951/work/W-3801" 390
cat "$OUT/scores.txt"
