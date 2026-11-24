STATUS: READY
COMMIT: 6636f0eb7b4ae40ec93e12d35c6e3a8b7b2d9753
BUILDER: builder
LANE: full

## Summary
- Root cause of UX-1-1, UI-1-1 and UI-1-2: my row classes (`delivery__row`, `delivery__title` and so on) collided with older, unused rules of the same names in `project-tabs.css`, which overrode my grid and padding. The tab now uses its own `dlvov__*` classes in the new `dlvov.css` (old `delivery.css` removed).
- Row layout now follows the board: number box, title with reference beneath, tag with "Updated <date>" beneath it on the right, inside the panel's 14px inset. Phone: one compact line (title, tag) with reference and date beneath; number box hidden as on the mobile board.
- The row title is now the link to `/work/{work_id}` (the API supplies the target). The separate "Open" link is removed, so spec AC3 ("click Open") is met by clicking the title; spec line 80-ish still says "Open" and should be reworded by the coordinator. The panel head is the board's "The six delivery lines, in order"; the spec does not word it differently.
- `fidelity-exceptions.json` written (proposal, pending design engineer). The fidelity re-run is NOT done (see Blocked).

## Changes
- `frontend/src/features/projects/DeliveryTab.tsx`, new `dlvov.css` (replaces `delivery.css`), `frontend/tests/delivery-tab.test.tsx`.
- `delivery/features/F-113/fidelity-exceptions.json`: 28 exceptions in F-14's format, each with `approved_by: "builder proposal, pending design engineer"` and a spec reason: the 3 OF 6 DONE tag and DLV-0052 (DC-3, D-182), Tola card and its texts, NEXT card, the Release to Closure sub-nav strip (Question 3 a, D-187), "Open the handover", the not-started Closure link, and frame items (breadcrumb with fixture project name, shell persona, PM tag, Planning tab from live tabs[]). `visual_waivers` is empty until the scores exist.

## Fixes
- UX-1-1 | tag and date no longer overlap; own class names | 6636f0eb
- UI-1-1 | same | 6636f0eb
- UI-1-2 | rows sit inside the panel body inset | 6636f0eb
- UI-1-3 | compact phone row (title and tag on one line) | 6636f0eb
- UI-1-4 | title is the link; board head wording | 6636f0eb
- UX-1-2 | closure reasons read "Title – finding" | 6636f0eb
- UX-1-3 | phone rows tightened (same change as UI-1-3) | 6636f0eb
- UI-1-5 | exceptions file written, pending design engineer | not a code commit

## Acceptance criteria
Unchanged from round 1 except AC3: the started row's title link goes to `/work/2501` (test updated). Targeted tests pass.

## Validation
- `npx vitest run tests/delivery-model.test.ts tests/delivery-tab.test.tsx tests/projects-journey.test.tsx tests/projects-model.test.ts`: 86 pass. `eslint` on the changed folders: clean.
- Full gate, full vitest: not run by me (coordinator queues the gate).
- Fidelity: not run.

## Blocked
Only the fidelity re-run. It needs a production build (`heavy-lock.sh run lane-d -- env API_ORIGIN=http://127.0.0.1:4991 npm run build`). The heavy-lock queue had 8 tickets ahead of mine (the oldest from 00:57Z) and the build had not started after about 30 minutes. The coordinator can run the tool after that build, on 4990/4991, with `--exceptions delivery/features/F-113/fidelity-exceptions.json`. The visual waivers (D-83) need the scores, so they are not written yet. A build ticket from lane-d may still be queued; it is harmless but will build `frontend/.next` when its turn comes. No servers of mine are running.
