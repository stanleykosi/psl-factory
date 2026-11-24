#!/bin/bash
# F-71 round 1: the one fidelity run, production build, next start 4970, mock 4971, persona finance_lead, no exceptions applied.
OUT=/private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/fid2
PW=/Users/Hunchoo/psl-factory-worktrees/lane-b/frontend/node_modules/playwright/index.mjs
FT=/Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs
B=/Users/Hunchoo/psl-factory-main/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board page width cookies
  node $FT --playwright $PW --board "$B/$1.dc.html" --page "$2" --width $3 --cookies "$4" --exceptions /Users/Hunchoo/psl-factory-main/delivery/features/F-71/fidelity-exceptions.json --wait-ms 12000 --out "$OUT/$1" > "$OUT/$1.log" 2>&1
  python3 - "$OUT/$1/report.json" "$1" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
P=psl_mock_persona=finance_lead
run SCR-12-desktop "http://localhost:4970/projects/P-0101/money?figure=kickoff" 1440 $P
run SCR-12-mobile "http://localhost:4970/projects/P-0101/money" 390 $P
run SCR-38-desktop "http://localhost:4970/projects/P-0101/milestones" 1440 $P
run SCR-38-desktop-changed "http://localhost:4970/projects/P-0101/milestones" 1440 $P,psl_mock_milestones=changed
run SCR-38-mobile "http://localhost:4970/projects/P-0101/milestones" 390 $P
run SCR-38-mobile-changed "http://localhost:4970/projects/P-0101/milestones" 390 $P,psl_mock_milestones=changed
cat "$OUT/scores.txt"
