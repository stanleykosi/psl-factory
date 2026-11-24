STATUS: READY
COMMIT: f29087ed4c453d75e2766dfa992956fcc94d9aab
BUILDER: builder
LANE: frontend

## Summary
- Round 2 fixes the UI and UX findings from round 1; no contract or data change.
- Money: each Paid and Owed figure stays on one line with its currency code; the side panel shows the prompt as its body before a figure is chosen.
- Unknown is bold brown text on Milestones (desktop and phone), same as Money. Unknown money stays Unknown, never 0, never summed.
- Escape closes the phone sheet; Proof buttons carry aria-expanded; both tabs have a section heading.
- `delivery/features/F-71/fidelity-exceptions.json` written from the spec's accepted hides only.

## Changes
- frontend/src/features/projects/MoneyCells.tsx: Paid and Owed each in a `money__fig` span.
- frontend/src/features/projects/money.css: `white-space: nowrap` on figures and amount links.
- frontend/src/features/projects/MoneyTab.tsx: idle panel head "Where a figure comes from" with the prompt as the body; hidden h2 "Billing by contract stage" (desktop and phone); document Escape listener while the phone sheet is open.
- frontend/src/features/projects/project-tabs.css: Unknown styled as plain bold text on the Milestones table and cards.
- frontend/src/features/projects/MilestonesTab.tsx: `aria-expanded` on Proof; hidden h2 "Contract milestones" ("Recorded completions" was already an h2; both tables already had captions).
- frontend/tests/money.test.tsx, milestones.test.tsx: one test per finding.

## Fixes
- UI-1-2 | cfc3c462 | figures unbreakable, Paid and Owed wrap only between the two
- UI-1-3 | cfc3c462 | prompt is the panel body, no empty box
- UI-1-4 | cfc3c462 | one Unknown style on Milestones
- UX-1-1 | cfc3c462 | Escape closes the phone sheet (the sheet's own handler needs focus inside it)
- UX-1-2 | cfc3c462 | hidden h2 on each tab
- UX-1-3 | cfc3c462 | aria-expanded on Proof
- UI-1-1 | not code | exceptions file written; fidelity not rerun (no one-run cost rule; coordinator/reviewer reruns)

## Acceptance criteria
1. [x] Unknown never 0, never summed: tests assert Paid Unknown / Owed Unknown and no zero pattern.
2. [x] Each UI/UX finding has a test (money.test.tsx "F-71 round 2", milestones.test.tsx "F-71 round 2").
3. [ ] Fidelity at 100% coverage and visual 90: not rerun here and not claimed; see exceptions below. Layout (nowrap, panel) was not checked in a browser; jsdom tests check structure and the CSS rule text only.

## Validation
- `npx tsc --noEmit`: clean. `npx eslint` on projects folder and both tests: clean.
- `npx vitest run tests/money.test.tsx tests/milestones.test.tsx`: 40 + 32 passed (first run; money rerun after removing one assertion: 40 passed).
- Gate not run (GitHub Actions, coordinator).

## Exceptions needing the design engineer
Written to fidelity-exceptions.json (spec items, D-182): Chidi card (3), report title eyebrow (3), INV-0398 and INV-0412 composed status (4), "Part paid · owed" word (1, 11), amount_note line (5), Mark milestone 3 complete (6), CR-0031 link (7).
Not listed, because the spec or answers do not cover them:
- UI-1-5: `NGN 3,000,000` against the board's `₦3,000,000` (spec assumption says currency code as text; no accepted exception recorded). Needs approval.
- Board sample values the live data does not carry (for example "Verified 03 Nov", "Awaiting Finance decision", "Held · owner needed", "Not yet due · amount set at go-live", "Finance tracks", source rows "Signed SOW v2 ...", stage names like "Stage 2 · UAT", "Tunde Bello · PMO", "Done 27 Oct · proof" wording, "CR-0031 added work..." note, "← Project" / "← Projects" back links, "Tap an amount..." link, lead sentence wording, "Where ₦4,250,000 comes from" head).
- Shell-owned differences (breadcrumb, Start work, user chip, tab counts) belong to F-70.
- Visual score under 90 may remain; layout gaps cannot be judged without a fidelity run.

## Coordinator sync before merge (D-193)
- f29087ed merges origin/main 4a88c26b, bringing in F-62 (#106), F-125 (#105), F-113 (#109) and #108, into the builder's cfc3c462. The one conflict was in frontend/mock/server.mjs: F-71's milestone-completion route and F-113's delivery-overview route are both kept, F-71's first. F-71's own diff and the sync share only server.mjs; the other projects-folder changes are F-113's Delivery tab. MoneyTab, MilestonesTab and their tests are unchanged. Typecheck is clean.
- D-200: F-71's own diff touches no protected path, so base_sha moved to 4a88c26b.
- ci-mode checks.sh PASS on f29087ed (GitHub Actions frontend-checks run, success). PR #114.
