#!/bin/bash
S=/private/tmp/claude-501/-Users-Hunchoo-psl-factory/a400a30b-92cb-4efc-99c2-4a72d08a67f7/scratchpad
for p in 3301 3302; do lsof -nP -iTCP:$p -sTCP:LISTEN -t; done | sort -u | xargs kill 2>/dev/null
pkill -f "psl-factory-worktrees/f-02/frontend/scripts/dev.mjs"; sleep 2
cd /Users/Hunchoo/psl-factory-worktrees/f-02/frontend
API_ORIGIN=http://127.0.0.1:3302 NEXT_TELEMETRY_DISABLED=1 npm run build > $S/build.log 2>&1 || { echo BUILD FAILED; exit 1; }
(MOCK_PORT=3302 nohup node mock/server.mjs > $S/mock.log 2>&1 &)
(API_ORIGIN=http://127.0.0.1:3302 NEXT_TELEMETRY_DISABLED=1 nohup npx next start -p 3301 > $S/start.log 2>&1 &)
for i in $(seq 1 60); do curl -s -o /dev/null http://localhost:3301/my-work && break; sleep 1; done
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3301/my-work
