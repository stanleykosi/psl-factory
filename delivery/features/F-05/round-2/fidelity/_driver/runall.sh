#!/bin/bash
# Round 2: runs the fidelity driver on every SCR-04 board in scope at 1440 and 390 against the built page.
D=$(cd "$(dirname "$0")" && pwd)
B=/Users/Hunchoo/psl-factory-worktrees/f-05/design/canvas/project
PW=/Users/Hunchoo/psl-factory-worktrees/f-05/frontend/node_modules/playwright/index.mjs
OUT=${OUT:-$D/../}
EXC=${EXC:-/Users/Hunchoo/psl-factory/delivery/features/F-05/fidelity-exceptions.json}
PAGE=${PAGE:-http://localhost:3501/my-work}
for dev in ${DEVS:-desktop mobile}; do
 W=1440; [ $dev = mobile ] && W=390
 for st in "" lines validation weekly minutes issue change incident escalation leadership; do
  name=SCR-04-$dev${st:+-$st}
  printf '%s ' "$name-$W"
  FID_STATE=$st node $D/fid-driver.mjs --playwright $PW --board $B/$name.dc.html --page $PAGE --width $W --cookies psl_mock_persona=pm --actions $D/act.mjs --exceptions $EXC --wait-ms 800 --out $OUT/$name-$W 2>&1 | grep -v '^report:' | head -1
 done
done
