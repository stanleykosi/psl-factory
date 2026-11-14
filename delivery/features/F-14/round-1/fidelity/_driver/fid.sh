#!/bin/bash
# usage: fid.sh <board> <width> <persona> <path> <outroot>
D=$(cd "$(dirname "$0")" && pwd)
B=$1; W=$2; P=$3; U=$4; R=$5
EX=/Users/Hunchoo/psl-factory/delivery/features/F-14/fidelity-exceptions.json
args=(--cookies "psl_mock_persona=$P" --actions $D/act-wait.mjs)
[ -f "$EX" ] && args+=(--exceptions "$EX")
OUT=$R/$B-$W; mkdir -p $R
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs --playwright /Users/Hunchoo/psl-factory-worktrees/f-14/frontend/node_modules/playwright/index.mjs --board /Users/Hunchoo/psl-factory/design/canvas/project/$B.dc.html --page "http://localhost:4501$U" --width $W "${args[@]}" --wait-ms 500 --out $OUT > $OUT.log 2>&1
echo "$B $W exit=$? $(python3 -c "import json;d=json.load(open('$OUT/report.json'));print(d['pass'],d['scores'])" 2>/dev/null)"
