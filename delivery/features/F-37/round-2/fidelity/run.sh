#!/bin/bash
# F-37: scores the 8 boards at 1440 and 390 on a production build. The four live boards run first (app 4995, mock 4994),
# then the mock is stopped, serve-frozen.mjs takes port 4994 and the four driver-frozen register and record boards run.
# Usage: run.sh <live|frozen> [exceptions.json] [out-dir]
MODE=$1
WT=/Users/Hunchoo/psl-factory-worktrees/f-37
EXC=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-37/fidelity-exceptions.json}
OUT=${3:-/Users/Hunchoo/psl-factory/delivery/features/F-37/round-2/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
mkdir -p "$OUT"
[ -f "$OUT/scores.txt" ] || printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board page width
  local name="$1-$3"
  [ "$MODE" = live ] && curl -s -X POST http://127.0.0.1:4994/__mock/reset > /dev/null
  node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright $PW \
    --board "$BOARDS/$1.dc.html" --page "$2" --width $3 --cookies psl_mock_persona=pm \
    --exceptions "$EXC" --wait-ms 500 --out "$OUT/$name" > "$OUT/$name.log" 2>&1
  python3 - "$OUT/$name/report.json" "$name" "$3" >> "$OUT/scores.txt" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); s=r['scores']
print(sys.argv[2],sys.argv[3],s.get('coverage'),s.get('coverageWithExceptions'),s.get('visual'),r.get('pass'),sep='\t')
PY
}
for W in 1440 390; do
  V=desktop; [ $W = 390 ] && V=mobile
  if [ "$MODE" = live ]; then
    D=desktop; [ $W = 390 ] && D=mobile
    run "SCR-26-$V" "http://localhost:4995/work/W-3401" $W
  else
    run "SCR-26-$V-review" "http://localhost:4994/frozen/SCR-26-$V-review-$W.html" $W
    run "SCR-26-$V-edit" "http://localhost:4994/frozen/SCR-26-$V-edit-$W.html" $W
    run "SCR-26-$V-reject" "http://localhost:4994/frozen/SCR-26-$V-reject-$W.html" $W
  fi
done
cat "$OUT/scores.txt"
