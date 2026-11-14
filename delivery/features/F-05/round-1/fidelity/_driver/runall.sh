#!/bin/bash
S=/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad
B=/Users/Hunchoo/psl-factory-worktrees/f-05/design/canvas/project
PW=/Users/Hunchoo/psl-factory-worktrees/f-05/frontend/node_modules/playwright/index.mjs
for dev in desktop mobile; do
 W=1440; [ $dev = mobile ] && W=390
 for st in "" lines validation weekly minutes issue change incident escalation leadership; do
  name=SCR-04-$dev${st:+-$st}
  echo "== $name-$W"
  FID_STATE=$st node $S/fid-driver.mjs --playwright $PW --board $B/$name.dc.html --page http://localhost:3511/my-work --width $W --cookies psl_mock_persona=pm --actions $S/act.mjs --wait-ms 800 --out $S/fidout/$name-$W 2>&1 | grep -v '^report:'
 done
done
