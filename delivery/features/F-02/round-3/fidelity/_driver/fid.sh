#!/bin/bash
# usage: fid.sh board width [extra-cookies] [url-suffix] [action]
S=/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad
B=$1; W=$2; C=$3; U=${4:-}; A=${5:-wait}
EX=/Users/Hunchoo/psl-factory/delivery/features/F-02/fidelity-exceptions.json
[ -n "$FIDEX" ] && EX=$FIDEX
args=(--cookies "psl_mock_worklist=board${C:+,$C}" --actions $S/act-$A.mjs)
[ -f "$EX" ] && args+=(--exceptions "$EX")
OUT=$S/f02-fid-$B-$W
node $S/fid-driver.mjs --playwright /Users/Hunchoo/psl-factory-worktrees/f-02/frontend/node_modules/playwright/index.mjs --board /Users/Hunchoo/psl-factory/design/canvas/project/$B.dc.html --page "http://localhost:3301/my-work$U" --width $W "${args[@]}" --wait-ms 500 --out $OUT > $OUT.log 2>&1
echo "$B $W exit=$? $(python3 -c "import json;d=json.load(open('$OUT/report.json'));print(d['pass'],d['scores'])")"
