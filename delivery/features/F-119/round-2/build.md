STATUS: READY
COMMIT: f39d6dda8b095d99f19a3f9c809a2c97b71eba27
BUILDER: builder
LANE: full

## Summary
- Merged origin/main (8692cf87, D-199) keeping both sides of `mock/server.mjs` (F-119 routes plus F-85/F-86 routes) and `src/api/types.ts` (F-119 aliases plus F-85 types); `node --check` and `tsc` clean. Merge commit f421b8e6.
- TECH-1-1: a 422 the page cannot place on a control now shows as a message above the button in both forms; "Check the highlighted fields." is gone.
- UI-1-1 to UI-1-4: layout moved to the board (no panel title bar, Save straight after the notes file at 300x50, full width on phone, board chip colours, phone box cards, 22px phone title, no resize grip).
- TECH-1-2, 1-3, 1-4 fixed; fidelity-exceptions.json written for the spec-hidden and accepted parts.

## Changes
- `failure.ts` (new): `failureOf` moved out of the hook, unplaced 422 fields kept under `other`, `generalMessage(failure, drawn)`.
- `FailureNotice.tsx` (new): one notice for both forms (general 422 text, sign-in link after a 401, plain sentence otherwise).
- `RetroForm.tsx`: order is When/Reference, boxes, who took part, notes file, Save, then the optional Decisions block; Save is `.retro__save`.
- `ActionForm.tsx`: Owner now shows its server error; uses `FailureNotice`.
- `RetrospectiveView.tsx`: form panel has no header (aria-label only); page title phone size 22.
- `ChecklistStrip.tsx`: tones Closed/Recorded/Current green, Not yet orange-red (person), Unknown amber (waiting), Unavailable grey.
- `retrospective.css`: no textarea resize grip, Save width, phone box cards.
- `useRetrospective.ts`: after a 201, a failed re-read is "not confirmed" (never "Try again shortly"); action create re-reads the detail on an unconfirmed failure.
- `mock/retrospective.mjs`, `e2e/retrospective.spec.ts`, `tests/retrospective-failure.test.ts`: tests for both forms.
- `delivery/features/F-119/fidelity-exceptions.json`: 28 entries, each "builder proposal, pending design engineer".

## Fixes
- TECH-1-1 | f39d6dda | 422 without a placed field shows a form-level Callout in the retrospective and follow-up forms; unit tests (`retrospective-failure.test.ts`) and two e2e tests (unmapped field on save; message-only 422 on action create)
- TECH-1-2 | f39d6dda | failure after the 201 is treated as unconfirmed and re-read
- TECH-1-3 | f39d6dda | create-action re-reads the actions on an unconfirmed failure
- TECH-1-4 | f39d6dda | 401 on either write shows the sign-in link
- TECH-1-6 | f39d6dda | e2e re-run after the toast change: 24 of 24 pass
- UI-1-1 | f39d6dda | Save placement and size
- UI-1-2 | f39d6dda | extra panel title removed
- UI-1-3 | f39d6dda | chip colours
- UI-1-4 | f39d6dda | phone cards, title size, resize grip
- UI-1-5 to UI-1-10 | f39d6dda | listed in fidelity-exceptions.json (not code)

## Left
- TECH-1-5 (say "held" instead of "saved" for the version date): left. The spec's wording is "saved" and the e2e asserts it; it is the meeting's `occurred_at`, so the design engineer may prefer "held".
- Criterion 21 (live Django) is still unchecked (no credentials).
- Fidelity not re-run this round (no production build here per D-199; one run is the reviewer's). Expect visual to rise from 79.7/78; the exceptions file covers the coverage items.

## Validation
- `node --check mock/server.mjs`; `npx tsc --noEmit`: no errors.
- `npx vitest run` on tests/retrospective-failure, -model, -summary: 49 passed. no-success-callouts earlier run passes; toast unchanged.
- Dev server 4992 + mock 4993: `playwright test e2e/retrospective.spec.ts`: 24 of 24 pass. Servers stopped by PID; ports free.
- eslint on my files clean. No build, full vitest or gate run (GitHub gate, D-199).

## Coordinator: D-202 (24 Nov)
The design engineer answered in chat, relayed by the main coordinator: LD-Q5 "Sign all". The 28 exceptions and two D-83 visual waivers (78.8 desktop, 76.6 phone) are signed in `fidelity-exceptions.json`, which settles UI-2-2. LD-Q6: "keep saved", so the strip keeps "(saved <date>)" (TECH-1-5).
