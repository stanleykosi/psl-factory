#!/bin/bash
# Production build of the F-14 worktree on 4501 with the contract mock on 4502 (no dev overlay).
L=${FID_LOGS:-/tmp}
for p in 4501 4502; do lsof -nP -iTCP:$p -sTCP:LISTEN -t; done | sort -u | xargs kill 2>/dev/null; sleep 1
cd /Users/Hunchoo/psl-factory-worktrees/f-14/frontend
API_ORIGIN=http://127.0.0.1:4502 NEXT_TELEMETRY_DISABLED=1 npm run build > $L/f14-build.log 2>&1 || { echo BUILD FAILED; tail -30 $L/f14-build.log; exit 1; }
(MOCK_PORT=4502 nohup node mock/server.mjs > $L/f14-mock.log 2>&1 &)
(API_ORIGIN=http://127.0.0.1:4502 NEXT_TELEMETRY_DISABLED=1 nohup npx next start -p 4501 > $L/f14-start.log 2>&1 &)
for i in $(seq 1 60); do curl -s -o /dev/null http://localhost:4501/my-work && break; sleep 1; done
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4501/work/W-1701
