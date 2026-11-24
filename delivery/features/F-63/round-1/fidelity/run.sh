#!/bin/bash
# F-63 round 1: scores SCR-01 boards (desktop 1440, phone 390) on a production build:
# app on 4984 (API_ORIGIN=http://127.0.0.1:4985 FRAME_FIXTURES=1), mock on 4985. One run, finance_lead with the boards' own rows (psl_mock_worklist=board).
WT=/Users/Hunchoo/psl-factory-worktrees/lane-a2
D=$(cd "$(dirname "$0")" && pwd)
EXC=${1:-}
OUT=${2:-$D}
PW=$WT/frontend/node_modules/playwright/index.mjs
B=$WT/design/canvas/project
TOOL=/Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs
printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
for S in SCR-01-desktop:"" SCR-01-desktop-my-work:"queue=waiting" SCR-01-desktop-empty:"" SCR-01-mobile:"" SCR-01-mobile-my-work:"queue=waiting" SCR-01-mobile-empty:"" SCR-01-mobile-lead:""; do
  name=${S%%:*}; q=${S#*:}
  W=1440; case $name in *mobile*) W=390;; esac
  persona=finance_lead; case $name in *empty) persona=pm;; esac
  ARGS=(--playwright $PW --board "$B/$name.dc.html" --page "http://localhost:4984/my-work${q:+?$q}" --width $W --cookies psl_mock_persona=$persona,psl_mock_worklist=board --visual-height union --wait-ms 800 --out "$OUT/$name-$W")
  [ -n "$EXC" ] && ARGS+=(--exceptions "$EXC")
  node $TOOL "${ARGS[@]}" > "$OUT/$name-$W.log" 2>&1
  python3 - "$OUT/$name-$W/report.json" "$name-$W" "$W" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
done
cat "$OUT/scores.txt"
