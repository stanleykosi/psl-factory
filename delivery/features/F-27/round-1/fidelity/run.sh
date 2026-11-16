#!/bin/bash
# F-27: scores SCR-13-desktop-delegation at 1440 (the frozen, driven page) and SCR-13-mobile-delegation at 390 (live).
# Usage: run.sh <exceptions.json> <out-dir>   (app on 4801, mock on 4802 with MOCK_DELEGATIONS_SCENARIO=default, frozen on 4803)
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-27/fidelity-exceptions.json}
OUT=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-27/round-1/fidelity}
PW=/Users/Hunchoo/psl-factory-worktrees/f-27/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board page width
  local name="$1-$3"
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$1.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=admin \
    --exceptions "$EXC" --wait-ms 500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
run SCR-13-desktop-delegation "http://localhost:4803/frozen/default-1440.html" 1440
run SCR-13-mobile-delegation "http://localhost:4801/setup/delegation" 390
cat "$OUT/scores.txt"
