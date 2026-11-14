STATUS: READY
COMMIT: 230edd60f366ea64a1a138dc66f2084bd447ebd1
BUILDER: builder
LANE: frontend

## Summary
- The "See the full journey" link now appears only when `journey_url` resolves to the page's own origin. The value is parsed with `new URL(value, window.location.origin)`. Any value that contains a control character (tab, newline and the like) or a backslash is refused before it is parsed (TECH-2-1).
- After a 422, the start button is greyed. A test now checks that it is greyed after the 422 and enabled again after a change (TECH-2-2). Problem boxes are keyed by name plus index. A 422 aimed at the disabled Proof box is drawn as its own box, not inline under the disabled control (TECH-2-4).
- The branch now includes origin/dlv-00-delivery-setup (merge a257dfa), which brings in the mascot images. The chooser's Tola avatar is now the mascot image instead of the letter "T" (UI-2-1).
- On the change line, the hint for "What the client asked for" is now drawn under the Proof box, as both SCR-04-change boards show it. It is still linked to the request box through `aria-describedby` (UI-2-3). "change line" is now regular weight, as the boards draw it.
- desktop-validation still scores 88.3 visual and is left as noted. The gap is the kept optional note field and help hint. The only fix that would close it is dropping them, which would drop required behaviour (spec.md:134, 178).

## Changes
- `frontend/src/features/start-work/LineForm.tsx`:
  - `safePath` is exported and does the following:
    - refuses any URL that contains a control character or a backslash;
    - resolves the URL against the page origin;
    - returns `pathname + search + hash` only when the origins match.
  - `ProblemBox` keys are now `${name}-${index}`.
  - `movedHelp()` moves a field's help to the proof box that comes straight after that field.
- `frontend/src/features/start-work/IntakeField.tsx`: adds a `movedHelp` prop. The owning field keeps the help's id in `aria-describedby` and does not draw the help. The proof box draws the text under itself.
- `frontend/src/features/start-work/intake.ts`: adds `fillable(field)`, which is true for the kinds this drawer renders as controls. It excludes the disabled proof box.
- `frontend/src/features/start-work/useStartWork.ts`: a 422 is matched inline only against fillable fields. Every other problem, including one for `proof`, goes to `unmatched`.
- `frontend/src/features/start-work/LineChooser.tsx`: the Tola avatar is `next/image` showing `/agents/tola.png` at 28px, with `alt=""`.
- `frontend/src/features/start-work/start-work.css`:
  - `object-fit: cover` on the Tola avatar;
  - `.sw-change` is weight 400, matching the boards' plain link.
- `frontend/tests/start-work.test.tsx`:
  - unit tests for `safePath`. Refused: `"/\t/evil.example"`, `"/\n/evil.example"`, `"//evil"`, `"/\\evil"`, `"https://evil"`, `javascript:` and empty. Kept: a same-origin path with query and hash, and an absolute same-origin URL.
  - the component `it.each` now also covers `/\t/` and `/\n/`.
  - a disabled/enabled assertion around the 422 retry.
  - a 422 test for a problem on the proof field and the same name twice.
  - a test that the change line's help sits under Proof and still describes the request box.
- Merge a257dfa: origin/dlv-00-delivery-setup, which brings in `frontend/public/agents/*.png` (PR #12) and delivery files.

## Fixes
- TECH-2-1 | 230edd6 | `journey_url` is resolved with `new URL` against the page origin and linked only when the origins match. Control characters and backslashes are refused. Unit tests and component tests cover tab, newline, `//`, backslash, another origin and a good path.
- TECH-2-2 | 230edd6 | The 422 test asserts `disabled === true` after the 422 and `false` after picking Milestone 3.
- TECH-2-4 | 230edd6 | Problem boxes are keyed by name plus index. A problem for the disabled proof field is drawn as its own box. Tested with proof plus a duplicate `billing_contact`.
- UI-2-1 | 230edd6 | The Tola avatar in the chooser is the mascot image (`/agents/tola.png`), after merging origin/dlv-00-delivery-setup (a257dfa).
- UI-2-3 | 230edd6 | The change line's hint is drawn under the Proof box, on phone and desktop, as both boards draw it.

Left this round:
- TECH-2-3 (backend, non-blocking) is kept. Handoff note for the backend and D-START-INTAKE (v7 proposal): `next.summary` parts are joined by `" · "`, and the drawer puts the decision after the first part. A summary without the separator still reads correctly, with the decision after the whole sentence.
- UI-2-2 (product, non-blocking): the only non-data difference I could close on the three sheet-drawn phone boards was the weight of "change line". The rest is outside F-05 or would drop behaviour:
  - the app-frame phone bar (D-08);
  - the real line count and the Tola box on the phone chooser, which the spec and tests require;
  - the kept help hint, optional note and Project field.
  I measured one more option: letting the error replace the help hint. It moved desktop-validation from 88.3 to 88.6 and dropped mobile-validation from 75.8 to 75.0, so I reverted it.
- TECH-1-1 and TECH-1-4 are unchanged (non-blocking, from round 1).

## Acceptance criteria
1. [x] Unsafe `journey_url` values are not linked: unit tests plus component `it.each` (7 values) pass. A same-origin path is still linked to `/projects` (existing desktop test).
2. [x] After a 422, the start button stays greyed until something changes, then a new key is sent: the 422 test checks disabled, enabled, and that the second POST uses a different `idempotency_key`.
3. [x] A 422 for an unrendered or disabled field becomes its own box, with no duplicate keys: the new test (3 boxes, none inline under the proof control).
4. [x] The Tola mascot shows in the chooser: the fidelity side-by-side at SCR-04-mobile-lines-390 shows the image in the "Not sure which line?" box.
5. [x] On the change line, the hint is drawn below Proof: component test, plus the SCR-04-mobile-change-390 side-by-side (hint under the Proof box, as on the board).
6. [x] All earlier F-05 criteria still hold: the full vitest suite (437) and e2e (93) pass.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-05 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0 at 230edd6 (16 files, 437 tests).
- `E2E_PORT=3501 MOCK_PORT=3502 npm run test:e2e` passed (93 tests). `frontend/test-results` was deleted afterwards.
- Fidelity re-run on all 20 SCR-04 boards, using the round-2 driver and `delivery/features/F-05/fidelity-exceptions.json`, against a build of the final code on :3501 with the mock on :3502. Coverage is 100% with exceptions on every board.
  - Desktop (visual): default 92.7, lines 92.9, weekly 96.2, minutes 94.7, issue 96.4, change 94.6, incident 95.5, escalation 94.5 and leadership 95.1 pass. validation is 88.3 and still fails (see above).
  - Phone (visual): default 86.2, lines 76.6, validation 75.8, weekly 85.3, minutes 77.9, issue 86.5, change 78.9, incident 78.9, escalation 78.6, leadership 76.3. The causes are the same as in round 2: the bottom sheet (D-02/D-16), the frame bar (D-08), and real data versus board samples.
  - The reports were written to the session scratchpad, not the feature folder.
- The servers on 3501 and 3502 were stopped after the run.

## Blocked
