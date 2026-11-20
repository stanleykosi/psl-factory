#!/bin/bash
# F-51 round 1: scores the 4 SCR-04 boards (ppe and forecast, desktop 1440 and phone 390) on a production build:
# app on 4965 (API_ORIGIN=http://127.0.0.1:4964 FRAME_FIXTURES=1), mock on 4964. One run.
WT=/Users/Hunchoo/psl-factory-worktrees/f-51
D=$(cd "$(dirname "$0")" && pwd)
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-51/fidelity-exceptions.json}
OUT=${2:-$D/..}
PW=$WT/frontend/node_modules/playwright/index.mjs
B=$WT/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
for LINE in ppe forecast; do
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  name=SCR-04-$V-$LINE
  curl -s -X POST http://127.0.0.1:4964/__mock/reset > /dev/null
  FID_LINE=$LINE node $D/fid-driver.mjs --playwright $PW \
    --board "$B/$name.dc.html" --page http://localhost:4965/my-work --width $W --cookies psl_mock_persona=finance_lead \
    --actions $D/act.mjs --exceptions "$EXC" --visual-height union --wait-ms 800 --out "$OUT/$name-$W" > "$OUT/$name-$W.log" 2>&1
  python3 - "$OUT/$name-$W/report.json" "$name-$W" "$W" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
done
done
cat "$OUT/scores.txt"
