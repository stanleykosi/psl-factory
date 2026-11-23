#!/bin/bash
# F-62 round 1: scores SCR-10 and SCR-14 (desktop 1440, phone 390) on a production build:
# app on 4964 (API_ORIGIN=http://127.0.0.1:4965 FRAME_FIXTURES=1), mock on 4965. One run, persona finance_lead.
WT=/Users/Hunchoo/psl-factory-worktrees/lane-a
D=$(cd "$(dirname "$0")" && pwd)
EXC=${1:-}
OUT=${2:-$D}
PW=$WT/frontend/node_modules/playwright/index.mjs
B=$WT/design/canvas/project
TOOL=/Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
for S in SCR-10:exceptions SCR-14:verified; do
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  name=${S%%:*}-$V; route=${S##*:}
  ARGS=(--playwright $PW --board "$B/$name.dc.html" --page http://localhost:4964/$route --width $W --cookies psl_mock_persona=finance_lead --visual-height union --wait-ms 800 --out "$OUT/$name-$W")
  [ -n "$EXC" ] && ARGS+=(--exceptions "$EXC")
  node $TOOL "${ARGS[@]}" > "$OUT/$name-$W.log" 2>&1
  python3 - "$OUT/$name-$W/report.json" "$name-$W" "$W" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
done
done
cat "$OUT/scores.txt"
