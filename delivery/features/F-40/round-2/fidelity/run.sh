#!/bin/bash
# F-40: scores the 8 SCR-48 boards at 1440 and 390 on a production build. The six live boards run first (app 4975, mock 4974),
# then the mock is stopped, serve-frozen.mjs takes port 4974 and the two driver-frozen record boards run.
# Usage: run.sh <live|frozen> [exceptions.json] [out-dir]
MODE=$1
WT=/Users/Hunchoo/psl-factory-worktrees/f-40
EXC=${2:-/Users/Hunchoo/psl-factory/delivery/features/F-40/fidelity-exceptions.json}
OUT=${3:-/Users/Hunchoo/psl-factory/delivery/features/F-40/round-2/fidelity}
PW=$WT/frontend/node_modules/playwright/index.mjs
BOARDS=/Users/Hunchoo/psl-factory/design/canvas/project
mkdir -p "$OUT"
[ -f "$OUT/scores.txt" ] || printf 'board\twidth\tcoverage\twith-exceptions\tvisual\tpass\n' > "$OUT/scores.txt"
run() { # board page width
  local name="$1-$3"
  [ "$MODE" = live ] && curl -s -X POST http://127.0.0.1:4974/__mock/reset > /dev/null
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
    run "SCR-48-$V" "http://localhost:4975/work/W-3701" $W
    run "SCR-48-$V-gaps" "http://localhost:4975/work/W-3704" $W
    run "SCR-48-$V-received" "http://localhost:4975/work/W-3705" $W
  else
    run "SCR-48-$V-record" "http://localhost:4974/frozen/SCR-48-$V-record-$W.html" $W
  fi
done
cat "$OUT/scores.txt"
