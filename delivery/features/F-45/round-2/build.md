STATUS: READY
COMMIT: 777f266846484b7d022ba703d9a180cb234e1d12
BUILDER: builder
LANE: full

## Summary
- Option B (D-125): on the verified ledger state the re-check sentence is now sent as `workspace.next`, so the frame draws it in the side column under "Next", as the SCR-58 desktop verified board shows.
- Fixture data only (W-4204, W-4203.approve); no frame change.
- The "NOT approved: replaced by Option B" exception was removed from fidelity-exceptions.json (main repo); all other entries unchanged.
- BACKEND-HANDOFF.md F-45 section now says the backend sends the sentence as `workspace.next`.

## Changes
- frontend/mock/fixtures/work/W-4204.json, W-4203.approve.json: removed the untitled `recheck` text section; added `next: [sentence]`.
- frontend/tests/ledger-source.test.tsx: the W-4204 test asserts the sentence is in the side area under a "Next" heading and not in a main section.
- delivery/BACKEND-HANDOFF.md: Re-check (G-58-5) line.

## Fixes
- UI-2 | Option B: the re-check sentence sent as workspace.next | 777f2668

## Acceptance criteria
1. [x] Verified state shows the sentence in the Next area: unit test plus both verified fidelity runs (no layout gap left).
2. [x] Phone verified board reads right: phone run coverage with exceptions 100, visual 84.4 (was 75.9).

## Validation
- delivery/checks.sh under the shared lock: exit 0, 2882 tests passed.
- e2e/ledger-source.spec.ts on 4955/4954: 37 passed.
- Fidelity, one run of the two verified boards only (round-2/fidelity/): desktop 1440 coverage 92.9, with exceptions 100, visual 87 (was 74.1); phone 390 coverage 80, with exceptions 100, visual 84.4 (was 75.9). Both are under 90 but above their existing signed visual waivers (80.5 and 78.2). Other six boards not re-run; the change touches only W-4204.
- Demo running on 4955 (app) and 4954 (mock), production build.
