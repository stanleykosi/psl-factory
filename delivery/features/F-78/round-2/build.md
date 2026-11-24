STATUS: READY
COMMIT: ca4abee2fb0b22e6aca06c61e643eba2ae8fb02f
BUILDER: builder
LANE: frontend

## Summary
- Round 2 fixes the round-1 findings: board header colours, Project field, flat phone layout, no evidence under a hold, PDF-only upload, file tick bound to the file, and the missing tests.
- Behaviour is otherwise as round 1 (write after the re-read, 409 keeps input, uncertain never resent).
- LB-2 stays open (server PMO Lead enforcement unconfirmed); the UI follows `can_complete` only.
- fidelity-exceptions.json written for F-78; items without an earlier approval say "pending design engineer (questions-batch B36)". No visual waiver proposed.

## Changes
- `src/features/workspace/EvidencePicker.tsx` (lane C file, own commit): optional `accept`, `label`, `describeError` props; defaults unchanged, so other callers are unaffected.
- `MilestoneComplete.tsx`, `useMilestoneComplete.ts`, `milestone-complete.css`: see Fixes.
- `tests/milestone-complete.test.tsx`: 17 new cases.
- `/Users/Hunchoo/psl-factory-main/delivery/features/F-78/fidelity-exceptions.json`.

## Fixes
- UI-1-1 | ca4abee2 | desktop card uses the dark head (Panel darkHead), "What happens next" is an agent panel with the blue --action header
- UI-1-2 | ca4abee2 | read-only Project field and bordered Milestone field (project name from useProject)
- UI-1-3 | ca4abee2 | phone is flat: milestone name as 22px h1, project line, no breadcrumb, no cards, short next line, bar with 120px bottom padding
- UI-1-4 / UX-1-1 | ca4abee2 | radios and PDF zone only when can_complete; under proof_required only the PDF zone (spec)
- TECH-1-1 | ca4abee2 + EvidencePicker commit | accept `.pdf` only, label "Or upload a private PDF", 413/415 spec wording; a PNG is refused before any request
- TECH-1-2 | ca4abee2 | the file tick clears whenever the file changes or is removed
- TECH-1-3 | ca4abee2 | tests added: 401 on write, options 404/500, 409 keeps PDF and ticks, proof-gone note, not-recorded keeps input, Recorded wording and allowed-request list (includes GET /projects/{id}, a spec amendment for the breadcrumb/Project field)
- TECH-1-4 | ca4abee2 | stays busy until the 409 reload settles; a failed reload says so
- TECH-1-5 | ca4abee2 | 422/400 show the field message or the spec fallback only
- TECH-1-8 | ca4abee2 | 401 on the re-read after a 201 shows "We saved your completion…" above the sign-in prompt
- SEC-1-2 | ca4abee2 | test asserts X-CSRFToken on the POST

## Left as is
- TECH-1-6 (destination check, blocked by the cash-forecast guard), UX-1-2 (wording waits on LB-2), SEC-1-1 (backend), TECH-1-7 (LB-2), UI-1-5 (no-access card size, non-blocking, not done).
- AC 10 uses a short real wait, not a 60 s fake-timer advance: the code has no timer.

## Validation
- `npx tsc --noEmit -p .` and `npx eslint` on touched paths: clean.
- `npx vitest run tests/milestone-complete.test.tsx tests/mock-live-milestone-complete.test.ts tests/cash-forecast.test.tsx`: 104 passed (the 3 failures from my first run were test-harness bugs, fixed; the 44 in milestone-complete re-run passed).
- Fidelity tool and a browser check were not re-run (no servers, one run per round); phone/desktop look is by the board's tokens and tests.
- Not run: full suite, milestones.test.tsx (tab untouched this round).
