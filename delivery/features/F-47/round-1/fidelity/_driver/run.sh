#!/bin/bash
# F-47 round 1: scores the 8 SCR-04 proof boards (minutes, change, schedules, ledger; desktop 1440, phone 390) on a
# production build: app on 4941 (API_ORIGIN=http://127.0.0.1:4940 FRAME_FIXTURES=1), mock on 4940.
WT=/Users/Hunchoo/psl-factory-worktrees/f-47
D=$(cd "$(dirname "$0")" && pwd)
EXC=${1:-/Users/Hunchoo/psl-factory/delivery/features/F-47/fidelity-exceptions.json}
OUT=${2:-$D/..}
PW=$WT/frontend/node_modules/playwright/index.mjs
B=$WT/design/canvas/project
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  for st in minutes change schedules ledger; do
    P=pm; { [ $st = schedules ] || [ $st = ledger ]; } && P=finance_lead
    name=SCR-04-$V-$st
    curl -s -X POST http://127.0.0.1:4940/__mock/reset > /dev/null
    FID_STATE=$st node $D/fid-driver.mjs --playwright $PW \
      --board "$B/$name.dc.html" --page http://localhost:4941/my-work --width $W --cookies psl_mock_persona=$P \
      --actions $D/act.mjs --exceptions "$EXC" --wait-ms 800 --out "$OUT/$name-$W" > "$OUT/$name-$W.log" 2>&1
    python3 - "$OUT/$name-$W/report.json" "$name-$W" "$W" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
  done
done
cat "$OUT/scores.txt"
