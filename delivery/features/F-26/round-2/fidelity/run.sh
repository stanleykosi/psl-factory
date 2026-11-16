#!/bin/bash
# F-26 round 2: the one recorded fidelity run, SCR-12 desktop at 1440 and mobile at 390, on a production build
# (next start -p 4780, mock on 4781, persona finance_lead). Usage: run.sh
EXC=/Users/Hunchoo/psl-factory/delivery/features/F-26/fidelity-exceptions.json
OUT=/Users/Hunchoo/psl-factory/delivery/features/F-26/round-2/fidelity
PW=/Users/Hunchoo/psl-factory-worktrees/f-26/frontend/node_modules/playwright/index.mjs
FT=/Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs
B=/Users/Hunchoo/psl-factory/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board page width
  node $FT --playwright $PW --board "$B/$1.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=finance_lead \
    --exceptions "$EXC" --wait-ms 500 --out "$OUT/$1-$3" > "$OUT/$1-$3.log" 2>&1
  python3 - "$OUT/$1-$3/report.json" "$1" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
run SCR-12-desktop "http://localhost:4780/projects/P-0101/money?figure=FIG-0101-S2" 1440
run SCR-12-mobile "http://localhost:4780/projects/P-0101/money" 390
cat "$OUT/scores.txt"
