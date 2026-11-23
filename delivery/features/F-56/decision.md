RECOMMENDATION: ESCALATE
COMMIT: abf2482a0bbc656b975f1f1afda722df6cdf7941
APPROVER: approver

## Summary
- The code change is small and matches the scope. It deletes FactoryDesk, removes the `native` branch from AppShell, and cuts next.config.ts down to /api/v1, six download routes and the mock reset. Tests were added for the rewrite set and for the shell.
- The final round's gate, QA, security, technical, UI and UX reviews and PMO acceptance all PASS and name head abf2482a.
- Readiness risk is medium, with surfaces ui, infra and security. Merge policy auto-merges only low risk.
- The diff against base 9bac3109 is 31 files, over the 15-file limit. It includes architecture/packages/v8/* and architecture/sources/*, which are always-human paths.
- The project rule is that merges into main need the design engineer's word.

## Why
The F-56 change itself looks sound and well reviewed. The PR also carries the architecture v8 package and decision records (D-API-STYLE r3, D-AUTH r3, D-172), which sit on an always-human path. It changes the proxy and infra surface, and the target is main. A person should confirm those before merge.

## Acceptance criteria
1. Shell always draws our frame (FactoryDesk removed): met. The diff shows the file deleted and the AppShell guard removed. PMO acceptance and QA both PASS.
2. Proxy forwards only /api/v1 and the six download routes, with no catch-all: met. The diff of next.config.ts and the new next-config.test.ts pin this. Security review PASS.
3. Mock mode still works and nothing else in the frame changes: met per the gate and QA at this head. I did not rerun the tests myself.
I did not enumerate all 12 spec criteria one by one. The reviewers' PASS verdicts at this head cover them.

## For the human
Decision needed: do you approve merging PR #96 into main? That includes the architecture v8 package and decision records (D-172, D-API-STYLE r3, D-AUTH r3) and removing the Django proxy fallbacks.
Files to look at:
- /Users/Hunchoo/psl-factory/frontend/next.config.ts
- /Users/Hunchoo/psl-factory/frontend/src/shell/AppShell.tsx
- /Users/Hunchoo/psl-factory/architecture/sources/decisions-2026-11-23.md
- /Users/Hunchoo/psl-factory/delivery/OVERNIGHT-DECISIONS.md
Also confirm that the architecture v8 files belong in this PR rather than a separate one.
