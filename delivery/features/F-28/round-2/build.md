STATUS: READY
COMMIT: cc694876c715f0c927f3879491eb9ede706c4f31
BUILDER: builder
LANE: full

## Summary
- Contract mock only: nothing is sent, filed or created; test template; D-LINE-WORKSPACE proposed. Round 1's limits all stand (see round-1/build.md).
- Round 2 fixes UI-1-1 and UI-1-2 and adds the missing fidelity exceptions (UI-1-3).
- Fidelity: mobile-published now passes (92.1). The other three boards are 76.9, 89.0 and 81.5 with coverage 100 after exceptions; the D-83 waivers stay pending the design engineer.

## Changes
- `workspace/Links.tsx`: the `project_tab` link is drawn as `<Link className="psl-btn psl-btn--secondary">` (still a link); the assistant link is unchanged.
- `workspace/Sections.tsx`: each table cell carries `data-label`; a table with a `tag` column gets `ws-table--stack`.
- `workspace/workspace.css`: at phone width a `ws-table--stack` table stacks every cell with its column label (ACTION, OWNER, DUE, STATE); no sideways scroll. Tokens only. Scope: tables with a state-tag column, that is the F-28 actions tables, W-2313 (labels added to its existing stack) and F-17's W-2002; no F-23 table has a tag column, so F-23 tables are unchanged. Full vitest (2138) and the F-28 axe e2e pass.
- Tests: component test asserts the button-link class and the labels; e2e at 390 asserts the table frame does not scroll sideways and DUE/STATE labels exist.

## Fixes
- UI-1-1 | cc694876c715f0c927f3879491eb9ede706c4f31 | Open actions is the outlined button-link
- UI-1-2 | cc694876c715f0c927f3879491eb9ede706c4f31 | phone actions table stacked with visible labels, nothing cut off
- UI-1-3 | (factory file, uncommitted) | exceptions added for Open actions (C6), Next sentence (C8), sentence panel (C7), Journey tab (C11)

## Left as is
- TECH-1-1: by spec (Conflicts 2), the backend's G-SCR25-1 rule; recorded in BACKEND-HANDOFF.
- TECH-1-2: owner-assignment step stays flagged "keep or drop" for the design engineer or backend.
- UX-1-1: fixed by UI-1-1.
- UX-1-2: frame copy of F-17, outside this lane.
- UX-1-3: reconcile lock-first order is intended; note only.
- Stacked tags span the cell width on phones (cosmetic); not changed to avoid another fidelity run.

## Acceptance criteria
Unchanged from round 1 except: AC 2 phone-published now passes outright (92.1). Open: waivers for 76.9, 89.0, 81.5.

## Validation
- `tests/minutes-end.test.tsx` 42 pass; `npx vitest run` full: 2138 pass.
- `E2E_PORT=4792 MOCK_PORT=4791 npx playwright test e2e/minutes-end.spec.ts`: pass (W-2313 rerun after a label-count fix).
- Fidelity (production build): round-2/fidelity/scores.txt.
- `delivery/checks.sh` under the lock: two runs failed on one test, tests/start-work.test.tsx "422: the missing milestone is named inline ... focus moves there" (focus assertion, unrelated file). It passes alone (twice), with the workspace subset on the base stash, and in a full `npx vitest run` (2138 pass). It looks like a load-dependent flake in checks.sh; not caused by this change as far as I can show. The gate may need a rerun.

## Blocked
Not blocked.
