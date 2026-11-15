VERDICT: PASS
COMMIT: 4e8a8c7d75957adbc9de381887453e0e5e11ecf4
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- Extra round (D-47), diff 2892f00..4e8a8c7: merge of the v7 base, model.ts aliasing the generated v7 types, `usePhoneBack` adoption, the Tola avatar, small CSS line-height changes.
- `git diff origin/dlv-00-delivery-setup...HEAD` touches only F-07 files: `frontend/src/features/projects/**`, `frontend/src/app/projects/**`, `frontend/mock/projects.mjs`, `frontend/mock/fixtures/projects/**`, the two F-07 contract fixtures `E-PROJECT.json` and `E-PROJECTS.json`, the F-07 registration lines in `mock/server.mjs` (import, `M1_OPERATIONS`, one route line) and `tests/mock-contract.test.ts` (import, two `CONTRACT_BODY` entries), and F-07 tests. The merge kept both sides in both conflict files; the other features' registrations (alerts, exceptions, month-end, setup, evidence) are intact.
- model.ts: the types now come from `operations['E-PROJECTS']` and `operations['E-PROJECT']`. All runtime guards are kept (`textOf`, `countOf`, `nextMilestoneText`, `factsOf`, `factText`, `lineDetail`, `agentSummaryOf`, `isProjectList`, `isJourney`). An unknown fact or money value still returns undefined and shows "Not known"; it is never shown as 0. `buildProjectsQuery` still omits `status` for Active. No behaviour was lost.
- `usePhoneBack({ label: 'Projects', href: '/projects' })` is called before the early return for a user without Projects, so hook order is stable. The in-page back link is removed. Page code uses the frame helper rather than a copy.
- Avatar: `next/image` with `unoptimized`, `alt=""` and `aria-hidden`. The path is built from `agent.toLowerCase()`, and `agentSummaryOf` only accepts agents that are keys of `AGENT_NAMES`, so a response cannot choose an arbitrary image path.
- I ran the F-07 vitest files plus `mock-contract`, `api-schema-drift` and `shell`: 7 files, 271 tests passed. `round-3/checks.md` is for the earlier head 2892f00; the builder reports checks.sh passing on 4e8a8c7 (875 tests). I did not re-run the full gate.

## Findings
- TECH-3-1 | low | non-blocking | open
  - `build.md` says the contract-body stripping for projects in `mock-contract.test.ts` is gone. It is not. `tests/mock-contract.test.ts` still imports `contractBody as projectsBody` from `mock/projects.mjs` and strips the proposed fields from the E-PROJECTS and E-PROJECT bodies before validating. `mock/projects.mjs` header and `PROPOSED_FIELDS` still describe the fields as "not in the loaded contract (v6)". Since v7 is now the loaded contract, this strips fields the contract does define, so `mock-contract.test.ts` checks these two operations less strictly than it could.
  - Impact: none on behaviour. The full v7 body is still validated in `mock-projects.test.ts` (per the round-3 build), so coverage is not lost. Suggested fix, for a later round: delete `contractBody`, `PROPOSED_FIELDS` and the two `CONTRACT_BODY` entries, and correct the comment and the build note.

## Verified
- TECH-2-1 | verified | still holds after the type alias change; guard tests pass.
- TECH-2-2 | verified | `buildProjectsQuery` sends no `status` for Active; `closed` and `all` otherwise.
