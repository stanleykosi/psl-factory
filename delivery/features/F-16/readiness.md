DECISION: READY
RISK: high
SURFACES: ui, security, payments
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-16 is FE-DECIDE only: a layout and design-fidelity rebuild of the merged decision page (F-04) to its approved SCR-03 boards at 1440 and 390 (D-26). It is conformance work to boards the client already approved (design/review.json lists SCR-03, approved 13 Nov), so product acceptance is not required.
- Gates are met. FE-DECIDE is in architecture v7 with "Unresolved gates: none" (delivery.md:985-1015), F-04 is merged, and the frame back-link slot (`usePhoneBack`, PR #17, D-28) and F-05/F-09/F-14 are merged. No business rule is open. `design.py check` was not run (my role has no shell), so the spec writer or builder must run it first and stop if it fails.
- Risk is high, only because of what the files touch. `frontend/src/features/decide/**` holds the claim and decide writes (CSRF, `expected_revision`, 409 stale flow, no retry, note rules) that approve money-relevant work. The rebuild is layout only. A change to any of that behaviour fails the feature.
- The payment-exception, CEO costing and CTO emergency boards are out. FE-DECIDE-VARIANTS is gated on the open D-DECISION-VARIANTS. The spec must list them as excluded and must not build them.
- Overlap is manageable. F-15 (alert bell) edits `src/shell/**` and F-16 must not. F-14's work item page imports `DecisionRows` and `AmountValue` from `features/decide/DecisionContent.tsx`, so F-16 keeps those exports and their output stable.

## Scope
**Outcome (one):** the decision page matches the SCR-03 boards for the standard decision: 100% element coverage after approved exceptions and visual >= 90 at 1440 and 390, on the contract mock, with decide and claim behaviour unchanged.

**Boards (scored by the fidelity gate), desktop and mobile each:**
- `SCR-03-desktop` and `SCR-03-mobile` (default).
- `SCR-03-*-done`, `SCR-03-*-stale`, `SCR-03-*-not-yours`.
- `design/canvas/finance/project/SCR-03-desktop-own` and `SCR-03-mobile-own` (prepared by you). Per `delivery/screen-coverage.md:106` these belong to FE-DECIDE.
- Total 10 boards. This is smaller than F-14's 26, so one PR.

**In:**
1. Rebuild `frontend/src/app/work/[id]/decide/**` and `frontend/src/features/decide/**` (`DecideView`, `DecidePanel`, `DecideStates`, `DecisionContent`, `decide.css`) to the boards, token variables only, using the existing v7-typed contract and mock.
2. Adopt `usePhoneBack` for the phone back link as the boards draw it, with 40px page titles. Phone bar and action bar placement follow the boards.
3. Lessons from F-14 (binding on the spec writer):
   - Up front, in the spec, list every place the spec would differ from a board, for the design engineer to see before the build. Each is an exception candidate in `delivery/features/F-16/fidelity-exceptions.json`, provisional until the design engineer signs it, as with F-14's.
   - Where a board draws something the API has no field for, build it from mock or locally typed data marked PROPOSAL and list it in build.md as a contract proposal. Never omit it. Known candidates from F-04 (PMO-0-4): the not-yours board's "Comment for the Finance Lead (optional)" and "Add comment", and the "Decisions 1 of 3" pager and "Next decision, 2 of 3". These have no endpoint. They must be drawn but inert or hidden-when-absent per the board, and never sent anywhere. The spec writer decides which, and must state that no new write is added.
   - Where the frame owns a difference (phone top bar) and holds a score under 90, use an exception, not a hack.
4. Update `tests/decide*.test.tsx` and `e2e/decide.spec.ts`. Add Playwright and axe at 390 and 1440 for the five states. Every changed assertion is listed in build.md with its reason.

**Binding "do not change" list (the reviewers check each):**
- E-TASK-CLAIM and E-TASK-DECIDE calls, the CSRF header, `expected_revision` set to the task revision, verdicts `approve | return | reject`, and no client retry.
- The 409 flow: keep the version shown, reload the work item, show the replaced and current versions, never auto-approve.
- Controls render only when `you_can_act` is true. Cannot-act views key only on `cannot_act_reason`. Eligibility is never derived from `/me` roles.
- Unknown amount shows "Unknown", never 0 or blank (INV-UNKNOWN). The note is required for return and reject and capped at 2000 characters. The sample label shows whenever `sample: true`.
- The same ApiError mapping for 401, 403, 404 and 422.
- Existing tests that assert these stay green. Any weakened assertion is a blocking finding.

**Out:**
- FE-DECIDE-VARIANTS boards: `SCR-03-*-payment-exception`, `-ceo-costing`, `-cto-emergency` (gated by D-DECISION-VARIANTS).
- Any backend, API, OpenAPI, `schema.d.ts` or `architecture/**` change. No new npm dependency. No mock handler change beyond new fixtures if a board needs them.
- The shell (`src/shell/**`, F-15's area), `my-work/**`, and the work item page's own layout (F-14).
- `revoke`, return semantics (D-RETURN), notifications, document review.

**Seam with F-14:** keep the exports `DecisionRows`, `AmountValue` (`DecisionContent.tsx`) and `formatClock` (`format.ts`) and their rendered output, because `WorkItemOverview.tsx:11` uses them in the decision card. If the board needs different rows, add a new component and leave those alone, or change them together with an updated `tests/work-item.test.tsx` and a note in build.md. F-14's decision card CSS (`work-item.css:162-179, 255-260`) is not F-16's.

**Seam with F-15:** F-15 adds the bell to `AppShell.tsx` `TopNav` and `PhoneBar`. F-16 does not edit `src/shell/**`. `usePhoneBack` is read through its existing API only. Whichever merges second merges the current base and re-runs `delivery/checks.sh`. The decision page's phone back link must still show after the bell lands, so the e2e/axe at 390 should be re-run after F-15 merges.

**Size:** 10 boards, one route, one component tree: one PR. If the builder cannot reach 90 on every state in the round limit, continue as a recorded extra round on the same branch (D-47 precedent), not a split.

**Task ID:** FE-DECIDE (R-DECIDE). **Endpoints:** E-WORK-ITEM (read), E-TASK-CLAIM, E-TASK-DECIDE on the contract mock, unchanged. **Acceptance:** A-DECIDE, A-STALE, A-NOT-YOURS and A-ACCESSIBILITY keep passing.

## Risk
High. The files rebuilt contain the only writes where a person approves, returns or rejects money-relevant work (F-04 readiness rated it high for INV-UNKNOWN amounts, INV-REVISION stale versions and separation of duties), so `payments` and `security` stay on the surfaces for the reviewers, and `ui` is the change itself. The change is layout only on the mock, and no API, auth or contract work, which is why no `api` or `contract-change` surface is listed. High risk means the security reviewer runs and the merge is not auto-delegated. The tests, which should fail on any behaviour change, are the main safeguard. Do not merge on a fidelity score alone.

## Questions
None.
