#!/bin/bash
# F-38: scores the 8 SCR-40 boards (draft, review, submitted, submitted-portal; desktop 1440, phone 390) on the live pages.
# App on 4985 (production build, API_ORIGIN=http://127.0.0.1:4984), mock on 4984, persona pm.
WT=/Users/Hunchoo/psl-factory-worktrees/f-38
EXC=/Users/Hunchoo/psl-factory/delivery/features/F-38/fidelity-exceptions.json
OUT=/Users/Hunchoo/psl-factory/delivery/features/F-38/round-2/fidelity
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() {
  local V=desktop; [ $3 = 390 ] && V=mobile
  local board="SCR-40-$V$1"; local name="$board-$3"
  curl -s -X POST http://127.0.0.1:4984/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$board.dc.html" --page "http://localhost:4985/work/$2" --width $3 --cookies psl_mock_persona=pm \
    --exceptions "$EXC" --wait-ms 1500 --out "$OUT/$name" > "$OUT/$name.out" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  run "-draft" W-3501 $W; run "-review" W-3502 $W; run "-submitted" W-3503 $W; run "-submitted-portal" W-3504 $W
done
cat "$OUT/scores.txt"
